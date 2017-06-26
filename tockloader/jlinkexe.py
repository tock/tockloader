'''
Interface for boards using Seggger's JLinkExe program.

All communication with the board is done using JLinkExe commands and scripts.

Different MCUs require different command line arguments so that the JLinkExe
tool knows which JTAG interface it is talking to. Since we don't want to burden
the user with specifying the board each time, we default to using a generic
cortex-m0 target, and use that to read the bootloader attributes to get the
correct version. Once we know more about the board we are talking to we use the
correct command line argument for future communication.
'''

import subprocess
import tempfile

from .board_interface import BoardInterface
from .exceptions import TockLoaderException

class JLinkExe(BoardInterface):
	def _run_jtag_commands (self, commands, binary, write=True):
		'''
		- `commands`: List of JLinkExe commands. Use {binary} for where the name
		  of the binary file should be substituted.
		- `binary`: A bytes() object that will be used to write to the board.
		- `write`: Set to true if the command writes binaries to the board. Set
		  to false if the command will read bits from the board.
		'''
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

	def flash_binary (self, address, binary):
		'''
		Write using JTAG
		'''
		commands = [
			'r',
			'loadbin {{binary}}, {address:#x}'.format(address=address),
			'verifybin {{binary}}, {address:#x}'.format(address=address),
			'r\ng\nq'
		]

		self._run_jtag_commands(commands, binary)

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

	def erase_page (self, address):
		binary = bytes([0xFF]*512)
		commands = [
			'r',
			'loadbin {{binary}}, {address:#x}'.format(address=address),
			'verifybin {{binary}}, {address:#x}'.format(address=address),
			'r\ng\nq'
		]

		self._run_jtag_commands(commands, binary)

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
