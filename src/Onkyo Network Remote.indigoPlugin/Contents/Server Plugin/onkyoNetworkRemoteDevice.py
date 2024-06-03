#! /usr/bin/env python
# -*- coding: utf-8 -*-
#######################################################################################
# Onkyo Network Remote Control by RogueProeliator <rp@rogueproeliator.com>
#######################################################################################

# region Python imports
import re
import select
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
						self.onkyo_receiver = eiscp.eISCP(telnet_connection_info[0])
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
						# determine if any response has been received from the telnet device...
						response_text = self.onkyo_receiver.raw(command.command_payload)
						if response_text != "":
							self.host_plugin.logger.threaddebug(f"Received: {response_text}")
							self.handle_device_response(response_text, command)
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
						response_text = self.onkyo_receiver.raw(tune_command_prefix + tune_to_station)
						if response_text != "":
							self.host_plugin.logger.threaddebug(f"Received: {response_text}")
							self.handle_device_response(response_text, command)

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

	# endregion
	#######################################################################################
		
	#######################################################################################
	# region Custom Response Handlers
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for the receiver
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def input_selector_query_received(self, response_obj, rp_command):
		value_splitter   = re.compile(r"^\('input\-selector',\s{0,1}(?P<value>('|\().+('|\))|\d+)\)$")
		value_match      = value_splitter.search(response_obj)
		input_value      = value_match.groupdict().get("value").replace("'", "")
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
		value_splitter   = re.compile(r"^\('selector',\s{0,1}(?P<value>('|\().+('|\)))\)$")
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
		