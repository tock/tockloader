'''
Interface for boards using OpenOCD.
'''

import shlex
import subprocess
import tempfile

from .board_interface import BoardInterface
from .exceptions import TockLoaderException

class OpenOCD(BoardInterface):
	def _run_openocd_commands (self, commands, binary, write=True):
		'''
		- `commands`: String of openocd commands. Use {binary} for where the name
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

			# Update the command with the name of the binary file
			commands = commands.format(binary=temp_bin.name)

		# Create the actual openocd command and run it.
		openocd_command = 'openocd -c "source [find board/{}]; {}"'.format(self.openocd_board, commands)

		if self.args.debug:
			print('Running "{}".'.format(openocd_command))

		def print_output (subp):
			if subp.stdout:
				print(subp.stdout.decode('utf-8'))
			if subp.stderr:
				print(subp.stderr.decode('utf-8'))

		p = subprocess.run(shlex.split(openocd_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		if p.returncode != 0:
			print('ERROR: openocd returned with error code ' + str(p.returncode))
			print_output(p)
			raise TockLoaderException('openocd error')
		elif self.args.debug:
			print_output(p)

		# check that there was a JTAG programmer and that it found a device
		stdout = p.stdout.decode('utf-8')
		if 'Error: No J-Link device found.' in stdout:
			raise TockLoaderException('ERROR: Cannot find hardware. Is USB attached?')

		if write == False:
			# Wanted to read binary, so lets pull that
			temp_bin.seek(0, 0)
			return temp_bin.read()

	def flash_binary (self, address, binary):
		'''
		Write using openocd `program` command.
		'''
		command = 'init; reset init; halt; program {{binary}} verify {address:#x}; reset; exit'.format(address=address)
		self._run_openocd_commands(command, binary)

	def read_range (self, address, length):
		command = 'init; reset init; halt; dump_image {{binary}} {address:#x} {length}; reset; exit'.format(address=address, length=length)

		# Always return a valid byte array (like the serial version does)
		read = bytes()
		result = self._run_openocd_commands(command, None, write=False)
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
		command = 'init; reset init; halt; flash fillb {address:#x} 0xff 512; reset; exit'.format(address=address)
		self._run_openocd_commands(command, None)

	def determine_current_board (self):
		if self.board and self.arch and self.openocd_board and self.page_size>0:
			# These are already set! Yay we are done.
			return

		# If the user specified a board, use that configuration
		if self.board and self.board in self.KNOWN_BOARDS:
			print('Using known arch and jtag-device for known board {}'.format(self.board))
			board = self.KNOWN_BOARDS[self.board]
			self.arch = board['arch']
			self.openocd_board = board['openocd']
			self.page_size = board['page_size']
			return

		# The primary (only?) way to do this is to look at attributes
		attributes = self.get_all_attributes()
		for attribute in attributes:
			if attribute and attribute['key'] == 'board' and self.board == None:
				self.board = attribute['value']
			if attribute and attribute['key'] == 'arch' and self.arch == None:
				self.arch = attribute['value']
			if attribute and attribute['key'] == 'openocd':
				self.openocd_board = attribute['value']
			if attribute and attribute['key'] == 'pagesize' and self.page_size == 0:
				self.page_size = attribute['value']

		# Check that we learned what we needed to learn.
		if self.board == None or self.arch == None or self.openocd_board == 'cortex-m0' or self.page_size == 0:
			raise TockLoaderException('Could not determine the current board or arch or openocd board name')
