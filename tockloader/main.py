#!/usr/bin/env python3

'''
### Main command line interface for Tockloader.

Each `tockloader` command is mapped to a function which calls the correct
tockloader class function. This file also handles discovering and reading in TAB
files.
'''

import argparse
import atexit
import binascii
import glob
import os
import subprocess
import sys
import time

import argcomplete
import crcmod

from . import helpers
from .exceptions import TockLoaderException
from .tab import TAB
from .tockloader import TockLoader
from ._version import __version__

def check_and_run_make (args):
	'''
	Checks for a Makefile, and it it exists runs `make`.
	'''

	if args.make:
		if os.path.isfile('./Makefile'):
			print('Running `make`...')
			p = subprocess.Popen(['make'])
			out, err = p.communicate()
			if p.returncode != 0:
				print('Error running make.')
				sys.exit(1)

def collect_tabs (args, wait=True):
	'''
	Load in Tock Application Bundle (TAB) files. If none are specified, this
	searches for them in subfolders.
	'''

	tab_names = args.tab

	# Check if any tab files were specified. If not, find them based
	# on where this tool is being run.
	if len(tab_names) == 0 or tab_names[0] == '':
		print('No TABs passed to tockloader. Searching for TABs in subdirectories.')

		# First check to see if things could be built that haven't been
		if os.path.isfile('./Makefile'):
			p = subprocess.Popen(['make', '-n'], stdout=subprocess.PIPE)
			out, err = p.communicate()
			# Check for the name of the compiler to see if there is work
			# to be done
			if 'arm-none-eabi-gcc' in out.decode('utf-8'):
				print('Warning! There are uncompiled changes!')
				print('You may want to run `make` before loading the application.')

		# Search for ".tab" files
		tab_names = glob.glob('./**/*.tab', recursive=True)
		if len(tab_names) == 0:
			raise TockLoaderException('No TAB files found.')

		print('Using: {}'.format(tab_names))
		if wait:
			print('Waiting one second before continuing...')
			time.sleep(1)

	# Concatenate the binaries.
	tabs = []
	for tab_name in tab_names:
		try:
			tabs.append(TAB(tab_name))
		except Exception as e:
			print('Error opening and reading "{}"'.format(tab_name))

	return tabs


def command_listen (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)
	tock_loader.run_terminal()


def command_list (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)
	tock_loader.list_apps(args.app_address, args.verbose, args.quiet)


def command_install (args):
	check_and_run_make(args)

	# Load in all TABs
	tabs = collect_tabs(args)

	# Install the apps on the board
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	# Figure out how we want to do updates
	replace = 'yes'
	if args.no_replace:
		replace = 'no'

	print('Installing apps on the board...')
	tock_loader.install(tabs, args.app_address, replace=replace, erase=args.erase)


def command_update (args):
	check_and_run_make(args)
	tabs = collect_tabs(args)

	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Updating application(s) on the board...')
	tock_loader.install(tabs, args.app_address, replace='only')


