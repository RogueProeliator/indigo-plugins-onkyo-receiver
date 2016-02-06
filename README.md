#Introduction
This Indigo 6.0+ plugin allows Indigo to control Onkyo receivers via their network (IP) control protocol. Onkyo's protocol is very robust and, as a result, this plugin is able to both read and set nearly every aspect of the receiver - even features that are buried very deep in the menu system. To simplify the actions and plugin, I have omitted various commands that did not seem common - such as test tones and launching the built-in surround analyzer. These types of features generally do not add to the home automation control experience, but if something is missing that you desire, please do not hesitate ask and I can add as appropriate.

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
The latest released version of the plugin is available for download [here](http://www.duncanware.com/Downloads/IndigoHomeAutomation/Plugins/OnkyoNetworkRemote/OnkyoNetworkRemote.zip). This download is a ZIP archive of the .indigoPlugin file. ALternatively, you may pull from this source repository, but must also pull the [RPFramework](https://github.com/RogueProeliator/IndigoPlugins-RPFramework), add its contents to the plugin directory under 'Server Plugin'.

