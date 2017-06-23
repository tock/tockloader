
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
			out += 'Flash Start Address:   {:#010x}\n'.format(offset)
			out += 'Flash End Address:     {:#010x}\n'.format(offset+self.get_size()-1)
			out += 'Entry Address:         {:#010x}\n'.format(offset+fields['entry_offset'])
			out += 'Relocate Data Address: {:#010x} (length: {} bytes)\n'.format(offset+fields['rel_data_offset'], fields['rel_data_size'])
			out += 'Text Address:          {:#010x} (length: {} bytes)\n'.format(offset+fields['text_offset'], fields['text_size'])
			out += 'GOT Address:           {:#010x} (length: {} bytes)\n'.format(offset+fields['got_offset'], fields['got_size'])
			out += 'Data Address:          {:#010x} (length: {} bytes)\n'.format(offset+fields['data_offset'], fields['data_size'])
			out += 'Minimum Stack Size:    {} bytes\n'.format(fields['min_stack_len'])
			out += 'Minimum Heap Size:     {} bytes\n'.format(fields['min_app_heap_len'])
			out += 'Minimum Grant Size:    {} bytes'.format(fields['min_kernel_heap_len'])
		return out

	def __str__ (self):
		return self.name
