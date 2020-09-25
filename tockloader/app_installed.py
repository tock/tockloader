import struct
import textwrap

class InstalledApp:
	'''
	Representation of a Tock app that is installed on a specific board. This
	object is created when Tockloader finds an app already installed on a board.

	At the very least this includes the TBF header and an address of where the
	app is on the board. It can also include the actual app binary which is
	necessary if the app needs to be moved.
	'''

	def __init__ (self, tbfh, address, app_binary=None):
		self.tbfh = tbfh             # A `tbfh` object representing this app's header.
		self.app_binary = app_binary # A binary array of the app _after_ the header.
		self.address = address       # Where on the board this app currently is.

		# Store the length of the TBF header and any padding before the actual
		# app binary. This allows us to keep track of if the actual application
		# has to move or not.
		self.original_size_before_app = tbfh.get_size_before_app()

		# A flag indicating if this app has been modified by tockloader.
		self.app_binary_modified = False

	def get_name (self):
		'''
		Return the app name.
		'''
		return self.tbfh.get_app_name()

	def is_modified (self):
		'''
		Returns whether this app has been modified by tockloader since it was
		initially created by `__init__`.
		'''
		return self.app_binary_modified or self.tbfh.is_modified()

	def is_sticky (self):
		'''
		Returns true if the app is set as sticky and will not be removed with
		a normal app erase command. Sticky apps must be force removed.
		'''
		return self.tbfh.is_sticky()

	def set_sticky (self):
		'''
		Mark this app as "sticky" in the app's header. This makes it harder to
		accidentally remove this app if it is a core service or debug app.
		'''
		self.tbfh.set_flag('sticky', True)

	def get_size (self):
		'''
		Return the total size (including TBF header) of this app in bytes.
		'''
		return self.tbfh.get_app_size()

	def set_size (self, size):
		'''
		Force the entire app to be a certain size. If `size` is smaller than the
		actual app an error will be thrown.
		'''
		header_size = self.tbfh.get_header_size()
		binary_size = len(self.app_binary)
		current_size = header_size + binary_size
		if size < current_size:
			raise TockLoaderException('Cannot make app smaller. Current size: {} bytes'.format(current_size))
		self.tbfh.set_app_size(size)

	def has_fixed_addresses(self):
		'''
		Return true if the TBF binary is compiled for a fixed address.
		'''
		return self.tbfh.has_fixed_addresses()

	def get_fixed_addresses_flash_and_sizes (self):
		'''
		Return a list of tuples of all addresses in flash this app is compiled
		for and the size of the app at that address.

		[(address, size), (address, size), ...]
		'''
		return [(self.tbfh.get_fixed_addresses()[1], self.tbfh.get_app_size())]

	def is_loadable_at_address (self, address):
		'''
		Check if it is possible to load this app at the given address. Returns
		True if it is possible, False otherwise.
		'''
		if not self.has_fixed_addresses():
			# If there are not fixed addresses, then we can flash this anywhere.
			return True


		fixed_flash_address = self.tbfh.get_fixed_addresses()[1]
		tbf_header_length = self.tbfh.get_header_size()

		# Ok, we have to be a little tricky here. What we actually care
		# about is ensuring that the application binary itself ends up at
		# the requested fixed address. However, what this function has to do
		# is see if the start of the TBF header can go at the requested
		# address. We have some flexibility, since we can make the header
		# larger so that it pushes the application binary to the correct
		# address. So, we want to see if we can reasonably do that. If we
		# are within 128 bytes, we say that we can.
		if fixed_flash_address >= (address + tbf_header_length) and\
		   (address + tbf_header_length + 128) > fixed_flash_address:
			return True

		return False

	def fix_at_next_loadable_address (self, address):
		'''
		Calculate the next reasonable address where we can put this app where
		the address is greater than or equal to `address`. The `address`
		argument is the earliest address the app can be at, either the start of
		apps or immediately after a previous app.

		If the app doesn't have a fixed address, then we can put it anywhere,
		and we just return the address. If the app is compiled with fixed
		addresses, then we need to calculate an address. We do a little bit of
		"reasonable assuming" here. Fixed addresses are based on where the _app
		binary_ must be located. Therefore, the start of the app where the TBF
		header goes must be before that. This can be at any address (as long as
		the header will fit), but we want to make this simpler, so we just
		assume the TBF header should start on a 1024 byte alignment.
		'''
		if not self.has_fixed_addresses():
			# No fixed addresses means we can put the app anywhere.
			return address

		def align_down_to(v, a):
			'''
			Calculate the address correctly aligned to `a` that is lower than or
			equal to `v`.
			'''
			return v - (v % a)

		# Get the fixed flash address. This address is fixed, and our starting
		# address must be before it.
		fixed_flash_address = self.tbfh.get_fixed_addresses()[1]

		# Align to get a reasonable address for this app.
		wanted_address = align_down_to(fixed_flash_address, 1024)

		if wanted_address >= address:
			return wanted_address
		else:
			return None

	def get_header (self):
		'''
		Return the TBFH object for the header.
		'''
		return self.tbfh

	def get_header_size (self):
		'''
		Return the size of the TBF header in bytes.
		'''
		return self.tbfh.get_header_size()

	def get_header_binary (self):
		'''
		Get the TBF header as a bytes array.
		'''
		return self.tbfh.get_binary()

	def set_app_binary (self, app_binary):
		'''
		Update the application binary. Likely this binary would come from the
		existing contents of flash on a board.
		'''
		self.app_binary = app_binary
		self.app_binary_modified = True

	def get_address (self):
		'''
		Get the address of where on the board the app is or should go.
		'''
		return self.address

	def has_app_binary (self):
		'''
		Whether we have the actual application binary for this app.
		'''
		return self.app_binary != None

	def get_app_binary (self):
		'''
		Return just the compiled application code binary. Does not include
		the TBF header.
		'''
		return self.app_binary

	def get_binary (self, address):
		'''
		Return the binary array comprising the entire application if it needs to
		be written to the board. Otherwise, if it is already installed, return
		`None`.
		'''
		# Since this is an already installed app, we first check to see if
		# anything actually changed. If not, then we don't need to re-flash this
		# app.
		if not self.is_modified() and address == self.address:
			return None

		# Set the starting address for this app. This is only relevant with
		# fixed addresses, and is a no-op for apps which are not compiled for
		# fixed addresses.
		self.tbfh.adjust_starting_address(address)

		# Now, we can check if we need to flash the header and the app binary,
		# or just the header. We need to flash both the header _and_ the app
		# binary
		#
		# - if the length of the header changed, or
		# - if the app binary itself has changed, or
		# - if the location of the app has changed
		if self.tbfh.get_size_before_app() != self.original_size_before_app or \
			self.app_binary_modified or \
			address != self.address:

			# Get the actual full app binary.
			binary = self.tbfh.get_binary() + self.app_binary

			# Check that the binary is not longer than it is supposed to be.
			# This might happen if the size was changed, but any code using this
			# binary has no way to check. If the binary is too long, we truncate
			# the actual binary blob (which should just be padding) to the
			# correct length. If it is too short it is ok, since the board
			# shouldn't care what is in the flash memory the app is not using.
			size = self.get_size()
			if len(binary) > size:
				logging.info('Binary is larger than what it says in the header. Actual:{}, expected:{}'
					.format(len(binary), size))
				logging.info('Truncating binary to match.')

				# Check on what we would be removing. If it is all zeros, we
				# determine that it is OK to truncate.
				to_remove = binary[size:]
				if len(to_remove) != to_remove.count(0):
					raise TockLoaderException('Error truncating binary. Not zero.')

			return binary

		else:
			# Only the header needs to be flashed
			return self.tbfh.get_binary()

	def info (self, verbose=False):
		'''
		Get a string describing various properties of the app.
		'''
		offset = self.address

		out = ''
		out += 'Name:                  {}\n'.format(self.get_name())
		out += 'Enabled:               {}\n'.format(self.tbfh.is_enabled())
		out += 'Sticky:                {}\n'.format(self.tbfh.is_sticky())
		out += 'Total Size in Flash:   {} bytes\n'.format(self.get_size())

		if verbose:
			out += 'Address in Flash:      {:#x}\n'.format(offset)
			out += textwrap.indent(str(self.tbfh), '  ')
		return out

	def __str__ (self):
		return self.get_name()
