#!/usr/bin/env python3

import argparse
import binascii
import glob
import os
import struct
import subprocess
import sys
import time

import crcmod
import serial
import serial.tools.list_ports
import serial.tools.miniterm

from ._version import __version__


################################################################################
## Global Bootloader Constants
################################################################################

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
COMMAND_SATTR              = 0x13
COMMAND_GATTR              = 0x14
COMMAND_CRC_INTERNAL_FLASH = 0x15
COMMAND_CRCEF              = 0x16
COMMAND_XEPAGE             = 0x17
COMMAND_XFINIT             = 0x18
COMMAND_CLKOUT             = 0x19
COMMAND_WUSER              = 0x20

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
RESPONSE_GATTR              = 0x22
RESPONSE_CRC_INTERNAL_FLASH = 0x23
RESPONSE_CRCXF              = 0x24
RESPONSE_INFO               = 0x25

# Tell the bootloader to reset its buffer to handle a new command.
SYNC_MESSAGE = bytes([0x00, ESCAPE_CHAR, COMMAND_RESET])


################################################################################
## Main Bootloader Interface
################################################################################

class TockLoader:
	def __init__ (self, args):
		self.debug = args.debug


	# Open the serial port to the chip/bootloader
	def open (self, port):

		# Check to see if the serial port was specified or we should find
		# one to use
		if port == None:
			print('No serial port specified. Discovering attached serial devices...')
			# Start by looking for one with "tock" in the description
			ports = list(serial.tools.list_ports.grep('tock'))
			if len(ports) > 0:
				# Use the first one
				print('Using "{}"'.format(ports[0]))
				port = ports[0][0]
			else:
				# Just find any port and use the first one
				ports = list(serial.tools.list_ports.comports())
				# Mac's will report Bluetooth devices with serial, which is
				# almost certainly never what you want, so drop these
				ports = [p for p in ports if 'Bluetooth-Incoming-Port' not in p[0]]
				if len(ports) == 0:
					print('No serial ports found. Is the board connected?')
					return False

				print('Found {} serial port(s).'.format(len(ports)))
				print('Using "{}"'.format(ports[0]))
				port = ports[0][0]

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

		return True


	# Tell the bootloader to save the binary blob to an address in internal
	# flash.
	#
	# This will pad the binary as needed, so don't worry about the binary being
	# a certain length.
	#
	# Returns False if there is an error.
	def flash_binary (self, binary, address):
		# Enter bootloader mode to get things started
		entered = self._enter_bootloader_mode();
		if not entered:
			return False

		# Make sure the binary is a multiple of 512 bytes by padding 0xFFs
		if len(binary) % 512 != 0:
			remaining = 512 - (len(binary) % 512)
			binary += bytes([0xFF]*remaining)

		# Time the programming operation
		then = time.time()

		flashed = self._flash_binary(address, binary)
		if not flashed:
			return False

		# Then erase the next page. This ensures that flash is clean at the
		# end of the installed apps and makes things nicer for future uses of
		# this script.
		self._erase_page(address + len(binary))

		# How long did that take
		now = time.time()
		print('Wrote {} bytes in {:0.3f} seconds'.format(len(binary), now-then))

		# All done, now run the application
		self._exit_bootloader_mode()

		return True

	# Run miniterm for receiving data from the board.
	def run_terminal (self):
		# Use trusty miniterm
		miniterm = serial.tools.miniterm.Miniterm(
			self.sp,
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
		entered = self._enter_bootloader_mode();
		if not entered:
			return False

		# Get all apps based on their header
		apps = self._extract_all_app_headers(address)

		if not quiet:
			# Print info about each app
			for i,app in enumerate(apps):
				tbfh = app['header']
				start_address = app['address']

				print('[App {}]'.format(i))
				print('  Name:                  {}'.format(app['name']))
				print('  Total Size in Flash:   {} bytes'.format(tbfh['total_size']))

				# Check if this app is OK with the MPU region requirements.
				if not self._app_is_aligned_correctly(start_address, tbfh['total_size']):
					print('  [WARNING] App is misaligned for the MPU')

				if verbose:
					print('  Flash Start Address:   {:#010x}'.format(start_address))
					print('  Flash End Address:     {:#010x}'.format(start_address+tbfh['total_size']-1))
					print('  Entry Address:         {:#010x}'.format(start_address+tbfh['entry_offset']))
					print('  Relocate Data Address: {:#010x} (length: {} bytes)'.format(start_address+tbfh['rel_data_offset'], tbfh['rel_data_size']))
					print('  Text Address:          {:#010x} (length: {} bytes)'.format(start_address+tbfh['text_offset'], tbfh['text_size']))
					print('  GOT Address:           {:#010x} (length: {} bytes)'.format(start_address+tbfh['got_offset'], tbfh['got_size']))
					print('  Data Address:          {:#010x} (length: {} bytes)'.format(start_address+tbfh['data_offset'], tbfh['data_size']))
					print('  Minimum Stack Size:    {} bytes'.format(tbfh['min_stack_len']))
					print('  Minimum Heap Size:     {} bytes'.format(tbfh['min_app_heap_len']))
					print('  Minimum Grant Size:    {} bytes'.format(tbfh['min_kernel_heap_len']))
					print('  Checksum:              {:#010x}'.format(tbfh['checksum']))
				print('')

			if len(apps) == 0:
				print('No found apps.')

		else:
			# In quiet mode just show the names.
			app_names = []
			for app in apps:
				app_names.append(app['name'])
			print(' '.join(app_names))

		# Done
		self._exit_bootloader_mode()
		return True


	# Inspect the given binary and find one that matches that's already programmed,
	# then replace it on the chip. address is the starting address to search
	# for apps.
	def replace_binary (self, binary, address):
		# Enter bootloader mode to get things started
		entered = self._enter_bootloader_mode();
		if not entered:
			return False

		# Get the application name and properties to match it with
		tbfh = self._parse_tbf_header(binary)

		# Need its name to match to existing apps
		name_binary = binary[tbfh['package_name_offset']:tbfh['package_name_offset']+tbfh['package_name_size']];
		new_name = name_binary.decode('utf-8')

		# Time the programming operation
		then = time.time()

		# Get a list of installed apps
		apps = self._extract_all_app_headers(address)

		# Check to see if this app is in there
		for app in apps:
			if app['name'] == new_name:
				if app['header']['total_size'] == tbfh['total_size']:
					# Great we can just overwrite it!
					print('Found matching binary at address {:#010x}'.format(app['address']))
					print('Replacing the binary...')
					flashed = self._flash_binary(app['address'], binary)
					if not flashed:
						return False

				else:
					# Need to expand this app's slot and possibly reshuffle apps
					print('Found matching binary, but the size has changed.')

					app['address'] = None
					app['binary'] = binary
					app['header'] = tbfh
					self._reshuffle_apps(address, apps)

				break

		else:
			print('No app named "{}" found on the board.'.format(new_name))
			print('Cannot replace.')
			return False

		# How long did it take?
		now = time.time()
		print('Wrote {} bytes in {:0.3f} seconds'.format(len(binary), now-then))

		# Done
		self._exit_bootloader_mode()
		return True


	# Add the app to the list of the currently flashed apps
	def add_binary (self, binary, address):
		# Enter bootloader mode to get things started
		entered = self._enter_bootloader_mode();
		if not entered:
			return False

		# Time the programming operation
		then = time.time()

		# Get a list of installed apps
		apps = self._extract_all_app_headers(address)
		# Add the new apps
		apps += self._extract_all_app_headers(binary)

		# Now that we have an array of all the apps that are supposed to be
		# on the board, write them in the correct order.
		self._reshuffle_apps(address, apps)

		# How long did it take?
		now = time.time()
		print('Wrote {} bytes in {:0.3f} seconds'.format(len(binary), now-then))

		# Done
		self._exit_bootloader_mode()
		return True


	# Add the app to the list of the currently flashed apps
	def remove_app (self, app_name, address):
		# Enter bootloader mode to get things started
		entered = self._enter_bootloader_mode();
		if not entered:
			return False

		# Time the programming operation
		then = time.time()

		# Get a list of installed apps
		apps = self._extract_all_app_headers(address)

		# Remove the on if its there
		app_index = -1
		for i,app in enumerate(apps):
			if app['name'] == app_name:
				app_index = i
				break

		if app_index >= 0:
			apps.pop(app_index)

			# Now take the remaining apps and make sure they are on the board
			# properly.
			self._reshuffle_apps(address, apps)

		else:
			print('Could not find the app on the board.')

		# How long did it take?
		now = time.time()
		print('Removed app in {:0.3f} seconds'.format(now-then))

		# Done
		self._exit_bootloader_mode()
		return True


	# Erase flash where apps go
	def erase_apps (self, address):
		# Enter bootloader mode to get things started
		entered = self._enter_bootloader_mode();
		if not entered:
			return False

		# Then erase the next page. This ensures that flash is clean at the
		# end of the installed apps and makes things nicer for future uses of
		# this script.
		self._erase_page(address)

		# Done
		self._exit_bootloader_mode()
		return True


	############################
	## Internal Helper Functions
	############################

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
	def _enter_bootloader_mode (self):
		self._toggle_bootloader_entry()

		# Make sure the bootloader is actually active and we can talk to it.
		alive = self._ping_bootloader_and_wait_for_response()
		if not alive:
			print('Error connecting to bootloader. No "pong" received.')
			print('Things that could be wrong:')
			print('  - The bootloader is not flashed on the chip')
			print('  - The DTR/RTS lines are not working')
			print('  - The serial port being used is incorrect')
			print('  - The bootloader API has changed')
			print('  - There is a bug in this script')
			return False
		return True

	# Reset the chip to exit bootloader mode
	def _exit_bootloader_mode (self):
		# Reset the SAM4L
		self.sp.dtr = 1
		# Make sure this line is de-asserted (high)
		self.sp.rts = 0
		# Let the reset take effect
		time.sleep(0.1)
		# Let the SAM4L startup
		self.sp.dtr = 0

	# Returns True if the device is there and responding, False otherwise
	def _ping_bootloader_and_wait_for_response (self):
		for i in range(30):
			# Try to ping the SAM4L to ensure it is in bootloader mode
			ping_pkt = bytes([ESCAPE_CHAR, COMMAND_PING])
			self.sp.write(ping_pkt)

			ret = self.sp.read(2)

			if len(ret) == 2 and ret[1] == RESPONSE_PONG:
				return True
		return False

	# Setup a command to send to the bootloader and handle the response.
	def _issue_command (self, command, message, sync, response_len, response_code):
		if sync:
			self.sp.write(SYNC_MESSAGE)
			time.sleep(0.0001)

		# Generate the message to send to the bootloader
		escaped_message = message.replace(bytes([ESCAPE_CHAR]), bytes([ESCAPE_CHAR, ESCAPE_CHAR]))
		pkt = escaped_message + bytes([ESCAPE_CHAR, command])
		self.sp.write(pkt)

		# Response has a two byte header, then response_len bytes
		ret = self.sp.read(2 + response_len)

		# Response is escaped, so we need to handle that
		while True:
			num_escaped = ret.count(bytes([ESCAPE_CHAR, ESCAPE_CHAR]))
			if num_escaped > 0:
				# De-escape, and then read in the missing characters.
				ret = ret.replace(bytes([ESCAPE_CHAR, ESCAPE_CHAR]), bytes([ESCAPE_CHAR]))
				ret += self.sp.read(num_escaped)
			else:
				break

		if len(ret) < 2:
			print('Error: No response after issuing command')
			return (False, bytes())

		if ret[0] != ESCAPE_CHAR:
			print('Error: Invalid response from bootloader (no escape character)')
			return (False, ret[0:2])
		if ret[1] != response_code:
			print('Error: Expected return type {:x}, got return {:x}'.format(response_code, ret[1]))
			return (False, ret[0:2])
		if len(ret) != 2 + response_len:
			print('Error: Incorrect number of bytes received')
			return (False, ret[0:2])

		return (True, ret[2:])

	# Write pages until a binary has been flashed. binary must have a length that
	# is a multiple of 512.
	def _flash_binary (self, address, binary):
		assert len(binary) % 512 == 0
		# Loop through the binary 512 bytes at a time until it has been flashed
		# to the chip.
		for i in range(len(binary) // 512):
			# Create the packet that we send to the bootloader. First four
			# bytes are the address of the page.
			pkt = struct.pack('<I', address + (i*512))

			# Next are the 512 bytes that go into the page.
			pkt += binary[i*512: (i+1)*512]

			# Write to bootloader
			success, ret = self._issue_command(COMMAND_WRITE_PAGE, pkt, True, 0, RESPONSE_OK)

			if not success:
				print('Error: Error when flashing page')
				if ret[1] == RESPONSE_BADADDR:
					print('Error: RESPONSE_BADADDR: Invalid address for page to write (address: 0x{:X}'.format(address + (i*512)))
				elif ret[1] == RESPONSE_INTERROR:
					print('Error: RESPONSE_INTERROR: Internal error when writing flash')
				elif ret[1] == RESPONSE_BADARGS:
					print('Error: RESPONSE_BADARGS: Invalid length for flash page write')
				else:
					print('Error: 0x{:X}'.format(ret[1]))
				return False

		# And check the CRC
		crc_passed = self._check_crc(address, binary)
		if not crc_passed:
			return False

		return True

	# Read a specific range of flash.
	def _read_range (self, address, length):
		if self.debug:
			print('DEBUG => Read Range, address: {:#010x}, length: {}'.format(address, length))

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
			success, flash = self._issue_command(COMMAND_READ_RANGE, message, True, this_length, RESPONSE_READ_RANGE)

			if not success:
				print('Error: Could not read flash')
			else:
				read += flash

			address += this_length

		return read

	# Read a specific range of flash.
	def _erase_page (self, address):
		message = struct.pack('<I', address)
		success, ret = self._issue_command(COMMAND_ERASE_PAGE, message, True, 0, RESPONSE_OK)

		if not success:
			if ret[1] == RESPONSE_BADADDR:
				print('Error: Page erase address was not on a page boundary.')
			elif ret[1] == RESPONSE_BADARGS:
				print('Error: Need to supply erase page with correct 4 byte address.')
			elif ret[1] == RESPONSE_INTERROR:
				print('Error: Internal error when erasing flash page.')
			else:
				print('Error: 0x{:X}'.format(ret[1]))
		return success

	# Get the bootloader to compute a CRC
	def _get_crc_internal_flash (self, address, length):
		message = struct.pack('<II', address, length)
		success, crc = self._issue_command(COMMAND_CRC_INTERNAL_FLASH, message, True, 4, RESPONSE_CRC_INTERNAL_FLASH)

		# There is a bug in a version of the bootloader where the CRC returns 6
		# bytes and not just 4. Need to read just in case to grab those extra
		# bytes.
		self.sp.read(2)

		if not success:
			if crc[1] == RESPONSE_BADADDR:
				print('Error: RESPONSE_BADADDR: Invalid address for CRC (address: 0x{:X})'.format(address))
			elif crc[1] == RESPONSE_BADARGS:
				print('Error: RESPONSE_BADARGS: Invalid length for CRC check')
			else:
				print('Error: 0x{:X}'.format(crc[1]))
			return bytes()

		return crc

	# Compares the CRC of the local binary to the one calculated by the bootloader
	def _check_crc (self, address, binary):
		# Check the CRC
		crc_data = self._get_crc_internal_flash(address, len(binary))

		# Now interpret the returned bytes as the CRC
		crc_bootloader = struct.unpack("<I", crc_data[0:4])[0]

		# Calculate the CRC locally
		crc_function = crcmod.mkCrcFun(0x104c11db7, initCrc=0, xorOut=0xFFFFFFFF)
		crc_loader = crc_function(binary, 0)

		if crc_bootloader != crc_loader:
			print('Error: CRC check failed. Expected: 0x{:04x}, Got: 0x{:04x}'.format(crc_loader, crc_bootloader))
			return False
		else:
			print('CRC check passed. Binaries successfully loaded.')
			return True

	# Given an array of apps, some of which are new and some of which exist,
	# sort them in flash so they are in descending size order.
	def _reshuffle_apps(self, address, apps):
		# We are given an array of apps. First we need to order them by size.
		apps.sort(key=lambda x: x['header']['total_size'], reverse=True)

		# Now iterate to see if the address has changed
		start_address = address
		for app in apps:
			# If the address already matches, then we are good.
			# On to the next app.
			if app['address'] != start_address:
				# If they don't, then we need to read the binary out of
				# flash and save it to be moved, as well as update the address.
				# However, we may have a new binary to use, so we don't need to
				# fetch it.
				if 'binary' not in app:
					app['binary'] = self._read_range(app['address'], app['header']['total_size'])

				# Either way save the new address.
				app['address'] = start_address

			start_address += app['header']['total_size']

		# Now flash all apps that have a binary field. The presence of the
		# binary indicates that they are new or moved.
		end = address
		for app in apps:
			if 'binary' in app:
				self._flash_binary(app['address'], app['binary'])
				end = app['address'] + len(app['binary'])

		# Then erase the next page. This ensures that flash is clean at the
		# end of the installed apps and makes things nicer for future uses of
		# this script.
		self._erase_page(end)

	# Iterate through the flash on the board or a local binary for
	# the header information about each app.
	def _extract_all_app_headers (self, address_or_binary):
		apps = []

		# Check which mode we are in
		if type(address_or_binary) == type(bytes()):
			onboard = False
			address = 0
		else:
			onboard = True
			address = address_or_binary

		# Jump through the linked list of apps
		while (True):
			header_length = 76 # Version 1
			if onboard:
				flash = self._read_range(address, header_length)
			else:
				flash = address_or_binary[address:address+header_length]
				if len(flash) < header_length:
					break

			# Get all the fields from the header
			tbfh = self._parse_tbf_header(flash)

			if tbfh['valid']:
				# Get the name out of the app
				if onboard:
					name = self._get_app_name(address+tbfh['package_name_offset'], tbfh['package_name_size'])
					app_address = address
				else:
					start = address+tbfh['package_name_offset']
					name = address_or_binary[start:start+tbfh['package_name_size']].decode('utf-8')
					app_address = None

				apps.append({
					'address': app_address,
					'header': tbfh,
					'name': name,
				})

				# If this is a local binary, also add the binary
				if not onboard:
					apps[-1]['binary'] = address_or_binary[address:address+tbfh['total_size']]

				address += tbfh['total_size']

			else:
				break

		return apps

	# Retrieve bytes from the board and interpret them as a string
	def _get_app_name (self, address, length):
		if length == 0:
			return ''

		name_memory = self._read_range(address, length)
		return name_memory.decode('utf-8')

	# Parses a buffer into the Tock Binary Format header fields
	def _parse_tbf_header (self, buffer):
		out = {'valid': False}

		# Read first word to get the TBF version
		out['version'] = struct.unpack('<I', buffer[0:4])[0]

		if out['version'] == 1:
			tbf_header = struct.unpack('<IIIIIIIIIIIIIIIIII', buffer[4:76])
			out['total_size'] = tbf_header[0]
			out['entry_offset'] = tbf_header[1]
			out['rel_data_offset'] = tbf_header[2]
			out['rel_data_size'] = tbf_header[3]
			out['text_offset'] = tbf_header[4]
			out['text_size'] = tbf_header[5]
			out['got_offset'] = tbf_header[6]
			out['got_size'] = tbf_header[7]
			out['data_offset'] = tbf_header[8]
			out['data_size'] = tbf_header[9]
			out['bss_mem_offset'] = tbf_header[10]
			out['bss_mem_size'] = tbf_header[11]
			out['min_stack_len'] = tbf_header[12]
			out['min_app_heap_len'] = tbf_header[13]
			out['min_kernel_heap_len'] = tbf_header[14]
			out['package_name_offset'] = tbf_header[15]
			out['package_name_size'] = tbf_header[16]
			out['checksum'] = tbf_header[17]

			xor = out['version'] ^ out['total_size'] ^ out['entry_offset'] \
			      ^ out['rel_data_offset'] ^ out['rel_data_size'] ^ out['text_offset'] \
			      ^ out['text_size'] ^ out['got_offset'] ^ out['got_size'] \
			      ^ out['data_offset'] ^ out['data_size'] ^ out['bss_mem_offset'] \
			      ^ out['bss_mem_size'] ^ out['min_stack_len'] \
			      ^ out['min_app_heap_len'] ^ out['min_kernel_heap_len'] \
			      ^ out['package_name_offset'] ^ out['package_name_size']

			if xor == out['checksum']:
				out['valid'] = True

		return out

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

def collect_binaries (binaries, single=False):
	binary = bytes()

	# Check if array of binaries is empty. If so, find them based on where this
	# tool is being run.
	if len(binaries) == 0 or binaries[0] == '':
		print('No binaries passed to tockloader. Searching for binaries in subdirectories.')

		# First check to see if things could be built that haven't been
		if os.path.isfile('./Makefile'):
			p = subprocess.Popen(['make', '-n'], stdout=subprocess.PIPE)
			out, err = p.communicate()
			# Check for the name of the compiler to see if there is work
			# to be done
			if 'arm-none-eabi-gcc' in out.decode('utf-8'):
				print('Warning! There are uncompiled changes!')
				print('You may want to run `make` before loading the application.')

		# Search for ".bin" files
		binaries = glob.glob('./**/*.bin', recursive=True)
		if single:
			binaries = binaries[0:1]
		if len(binaries) == 0:
			print('No binaries found.')
			sys.exit(1)

		print('Using: {}'.format(binaries))
		print('Waiting one second before continuing...')
		time.sleep(1)

	# Concatenate the binaries.
	for binary_filename in binaries:
		try:
			with open(binary_filename, 'rb') as f:
				binary += f.read()
		except Exception as e:
			print('Error opening and reading "{}"'.format(binary_filename))
			sys.exit(1)

		if single:
			break

	return binary


def command_flash (args):
	check_and_run_make(args)

	# Load in all binaries
	binary = collect_binaries(args.binary)

	# Flash the binary to the chip
	tock_loader = TockLoader(args)
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)

	print('Flashing binar(y|ies) to board...')
	success = tock_loader.flash_binary(binary, args.address)
	if not success:
		print('Could not flash the binaries.')
		sys.exit(1)


def command_listen (args):
	tock_loader = TockLoader(args)
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)
	tock_loader.run_terminal()


