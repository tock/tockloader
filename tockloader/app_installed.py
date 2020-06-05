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
		None
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

	def get_crt0_header_str (self):
		'''
		Return a string representation of the crt0 header some apps use for
		doing PIC fixups. We assume this header is positioned immediately
		after the TBF header.
		'''
		header_size = self.tbfh.get_header_size()
		app_binary_notbfh = self.get_app_binary()

		crt0 = struct.unpack('<IIIIIIIIII', app_binary_notbfh[0:40])

		out = ''
		out += '{:<20}: {:>10} {:>#12x}\n'.format('got_sym_start', crt0[0], crt0[0])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('got_start', crt0[1], crt0[1])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('got_size', crt0[2], crt0[2])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('data_sym_start', crt0[3], crt0[3])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('data_start', crt0[4], crt0[4])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('data_size', crt0[5], crt0[5])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('bss_start', crt0[6], crt0[6])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('bss_size', crt0[7], crt0[7])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('reldata_start', crt0[8], crt0[8])
		out += '{:<20}: {:>10} {:>#12x}\n'.format('stack_size', crt0[9], crt0[9])

		return out

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
