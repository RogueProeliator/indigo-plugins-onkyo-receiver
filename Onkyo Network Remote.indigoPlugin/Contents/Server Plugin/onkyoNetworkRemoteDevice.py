#! /usr/bin/env python
# -*- coding: utf-8 -*-
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Onkyo Network Remote Control by RogueProeliator <rp@rogueproeliator.com>
# 	See plugin.py for more plugin details and information
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////

#/////////////////////////////////////////////////////////////////////////////////////////
# Python imports
#/////////////////////////////////////////////////////////////////////////////////////////
import re	
import sys
import select
import threading
import time

import indigo
import RPFramework
import eISCP


#/////////////////////////////////////////////////////////////////////////////////////////
# Constants and configuration variables
#/////////////////////////////////////////////////////////////////////////////////////////
CMD_SEND_EISCP = u'sendEISCPCommand'
CMD_DIRECT_TUNE = u'directTune'
CMD_DIRECT_TUNE_ZONE2 = u'directTuneZone2'


#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# OnkyoReceiverNetworkRemoteDevice
#	Handles the configuration of a single Onkyo device that is connected to this plugin;
#	this class does all the 'grunt work' of communications with the receiver
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class OnkyoReceiverNetworkRemoteDevice(RPFramework.RPFrameworkTelnetDevice.RPFrameworkTelnetDevice):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super(OnkyoReceiverNetworkRemoteDevice, self).__init__(plugin, device, connectionType=RPFramework.RPFrameworkTelnetDevice.CONNECTIONTYPE_SOCKET)
		
		# create the dictionary that maps input selector values to/from their respective numbers
		self.inputSelectorEISCPMappings = {
			"(video1, vcr, dvr)" : "00",
			"(video2, cbl, sat)" : "01",
			"(video3, game, tv, game)" : "02",
			"(video4, aux1)" : "03",
			"(video5, aux2)" : "04",
			"(video6, pc)" : "05",
			"video7" : "06",
			"07" : "07",
			"08" : "08",
			"09" : "09",
			"(dvd, bd, dvd)" : "10",
			"(tape-1, tv, tape)" : "20",
			"tape2" : "21",
			"phono" : "22",
			"(cd, tv, cd)" : "23",
			"fm" : "24",
			"am" : "25",
			"tuner" : "26",
			"(music-server, p4s, dlna)" : "27",
			"(internet-radio, iradio-favorite)" : "28",
			"(usb, usb)" : "29",
			"usb" : "2A",
			"(network, net)" : "2B",
			"usb" : "2C",
			"multi-ch" : "30",
			"xm" : "31",
			"sirius" : "32",
			"universal-port" : "40" }
		
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
			"40" : "Universal PORT"
		}
		
		# record the new states that have been added so that the device will automatically reload the
		# state list from the Devices.xml
		self.upgradedDeviceStates.append(u'zone2PoweredOn')
		self.upgradedDeviceStates.append(u'zone2InputNumber')
		self.upgradedDeviceStates.append(u'zone2InputLabel')
		self.upgradedDeviceStates.append(u'zone2VolumeLevel')
		self.upgradedDeviceStates.append(u'tunerFrequency')
		self.upgradedDeviceStates.append(u'networkPlayTitle')
		self.upgradedDeviceStates.append(u'networkPlayAlbum')
		self.upgradedDeviceStates.append(u'networkPlayArtist')
		self.upgradedDeviceStates.append(u'networkPlayStatus')
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Processing and command functions
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should be overridden in individual device classes whenever they must
	# handle custom commands that are not already defined
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def handleUnmanagedCommandInQueue(self, ipConnection, rpCommand):
		if rpCommand.commandName == CMD_SEND_EISCP:
			self.hostPlugin.logger.debug(u'Sending eISCP Command: ' + rpCommand.commandPayload)
			ipConnection.send(eISCP.command_to_packet(rpCommand.commandPayload))
			self.hostPlugin.logger.threaddebug(u'Send command completed.')
		elif rpCommand.commandName == CMD_DIRECT_TUNE or rpCommand.commandName == CMD_DIRECT_TUNE_ZONE2:
			self.hostPlugin.logger.debug(u'Received direct tune action to ' + rpCommand.commandPayload)
			if '.' in rpCommand.commandPayload:
				# this is an FM station, pad to 2 digits to right of decimal, others to left
				fmStationInfo = rpCommand.commandPayload.split('.')
				tuneToStation = fmStationInfo[0].rjust(3, '0') + fmStationInfo[1].ljust(2, '0')
			else:
				# this is an AM or SR station, do all padding to the left
				tuneToStation = rpCommand.commandPayload #.rjust(5, '0')
				
			tuneCommandPrefix = "TUN"
			if rpCommand.commandName == CMD_DIRECT_TUNE_ZONE2:
				tuneCommandPrefix = "TUZ"
				
			self.hostPlugin.logger.debug(u'Sending tune command for ' + tuneToStation)				
			ipConnection.send(eISCP.command_to_packet(tuneCommandPrefix + tuneToStation))
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should attempt to read a line of text from the connection, using the
	# provided timeout as the upper-limit to wait
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def readLine(self, connection, lineEndingToken, commandResponseTimeout):
		eISCPData = select.select([connection], [], [], commandResponseTimeout)
		if eISCPData[0]:
			header_bytes = connection.recv(16)
			header = eISCP.eISCPPacket.parse_header(header_bytes)
			message = connection.recv(header.data_size)
			try:
				return str(eISCP.iscp_to_command(eISCP.ISCPMessage.parse(message)))
			except:
				self.hostPlugin.logger.debug(u'Failed to parse eISCP message, message ignored: ' + RPFramework.RPFrameworkUtils.to_unicode(message))
				return message
		else:
			return u''
			
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should attempt to read a line of text from the connection only if there
	# is an indication of waiting data (there is no waiting until a specified timeout)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def readIfAvailable(self, connection, lineEndingToken, commandResponseTimeout):
		return self.readLine(connection, lineEndingToken, commandResponseTimeout)
	
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine should return a touple of information about the connection - in the
	# format of (ipAddress/HostName, portNumber)
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getDeviceAddressInfo(self):
		return (self.indigoDevice.pluginProps.get(u'ipAddress', u''), int(self.indigoDevice.pluginProps.get(u'portNumber', u'60128')))	
		
		
	#/////////////////////////////////////////////////////////////////////////////////////
	# Custom Response Handlers
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for the receiver
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def inputSelectorQueryReceived(self, responseObj, rpCommand):
		valueSplitter = re.compile("^\('input\-selector',\s{0,1}(?P<value>('|\().+('|\)))\)$")
		valueMatch = valueSplitter.search(responseObj)
		inputValue = valueMatch.groupdict().get(u'value').replace("'", "")
		inputDefinition = self.parseEISCPInputDefinition(inputValue)
		
		# update the two "current inputs" on the server...
		self.indigoDevice.updateStateOnServer(key=u'currentInputNumber', value=inputDefinition[0])
		self.indigoDevice.updateStateOnServer(key=u'currentInputLabel', value=inputDefinition[1])
		self.hostPlugin.logger.debug(u'Updating current input number/label: ' + inputDefinition[0] + u' / ' + inputDefinition[1])
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback is made whenever the plugin has received the response to a status
	# request for the current input for Zone 2 of the receiver
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def zone2SelectorQueryReceived(self, responseObj, rpCommand):
		valueSplitter = re.compile("^\('selector',\s{0,1}(?P<value>('|\().+('|\)))\)$")
		valueMatch = valueSplitter.search(responseObj)
		inputValue = valueMatch.groupdict().get(u'value').replace(u"'", u"")
		inputDefinition = self.parseEISCPInputDefinition(inputValue)
		
		# update the two "current inputs" on the server...
		self.indigoDevice.updateStateOnServer(key=u'zone2InputNumber', value=inputDefinition[0])
		self.indigoDevice.updateStateOnServer(key=u'zone2InputLabel', value=inputDefinition[1])
		self.hostPlugin.logger.debug(u'Updating zone 2 input number/label: ' + inputDefinition[0] + u' / ' + inputDefinition[1])
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Master Volume has been
	# found; it should update any virtual controllers attached
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def updateVirtualMasterVolume(self, responseObj, rpCommand):
		if u'main' in self.childDevices:
			# find the child device and ensure we have the latest version of the states
			volumeController = self.childDevices[u'main']
			volumeController.reloadIndigoDevice()
			
			# update the volume of the virtual controller if it is different than the master...
			if volumeController.indigoDevice.states.get(u'brightnessLevel', 0) != self.indigoDevice.states.get(u'masterVolumeLevel', 0):
				self.hostPlugin.logger.debug(u'Setting Master Volume Virtual Controller brightness to ' + RPFramework.RPFrameworkUtils.to_unicode(self.indigoDevice.states.get(u'masterVolumeLevel', 0)))
				volumeController.indigoDevice.updateStateOnServer(key=u'brightnessLevel', value=self.indigoDevice.states.get(u'masterVolumeLevel', 0))

			# determine the on/off state for the controller
			isOn = self.indigoDevice.states.get(u'isPoweredOn', False) == True and self.indigoDevice.states.get(u'isMuted', True) == False and self.indigoDevice.states.get(u'masterVolumeLevel', 0) > 0
			if volumeController.indigoDevice.states.get(u'onOffState', False) != isOn:
				self.hostPlugin.logger.debug(u'Setting On/Off state to: ' + RPFramework.RPFrameworkUtils.to_unicode(isOn))
				volumeController.indigoDevice.updateStateOnServer(key=u'onOffState', value=isOn)
					
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This callback will be triggered whenever an update to the Zone 2 Volume has been
	# found; it should update any virtual controllers attached
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def updateVirtualZone2Volume(self, responseObj, rpCommand):
		if u'zone2' in self.childDevices:
			# find the child device and ensure we have the latest version of the states
			volumeController = self.childDevices[u'zone2']
			volumeController.reloadIndigoDevice()
			
			# update the volume of the virtual controller if it is different than the master...
			if volumeController.indigoDevice.states.get(u'brightnessLevel', 0) != self.indigoDevice.states.get(u'zone2VolumeLevel', 0):
				self.hostPlugin.logger.debug(u'Setting Zone 2 Volume Virtual Controller brightness to ' + RPFramework.RPFrameworkUtils.to_unicode(self.indigoDevice.states.get(u'zone2VolumeLevel', 0)))
				volumeController.indigoDevice.updateStateOnServer(key=u'brightnessLevel', value=self.indigoDevice.states.get(u'zone2VolumeLevel', 0))

			# determine the on/off state for the controller
			isOn = self.indigoDevice.states.get(u'zone2PoweredOn', False) == True and self.indigoDevice.states.get(u'isMuted', True) == False and self.indigoDevice.states.get(u'zone2VolumeLevel', 0) > 0
			if volumeController.indigoDevice.states.get(u'onOffState', False) != isOn:
				self.hostPlugin.logger.debug(u'Setting On/Off state to: ' + RPFramework.RPFrameworkUtils.to_unicode(isOn))
				volumeController.indigoDevice.updateStateOnServer(key=u'onOffState', value=isOn)
				
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Utility routines
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will parse the return from an eISCP input query to the equivalent
	# "human readable" form. Return is tuple - ("input#", "Description")
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def parseEISCPInputDefinition(self, eiscpInputDefn):
		# attempt to find both the input number and name from our lookup tables
		inputNumber = self.inputSelectorEISCPMappings.get(eiscpInputDefn, "")
		inputDesc = self.inputChannelToDescription.get(inputNumber, "")
		return (inputNumber, inputDesc)
	

#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# OnkyoVirtualVolumeController
#	Handles the volume control for an Onkyo device, modeled after a dimmer so that it may
#	be operated as a slider on client devices
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class OnkyoVirtualVolumeController(RPFramework.RPFrameworkNonCommChildDevice.RPFrameworkNonCommChildDevice):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class receiving a command to start device
	# communication. The plugin will call other commands when needed, simply zero out the
	# member variables
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin, device):
		super(OnkyoVirtualVolumeController, self).__init__(plugin, device)
		