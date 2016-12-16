#!/usr/bin/env python3

import argparse
import struct
import sys
import time

import crcmod
import serial
import serial.tools.list_ports
import serial.tools.miniterm


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
COMMAND_RRANGE             = 0x11
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
RESPONSE_RRANGE             = 0x20
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
	# Open the serial port to the chip/bootloader
	def open (self, port):

		# Check to see if the serial port was specified or we should find
		# one to use
		if port == None:
			print('No serial port specified. Discovering attached serial devices...')
			ports = list(serial.tools.list_ports.comports())
			if len(ports) == 0:
				print('No serial ports found. Is the board connected?')
				return False
			else:
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

	# Reset the chip and assert the bootloader select pin to enter bootloader
	# mode.
	def enter_bootloader_mode (self):
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

	# Reset the chip to exit bootloader mode
	def exit_bootloader_mode (self):
		# Reset the SAM4L
		self.sp.dtr = 1
		# Make sure this line is de-asserted (high)
		self.sp.rts = 0
		# Let the reset take effect
		time.sleep(0.1)
		# Let the SAM4L startup
		self.sp.dtr = 0

	# Returns True if the device is there and responding, False otherwise
	def ping_bootloader_and_wait_for_response (self):
		for i in range(30):
			# Try to ping the SAM4L to ensure it is in bootloader mode
			ping_pkt = bytes([0xFC, 0x01])
			self.sp.write(ping_pkt)

			ret = self.sp.read(2)

			if len(ret) == 2 and ret[1] == RESPONSE_PONG:
				return True
		return False


	# Tell the bootloader to save the binary blob to an address in internal
	# flash.
	#
	# This will pad the binary as needed, so don't worry about the binary being
	# a certain length.
	#
	# Returns False if there is an error.
	def flash_binary (self, binary, address):
		# Enter bootloader mode to get things started
		self.enter_bootloader_mode();

		# Make sure the bootloader is actually active and we can talk to it.
		alive = self.ping_bootloader_and_wait_for_response()
		if not alive:
			print('Error connecting to bootloader. No "pong" received.')
			print('Things that could be wrong:')
			print('  - The bootloader is not flashed on the chip')
			print('  - The DTR/RTS lines are not working')
			print('  - The serial port being used is incorrect')
			print('  - The bootloader API has changed')
			print('  - There is a bug in this script')
			return False

		# Make sure the binary is a multiple of 512 bytes by padding 0xFFs
		if len(binary) % 512 != 0:
			remaining = 512 - (len(binary) % 512)
			binary += bytes([0xFF]*remaining)

		# Time the programming operation
		then = time.time()

		# Loop through the binary 512 bytes at a time until it has been flashed
		# to the chip.
		for i in range(len(binary) // 512):
			# First we write the sync string to make sure the bootloader is ready
			# to receive this page of the binary.
			self.sp.write(SYNC_MESSAGE)
			time.sleep(0.0001)

			# Now create the packet that we send to the bootloader. First four
			# bytes are the address of the page.
			pkt = struct.pack('<I', address + (i*512))

			# Next are the 512 bytes that go into the page.
			pkt += binary[i*512: (i+1)*512]

			# Escape any bytes that need to be escaped
			pkt = pkt.replace(bytes([ESCAPE_CHAR]), bytes([ESCAPE_CHAR, ESCAPE_CHAR]))

			# Add the ending escape that ends the packet and the command byte
			pkt += bytes([ESCAPE_CHAR, COMMAND_WRITE_PAGE])

			# Send this page to the bootloader
			self.sp.write(pkt)

			# We expect a two byte response
			ret = self.sp.read(2)

			# Check that we get the RESPONSE_OK return code
			if ret[0] != ESCAPE_CHAR:
				print('Error: Invalid response from bootloader when flashing page')
				return False

			if ret[1] != RESPONSE_OK:
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

		# How long did that take
		now = time.time()
		print('Wrote {} bytes in {:0.3f} seconds'.format(len(binary), now-then))

		# Check the CRC
		# Start by doing a sync
		self.sp.write(SYNC_MESSAGE)
		time.sleep(0.0001)

		# Generate the message to send to the bootloader
		pkt = struct.pack('<II', address, len(binary)) + bytes([ESCAPE_CHAR, COMMAND_CRC_INTERNAL_FLASH])
		self.sp.write(pkt)

		# Response has a two byte header, then four byte CRC
		ret = self.sp.read(6)
		if len(ret) < 2:
			print('Error: No response when requesting the CRC')
			return False

		# Check that we got a valid return code
		if ret[0] != ESCAPE_CHAR:
			print('Error: Invalid response from bootloader when asking for CRC')
			return False

		if ret[1] != RESPONSE_CRC_INTERNAL_FLASH:
			print('Error: Error when flashing page')
			if ret[1] == RESPONSE_BADADDR:
				print('Error: RESPONSE_BADADDR: Invalid address for CRC (address: 0x{:X})'.format(address))
			elif ret[1] == RESPONSE_BADARGS:
				print('Error: RESPONSE_BADARGS: Invalid length for CRC check')
			else:
				print('Error: 0x{:X}'.format(ret[1]))
			return False

		# Now interpret the last four bytes as the CRC
		crc_bootloader = struct.unpack("<I", ret[2:6])[0]

		# Calculate the CRC locally
		crc_function = crcmod.mkCrcFun(0x104c11db7, initCrc=0, xorOut=0xFFFFFFFF)
		crc_loader = crc_function(binary, 0)

		if crc_bootloader != crc_loader:
			print('Error: CRC check failed. Expected: 0x{:04x}, Got: 0x{:04x}')
			return False
		else:
			print('CRC check passed. Binaries successfully loaded.')

		# All done, now run the application
		self.exit_bootloader_mode()

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


################################################################################
## Command Functions
################################################################################

def command_flash (args):
	# Load in all binaries
	binary = bytes([])
	for binary_filename in args.binary:
		try:
			with open(binary_filename, 'rb') as f:
				binary += f.read()
		except Exception as e:
			print('Error opening and reading "{}"'.format(binary_filename))
			sys.exit(1)

	# Temporary: append 0x00s to signal the end of valid applications
	binary += bytes([0]*8)

	# Flash the binary to the chip
	tock_loader = TockLoader()
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)
	success = tock_loader.flash_binary(binary, args.address)
	if not success:
		print('Could not flash the binaries.')
		sys.exit(1)


