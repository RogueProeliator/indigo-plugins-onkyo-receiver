# Introduction
This Indigo plugin allows Indigo to act as a remote display and/or control for a network-connected Onkyo Receiver. All commands/buttons found on the standard remote can be sent to the receiver as well as many additional commands not readily available for direct access (normally requiring menu navigation). The status of many different aspects of the receiver is available via Indigo Device states.

[Plugin Store](https://www.indigodomo.com/pluginstore/104/) | [Full Documentation](https://github.com/RogueProeliator/indigo-plugins-onkyo-receiver/wiki) | [GitHub Repo](https://github.com/RogueProeliator/indigo-plugins-onkyo-receiver) | [Help Forum](http://forums.indigodomo.com/viewforum.php?f=146)

_**Latest Versions for Previous Indigo Releases**_  
[Plugin for Indigo 6 - 2022.1](https://github.com/RogueProeliator/indigo-plugins-onkyo-receiver/releases/tag/v2.0.0)
## Connection recovery and fresh replies

Each receiver has one TCP connection for both commands and unsolicited state updates.
The plugin uses `onkyo-eiscp` for discovery, command encoding and header decoding, and
owns the socket/thread lifecycle in `receiver_transport.py`. RPFramework remains the
Indigo integration layer. Neither dependency is patched or replaced globally.

EOF, socket errors, malformed frames and unanswered explicit queries close the connection,
mark the device disconnected and retry with exponential backoff (1–30 seconds).
A successful session that receives a message resets the backoff. TCP keepalive is enabled,
with a requested 30-second idle period, 10-second probe interval and three probes where
supported by the OS. Unsupported tuning is logged; OS defaults then apply. Keepalive
detects dead network peers, not a receiver application that still acknowledges TCP but
has stopped responding. A timed-out explicit query detects the latter when used.

After connecting, the plugin requests one read-only state snapshot. There is no recurring
status poll; the old `updateInterval` property is ignored. Normal remote-control changes
arrive as push messages. The existing Update Receiver Status action remains available for
manual refresh. Reconnect never sends power, source or volume settings and never replays
commands queued for a previous connection. Shutdown interrupts retries and closes the socket.

Volume and source replies accept the complete two-digit hexadecimal range, including
`MVL2D`, `ZVL4B` and `SLI2B`. Volume state values are raw receiver protocol units, not
percentages; physical volume scales vary by receiver. The existing standard volume action
and virtual-controller safety limits are retained. Arbitrary commands remain available for
models whose raw volume range exceeds the standard action's limit.

Two synchronous scripting actions use this same connection:

```python
import json
plugin = indigo.server.getPlugin('com.duncanware.onkyoNetworkRemote')
reply = json.loads(plugin.executeAction('queryReceiver', deviceId=receiver_id,
    props={'prefix': 'MVL', 'timeout': 3}, waitUntilDone=True))
# {'ok': True, 'value': '2D'} or {'ok': False, 'error': '...'}
```

`queryReceiver` accepts a three-letter prefix and a timeout greater than zero and at most
five seconds. It returns a matching reply received on the live connection, never cached
Indigo state or log text. Other received messages still update Indigo. Queries are serialized;
EOF/shutdown releases waiting callers. A query timeout invalidates the connection so a late
reply cannot satisfy the next query. eISCP has no request identifiers: a simultaneous push
for the queried property can satisfy the query; this is fresh receiver state, not proof of
which command caused it. Verify the returned value before treating a setting as applied.

`sendReceiverCommand`, with `props={'command': 'PWRQSTN'}`, reports whether a write succeeded
via `{'ok': True}` or an explicit error. Success means written to the socket, not confirmed
by the receiver. It does not queue commands while disconnected. Existing Indigo actions
keep their IDs and remain compatible.

## Development and tests

Clone with `--recurse-submodules` (RPFramework is pinned). Tests use local simulated receivers
and Indigo doubles, never household equipment. Run under Indigo's Python version (3.13):

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
.venv/bin/ruff check --select E9,F tests "src/Onkyo Network Remote.indigoPlugin/Contents/Server Plugin/receiver_transport.py"
```
