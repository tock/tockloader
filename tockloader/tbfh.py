
import logging
import struct

def roundup (x, to):
	return x if x % to == 0 else x + to - x % to

class TBFHeader:
	'''
	Tock Binary Format header class. This can parse TBF encoded headers and
	return various properties of the application.
	'''

	HEADER_TYPE_MAIN                    = 0x01
	HEADER_TYPE_WRITEABLE_FLASH_REGIONS = 0x02
	HEADER_TYPE_PACKAGE_NAME            = 0x03
	HEADER_TYPE_PIC_OPTION_1            = 0x04
	HEADER_TYPE_FIXED_ADDRESSES         = 0x05

	def __init__ (self, buffer):
		# Flag that records if this TBF header is valid. This is calculated once
		# when a new TBF header is read in. Any manipulations that tockloader
		# does will not make a TBF header invalid, so we do not need to
		# re-calculate this.
		self.valid = False
		# Whether this TBF header is for an app, or is just padding (or perhaps
		# something else). Tockloader will not change this after the TBF header
		# is initially parsed, so we do not need to re-calculate this and can
		# used a flag here.
		self.is_app = False
		# Whether the TBF header has been modified from when it was first
		# created (by calling `__init__`). This might happen, for example, if a
		# new flag was set. We keep track of this so that we know if we need to
		# re-flash the TBF header to the board.
		self.modified = False

		self.fields = {}

		full_buffer = buffer;

		# Need at least a version number
		if len(buffer) < 2:
			return

		# Get the version number
		self.version = struct.unpack('<H', buffer[0:2])[0]
		buffer = buffer[2:]

		if self.version == 1 and len(buffer) >= 74:
			checksum = self._checksum(full_buffer[0:72])
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

			if checksum == self.fields['checksum']:
				self.valid = True

		elif self.version == 2 and len(buffer) >= 14:
			base = struct.unpack('<HIII', buffer[0:14])
			buffer = buffer[14:]
			self.fields['header_size'] = base[0]
			self.fields['total_size'] = base[1]
			self.fields['flags'] = base[2]
			self.fields['checksum'] = base[3]

			if len(full_buffer) >= self.fields['header_size'] and self.fields['header_size'] >= 16:
				# Zero out checksum for checksum calculation.
				nbuf = bytearray(self.fields['header_size'])
				nbuf[:] = full_buffer[0:self.fields['header_size']]
				struct.pack_into('<I', nbuf, 12, 0)
				checksum = self._checksum(nbuf)

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
								self.fields['init_fn_offset'] = base[0]
								self.fields['protected_size'] = base[1]
								self.fields['minimum_ram_size'] = base[2]

						elif tipe == self.HEADER_TYPE_WRITEABLE_FLASH_REGIONS:
							self.writeable_flash_regions = []
							if remaining >= length:
								for i in range(0, int(length / 8)):
									base = struct.unpack('<II', buffer[i*8:(i+1)*8])
									# Add offset,length.
									self.writeable_flash_regions.append((base[0], base[1]))

						elif tipe == self.HEADER_TYPE_PACKAGE_NAME:
							if remaining >= length:
								self.package_name = buffer[0:length].decode('utf-8')

						elif tipe == self.HEADER_TYPE_PIC_OPTION_1:
							if remaining >= 40 and length == 40:
								base = struct.unpack('<IIIIIIIIII', buffer[0:40])
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

						elif tipe == self.HEADER_TYPE_FIXED_ADDRESSES:
							if remaining >= 8 and length == 8:
								base = struct.unpack('<II', buffer[0:8])
								self.fields['fixed_address_ram'] = base[0]
								self.fields['fixed_address_flash'] = base[1]
								self.fixed_addresses = True

						else:
							logging.warning('Unknown TLV block in TBF header.')
							logging.warning('You might want to update tockloader.')

							# Add the unknown data to the stored state so we can
							# put it back afterwards.
							if not hasattr(self, 'unknown'):
								self.unknown = []
							self.unknown.append((tipe, length, buffer[0:length]))

						# All blocks are padded to four byte, so we may need to
						# round up.
						length = roundup(length, 4)
						buffer = buffer[length:]
						remaining -= length

					if checksum == self.fields['checksum']:
						self.valid = True
					else:
						logging.error('Checksum mismatch. in packet: {:#x}, calculated: {:#x}'.format(self.fields['checksum'], checksum))

				else:
					# This is just padding and not an app.
					if checksum == self.fields['checksum']:
						self.valid = True

	def is_valid (self):
		'''
		Whether the CRC and other checks passed for this header.
		'''
		return self.valid

	def is_modified (self):
		'''
		Whether the TBF header has been modified by Tockloader after it was
		initially read in (either from a new TAB or from the board).
		'''
		return self.modified

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
			return self.fields['flags'] & 0x01 == 0x01

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
			return self.fields['flags'] & 0x02 == 0x02

	def set_flag (self, flag_name, flag_value):
		'''
		Set a flag in the TBF header.

		Valid flag names: `enable`, `sticky`
		'''
		if self.version == 1 or not self.valid:
			return

		if flag_name == 'enable':
			if flag_value:
				self.fields['flags'] |= 0x01;
			else:
				self.fields['flags'] &= ~0x01;
			self.modified = True

		elif flag_name == 'sticky':
			if flag_value:
				self.fields['flags'] |= 0x02;
			else:
				self.fields['flags'] &= ~0x02;
			self.modified = True

	def get_app_size (self):
		'''
		Get the total size the app takes in bytes in the flash of the chip.
		'''
		return self.fields['total_size']

	def set_app_size (self, size):
		'''
		Set the total size the app takes in bytes in the flash of the chip.

		Since this does not change the header size we do not need to update
		any other fields in the header.
		'''
		self.fields['total_size'] = size
		self.modified = True

	def get_header_size (self):
		'''
		Get the size of the header in bytes. This includes any alignment
		padding at the end of the header.
		'''
		if self.version == 1:
			return 74
		else:
			return self.fields['header_size']

	def get_size_before_app (self):
		'''
		Get the number of bytes before the actual app binary in the .tbf file.
		'''
		if self.version == 1:
			return 74
		else:
			return self.fields['header_size'] + self.fields['protected_size']

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

	def has_fixed_addresses (self):
		'''
		Return true if this TBF header includes the fixed addresses TLV.
		'''
		return hasattr(self, 'fixed_addresses')

	def get_fixed_addresses (self):
		'''
		Return (fixed_address_ram, fixed_address_flash) if there are fixed
		addresses, or None.
		'''
		if hasattr(self, 'fixed_addresses'):
			return (self.fields['fixed_address_ram'], self.fields['fixed_address_flash'])
		else:
			return None

	def adjust_starting_address (self, address):
		'''
		Alter this TBF header so the fixed address in flash will be correct
		if the entire TBF binary is loaded at address `address`.
		'''
		# Check if we can even do anything. No fixed address means this is
		# meaningless.
		if hasattr(self, 'fixed_addresses'):
			# Now see if the header is already the right length.
			if address + self.fields['header_size'] + self.fields['protected_size'] != self.fields['fixed_address_flash']:
				# Make sure we need to make the header bigger
				if address + self.fields['header_size'] + self.fields['protected_size'] < self.fields['fixed_address_flash']:
					# The header is too small, so we can fix it.
					delta = self.fields['fixed_address_flash'] - (address + self.fields['header_size'] + self.fields['protected_size'])
					# Increase the protected size to match this.
					self.fields['protected_size'] += delta

					#####
					##### NOTE! Based on how things are implemented in the Tock
					##### universe, it seems we also need to increase the
					##### `init_fn_offset`, which is calculated from the end of
					##### the TBF header everywhere, and NOT the beginning of
					##### the actual application binary (like the documentation
					##### indicates it should be).
					#####
					self.fields['init_fn_offset'] += delta

				else:
					# The header actually needs to shrink, which we can't do.
					# We should never hit this case.
					raise TockLoaderException('Cannot shrink the header. This is a tockloader bug.')


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
				self.fields['package_name_size'])
			checksum = self._checksum(buf)
			buf += struct.pack('<I', checksum)

		elif self.version == 2:
			buf = struct.pack('<HHIII',
				self.version, self.fields['header_size'], self.fields['total_size'],
				self.fields['flags'], 0)
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
					# May need to add padding.
					padding_length = roundup(len(encoded_name), 4) - len(encoded_name)
					if padding_length > 0:
						buf += b'\0'*padding_length
				if hasattr(self, 'fixed_addresses'):
					buf += struct.pack('<HHII',
						self.HEADER_TYPE_FIXED_ADDRESSES, 8,
						self.fields['fixed_address_ram'],
						self.fields['fixed_address_flash'])
				if hasattr(self, 'unknown'):
					# Add back any unknown headers so they are preserved in the
					# binary.
					for tipe,length,binary in self.unknown:
						buf += struct.pack('<HH', tipe, length)
						buf += binary

			nbuf = bytearray(len(buf))
			nbuf[:] = buf
			buf = nbuf

			checksum = self._checksum(buf)
			struct.pack_into('<I', buf, 12, checksum)

			if 'protected_size' in self.fields and self.fields['protected_size'] > 0:
				# Add padding to this header binary to account for the
				# protected region between the header and the application
				# binary.
				buf += b'\0'*self.fields['protected_size']

		return buf

	def _checksum (self, buffer):
		'''
		Calculate the TBF header checksum.
		'''
		# Add 0s to the end to make sure that we are multiple of 4.
		padding = len(buffer) % 4
		if padding != 0:
			padding = 4 - padding
			buffer += bytes([0]*padding)

		# Loop throw
		checksum = 0
		for i in range(0, len(buffer), 4):
			checksum ^= struct.unpack('<I', buffer[i:i+4])[0]

		return checksum

	def __str__ (self):
		out = ''

		if not self.valid:
			out += 'INVALID!\n'

		out += '{:<22}: {}\n'.format('version', self.version)

		# Special case version 1. However, at this point (May 2020), I would be
		# shocked if this ever gets run on a version 1 TBFH.
		if self.version == 1:
			for k,v in sorted(self.fields.items()):
				if k == 'checksum':
					out += '{:<22}:            {:>#12x}\n'.format(k, v)
				else:
					out += '{:<22}: {:>10} {:>#12x}\n'.format(k, v, v)

				if k == 'flags':
					values = ['No', 'Yes']
					out += '  {:<20}: {}\n'.format('enabled', values[(v >> 0) & 0x01])
					out += '  {:<20}: {}\n'.format('sticky', values[(v >> 1) & 0x01])
			return out

		# Base fields that always exist.
		out += '{:<22}: {:>10} {:>#12x}\n'.format('header_size', self.fields['header_size'], self.fields['header_size'])
		out += '{:<22}: {:>10} {:>#12x}\n'.format('total_size', self.fields['total_size'], self.fields['total_size'])
		out += '{:<22}:            {:>#12x}\n'.format('checksum', self.fields['checksum'])
		out += '{:<22}: {:>10} {:>#12x}\n'.format('flags', self.fields['flags'], self.fields['flags'])
		out += '  {:<20}: {}\n'.format('enabled', ['No', 'Yes'][(self.fields['flags'] >> 0) & 0x01])
		out += '  {:<20}: {}\n'.format('sticky', ['No', 'Yes'][(self.fields['flags'] >> 1) & 0x01])

		# Main TLV
		if self.is_app:
			out += 'TLV: Main ({})\n'.format(self.HEADER_TYPE_MAIN)
			out += '  {:<20}: {:>10} {:>#12x}\n'.format('init_fn_offset', self.fields['init_fn_offset'], self.fields['init_fn_offset'])
			out += '  {:<20}: {:>10} {:>#12x}\n'.format('protected_size', self.fields['protected_size'], self.fields['protected_size'])
			out += '  {:<20}: {:>10} {:>#12x}\n'.format('minimum_ram_size', self.fields['minimum_ram_size'], self.fields['minimum_ram_size'])

		if hasattr(self, 'package_name'):
			out += 'TLV: Package Name ({})\n'.format(self.HEADER_TYPE_PACKAGE_NAME)
			out += '  {:<20}: {}\n'.format('package_name', self.package_name)

		if hasattr(self, 'pic_strategy'):
			out += 'TLV: PIC Option 1 ({})\n'.format(self.HEADER_TYPE_PIC_OPTION_1)
			out += '  {:<20}: {}\n'.format('PIC', self.pic_strategy)

		if hasattr(self, 'writeable_flash_regions'):
			out += 'TLV: Writeable Flash Regions ({})\n'.format(self.HEADER_TYPE_WRITEABLE_FLASH_REGIONS)
			for i, wfr in enumerate(self.writeable_flash_regions):
				out += '  writeable flash region {}\n'.format(i)
				out += '    {:<18}: {:>8} {:>#12x}\n'.format('offset', wfr[0], wfr[0])
				out += '    {:<18}: {:>8} {:>#12x}\n'.format('length', wfr[1], wfr[1])

		if hasattr(self, 'fixed_addresses'):
			out += 'TLV: Fixed Addresses ({})\n'.format(self.HEADER_TYPE_FIXED_ADDRESSES)
			out += '  {:<20}: {:>10} {:>#12x}\n'.format('fixed_address_ram', self.fields['fixed_address_ram'], self.fields['fixed_address_ram'])
			out += '  {:<20}: {:>10} {:>#12x}\n'.format('fixed_address_flash', self.fields['fixed_address_flash'], self.fields['fixed_address_flash'])

		return out

class TBFHeaderPadding(TBFHeader):
	'''
	TBF Header that is only padding between apps. Since apps are packed as
	linked-list, this allows apps to be pushed to later addresses while
	preserving the linked-list structure.
	'''

	def __init__ (self, size):
		'''
		Create the TBF header. All we need to know is how long the entire
		padding should be.
		'''
		self.valid = True
		self.is_app = False
		self.modified = False
		self.fields = {}

		self.version = 2
		# self.fields['header_size'] = 14 # this causes interesting bugs...
		self.fields['header_size'] = 16
		self.fields['total_size'] = size
		self.fields['flags'] = 0
