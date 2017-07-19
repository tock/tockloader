import struct

class TBFHeader:
	'''
	Tock Binary Format header class. This can parse TBF encoded headers and
	return various properties of the application.
	'''

	HEADER_TYPE_MAIN                    = 0x01
	HEADER_TYPE_WRITEABLE_FLASH_REGIONS = 0x02
	HEADER_TYPE_PACKAGE_NAME            = 0x03
	HEADER_TYPE_PIC_OPTION_1            = 0x04

	def __init__ (self, buffer):
		self.valid = False
		self.is_app = False
		self.fields = {}

		# Need at least a version number
		if len(buffer) < 4:
			return

		# Get the version number
		self.version = struct.unpack('<H', buffer[0:2])[0]
		buffer = buffer[2:]

		if self.version == 1 and len(buffer) >= 74:
			buffer = buffer[2:]
			base = struct.unpack('<IIIIIIIIIIIIIIIIII', buffer[0:72])
			buffer = buffer[72:]
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
			self.fields['checksum'] = base[17]
			self.is_app = True

			if self._checksum() == self.fields['checksum']:
				self.valid = True

		elif self.version == 2 and len(buffer) >= 14:
			base = struct.unpack('<HIII', buffer[0:14])
			buffer = buffer[14:]
			self.fields['header_size'] = base[0]
			self.fields['total_size'] = base[1]
			self.fields['flags'] = base[2]
			self.fields['checksum'] = base[3]

			remaining = self.fields['header_size'] - 16

			# Now check to see if this is an app or padding.
			if remaining > 0 and len(buffer) >= remaining:
				# This is an application. That means we need more parsing.
				self.is_app = True

				while remaining >= 4:
					base = struct.unpack('<HH', buffer[0:4])
					buffer = buffer[4:]
					tipe = base[0]
					length = base[1]

					remaining -= 4

					if tipe == self.HEADER_TYPE_MAIN:
						if remaining >= 12 and length == 12:
							base = struct.unpack('<III', buffer[0:12])
							buffer = buffer[12:]
							self.fields['init_fn_offset'] = base[0]
							self.fields['protected_size'] = base[1]
							self.fields['minimum_ram_size'] = base[2]

					elif tipe == self.HEADER_TYPE_WRITEABLE_FLASH_REGIONS:
						if remaining >= length:
							self.writeable_flash_regions = []
							for i in length / 8:
								base = struct.unpack('<II', buffer[0:8])
								buffer = buffer[8:]
								# Add offset,length.
								self.writeable_flash_regions.append((base[0], base[1]))

					elif tipe == self.HEADER_TYPE_PACKAGE_NAME:
						if remaining >= length:
							self.package_name = buffer[0:length].decode('utf-8')
							buffer = buffer[length:]

					elif tipe == self.HEADER_TYPE_PIC_OPTION_1:
						if remaining >= 40 and length == 40:
							base = struct.unpack('<IIIIIIIIII', buffer[0:40])
							buffer = buffer[40:]
							self.fields['text_offset'] = base[0]
							self.fields['data_offset'] = base[1]
							self.fields['data_size'] = base[2]
							self.fields['bss_memory_offset'] = base[3]
							self.fields['bss_size'] = base[4]
							self.fields['relocation_data_offset'] = base[5]
							self.fields['relocation_data_size'] = base[6]
							self.fields['got_offset'] = base[7]
							self.fields['got_size'] = base[8]
							self.fields['minimum_stack_length'] = base[9]

							self.pic_strategy = 'C Style'

					remaining -= length


				# if self._checksum() == self.fields['checksum']:
				self.valid = True


				# if len(buffer) >= 16:
				# 	base = struct.unpack('<IIII', buffer[0:16])
				# 	buffer = buffer[16:]
				# 	self.fields['init_fn_offset'] = base[0]
				# 	self.fields['protected_size'] = base[1]
				# 	self.fields['minimum_ram_size'] = base[2]
				# 	self.fields['number_writeable_flash_regions'] = base[3]

				# 	# Extract any writeable flash regions specified.
				# 	self.writeable_flash_regions = []
				# 	if self.fields['number_writeable_flash_regions'] > 0:
				# 		if len(buffer) >= self.fields['number_writeable_flash_regions']*8:
				# 			for i in self.fields['number_writeable_flash_regions']:
				# 				base = struct.unpack('<II', buffer[0:8])
				# 				buffer = buffer[8:]
				# 				# Add offset,length.
				# 				self.writeable_flash_regions.append((base[0], base[1]))

				# 	# Check if there are PIC fields.
				# 	if (self.fields['flags'] >> 3) & 0x07 == 0x01 and len(buffer) >= 40:
				# 		base = struct.unpack('<IIIIIIIIII', buffer[0:40])
				# 		buffer = buffer[40:]
				# 		self.fields['text_offset'] = base[0]
				# 		self.fields['data_offset'] = base[1]
				# 		self.fields['data_size'] = base[2]
				# 		self.fields['bss_memory_offset'] = base[3]
				# 		self.fields['bss_size'] = base[4]
				# 		self.fields['relocation_data_offset'] = base[5]
				# 		self.fields['relocation_data_size'] = base[6]
				# 		self.fields['got_offset'] = base[7]
				# 		self.fields['got_size'] = base[8]
				# 		self.fields['minimum_stack_length'] = base[9]

				# 	# Now get the package name.
				# 	if len(buffer) >= 4:
				# 		base = struct.unpack('<I', buffer[0:4])
				# 		buffer = buffer[4:]
				# 		self.fields['package_name_size'] = base[0]

				# 		if len(buffer) >= self.fields['package_name_size']:
				# 			self.package_name = buffer[0:self.fields['package_name_size']].decode('utf-8')

				# 		# And check the checksum. We do this here because
				# 		# we don't want the checksum to match if the buffer
				# 		# isn't long enough.
				# 		if self._checksum() == self.fields['checksum']:
				# 			self.valid = True

			else:
				# This is just padding and not an app.
				if self._checksum() == self.fields['checksum']:
					self.valid = True

		else:
			# Unknown version.
			return

	def is_valid (self):
		'''
		Whether the CRC and other checks passed for this header.
		'''
		return self.valid

	def is_enabled (self):
		'''
		Whether the application is marked as enabled. Enabled apps start when
		the board boots, and disabled ones do not.
		'''
		if not self.valid:
			return False
		elif self.version == 1:
			# Version 1 apps don't have this bit so they are just always enabled
			return True
		else:
			return self.fields['flags'] & 0x02 == 0x02

	def is_sticky (self):
		'''
		Whether the app is marked sticky and won't be erase during normal app
		erases.
		'''
		if not self.valid:
			return False
		elif self.version == 1:
			# No sticky bit in version 1, so they are not sticky
			return False
		else:
			return self.fields['flags'] & 0x04 == 0x04

	def set_flag (self, flag_name, flag_value):
		'''
		Set a flag in the TBF header.

		Valid flag names: `enable`, `sticky`
		'''
		if self.version == 1 or not self.valid:
			return

		if flag_name == 'enable':
			if flag_value:
				self.fields['flags'] |= 0x02;
			else:
				self.fields['flags'] &= ~0x02;

		elif flag_name == 'sticky':
			if flag_value:
				self.fields['flags'] |= 0x04;
			else:
				self.fields['flags'] &= ~0x04;

	def get_app_size (self):
		'''
		Get the total size the app takes in bytes in the flash of the chip.
		'''
		return self.fields['total_size']

	def get_app_name (self):
		'''
		Return the package name if it was encoded in the header, otherwise
		return a tuple of (package_name_offset, package_name_size).
		'''
		if hasattr(self, 'package_name'):
			return self.package_name
		elif 'package_name_offset' in self.fields and 'package_name_size' in self.fields:
			return (self.fields['package_name_offset'], self.fields['package_name_size'])
		else:
			return ''

	# Return a buffer containing the header repacked as a binary buffer
	def get_binary (self):
		'''
		Get the TBF header in a bytes array.
		'''
		if self.version == 1:
			buf = struct.pack('<IIIIIIIIIIIIIIIIIII',
				self.version, self.fields['total_size'], self.fields['entry_offset'],
				self.fields['rel_data_offset'], self.fields['rel_data_size'],
				self.fields['text_offset'], self.fields['text_size'],
				self.fields['got_offset'], self.fields['got_size'],
				self.fields['data_offset'], self.fields['data_size'],
				self.fields['bss_mem_offset'], self.fields['bss_mem_size'],
				self.fields['min_stack_len'], self.fields['min_app_heap_len'],
				self.fields['min_kernel_heap_len'], self.fields['package_name_offset'],
				self.fields['package_name_size'], self._checksum())

		elif self.version == 2:
			buf = struct.pack('<HHIII',
				self.version, self.fields['header_size'], self.fields['total_size'],
				self.fields['flags'], self._checksum())
			if self.is_app:
				buf += struct.pack('<HHIII',
					self.HEADER_TYPE_MAIN, 12,
					self.fields['init_fn_offset'], self.fields['protected_size'],
					self.fields['minimum_ram_size'])
				if hasattr(self, 'writeable_flash_regions'):
					buf += struct.pack('<HH',
						self.HEADER_TYPE_WRITEABLE_FLASH_REGIONS,
						len(self.writeable_flash_regions) * 8)
					for wfr in self.writeable_flash_regions:
						buf += struct.pack('<II', wfr[0], wfr[1])
				if hasattr(self, 'pic_strategy'):
					if self.pic_strategy == 'C Style':
						buf += struct.pack('<HHIIIIIIIIII',
							self.HEADER_TYPE_PIC_OPTION_1, 40,
							self.fields['text_offset'], self.fields['data_offset'],
							self.fields['data_size'], self.fields['bss_memory_offset'],
							self.fields['bss_size'], self.fields['relocation_data_offset'],
							self.fields['relocation_data_size'], self.fields['got_offset'],
							self.fields['got_size'], self.fields['minimum_stack_length'])
				if hasattr(self, 'package_name'):
					encoded_name = self.package_name.encode('utf-8')
					buf += struct.pack('<HH', self.HEADER_TYPE_PACKAGE_NAME, len(encoded_name))
					buf += encoded_name

		return buf

	def _checksum (self):
		'''
		Calculate the TBF header checksum.
		'''
		if self.version == 1:
			return self.version ^ self.fields['total_size'] ^ self.fields['entry_offset'] \
				^ self.fields['rel_data_offset'] ^ self.fields['rel_data_size'] ^ self.fields['text_offset'] \
				^ self.fields['text_size'] ^ self.fields['got_offset'] ^ self.fields['got_size'] \
				^ self.fields['data_offset'] ^ self.fields['data_size'] ^ self.fields['bss_mem_offset'] \
				^ self.fields['bss_mem_size'] ^ self.fields['min_stack_len'] \
				^ self.fields['min_app_heap_len'] ^ self.fields['min_kernel_heap_len'] \
				^ self.fields['package_name_offset'] ^ self.fields['package_name_size']

		elif self.version == 2:
			checksum = self.version ^ self.fields['total_size'] ^ self.fields['flags']
			# if self.is_app:
			# 	checksum ^= self.fields['init_fn_offset'] ^ self.fields['protected_size'] \
			# 		^ self.fields['minimum_ram_size'] ^ self.fields['number_writeable_flash_regions']
			# 	if self.fields['number_writeable_flash_regions'] > 0:
			# 		for wfr in self.writeable_flash_regions:
			# 			checksum ^= wfr[0] ^ wfr[1]
			# 	if (self.fields['flags'] >> 3) & 0x07 == 0x01:
			# 		checksum ^= self.fields['text_offset'] ^ self.fields['data_offset'] \
			# 			^ self.fields['data_size'] ^ self.fields['bss_memory_offset'] \
			# 			^ self.fields['bss_size'] ^ self.fields['relocation_data_offset'] \
			# 			^ self.fields['relocation_data_size'] ^ self.fields['got_offset'] \
			# 			^ self.fields['got_size'] ^ self.fields['minimum_stack_length']
			# 	checksum ^= self.fields['package_name_size']
			return checksum

		else:
			return 0

	def __str__ (self):
		out = ''
		if not self.valid:
			out += 'INVALID!\n'
		if hasattr(self, 'package_name'):
			out += '{:<30}: {}\n'.format('package_name', self.package_name)
		if hasattr(self, 'pic_strategy'):
			out += '{:<30}: {}\n'.format('PIC', self.pic_strategy)
		out += '{:<30}: {:>8}\n'.format('version', self.version)
		if hasattr(self, 'writeable_flash_regions'):
			for i, wfr in enumerate(self.writeable_flash_regions):
				out += 'writeable flash region {}\n'.format(i)
				out += '  {:<28}: {:>8} {:>#10x}\n'.format('offset', wfr[0], wfr[0])
				out += '  {:<28}: {:>8} {:>#10x}\n'.format('length', wfr[1], wfr[1])
		for k,v in sorted(self.fields.items()):
			out += '{:<30}: {:>8} {:>#10x}\n'.format(k, v, v)
			if k == 'flags':
				out += '  {:<28}: {:>8}\n'.format('enabled', (v >> 0) & 0x01)
				out += '  {:<28}: {:>8}\n'.format('sticky', (v >> 1) & 0x01)

		out += '{:<30}:          {:>#10x}'.format('checksum', self._checksum(), self._checksum())
		return out
