import struct
import textwrap

class InstalledApp:
	'''
	Representation of a Tock app installed on a specific board.

	At the very least this includes the TBF header and an address of where the
	app is on the board. It can also include the actual app binary which is
	necessary if the app needs to be moved.
	'''

	def __init__ (self, tbfh, address, app_binary=None):
		self.tbfh = tbfh             # A `tbfh` object representing this app's header.
		self.app_binary = app_binary # A binary array of the app _after_ the header.
		self.address = address       # Where on the board this app currently is.

		self.modified = False        # A flag indicating if this app has been modified by tockloader.

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
		return self.modified or self.tbfh.is_modified()

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
		self.is_modified = True

	def has_fixed_addresses(self):
		'''
		Return true if the TBF binary is compiled for a fixed address.
		'''
		return self.tbfh.has_fixed_addresses()

	def is_loadable_at_address (self, address):
		'''
		Check if it is possible to load this app at the given address. Returns
		True if it is possible, False otherwise.
		'''
		if not self.has_fixed_addresses():
			# If there are not fixed addresses, then we can flash this anywhere.
			return True

		# Check if the flash address matches.
		return self.tbfh.get_fixed_addresses()[1] - self.tbfh.get_header_size() == address

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
		self.modified = True

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
		if not self.is_modified() and address == self.address:
			return None

		binary = self.tbfh.get_binary() + self.app_binary

		# Check that the binary is not longer than it is supposed to be. This
		# might happen if the size was changed, but any code using this binary
		# has no way to check. If the binary is too long, we truncate the actual
		# binary blob (which should just be padding) to the correct length. If
		# it is too short it is ok, since the board shouldn't care what is in
		# the flash memory the app is not using.
		size = self.get_size()
		if len(binary) > size:
			binary = binary[0:size]

		return binary

	def info (self, verbose=False):
		'''
		Get a string describing various properties of the app.
		'''
		offset = self.address
		fields = self.tbfh.fields

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
