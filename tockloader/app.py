
class App:
	'''
	Representation of a Tock app stored on a board. YES
	'''

	def __init__ (self, tbfh, address, name, binary=None):
		self.tbfh = tbfh
		self.address = address
		self.name = name
		self.binary = binary

	def is_sticky (self):
		return self.tbfh.is_sticky()

	# Return the total size (including TBF header) of this app in bytes.
	def get_size (self):
		return self.tbfh.get_app_size()

	def get_header_binary (self):
		return self.tbfh.get_binary()

	def set_binary (self, binary):
		self.binary = binary

	def set_address (self, address):
		self.address = address

	def has_binary (self):
		return self.binary != None

	def info (self, verbose=False):
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
