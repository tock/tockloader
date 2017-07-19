import textwrap

class App:
	'''
	Representation of a Tock app stored on a board.
	'''

	def __init__ (self, tbfh, address, name, binary=None):
		self.tbfh = tbfh
		self.address = address
		self.name = name
		self.binary = binary

	def is_sticky (self):
		'''
		Returns true if the app is set as sticky and will not be removed with
		a normal app erase command. Sticky apps must be force removed.
		'''
		return self.tbfh.is_sticky()

	def get_size (self):
		'''
		Return the total size (including TBF header) of this app in bytes.
		'''
		return self.tbfh.get_app_size()

	def get_header_binary (self):
		'''
		Get the TBF header as a bytes array.
		'''
		return self.tbfh.get_binary()

	def set_binary (self, binary):
		'''
		Update the application binary. Likely this binary would come from the
		existing contents of flash on a board.
		'''
		self.binary = binary

	def set_address (self, address):
		'''
		Set the address of flash where this app is or should go.
		'''
		self.address = address

	def has_binary (self):
		'''
		Whether we have the actually application binary for this app.
		'''
		return self.binary != None

	def info (self, verbose=False):
		'''
		Get a string describing various properties of the app.
		'''
		offset = self.address
		fields = self.tbfh.fields

		out = ''
		out += 'Name:                  {}\n'.format(self.name)
		out += 'Enabled:               {}\n'.format(self.tbfh.is_enabled())
		out += 'Sticky:                {}\n'.format(self.tbfh.is_sticky())
		out += 'Total Size in Flash:   {} bytes\n'.format(self.get_size())

		if verbose:
			out += textwrap.indent(str(self.tbfh), '  ')
		return out

	def __str__ (self):
		return self.name
