#! /usr/bin/env python
# -*- coding: utf-8 -*-
#######################################################################################
# Onkyo Network Remote Control by RogueProeliator <rp@rogueproeliator.com>
#######################################################################################

# region Python imports
import re
import sys
import select
import threading
import time

import indigo
from RPFramework.RPFrameworkTelnetDevice import RPFrameworkTelnetDevice
from RPFramework.RPFrameworkNonCommChildDevice import RPFrameworkNonCommChildDevice
from RPFramework.RPFrameworkCommand import RPFrameworkCommand
import eISCP
# endregion

#######################################################################################
# region Constants and configuration variables
CMD_SEND_EISCP        = u'sendEISCPCommand'
CMD_DIRECT_TUNE       = u'directTune'
CMD_DIRECT_TUNE_ZONE2 = u'directTuneZone2'
# endregion
#######################################################################################


class OnkyoReceiverNetworkRemoteDevice(RPFrameworkTelnetDevice):

	#######################################################################################
	# region Class construction and destruction methods
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
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
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should be overridden in individual device classes whenever they must
	# handle custom commands that are not already defined
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def handle_unmanaged_command_in_queue(self, ip_connection, rp_command):
		if rp_command.command_name == CMD_SEND_EISCP:
			self.host_plugin.logger.debug(f"Sending eISCP Command: {rp_command.command_payload}")
			ip_connection.send(eISCP.command_to_packet(rp_command.command_payload))
			self.host_plugin.logger.threaddebug("Send command completed.")
		elif rp_command.command_name == CMD_DIRECT_TUNE or rp_command.command_name == CMD_DIRECT_TUNE_ZONE2:
			self.host_plugin.logger.debug(f"Received direct tune action to {rp_command.commandPayload}")
			if "." in rp_command.commandPayload:
				# this is an FM station, pad to 2 digits to right of decimal, others to left
				fm_station_info = rp_command.commandPayload.split(".")
				tune_to_station = fm_station_info[0].rjust(3, "0") + fm_station_info[1].ljust(2, "0")
			else:
				# this is an AM or SR station, do all padding to the left
				tune_to_station = rp_command.command_payload.rjust(5, "0")
				
			tune_command_prefix = "TUN"
			if rp_command.command_name == CMD_DIRECT_TUNE_ZONE2:
				tune_command_prefix = "TUZ"
				
			self.host_plugin.logger.debug(f"Sending tune command for {tune_to_station}")
			ip_connection.send(eISCP.command_to_packet(tune_command_prefix + tune_to_station))
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should attempt to read a line of text from the connection, using the
	# provided timeout as the upper-limit to wait
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def read_line(self, connection, line_ending_token, command_response_timeout):
		eISCPData = select.select([connection], [], [], command_response_timeout)
		if eISCPData[0]:
			header_bytes = connection.recv(16)
			header       = eISCP.eISCPPacket.parse_header(header_bytes)
			message      = connection.recv(header.data_size)
			try:
				return f"{eISCP.iscp_to_command(eISCP.ISCPMessage.parse(message))}"
			except:
				self.host_plugin.logger.debug(f"Failed to parse eISCP message, message ignored: {message}")
				return message
		else:
			return ""
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should attempt to read a line of text from the connection only if there
	# is an indication of waiting data (there is no waiting until a specified timeout)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def read_if_available(self, connection, line_ending_token, command_response_timeout):
		return self.read_line(connection, line_ending_token, command_response_timeout)

	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should return a tuple of information about the connection - in the
	# format of (ipAddress/HostName, portNumber)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def get_device_address_info(self):
		return (self.indigo_device.pluginProps.get("ipAddress", ""), int(self.indigo_device.pluginProps.get("portNumber", "60128")))

	# endregion
	#######################################################################################
		
	#######################################################################################
	#region Custom Response Handlers
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for the receiver
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def input_selector_query_received(self, response_obj, rp_command):
		value_splitter   = re.compile(r"^\('input\-selector',\s{0,1}(?P<value>('|\().+('|\))|\d+)\)$")
		value_match      = value_splitter.search(response_obj)
		input_value      = value_match.groupdict().get("value").replace("'", "")
		input_definition = self.parse_eiscp_input_definition(input_value)
		
		# update the two "current inputs" on the server...
		self.indigo_device.updateStateOnServer(key="currentInputNumber", value=input_definition[0])
		self.indigo_device.updateStateOnServer(key="currentInputLabel", value=input_definition[1])
		self.host_plugin.logger.debug(f"Updating current input number/label: {input_definition[0]} / {input_definition[1]}")
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for Zone 2 of the receiver
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def zone2_selector_query_received(self, response_obj, rp_command):
		value_splitter   = re.compile(r"^\('selector',\s{0,1}(?P<value>('|\().+('|\)))\)$")
		value_match      = value_splitter.search(response_obj)
		input_value      = value_match.groupdict().get("value").replace("'", "")
		input_definition = self.parse_eiscp_input_definition(input_value)
		
		# update the two "current inputs" on the server...
		self.indigo_device.updateStateOnServer(key="zone2InputNumber", value=input_definition[0])
		self.indigo_device.updateStateOnServer(key="zone2InputLabel", value=input_definition[1])
		self.host_plugin.logger.debug(f"Updating zone 2 input number/label: {input_definition[0]} / {input_definition[1]}")
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Master Volume has been
	# found; it should update any virtual controllers attached
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def update_virtual_master_volume(self, response_obj, rp_command):
		if "main" in self.child_devices:
			# find the child device and ensure we have the latest version of the states
			volume_controller = self.childDevices["main"]
			volume_controller.reload_indigo_device()
			
			# update the volume of the virtual controller if it is different than the master...
			if volume_controller.indigo_device.states.get("brightnessLevel", 0) != self.indigoDevice.states.get("masterVolumeLevel", 0):
				self.host_plugin.logger.debug(f"Setting Master Volume Virtual Controller brightness to {self.indigoDevice.states.get('masterVolumeLevel', 0)}")
				volume_controller.indigo_device.updateStateOnServer(key="brightnessLevel", value=self.indigo_device.states.get("masterVolumeLevel", 0))

			# determine the on/off state for the controller
			is_on = self.indigo_device.states.get("isPoweredOn", False) == True and self.indigoDevice.states.get("isMuted", True) == False and self.indigoDevice.states.get("masterVolumeLevel", 0) > 0
			if volume_controller.indigo_device.states.get("onOffState", False) != is_on:
				self.host_plugin.logger.debug(f"Setting On/Off state to: {is_on}")
				volume_controller.indigo_device.updateStateOnServer(key="onOffState", value=is_on)
					
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Zone 2 Volume has been
	# found; it should update any virtual controllers attached
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def update_virtual_zone2_volume(self, response_obj, rp_command):
		if "zone2" in self.child_devices:
			# find the child device and ensure we have the latest version of the states
			volume_controller = self.childDevices["zone2"]
			volume_controller.reload_indigo_device()
			
			# update the volume of the virtual controller if it is different than the master...
			if volume_controller.indigo_device.states.get("brightnessLevel", 0) != self.indigo_device.states.get("zone2VolumeLevel", 0):
				self.host_plugin.logger.debug(f"Setting Zone 2 Volume Virtual Controller brightness to {self.indigoDevice.states.get('zone2VolumeLevel', 0)}")
				volume_controller.indigo_device.updateStateOnServer(key="brightnessLevel", value=self.indigo_device.states.get("zone2VolumeLevel", 0))

			# determine the on/off state for the controller
			is_on = self.indigo_device.states.get("zone2PoweredOn", False) == True and self.indigoDevice.states.get("isMuted", True) == False and self.indigoDevice.states.get("zone2VolumeLevel", 0) > 0
			if volume_controller.indigo_device.states.get("onOffState", False) != is_on:
				self.hostPlugin.logger.debug(f"Setting On/Off state to: {is_on}")
				volume_controller.indigo_device.updateStateOnServer(key="onOffState", value=is_on)

	# endregion
	#######################################################################################
	
	#######################################################################################
	#region Utility routines
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will parse the return from an eISCP input query to the equivalent
	# "human readable" form. Return is tuple - ("input#", "Description")
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def parse_eiscp_input_definition(self, eiscp_input_defn):
		# attempt to find both the input number and name from our lookup tables
		input_number = self.inputSelectorEISCPMappings.get(eiscp_input_defn, "")
		input_desc   = self.inputChannelToDescription.get(input_number, "")
		return input_number, input_desc

	# endregion
	#######################################################################################


class OnkyoVirtualVolumeController(RPFrameworkNonCommChildDevice):
	
	#######################################################################################
	# Class construction and destruction methods
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super().__init__(plugin, device)
		