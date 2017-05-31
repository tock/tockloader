#!/usr/bin/env python3

import argparse
import atexit
import binascii
import contextlib
import copy
import glob
import json
import os
import struct
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import time

import argcomplete
import colorama
import crcmod
import pytoml
import serial
import serial.tools.list_ports
import serial.tools.miniterm

from ._version import __version__


################################################################################
## Niceties and Support
################################################################################

from serial.tools import list_ports_common

def set_terminal_title(title):
	print(colorama.ansi.set_title(title))

def set_terminal_title_from_port_info(info):
	extras = ['Tockloader']
	if info.manufacturer and info.manufacturer != 'n/a':
		extras.append(info.manufacturer)
	if info.name and info.name != 'n/a':
		extras.append(info.name)
	if info.description and info.description != 'n/a':
		extras.append(info.description)
	#if info.hwid and info.hwid != 'n/a':
	#	extras.append(info.hwid)
	if info.product and info.product != 'n/a':
		if info.product != info.description:
			extras.append(info.product)
	title = ' : '.join(extras)

	set_terminal_title(title)

def set_terminal_title_from_port(port):
	set_terminal_title('Tockloader : ' + port)

# Cleanup any title the program may set
atexit.register(set_terminal_title, '')

def menu(options, *,
		return_type,
		default_index=0,
		prompt='Which option? '
		):
	'''Present a menu of choices to a user

	`options` should be a like-list object whose iterated objects can be coerced
	into strings.

	`return_type` must be set to one of
	  - "index" - for the index into the options array
	  - "value" - for the option value chosen

	`default_index` is the index to present as the default value (what happens
	if the user simply presses enter). Passing `None` disables default
	selection.
	'''
	print()
	for i,opt in enumerate(options):
		print('[{}]\t{}'.format(i, opt))
	if default_index is not None:
		prompt += '[{}] '.format(default_index)
	print()

	resp = input(prompt)
	if resp == '':
		resp = default_index
	else:
		try:
			resp = int(resp)
			if resp < 0 or resp > len(options):
				raise ValueError
		except:
			return menu(options, return_type=return_type,
					default_index=default_index, prompt=prompt)

	if return_type == 'index':
		return resp
	elif return_type == 'value':
		return options[resp]
	else:
		raise NotImplementedError('Menu caller asked for bad return_type')

class TockLoaderException(Exception):
	pass

################################################################################
## Main TockLoader Interface
################################################################################

