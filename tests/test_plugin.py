"""Exercise the integration against small Indigo/framework doubles and real XML."""
import importlib
import json
import queue
import re
import sys
import threading
import types
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import Mock

import pytest

PLUGIN = Path(__file__).parents[1] / 'src/Onkyo Network Remote.indigoPlugin/Contents/Server Plugin'


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.setitem(sys.modules, 'indigo', types.ModuleType('indigo'))
    package = types.ModuleType('RPFramework')
    package.__path__ = [str(PLUGIN / 'RPFramework')]
    monkeypatch.setitem(sys.modules, 'RPFramework', package)
    for name, cls in [('RPFrameworkTelnetDevice', 'RPFrameworkTelnetDevice'),
                      ('RPFrameworkNonCommChildDevice', 'RPFrameworkNonCommChildDevice'),
                      ('RPFrameworkPlugin', 'RPFrameworkPlugin')]:
        module = types.ModuleType('RPFramework.' + name)
        base = type(cls, (), {'queue_device_command': lambda self, cmd: self.command_queue.put(cmd)})
        setattr(module, cls, base)
        monkeypatch.setitem(sys.modules, 'RPFramework.' + name, module)
    for name in ('onkyoNetworkRemoteDevice', 'plugin'):
        monkeypatch.delitem(sys.modules, name, raising=False)
    return importlib.import_module('onkyoNetworkRemoteDevice'), importlib.import_module('plugin')


def device(modules):
    mod, _ = modules
    dev = mod.OnkyoReceiverNetworkRemoteDevice.__new__(mod.OnkyoReceiverNetworkRemoteDevice)
    dev.indigoDevice = Mock(id=123, states={}, pluginProps={'ipAddress': 'localhost', 'portNumber': '12345'})
    dev.host_plugin = Mock()
    dev._processing_stop = threading.Event()
    dev.command_queue = queue.Queue()
    dev.concurrent_thread = None
    dev.onkyo_receiver = Mock(generation=7)
    return dev


@pytest.mark.parametrize('prefix,key', [('MVL', 'masterVolumeLevel'), ('ZVL', 'zone2VolumeLevel')])
@pytest.mark.parametrize('number', range(256))
def test_all_hex_volume_values(prefix, key, number):
    root = ET.parse(PLUGIN / 'RPFrameworkConfig.xml')
    response = next(r for r in root.findall('.//deviceResponses/response')
                    if prefix in (r.findtext('matchExpression') or ''))
    message = prefix + f'{number:02X}'
    assert re.search(response.findtext('matchExpression'), message)
    effect = next(e for e in response.findall('./effects/effect') if e.findtext('updateParam') == key)
    expression = effect.findtext('updateValueFormat').replace('%cp:response%', message)
    assert eval(expression, {'re': re}) == number
    assert re.search(response.findtext('matchExpression'), message + 'garbage') is None


def test_hex_input_callbacks(modules):
    dev = device(modules)
    dev.input_number_to_description = {'2B': 'Network'}
    dev.input_selector_query_received('SLI2B', None)
    dev.zone2_selector_query_received('SLZ2B', None)
    dev.indigoDevice.updateStateOnServer.assert_any_call(key='currentInputNumber', value='2B')
    dev.indigoDevice.updateStateOnServer.assert_any_call(key='zone2InputNumber', value='2B')


def test_command_generation_captured_at_enqueue(modules):
    mod, _ = modules
    dev = device(modules)
    cmd = mod.RPFrameworkCommand(mod.CMD_SEND_EISCP, command_payload='PWR01')
    dev.queue_device_command(cmd)
    assert cmd.connection_generation == 7
    dev.process_receiver_command(cmd)
    dev.onkyo_receiver.send.assert_called_once_with('PWR01', generation=7)
    dev.onkyo_receiver.generation = None
    dev.queue_device_command(cmd)
    with pytest.raises(ConnectionError):
        dev.process_receiver_command(cmd)


def test_connection_snapshot_and_shutdown_no_respawn(modules):
    mod, _ = modules
    dev = device(modules)
    dev.onkyo_connection_changed(True, 'Connected')
    dev.process_receiver_command(dev.command_queue.get_nowait())
    dev.host_plugin.execute_action.assert_called_once_with(None, indigoActionId='updateReceiverStatusFull',
                                                         indigoDeviceId=123, paramValues=None)
    dev.indigoDevice.updateStateOnServer.assert_any_call(key='isConnected', value=True)
    dev.terminate_communications()
    dev.onkyo_message_received('MVL41')
    dev.queue_device_command(mod.RPFrameworkCommand(mod.CMD_SEND_EISCP, command_payload='PWR01'))
    assert dev.command_queue.empty()
    assert dev.concurrent_thread is None


def test_api_returns_errors_and_values(modules):
    _, mod = modules
    obj = mod.Plugin.__new__(mod.Plugin)
    receiver = Mock()
    obj.managed_devices = {123: types.SimpleNamespace(onkyo_receiver=receiver)}
    action = types.SimpleNamespace(deviceId=123, props={'prefix': 'MVL', 'timeout': 2})
    receiver.query.return_value = '2D'
    assert json.loads(obj.query_receiver(action)) == {'ok': True, 'value': '2D'}
    receiver.query.side_effect = TimeoutError('missing reply')
    assert json.loads(obj.query_receiver(action)) == {'ok': False, 'error': 'missing reply'}
    action.props = {'command': 'MVL2D'}
    assert json.loads(obj.send_receiver_command(action)) == {'ok': True}
    receiver.send.side_effect = ConnectionError('offline')
    assert json.loads(obj.send_receiver_command(action))['ok'] is False


def test_snapshot_contains_only_queries():
    commands = ET.parse(PLUGIN / 'RPFrameworkConfig.xml').findall(".//action[@indigoId='updateReceiverStatusFull']/commands/command")
    assert commands
    assert all(c.findtext('commandFormat').endswith('QSTN') for c in commands)
