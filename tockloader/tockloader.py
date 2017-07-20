'''
Main Tockloader interface.

All high-level logic is contained here. All board-specific or communication
channel specific code is in other files.
'''

import binascii
import contextlib
import copy
import string
import textwrap
import time

from . import helpers
from .app import App
from .bootloader_serial import BootloaderSerial
from .exceptions import TockLoaderException
from .tbfh import TBFHeader
from .jlinkexe import JLinkExe

class TockLoader:
	'''
	Implement all Tockloader commands. All logic for how apps are arranged
	is contained here.
	'''

	def __init__ (self, args):
		self.args = args

		# Get an object that allows talking to the board
		if hasattr(self.args, 'jtag') and self.args.jtag:
			self.channel = JLinkExe(args)
		else:
			self.channel = BootloaderSerial(args)


	def open (self, args):
		'''
		Open the correct channel to talk to the board.

		For the bootloader, this means opening a serial port. For JTAG, not much
		needs to be done.
		'''
		self.channel.open_link_to_board()


	def flash_binary (self, binary, address):
		'''
		Tell the bootloader to save the binary blob to an address in internal
		flash.

		This will pad the binary as needed, so don't worry about the binary
		being a certain length.
		'''
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():
			self.channel.flash_binary(address, binary)


	def run_terminal (self):
		'''
		Create an interactive terminal session with the board.
		'''
		self.channel.run_terminal()


	def list_apps (self, address, verbose, quiet):
		'''
		Query the chip's flash to determine which apps are installed.
		'''
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Get all apps based on their header
			apps = self._extract_all_app_headers(address)

			self._print_apps(apps, verbose, quiet)


	def install (self, tabs, address, replace='yes', erase=False):
		'''
		Add or update TABs on the board.

		- `replace` can be either "yes", "no", or "only"
		- `erase` if true means erase all other apps before installing
		'''
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Start with the apps we are searching for.
			replacement_apps = self._extract_apps_from_tabs(tabs)

			# Get a list of installed apps
			existing_apps = self._extract_all_app_headers(address)

			# What apps we want after this command completes
			resulting_apps = []

			# Whether we actually made a change or not
			changed = False

			# If we want to erase first, loop through looking for non sticky
			# apps and remove them from the existing app list.
			if erase:
				new_existing_apps = []
				for existing_app in existing_apps:
					if existing_app.is_sticky():
						new_existing_apps.append(existing_app)
				if len(existing_apps) != len(new_existing_apps):
					changed = True
				existing_apps = new_existing_apps

			# Check to see if this app is in there
			if replace == 'yes' or replace == 'only':
				for existing_app in existing_apps:
					for replacement_app in replacement_apps:
						if existing_app.name == replacement_app.name:
							resulting_apps.append(copy.deepcopy(replacement_app))
							changed = True
							break
					else:
						# We did not find a replacement app. That means we want
						# to keep the original.
						resulting_apps.append(existing_app)

				# Now, if we want a true install, and not an update, make sure
				# we add all apps that did not find a replacement on the board.
				if replace == 'yes':
					for replacement_app in replacement_apps:
						for resulting_app in resulting_apps:
							if replacement_app.name == resulting_app.name:
								break
						else:
							# We did not find the name in the resulting apps.
							# Add it.
							resulting_apps.append(replacement_app)
							changed = True

			elif replace == 'no':
				# Just add the apps
				resulting_apps = existing_apps + replacement_apps
				changed = True

			if changed:
				# Since something is now different, update all of the apps
				self._reshuffle_apps(address, resulting_apps)
			else:
				# Nothing changed, so we can raise an error
				raise TockLoaderException('Nothing found to update')


	def uninstall_app (self, app_names, address, force=False):
		'''
		If an app by this name exists, remove it from the chip. If no name is
		given, present the user with a list of apps to remove.
		'''
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Get a list of installed apps
			apps = self._extract_all_app_headers(address)

			# If the user didn't specify an app list...
			if len(app_names) == 0:
				if len(apps) == 0:
					raise TockLoaderException('No apps are installed on the board')
				elif len(apps) == 1:
					# If there's only one app, delete it
					app_names = [apps[0].name]
					print('Only one app on board. Uninstalling {}'.format(apps[0]))
				else:
					print('There are multiple apps currently on the board:')
					options = ['** Delete all']
					options.extend([app.name for app in apps])
					name = helpers.menu(options,
							return_type='value',
							prompt='Select app to uninstall ')
					if name == '** Delete all':
						app_names = [app.name for app in apps]
					else:
						app_names = [name]

			# Remove the apps if they are there
			removed = False
			keep_apps = []
			for app in apps:
				# Only keep apps that are not marked for uninstall or that
				# are sticky (unless force was set)
				if app.name not in app_names or (app.is_sticky() and not force):
					keep_apps.append(app)
				else:
					removed = True

			# Tell the user if we are not removing certain apps because they
			# are sticky.
			if not force:
				for app in apps:
					if app.name in app_names and app.is_sticky():
						print('INFO: Not removing app "{}" because it is sticky.'.format(app))

			# Now take the remaining apps and make sure they
			# are on the board properly.
			self._reshuffle_apps(address, keep_apps)

			print('Uninstall complete.')

			# And let the user know the state of the world now that we're done
			apps = self._extract_all_app_headers(address)
			if len(apps):
				print('Remaining apps on board:')
				self._print_apps(apps, verbose=False, quiet=True)
			else:
				print('No apps on board.')

			if not removed:
				raise TockLoaderException('Could not find any apps on the board to remove.')


	def erase_apps (self, address, force=False):
		'''
		Erase flash where apps go. All apps are not actually cleared, we just
		overwrite the header of the first app.
		'''
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# On force we can just eliminate all apps
			if force:
				# Erase the first page where apps go. This will cause the first
				# header to be invalid and effectively removes all apps.
				self.channel.erase_page(address)

			else:
				# Get a list of installed apps
				apps = self._extract_all_app_headers(address)

				keep_apps = []
				for app in apps:
					if app.is_sticky():
						keep_apps.append(app)
						print('INFO: Not erasing app "{}" because it is sticky.'.format(app))

				if len(keep_apps) == 0:
					self.channel.erase_page(address)
				else:
					self._reshuffle_apps(address, keep_apps)


	def set_flag (self, app_names, flag_name, flag_value, address):
		'''
		Set a flag in the TBF header.
		'''
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Get a list of installed apps
			apps = self._extract_all_app_headers(address)

			if len(apps) == 0:
				raise TockLoaderException('No apps are installed on the board')

			# User did not specify apps. Pick from list.
			if len(app_names) == 0:
				print('Which apps to configure?')
				options = ['** All']
				options.extend([app.name for app in apps])
				name = helpers.menu(options,
						return_type='value',
						prompt='Select app to configure ')
				if name == '** All':
					app_names = [app.name for app in apps]
				else:
					app_names = [name]

			# Configure all selected apps
			changed = False
			for app in apps:
				if app.name in app_names:
					app.tbfh.set_flag(flag_name, flag_value)
					changed = True

			if changed:
				self._reflash_app_headers(apps)
			else:
				print('No matching apps found. Nothing changed.')


	def list_attributes (self):
		'''
		Download all attributes stored on the board.
		'''
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			if not self._bootloader_is_present():
				raise TockLoaderException('No bootloader found! That means there is nowhere for attributes to go.')

			self._print_attributes(self.channel.get_all_attributes())


	def set_attribute (self, key, value):
		'''
		Download all attributes stored on the board.
		'''
		# Do some checking
		if len(key.encode('utf-8')) > 8:
			raise TockLoaderException('Key is too long. Must be 8 bytes or fewer.')
		if len(value.encode('utf-8')) > 55:
			raise TockLoaderException('Value is too long. Must be 55 bytes or fewer.')

		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			if not self._bootloader_is_present():
				raise TockLoaderException('No bootloader found! That means there is nowhere for attributes to go.')

			# Create the buffer to write as the attribute
			out = bytes([])
			# Add key
			out += key.encode('utf-8')
			out += bytes([0] * (8-len(out)))
			# Add length
			out += bytes([len(value.encode('utf-8'))])
			# Add value
			out += value.encode('utf-8')

			# Find if this attribute key already exists
			open_index = -1
			for index, attribute in enumerate(self.channel.get_all_attributes()):
				if attribute:
					if attribute['key'] == key:
						print('Found existing key at slot {}. Overwriting.'.format(index))
						self.channel.set_attribute(index, out)
						break
				else:
					# Save where we should put this attribute if it does not
					# already exist.
					if open_index == -1:
						open_index = index
			else:
				if open_index == -1:
					raise TockLoaderException('Error: No open space to save this attribute.')
				else:
					print('Key not found. Writing new attribute to slot {}'.format(open_index))
					self.channel.set_attribute(open_index, out)


	def remove_attribute (self, key):
		'''
		Remove an existing attribute already stored on the board.
		'''
		# Do some checking
		if len(key.encode('utf-8')) > 8:
			raise TockLoaderException('Key is too long. Must be 8 bytes or fewer.')

		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			if not self._bootloader_is_present():
				raise TockLoaderException('No bootloader found! That means there is nowhere for attributes to go.')

			# Create a null buffer to overwrite with
			out = bytes([0]*9)

			# Find if this attribute key already exists
			for index, attribute in enumerate(self.channel.get_all_attributes()):
				if attribute and attribute['key'] == key:
					print('Found existing key at slot {}. Removing.'.format(index))
					self.channel.set_attribute(index, out)
					break
			else:
				raise TockLoaderException('Error: Attribute does not exist.')


	def info (self, app_address):
		'''
		Print all info about this board.
		'''
		# Enter bootloader mode to get things started
		with self._start_communication_with_board():

			# Print all apps
			print('Apps:')
			apps = self._extract_all_app_headers(app_address)
			self._print_apps(apps, True, False)

			if self._bootloader_is_present():
				# Print all attributes
				print('Attributes:')
				attributes = self.channel.get_all_attributes()
				self._print_attributes(attributes)
				print('')

				# Show bootloader version
				version = self.channel.get_bootloader_version()
				if version == None:
					version = 'unknown'
				print('Bootloader version: {}'.format(version))
			else:
				print('No bootloader.')


	def dump_flash_page (self, page_num):
		'''
		Print one page of flash contents.
		'''
		with self._start_communication_with_board():
			address = 512 * page_num
			print('Page number: {} ({:#08x})'.format(page_num, address))

			flash = self.channel.read_range(address, 512)

			def chunks(l, n):
				for i in range(0, len(l), n):
					yield l[i:i + n]

			def dump_line (addr, bytes):
				k = binascii.hexlify(bytes).decode('utf-8')
				b = ' '.join(list(chunks(k, 2)))
				if len(b) >= 26:
					# add middle space
					b = '{} {}'.format(b[0:24], b[24:])
				printable = string.ascii_letters + string.digits + string.punctuation + ' '
				t = ''.join([chr(i) if chr(i) in printable else '.' for i in bytes])
				print('{:08x}  {}  |{}|'.format(addr, b, t))

			for i,chunk in enumerate(chunks(flash, 16)):
				dump_line(address+(i*16), chunk)

	############################################################################
	## Internal Helper Functions for Communicating with Boards
	############################################################################

	@contextlib.contextmanager
	def _start_communication_with_board (self):
		'''
		Based on the transport method used, there may be some setup required
		to connect to the board. This function runs the setup needed to connect
		to the board. It also times the operation.

		For the bootloader, the board needs to be reset and told to enter the
		bootloader mode. For JTAG, this is unnecessary.
		'''
		# Time the operation
		then = time.time()
		try:
			self.channel.enter_bootloader_mode()

			# Now that we have connected to the board and the bootloader
			# if necessary, make sure we know what kind of board we are
			# talking to.
			self.channel.determine_current_board()

			yield

			now = time.time()
			print('Finished in {:0.3f} seconds'.format(now-then))
		except Exception as e:
			raise(e)
		finally:
			self.channel.exit_bootloader_mode()

	def _bootloader_is_present (self):
		'''
		Check if a bootloader exists on this board. It is specified by the
		string "TOCKBOOTLOADER" being at address 0x400.
		'''
		# Check to see if the channel already knows this. For example,
		# if you are connected via a serial link to the bootloader,
		# then obviously the bootloader is present.
		if self.channel.bootloader_is_present() == True:
			return True

		# Otherwise check for the bootloader flag in the flash.

		# Constants for the bootloader flag
		address = 0x400
		length = 14
		flag = self.channel.read_range(address, length)
		flag_str = flag.decode('utf-8')
		if self.args.debug:
			print('Read from flags location: {}'.format(flag_str))
		return flag_str == 'TOCKBOOTLOADER'


	############################################################################
	## Helper Functions for Manipulating Binaries and TBF
	############################################################################

	def _reshuffle_apps (self, address, apps):
		'''
		Given an array of apps, some of which are new and some of which exist,
		sort them in flash so they are in descending size order.
		'''
		# We are given an array of apps. First we need to order them by size.
		apps.sort(key=lambda app: app.get_size(), reverse=True)

		# Now iterate to see if the address has changed
		start_address = address
		for app in apps:
			# If the address already matches, then we are good.
			# On to the next app.
			if app.address != start_address:
				# If they don't, then we need to read the binary out of
				# flash and save it to be moved, as well as update the address.
				# However, we may have a new binary to use, so we don't need to
				# fetch it.
				if not app.has_binary():
					app.set_binary(self.channel.read_range(app.address, app.get_size()))

				# Either way save the new address.
				app.set_address(start_address)

			start_address += app.get_size()

		# Now flash all apps that have a binary field. The presence of the
		# binary indicates that they are new or moved.
		end = address
		for app in apps:
			if app.has_binary():
				self.channel.flash_binary(app.address, app.binary)
			end = app.address + app.get_size()

		# Then erase the next page. This ensures that flash is clean at the
		# end of the installed apps and makes things nicer for future uses of
		# this script.
		self.channel.erase_page(end)

	def _extract_all_app_headers (self, address):
		'''
		Iterate through the flash on the board for the header information about
		each app.
		'''
		apps = []

		# Jump through the linked list of apps
		while (True):
			header_length = 200 # Version 2
			flash = self.channel.read_range(address, header_length)

			# if there was an error, the binary array will be empty
			if len(flash) < header_length:
				break

			# Get all the fields from the header
			tbfh = TBFHeader(flash)

			if tbfh.is_valid():
				# Get the name out of the app.
				name_or_params = tbfh.get_app_name()
				if isinstance(name_or_params, str):
					name = name_or_params
				else:
					name = self._get_app_name(address+name_or_params[0], name_or_params[1])

				app = App(tbfh, address, name)
				apps.append(app)

				address += app.get_size()

			else:
				break

		return apps

	def _reflash_app_headers (self, apps):
		'''
		Take a list of app headers and reflash them to the chip. This doesn't do
		a lot of checking, so you better have not re-ordered the headers or
		anything annoying like that.
		'''
		for app in apps:
			if app.has_binary():
				raise TockLoaderException('App headers should not have binaries! That would imply the app has changed!')

			self.channel.flash_binary(app.address, app.get_header_binary(), pad=False)

	def _extract_apps_from_tabs (self, tabs):
		'''
		Iterate through the list of TABs and create the app dict for each.
		'''
		apps = []

		# This is the architecture we need for the board
		arch = self.channel.get_board_arch()

		for tab in tabs:
			if self.args.force or tab.is_compatible_with_board(self.channel.get_board_name()):
				apps.append(tab.extract_app(arch))

		if len(apps) == 0:
			raise TockLoaderException('No valid apps for this board were provided. Use --force to override.')

		return apps

	def _get_app_name (self, address, length):
		'''
		Retrieve bytes from the board and interpret them as a string
		'''
		if length == 0:
			return ''

		name_memory = self.channel.read_range(address, length)
		return name_memory.decode('utf-8')

	def _app_is_aligned_correctly (self, address, size):
		'''
		Check if putting an app at this address will be OK with the MPU.
		'''
		# The rule for the MPU is that the size of the protected region must be
		# a power of two, and that the region is aligned on a multiple of that
		# size.

		# Check if not power of two
		if (size & (size - 1)) != 0:
			return False

		# Check that address is a multiple of size
		multiple = address // size
		if multiple * size != address:
			return False

		return True

	############################################################################
	## Printing helper functions
	############################################################################

	def _print_apps (self, apps, verbose, quiet):
		'''
		Print information about a list of apps
		'''
		if not quiet:
			# Print info about each app
			for i,app in enumerate(apps):
				print('[App {}]'.format(i))

				# Check if this app is OK with the MPU region requirements.
				if not self._app_is_aligned_correctly(app.address, app.get_size()):
					print('  [WARNING] App is misaligned for the MPU')

				print(textwrap.indent(app.info(verbose), '  '))
				print('')

			if len(apps) == 0:
				print('No found apps.')

		else:
			# In quiet mode just show the names.
			app_names = []
			for app in apps:
				app_names.append(app.name)
			print(' '.join(app_names))

	def _print_attributes (self, attributes):
		'''
		Print the list of attributes in the bootloader.
		'''
		for index, attribute in enumerate(attributes):
			if attribute:
				print('{:02d}: {:>8} = {}'.format(index, attribute['key'], attribute['value']))
			else:
				print('{:02d}:'.format(index))
