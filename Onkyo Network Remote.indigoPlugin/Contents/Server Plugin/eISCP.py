import re
import struct
import time
import socket, select
import Queue, threading
#from collections import namedtuple

import eISCPCommands

from operator import itemgetter as _itemgetter
from keyword import iskeyword as _iskeyword
import sys as _sys

def namedtuple(typename, field_names, verbose=False, rename=False):
    """Returns a new subclass of tuple with named fields.

    >>> Point = namedtuple('Point', 'x y')
    >>> Point.__doc__                   # docstring for the new class
    'Point(x, y)'
    >>> p = Point(11, y=22)             # instantiate with positional args or keywords
    >>> p[0] + p[1]                     # indexable like a plain tuple
    33
    >>> x, y = p                        # unpack like a regular tuple
    >>> x, y
    (11, 22)
    >>> p.x + p.y                       # fields also accessable by name
    33
    >>> d = p._asdict()                 # convert to a dictionary
    >>> d['x']
    11
    >>> Point(**d)                      # convert from a dictionary
    Point(x=11, y=22)
    >>> p._replace(x=100)               # _replace() is like str.replace() but targets named fields
    Point(x=100, y=22)

    """

    # Parse and validate the field names.  Validation serves two purposes,
    # generating informative error messages and preventing template injection attacks.
    if isinstance(field_names, basestring):
        field_names = field_names.replace(',', ' ').split() # names separated by whitespace and/or commas
    field_names = tuple(map(str, field_names))
    if rename:
        names = list(field_names)
        seen = set()
        for i, name in enumerate(names):
            if (not min(c.isalnum() or c=='_' for c in name) or _iskeyword(name)
                or not name or name[0].isdigit() or name.startswith('_')
                or name in seen):
                    names[i] = '_%d' % i
            seen.add(name)
        field_names = tuple(names)
    for name in (typename,) + field_names:
        if not min(c.isalnum() or c=='_' for c in name):
            raise ValueError('Type names and field names can only contain alphanumeric characters and underscores: %r' % name)
        if _iskeyword(name):
            raise ValueError('Type names and field names cannot be a keyword: %r' % name)
        if name[0].isdigit():
            raise ValueError('Type names and field names cannot start with a number: %r' % name)
    seen_names = set()
    for name in field_names:
        if name.startswith('_') and not rename:
            raise ValueError('Field names cannot start with an underscore: %r' % name)
        if name in seen_names:
            raise ValueError('Encountered duplicate field name: %r' % name)
        seen_names.add(name)

    # Create and fill-in the class template
    numfields = len(field_names)
    argtxt = repr(field_names).replace("'", "")[1:-1]   # tuple repr without parens or quotes
    reprtxt = ', '.join('%s=%%r' % name for name in field_names)
    template = '''class %(typename)s(tuple):
        '%(typename)s(%(argtxt)s)' \n
        __slots__ = () \n
        _fields = %(field_names)r \n
        def __new__(_cls, %(argtxt)s):
            return _tuple.__new__(_cls, (%(argtxt)s)) \n
        @classmethod
        def _make(cls, iterable, new=tuple.__new__, len=len):
            'Make a new %(typename)s object from a sequence or iterable'
            result = new(cls, iterable)
            if len(result) != %(numfields)d:
                raise TypeError('Expected %(numfields)d arguments, got %%d' %% len(result))
            return result \n
        def __repr__(self):
            return '%(typename)s(%(reprtxt)s)' %% self \n
        def _asdict(self):
            'Return a new dict which maps field names to their values'
            return dict(zip(self._fields, self)) \n
        def _replace(_self, **kwds):
            'Return a new %(typename)s object replacing specified fields with new values'
            result = _self._make(map(kwds.pop, %(field_names)r, _self))
            if kwds:
                raise ValueError('Got unexpected field names: %%r' %% kwds.keys())
            return result \n
        def __getnewargs__(self):
            return tuple(self) \n\n''' % locals()
    for i, name in enumerate(field_names):
        template += '        %s = _property(_itemgetter(%d))\n' % (name, i)
    if verbose:
        print template

    # Execute the template string in a temporary namespace
    namespace = dict(_itemgetter=_itemgetter, __name__='namedtuple_%s' % typename,
                     _property=property, _tuple=tuple)
    try:
        exec template in namespace
    except SyntaxError, e:
        raise SyntaxError(e.message + ':\n' + template)
    result = namespace[typename]

    # For pickling to work, the __module__ variable needs to be set to the frame
    # where the named tuple is created.  Bypass this step in enviroments where
    # sys._getframe is not defined (Jython for example) or sys._getframe is not
    # defined for arguments greater than 0 (IronPython).
    try:
        result.__module__ = _sys._getframe(1).f_globals.get('__name__', '__main__')
    except (AttributeError, ValueError):
        pass

    return result