def command_uninstall (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Removing app(s) {} from board...'.format(', '.join(args.name)))
	tock_loader.uninstall_app(args.name, args.app_address, args.force)


def command_erase_apps (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Removing apps...')
	tock_loader.erase_apps(args.app_address, args.force)


def command_enable_app (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Enabling apps...')
	tock_loader.set_flag(args.name, 'enable', True, args.app_address)


def command_disable_app (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Disabling apps...')
	tock_loader.set_flag(args.name, 'enable', False, args.app_address)


def command_sticky_app (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Making apps sticky...')
	tock_loader.set_flag(args.name, 'sticky', True, args.app_address)


def command_unsticky_app (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Making apps no longer sticky...')
	tock_loader.set_flag(args.name, 'sticky', False, args.app_address)


def command_flash (args):
	check_and_run_make(args)

	# Load in all binaries
	binary = bytes()
	for binary_name in args.binary:
		# check that file isn't a `.hex` file
		if binary_name.endswith('.hex'):
			exception_string = 'Error: Cannot flash ".hex" files.'
			exception_string += ' Likely you meant to use a ".bin" file but used an intel hex file by accident.'
			raise TockLoaderException(exception_string)

		# add contents to binary
		with open(binary_name, 'rb') as f:
			binary += f.read()

	# Flash the binary to the chip
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Flashing binar(y|ies) to board...')
	tock_loader.flash_binary(binary, args.address)


def command_list_attributes (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Listing attributes...')
	tock_loader.list_attributes()


def command_set_attribute (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Setting attribute...')
	tock_loader.set_attribute(args.key, args.value)


def command_remove_attribute (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Removing attribute...')
	tock_loader.remove_attribute(args.key)


def command_info (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('tockloader version: {}'.format(__version__))
	print('Showing all properties of the board...')
	tock_loader.info(args.app_address)


def command_inspect_tab (args):
	tabs = collect_tabs(args, wait=False)

	if len(tabs) == 0:
		raise TockLoaderException('No TABs found to inspect')

	print('Inspecting TABs...')
	for tab in tabs:
		print(tab)
		print('')


def command_dump_flash_page (args):
	tock_loader = TockLoader(args)
	tock_loader.open(args)

	print('Getting page of flash...')
	tock_loader.dump_flash_page(args.page)

################################################################################
## Setup and parse command line arguments
################################################################################

def main ():
	'''
	Read in command line arguments and call the correct command function.
	'''

	# Cleanup any title the program may set
	atexit.register(helpers.set_terminal_title, '')

	# Create a common parent parser for arguments shared by all subparsers
	parent = argparse.ArgumentParser(add_help=False)

	# All commands need a serial port to talk to the board
	parent.add_argument('--port', '-p', '--device', '-d',
		help='The serial port or device name to use',
		metavar='STR')

	parent.add_argument('--make',
		action='store_true',
		help='Run `make` before loading an application')

	parent.add_argument('--debug',
		action='store_true',
		help='Print additional debugging information')

	parent.add_argument('--version',
		action='version',
		version=__version__,
		help='Print Tockloader version and exit')

	# Get the list of arguments before any command
	before_command_args = parent.parse_known_args()

	# The top-level parser object
	parser = argparse.ArgumentParser(parents=[parent])

	# Parser for all app related commands
	parent_apps = argparse.ArgumentParser(add_help=False)
	parent_apps.add_argument('--app-address', '-a',
		help='Address where apps are located',
		type=lambda x: int(x, 0),
		default=0x30000)
	parent_apps.add_argument('--force',
		help='Allow apps on boards that are not listed as compatible',
		action='store_true')

	# Parser for most commands
	parent_jtag = argparse.ArgumentParser(add_help=False)
	parent_jtag.add_argument('--jtag',
		action='store_true',
		help='Use JTAG and JLinkExe to flash.')
	parent_jtag.add_argument('--jtag-device',
		default='cortex-m0',
		help='The device type to pass to JLinkExe. Useful for initial commissioning.')
	parent_jtag.add_argument('--board',
		default=None,
		help='Explicitly specify the board that is being targeted.')
	parent_jtag.add_argument('--arch',
		default=None,
		help='Explicitly specify the architecture of the board that is being targeted.')
	parent_jtag.add_argument('--baud-rate',
		default=600000,
		type=int,
		help='If using serial, set the target baud rate.')

	# Support multiple commands for this tool
	subparser = parser.add_subparsers(
		title='Commands',
		metavar='')

	listen = subparser.add_parser('listen',
		parents=[parent],
		help='Open a terminal to receive UART data')
	listen.add_argument('--wait-to-listen',
		help='Wait until contacted on server socket to actually listen',
		action='store_true')
	listen.set_defaults(func=command_listen)

	listcmd = subparser.add_parser('list',
		parents=[parent, parent_apps, parent_jtag],
		help='List the apps installed on the board')
	listcmd.set_defaults(func=command_list)
	listcmd.add_argument('--verbose', '-v',
		help='Print more information',
		action='store_true')
	listcmd.add_argument('--quiet', '-q',
		help='Print just a list of application names',
		action='store_true')

	install = subparser.add_parser('install',
		parents=[parent, parent_apps, parent_jtag],
		help='Install apps on the board')
	install.set_defaults(func=command_install)
	install.add_argument('tab',
		help='The TAB or TABs to install',
		nargs='*')
	install.add_argument('--no-replace',
		help='Install apps again even if they are already there',
		action='store_true')
	install.add_argument('--erase',
		help='Erase all existing apps before installing.',
		action='store_true')

	update = subparser.add_parser('update',
		parents=[parent, parent_apps, parent_jtag],
		help='Update an existing app with this version')
	update.set_defaults(func=command_update)
	update.add_argument('tab',
		help='The TAB or TABs to replace',
		nargs='*')

	uninstall = subparser.add_parser('uninstall',
		parents=[parent, parent_apps, parent_jtag],
		help='Remove an already flashed app')
	uninstall.set_defaults(func=command_uninstall)
	uninstall.add_argument('name',
		help='The name of the app(s) to remove',
		nargs='*')

	eraseapps = subparser.add_parser('erase-apps',
		parents=[parent, parent_apps, parent_jtag],
		help='Delete apps from the board')
	eraseapps.set_defaults(func=command_erase_apps)

	enableapp = subparser.add_parser('enable-app',
		parents=[parent, parent_apps, parent_jtag],
		help='Enable an app so the kernel runs it')
	enableapp.set_defaults(func=command_enable_app)
	enableapp.add_argument('name',
		help='The name of the app(s) to enable',
		nargs='*')

	disableapp = subparser.add_parser('disable-app',
		parents=[parent, parent_apps, parent_jtag],
		help='Disable an app so it will not be started')
	disableapp.set_defaults(func=command_disable_app)
	disableapp.add_argument('name',
		help='The name of the app(s) to disable',
		nargs='*')

	stickyapp = subparser.add_parser('sticky-app',
		parents=[parent, parent_apps, parent_jtag],
		help='Make an app sticky so it is hard to erase')
	stickyapp.set_defaults(func=command_sticky_app)
	stickyapp.add_argument('name',
		help='The name of the app(s) to sticky',
		nargs='*')

	unstickyapp = subparser.add_parser('unsticky-app',
		parents=[parent, parent_apps, parent_jtag],
		help='Make an app unsticky (the normal setting)')
	unstickyapp.set_defaults(func=command_unsticky_app)
	unstickyapp.add_argument('name',
		help='The name of the app(s) to unsticky',
		nargs='*')

	flash = subparser.add_parser('flash',
		parents=[parent, parent_jtag],
		help='Flash binaries to the chip')
	flash.set_defaults(func=command_flash)
	flash.add_argument('binary',
		help='The binary file or files to flash to the chip',
		nargs='+')
	flash.add_argument('--address', '-a',
		help='Address to flash the binary at',
		type=lambda x: int(x, 0),
		default=0x30000)

	listattributes = subparser.add_parser('list-attributes',
		parents=[parent, parent_jtag],
		help='List attributes stored on the board')
	listattributes.set_defaults(func=command_list_attributes)

	setattribute = subparser.add_parser('set-attribute',
		parents=[parent, parent_jtag],
		help='Store attribute on the board')
	setattribute.set_defaults(func=command_set_attribute)
	setattribute.add_argument('key',
		help='Attribute key')
	setattribute.add_argument('value',
		help='Attribute value')

	removeattribute = subparser.add_parser('remove-attribute',
		parents=[parent, parent_jtag],
		help='Remove attribute from the board')
	removeattribute.set_defaults(func=command_remove_attribute)
	removeattribute.add_argument('key',
		help='Attribute key')

	info = subparser.add_parser('info',
		parents=[parent, parent_apps, parent_jtag],
		help='Verbose information about the connected board')
	info.set_defaults(func=command_info)

	inspect_tab = subparser.add_parser('inspect-tab',
		parents=[parent],
		help='Get details about a TAB')
	inspect_tab.set_defaults(func=command_inspect_tab)
	inspect_tab.add_argument('tab',
		help='The TAB or TABs to inspect',
		nargs='*')

	dump_flash_page = subparser.add_parser('dump-flash-page',
		parents=[parent, parent_jtag],
		help='Read a page of flash from the board')
	dump_flash_page.set_defaults(func=command_dump_flash_page)
	dump_flash_page.add_argument('page',
		help='The number of the page to read',
		type=int)

	argcomplete.autocomplete(parser)
	args = parser.parse_args()

	# Concat the args before the command with those that were specified
	# after the command. This is a workaround because for some reason python
	# won't parse a set of parent options before the "command" option
	# (or it is getting overwritten).
	for key,value in vars(before_command_args[0]).items():
		if getattr(args, key) == None and value != None:
			setattr(args, key, value)

	if hasattr(args, 'func'):
		try:
			args.func(args)
		except TockLoaderException as e:
			print(e)
			sys.exit(1)
	else:
		print('Missing Command.\n')
		parser.print_help()
		sys.exit(1)


if __name__ == '__main__':
	main()