class TockLoader:

	def __init__ (self, args):
		self.args = args

		# Get an object that allows talking to the board
		if hasattr(self.args, 'jtag') and self.args.jtag:
			self.channel = JLinkExe(args)
		else:
			self.channel = BootloaderSerial(args)


	# Open the correct channel to talk to the board.
	#
	# For the bootloader, this means opening a serial port.
	# For JTAG, not much needs to be done.
	def open (self, args):
		self.channel.open_link_to_board()


	# Tell the bootloader to save the binary blob to an address in internal
	# flash.
	#
	# This will pad the binary as needed, so don't worry about the binary being
	# a certain length.
	def flash_binary (self, binary, address):
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():
			self.channel.flash_binary(address, binary)


	# Run miniterm for receiving data from the board.
	def run_terminal (self):
		print('Listening for serial output.')

		# Use trusty miniterm
		miniterm = serial.tools.miniterm.Miniterm(
			self.channel.get_serial_port(),
			echo=False,
			eol='crlf',
			filters=['default'])

		# Ctrl+c to exit.
		miniterm.exit_character = serial.tools.miniterm.unichr(0x03)
		miniterm.set_rx_encoding('UTF-8')
		miniterm.set_tx_encoding('UTF-8')

		miniterm.start()
		try:
			miniterm.join(True)
		except KeyboardInterrupt:
			pass
		miniterm.join()
		miniterm.close()


	# Query the chip's flash to determine which apps are installed.
	def list_apps (self, address, verbose, quiet):
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Get all apps based on their header
			apps = self._extract_all_app_headers(address)

			self._print_apps(apps, verbose, quiet)


	# Add or update TABs on the board.
	#
	# `replace` can be either "yes", "no", or "only"
	def install (self, tabs, address, replace='yes'):
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Start with the apps we are searching for.
			replacement_apps = self._extract_apps_from_tabs(tabs)

			# Get a list of installed apps
			existing_apps = self._extract_all_app_headers(address)

			# What apps we want after this command completes
			resulting_apps = []

			# Whether we actually made a change or not
			changed = False

			# Check to see if this app is in there
			if replace == 'yes' or replace == 'only':
				for existing_app in existing_apps:
					for replacement_app in replacement_apps:
						if existing_app.name == replacement_app.name:
							resulting_apps.append(copy.deepcopy(replacement_app))
							changed = True
							break
					else:
						# We did not find a replacement app. That means we want
						# to keep the original.
						resulting_apps.append(existing_app)

				# Now, if we want a true install, and not an update, make sure
				# we add all apps that did not find a replacement on the board.
				if replace == 'yes':
					for replacement_app in replacement_apps:
						for resulting_app in resulting_apps:
							if replacement_app.name == resulting_app.name:
								break
						else:
							# We did not find the name in the resulting apps.
							# Add it.
							resulting_apps.append(replacement_app)
							changed = True

			elif replace == 'no':
				# Just add the apps
				resulting_apps = existing_apps + replacement_apps
				changed = True

			if changed:
				# Since something is now different, update all of the apps
				self._reshuffle_apps(address, resulting_apps)
			else:
				# Nothing changed, so we can raise an error
				raise TockLoaderException('Nothing found to update')


	# If an app by this name exists, remove it from the chip
	def uninstall_app (self, app_names, address, force=False):
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Get a list of installed apps
			apps = self._extract_all_app_headers(address)

			# If the user didn't specify an app list...
			if len(app_names) == 0:
				if len(apps) == 0:
					raise TockLoaderException('No apps are installed on the board')
				elif len(apps) == 1:
					# If there's only one app, delete it
					app_names = [apps[0].name]
					print('Only one app on board. Uninstalling {}'.format(apps[0]))
				else:
					print('There are multiple apps currently on the board:')
					options = ['** Delete all']
					options.extend([app.name for app in apps])
					name = menu(options,
							return_type='value',
							prompt='Select app to uninstall ')
					if name == '** Delete all':
						app_names = [app.name for app in apps]
					else:
						app_names = [name]

			# Remove the apps if they are there
			removed = False
			keep_apps = []
			for app in apps:
				# Only keep apps that are not marked for uninstall or that
				# are sticky (unless force was set)
				if app.name not in app_names or (app.is_sticky() and not force):
					keep_apps.append(app)
				else:
					removed = True

			# Tell the user if we are not removing certain apps because they
			# are sticky.
			if not force:
				for app in apps:
					if app.name in app_names and app.is_sticky():
						print('INFO: Not removing app "{}" because it is sticky.'.format(app))

			# Now take the remaining apps and make sure they
			# are on the board properly.
			self._reshuffle_apps(address, keep_apps)

			print('Uninstall complete.')

			# And let the user know the state of the world now that we're done
			apps = self._extract_all_app_headers(address)
			if len(apps):
				print('Remaining apps on board:')
				self._print_apps(apps, verbose=False, quiet=True)
			else:
				print('No apps on board.')

			if not removed:
				raise TockLoaderException('Could not find any apps on the board to remove.')


	# Erase flash where apps go
	def erase_apps (self, address, force=False):
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# On force we can just eliminate all apps
			if force:
				# Erase the first page where apps go. This will cause the first
				# header to be invalid and effectively removes all apps.
				self.channel.erase_page(address)

			else:
				# Get a list of installed apps
				apps = self._extract_all_app_headers(address)

				keep_apps = []
				for app in apps:
					if app.is_sticky():
						keep_apps.append(app)
						print('INFO: Not erasing app "{}" because it is sticky.'.format(app))

				if len(keep_apps) == 0:
					self.channel.erase_page(address)
				else:
					self._reshuffle_apps(address, keep_apps)


	# Set a flag in the TBF header
	def set_flag (self, app_names, flag_name, flag_value, address):
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Get a list of installed apps
			apps = self._extract_all_app_headers(address)

			if len(apps) == 0:
				raise TockLoaderException('No apps are installed on the board')

			# User did not specify apps. Pick from list.
			if len(app_names) == 0:
				print('Which apps to configure?')
				options = ['** All']
				options.extend([app.name for app in apps])
				name = menu(options,
						return_type='value',
						prompt='Select app to configure ')
				if name == '** All':
					app_names = [app.name for app in apps]
				else:
					app_names = [name]

			# Configure all selected apps
			changed = False
			for app in apps:
				if app.name in app_names:
					app.tbfh.set_flag(flag_name, flag_value)
					changed = True

			if changed:
				self._reflash_app_headers(apps)
			else:
				print('No matching apps found. Nothing changed.')


	# Download all attributes stored on the board
	def list_attributes (self):
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			if not self._bootloader_is_present():
				raise TockLoaderException('No bootloader found! That means there is nowhere for attributes to go.')

			self._print_attributes(self.channel.get_all_attributes())


	# Download all attributes stored on the board
	def set_attribute (self, key, value):
		# Do some checking
		if len(key.encode('utf-8')) > 8:
			raise TockLoaderException('Key is too long. Must be 8 bytes or fewer.')
		if len(value.encode('utf-8')) > 55:
			raise TockLoaderException('Value is too long. Must be 55 bytes or fewer.')

		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			if not self._bootloader_is_present():
				raise TockLoaderException('No bootloader found! That means there is nowhere for attributes to go.')

			# Create the buffer to write as the attribute
			out = bytes([])
			# Add key
			out += key.encode('utf-8')
			out += bytes([0] * (8-len(out)))
			# Add length
			out += bytes([len(value.encode('utf-8'))])
			# Add value
			out += value.encode('utf-8')

			# Find if this attribute key already exists
			open_index = -1
			for index, attribute in enumerate(self.channel.get_all_attributes()):
				if attribute:
					if attribute['key'] == key:
						print('Found existing key at slot {}. Overwriting.'.format(index))
						self.channel.set_attribute(index, out)
						break
				else:
					# Save where we should put this attribute if it does not
					# already exist.
					if open_index == -1:
						open_index = index
			else:
				if open_index == -1:
					raise TockLoaderException('Error: No open space to save this attribute.')
				else:
					print('Key not found. Writing new attribute to slot {}'.format(open_index))
					self.channel.set_attribute(open_index, out)


	# Remove an existing attribute already stored on the board
	def remove_attribute (self, key):
		# Do some checking
		if len(key.encode('utf-8')) > 8:
			raise TockLoaderException('Key is too long. Must be 8 bytes or fewer.')

		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			if not self._bootloader_is_present():
				raise TockLoaderException('No bootloader found! That means there is nowhere for attributes to go.')

			# Create a null buffer to overwrite with
			out = bytes([0]*9)

			# Find if this attribute key already exists
			for index, attribute in enumerate(self.channel.get_all_attributes()):
				if attribute and attribute['key'] == key:
					print('Found existing key at slot {}. Removing.'.format(index))
					self.channel.set_attribute(index, out)
					break
			else:
				raise TockLoaderException('Error: Attribute does not exist.')


	# Print all info about this board.
	def info (self, app_address):
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Print all apps
			print('Apps:')
			apps = self._extract_all_app_headers(app_address)
			self._print_apps(apps, True, False)

			if self._bootloader_is_present():
				# Print all attributes
				print('Attributes:')
				attributes = self.channel.get_all_attributes()
				self._print_attributes(attributes)
				print('')

				# Show bootloader version
				version = self.channel.get_bootloader_version()
				if version == None:
					version = 'unknown'
				print('Bootloader version: {}'.format(version))
			else:
				print('No bootloader.')

	############################################################################
	## Internal Helper Functions for Communicating with Boards
	############################################################################

	# Based on the transport method used, there may be some setup required
	# to connect to the board. This function runs the setup needed to connect
	# to the board. It also times the operation.
	#
	# For the bootloader, the board needs to be reset and told to enter the
	# bootloader mode.
	# For JTAG, this is unnecessary.
	@contextlib.contextmanager
	def _start_communication_with_board (self):
		# Time the operation
		then = time.time()
		try:
			self.channel.enter_bootloader_mode()

			# Now that we have connected to the board and the bootloader
			# if necessary, make sure we know what kind of board we are
			# talking to.
			self.channel.determine_current_board()

			yield

			now = time.time()
			print('Finished in {:0.3f} seconds'.format(now-then))
		except Exception as e:
			raise(e)
		finally:
			self.channel.exit_bootloader_mode()

	# Check if a bootloader exists on this board. It is specified by the
	# string "TOCKBOOTLOADER" being at address 0x400.
	def _bootloader_is_present (self):
		# Check to see if the channel already knows this. For example,
		# if you are connected via a serial link to the bootloader,
		# then obviously the bootloader is present.
		if self.channel.bootloader_is_present() == True:
			return True

		# Otherwise check for the bootloader flag in the flash.

		# Constants for the bootloader flag
		address = 0x400
		length = 14
		flag = self.channel.read_range(address, length)
		flag_str = flag.decode('utf-8')
		if self.args.debug:
			print('Read from flags location: {}'.format(flag_str))
		return flag_str == 'TOCKBOOTLOADER'


	############################################################################
	## Helper Functions for Manipulating Binaries and TBF
	############################################################################

	# Given an array of apps, some of which are new and some of which exist,
	# sort them in flash so they are in descending size order.
	def _reshuffle_apps(self, address, apps):
		# We are given an array of apps. First we need to order them by size.
		apps.sort(key=lambda app: app.get_size(), reverse=True)

		# Now iterate to see if the address has changed
		start_address = address
		for app in apps:
			# If the address already matches, then we are good.
			# On to the next app.
			if app.address != start_address:
				# If they don't, then we need to read the binary out of
				# flash and save it to be moved, as well as update the address.
				# However, we may have a new binary to use, so we don't need to
				# fetch it.
				if not app.has_binary():
					app.set_binary(self.channel.read_range(app.address, app.get_size()))

				# Either way save the new address.
				app.set_address(start_address)

			start_address += app.get_size()

		# Now flash all apps that have a binary field. The presence of the
		# binary indicates that they are new or moved.
		end = address
		for app in apps:
			if app.has_binary():
				self.channel.flash_binary(app.address, app.binary)
			end = app.address + app.get_size()

		# Then erase the next page. This ensures that flash is clean at the
		# end of the installed apps and makes things nicer for future uses of
		# this script.
		self.channel.erase_page(end)

	# Iterate through the flash on the board for
	# the header information about each app.
	def _extract_all_app_headers (self, address):
		apps = []

		# Jump through the linked list of apps
		while (True):
			header_length = 80 # Version 2
			flash = self.channel.read_range(address, header_length)

			# if there was an error, the binary array will be empty
			if len(flash) < header_length:
				break

			# Get all the fields from the header
			tbfh = TBFHeader(flash)

			if tbfh.is_valid():
				# Get the name out of the app
				name = self._get_app_name(address+tbfh.get_name_offset(), tbfh.get_name_length())

				app = App(tbfh, address, name)
				apps.append(app)

				address += app.get_size()

			else:
				break

		return apps

	# Take a list of app headers and reflash them to the chip.
	# This doesn't do a lot of checking, so you better have not re-ordered
	# the headers or anything annoying like that.
	def _reflash_app_headers (self, apps):
		for app in apps:
			if app.has_binary():
				raise TockLoaderException('App headers should not have binaries! That would imply the app has changed!')

			self.channel.flash_binary(app.address, app.get_header_binary(), pad=False)

	# Iterate through the list of TABs and create the app dict for each.
	def _extract_apps_from_tabs (self, tabs):
		apps = []

		# This is the architecture we need for the board
		arch = self.channel.get_board_arch()

		for tab in tabs:
			if self.args.force or tab.is_compatible_with_board(self.channel.get_board_name()):
				apps.append(tab.extract_app(arch))

		if len(apps) == 0:
			raise TockLoaderException('No valid apps for this board were provided. Use --force to override.')

		return apps

	# Retrieve bytes from the board and interpret them as a string
	def _get_app_name (self, address, length):
		if length == 0:
			return ''

		name_memory = self.channel.read_range(address, length)
		return name_memory.decode('utf-8')

	# Check if putting an app at this address will be OK with the MPU.
	def _app_is_aligned_correctly (self, address, size):
		# The rule for the MPU is that the size of the protected region must be
		# a power of two, and that the region is aligned on a multiple of that
		# size.

		# Check if not power of two
		if (size & (size - 1)) != 0:
			return False

		# Check that address is a multiple of size
		multiple = address // size
		if multiple * size != address:
			return False

		return True

	############################################################################
	## Printing helper functions
	############################################################################

	# Print information about a list of apps
	def _print_apps (self, apps, verbose, quiet):
		if not quiet:
			# Print info about each app
			for i,app in enumerate(apps):
				print('[App {}]'.format(i))

				# Check if this app is OK with the MPU region requirements.
				if not self._app_is_aligned_correctly(app.address, app.get_size()):
					print('  [WARNING] App is misaligned for the MPU')

				print(textwrap.indent(app.info(verbose), '  '))
				print('')

			if len(apps) == 0:
				print('No found apps.')

		else:
			# In quiet mode just show the names.
			app_names = []
			for app in apps:
				app_names.append(app.name)
			print(' '.join(app_names))

	def _print_attributes (self, attributes):
		for index, attribute in enumerate(attributes):
			if attribute:
				print('{:02d}: {:>8} = {}'.format(index, attribute['key'], attribute['value']))
			else:
				print('{:02d}:'.format(index))


