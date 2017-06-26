'''
Interface with a board over serial that is using the
[Tock Bootloader](https://github.com/helena-project/tock-bootloader).
'''

import atexit
import crcmod
import fcntl
import hashlib
import json
import os
import socket
import struct
import sys
import time
import threading

import serial
import serial.tools.list_ports
import serial.tools.miniterm

from . import helpers
from .board_interface import BoardInterface
from .exceptions import TockLoaderException

class BootloaderSerial(BoardInterface):
	'''
	Implementation of `BoardInterface` for the Tock Bootloader over serial.
	'''

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

	def open_link_to_board (self):
		'''
		Open the serial port to the chip/bootloader.

		Also sets up a local port for determining when two Tockloader instances
		are running simultaneously.
		'''
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
			index = helpers.menu(ports, return_type='index')
		elif must_match:
			# pyserial's list_ports can't find all valid serial ports, for
			# example if someone symlinks to a port or creates a software
			# serial port with socat, if this path exists, let's trust the
			# caller for now
			if os.path.exists(device_name):
				index = 0
				ports = [serial.tools.list_ports_common.ListPortInfo(device_name)]
			else:
				# We want to find a very specific board. If this does not
				# exist, we want to fail.
				raise TockLoaderException('Could not find a board matching "{}"'.format(device_name))
		else:
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
				index = helpers.menu(ports, return_type='index')
		port = ports[index][0]
		helpers.set_terminal_title_from_port_info(ports[index])

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

		# Only one process at a time can talk to a serial port (reliably)
		# Before connecting, check whether there is another tockloader process
		# running, if it's a listen, pause listening, otherwise bail out
		self.comm_path = '/tmp/tockloader.' + self._get_serial_port_hash()
		if os.path.exists(self.comm_path):
			self.client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			try:
				self.client_sock.connect(self.comm_path)
			except ConnectionRefusedError:
				print('  [Warning]: Found stale tockloader server, removing')
				print('             This may occur if a previous tockloader instance crashed')
				os.unlink(self.comm_path)
				self.client_sock = None
		else:
			self.client_sock = None

		if self.client_sock:
			self.client_sock.sendall('Version 1\n'.encode('utf-8'))
			self.client_sock.sendall('Stop Listening\n'.encode('utf-8'))
			r = ''
			while '\n' not in r:
				r += self.client_sock.recv(100).decode('utf-8')
			if r == 'Busy\n':
				raise TockLoaderException('Another tockloader process is active on this serial port')
			elif r == 'Killing\n':
				def restart_listener(path):
					sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
					try:
						sock.connect(path)
						sock.sendall('Version 1\n'.encode('utf-8'))
						sock.sendall('Start Listening\n'.encode('utf-8'))
						sock.close()
						print('     [Info]: Resumed other tockloader listen session')
					except:
						print('  [Warning]: Error restarting other tockloader listen process')
						print('             You may need to manually begin listening again')
				atexit.register(restart_listener, self.comm_path)
				self.client_sock.close()
				while os.path.exists(self.comm_path):
					time.sleep(.1)
				print('     [Info]: Paused an active tockloader listen in another session')
			else:
				raise TockLoaderException('Internal error: Got >{}< from IPC'.format(r))
		else:
			self.server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			flags = fcntl.fcntl(self.server_sock, fcntl.F_GETFD)
			fcntl.fcntl(self.server_sock, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
			self.server_sock.bind(self.comm_path)
			self.server_sock.listen(1)
			self.server_event = threading.Event()
			self.server_thread = threading.Thread(
					target=self._server_thread,
					daemon=True,
					)
			self.server_thread.start()
			def server_cleanup():
				if self.server_sock is not None:
					self.server_sock.close()
					os.unlink(self.comm_path)
			atexit.register(server_cleanup)

			if hasattr(self.args, 'wait_to_listen') and self.args.wait_to_listen:
				print('     [Info]: Waiting for other tockloader to finish before listening')
				self.server_event.wait()
				print('     [Info]: Resuming listening...')

		self.sp.open()

	# While tockloader has a serial connection open, it leaves a unix socket
	# open for other tockloader processes. For most of the time, this will
	# simply report 'Busy\n' and new tockloader processes will back off and not
	# steal the serial port. If miniterm is active, however, this process will
	# send back 'Killing\n', terminate this process (due to miniterm
	# architecture, there's no good way to programmatically kill & restart
	# miniterm threads), and restart this process with --wait-to-listen
	def _server_thread (self):
		while True:
			connection, client_address = self.server_sock.accept()
			r = ''
			while '\n' not in r:
				r += connection.recv(100).decode('utf-8')
			if r[:len('Version 1\n')] != 'Version 1\n':
				print('WARN: Got unexpected connection: >{}< ; dropping'.format(r))
				connection.close()
				continue

			r = r[len('Version 1\n'):]
			while '\n' not in r:
				r += connection.recv(100).decode('utf-8')

			if r == 'Start Listening\n':
				self.server_event.set()
				continue
			if r != 'Stop Listening\n':
				print('WARN: Got unexpected command: >{}< ; dropping'.format(r))
				connection.close()
				continue

			if not hasattr(self, 'miniterm'):
				# Running something other than listen, reject other tockloader
				connection.sendall('Busy\n'.encode('utf-8'))
				connection.close()
				continue

			# Since there's no great way to kill & restart miniterm, we just
			# redo the whole process, only tacking on a --wait-to-listen
			print('     [Info]: Received request to pause from another tockloader process. Disconnecting...')
			# And let them know we've progressed
			connection.sendall('Killing\n'.encode('utf-8'))
			connection.close()
			self.server_sock.close()
			os.unlink(self.comm_path)
			# Need to run miniterm's atexit handler
			self.miniterm.console.cleanup()

			args = list(sys.argv)
			args.append('--wait-to-listen')
			os.execvp(args[0], args)

	def _get_serial_port_hash (self):
		'''
		Get an identifier that will be consistent for this serial port on this
		machine that is also guaranteed to not have any special characters (like
		slashes) that would interfere with using as a file name.
		'''
		return hashlib.sha1(self.sp.port.encode('utf-8')).hexdigest()

	def _toggle_bootloader_entry (self):
		'''
		Reset the chip and assert the bootloader select pin to enter bootloader
		mode.
		'''
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

	def enter_bootloader_mode (self):
		'''
		Reset the chip and assert the bootloader select pin to enter bootloader
		mode. Handle retries if necessary.
		'''
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

	def exit_bootloader_mode (self):
		'''
		Reset the chip to exit bootloader mode.
		'''
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

	def _ping_bootloader_and_wait_for_response (self):
		'''
		Throws an exception if the device does not respond with a PONG.
		'''
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

	def _issue_command (self, command, message, sync, response_len, response_code, show_errors=True):
		'''
		Setup a command to send to the bootloader and handle the response.
		'''
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

	def _change_baud_rate (self, baud_rate):
		'''
		If the bootloader on the board supports it and if it succeeds, try to
		increase the baud rate to make everything faster.
		'''
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

	def flash_binary (self, address, binary, pad=True):
		'''
		Write pages until a binary has been flashed. binary must have a length
		that is a multiple of 512.
		'''
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

	def _get_crc_internal_flash (self, address, length):
		'''
		Get the bootloader to compute a CRC.
		'''
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

	def _check_crc (self, address, binary):
		'''
		Compares the CRC of the local binary to the one calculated by the
		bootloader.
		'''
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

	def bootloader_is_present (self):
		'''
		For this communication protocol we can safely say the bootloader is
		present.
		'''
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


	def run_terminal(self):
		'''
		Run miniterm for receiving data from the board.
		'''
		print('Listening for serial output.')

		# Use trusty miniterm
		self.miniterm = serial.tools.miniterm.Miniterm(
			self.sp,
			echo=False,
			eol='crlf',
			filters=['default'])

		# Ctrl+c to exit.
		self.miniterm.exit_character = serial.tools.miniterm.unichr(0x03)
		self.miniterm.set_rx_encoding('UTF-8')
		self.miniterm.set_tx_encoding('UTF-8')

		self.miniterm.start()
		try:
			self.miniterm.join(True)
		except KeyboardInterrupt:
			pass

		self.miniterm.stop()
		self.miniterm.join()
		self.miniterm.close()