class ISCPMessage(object):
    """Deals with formatting and parsing data wrapped in an ISCP
    containers. The docs say:

        ISCP (Integra Serial Control Protocol) consists of three
        command characters and parameter character(s) of variable
        length.

    It seems this was the original protocol used for communicating
    via a serial cable.
    """

    def __init__(self, data):
        self.data = data

    def __str__(self):
        # ! = start character
        # 1 = destination unit type, 1 means receiver
        # End character may be CR, LF or CR+LF, according to doc
        return '!1%s\r' % self.data

    @classmethod
    def parse(self, data):
        EOF = '\x1a'
        TERMINATORS = ['\n', '\r']
        assert data[:2] == '!1'
                
        # EOF can be followed by CR/LF/CR+LF
        eof_offset = -1
        if data[eof_offset] in TERMINATORS:
          eof_offset -= 1
          if data[eof_offset] in TERMINATORS:
            eof_offset -= 1
        assert data[eof_offset] == EOF
        return data[2:eof_offset]


class eISCPPacket(object):
    """For communicating over Ethernet, traditional ISCP messages are
    wrapped inside an eISCP package.
    """

    header = namedtuple('header', (
        'magic, header_size, data_size, version, reserved'))

    def __init__(self, iscp_message):
        iscp_message = str(iscp_message)
        # We attach data separately, because Python's struct module does
        # not support variable length strings,
        header = struct.pack(
            '! 4s I I b 3b',
            'ISCP',             # magic
            16,                 # header size (16 bytes)
            len(iscp_message),  # data size
            0x01,               # version
            0x00, 0x00, 0x00    # reserved
        )

        self._bytes = "%s%s" % (header, iscp_message)
        # __new__, string subclass?

    def __str__(self):
        return self._bytes

    @classmethod
    def parse(cls, bytes):
        """Parse the eISCP package given by ``bytes``.
        """
        h = cls.parse_header(bytes[:16])
        data = bytes[h.header_size:h.header_size + h.data_size]
        assert len(data) == h.data_size
        return data

    @classmethod
    def parse_header(self, bytes):
        """Parse the header of an eISCP package.

        This is useful when reading data in a streaming fashion,
        because you can subsequently know the number of bytes to
        expect in the packet.
        """
        # A header is always 16 bytes in length
        assert len(bytes) == 16

        # Parse the header
        magic, header_size, data_size, version, reserved = \
            struct.unpack('! 4s I I b 3s', bytes)

        # Strangly, the header contains a header_size field.
        assert magic == 'ISCP'
        assert header_size == 16

        return eISCPPacket.header(
            magic, header_size, data_size, version, reserved)


def command_to_packet(command):
    """Convert an ascii command like (PVR00) to the binary data we
    need to send to the receiver.
    """
    return str(eISCPPacket(ISCPMessage(command)))


def normalize_command(command):
    """Ensures that various ways to refer to a command can be used."""
    command = command.lower()
    command = command.replace('_', ' ')
    command = command.replace('-', ' ')
    return command


