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
#	This plugin is released under an MIT license - this is a very simple and permissive
#	license and may be found in the LICENSE.txt file found in the root of this plugin's
#	GitHub repository:
#		https://github.com/RogueProeliator/IndigoPlugins-Onkyo-Receiver-Network-Remote
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
		super(Plugin, self).__init__(pluginId, pluginDisplayName, pluginVersion, pluginPrefs, managedDeviceClassModule=onkyoNetworkRemoteDevice)
	
	
	#/////////////////////////////////////////////////////////////////////////////////////
	# Configuration and Action Dialog Callbacks
	#/////////////////////////////////////////////////////////////////////////////////////
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called in order to determine which state should be shown in the
	# "State" column on the Indigo devices list
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getDeviceDisplayStateId(self, dev):
		# this comes from the user's selection, stored in the device properties
		stateId = dev.pluginProps.get(u'stateDisplayColumnState', u'connectionState')
		self.logger.debug(u'Returning state for State column: {0}'.format(stateId))
		return stateId
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called by the device configuration dialog in order to get the
	# menu of available Onkyo devices
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def discoverOnkyoDevices(self, filter=u'', valuesDict=None, typeId=u'', targetId=0):
		foundReceivers = []
		for receiver in eISCP.eISCP.discover(timeout=1):
			foundReceivers.append((u'%s:%s' % (receiver.host, receiver.port), u'%s:%s' % (receiver.info['model_name'], receiver.host)))
		return foundReceivers
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called whenever the user has clicked to use the selected onkyo
	# from the menu of discovered devices
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def selectEnumeratedOnkyoForUse(self, valuesDict=None, filter=u'', typeId=u'', targetId=0):
		selectedDeviceInfo = valuesDict.get(u'onkyoReceiversFound', u'')
		if selectedDeviceInfo != u'':
			addressInfo = selectedDeviceInfo.split(':')
			valuesDict[u'ipAddress']  = addressInfo[0]
			valuesDict[u'portNumber'] = addressInfo[1]
		return valuesDict
	
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called by the action configuration dialog to get the menu of zonesAvailable
	# available for the device
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getZoneSelectorMenu(self, filter=u'', valuesDict=None, typeId=u'', targetId=0):
		zonesAvailable = []
		rpDevice = self.managedDevices[targetId]
		for zone in rpDevice.indigoDevice.pluginProps.get(u'deviceZonesConnected'):
			zoneValue = zone
			if zoneValue == u'main':
				zoneText = u'Main'
			else:
				zoneText = u'Zone {0}'.format(zoneValue[-1:])
			zonesAvailable.append((zoneValue, zoneText))
		return zonesAvailable
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called by the action configuration dialog to retrieve either the
	# list of all inputs ("all" or None for filter) or only the connected inputs
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getInputSelectorMenu(self, filter=u'', valuesDict=None, typeId=u'', targetId=0):
		self.logger.threaddebug(u'getInputSelectorMenu called for filter: {0}'.format(filter))
	
		inputsAvailable = []
		if targetId in self.managedDevices:
			rpDevice = self.managedDevices[targetId]
		else:
			rpDevice = onkyoNetworkRemoteDevice.OnkyoReceiverNetworkRemoteDevice(self, None)
		
		if filter is None or filter == u'' or filter == u'all':
			inputsAvailable = sorted(rpDevice.inputChannelToDescription.iteritems(), key=operator.itemgetter(1))
		else:
			# we need to get the list of inputs matching the selected/connected list from the device
			connectedList = []
			for inputNum in rpDevice.indigoDevice.pluginProps.get(u'deviceInputsConnected'):
				connectedList.append((inputNum, rpDevice.inputChannelToDescription[inputNum]))
			inputsAvailable = sorted(connectedList, key=operator.itemgetter(1))
			
		return inputsAvailable
		
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-	
	# This routine will be called from the user executing the menu item action to send
	# an arbitrary command code to the Onkyo receiver
	#-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-	
	def sendArbitraryCommand(self, valuesDict, typeId):
		try:
			deviceId = valuesDict.get(u'targetDevice', u'0')
			commandCode = valuesDict.get(u'commandToSend', u'').strip()
		
			if deviceId == u'' or deviceId == u'0':
				# no device was selected
				errorDict = indigo.Dict()
				errorDict[u'targetDevice'] = u'Please select a device'
				return (False, valuesDict, errorDict)
			elif commandCode == u'':
				errorDict = indigo.Dict()
				errorDict[u'commandToSend'] = u'Enter command to send'
				return (False, valuesDict, errorDict)
			else:
				# send the code using the normal action processing...
				actionParams = indigo.Dict()
				actionParams[u'commandToSend'] = commandCode
				self.executeAction(pluginAction=None, indigoActionId=u'SendArbitraryCommand', indigoDeviceId=int(deviceId), paramValues=actionParams)
				return (True, valuesDict)
		except:
			self.logger.exception(u'Error sending arbitrary command: ')
			return (False, valuesDict)	
	