def command_list (args):
	tock_loader = TockLoader(args)
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)
	tock_loader.list_apps(args.address, args.verbose, args.quiet)


def command_replace (args):
	check_and_run_make(args)

	# Load in all binaries
	binary = collect_binaries(args.binary, True)

	# Flash the binary to the chip
	tock_loader = TockLoader(args)
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)

	print('Replacing binary on the board...')
	success = tock_loader.replace_binary(binary, args.address)
	if not success:
		print('Could not replace the binary.')
		sys.exit(1)


def command_add (args):
	check_and_run_make(args)

	# Load in all binaries
	binary = collect_binaries(args.binary)

	# Flash the binary to the chip
	tock_loader = TockLoader(args)
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)

	print('Adding binar(y|ies) to board...')
	success = tock_loader.add_binary(binary, args.address)
	if not success:
		print('Could not add the binaries.')
		sys.exit(1)


def command_remove (args):
	tock_loader = TockLoader(args)
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)

	print('Removing app "{}" from board...'.format(args.name[0]))
	success = tock_loader.remove_app(args.name[0], args.address)
	if not success:
		print('Could not remove the app.')
		sys.exit(1)


def command_erase_apps (args):
	tock_loader = TockLoader(args)
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)

	print('Removing apps...')
	success = tock_loader.erase_apps(args.address)
	if not success:
		print('Could not erase the apps.')
		sys.exit(1)

