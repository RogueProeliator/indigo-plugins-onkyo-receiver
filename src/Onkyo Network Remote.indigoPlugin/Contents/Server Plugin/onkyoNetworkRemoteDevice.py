#! /usr/bin/env python
# -*- coding: utf-8 -*-
#######################################################################################
# Onkyo Network Remote Control by RogueProeliator <rp@rogueproeliator.com>
#######################################################################################

# region Python imports
import re
import queue
import threading

import indigo
from RPFramework.RPFrameworkTelnetDevice import RPFrameworkTelnetDevice
from RPFramework.RPFrameworkNonCommChildDevice import RPFrameworkNonCommChildDevice
from RPFramework.RPFrameworkCommand import RPFrameworkCommand
from receiver_transport import ReceiverTransport
# endregion

#######################################################################################
# region Constants and configuration variables
CMD_SEND_EISCP        = "sendEISCPCommand"
CMD_DIRECT_TUNE       = "directTune"
CMD_DIRECT_TUNE_ZONE2 = "directTuneZone2"
CMD_PROCESS_MESSAGE   = "processMessage"
# endregion
#######################################################################################


class OnkyoReceiverNetworkRemoteDevice(RPFrameworkTelnetDevice):

	#######################################################################################
	# region Class construction and destruction methods
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super().__init__(plugin, device, connection_type=RPFrameworkTelnetDevice.CONNECTIONTYPE_SOCKET)

		self.input_number_to_description = {
			"00" : "VIDEO1, VCR/DVR",
			"01" : "VIDEO2, CBL/SAT",
			"02" : "VIDEO3, GAME/TV, GAME",
			"03" : "VIDEO4, AUX1(AUX)",
			"04" : "VIDEO5, AUX2",
			"05" : "VIDEO6, PC",
			"06" : "VIDEO7",
			"07" : "Hidden1",
			"08" : "Hidden2",
			"09" : "Hidden3",
			"10" : "DVD, BD/DVD",
			"11" : "STRMBOX",
			"12" : "TV",
			"20" : "TAPE(1), TV/TAPE",
			"21" : "TAPE2",
			"22" : "PHONO",
			"23" : "CD, TV/CD",
			"24" : "FM",
			"25" : "AM",
			"26" : "TUNER",
			"27" : "MUSIC SERVER, P4S, DLNA",
			"28" : "INTERNET RADIO",
			"29" : "USB/USB(Front)",
			"2A" : "USB(Rear)",
			"2B" : "NETWORK, NET",
			"2C" : "USB(toggle)",
			"30" : "MULTI CH",
			"31" : "XM",
			"32" : "SIRIUS",
			"40" : "Universal PORT" }

		self.video_resolution_map = {
			"00" : "Through",
			"01" : "Auto",
			"02" : "480p",
			"03" : "720p",
			"13" : "1680x720p",
			"04" : "1080i",
			"05" : "1080p",
			"07" : "1080p/24fps",
			"15" : "2560x1080p",
			"08" : "4K",
			"06" : "Source"
		}

		self.video_widescreenmode_map = {
			"00" : "Auto",
			"01" : "4:3",
			"02" : "Full",
			"03" : "Zoom",
			"04" : "Wide Zoom",
			"05" : "Smart Zoom"
		}

		self.video_picturemode_map = {
			"00" : "Through",
			"01" : "Custom",
			"02" : "Cinema",
			"03" : "Game",
			"05" : "ISF Day",
			"06" : "ISF Night",
			"07" : "Streaming",
			"08" : "Direct Bypass"
		}

		self.listening_mode_map = {
			'05': 'action',
			'0C': 'all-ch-stereo',
			'16': 'audyssey-dsx',
			'50': 'cinema2',
			'01': 'direct',
			'41': 'dolby-ex',
			'A7': 'dolby-ex-audyssey-dsx',
			'14': 'dolby-virtual',
			'DOWN': 'down',
			'15': 'dts-surround-sensation',
			'0E': 'enhance',
			'03': 'film',
			'13': 'full-mono',
			'GAME': 'game',
			'06': 'game-rock/musical',
			'52': 'i',
			'0F': 'mono',
			'07': 'mono-movie',
			'MOVIE': 'movie',
			'12': 'multiplex',
			'MUSIC': 'music',
			'8C': 'neo-6',
			'82': 'neo-6-cinema',
			'A3': 'neo-6-cinema-audyssey-dsx',
			'91': 'neo-6-cinema-dts-surround-sensation',
			'83': 'neo-6-music',
			'A4': 'neo-6-music-audyssey-dsx',
			'92': 'neo-6-music-dts-surround-sensation',
			'9A': 'neo-x-game',
			'85': 'neo-x-thx-cinema',
			'8A': 'neo-x-thx-games',
			'93': 'neural-digital-music',
			'A6': 'neural-digital-music-audyssey-dsx',
			'87': 'neural-surr',
			'88': 'neural-surround/thx',
			'A5': 'neural-surround-audyssey-dsx',
			'8D': 'neural-thx-cinema',
			'8F': 'neural-thx-games',
			'8E': 'neural-thx-music',
			'08': 'orchestra',
			'8B': 'plii',
			'A2': 'plii-game-audyssey-dsx',
			'A0': 'plii-movie-audyssey-dsx',
			'A1': 'plii-music-audyssey-dsx',
			'86': 'pliix-game',
			'80': 'pliix-movie',
			'81': 'pliix-music',
			'84': 'pliix-thx-cinema',
			'89': 'pliix-thx-games',
			'90': 'pliiz-height',
			'94': 'pliiz-height-thx-cinema',
			'96': 'pliiz-height-thx-games',
			'95': 'pliiz-height-thx-music',
			'99': 's2-games/pliiz-height-thx-u2',
			'11': 'pure-audio',
			'51': 's-music',
			'97': 's2-cinema',
			'98': 's2-music',
			'00': 'stereo',
			'40': 'straight-decode',
			'0A': 'studio-mix',
			'02': 'surround',
			'0D': 'theater-dimensional',
			'04': 'thx',
			'42': 'thx-cinema',
			'44': 'thx-music',
			'43': 'thx-surround-ex',
			'0B': 'tv-logic',
			'09': 'unplugged',
			'1F': 'whole-house'
		}

		self.onkyo_receiver = None
		self._processing_stop = threading.Event()
		
		# record the new states that have been added so that the device will automatically reload the
		# state list from the Devices.xml
		self.upgraded_device_states.append("zone2PoweredOn")
		self.upgraded_device_states.append("zone2InputNumber")
		self.upgraded_device_states.append("zone2InputLabel")
		self.upgraded_device_states.append("zone2VolumeLevel")
		self.upgraded_device_states.append("tunerFrequency")
		self.upgraded_device_states.append("networkPlayTitle")
		self.upgraded_device_states.append("networkPlayAlbum")
		self.upgraded_device_states.append("networkPlayArtist")
		self.upgraded_device_states.append("networkPlayStatus")

	# endregion
	#######################################################################################
		
	#######################################################################################
	# region Processing and command functions
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is designed to run in a concurrent thread and will continuously monitor
	# the commands queue for work to do.
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def initiate_communications(self, initialize_connect=True):
		if self._processing_stop.is_set():
			while not self.command_queue.empty():
				self.command_queue.get_nowait()
				self.command_queue.task_done()
		self._processing_stop.clear()
		super().initiate_communications(initialize_connect)

	def terminate_communications(self):
		# Cooperative cancellation also interrupts command pauses and reconnect waits.
		self._processing_stop.set()
		if self.onkyo_receiver is not None:
			self.onkyo_receiver.close()
		if self.concurrent_thread is not None:
			self.concurrent_thread.join(timeout=6)
			if self.concurrent_thread.is_alive():
				raise RuntimeError("Onkyo command thread did not stop")
		self.concurrent_thread = None

	def queue_device_command(self, command):
		if self._processing_stop.is_set():
			return
		if command.command_name in (CMD_SEND_EISCP, CMD_DIRECT_TUNE, CMD_DIRECT_TUNE_ZONE2):
			command.connection_generation = self.onkyo_receiver.generation if self.onkyo_receiver else None
		super().queue_device_command(command)

	def onkyo_connection_changed(self, connected, reason):
		# Never start an RPFramework thread from a socket callback during shutdown.
		self.command_queue.put(RPFrameworkCommand("connectionChanged", command_payload=(connected, reason)))

	def update_connection_state(self, connected, reason):
		self.indigoDevice.updateStateOnServer(key="isConnected", value=connected)
		self.indigoDevice.updateStateOnServer(key="connectionState", value="Connected" if connected else "Disconnected")
		self.indigoDevice.setErrorStateOnServer(None if connected else "disconnected")
		self.host_plugin.logger.info(f"Receiver connection: {reason}")

	def concurrent_command_processing_thread(self, command_queue):
		try:
			self.update_connection_state(False, "Starting")
			while not self._processing_stop.is_set():
				try:
					command = command_queue.get(timeout=0.2)
				except queue.Empty:
					continue
				try:
					self.process_receiver_command(command)
				except (OSError, ValueError) as exc:
					self.host_plugin.logger.warning(f"Receiver command rejected: {exc}")
				finally:
					command_queue.task_done()
				self._processing_stop.wait(max(0, command.post_command_pause))
		except Exception:
			self.host_plugin.logger.exception("Exception in background processing")
		finally:
			self._processing_stop.set()
			if self.onkyo_receiver is not None:
				self.onkyo_receiver.close()
			self.update_connection_state(False, "Stopped")

	def process_receiver_command(self, command):
		name = command.command_name
		if name == RPFrameworkCommand.CMD_INITIALIZE_CONNECTION:
			if self.onkyo_receiver is not None:
				self.onkyo_receiver.close()
			host, port = self.get_device_address_info()
			self.onkyo_receiver = ReceiverTransport(host, port, self.onkyo_message_received,
				self.onkyo_connection_changed, self.host_plugin.logger)
			self.onkyo_receiver.start()
		elif name == "connectionChanged":
			connected, reason = command.command_payload
			self.update_connection_state(connected, reason)
			if connected and self.onkyo_receiver.generation is not None:
				# One read-only snapshot after each connection. Subsequent state
				# changes arrive as receiver pushes; no recurring status queries.
				self.host_plugin.execute_action(None, indigoActionId="updateReceiverStatusFull",
					indigoDeviceId=self.indigoDevice.id, paramValues=None)
		elif name == RPFrameworkCommand.CMD_TERMINATE_PROCESSING_THREAD:
			self._processing_stop.set()
		elif name == RPFrameworkCommand.CMD_PAUSE_PROCESSING:
			self._processing_stop.wait(max(0, float(command.command_payload)))
		elif name == RPFrameworkCommand.CMD_UPDATE_DEVICE_STATUS_FULL:
			self.host_plugin.execute_action(None, indigoActionId="updateReceiverStatusFull",
				indigoDeviceId=self.indigoDevice.id, paramValues=None)
		elif name == RPFrameworkCommand.CMD_UPDATE_DEVICE_STATE:
			match = re.fullmatch(r'\{ds:([a-zA-Z\d]+)\}\{(.+)\}', command.command_payload)
			if match is None:
				raise ValueError("Invalid device state update")
			value = match.group(2)
			if value.startswith("eval:"):
				value = eval(value[5:])
			self.indigoDevice.updateStateOnServer(key=match.group(1), value=value)
		elif name in (CMD_SEND_EISCP, CMD_DIRECT_TUNE, CMD_DIRECT_TUNE_ZONE2):
			generation = getattr(command, "connection_generation", None)
			if generation is None or self.onkyo_receiver is None:
				raise ConnectionError("Receiver was disconnected when command was queued")
			payload = command.command_payload
			if name != CMD_SEND_EISCP:
				if "." in payload:
					whole, fraction = payload.split(".")
					payload = whole.rjust(3, "0") + fraction.ljust(2, "0")
				else:
					payload = payload.rjust(5, "0")
				payload = ("TUZ" if name == CMD_DIRECT_TUNE_ZONE2 else "TUN") + payload
			self.host_plugin.logger.debug(f"Sending command: {payload}")
			self.onkyo_receiver.send(payload, generation=generation)
		elif name == CMD_PROCESS_MESSAGE and command.command_payload:
			self.handle_device_response(command.command_payload, None)

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should return a tuple of information about the connection - in the
	# format of (ipAddress/HostName, portNumber)
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def get_device_address_info(self):
		return self.indigoDevice.pluginProps.get("ipAddress", ""), int(self.indigoDevice.pluginProps.get("portNumber", "60128"))

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Called whenever the Onkyo device has sent a message to the socket... this needs to
	# queue the message up for processing, not process it in a blocking manner
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def onkyo_message_received(self, message):
		self.host_plugin.logger.threaddebug(f"Received: {message}")
		if not self._processing_stop.is_set():
			self.command_queue.put(RPFrameworkCommand(CMD_PROCESS_MESSAGE, command_payload=message))

	# endregion
	#######################################################################################
		
	#######################################################################################
	# region Custom Response Handlers
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for the receiver
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def input_selector_query_received(self, response_obj, rp_command):
		value_splitter   = re.compile(r"^SLI(?P<value>[0-9A-F]{2})$")
		value_match      = value_splitter.search(response_obj)
		input_value      = value_match.groupdict().get("value")
		input_definition = self.parse_eiscp_input_definition(input_value)
		
		# update the two "current inputs" on the server...
		self.indigoDevice.updateStateOnServer(key="currentInputNumber", value=input_value)
		self.indigoDevice.updateStateOnServer(key="currentInputLabel", value=input_definition)
		self.host_plugin.logger.debug(f"Updating current input number/label: {input_value} / {input_definition}")
		
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for Zone 2 of the receiver
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def zone2_selector_query_received(self, response_obj, rp_command):
		value_splitter   = re.compile(r"^SLZ(?P<value>[0-9A-F]{2})$")
		value_match      = value_splitter.search(response_obj)
		input_value      = value_match.groupdict().get("value")
		input_definition = self.parse_eiscp_input_definition(input_value)
		
		# update the two "current inputs" on the server...
		self.indigoDevice.updateStateOnServer(key="zone2InputNumber", value=input_value)
		self.indigoDevice.updateStateOnServer(key="zone2InputLabel", value=input_definition)
		self.host_plugin.logger.debug(f"Updating zone 2 input number/label: {input_value} / {input_definition}")
	
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Master Volume has been
	# found; it should update any virtual controllers attached
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def update_virtual_master_volume(self, response_obj, rp_command):
		if "main" in self.child_devices:
			# find the child device and ensure we have the latest version of the states
			volume_controller = self.child_devices["main"]
			volume_controller.reload_indigo_device()
			
			# update the volume of the virtual controller if it is different than the master...
			if volume_controller.indigoDevice.states.get("brightnessLevel", 0) != self.indigoDevice.states.get("masterVolumeLevel", 0):
				self.host_plugin.logger.debug(f"Setting Master Volume Virtual Controller brightness to {self.indigoDevice.states.get('masterVolumeLevel', 0)}")
				volume_controller.indigoDevice.updateStateOnServer(key="brightnessLevel", value=self.indigoDevice.states.get("masterVolumeLevel", 0))

			# determine the on/off state for the controller
			is_on = self.indigoDevice.states.get("isPoweredOn", False) and not self.indigoDevice.states.get("isMuted", True) and self.indigoDevice.states.get("masterVolumeLevel", 0) > 0
			if volume_controller.indigoDevice.states.get("onOffState", False) != is_on:
				self.host_plugin.logger.debug(f"Setting On/Off state to: {is_on}")
				volume_controller.indigoDevice.updateStateOnServer(key="onOffState", value=is_on)
					
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Zone 2 Volume has been
	# found; it should update any virtual controllers attached
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def update_virtual_zone2_volume(self, response_obj, rp_command):
		if "zone2" in self.child_devices:
			# find the child device and ensure we have the latest version of the states
			volume_controller = self.child_devices["zone2"]
			volume_controller.reload_indigo_device()
			
			# update the volume of the virtual controller if it is different from the master...
			if volume_controller.indigoDevice.states.get("brightnessLevel", 0) != self.indigoDevice.states.get("zone2VolumeLevel", 0):
				self.host_plugin.logger.debug(f"Setting Zone 2 Volume Virtual Controller brightness to {self.indigoDevice.states.get('zone2VolumeLevel', 0)}")
				volume_controller.indigoDevice.updateStateOnServer(key="brightnessLevel", value=self.indigoDevice.states.get("zone2VolumeLevel", 0))

			# determine the on/off state for the controller
			is_on = self.indigoDevice.states.get("zone2PoweredOn", False) and not self.indigoDevice.states.get("isMuted", True) and self.indigoDevice.states.get("zone2VolumeLevel", 0) > 0
			if volume_controller.indigoDevice.states.get("onOffState", False) != is_on:
				self.host_plugin.logger.debug(f"Setting On/Off state to: {is_on}")
				volume_controller.indigoDevice.updateStateOnServer(key="onOffState", value=is_on)

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Video Out resolution has
	# been received; this will convert the number to the text equivalent
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def video_resolution_response_received(self, response_obj, rp_command):
		self.response_to_mapped_value(r"RES(?P<value>\d{2})", response_obj, "videoOutputResolution", self.video_resolution_map)

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Video Widescreen Mode has
	# been received; this will convert the number to the text equivalent
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def video_widescreen_mode_response_received(self, response_obj, rp_command):
		self.response_to_mapped_value(r"VWM(?P<value>\d{2})", response_obj, "videoWideScreenMode", self.video_widescreenmode_map)

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Video Picture Mode has
	# been received; this will convert the number to the text equivalent
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def video_picture_mode_response_received(self, response_obj, rp_command):
		self.response_to_mapped_value(r"VPM(?P<value>\d{2})", response_obj, "videoPictureMode", self.video_picturemode_map)

	def listening_mode_response_received(self, response_obj, rp_command):
		self.response_to_mapped_value(r"LMD(?P<value>[\dA-Z]+)", response_obj, "listeningMode", self.listening_mode_map)

	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback processor performs a standard mapping of a response value to its
	# description via a dictionary; if value is not found in the map then the raw value
	# is used as the state
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def response_to_mapped_value(self, parse_expression, response_obj, state_name, value_map):
		value_splitter = re.compile(parse_expression)
		value_match = value_splitter.search(response_obj)
		input_value = value_match.groupdict().get("value")
		if input_value in value_map:
			self.indigoDevice.updateStateOnServer(key=state_name, value=value_map[input_value])
		else:
			self.indigoDevice.updateStateOnServer(key=state_name, value=input_value)

	# endregion
	#######################################################################################

	#######################################################################################
	# region Utility routines
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will parse the return from an eISCP input query to the equivalent
	# "human-readable" form. Return is tuple - ("input#", "Description")
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def parse_eiscp_input_definition(self, eiscp_input_defn):
		# attempt to find both the input number and name from our lookup tables
		input_desc = self.input_number_to_description.get(eiscp_input_defn, "")
		if not input_desc:
			input_desc = f"Input {eiscp_input_defn}"
		return input_desc

	# endregion
	#######################################################################################

class OnkyoVirtualVolumeController(RPFrameworkNonCommChildDevice):
	
	#######################################################################################
	# Class construction and destruction methods
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super().__init__(plugin, device)
		