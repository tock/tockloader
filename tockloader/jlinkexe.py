'''
Interface for boards using Segger's JLinkExe program.

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
import time

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

			jlink_command = 'JLinkExe -device {} -if {} -speed {} -AutoConnect 1 -jtagconf -1,-1 {}'.format(
                                self.jlink_device, self.jlink_if, self.jlink_speed, jlink_file.name)

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
			'h\nr',
			'loadbin {{binary}}, {address:#x}'.format(address=address),
			'verifybin {{binary}}, {address:#x}'.format(address=address),
			'r\nh\ng\nq'
		]

		self._run_jtag_commands(commands, binary)

	def read_range (self, address, length):

		commands = []
		if self.jlink_device == 'cortex-m0':
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
                                'h\nr',
				'savebin {{binary}}, {address:#x} {length}'.format(address=address, length=length),
				'r\nh\ng\nq'
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
		if self.args.debug:
			print('Erasing page at address {:#0x}'.format(address))

		# For some reason on the nRF52840DK erasing an entire page causes
		# previous flash to be reset to 0xFF. This doesn't seem to happen
		# if the binary we write is 512 bytes, so let's just do that. Since
		# we only use erase_page to end the linked-list of apps this will be
		# ok. If we ever actually need to reset an entire page exactly we will
		# have to revisit this.
		binary = bytes([0xFF]*512)
		commands = [
			'h\nr',
			'loadbin {{binary}}, {address:#x}'.format(address=address),
			'verifybin {{binary}}, {address:#x}'.format(address=address),
			'r\nh\ng\nq'
		]

		self._run_jtag_commands(commands, binary)

	def determine_current_board (self):
		if self.board and self.arch and self.jlink_device and self.page_size>0:
			# These are already set! Yay we are done.
			return

		# If the user specified a board, use that configuration
		if self.board and self.board in self.KNOWN_BOARDS:
			print('Using known arch and jtag-device for known board {}'.format(self.board))
			board = self.KNOWN_BOARDS[self.board]
			self.arch = board['arch']
			self.jlink_device = board['jlink_device']
			if 'jlink_speed' in board:
				self.jlink_speed = board['jlink_speed']
			if 'jlink_if' in board:
				self.jlink_if = board['jlink_if']
			self.page_size = board['page_size']
			return

		# The primary (only?) way to do this is to look at attributes
		attributes = self.get_all_attributes()
		for attribute in attributes:
			if attribute and attribute['key'] == 'board' and self.board == None:
				self.board = attribute['value']
			if attribute and attribute['key'] == 'arch' and self.arch == None:
				self.arch = attribute['value']
			if attribute and attribute['key'] == 'jldevice':
				self.jlink_device = attribute['value']
			if attribute and attribute['key'] == 'pagesize' and self.page_size == 0:
				self.page_size = attribute['value']

		# Check that we learned what we needed to learn.
		if self.board == None or self.arch == None or self.jlink_device == 'cortex-m0' or self.page_size == 0:
			raise TockLoaderException('Could not determine the current board or arch or jtag device name')

	def run_terminal (self):
		'''
		Use JLinkRTTClient to listen for RTT messages.
		'''
		# Do a mini `determine_current_board` here so we know what to pass to
		# JLinkExe. We don't bother trying to find this all automatically, for
		# now it will just have to be passed in.
		if self.jlink_device == None and self.board and self.board in self.KNOWN_BOARDS:
			board = self.KNOWN_BOARDS[self.board]
			self.jlink_device = board['jlink_device']
			if 'jlink_speed' in board:
				self.jlink_speed = board['jlink_speed']
			if 'jlink_if' in board:
				self.jlink_if = board['jlink_if']

		if self.jlink_device == None:
			print('Unknown jlink_device. Use the --board or --jlink-device options.')
			return

		print('Starting JLinkExe JTAG connection.')
		jtag_p = subprocess.Popen('JLinkExe -device {} -if {} -speed {} -autoconnect 1 -jtagconf -1,-1'.format(
                    self.jlink_device, self.jlink_if, self.jlink_speed).split(),
			stdout=subprocess.PIPE, stderr=subprocess.PIPE)

		# Delay to give the JLinkExe JTAG connection time to start before running
		# the RTT listener.
		time.sleep(1)

		print('Starting JLinkRTTClient to listen for messages.')
		p = subprocess.Popen('JLinkRTTClient', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		for stdout_line in iter(p.stdout.readline, ""):
			l = stdout_line.decode("utf-8")
			if not l.startswith('###RTT Client: *'):
				print(l, end='')
