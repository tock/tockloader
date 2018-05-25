import os
import shutil
import struct
import tarfile
import tempfile
import textwrap
import urllib.request

import pytoml

from .app import App
from .exceptions import TockLoaderException
from .tbfh import TBFHeader

class TAB:
	'''
	Tock Application Bundle object. This class handles the TAB format.
	'''
	def __init__ (self, tab_path):
		if os.path.exists(tab_path):
			# Fetch it from the local filesystem.
			self.tab = tarfile.open(tab_path)
		else:
			# Otherwise download it as a URL.
			with urllib.request.urlopen(tab_path) as response:
				tmp_file = tempfile.TemporaryFile()
				# Copy the downloaded response to our temporary file.
				shutil.copyfileobj(response, tmp_file)
				# Need to seek to the beginning of the file for tarfile
				# to work.
				tmp_file.seek(0)
				self.tab = tarfile.open(fileobj=tmp_file)

	def extract_app (self, arch):
		'''
		Return an `App` object from this TAB. You must specify the desired
		MCU architecture so the correct binary can be retrieved.
		'''
		try:
			binary_tarinfo = self.tab.getmember('{}.tbf'.format(arch))
		except Exception:
			binary_tarinfo = self.tab.getmember('{}.bin'.format(arch))
		binary = self.tab.extractfile(binary_tarinfo).read()

		# First get the TBF header from the correct binary in the TAB
		tbfh = TBFHeader(binary)

		if tbfh.is_valid():
			name_or_params = tbfh.get_app_name()
			if isinstance(name_or_params, str):
				name = name_or_params
			else:
				start = name_or_params[0]
				end = start+name_or_params[1]
				name = binary[start:end].decode('utf-8')

			# Check that total size actually matches the binary that we got.
			if tbfh.get_app_size() < len(binary):
				# It's fine if the binary is smaller, but the binary cannot be
				# longer than the amount of reserved space (`total_size` in the
				# TBF header) for the app.
				raise TockLoaderException('Invalid TAB, the app binary is longer than its defined total_size')

			return App(tbfh, None, name, binary)
		else:
			raise TockLoaderException('Invalid TBF found in app in TAB')

	def is_compatible_with_board (self, board):
		'''
		Check if the Tock app is compatible with a particular Tock board.
		'''
		metadata = self.parse_metadata()
		if metadata['tab-version'] == 1:
			return 'only-for-boards' not in metadata or \
			       board in metadata['only-for-boards'] or \
			       metadata['only-for-boards'] == ''
		else:
			raise TockLoaderException('Unable to understand version {} of metadata'.format(metadata['tab-version']))

	def parse_metadata (self):
		'''
		Open and parse the included metadata file in the TAB.
		'''
		metadata_tarinfo = self.tab.getmember('metadata.toml')
		metadata_str = self.tab.extractfile(metadata_tarinfo).read().decode('utf-8')
		return pytoml.loads(metadata_str)

	def get_supported_architectures (self):
		'''
		Return a list of architectures that this TAB has compiled binaries for.
		'''
		contained_files = self.tab.getnames()
		archs = [i[:-4] for i in contained_files if i[-4:] == '.tbf']
		if len(archs) == 0:
			archs = [i[:-4] for i in contained_files if i[-4:] == '.bin']
		return archs

	def get_tbf_header (self):
		'''
		Return a TBFHeader object with the TBF header from the app in the TAB.
		TBF headers are not architecture specific, so we pull from a random
		binary if there are multiple architectures supported.
		'''
		# Find a .tbf file
		for f in self.tab.getnames():
			if f[-4:] == '.tbf':
				binary_tarinfo = self.tab.getmember(f)
				binary = self.tab.extractfile(binary_tarinfo).read()

				# Get the TBF header from a binary in the TAB
				return TBFHeader(binary)

		# Fall back to a .bin file
		for f in self.tab.getnames():
			if f[-4:] == '.bin':
				binary_tarinfo = self.tab.getmember(f)
				binary = self.tab.extractfile(binary_tarinfo).read()

				# Get the TBF header from a binary in the TAB
				return TBFHeader(binary)
		return None

	def get_crt0_header_str (self, arch):
		'''
		Return a string representation of the crt0 header some apps use for
		doing PIC fixups. We assume this header is positioned immediately
		after the TBF header.
		'''
		app = self.extract_app(arch)
		header_size = app.tbfh.get_header_size()

		crt0 = struct.unpack('<IIIIIIIIIII', app.binary[header_size:header_size+44])

		out = ''
		out += '{:<20}: {:>8} {:>#12x}\n'.format('got_sym_start', crt0[0], crt0[0])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('got_start', crt0[1], crt0[1])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('got_size', crt0[2], crt0[2])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('data_sym_start', crt0[3], crt0[3])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('data_start', crt0[4], crt0[4])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('data_size', crt0[5], crt0[5])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('bss_start', crt0[6], crt0[6])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('bss_size', crt0[7], crt0[7])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('reldata_start', crt0[8], crt0[8])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('stack_size', crt0[9], crt0[9])
		out += '{:<20}: {:>8} {:>#12x}\n'.format('text_offset', crt0[10], crt0[10])

		return out

	def __str__ (self):
		out = ''
		metadata = self.parse_metadata()
		out += 'TAB: {}\n'.format(metadata['name'])
		for k,v in sorted(metadata.items()):
			if k == 'name':
				continue
			out += '  {}: {}\n'.format(k,v)
		out += '  supported architectures: {}\n'.format(', '.join(self.get_supported_architectures()))
		out += '  TBF Header\n'
		out += textwrap.indent(str(self.get_tbf_header()), '    ')
		return out