def command_listen (args):
	tock_loader = TockLoader()
	success = tock_loader.open(port=args.port)
	if not success:
		print('Could not open the serial port. Make sure the board is plugged in.')
		sys.exit(1)
	tock_loader.run_terminal()


################################################################################
## Setup and parse command line arguments
################################################################################

def main ():
	# Setup command line arguments
	parser = argparse.ArgumentParser()

	# All commands need a serial port to talk to the board
	parser.add_argument('--port', '-p',
		help='The serial port to use')

	# Support multiple commands for this tool
	subparser = parser.add_subparsers(
		title='Commands')

	flash = subparser.add_parser('flash',
		help='Flash binaries to the chip')
	flash.set_defaults(func=command_flash)
	flash.add_argument('binary',
		help='The binary file or files to flash to the chip',
		nargs='+')
	flash.add_argument('--address', '-a',
		help='Address to flash the binary at',
		type=lambda x: int(x, 0),
		default=0x30000)

	listen = subparser.add_parser('listen',
		help='Open a terminal to receive UART data')
	listen.set_defaults(func=command_listen)

	args = parser.parse_args()
	if hasattr(args, 'func'):
		args.func(args)
	else:
		print('Missing Command. Run with --help to see supported commands.')
		sys.exit(1)


if __name__ == "__main__":
    main()
