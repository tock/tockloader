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
