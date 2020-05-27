import argparse
import logging
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
	def __init__ (self, tab_path, args=argparse.Namespace()):
		self.args = args

		if os.path.exists(tab_path):
			# Fetch it from the local filesystem.
			self.tab = tarfile.open(tab_path)
		else:
			try:
				# Otherwise download it as a URL.
				with urllib.request.urlopen(tab_path) as response:
					tmp_file = tempfile.TemporaryFile()
					# Copy the downloaded response to our temporary file.
					shutil.copyfileobj(response, tmp_file)
					# Need to seek to the beginning of the file for tarfile
					# to work.
					tmp_file.seek(0)
					self.tab = tarfile.open(fileobj=tmp_file)
			except Exception as e:
				if self.args.debug:
					logging.error('Could not download .tab file. This may have happened because:')
					logging.error('  - An HTTPS connection could not be established.')
					logging.error('  - A temporary file could not be created.')
					logging.error('  - Untarring the TAB failed.')
					logging.error('Exception: {}'.format(e))
				raise TockLoaderException('Could not download .tab file.')

	def extract_app (self, arch):
		'''
		Return an `App` object from this TAB. You must specify the desired
		MCU architecture so the correct binary can be retrieved.
		'''
		try:
			binary_tarinfo = self.tab.getmember('{}.tbf'.format(arch))
		except Exception:
			try:
				binary_tarinfo = self.tab.getmember('{}.bin'.format(arch))
			except Exception:
				raise TockLoaderException('Could not find arch "{}" in TAB file.'.format(arch))
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

			return App(tbfh, None, name, binary[tbfh.get_header_size():])
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

	def get_tbf_names (self):
		'''
		Returns a list of the names of all of the .tbf files contained in the
		TAB, without the extension.
		'''
		tbfs = []
		for f in self.tab.getnames():
			if f[-4:] == '.tbf':
				tbfs.append(f[:-4])
		return tbfs

	def __str__ (self):
		out = ''
		metadata = self.parse_metadata()
		out += 'TAB: {}\n'.format(metadata['name'])
		for k,v in sorted(metadata.items()):
			if k == 'name':
				continue
			out += '  {}: {}\n'.format(k,v)
		out += '  included architectures: {}\n'.format(', '.join(self.get_supported_architectures()))
		return out
