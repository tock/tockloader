
class BoardInterface:
	'''
	Base class for interacting with hardware boards. All of the class functions
	should be overridden to support a new method of interacting with a board.
	'''

	def __init__ (self, args):
		self.args = args

		# These settings need to come from somewhere. Once place is the
		# command line. Another is the attributes section on the board.
		# There could be more in the future.
		# Also, not all are required depending on the connection method used.
		self.board = getattr(self.args, 'board', None)
		self.arch = getattr(self.args, 'arch', None)
		self.jtag_device = getattr(self.args, 'jtag_device', None)

	def open_link_to_board (self):
		'''
		Open a connection to the board.
		'''
		return

	def enter_bootloader_mode (self):
		'''
		Get to a mode where we can read & write flash.
		'''
		return

	def exit_bootloader_mode (self):
		'''
		Get out of bootloader mode and go back to running main code.
		'''
		return

	def flash_binary (self, address, binary):
		'''
		Write a binary to the address given.
		'''
		return

	def read_range (self, address, length):
		'''
		Read a specific range of flash.
		'''
		if self.args.debug:
			print('DEBUG => Read Range, address: {:#010x}, length: {}'.format(address, length))

	def erase_page (self, address):
		'''
		Erase a specific page of internal flash.
		'''
		return

	def get_attribute (self, index):
		'''
		Get a single attribute.
		'''
		return

	def get_all_attributes (self):
		'''
		Get all attributes on a board.
		'''
		return

	def set_attribute (self, index, raw):
		'''
		Set a single attribute.
		'''
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

	def bootloader_is_present (self):
		'''
		Check for the Tock bootloader. Returns `True` if it is present, `False`
		if not, and `None` if unsure.
		'''
		return None

	def get_bootloader_version (self):
		'''
		Return the version string of the bootloader. Should return a value
		like `0.5.0`, or `None` if it is unknown.
		'''
		return

	def determine_current_board (self):
		'''
		Figure out which board we are connected to. Most likely done by reading
		the attributes. Doesn't return anything.
		'''
		return

	def get_board_name (self):
		'''
		Return the name of the board we are connected to.
		'''
		return self.board

	def get_board_arch (self):
		'''
		Return the architecture of the board we are connected to.
		'''
		return self.arch
