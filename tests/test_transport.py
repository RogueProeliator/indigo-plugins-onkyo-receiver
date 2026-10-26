import logging
import queue
import socket
import struct
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from eiscp.core import command_to_packet
from receiver_transport import ReceiverTransport


def reply(message):
    body = ('!1' + message + '\x1a\r\n').encode()
    return struct.pack('!4sIIB3x', b'ISCP', 16, len(body), 1) + body


@pytest.fixture
def connection():
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen()
    listener.settimeout(3)
    messages, states = queue.Queue(), queue.Queue()
    receiver = ReceiverTransport(*listener.getsockname(), messages.put,
                                 lambda *args: states.put(args), logging.getLogger('test'),
                                 retry_min=.02, retry_max=.08)
    receiver.start()
    peer, _ = listener.accept()
    peer.settimeout(2)
    assert states.get(timeout=2)[0] is True
    yield receiver, peer, listener, messages, states
    receiver.close()
    peer.close()
    listener.close()
    assert not receiver._thread.is_alive()


def test_library_encoder():
    assert ReceiverTransport.packet('MVL2D') == command_to_packet('MVL2D')
    with pytest.raises(ValueError):
        ReceiverTransport.packet('MVL2D\rPWR01')


def test_fragmented_and_coalesced_frames():
    frames = reply('MVL2D') + reply('SLI2B')
    buffer = bytearray()
    results = []
    for byte in frames:
        buffer.append(byte)
        results.extend(ReceiverTransport.messages(buffer))
    assert results == ['MVL2D', 'SLI2B']
    assert not buffer
    assert ReceiverTransport.messages(bytearray(frames)) == results


@pytest.mark.parametrize('data', [b'BAD!' + bytes(12), struct.pack('!4sIIB3x', b'ISCP', 16, 1000000, 1),
                                  struct.pack('!4sIIB3x', b'ISCP', 16, 6, 9)])
def test_invalid_frames_rejected(data):
    with pytest.raises(ValueError):
        ReceiverTransport.messages(bytearray(data))


def test_push_without_any_query(connection):
    receiver, peer, _, messages, _ = connection
    peer.sendall(reply('MVL4B') + reply('ZVL2D'))
    assert messages.get(timeout=2) == 'MVL4B'
    assert messages.get(timeout=2) == 'ZVL2D'
    peer.settimeout(.1)
    with pytest.raises(socket.timeout):
        peer.recv(1024)  # Idle connection never polls state.
    assert receiver.generation == 1


def test_query_preserves_unrelated_pushes(connection):
    receiver, peer, _, messages, _ = connection
    with ThreadPoolExecutor() as pool:
        result = pool.submit(receiver.query, 'MVL', 1)
        assert b'MVLQSTN' in peer.recv(1024)
        peer.sendall(reply('SLI2B') + reply('MVL41'))
        assert result.result(timeout=2) == '41'
    assert messages.get(timeout=2) == 'SLI2B'
    assert messages.get(timeout=2) == 'MVL41'


def test_eof_reconnect_and_no_command_replay(connection):
    receiver, peer, listener, _, states = connection
    generation = receiver.generation
    peer.shutdown(socket.SHUT_RDWR)
    peer.close()
    assert states.get(timeout=2)[0] is False
    second, _ = listener.accept()
    try:
        assert states.get(timeout=2)[0] is True
        with pytest.raises(ConnectionError, match='earlier connection'):
            receiver.send('PWR01', generation=generation)
        second.settimeout(.1)
        with pytest.raises(socket.timeout):
            second.recv(1024)
        receiver.send('PWRQSTN')
        assert b'PWRQSTN' in second.recv(1024)
    finally:
        second.close()


def test_eof_releases_pending_query(connection):
    receiver, peer, _, _, _ = connection
    with ThreadPoolExecutor() as pool:
        result = pool.submit(receiver.query, 'MVL', 2)
        peer.recv(1024)
        peer.close()
        with pytest.raises(ConnectionError):
            result.result(timeout=1)


def test_timeout_invalidates_connection(connection):
    receiver, peer, listener, _, states = connection
    generation = receiver.generation
    with pytest.raises(TimeoutError):
        receiver.query('MVL', .05)
    assert states.get(timeout=1)[0] is False
    second, _ = listener.accept()
    try:
        assert states.get(timeout=1)[0] is True
        assert receiver.generation != generation
        assert peer.recv(1024)  # Only the original query was sent.
        assert peer.recv(1024) == b''
    finally:
        second.close()


def test_unsupported_reply(connection):
    receiver, peer, _, _, _ = connection
    with ThreadPoolExecutor() as pool:
        result = pool.submit(receiver.query, 'MVL', 1)
        peer.recv(1024)
        peer.sendall(reply('MVLN/A'))
        with pytest.raises(ValueError, match='does not support'):
            result.result(timeout=2)


def test_close_unblocks_query_and_rejects_sends(connection):
    receiver, peer, _, _, _ = connection
    with ThreadPoolExecutor() as pool:
        result = pool.submit(receiver.query, 'MVL', 2)
        peer.recv(1024)
        receiver.close()
        with pytest.raises(ConnectionError):
            result.result(timeout=1)
    with pytest.raises(ConnectionError):
        receiver.send('PWR01')


def test_failed_connect_backoff_and_cancellable_shutdown(monkeypatch):
    attempts = []
    def fail(*args, **kwargs):
        attempts.append(time.monotonic())
        raise ConnectionRefusedError('offline')
    monkeypatch.setattr(socket, 'create_connection', fail)
    receiver = ReceiverTransport('localhost', 1, lambda _: None, lambda *a: None,
                                 logging.getLogger('test'), retry_min=.03, retry_max=.06)
    receiver.start()
    time.sleep(.17)
    receiver.close()
    assert 3 <= len(attempts) <= 4
    assert attempts[1] - attempts[0] >= .025
    assert attempts[2] - attempts[1] >= .055
    assert not receiver._thread.is_alive()


def test_keepalive_enabled(connection):
    receiver, *_ = connection
    assert receiver._socket.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) == 1