################################################################################
## Connection to the Board Classes
################################################################################

# Generic template class that allows actually talking to the board
class BoardInterface:

	def __init__ (self, args):
		self.args = args

		# These settings need to come from somewhere. Once place is the
		# command line. Another is the attributes section on the board.
		# There could be more in the future.
		# Also, not all are required depending on the connection method used.
		self.board = getattr(self.args, 'board', None)
		self.arch = getattr(self.args, 'arch', None)
		self.jtag_device = getattr(self.args, 'jtag_device', None)

	# Open a connection to the board
	def open_link_to_board (self):
		return

	# Get access to the underlying serial port (if it exists).
	# This is used for running miniterm.
	def get_serial_port (self):
		return

	# Get to a mode where we can read & write flash
	def enter_bootloader_mode (self):
		return

	# Get out of bootloader mode and go back to running main code
	def exit_bootloader_mode (self):
		return

	# Write a binary to the address given
	def flash_binary (self, address, binary):
		return

	# Read a specific range of flash.
	def read_range (self, address, length):
		if self.args.debug:
			print('DEBUG => Read Range, address: {:#010x}, length: {}'.format(address, length))

	# Erase a specific page.
	def erase_page (self, address):
		return

	# Get a single attribute.
	def get_attribute (self, index):
		return

	# Get all atributes on a board.
	def get_all_attributes (self):
		return

	# Set a single attribute.
	def set_attribute (self, index, raw):
		return

	def _decode_attribute (self, raw):
		try:
			key = raw[0:8].decode('utf-8').strip(bytes([0]).decode('utf-8'))
			vlen = raw[8]
			if vlen > 55 or vlen == 0:
				return None
			value = raw[9:9+vlen].decode('utf-8')
			return {
				'key': key,
				'value': value
			}
		except Exception as e:
			return None

	# Default answer is to not answer.
	def bootloader_is_present (self):
		return None

	# Return the version string of the bootloader.
	def get_bootloader_version (self):
		return

	# Figure out which board we are connected to. Most likely done by
	# reading the attributes.
	def determine_current_board (self):
		return

	# Return the name of the board we are connected to.
	def get_board_name (self):
		return self.board

	# Return the architecture of the board we are connected to.
	def get_board_arch (self):
		return self.arch


################################################################################
## Bootloader Specific Functions
################################################################################

