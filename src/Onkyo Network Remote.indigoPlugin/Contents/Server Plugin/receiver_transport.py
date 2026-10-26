"""One reconnecting eISCP connection. No application heartbeat or command replay."""
import re
import select
import socket
import sys
import threading
import time

from eiscp.core import command_to_packet, eISCPPacket


class ReceiverTransport:
    def __init__(self, host, port, on_message, on_connection, logger,
                 retry_min=1.0, retry_max=30.0):
        self.address = (host, port)
        self.on_message = on_message
        self.on_connection = on_connection
        self.logger = logger
        self.retry_min, self.retry_max = retry_min, retry_max
        self._lock = threading.RLock()
        self._query_lock = threading.Lock()
        self._stop = threading.Event()
        self._socket = None
        self._generation = 0
        self._pending = None
        self._thread = threading.Thread(target=self._run, name="Onkyo receiver", daemon=True)

    @property
    def generation(self):
        with self._lock:
            return self._generation if self._socket is not None else None

    def start(self):
        self._thread.start()

    def close(self):
        self._stop.set()
        self._disconnect("Stopped")
        if self._thread.is_alive() and threading.current_thread() is not self._thread:
            self._thread.join(timeout=5)
            if self._thread.is_alive():
                raise RuntimeError("Receiver thread did not stop")

    @staticmethod
    def packet(command):
        if not re.fullmatch(r"[A-Z0-9]+", command):
            raise ValueError("Expected an uppercase eISCP command")
        return command_to_packet(command)

    @staticmethod
    def messages(buffer):
        """Consume complete frames; preserve split headers and payloads."""
        result = []
        while len(buffer) >= 16:
            try:
                header = eISCPPacket.parse_header(bytes(buffer[:16]))
            except (AssertionError, UnicodeError) as exc:
                raise ValueError("Invalid eISCP frame header") from exc
            if header.version != 1 or not 3 <= header.data_size <= 65536:
                raise ValueError("Invalid eISCP frame size/version")
            total = header.header_size + header.data_size
            if len(buffer) < total:
                break
            payload = bytes(buffer[header.header_size:total])
            del buffer[:total]
            if not payload.startswith(b"!1"):
                raise ValueError("Invalid eISCP message")
            result.append(payload[2:].rstrip(b"\x1a\r\n\0").decode("utf-8", errors="replace"))
        return result

    def _keepalive(self, sock):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        # Darwin calls TCP_KEEPIDLE TCP_KEEPALIVE (0x10). Python does not
        # expose that name on every macOS build. These are kernel probes,
        # not eISCP state queries. Unsupported tuning retains OS defaults.
        idle = getattr(socket, "TCP_KEEPIDLE", 0x10 if sys.platform == "darwin" else None)
        for option, value in ((idle, 30), (getattr(socket, "TCP_KEEPINTVL", None), 10),
                              (getattr(socket, "TCP_KEEPCNT", None), 3)):
            if option is not None:
                try:
                    sock.setsockopt(socket.IPPROTO_TCP, option, value)
                except OSError as exc:
                    self.logger.warning(f"TCP keepalive tuning unavailable: {exc}")

    def _disconnect(self, reason, expected=None):
        with self._lock:
            if expected is not None and self._socket is not expected:
                return
            sock, self._socket = self._socket, None
            if self._pending is not None:
                self._pending["error"] = ConnectionError(reason)
                self._pending["event"].set()
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                sock.close()
        if sock is not None:
            self.on_connection(False, reason)

    def send(self, command, generation=None):
        packet = self.packet(command)
        with self._lock:
            sock = self._socket
            if sock is None or self._stop.is_set():
                raise ConnectionError("Receiver disconnected; command was not queued")
            if generation is not None and generation != self._generation:
                raise ConnectionError("Discarded command from an earlier connection")
            try:
                sock.sendall(packet)
            except OSError:
                self._disconnect("Send failed", expected=sock)
                raise

    def query(self, prefix, timeout=3.0):
        if not re.fullmatch(r"[A-Z]{3}", prefix) or not 0 < timeout <= 5:
            raise ValueError("Expected a three-letter prefix and timeout in (0, 5]")
        deadline = time.monotonic() + timeout
        if not self._query_lock.acquire(timeout=timeout):
            raise TimeoutError("Another receiver query is still running")
        pending = {"prefix": prefix, "event": threading.Event()}
        try:
            with self._lock:
                self._pending = pending
                sock = self._socket
                self.send(prefix + "QSTN")
            if not pending["event"].wait(max(0, deadline - time.monotonic())):
                # eISCP has no request IDs. Reconnect so a late reply cannot
                # accidentally confirm the next request for this prefix.
                self._disconnect("Query timed out", expected=sock)
                raise TimeoutError("No fresh receiver reply for " + prefix)
            if "error" in pending:
                raise pending["error"]
            return pending["value"]
        finally:
            with self._lock:
                self._pending = None
            self._query_lock.release()

    def _receive(self, sock, message):
        with self._lock:
            if self._socket is not sock:
                return
            pending = self._pending
            if pending is not None and message.startswith(pending["prefix"]) and not pending["event"].is_set():
                value = message[3:]
                if value == "N/A":
                    pending["error"] = ValueError("Receiver does not support " + pending["prefix"])
                else:
                    pending["value"] = value
                pending["event"].set()
        self.on_message(message)

    def _run(self):
        delay = self.retry_min
        while not self._stop.is_set():
            sock = None
            received = False
            try:
                sock = socket.create_connection(self.address, timeout=2)
                sock.settimeout(2)
                self._keepalive(sock)
                with self._lock:
                    if self._stop.is_set():
                        sock.close()
                        return
                    self._generation += 1
                    self._socket = sock
                self.on_connection(True, "Connected")
                buffer = bytearray()
                while not self._stop.is_set():
                    if not select.select([sock], [], [], 0.2)[0]:
                        continue
                    data = sock.recv(8192)
                    if not data:
                        raise ConnectionError("Receiver closed the connection")
                    buffer.extend(data)
                    for message in self.messages(buffer):
                        received = True
                        self._receive(sock, message)
            except (OSError, ValueError) as exc:
                if not self._stop.is_set():
                    self.logger.warning(f"Receiver connection lost: {exc}")
            except Exception:
                self.logger.exception("Receiver callback failed")
            finally:
                self._disconnect("Disconnected", expected=sock)
                if sock is not None:
                    sock.close()
            if received:
                delay = self.retry_min
            if self._stop.wait(delay):
                break
            delay = min(delay * 2, self.retry_max)
