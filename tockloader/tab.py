import tarfile
import textwrap

import pytoml

from .app import App
from .tbfh import TBFHeader

################################################################################
## Tock Application Bundle Object
################################################################################

class TAB:
	def __init__ (self, tab_name):
		self.tab = tarfile.open(tab_name)

	def extract_app (self, arch):
		binary_tarinfo = self.tab.getmember('{}.bin'.format(arch))
		binary = self.tab.extractfile(binary_tarinfo).read()

		# First get the TBF header from the correct binary in the TAB
		tbfh = TBFHeader(binary)

		if tbfh.is_valid():
			start = tbfh.fields['package_name_offset']
			end = start+tbfh.fields['package_name_size']
			name = binary[start:end].decode('utf-8')

			return App(tbfh, None, name, binary)
		else:
			raise TockLoaderException('Invalid TBF found in app in TAB')

	def is_compatible_with_board (self, board):
		metadata = self.parse_metadata()
		if metadata['tab-version'] == 1:
			return 'only-for-boards' not in metadata or \
			       board in metadata['only-for-boards'] or \
			       metadata['only-for-boards'] == ''
		else:
			raise TockLoaderException('Unable to understand version {} of metadata'.format(metadata['tab-version']))

	def parse_metadata (self):
		metadata_tarinfo = self.tab.getmember('metadata.toml')
		metadata_str = self.tab.extractfile(metadata_tarinfo).read().decode('utf-8')
		return pytoml.loads(metadata_str)

	def get_supported_architectures (self):
		contained_files = self.tab.getnames()
		return [i[:-4] for i in contained_files if i[-4:] == '.bin']

	def get_tbf_header (self):
		# Find a .bin file
		for f in self.tab.getnames():
			if f[-4:] == '.bin':
				binary_tarinfo = self.tab.getmember(f)
				binary = self.tab.extractfile(binary_tarinfo).read()

				# Get the TBF header from a binary in the TAB
				return TBFHeader(binary)
		return None

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