def command_to_iscp(command, arguments=None, zone=None):
    """Transform the given given high-level command to a
    low-level ISCP message.

    Raises :class:`ValueError` if `command` is not valid.

    This exposes a system of human-readable, "pretty"
    commands, which is organized into three parts: the zone, the
    command, and arguments. For example::

        command('power', 'on')
        command('power', 'on', zone='main')
        command('volume', 66, zone='zone2')

    As you can see, if no zone is given, the main zone is assumed.

    Instead of passing three different parameters, you may put the
    whole thing in a single string, which is helpful when taking
    input from users::

        command('power on')
        command('zone2 volume 66')

    To further simplify things, for example when taking user input
    from a command line, where whitespace needs escaping, the
    following is also supported:

        command('power=on')
        command('zone2.volume=66')
    """
    default_zone = 'main'
    command_sep = r'[. ]'
    norm = lambda s: s.strip().lower()

    # If parts are not explicitly given, parse the command
    if arguments is None and zone is None:
        # Separating command and args with colon allows multiple args
        if ':' in command or '=' in command:
            base, arguments = re.split(r'[:=]', command, 1)
            parts = [norm(c) for c in re.split(command_sep, base)]
            if len(parts) == 2:
                zone, command = parts
            else:
                zone = default_zone
                command = parts[0]
            # Split arguments by comma or space
            arguments = [norm(a) for a in re.split(r'[ ,]', arguments)]
        else:
            # Split command part by space or dot
            parts = [norm(c) for c in re.split(command_sep, command)]
            if len(parts) >= 3:
                zone, command = parts[:2]
                arguments = parts[3:]
            elif len(parts) == 2:
                zone = default_zone
                command = parts[0]
                arguments = parts[1:]
            else:
                raise ValueError('Need at least command and argument')

    # Find the command in our database, resolve to internal eISCP command
    group = eISCPCommands.ZONE_MAPPINGS.get(zone, zone)
    if not zone in eISCPCommands.COMMANDS:
        raise ValueError('"%s" is not a valid zone' % zone)

    prefix = eISCPCommands.COMMAND_MAPPINGS[group].get(command, command)
    if not prefix in eISCPCommands.COMMANDS[group]:
        raise ValueError('"%s" is not a valid command in zone "%s"'
                % (command, zone))

    # Resolve the argument to the command. This is a bit more involved,
    # because some commands support ranges (volume) or patterns
    # (setting tuning frequency). In some cases, we might imagine
    # providing the user an API with multiple arguments (TODO: not
    # currently supported).
    argument = arguments[0]

    # 1. Consider if there is a alias, e.g. level-up for UP.
    try:
        value = eISCPCommands.VALUE_MAPPINGS[group][prefix][argument]
    except KeyError:
        # 2. See if we can match a range or pattern
        for possible_arg in eISCPCommands.VALUE_MAPPINGS[group][prefix]:
            if argument.isdigit():
                if isinstance(possible_arg, xrange):
                    if int(argument) in possible_arg:
                        # We need to send the format "FF", hex() gives us 0xff
                        value = hex(int(argument))[2:].zfill(2).upper()
                    break

            # TODO: patterns not yet supported
        else:
            raise ValueError('"%s" is not a valid argument for command '
                             '"%s" in zone "%s"' % (argument, command, zone))

    return '%s%s' % (prefix, value)


def iscp_to_command(iscp_message):
    for zone, zone_cmds in eISCPCommands.COMMANDS.iteritems():
        # For now, ISCP commands are always three characters, which
        # makes this easy.
        command, args = iscp_message[:3], iscp_message[3:]
        if command in zone_cmds:
            if args in zone_cmds[command]['values']:
                return zone_cmds[command]['name'], \
                       zone_cmds[command]['values'][args]['name']
            else:
                match = re.match('[+-]?[0-9a-f]$', args, re.IGNORECASE)
                if match:
                    return zone_cmds[command]['name'], \
                             int(args, 16)
                else:
                    return zone_cmds[command]['name'], args

    else:
        raise ValueError(
            'Cannot convert ISCP message to command: %s' % iscp_message)


def filter_for_message(getter_func, msg):
    """Helper that calls ``getter_func`` until a matching message
    is found, or the timeout occurs. Matching means the same commands
    group, i.e. for sent message MVLUP we would accept MVL13
    in response."""
    start = time.time()
    while True:
        candidate = getter_func(0.05)
        # It seems ISCP commands are always three characters.
        if candidate and candidate[:3] == msg[:3]:
            return candidate
        # The protocol docs claim that a response  should arrive
        # within *50ms or the communication has failed*. In my tests,
        # however, the interval needed to be at least 200ms before
        # I managed to see any response, and only after 300ms
        # reproducably, so use a generous timeout.
        if time.time() - start > 5.0:
            raise ValueError('Timeout waiting for response.')


