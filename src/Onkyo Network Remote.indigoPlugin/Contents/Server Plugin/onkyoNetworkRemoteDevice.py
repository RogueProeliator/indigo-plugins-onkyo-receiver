#! /usr/bin/env python
# -*- coding: utf-8 -*-
#######################################################################################
# Onkyo Network Remote Control by RogueProeliator <rp@rogueproeliator.com>
#######################################################################################

# region Python imports
import re
import time

import indigo
from RPFramework.RPFrameworkTelnetDevice import RPFrameworkTelnetDevice
from RPFramework.RPFrameworkNonCommChildDevice import RPFrameworkNonCommChildDevice
from RPFramework.RPFrameworkCommand import RPFrameworkCommand
import eiscp
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
		
		# create the dictionary that maps input selector values to/from their respective numbers
		self.inputSelectorEISCPMappings = {
			"(video1, vcr, dvr)"        : "00",
			"(video2, cbl, sat)"        : "01",
			"(video3, game, tv, game)"  : "02",
			"(video4, aux1)"            : "03",
			"(video5, aux2)"            : "04",
			"(video6, pc)"              : "05",
			"video7"                    : "06",
			"07"                        : "07",
			"08"                        : "08",
			"09"                        : "09",
			"(dvd, bd, dvd)"            : "10",
			"11"                        : "11",
			"18"                        : "12",
			"(tape-1, tv, tape)"        : "20",
			"tape2"                     : "21",
			"phono"                     : "22",
			"(cd, tv, cd)"              : "23",
			"fm"                        : "24",
			"am"                        : "25",
			"tuner"                     : "26",
			"(music-server, p4s, dlna)" : "27",
			"(internet-radio, iradio-favorite)" : "28",
			"(usb, usb)"                : "29",
			"usb"                       : "2A",
			"(network, net)"            : "2B",
			#"usb"                       : "2C",
			"multi-ch"                  : "30",
			"xm"                        : "31",
			"sirius"                    : "32",
			"universal-port"            : "40" }
		
		self.inputChannelToDescription = {
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
	def concurrent_command_processing_thread(self, command_queue):
		try:
			self.host_plugin.logger.debug(f"Concurrent Processing Thread started for device {self.indigoDevice.id}")
			# retrieve the keys and settings that will be used during the command processing
			# for this telnet device
			is_connected_state_key = self.host_plugin.get_gui_config_value(self.indigoDevice.deviceTypeId, RPFrameworkTelnetDevice.GUI_CONFIG_ISCONNECTEDSTATEKEY, "")
			connection_state_key   = self.host_plugin.get_gui_config_value(self.indigoDevice.deviceTypeId, RPFrameworkTelnetDevice.GUI_CONFIG_CONNECTIONSTATEKEY, "")
			self.host_plugin.logger.threaddebug(f"Read device state config... isConnected: {is_connected_state_key}; connectionState: {connection_state_key}")
			telnet_connection_info = self.get_device_address_info()

			# start with a clean slate if this is the first time we are attempting connection
			if self.failed_connection_attempts == 0:
				self.indigoDevice.setErrorStateOnServer(None)
				if is_connected_state_key != "":
					self.indigoDevice.updateStateOnServer(key=is_connected_state_key, value="false")
				if connection_state_key != "":
					self.indigoDevice.updateStateOnServer(key=connection_state_key, value="Not Connected")

			# retrieve any configuration information that may have been set up in the
			# plugin configuration and/or device configuration
			command_response_timeout           = float(self.host_plugin.get_gui_config_value(self.indigoDevice.deviceTypeId, RPFrameworkTelnetDevice.GUI_CONFIG_COMMANDREADTIMEOUT, "0.5"))
			update_status_poller_property_name = self.host_plugin.get_gui_config_value(self.indigoDevice.deviceTypeId, RPFrameworkTelnetDevice.GUI_CONFIG_STATUSPOLL_INTERVALPROPERTY, "updateInterval")
			update_status_poller_interval      = int(self.indigoDevice.pluginProps.get(update_status_poller_property_name, "90"))
			update_status_poller_next_run      = None
			update_status_poller_action_id     = self.host_plugin.get_gui_config_value(self.indigoDevice.deviceTypeId, RPFrameworkTelnetDevice.GUI_CONFIG_STATUSPOLL_ACTIONID, "")
			update_status_poller_initial_delay = float(self.host_plugin.get_gui_config_value(self.indigoDevice.deviceTypeId, RPFrameworkTelnetDevice.GUI_CONFIG_STATUSPOLL_INITIALDELAY, "0.5"))
			empty_queue_reduced_wait_cycles    = int(self.host_plugin.get_gui_config_value(self.indigoDevice.deviceTypeId, RPFrameworkTelnetDevice.GUI_CONFIG_TELNETDEV_EMPTYQUEUE_SPEEDUPCYCLES, "200"))

			# begin the infinite loop which will run as long as the queue contains commands
			# and we have not received an explicit shutdown request
			continue_processing_commands = True
			last_queued_command_completed = 0
			while continue_processing_commands:
				# process pending commands now...
				while not command_queue.empty():
					len_queue = command_queue.qsize()
					self.host_plugin.logger.threaddebug(f"Command queue has {len_queue} command(s) waiting")

					# the command name will identify what action should be taken... we will handle the known
					# commands and dispatch out to the device implementation, if necessary, to handle unknown
					# commands
					command = command_queue.get()
					if command.command_name == RPFrameworkCommand.CMD_INITIALIZE_CONNECTION:
						# specialized command to instantiate the thread/telnet connection
						self.host_plugin.logger.threaddebug("Create connection command de-queued")

						# establish the telnet connection to the telnet-based which handles the primary
						# network remote operations
						self.host_plugin.logger.debug(f"Establishing connection to {telnet_connection_info[0]}")
						self.onkyo_receiver = eiscp.core.Receiver(telnet_connection_info[0])
						self.onkyo_receiver.on_message = self.onkyo_message_received
						self.failed_connection_attempts = 0
						self.host_plugin.logger.debug("Connection established")

						self.indigoDevice.setErrorStateOnServer(None)
						if is_connected_state_key != "":
							self.indigoDevice.updateStateOnServer(key=is_connected_state_key, value="true")
						if connection_state_key != "":
							self.indigoDevice.updateStateOnServer(key=connection_state_key, value="Connected")

						# if the device supports polling for status, it may be initiated here now that
						# the connection has been established; no additional command will come through
						self.host_plugin.logger.threaddebug("Scheduling status update")
						command.post_command_pause = update_status_poller_initial_delay
						command_queue.put(RPFrameworkCommand(RPFrameworkCommand.CMD_UPDATE_DEVICE_STATUS_FULL, parent_action=update_status_poller_action_id))

					elif command.command_name == RPFrameworkCommand.CMD_TERMINATE_PROCESSING_THREAD:
						# a specialized command designed to stop the processing thread indigo
						# the event of a shutdown
						continue_processing_commands = False

					elif command.command_name == RPFrameworkCommand.CMD_PAUSE_PROCESSING:
						# the amount of time to sleep should be a float found in the
						# payload of the command
						try:
							pause_time = float(command.command_payload)
							self.host_plugin.logger.threaddebug(f"Initiating sleep of {pause_time} seconds from command.")
							time.sleep(pause_time)
						except:
							self.host_plugin.logger.error("Invalid pause time requested")

					elif command.command_name == RPFrameworkCommand.CMD_UPDATE_DEVICE_STATUS_FULL:
						# this command instructs the plugin to update the full status of the device (all statuses
						# that may be read from the device should be read)
						if update_status_poller_action_id != "":
							self.host_plugin.logger.debug("Executing full status update request...")
							self.host_plugin.execute_action(None, indigoActionId=update_status_poller_action_id, indigoDeviceId=self.indigoDevice.id, paramValues=None)
							if update_status_poller_interval > 0:
								update_status_poller_next_run = time.time() + update_status_poller_interval
						else:
							self.host_plugin.logger.threaddebug("Ignoring status update request, no action specified to update device status")

					elif command.command_name == RPFrameworkCommand.CMD_UPDATE_DEVICE_STATE:
						# this command is to update a device state with the payload (which may be an
						# eval command)
						new_state_info = re.match(r'^\{ds\:([a-zA-Z\d]+)\}\{(.+)\}$', command.command_payload, re.I)
						if new_state_info is None:
							self.host_plugin.logger.error(f"Invalid new device state specified")
						else:
							# the new device state may include an eval statement...
							update_state_name = new_state_info.group(1)
							update_state_value = new_state_info.group(2)
							if update_state_value.startswith("eval"):
								update_state_value = eval(update_state_value.replace("eval:", ""))

							self.host_plugin.logger.debug(
								f"Updating state '{update_state_name}' to: '{update_state_value}'")
							self.indigoDevice.updateStateOnServer(key=update_state_name, value=update_state_value)

					elif command.command_name == CMD_SEND_EISCP:
						# this command initiates a write of data to the device
						self.host_plugin.logger.debug(f"Sending command: {command.command_payload}")
						self.onkyo_receiver.send(command.command_payload)
						self.host_plugin.logger.threaddebug("Write command completed.")

					elif command.command_name == CMD_DIRECT_TUNE or command.command_name == CMD_DIRECT_TUNE_ZONE2:
						self.host_plugin.logger.debug(f"Received direct tune action to {command.command_payload}")
						if "." in command.command_payload:
							# this is an FM station, pad to 2 digits to right of decimal, others to left
							fm_station_info = command.command_payload.split(".")
							tune_to_station = fm_station_info[0].rjust(3, "0") + fm_station_info[1].ljust(2, "0")
						else:
							# this is an AM or SR station, do all padding to the left
							tune_to_station = command.command_payload.rjust(5, "0")

						tune_command_prefix = "TUN"
						if command.command_name == CMD_DIRECT_TUNE_ZONE2:
							tune_command_prefix = "TUZ"

						self.host_plugin.logger.debug(f"Sending tune command for {tune_to_station}")
						self.onkyo_receiver.send(tune_command_prefix + tune_to_station)

					elif command.command_name == CMD_PROCESS_MESSAGE:
						response_text = command.command_payload
						if response_text != "":
							self.host_plugin.logger.threaddebug(f"Processing Message: {response_text}")
							self.handle_device_response(response_text, None)

					# if the command has a pause defined for after it is completed then we
					# should execute that pause now
					if command.post_command_pause > 0.0 and continue_processing_commands:
						self.host_plugin.logger.threaddebug(f"Post Command Pause: {command.post_command_pause}")
						time.sleep(command.post_command_pause)

					# complete the de-queuing of the command, allowing the next
					# command in queue to rise to the top
					command_queue.task_done()
					last_queued_command_completed = empty_queue_reduced_wait_cycles

				# continue with empty-queue processing unless the connection is shutting down...
				if continue_processing_commands:
					# when the queue is empty, pause a bit on each iteration
					if last_queued_command_completed > 0:
						time.sleep(self.empty_queue_sleep_time / 2)
						last_queued_command_completed = last_queued_command_completed - 1
					else:
						time.sleep(self.empty_queue_sleep_time)

					# check to see if we need to issue an update...
					if update_status_poller_next_run is not None and time.time() > update_status_poller_next_run:
						command_queue.put(RPFrameworkCommand(RPFrameworkCommand.CMD_UPDATE_DEVICE_STATUS_FULL, parent_action=update_status_poller_action_id))

		# handle any exceptions that are thrown during execution of the plugin... note that this
		# should terminate the thread, but it may get spun back up again
		except SystemExit:
			pass
		except Exception:
			self.host_plugin.logger.exception("Exception in background processing")
		except:
			self.host_plugin.logger.exception("Exception in background processing")
		finally:
			self.host_plugin.logger.debug("Command thread ending processing")

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
		self.queue_device_command(RPFrameworkCommand(CMD_PROCESS_MESSAGE, command_payload=message))

	# endregion
	#######################################################################################
		
	#######################################################################################
	# region Custom Response Handlers
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for the receiver
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def input_selector_query_received(self, response_obj, rp_command):
		value_splitter   = re.compile(r"^SLI(?P<value>\d{2})$")
		value_match      = value_splitter.search(response_obj)
		input_value      = value_match.groupdict().get("value")
		input_definition = self.parse_eiscp_input_definition(input_value)
		
		# update the two "current inputs" on the server...
		self.indigoDevice.updateStateOnServer(key="currentInputNumber", value=input_definition[0])
		self.indigoDevice.updateStateOnServer(key="currentInputLabel", value=input_definition[1])
		self.host_plugin.logger.debug(f"Updating current input number/label: {input_definition[0]} / {input_definition[1]}")
		
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for Zone 2 of the receiver
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def zone2_selector_query_received(self, response_obj, rp_command):
		value_splitter   = re.compile(r"SLZ(?P<value>\d{2})")
		value_match      = value_splitter.search(response_obj)
		input_value      = value_match.groupdict().get("value").replace("'", "")
		input_definition = self.parse_eiscp_input_definition(input_value)
		
		# update the two "current inputs" on the server...
		self.indigoDevice.updateStateOnServer(key="zone2InputNumber", value=input_definition[0])
		self.indigoDevice.updateStateOnServer(key="zone2InputLabel", value=input_definition[1])
		self.host_plugin.logger.debug(f"Updating zone 2 input number/label: {input_definition[0]} / {input_definition[1]}")
	
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
		self.response_to_mapped_value(r"LMD(?P<value>([\dA-Z]+)", response_obj, "listeningMode", self.listening_mode_map)

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
		input_number = self.inputSelectorEISCPMappings.get(eiscp_input_defn, "")
		input_desc = self.inputChannelToDescription.get(input_number, "")
		return input_number, input_desc

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
		