#Introduction
This Indigo 6.0+ plugin allows Indigo to control Onkyo receivers via their network (IP) control protocol. Onkyo's protocol is very robust and, as a result, this plugin is able to both read and set nearly every aspect of the receiver - even features that are buried very deep in the menu system. To simplify the actions and plugin, I have omitted various commands that did not seem common - such as test tones and launching the built-in surround analyzer. These types of features generally do not add to the home automation control experience, but if something is missing that you desire, please do not hesitate ask and I can add as appropriate.

_**INDIGO 6 IMPORTANT NOTE:**_ The Indigo 6 version of this plugin is end-of-life with respect to new development, however the latest stable version on Indigo 6 is [still available](https://github.com/RogueProeliator/IndigoPlugins-Onkyo-Receiver-Network-Remote/releases/tag/v2.0.0) on the releases page and is working as expected at the moment. Please consider an upgrade to Indigo 7 to support further development of our favorite HA platform!

#Hardware Requirements
This plugin should work with any network-connected Onkyo receiver which supports IP control via ethernet; generally speaking the Onkyo protocol SEEMS to be pretty universal between receivers, with the caveat that not all receivers support all operations (e.g. not all have the same number of inputs, outputs, etc.). The plugin has been tested with the following hardware:

- TX-NR414
- TX-NR515
- TX-NR535
- TX-NR616
- TX-NR808
- TX-NR809
- TX-NR3008

If you have tested it successfully (or unsuccessfully) with other models and feel inclined to share, please let me know and I will update this list.

#Enabling Network Control of the Receiver - Important Step
The first step is to ensure that your receiver is connected to the network; the menu system will vary by model, but generally this is pretty easy to setup for those models with an On Screen Display. Additionally, some models require that you enable network control of the receiver -- please check your menus/settings or manual for more information.

#Installation and Configuration
###Obtaining the Plugin
The latest released version of the plugin is available for download in the Releases section... those versions in beta will be marked as a Pre-Release and will not appear in update notifications.

###Configuring the Plugin
Upon first installation you will be asked to configure the plugin; please see the instructions on the configuration screen for more information. Most users will be fine with the defaults unless an email is desired when a new version is released.
![](<Documentation/Doc-Images/OnkyoPluginConfig.png>)

#Plugin Devices
When creating (or editing a device), in the Device Settings you will need to select from the list of Onkyo devices found on the network or else manually enter your receivers's IP address. Please be sure to select the zones and inputs available on your Onkyo receiver (note that some commands only work with the main zone). These selection govern what you are able to select when creating Actions, helping to reduce the choices/menu selections.
![](<Documentation/Doc-Images/OnkyoDeviceConfig.png>)

###Virtual Volume Controllers
The Onkyo Virtual Volume Controller allows you to control the volume of the receiver directly from a remote device (as opposed through a control page.) This device is tied to a receiver/zone and appears in Indigo Touch, HousePad and webpages as a standard dimmer device. Create the device, select your receiver and zone (only Main is currently supported) and set a maximum volume level. Any setting above this maximum will be ignored -- this is to prevent accidentally setting the volume to a large number that could damage speakers and equipment!
![](<Documentation/Doc-Images/VirtualVolumeControllerConfig.png>)

#Available Device Actions
The list of actions available for the should be fairly self-explanatory; please post any questions or requests for additional actions in the [Indigo Domo forum](http://forums.indigodomo.com/viewforum.php?f=146) and I will do my best to help out where possible.

#Available Device States
The plugin tracks several devices states which are updated according to the polling frequency (set in Device Config) or upon execution of a command which will affect the state. The following states are supported:

- **isConnected** & **connectionState** - track if Indigo has been able to successfully create/maintain a connection to the receiver
- **isPoweredOn** - tracks the power state of the device, but is only applicable if Standby mode is used (a full power down will kill the connection to the device)
- **sleepTimer** - specifies the number of minutes remaining on the current sleep timer, 0 if not set
- **masterVolumeLevel**
- **isMuted**
- **hdmiAudioOut** - this tracks whether or not the receiver will pass audio through the HDMI out to the television
- **listeningMode** - this is the preset modes/equalizer states/settings that many receivers support, such as Stereo vs. Music vs. Theater
- **currentInputNumber** & **currentInputLabel**
- **tunerFrequency**
- **networkPlayArtist**, **networkPlayAlbum**, **networkPlayTitle**, & **networkPlayStatus** - these pull the status from network streaming such as Pandora (will also pull from USB storage)
- **videoOutputResolution** - the output of the video out, such as 720p or 1080p
- **videoWideScreenMode** - widescreen "adjustment" mode such as zoom or stretch
- **videoPictureMode** - video adjustments such as seen on many televisions
- **speakerAPower**/**speakerBPower** - power status for speaker selections on some receivers (many will read N/A for not supported)
- **zone2InputLabel** & **zone2InputNumber**
- **zone2PoweredOn**
- **zone2VolumeLevel**
