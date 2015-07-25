#! /usr/bin/env python
# -*- coding: utf-8 -*-
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Onkyo Network Remote Control by RogueProeliator <rp@rogueproeliator.com>
# 	Indigo plugin designed to allow full control of Onkyo Receivers via their network
#	interface
#	
#	Command structure based on the eISCP messages; commands and some code may be found
#	in the open source project on GitHub:
#	https://github.com/miracle2k/onkyo-eiscp
#
#	Version 0.5.9 [July 2014]:
#		* Beta release of the plugin to Indigo users
#	Version 1.1.12:
#		* Added virtual volume controller (dimmer) device
#		* Added ability to choose the State display column
#	Version 1.3.14:
#		* Added Zone 2 power commands
#	Version 1.4.15:
#		* Added Zone 2 input selection and state retrieval
#	Version 1.5.15:
#		* Added Zone 2 volume control
#	Version 1.6.16:
#		* Added ability to reconnect when the connection fails (this was accidentally
#		  turned off previously
#		* Change isPoweredOn to be False for standby mode (UI Value of Standby)
#		* Will properly set error state to Error for failed connections
#
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////


#/////////////////////////////////////////////////////////////////////////////////////////
# Python imports
#/////////////////////////////////////////////////////////////////////////////////////////
import operator
import re
import socket
import string

import RPFramework
import onkyoNetworkRemoteDevice
import eISCP


#/////////////////////////////////////////////////////////////////////////////////////////
# Constants and configuration variables
#/////////////////////////////////////////////////////////////////////////////////////////


#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
# Plugin
#	Primary Indigo plugin class that is universal for all devices (receivers) to be
#	controlled
#/////////////////////////////////////////////////////////////////////////////////////////
#/////////////////////////////////////////////////////////////////////////////////////////
class Plugin(RPFramework.RPFrameworkPlugin.RPFrameworkPlugin):
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Class construction and destruction methods
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class creation; setup the device tracking
	# variables for later use
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		# RP framework base class's init method
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs, "http://www.duncanware.com/Downloads/IndigoHomeAutomation/Plugins/OnkyoNetworkRemote/OnkyoNetworkRemoteVersionInfo.html", managedDeviceClassModule=onkyoNetworkRemoteDevice)
	
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Configuration and Action Dialog Callbacks
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called in order to determine which state should be shown in the
	# "State" column on the Indigo devices list
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getDeviceDisplayStateId(self, dev):
		# this comes from the user's selection, stored in the device properties
		stateId = dev.pluginProps.get("stateDisplayColumnState", "connectionState")
		self.logDebugMessage("Returning state for State column: " + stateId, RPFramework.RPFrameworkPlugin.DEBUGLEVEL_LOW)
		return stateId
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called by the device configuration dialog in order to get the
	# menu of available Onkyo devices
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def discoverOnkyoDevices(self, filter="", valuesDict=None, typeId="", targetId=0):
		foundReceivers = []
		for receiver in eISCP.eISCP.discover(timeout=1):
			foundReceivers.append(('%s:%s' % (receiver.host, receiver.port), '%s:%s' % (receiver.info['model_name'], receiver.host)))
		return foundReceivers
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called whenever the user has clicked to use the selected onkyo
	# from the menu of discovered devices
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def selectEnumeratedOnkyoForUse(self, valuesDict=None, filter="", typeId="", targetId=0):
		selectedDeviceInfo = valuesDict.get("onkyoReceiversFound", "")
		if selectedDeviceInfo != "":
			addressInfo = selectedDeviceInfo.split(':')
			valuesDict["ipAddress"] = addressInfo[0]
			valuesDict["portNumber"] = addressInfo[1]
		return valuesDict
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called by the action configuration dialog to get the menu of zonesAvailable
	# available for the device
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getZoneSelectorMenu(self, filter="", valuesDict=None, typeId="", targetId=0):
		zonesAvailable = []
		rpDevice = self.managedDevices[targetId]
		for zone in rpDevice.indigoDevice.pluginProps.get("deviceZonesConnected"):
			zoneValue = zone
			if zoneValue == "main":
				zoneText = "Main"
			else:
				zoneText = "Zone " + zoneValue[-1:]
			zonesAvailable.append((zoneValue, zoneText))
		return zonesAvailable
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called by the action configuration dialog to retrieve either the
	# list of all inputs ("all" or None for filter) or only the connected inputs
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getInputSelectorMenu(self, filter="", valuesDict=None, typeId="", targetId=0):
		self.logDebugMessage("getInputSelectorMenu called for filter: {" + filter + "}", RPFramework.RPFrameworkPlugin.DEBUGLEVEL_HIGH)
	
		inputsAvailable = []
		if targetId in self.managedDevices:
			rpDevice = self.managedDevices[targetId]
		else:
			rpDevice = onkyoNetworkRemoteDevice.OnkyoReceiverNetworkRemoteDevice(self, None)
		
		if filter is None or filter == "" or filter == "all":
			inputsAvailable = sorted(rpDevice.inputChannelToDescription.iteritems(), key=operator.itemgetter(1))
		else:
			# we need to get the list of inputs matching the selected/connected list from the device
			connectedList = []
			for inputNum in rpDevice.indigoDevice.pluginProps.get("deviceInputsConnected"):
				connectedList.append((inputNum, rpDevice.inputChannelToDescription[inputNum]))
			inputsAvailable = sorted(connectedList, key=operator.itemgetter(1))
			
		return inputsAvailable
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-	
	# This routine will be called from the user executing the menu item action to send
	# an arbitrary command code to the Onkyo receiver
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-	
	def sendArbitraryCommand(self, valuesDict, typeId):
		try:
			deviceId = valuesDict.get("targetDevice", "0")
			commandCode = valuesDict.get("commandToSend", "").strip()
		
			if deviceId == "" or deviceId == "0":
				# no device was selected
				errorDict = indigo.Dict()
				errorDict["targetDevice"] = "Please select a device"
				return (False, valuesDict, errorDict)
			elif commandCode == "":
				errorDict = indigo.Dict()
				errorDict["commandToSend"] = "Enter command to send"
				return (False, valuesDict, errorDict)
			else:
				# send the code using the normal action processing...
				actionParams = indigo.Dict()
				actionParams["commandCode"] = commandCode
				self.executeAction(pluginAction=None, indigoActionId="SendArbitraryCommand", indigoDeviceId=int(deviceId), paramValues=actionParams)
				return (True, valuesDict)
		except:
			self.exceptionLog()
			return (False, valuesDict)	
	