class eISCP(object):
    """Implements the eISCP interface to Onkyo receivers.

    This uses a blocking interface. The remote end will regularily
    send unsolicited status updates. You need to manually call
    ``get_message`` to query those.

    You may want to look at the :meth:`Receiver` class instead, which
    uses a background thread.
    """

    @classmethod
    def discover(cls, timeout=5, clazz=None):
        """Try to find ISCP devices on network.

        Waits for ``timeout`` seconds, then returns all devices found,
        in form of a list of dicts.
        """
        onkyo_port = 60128
        onkyo_magic = str(eISCPPacket('!xECNQSTN'))

        # Broadcast magic
        sock = socket.socket(
            socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        sock.setblocking(0)   # So we can use select()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(('0.0.0.0', 0))
        sock.sendto(onkyo_magic, ('255.255.255.255', onkyo_port))

        found_receivers = []
        while True:
            ready = select.select([sock], [], [], timeout)
            if not ready[0]:
                break
            data, addr = sock.recvfrom(1024)

            response = eISCPPacket.parse(data)
            # Return string looks something like this:
            # !1ECNTX-NR609/60128/DX
            info = re.match(r'''
                !
                (?P<device_category>\d)
                ECN
                (?P<model_name>[^/]*)/
                (?P<iscp_port>\d{5})/
                (?P<area_code>\w{2})/
                (?P<identifier>.{0,12})
            ''', response.strip(), re.VERBOSE).groupdict()

            # Give the user a ready-made receiver instance. It will only
            # connect on demand, when actually used.
            receiver = (clazz or eISCP)(addr[0], int(info['iscp_port']))
            receiver.info = info
            found_receivers.append(receiver)

        sock.close()
        return found_receivers

    def __init__(self, host, port=60128):
        self.host = host
        self.port = port

        self.command_socket = None

    def __repr__(self):
        if getattr(self, 'info', False) and self.info.get('model_name'):
            model = self.info['model_name']
        else:
            model = 'unknown'
        string = "<%s(%s) %s:%s>" % (
            self.__class__.__name__, model, self.host, self.port)
        return string

    def _ensure_socket_connected(self):
        if self.command_socket is None:
            self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.command_socket.connect((self.host, self.port))
            self.command_socket.setblocking(0)

    def disconnect(self):
        try:
            self.command_socket.close()
        except:
            pass
        self.command_socket = None

    def __enter__(self):
        self._ensure_socket_connected()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def send(self, iscp_message):
        """Send a low-level ISCP message, like ``MVL50``.

        This does not return anything, nor does it wait for a response
        from the receiver. You can query responses via :meth:`get`,
        or use :meth:`raw` to send a message and waiting for one.
        """
        self._ensure_socket_connected()
        self.command_socket.send(command_to_packet(iscp_message))

    def get(self, timeout=0.1):
        """Return the next message sent by the receiver, or, after
        ``timeout`` has passed, return ``None``.
        """
        self._ensure_socket_connected()

        ready = select.select([self.command_socket], [], [], timeout or 0)
        if ready[0]:
            header_bytes = self.command_socket.recv(16)
            header = eISCPPacket.parse_header(header_bytes)
            message = self.command_socket.recv(header.data_size)
            return ISCPMessage.parse(message)

    def raw(self, iscp_message):
        """Send a low-level ISCP message, like ``MVL50``, and wait
        for a response.

        While the protocol is designed to acknowledge each message with
        a response, there is no fool-proof way to differentiate those
        from unsolicited status updates, though we'll do our best to
        try. Generally, this won't be an issue, though in theory the
        response this function returns to you sending ``SLI05`` may be
        an ``SLI06`` update from another controller.

        It'd be preferable to design your app in a way where you are
        processing all incoming messages the same way, regardless of
        their origin.
        """
        while self.get(False):
            # Clear all incoming messages. If not yet queried,
            # they are lost. This is so that we can find the real
            # response to our sent command later.
            pass
        self.send(iscp_message)
        return filter_for_message(self.get, iscp_message)

    def command(self, command, arguments=None, zone=None):
        """Send a high-level command to the receiver, return the
        receiver's response formatted has a command.

        This is basically a helper that combines :meth:`raw`,
        :func:`command_to_iscp` and :func:`iscp_to_command`.
        """
        iscp_message = command_to_iscp(command, arguments, zone)
        response = self.raw(iscp_message)
        if response:
            return iscp_to_command(response)

    def power_on(self):
        """Turn the receiver power on."""
        return self.command('power', 'on')

    def power_off(self):
        """Turn the receiver power off."""
        return self.command('power', 'off')
