#! /usr/bin/env python
# -*- coding: utf-8 -*-
#######################################################################################
# Onkyo Network Remote Control by RogueProeliator <rp@rogueproeliator.com>
# Indigo plugin designed to allow full control of Onkyo Receivers via their network
# interface
#
# Command structure based on the eISCP messages; commands and some code may be found
# in the open source project on GitHub:
# https://github.com/miracle2k/onkyo-eiscp
#######################################################################################

# region Python imports
import operator

from RPFramework.RPFrameworkPlugin import RPFrameworkPlugin
import onkyoNetworkRemoteDevice
import eiscp
# endregion


class Plugin(RPFrameworkPlugin):

	#######################################################################################
	# region Class construction and destruction methods
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# Constructor called once upon plugin class creation; setup the device tracking
	# variables for later use
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def __init__(self, plugin_id, plugin_display_name, plugin_version, plugin_prefs):
		# RP framework base class's init method
		super().__init__(plugin_id, plugin_display_name, plugin_version, plugin_prefs, managed_device_class_module=onkyoNetworkRemoteDevice)

	# endregion
	#######################################################################################

	#######################################################################################
	# region Actions object callback handlers/routines
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called in order to determine which state should be shown in the
	# "State" column on the Indigo devices list
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def getDeviceDisplayStateId(self, dev):
		# this comes from the user's selection, stored in the device properties
		state_id = dev.pluginProps.get("stateDisplayColumnState", "connectionState")
		self.logger.debug(f"Returning state for State column: {state_id}")
		return state_id
	
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called by the device configuration dialog in order to get the
	# menu of available Onkyo devices
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def discover_onkyo_devices(self, filter="", valuesDict=None, typeId="", targetId=0):
		found_receivers = []
		for receiver in eiscp.eISCP.discover(timeout=3):
			found_receivers.append((f"{receiver.info['identifier']}:{receiver.iscp_port}", f"{receiver.info['model_name']}:{receiver.info['identifier']}"))

		return found_receivers
	
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called whenever the user has clicked to use the selected onkyo
	# from the menu of discovered devices
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def select_enumerated_onkyo_for_use(self, valuesDict=None, filter="", typeId="", targetId=0):
		selected_device_info = valuesDict.get("onkyoReceiversFound", "")
		if selected_device_info != "":
			address_info = selected_device_info.split(":")
			valuesDict["ipAddress"]  = address_info[0]
			valuesDict["portNumber"] = address_info[1]
		return valuesDict
	
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called by the action configuration dialog to get the menu of zonesAvailable
	# available for the device
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def get_zone_selector_menu(self, filter="", valuesDict=None, typeId="", targetId=0):
		zones_available = []
		rp_device = self.managed_devices[targetId]
		for zone in rp_device.indigoDevice.pluginProps.get("deviceZonesConnected"):
			zone_value = zone
			if zone_value == "main":
				zone_text = "Main"
			else:
				zone_text = f"Zone {zone_value[-1:]}"
			zones_available.append((zone_value, zone_text))
		return zones_available
		
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine is called by the action configuration dialog to retrieve either the
	# list of all inputs ("all" or None for filter) or only the connected inputs
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def get_input_selector_menu(self, filter="", valuesDict=None, typeId="", target_id=0):
		self.logger.threaddebug(f"get_input_selector_menu called for filter: {filter}")
	
		if target_id in self.managed_devices:
			rp_device = self.managed_devices[target_id]
		else:
			rp_device = onkyoNetworkRemoteDevice.OnkyoReceiverNetworkRemoteDevice(self, None)
		
		if filter is None or filter == "" or filter == "all":
			inputs_available = sorted(rp_device.inputChannelToDescription.iteritems(), key=operator.itemgetter(1))
		else:
			# we need to get the list of inputs matching the selected/connected list from the device
			connected_list = []
			for input_num in rp_device.indigoDevice.pluginProps.get("deviceInputsConnected"):
				connected_list.append((input_num, rp_device.inputChannelToDescription[input_num]))
			inputs_available = sorted(connected_list, key=operator.itemgetter(1))
			
		return inputs_available
		
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	# This routine will be called from the user executing the menu item action to send
	# an arbitrary command code to the Onkyo receiver
	# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-
	def send_arbitrary_command(self, valuesDict, typeId):
		try:
			device_id = valuesDict.get("targetDevice", "0")
			command_code = valuesDict.get("commandToSend", "").strip()
		
			if device_id == "" or device_id == "0":
				# no device was selected
				error_dict = indigo.Dict()
				error_dict["targetDevice"] = "Please select a device"
				return False, valuesDict, error_dict
			elif command_code == "":
				error_dict = indigo.Dict()
				error_dict["commandToSend"] = "Enter command to send"
				return False, valuesDict, error_dict
			else:
				# send the code using the normal action processing...
				action_params = indigo.Dict()
				action_params["commandToSend"] = command_code
				self.execute_action(pluginAction=None, indigoActionId="SendArbitraryCommand", indigoDeviceId=int(device_id), paramValues=action_params)
				return True, valuesDict
		except:
			self.logger.exception("Error sending arbitrary command: ")
			return False, valuesDict

	# endregion
	#######################################################################################