################################################################################
## Setup and parse command line arguments
################################################################################

def main ():
	# Create a common parent parser for arguments shared by all subparsers
	parent = argparse.ArgumentParser(add_help=False)

	# All commands need a serial port to talk to the board
	parent.add_argument('--port', '-p',
		help='The serial port to use')

	parent.add_argument('--make',
		action='store_true',
		help='Run `make` before loading an application')

	parent.add_argument('--debug',
		action='store_true',
		help='Print additional debugging information')

	parent.add_argument('--version',
		action='version',
		version=__version__,
		help='Tockloader version')


	# The top-level parser object
	parser = argparse.ArgumentParser(parents=[parent])


	# Support multiple commands for this tool
	subparser = parser.add_subparsers(
		title='Commands')

	flash = subparser.add_parser('flash',
		parents=[parent],
		help='Flash binaries to the chip')
	flash.set_defaults(func=command_flash)
	flash.add_argument('binary',
		help='The binary file or files to flash to the chip',
		nargs='*')
	flash.add_argument('--address', '-a',
		help='Address to flash the binary at',
		type=lambda x: int(x, 0),
		default=0x30000)

	listen = subparser.add_parser('listen',
		parents=[parent],
		help='Open a terminal to receive UART data')
	listen.set_defaults(func=command_listen)

	listcmd = subparser.add_parser('list',
		parents=[parent],
		help='List the apps installed on the board')
	listcmd.set_defaults(func=command_list)
	listcmd.add_argument('--address', '-a',
		help='Address to flash the binary at',
		type=lambda x: int(x, 0),
		default=0x30000)
	listcmd.add_argument('--verbose', '-v',
		help='Print more information',
		action='store_true')
	listcmd.add_argument('--quiet', '-q',
		help='Print just a list of application names',
		action='store_true')

	replace = subparser.add_parser('replace',
		parents=[parent],
		help='Replace an already flashed app with this binary')
	replace.set_defaults(func=command_replace)
	replace.add_argument('binary',
		help='The binary file to use as the replacement',
		nargs='*')
	replace.add_argument('--address', '-a',
		help='Address where apps are placed',
		type=lambda x: int(x, 0),
		default=0x30000)

	add = subparser.add_parser('add',
		parents=[parent],
		help='Add an app to the already flashed apps')
	add.set_defaults(func=command_add)
	add.add_argument('binary',
		help='The binary file to add to the end',
		nargs='*')
	add.add_argument('--address', '-a',
		help='Address where apps are placed',
		type=lambda x: int(x, 0),
		default=0x30000)

	remove = subparser.add_parser('remove',
		parents=[parent],
		help='Remove an already flashed app')
	remove.set_defaults(func=command_remove)
	remove.add_argument('name',
		help='The name of the app to remove',
		nargs=1)
	remove.add_argument('--address', '-a',
		help='Address where apps are placed',
		type=lambda x: int(x, 0),
		default=0x30000)

	eraseapps = subparser.add_parser('erase-apps',
		parents=[parent],
		help='Delete apps from the board')
	eraseapps.set_defaults(func=command_erase_apps)
	eraseapps.add_argument('--address', '-a',
		help='Address where apps are placed',
		type=lambda x: int(x, 0),
		default=0x30000)

	args = parser.parse_args()
	if hasattr(args, 'func'):
		args.func(args)
	else:
		print('Missing Command. Run with --help to see supported commands.')
		sys.exit(1)


if __name__ == '__main__':
	main()
