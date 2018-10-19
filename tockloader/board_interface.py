
class BoardInterface:
	'''
	Base class for interacting with hardware boards. All of the class functions
	should be overridden to support a new method of interacting with a board.
	'''

	KNOWN_BOARDS = {
		'hail': {'arch': 'cortex-m4', 'jlink_device': 'ATSAM4LC8C', 'page_size': 512},
		'imix': {'arch': 'cortex-m4', 'jlink_device': 'ATSAM4LC8C', 'page_size': 512},
		'nrf51dk': {'arch': 'cortex-m0',
		            'jlink_device': 'nrf51422',
		            'page_size': 1024,
		            'openocd': 'nordic_nrf51_dk.cfg',
		            'openocd_options': ['workareazero']},
		'nrf52dk': {'arch': 'cortex-m4',
		            'jlink_device': 'nrf52',
		            'page_size': 4096,
		            'openocd': 'nordic_nrf52_dk.cfg'},
		'launchxl-cc26x2r1': {'arch': 'cortex-m4',
		                      'page_size': 512,
		                      'jlink_device': 'cc2652r1f',
		                      'jlink_speed': 4000,
		                      'jlink_if': 'jtag',
		                      'openocd': 'ti_cc26x2_launchpad.cfg',
		                      'openocd_options': ['noreset', 'resume']},
		'ek-tm4c1294xl': {'arch': 'cortex-m4',
		                  'page_size': 512,
		                  'openocd': 'ek-tm4c1294xl.cfg'},
	}

	def __init__ (self, args):
		self.args = args

		# These settings need to come from somewhere. Once place is the
		# command line. Another is the attributes section on the board.
		# There could be more in the future.
		# Also, not all are required depending on the connection method used.
		self.apps_start_address = getattr(self.args, 'app_address', None)
		self.board = getattr(self.args, 'board', None)
		self.arch = getattr(self.args, 'arch', None)
		self.jlink_device = getattr(self.args, 'jlink_device', None)
		self.jlink_speed = getattr(self.args, 'jlink_speed', None)
		self.jlink_if = getattr(self.args, 'jlink_if', None)
		self.openocd_board = getattr(self.args, 'openocd_board', None)
		self.openocd_options = getattr(self.args, 'openocd_options', [])
		self.page_size = getattr(self.args, 'page_size', 0)

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
		Get a single attribute. Returns a dict with two keys: `key` and `value`.
		'''
		# Default implementation to get an attribute. Reads flash directly and
		# extracts the attribute.
		address = 0x600 + (64 * index)
		attribute_raw = self.read_range(address, 64)
		return self._decode_attribute(attribute_raw)

	def get_all_attributes (self):
		'''
		Get all attributes on a board. Returns an array of attribute dicts.
		'''
		# Read the entire block of attributes directly from flash.
		# This is much faster.
		def chunks(l, n):
			for i in range(0, len(l), n):
				yield l[i:i + n]
		raw = self.read_range(0x600, 64*16)
		return [self._decode_attribute(r) for r in chunks(raw, 64)]

	def set_attribute (self, index, raw):
		'''
		Set a single attribute.
		'''
		address = 0x600 + (64 * index)
		self.flash_binary(address, raw)

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
		address = 0x40E
		version_raw = self.read_range(address, 8)
		try:
			return version_raw.decode('utf-8')
		except:
			return None

	def get_apps_start_address (self):
		'''
		Return the address in flash where applications start on this platform.
		This might be set on the board itself, in the command line arguments
		to Tockloader, or just be the default.
		'''

		# Start by checking if we already have the address. This would be if
		# we have already looked it up or we specified it on the command line.
		if self.apps_start_address != None:
			return self.apps_start_address

		# Check if there is an attribute we can use.
		attributes = self.get_all_attributes()
		for attribute in attributes:
			if attribute and attribute['key'] == 'appaddr':
				self.apps_start_address = int(attribute['value'], 0)
				return self.apps_start_address

		# Lastly resort to the default setting
		self.apps_start_address = 0x30000
		return self.apps_start_address

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

	def get_page_size (self):
		'''
		Return the size of the page in bytes for the connected board.
		'''
		return self.page_size

	def print_known_boards (self):
		'''
		Display the boards that have settings configured in tockloader.
		'''
		print('Known boards: {}'.format(', '.join(self.KNOWN_BOARDS.keys())))
