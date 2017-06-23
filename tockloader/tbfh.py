import struct

################################################################################
## Tock Binary Format Header
################################################################################

class TBFHeader:
	def __init__ (self, buffer):
		self.valid = False
		self.fields = {}

		# Need at least a version number
		if len(buffer) < 4:
			return

		# Get the version number
		self.version = struct.unpack('<I', buffer[0:4])[0]

		if (self.version == 1 or self.version == 2) and len(buffer) >= 72:
			# Version 1 and 2 have the same first fields
			base = struct.unpack('<IIIIIIIIIIIIIIIII', buffer[4:72])
			self.fields['total_size'] = base[0]
			self.fields['entry_offset'] = base[1]
			self.fields['rel_data_offset'] = base[2]
			self.fields['rel_data_size'] = base[3]
			self.fields['text_offset'] = base[4]
			self.fields['text_size'] = base[5]
			self.fields['got_offset'] = base[6]
			self.fields['got_size'] = base[7]
			self.fields['data_offset'] = base[8]
			self.fields['data_size'] = base[9]
			self.fields['bss_mem_offset'] = base[10]
			self.fields['bss_mem_size'] = base[11]
			self.fields['min_stack_len'] = base[12]
			self.fields['min_app_heap_len'] = base[13]
			self.fields['min_kernel_heap_len'] = base[14]
			self.fields['package_name_offset'] = base[15]
			self.fields['package_name_size'] = base[16]
		else:
			return

		if self.version == 1 and len(buffer) >= 76:
			others = struct.unpack('<I', buffer[72:76])
			checksum = others[0]

			if self._checksum() == checksum:
				self.valid = True

		elif self.version == 2 and len(buffer) >= 80:
			others = struct.unpack('<II', buffer[72:80])
			self.fields['flags'] = others[0]
			checksum = others[1]

			if self._checksum() == checksum:
				self.valid = True

	def is_valid (self):
		return self.valid

	def is_enabled (self):
		if not self.valid:
			return False
		elif self.version == 1:
			# Version 1 apps don't have this bit so they are just always enabled
			return True
		else:
			return self.fields['flags'] & 0x01 == 0x01

	def is_sticky (self):
		if not self.valid:
			return False
		elif self.version == 1:
			# No sticky bit in version 1, so they are not sticky
			return False
		else:
			return self.fields['flags'] & 0x02 == 0x02

	def set_flag(self, flag_name, flag_value):
		if self.version == 1 or not self.valid:
			return

		if flag_name == 'enable':
			if flag_value:
				self.fields['flags'] |= 0x01;
			else:
				self.fields['flags'] &= ~0x01;

		elif flag_name == 'sticky':
			if flag_value:
				self.fields['flags'] |= 0x02;
			else:
				self.fields['flags'] &= ~0x02;

	def get_app_size (self):
		return self.fields['total_size']

	def get_name_offset (self):
		return self.fields['package_name_offset']

	def get_name_length (self):
		return self.fields['package_name_size']

	# Return a buffer containing the header repacked as a binary buffer
	def get_binary (self):
		buf = struct.pack('<IIIIIIIIIIIIIIIIII',
			self.version, self.fields['total_size'], self.fields['entry_offset'],
			self.fields['rel_data_offset'], self.fields['rel_data_size'],
			self.fields['text_offset'], self.fields['text_size'],
			self.fields['got_offset'], self.fields['got_size'],
			self.fields['data_offset'], self.fields['data_size'],
			self.fields['bss_mem_offset'], self.fields['bss_mem_size'],
			self.fields['min_stack_len'], self.fields['min_app_heap_len'],
			self.fields['min_kernel_heap_len'], self.fields['package_name_offset'],
			self.fields['package_name_size'])

		if self.version == 2:
			buf += struct.pack('<I', self.fields['flags'])

		buf += struct.pack('<I', self._checksum())
		return buf

	def _checksum (self):
		if self.version == 1:
			return self.version ^ self.fields['total_size'] ^ self.fields['entry_offset'] \
			      ^ self.fields['rel_data_offset'] ^ self.fields['rel_data_size'] ^ self.fields['text_offset'] \
			      ^ self.fields['text_size'] ^ self.fields['got_offset'] ^ self.fields['got_size'] \
			      ^ self.fields['data_offset'] ^ self.fields['data_size'] ^ self.fields['bss_mem_offset'] \
			      ^ self.fields['bss_mem_size'] ^ self.fields['min_stack_len'] \
			      ^ self.fields['min_app_heap_len'] ^ self.fields['min_kernel_heap_len'] \
			      ^ self.fields['package_name_offset'] ^ self.fields['package_name_size']

		elif self.version == 2:
			return self.version ^ self.fields['total_size'] ^ self.fields['entry_offset'] \
			      ^ self.fields['rel_data_offset'] ^ self.fields['rel_data_size'] ^ self.fields['text_offset'] \
			      ^ self.fields['text_size'] ^ self.fields['got_offset'] ^ self.fields['got_size'] \
			      ^ self.fields['data_offset'] ^ self.fields['data_size'] ^ self.fields['bss_mem_offset'] \
			      ^ self.fields['bss_mem_size'] ^ self.fields['min_stack_len'] \
			      ^ self.fields['min_app_heap_len'] ^ self.fields['min_kernel_heap_len'] \
			      ^ self.fields['package_name_offset'] ^ self.fields['package_name_size'] \
			      ^ self.fields['flags']
		else:
			return 0

	def __str__ (self):
		out = ''
		out += '{:<19}: {:>8}\n'.format('version', self.version)
		for k,v in sorted(self.fields.items()):
			out += '{:<19}: {:>8} {:>#10x}\n'.format(k, v, v)
			if k == 'flags':
				out += '  {:<17}: {:>8}\n'.format('enabled', v & 0x01)
				out += '  {:<17}: {:>8}\n'.format('sticky', (v & 0x02) >> 1)
		out += '{:<19}:          {:>#10x}'.format('checksum', self._checksum(), self._checksum())
		return out