class BootloaderSerial(BoardInterface):

	# "This was chosen as it is infrequent in .bin files" - immesys
	ESCAPE_CHAR = 0xFC

	# Commands from this tool to the bootloader.
	# The "X" commands are for external flash.
	COMMAND_PING               = 0x01
	COMMAND_INFO               = 0x03
	COMMAND_ID                 = 0x04
	COMMAND_RESET              = 0x05
	COMMAND_ERASE_PAGE         = 0x06
	COMMAND_WRITE_PAGE         = 0x07
	COMMAND_XEBLOCK            = 0x08
	COMMAND_XWPAGE             = 0x09
	COMMAND_CRCRX              = 0x10
	COMMAND_READ_RANGE         = 0x11
	COMMAND_XRRANGE            = 0x12
	COMMAND_SET_ATTRIBUTE      = 0x13
	COMMAND_GET_ATTRIBUTE      = 0x14
	COMMAND_CRC_INTERNAL_FLASH = 0x15
	COMMAND_CRCEF              = 0x16
	COMMAND_XEPAGE             = 0x17
	COMMAND_XFINIT             = 0x18
	COMMAND_CLKOUT             = 0x19
	COMMAND_WUSER              = 0x20
	COMMAND_CHANGE_BAUD_RATE   = 0x21

	# Responses from the bootloader.
	RESPONSE_OVERFLOW           = 0x10
	RESPONSE_PONG               = 0x11
	RESPONSE_BADADDR            = 0x12
	RESPONSE_INTERROR           = 0x13
	RESPONSE_BADARGS            = 0x14
	RESPONSE_OK                 = 0x15
	RESPONSE_UNKNOWN            = 0x16
	RESPONSE_XFTIMEOUT          = 0x17
	RESPONSE_XFEPE              = 0x18
	RESPONSE_CRCRX              = 0x19
	RESPONSE_READ_RANGE         = 0x20
	RESPONSE_XRRANGE            = 0x21
	RESPONSE_GET_ATTRIBUTE      = 0x22
	RESPONSE_CRC_INTERNAL_FLASH = 0x23
	RESPONSE_CRCXF              = 0x24
	RESPONSE_INFO               = 0x25
	RESPONSE_CHANGE_BAUD_FAIL   = 0x26

	# Tell the bootloader to reset its buffer to handle a new command.
	SYNC_MESSAGE = bytes([0x00, 0xFC, 0x05])

	# Open the serial port to the chip/bootloader
	def open_link_to_board (self):
		# Check to see if the serial port was specified or we should find
		# one to use
		if self.args.port == None:
			# Nothing was specified, so we look for something marked as "Tock".
			# If we can't find something, it is OK.
			device_name = 'tock'
			must_match = False
			print('No device name specified. Using default "{}"'.format(device_name))
		else:
			# Since we specified, make sure we connect to that.
			device_name = self.args.port
			must_match = True

		# Look for a matching port
		ports = list(serial.tools.list_ports.grep(device_name))
		if len(ports) == 1:
			# Easy case, use the one that matches
			print('Using "{}"'.format(ports[0]))
			index = 0
		elif len(ports) > 1:
			index = menu(ports, return_type='index')
		else:
			if must_match:
				# We want to find a very specific board. If this does not
				# exist, we want to fail.
				raise TockLoaderException('Could not find a board matching "{}"'.format(device_name))

			# Just find any port and use the first one
			ports = list(serial.tools.list_ports.comports())
			# Mac's will report Bluetooth devices with serial, which is
			# almost certainly never what you want, so drop these
			ports = [p for p in ports if 'Bluetooth-Incoming-Port' not in p[0]]
			if len(ports) == 0:
				raise TockLoaderException('No serial ports found. Is the board connected?')

			print('No serial port with device name "{}" found'.format(device_name))
			print('Found {} serial port(s).'.format(len(ports)))

			if len(ports) == 1:
				print('Using "{}"'.format(ports[0]))
				index = 0
			else:
				index = menu(ports, return_type='index')
		port = ports[index][0]
		set_terminal_title_from_port_info(ports[index])

		# Open the actual serial port
		self.sp = serial.Serial()
		self.sp.port = port
		self.sp.baudrate = 115200
		self.sp.parity=serial.PARITY_NONE
		self.sp.stopbits=1
		self.sp.xonxoff=0
		self.sp.rtscts=0
		self.sp.timeout=0.5
		# Try to set initial conditions, but not all platforms support them.
		# https://github.com/pyserial/pyserial/issues/124#issuecomment-227235402
		self.sp.dtr = 0
		self.sp.rts = 0
		self.sp.open()

	def get_serial_port (self):
		return self.sp

	# Reset the chip and assert the bootloader select pin to enter bootloader
	# mode.
	def _toggle_bootloader_entry (self):
		# Reset the SAM4L
		self.sp.dtr = 1
		# Set RTS to make the SAM4L go into bootloader mode
		self.sp.rts = 1
		# Wait for the reset to take effect
		time.sleep(0.1)
		# Let the SAM4L startup
		self.sp.dtr = 0
		# Wait for 500 ms to make sure the bootloader enters bootloader mode
		time.sleep(0.5)
		# The select line can go back high
		self.sp.rts = 0

	# Reset the chip and assert the bootloader select pin to enter bootloader
	# mode.
	def enter_bootloader_mode (self):
		self._toggle_bootloader_entry()

		# Make sure the bootloader is actually active and we can talk to it.
		try:
			self._ping_bootloader_and_wait_for_response()
		except KeyboardInterrupt:
			raise TockLoaderException('Exiting.')
		except:
			try:
				# Give it another go
				time.sleep(1)
				self._toggle_bootloader_entry()
				self._ping_bootloader_and_wait_for_response()
			except KeyboardInterrupt:
				raise TockLoaderException('Exiting.')
			except:
				print('Error connecting to bootloader. No "pong" received.')
				print('Things that could be wrong:')
				print('  - The bootloader is not flashed on the chip')
				print('  - The DTR/RTS lines are not working')
				print('  - The serial port being used is incorrect')
				print('  - The bootloader API has changed')
				print('  - There is a bug in this script')
				raise TockLoaderException('Could not attach to the bootloader')

		# Speculatively try to get a faster baud rate.
		self._change_baud_rate(self.args.baud_rate)

	# Reset the chip to exit bootloader mode
	def exit_bootloader_mode (self):
		if self.args.jtag:
			return

		# Reset the SAM4L
		self.sp.dtr = 1
		# Make sure this line is de-asserted (high)
		self.sp.rts = 0
		# Let the reset take effect
		time.sleep(0.1)
		# Let the SAM4L startup
		self.sp.dtr = 0

	# Throws an exception if the device does not respond with a PONG
	def _ping_bootloader_and_wait_for_response (self):
		for i in range(30):
			# Try to ping the SAM4L to ensure it is in bootloader mode
			ping_pkt = bytes([self.ESCAPE_CHAR, self.COMMAND_PING])
			self.sp.write(ping_pkt)

			# Read much more than we need in case something got in the
			# serial channel that we need to clear.
			ret = self.sp.read(200)

			if len(ret) == 2 and ret[1] == self.RESPONSE_PONG:
				return
		raise TockLoaderException('No PONG received')

	# Setup a command to send to the bootloader and handle the response.
	def _issue_command (self, command, message, sync, response_len, response_code, show_errors=True):
		if sync:
			self.sp.write(self.SYNC_MESSAGE)
			time.sleep(0.0001)

		# Generate the message to send to the bootloader
		escaped_message = message.replace(bytes([self.ESCAPE_CHAR]), bytes([self.ESCAPE_CHAR, self.ESCAPE_CHAR]))
		pkt = escaped_message + bytes([self.ESCAPE_CHAR, command])
		self.sp.write(pkt)

		# Response has a two byte header, then response_len bytes
		ret = self.sp.read(2 + response_len)

		# Response is escaped, so we need to handle that
		while True:
			num_escaped = ret.count(bytes([self.ESCAPE_CHAR, self.ESCAPE_CHAR]))
			if num_escaped > 0:
				# De-escape, and then read in the missing characters.
				ret = ret.replace(bytes([self.ESCAPE_CHAR, self.ESCAPE_CHAR]), bytes([self.ESCAPE_CHAR]))
				ret += self.sp.read(num_escaped)
			else:
				break

		if len(ret) < 2:
			if show_errors:
				print('Error: No response after issuing command')
			return (False, bytes())

		if ret[0] != self.ESCAPE_CHAR:
			if show_errors:
				print('Error: Invalid response from bootloader (no escape character)')
			return (False, ret[0:2])
		if ret[1] != response_code:
			if show_errors:
				print('Error: Expected return type {:x}, got return {:x}'.format(response_code, ret[1]))
			return (False, ret[0:2])
		if len(ret) != 2 + response_len:
			if show_errors:
				print('Error: Incorrect number of bytes received. Expected {}, got {}.'.format(2+response_len, len(ret)))
			return (False, ret[0:2])

		return (True, ret[2:])

	# If the bootloader on the board supports it and if it succeeds, try
	# to increase the baud rate to make everything faster.
	def _change_baud_rate (self, baud_rate):
		pkt = struct.pack('<BI', 0x01, baud_rate)
		success, ret = self._issue_command(self.COMMAND_CHANGE_BAUD_RATE, pkt, True, 0, self.RESPONSE_OK, show_errors=False)

		if success:
			# The bootloader is new enough to support this.
			# Increase the baud rate
			self.sp.baudrate = baud_rate
			# Now confirm that everything is working.
			pkt = struct.pack('<BI', 0x02, baud_rate)
			success, ret = self._issue_command(self.COMMAND_CHANGE_BAUD_RATE, pkt, False, 0, self.RESPONSE_OK, show_errors=False)

			if not success:
				# Something went wrong. Go back to old baud rate
				self.sp.baudrate = 115200

	# Write pages until a binary has been flashed. binary must have a length that
	# is a multiple of 512.
	def flash_binary (self, address, binary, pad=True):
		# Make sure the binary is a multiple of 512 bytes by padding 0xFFs
		if len(binary) % 512 != 0:
			remaining = 512 - (len(binary) % 512)
			if pad:
				binary += bytes([0xFF]*remaining)
				print('NOTE: Padding binary with {} 0xFFs.'.format(remaining))
			else:
				# Don't pad, actually use the bytes already on the chip
				missing = self.read_range(address + len(binary), remaining)
				binary += missing
				print('NOTE: Padding binary with {} bytes already on chip.'.format(remaining))

		# Loop through the binary 512 bytes at a time until it has been flashed
		# to the chip.
		for i in range(len(binary) // 512):
			# Create the packet that we send to the bootloader. First four
			# bytes are the address of the page.
			pkt = struct.pack('<I', address + (i*512))

			# Next are the 512 bytes that go into the page.
			pkt += binary[i*512: (i+1)*512]

			# Write to bootloader
			success, ret = self._issue_command(self.COMMAND_WRITE_PAGE, pkt, True, 0, self.RESPONSE_OK)

			if not success:
				print('Error: Error when flashing page')
				if ret[1] == self.RESPONSE_BADADDR:
					raise TockLoaderException('Error: RESPONSE_BADADDR: Invalid address for page to write (address: 0x{:X}'.format(address + (i*512)))
				elif ret[1] == self.RESPONSE_INTERROR:
					raise TockLoaderException('Error: RESPONSE_INTERROR: Internal error when writing flash')
				elif ret[1] == self.RESPONSE_BADARGS:
					raise TockLoaderException('Error: RESPONSE_BADARGS: Invalid length for flash page write')
				else:
					raise TockLoaderException('Error: 0x{:X}'.format(ret[1]))

		# And check the CRC
		self._check_crc(address, binary)

	# Read a specific range of flash.
	def read_range (self, address, length):
		# Can only read up to 4095 bytes at a time.
		MAX_READ = 4095
		read = bytes()
		this_length = 0
		remaining = length
		while remaining > 0:
			if remaining > MAX_READ:
				this_length = MAX_READ
				remaining -= MAX_READ
			else:
				this_length = remaining
				remaining = 0

			message = struct.pack('<IH', address, this_length)
			success, flash = self._issue_command(self.COMMAND_READ_RANGE, message, True, this_length, self.RESPONSE_READ_RANGE)

			if not success:
				raise TockLoaderException('Error: Could not read flash')
			else:
				read += flash

			address += this_length

		return read

	# Erase a specific page.
	def erase_page (self, address):
		message = struct.pack('<I', address)
		success, ret = self._issue_command(self.COMMAND_ERASE_PAGE, message, True, 0, self.RESPONSE_OK)

		if not success:
			if ret[1] == self.RESPONSE_BADADDR:
				raise TockLoaderException('Error: Page erase address was not on a page boundary.')
			elif ret[1] == self.RESPONSE_BADARGS:
				raise TockLoaderException('Error: Need to supply erase page with correct 4 byte address.')
			elif ret[1] == self.RESPONSE_INTERROR:
				raise TockLoaderException('Error: Internal error when erasing flash page.')
			else:
				raise TockLoaderException('Error: 0x{:X}'.format(ret[1]))

	# Get the bootloader to compute a CRC
	def _get_crc_internal_flash (self, address, length):
		message = struct.pack('<II', address, length)
		success, crc = self._issue_command(self.COMMAND_CRC_INTERNAL_FLASH, message, True, 4, self.RESPONSE_CRC_INTERNAL_FLASH)

		# There is a bug in a version of the bootloader where the CRC returns 6
		# bytes and not just 4. Need to read just in case to grab those extra
		# bytes.
		self.sp.read(2)

		if not success:
			if crc[1] == self.RESPONSE_BADADDR:
				raise TockLoaderException('Error: RESPONSE_BADADDR: Invalid address for CRC (address: 0x{:X})'.format(address))
			elif crc[1] == self.RESPONSE_BADARGS:
				raise TockLoaderException('Error: RESPONSE_BADARGS: Invalid length for CRC check')
			else:
				raise TockLoaderException('Error: 0x{:X}'.format(crc[1]))

		return crc

	# Compares the CRC of the local binary to the one calculated by the bootloader
	def _check_crc (self, address, binary):
		# Check the CRC
		crc_data = self._get_crc_internal_flash(address, len(binary))

		# Now interpret the returned bytes as the CRC
		crc_bootloader = struct.unpack('<I', crc_data[0:4])[0]

		# Calculate the CRC locally
		crc_function = crcmod.mkCrcFun(0x104c11db7, initCrc=0, xorOut=0xFFFFFFFF)
		crc_loader = crc_function(binary, 0)

		if crc_bootloader != crc_loader:
			raise TockLoaderException('Error: CRC check failed. Expected: 0x{:04x}, Got: 0x{:04x}'.format(crc_loader, crc_bootloader))
		else:
			print('CRC check passed. Binaries successfully loaded.')

	# Get a single attribute.
	def get_attribute (self, index):
		message = struct.pack('<B', index)
		success, ret = self._issue_command(self.COMMAND_GET_ATTRIBUTE, message, True, 64, self.RESPONSE_GET_ATTRIBUTE)

		if not success:
			if ret[1] == self.RESPONSE_BADADDR:
				raise TockLoaderException('Error: Attribute number is invalid.')
			elif ret[1] == self.RESPONSE_BADARGS:
				raise TockLoaderException('Error: Need to supply a correct attribute index.')
			else:
				raise TockLoaderException('Error: 0x{:X}'.format(ret[1]))
		return self._decode_attribute(ret)

	def get_all_attributes (self):
		attributes = []
		for index in range(0, 16):
			attributes.append(self.get_attribute(index))
		return attributes

	# Set a single attribute.
	def set_attribute (self, index, raw):
		message = struct.pack('<B', index) + raw
		success, ret = self._issue_command(self.COMMAND_SET_ATTRIBUTE, message, True, 0, self.RESPONSE_OK)

		if not success:
			if ret[1] == self.RESPONSE_BADADDR:
				raise TockLoaderException('Error: Attribute number is invalid.')
			elif ret[1] == self.RESPONSE_BADARGS:
				raise TockLoaderException('Error: Wrong length of attribute set packet.')
			elif ret[1] == self.RESPONSE_INTERROR:
				raise TockLoaderException('Error: Internal error when setting attribute.')
			else:
				raise TockLoaderException('Error: 0x{:X}'.format(ret[1]))

	# For this communication protocol we can safely say the bootloader is
	# present.
	def bootloader_is_present (self):
		return True

	def get_bootloader_version (self):
		success, ret = self._issue_command(self.COMMAND_INFO, bytes(), True, 193, self.RESPONSE_INFO)

		if not success:
			raise TockLoaderException('Error: 0x{:X}'.format(ret[1]))

		length = ret[0]
		json_data = ret[1:1+length].decode('utf-8')
		try:
			info = json.loads(json_data)
			return info['version']
		except:
			# Could not get a valid version from the board.
			# In this case we don't know what the version is.
			return None

	# Figure out which board we are connected to. Most likely done by
	# reading the attributes.
	def determine_current_board (self):
		if self.board and self.arch:
			# These are already set! Yay we are done.
			return

		# The primary (only?) way to do this is to look at attributes
		attributes = self.get_all_attributes()
		for attribute in attributes:
			if attribute and attribute['key'] == 'board' and self.board == None:
				self.board = attribute['value']
			if attribute and attribute['key'] == 'arch' and self.arch == None:
				self.arch = attribute['value']

		# Check that we learned what we needed to learn.
		if self.board == None or self.arch == None:
			raise TockLoaderException('Could not determine the current board or arch')


############################################################################
## JTAG Specific Functions
############################################################################

class JLinkExe(BoardInterface):

	# commands: List of JLinkExe commands. Use {binary} for where the name of
	#           the binary file should be substituted.
	# binary:   A bytes() object that will be used to write to the board.
	# write:    Set to true if the command writes binaries to the board.
	#           Set to false if the command will read bits from the board.
	def _run_jtag_commands (self, commands, binary, write=True):
		delete = True
		if self.args.debug:
			delete = False

		if binary or not write:
			temp_bin = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=delete)
			if write:
				temp_bin.write(binary)

			temp_bin.flush()

			# Update all of the commands with the name of the binary file
			for i,command in enumerate(commands):
				commands[i] = command.format(binary=temp_bin.name)

		with tempfile.NamedTemporaryFile(mode='w', delete=delete) as jlink_file:
			for command in commands:
				jlink_file.write(command + '\n')

			jlink_file.flush()

			jlink_command = 'JLinkExe -device {} -if swd -speed 1200 -AutoConnect 1 {}'.format(self.jtag_device, jlink_file.name)

			if self.args.debug:
				print('Running "{}".'.format(jlink_command))

			def print_output (subp):
				if subp.stdout:
					print(subp.stdout.decode('utf-8'))
				if subp.stderr:
					print(subp.stderr.decode('utf-8'))

			p = subprocess.run(jlink_command.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			if p.returncode != 0:
				print('ERROR: JTAG returned with error code ' + str(p.returncode))
				print_output(p)
				raise TockLoaderException('JTAG error')
			elif self.args.debug:
				print_output(p)

			# check that there was a JTAG programmer and that it found a device
			stdout = p.stdout.decode('utf-8')
			if 'USB...FAILED' in stdout:
				raise TockLoaderException('ERROR: Cannot find JLink hardware. Is USB attached?')
			if 'Can not connect to target.' in stdout:
				raise TockLoaderException('ERROR: Cannot find device. Is JTAG connected?')
			if 'Error while programming flash' in stdout:
				raise TockLoaderException('ERROR: Problem flashing.')

			if write == False:
				# Wanted to read binary, so lets pull that
				temp_bin.seek(0, 0)
				return temp_bin.read()

	# Write using JTAG
	def flash_binary (self, address, binary):
		commands = [
			'r',
			'loadbin {{binary}}, {address:#x}'.format(address=address),
			'verifybin {{binary}}, {address:#x}'.format(address=address),
			'r\ng\nq'
		]

		self._run_jtag_commands(commands, binary)

	# Read a specific range of flash.
	def read_range (self, address, length):

		commands = []
		if self.jtag_device == 'cortex-m0':
			# We are in generic mode, trying to read attributes.
			# We've found that when connecting to a generic
			# `cortex-m0` reset commands sometimes fail, however it
			# seems that reading the binary directly from flash
			# still works, so do that.
			commands = [
				'savebin {{binary}}, {address:#x} {length}'.format(address=address, length=length),
				'\nq'
			]
		else:
			# We already know the specific jtag device we are
			# connected to. This means we can reset and run code.
			commands = [
				'r',
				'savebin {{binary}}, {address:#x} {length}'.format(address=address, length=length),
				'r\ng\nq'
			]

		# Always return a valid byte array (like the serial version does)
		read = bytes()
		result = self._run_jtag_commands(commands, None, write=False)
		if result:
			read += result

		# Check to make sure we didn't get too many
		if len(read) > length:
			read = read[0:length]

		return read

	# Read a specific range of flash.
	def erase_page (self, address):
		binary = bytes([0xFF]*512)
		commands = [
			'r',
			'loadbin {{binary}}, {address:#x}'.format(address=address),
			'verifybin {{binary}}, {address:#x}'.format(address=address),
			'r\ng\nq'
		]

		self._run_jtag_commands(commands, binary)

	# Get a single attribute.
	def get_attribute (self, index):
		address = 0x600 + (64 * index)
		attribute_raw = self.read_range(address, 64)
		return self._decode_attribute(attribute_raw)

	def get_all_attributes (self):
		# Read the entire block of attributes using JTAG.
		# This is much faster.
		def chunks(l, n):
			for i in range(0, len(l), n):
				yield l[i:i + n]
		raw = self.read_range(0x600, 64*16)
		return [self._decode_attribute(r) for r in chunks(raw, 64)]

	# Set a single attribute.
	def set_attribute (self, index, raw):
		address = 0x600 + (64 * index)
		self.flash_binary(address, raw)

	def get_bootloader_version (self):
		address = 0x40E
		version_raw = self.read_range(address, 8)
		try:
			return version_raw.decode('utf-8')
		except:
			return None

	def get_serial_port (self):
		raise TockLoaderException('No serial port for JLinkExe comm channel')

	# Figure out which board we are connected to. Most likely done by
	# reading the attributes.
	def determine_current_board (self):
		if self.board and self.arch and self.jtag_device:
			# These are already set! Yay we are done.
			return

		# The primary (only?) way to do this is to look at attributes
		attributes = self.get_all_attributes()
		for attribute in attributes:
			if attribute and attribute['key'] == 'board' and self.board == None:
				self.board = attribute['value']
			if attribute and attribute['key'] == 'arch' and self.arch == None:
				self.arch = attribute['value']
			if attribute and attribute['key'] == 'jldevice':
				self.jtag_device = attribute['value']

		# Check that we learned what we needed to learn.
		if self.board == None or self.arch == None or self.jtag_device == 'cortex-m0':
			raise TockLoaderException('Could not determine the current board or arch or jtag device name')


################################################################################
## Application Object
################################################################################

class App:
	def __init__ (self, tbfh, address, name, binary=None):
		self.tbfh = tbfh
		self.address = address
		self.name = name
		self.binary = binary

	def is_sticky (self):
		return self.tbfh.is_sticky()

	# Return the total size (including TBF header) of this app in bytes.
	def get_size (self):
		return self.tbfh.get_app_size()

	def get_header_binary (self):
		return self.tbfh.get_binary()

	def set_binary (self, binary):
		self.binary = binary

	def set_address (self, address):
		self.address = address

	def has_binary (self):
		return self.binary != None

	def info (self, verbose=False):
		offset = self.address
		fields = self.tbfh.fields

		out = ''
		out += 'Name:                  {}\n'.format(self.name)
		out += 'Enabled:               {}\n'.format(self.tbfh.is_enabled())
		out += 'Sticky:                {}\n'.format(self.tbfh.is_sticky())
		out += 'Total Size in Flash:   {} bytes\n'.format(self.get_size())

		if verbose:
			out += 'Flash Start Address:   {:#010x}\n'.format(offset)
			out += 'Flash End Address:     {:#010x}\n'.format(offset+self.get_size()-1)
			out += 'Entry Address:         {:#010x}\n'.format(offset+fields['entry_offset'])
			out += 'Relocate Data Address: {:#010x} (length: {} bytes)\n'.format(offset+fields['rel_data_offset'], fields['rel_data_size'])
			out += 'Text Address:          {:#010x} (length: {} bytes)\n'.format(offset+fields['text_offset'], fields['text_size'])
			out += 'GOT Address:           {:#010x} (length: {} bytes)\n'.format(offset+fields['got_offset'], fields['got_size'])
			out += 'Data Address:          {:#010x} (length: {} bytes)\n'.format(offset+fields['data_offset'], fields['data_size'])
			out += 'Minimum Stack Size:    {} bytes\n'.format(fields['min_stack_len'])
			out += 'Minimum Heap Size:     {} bytes\n'.format(fields['min_app_heap_len'])
			out += 'Minimum Grant Size:    {} bytes'.format(fields['min_kernel_heap_len'])
		return out

	def __str__ (self):
		return self.name


################################################################################
## Tock Application Bundle Object
################################################################################

class TAB:
	def __init__ (self, tab_name):
		self.tab = tarfile.open(tab_name)

	def extract_app (self, arch):
		binary_tarinfo = self.tab.getmember('{}.bin'.format(arch))
		binary = self.tab.extractfile(binary_tarinfo).read()

		# First get the TBF header from the correct binary in the TAB
		tbfh = TBFHeader(binary)

		if tbfh.is_valid():
			start = tbfh.fields['package_name_offset']
			end = start+tbfh.fields['package_name_size']
			name = binary[start:end].decode('utf-8')

			return App(tbfh, None, name, binary)
		else:
			raise TockLoaderException('Invalid TBF found in app in TAB')

	def is_compatible_with_board (self, board):
		metadata = self.parse_metadata()
		if metadata['tab-version'] == 1:
			return 'only-for-boards' not in metadata or \
			       board in metadata['only-for-boards'] or \
			       metadata['only-for-boards'] == ''
		else:
			raise TockLoaderException('Unable to understand version {} of metadata'.format(metadata['tab-version']))

	def parse_metadata (self):
		metadata_tarinfo = self.tab.getmember('metadata.toml')
		metadata_str = self.tab.extractfile(metadata_tarinfo).read().decode('utf-8')
		return pytoml.loads(metadata_str)

	def get_supported_architectures (self):
		contained_files = self.tab.getnames()
		return [i[:-4] for i in contained_files if i[-4:] == '.bin']

	def get_tbf_header (self):
		# Find a .bin file
		for f in self.tab.getnames():
			if f[-4:] == '.bin':
				binary_tarinfo = self.tab.getmember(f)
				binary = self.tab.extractfile(binary_tarinfo).read()

				# Get the TBF header from a binary in the TAB
				return TBFHeader(binary)
		return None

	def __str__ (self):
		out = ''
		metadata = self.parse_metadata()
		out += 'TAB: {}\n'.format(metadata['name'])
		for k,v in sorted(metadata.items()):
			if k == 'name':
				continue
			out += '  {}: {}\n'.format(k,v)
		out += '  supported architectures: {}\n'.format(', '.join(self.get_supported_architectures()))
		out += '  TBF Header\n'
		out += textwrap.indent(str(self.get_tbf_header()), '    ')
		return out


################################################################################
## Tock Binary Format Header
################################################################################

class TBFHeader:
	def __init__ (self, buffer):
		self.valid = False
		self.fields = {}

		# Need at least a version number
		if len(buffer) < 4:
			return

		# Get the version number
		self.version = struct.unpack('<I', buffer[0:4])[0]

		if (self.version == 1 or self.version == 2) and len(buffer) >= 72:
			# Version 1 and 2 have the same first fields
			base = struct.unpack('<IIIIIIIIIIIIIIIII', buffer[4:72])
			self.fields['total_size'] = base[0]
			self.fields['entry_offset'] = base[1]
			self.fields['rel_data_offset'] = base[2]
			self.fields['rel_data_size'] = base[3]
			self.fields['text_offset'] = base[4]
			self.fields['text_size'] = base[5]
			self.fields['got_offset'] = base[6]
			self.fields['got_size'] = base[7]
			self.fields['data_offset'] = base[8]
			self.fields['data_size'] = base[9]
			self.fields['bss_mem_offset'] = base[10]
			self.fields['bss_mem_size'] = base[11]
			self.fields['min_stack_len'] = base[12]
			self.fields['min_app_heap_len'] = base[13]
			self.fields['min_kernel_heap_len'] = base[14]
			self.fields['package_name_offset'] = base[15]
			self.fields['package_name_size'] = base[16]
		else:
			return

		if self.version == 1 and len(buffer) >= 76:
			others = struct.unpack('<I', buffer[72:76])
			checksum = others[0]

			if self._checksum() == checksum:
				self.valid = True

		elif self.version == 2 and len(buffer) >= 80:
			others = struct.unpack('<II', buffer[72:80])
			self.fields['flags'] = others[0]
			checksum = others[1]

			if self._checksum() == checksum:
				self.valid = True

	def is_valid (self):
		return self.valid

	def is_enabled (self):
		if not self.valid:
			return False
		elif self.version == 1:
			# Version 1 apps don't have this bit so they are just always enabled
			return True
		else:
			return self.fields['flags'] & 0x01 == 0x01

	def is_sticky (self):
		if not self.valid:
			return False
		elif self.version == 1:
			# No sticky bit in version 1, so they are not sticky
			return False
		else:
			return self.fields['flags'] & 0x02 == 0x02

	def set_flag(self, flag_name, flag_value):
		if self.version == 1 or not self.valid:
			return

		if flag_name == 'enable':
			if flag_value:
				self.fields['flags'] |= 0x01;
			else:
				self.fields['flags'] &= ~0x01;

		elif flag_name == 'sticky':
			if flag_value:
				self.fields['flags'] |= 0x02;
			else:
				self.fields['flags'] &= ~0x02;

	def get_app_size (self):
		return self.fields['total_size']

	def get_name_offset (self):
		return self.fields['package_name_offset']

	def get_name_length (self):
		return self.fields['package_name_size']

	# Return a buffer containing the header repacked as a binary buffer
	def get_binary (self):
		buf = struct.pack('<IIIIIIIIIIIIIIIIII',
			self.version, self.fields['total_size'], self.fields['entry_offset'],
			self.fields['rel_data_offset'], self.fields['rel_data_size'],
			self.fields['text_offset'], self.fields['text_size'],
			self.fields['got_offset'], self.fields['got_size'],
			self.fields['data_offset'], self.fields['data_size'],
			self.fields['bss_mem_offset'], self.fields['bss_mem_size'],
			self.fields['min_stack_len'], self.fields['min_app_heap_len'],
			self.fields['min_kernel_heap_len'], self.fields['package_name_offset'],
			self.fields['package_name_size'])

		if self.version == 2:
			buf += struct.pack('<I', self.fields['flags'])

		buf += struct.pack('<I', self._checksum())
		return buf

	def _checksum (self):
		if self.version == 1:
			return self.version ^ self.fields['total_size'] ^ self.fields['entry_offset'] \
			      ^ self.fields['rel_data_offset'] ^ self.fields['rel_data_size'] ^ self.fields['text_offset'] \
			      ^ self.fields['text_size'] ^ self.fields['got_offset'] ^ self.fields['got_size'] \
			      ^ self.fields['data_offset'] ^ self.fields['data_size'] ^ self.fields['bss_mem_offset'] \
			      ^ self.fields['bss_mem_size'] ^ self.fields['min_stack_len'] \
			      ^ self.fields['min_app_heap_len'] ^ self.fields['min_kernel_heap_len'] \
			      ^ self.fields['package_name_offset'] ^ self.fields['package_name_size']

		elif self.version == 2:
			return self.version ^ self.fields['total_size'] ^ self.fields['entry_offset'] \
			      ^ self.fields['rel_data_offset'] ^ self.fields['rel_data_size'] ^ self.fields['text_offset'] \
			      ^ self.fields['text_size'] ^ self.fields['got_offset'] ^ self.fields['got_size'] \
			      ^ self.fields['data_offset'] ^ self.fields['data_size'] ^ self.fields['bss_mem_offset'] \
			      ^ self.fields['bss_mem_size'] ^ self.fields['min_stack_len'] \
			      ^ self.fields['min_app_heap_len'] ^ self.fields['min_kernel_heap_len'] \
			      ^ self.fields['package_name_offset'] ^ self.fields['package_name_size'] \
			      ^ self.fields['flags']
		else:
			return 0

	def __str__ (self):
		out = ''
		out += '{:<19}: {:>8}\n'.format('version', self.version)
		for k,v in sorted(self.fields.items()):
			out += '{:<19}: {:>8} {:>#10x}\n'.format(k, v, v)
			if k == 'flags':
				out += '  {:<17}: {:>8}\n'.format('enabled', v & 0x01)
				out += '  {:<17}: {:>8}\n'.format('sticky', (v & 0x02) >> 1)
		out += '{:<19}:          {:>#10x}'.format('checksum', self._checksum(), self._checksum())
		return out


################################################################################
## Command Functions
################################################################################

# Checks for a Makefile, and it it exists runs `make`.
def check_and_run_make (args):
	if args.make:
		if os.path.isfile('./Makefile'):
			print('Running `make`...')
			p = subprocess.Popen(['make'])
			out, err = p.communicate()
			if p.returncode != 0:
				print('Error running make.')
				sys.exit(1)

# Load in Tock Application Bundle (TAB) files. If none are specified, this
# searches for them in subfolders.
def collect_tabs (args, wait=True):
	tab_names = args.tab

	# Check if any tab files were specified. If not, find them based
	# on where this tool is being run.
	if len(tab_names) == 0 or tab_names[0] == '':
		print('No TABs passed to tockloader. Searching for TABs in subdirectories.')

		# First check to see if things could be built that haven't been
		if os.path.isfile('./Makefile'):
			p = subprocess.Popen(['make', '-n'], stdout=subprocess.PIPE)
			out, err = p.communicate()
			# Check for the name of the compiler to see if there is work
			# to be done
			if 'arm-none-eabi-gcc' in out.decode('utf-8'):
				print('Warning! There are uncompiled changes!')
				print('You may want to run `make` before loading the application.')

		# Search for ".tab" files
		tab_names = glob.glob('./**/*.tab', recursive=True)
		if len(tab_names) == 0:
			raise TockLoaderException('No TAB files found.')

		print('Using: {}'.format(tab_names))
		if wait:
			print('Waiting one second before continuing...')
			time.sleep(1)

	# Concatenate the binaries.
	tabs = []
	for tab_name in tab_names:
		try:
			tabs.append(TAB(tab_name))
		except Exception as e:
			print('Error opening and reading "{}"'.format(tab_name))

	return tabs


def command_listen (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)
	tock_loader.run_terminal()


def command_list (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)
	tock_loader.list_apps(args.app_address, args.verbose, args.quiet)


def command_install (args):
	check_and_run_make(args)

	# Load in all TABs
	tabs = collect_tabs(args)

	# Install the apps on the board
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	# Figure out how we want to do updates
	replace = 'yes'
	if args.no_replace:
		replace = 'no'

	print('Installing apps on the board...')
	tock_loader.install(tabs, args.app_address, replace=replace)


def command_update (args):
	check_and_run_make(args)
	tabs = collect_tabs(args)

	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Updating application(s) on the board...')
	tock_loader.install(tabs, args.app_address, replace='only')


def command_uninstall (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Removing app(s) {} from board...'.format(', '.join(args.name)))
	tock_loader.uninstall_app(args.name, args.app_address, args.force)


def command_erase_apps (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Removing apps...')
	tock_loader.erase_apps(args.app_address, args.force)


def command_enable_app (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Enabling apps...')
	tock_loader.set_flag(args.name, 'enable', True, args.app_address)


def command_disable_app (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Disabling apps...')
	tock_loader.set_flag(args.name, 'enable', False, args.app_address)


def command_sticky_app (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Making apps sticky...')
	tock_loader.set_flag(args.name, 'sticky', True, args.app_address)


def command_unsticky_app (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Making apps no longer sticky...')
	tock_loader.set_flag(args.name, 'sticky', False, args.app_address)


def command_flash (args):
	check_and_run_make(args)

	# Load in all binaries
	binary = bytes()
	for binary_name in args.binary:
		# check that file isn't a `.hex` file
		if binary_name.endswith('.hex'):
			exception_string = 'Error: Cannot flash ".hex" files.'
			exception_string += ' Likely you meant to use a ".bin" file but used an intel hex file by accident.'
			raise TockLoaderException(exception_string)

		# add contents to binary
		with open(binary_name, 'rb') as f:
			binary += f.read()

	# Flash the binary to the chip
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Flashing binar(y|ies) to board...')
	tock_loader.flash_binary(binary, args.address)


def command_list_attributes (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Listing attributes...')
	tock_loader.list_attributes()


def command_set_attribute (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Setting attribute...')
	tock_loader.set_attribute(args.key, args.value)


def command_remove_attribute (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Removing attribute...')
	tock_loader.remove_attribute(args.key)


def command_info (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('tockloader version: {}'.format(__version__))
	print('Showing all properties of the board...')
	tock_loader.info(args.app_address)


def command_inspect_tab (args):
	tabs = collect_tabs(args, wait=False)

	if len(tabs) == 0:
		raise TockLoaderException('No TABs found to inspect')

	print('Inspecting TABs...')
	for tab in tabs:
		print(tab)
		print('')


################################################################################
## Setup and parse command line arguments
################################################################################

def main ():
	# Create a common parent parser for arguments shared by all subparsers
	parent = argparse.ArgumentParser(add_help=False)

	# All commands need a serial port to talk to the board
	parent.add_argument('--port', '-p', '--device', '-d',
		help='The serial port or device name to use',
		metavar='STR')

	parent.add_argument('--make',
		action='store_true',
		help='Run `make` before loading an application')

	parent.add_argument('--debug',
		action='store_true',
		help='Print additional debugging information')

	parent.add_argument('--version',
		action='version',
		version=__version__,
		help='Print Tockloader version and exit')

	# Get the list of arguments before any command
	before_command_args = parent.parse_known_args()

	# The top-level parser object
	parser = argparse.ArgumentParser(parents=[parent])

	# Parser for all app related commands
	parent_apps = argparse.ArgumentParser(add_help=False)
	parent_apps.add_argument('--app-address', '-a',
		help='Address where apps are located',
		type=lambda x: int(x, 0),
		default=0x30000)
	parent_apps.add_argument('--force',
		help='Allow apps on boards that are not listed as compatible',
		action='store_true')

	# Parser for most commands
	parent_jtag = argparse.ArgumentParser(add_help=False)
	parent_jtag.add_argument('--jtag',
		action='store_true',
		help='Use JTAG and JLinkExe to flash.')
	parent_jtag.add_argument('--jtag-device',
		default='cortex-m0',
		help='The device type to pass to JLinkExe. Useful for initial commissioning.')
	parent_jtag.add_argument('--board',
		default=None,
		help='Explicitly specify the board that is being targeted.')
	parent_jtag.add_argument('--arch',
		default=None,
		help='Explicitly specify the architecture of the board that is being targeted.')
	parent_jtag.add_argument('--baud-rate',
		default=600000,
		type=int,
		help='If using serial, set the target baud rate.')

	# Support multiple commands for this tool
	subparser = parser.add_subparsers(
		title='Commands',
		metavar='')

	listen = subparser.add_parser('listen',
		parents=[parent],
		help='Open a terminal to receive UART data')
	listen.set_defaults(func=command_listen)

	listcmd = subparser.add_parser('list',
		parents=[parent, parent_apps, parent_jtag],
		help='List the apps installed on the board')
	listcmd.set_defaults(func=command_list)
	listcmd.add_argument('--verbose', '-v',
		help='Print more information',
		action='store_true')
	listcmd.add_argument('--quiet', '-q',
		help='Print just a list of application names',
		action='store_true')

	install = subparser.add_parser('install',
		parents=[parent, parent_apps, parent_jtag],
		help='Install apps on the board')
	install.set_defaults(func=command_install)
	install.add_argument('tab',
		help='The TAB or TABs to install',
		nargs='*')
	install.add_argument('--no-replace',
		help='Install apps again even if they are already there',
		action='store_true')

	update = subparser.add_parser('update',
		parents=[parent, parent_apps, parent_jtag],
		help='Update an existing app with this version')
	update.set_defaults(func=command_update)
	update.add_argument('tab',
		help='The TAB or TABs to replace',
		nargs='*')

	uninstall = subparser.add_parser('uninstall',
		parents=[parent, parent_apps, parent_jtag],
		help='Remove an already flashed app')
	uninstall.set_defaults(func=command_uninstall)
	uninstall.add_argument('name',
		help='The name of the app(s) to remove',
		nargs='*')

	eraseapps = subparser.add_parser('erase-apps',
		parents=[parent, parent_apps, parent_jtag],
		help='Delete apps from the board')
	eraseapps.set_defaults(func=command_erase_apps)

	enableapp = subparser.add_parser('enable-app',
		parents=[parent, parent_apps, parent_jtag],
		help='Enable an app so the kernel runs it')
	enableapp.set_defaults(func=command_enable_app)
	enableapp.add_argument('name',
		help='The name of the app(s) to enable',
		nargs='*')

	disableapp = subparser.add_parser('disable-app',
		parents=[parent, parent_apps, parent_jtag],
		help='Disable an app so it will not be started')
	disableapp.set_defaults(func=command_disable_app)
	disableapp.add_argument('name',
		help='The name of the app(s) to disable',
		nargs='*')

	stickyapp = subparser.add_parser('sticky-app',
		parents=[parent, parent_apps, parent_jtag],
		help='Make an app sticky so it is hard to erase')
	stickyapp.set_defaults(func=command_sticky_app)
	stickyapp.add_argument('name',
		help='The name of the app(s) to sticky',
		nargs='*')

	unstickyapp = subparser.add_parser('unsticky-app',
		parents=[parent, parent_apps, parent_jtag],
		help='Make an app unsticky (the normal setting)')
	unstickyapp.set_defaults(func=command_unsticky_app)
	unstickyapp.add_argument('name',
		help='The name of the app(s) to unsticky',
		nargs='*')

	flash = subparser.add_parser('flash',
		parents=[parent, parent_jtag],
		help='Flash binaries to the chip')
	flash.set_defaults(func=command_flash)
	flash.add_argument('binary',
		help='The binary file or files to flash to the chip',
		nargs='+')
	flash.add_argument('--address', '-a',
		help='Address to flash the binary at',
		type=lambda x: int(x, 0),
		default=0x30000)

	listattributes = subparser.add_parser('list-attributes',
		parents=[parent, parent_jtag],
		help='List attributes stored on the board')
	listattributes.set_defaults(func=command_list_attributes)

	setattribute = subparser.add_parser('set-attribute',
		parents=[parent, parent_jtag],
		help='Store attribute on the board')
	setattribute.set_defaults(func=command_set_attribute)
	setattribute.add_argument('key',
		help='Attribute key')
	setattribute.add_argument('value',
		help='Attribute value')

	removeattribute = subparser.add_parser('remove-attribute',
		parents=[parent, parent_jtag],
		help='Remove attribute from the board')
	removeattribute.set_defaults(func=command_remove_attribute)
	removeattribute.add_argument('key',
		help='Attribute key')

	info = subparser.add_parser('info',
		parents=[parent, parent_apps, parent_jtag],
		help='Verbose information about the connected board')
	info.set_defaults(func=command_info)

	inspect_tab = subparser.add_parser('inspect-tab',
		parents=[parent],
		help='Get details about a TAB')
	inspect_tab.set_defaults(func=command_inspect_tab)
	inspect_tab.add_argument('tab',
		help='The TAB or TABs to inspect',
		nargs='*')

	argcomplete.autocomplete(parser)
	args = parser.parse_args()

	# Concat the args before the command with those that were specified
	# after the command. This is a workaround because for some reason python
	# won't parse a set of parent options before the "command" option
	# (or it is getting overwritten).
	for key,value in vars(before_command_args[0]).items():
		if getattr(args, key) == None and value != None:
			setattr(args, key, value)

	if hasattr(args, 'func'):
		try:
			args.func(args)
		except TockLoaderException as e:
			print(e)
			sys.exit(1)
	else:
		print('Missing Command.\n')
		parser.print_help()
		sys.exit(1)


if __name__ == '__main__':
	main()
