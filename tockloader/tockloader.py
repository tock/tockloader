"""
Main Tockloader interface.

All high-level logic is contained here. All board-specific or communication
channel specific code is in other files.
"""

import contextlib
import copy
import ctypes
import functools
import itertools
import logging
import os
import platform
import re
import textwrap
import time

from . import helpers
from . import display
from . import flash_file
from .app_installed import InstalledApp
from .app_padding import PaddingApp
from .app_padding import InstalledPaddingApp
from .app_tab import TabApp
from .board_interface import BoardInterface
from .bootloader_serial import BootloaderSerial
from .exceptions import TockLoaderException, ChannelAddressErrorException
from .kernel_attributes import KernelAttributes
from .tbfh import TBFHeader
from .tbfh import TBFFooter
from .jlinkexe import JLinkExe
from .openocd import OpenOCD, collect_temp_files
from .probers import ProbeRs
from .stlink import STLink
from .flash_file import FlashFile
from .tickv import TockTicKV


class TockLoader:
    """
    Implement all Tockloader commands. All logic for how apps are arranged
    is contained here.
    """

    # Tockloader includes built-in settings for known Tock boards to make the
    # overall user experience easier. As new boards support Tock, board-specific
    # options can be include in the Tockloader source to make it easier for
    # users.
    #
    # There are two levels of board-specific configurations: communication
    # details and application details.
    #
    # - Communication details: These are specifics about how Tockloader should
    #   communicate with the board and what specific commands are needed to
    #   program the device.
    #
    # - Application details: These are specifics about how applications should
    #   be situated in flash for a particular board. For instance, MPU rules may
    #   dictate where an application can be placed to properly protect its
    #   memory.
    #
    # Here, we set the application details that are board specific. See
    # `board_interface.py` for the board-specific communication details.
    #
    # Settings are applied iteratively:
    #
    # 1. Default settings
    # 2. General architecture-specific settings (i.e. "cortex-m")
    # 3. Specific architecture-specific settings (i.e. "cortex-m4")
    # 4. Board-specific settings
    #
    # Options
    # -------
    # - `start_address`:   The absolute address in flash where apps start and
    #                      must be loaded.
    # - `order`:           How apps should be sorted when flashed onto the board.
    #                      Supported values: size_descending, None
    # - `size_constraint`: Valid sizes for the entire application.
    #                      Supported values: powers_of_two, (multiple, value),
    #                                        None
    # - `alignment_constraint`: If apps have to be aligned to some value.
    #                      Supported values: size, None
    # - `cmd_flags`:       A dict of command line flags and the value they
    #                      should be set to for the board.
    TOCKLOADER_APP_SETTINGS = {
        "default": {
            "start_address": 0x30000,
            "order": None,
            "size_constraint": None,
            "alignment_constraint": None,
            "cmd_flags": {},
        },
        "arch": {
            "cortex-m": {
                "order": "size_descending",
                "size_constraint": "powers_of_two",
                "alignment_constraint": "size",
            }
        },
        "boards": {
            "arty": {
                "start_address": 0x40430000,
            },
            "edu-ciaa": {
                "start_address": 0x1A040000,
                "cmd_flags": {"bundle_apps": True, "openocd": True},
            },
            "hifive1": {"start_address": 0x20430000},
            "hifive1b": {"start_address": 0x20040000},
            "litex_arty": {"start_address": 0x41000000},
            "litex_sim": {"start_address": 0x00080000},
            "veer_el2_sim": {"start_address": 0x20300000},
            "nrf52dk": {
                "start_address": 0x40000,
                "app_ram_address": 0x20008000,
                "tickv": {
                    "region_size": 4096,
                    "number_regions": 32,
                    "start_address": 0x12000000,
                },
            },
            "particle_boron": {
                "start_address": 0x40000,
            },
            "nucleof4": {"start_address": 0x08040000},
            "microbit_v2": {"start_address": 0x00040000},
            "qemu_rv32_virt": {
                "start_address": 0x80100000,
            },
            "stm32f3discovery": {"start_address": 0x08020000},
            "stm32f4discovery": {
                "start_address": 0x08040000,
                "cmd_flags": {"bundle_apps": True},
            },
            "raspberry_pi_pico": {"start_address": 0x10020000},
            "tickv": {
                "tickv": {
                    "region_size": 4096,
                    "number_regions": 3,
                    "start_address": 0,
                }
            },
            "cy8cproto_62_4343_w": {
                "start_address": 0x10100000,
            },
        },
    }

    def __init__(self, args):
        self.args = args

        # These are customized once we have a connection to the board and know
        # what board we are talking to.
        self.app_settings = self.TOCKLOADER_APP_SETTINGS["default"]

        # If the user specified a board manually, we might be able to update
        # options now, so we can try.
        self._update_board_specific_options()

    def open(self):
        """
        Select and then open the correct channel to talk to the board.

        For the bootloader, this means opening a serial port. For JTAG, not much
        needs to be done.
        """

        # Verify only one of openocd, jlink, flash file, or serial are set.
        if (
            len(
                list(
                    filter(
                        lambda a: a != False,
                        [
                            getattr(self.args, "jlink", False),
                            getattr(self.args, "openocd", False),
                            getattr(self.args, "stlink", False),
                            getattr(self.args, "flash_file") != None,
                            getattr(self.args, "serial", False),
                        ],
                    )
                )
            )
            > 1
        ):
            raise TockLoaderException(
                "Can only use one of --jlink, --openocd, --stlink, --flash-file or --serial options"
            )

        # Get an object that allows talking to the board.
        if hasattr(self.args, "jlink") and self.args.jlink:
            # User passed `--jlink`. Force the jlink channel.
            self.channel = JLinkExe(self.args)
        elif hasattr(self.args, "openocd") and self.args.openocd:
            # User passed `--openocd`. Force the OpenOCD channel.
            self.channel = OpenOCD(self.args)
        elif hasattr(self.args, "stlink") and self.args.stlink:
            # User passed `--stlink`. Force the STLink channel.
            self.channel = STLink(self.args)
        elif hasattr(self.args, "probers") and self.args.probers:
            # User passed `--probers`. Force the probe-rs channel.
            self.channel = ProbeRs(self.args)
        elif hasattr(self.args, "serial") and self.args.serial:
            # User passed `--serial`. Force the serial bootloader channel.
            self.channel = BootloaderSerial(self.args)
        elif hasattr(self.args, "local_board") and self.args.local_board:
            # User passed `--local-board` option. Force operation on the
            # specified file.
            self.channel = FlashFile(self.args)
        elif hasattr(self.args, "flash_file") and self.args.flash_file is not None:
            # User passed `--flash-file` option with an associated file. Force
            # operation on the specified file.
            self.channel = FlashFile(self.args)
        else:
            # Try to do some magic to determine the correct channel to use. Our
            # goal is to automatically choose the correct setting so that
            # `tockloader` just works without having to specify a board and any
            # flags.

            # Loop so we can `break`. This will never execute more than once.
            while True:
                # One issue is that JTAG connections often expose both a JTAG
                # and a serial port. So, if we try to use the serial port first
                # we will incorrectly detect that serial port. So, we start with
                # the less likely jtag channel. We start with jlinkexe because
                # it has been in tockloader longer. Let me know if this is the
                # wrong decision.
                jlink_channel = JLinkExe(self.args)
                if jlink_channel.attached_board_exists():
                    self.channel = jlink_channel
                    logging.info("Using jlink channel to communicate with the board.")
                    break

                # Next try openocd.
                openocd_channel = OpenOCD(self.args)
                if openocd_channel.attached_board_exists():
                    self.channel = openocd_channel
                    logging.info("Using openocd channel to communicate with the board.")
                    break

                # Next try st-link.
                stlink_channel = STLink(self.args)
                if stlink_channel.attached_board_exists():
                    self.channel = stlink_channel
                    logging.info("Using stlink channel to communicate with the board.")
                    break

                # Try using the serial bootloader. Traditionally, we have
                # defaulted to this, and if there is a reasonable serial port we
                # still will, but we no longer unconditionally default to this.
                # The number of tock boards in frequent use that use the serial
                # bootloader has decreased.
                serial_channel = BootloaderSerial(self.args)
                if serial_channel.attached_board_exists():
                    self.channel = serial_channel
                    logging.info("Using serial channel to communicate with the board.")
                    break

                flash_file_channel = FlashFile(self.args)
                if flash_file_channel.attached_board_exists():
                    self.channel = flash_file_channel
                    logging.info("Using flash-file to communicate with the board.")
                    break

                # If we get here we were unable to connect to a board and a
                # specific instruction was not given to us. We offer to use a
                # simulated flash-file board.
                logging.info("No connected board detected.")
                use_sim_board = helpers.menu_new_yes_no(
                    prompt="Would you like to use a local simulated board?",
                )
                if use_sim_board:
                    logging.info(
                        "Using simulated board file 'tock_simulated_board.bin'"
                    )
                    if not hasattr(self.args, "arch") or self.args.arch == None:
                        logging.info("Using default arch of 'cortex-m4'")
                        self.args.arch = "cortex-m4"
                    self.args.flash_file = "tock_simulated_board.bin"
                    self.channel = FlashFile(self.args)
                else:
                    raise TockLoaderException("No connected board found.")

                # Exit while(1) loop, do not remove this break!
                break

        # And make sure the channel is open (e.g. open a serial port).
        self.channel.open_link_to_board()

    def flash_binary(self, binary, address, pad=None):
        """
        Tell the bootloader to save the binary blob to an address in internal
        flash.

        This will pad the binary as needed, so don't worry about the binary
        being a certain length.

        This accepts an optional `pad` parameter. If used, the `pad` parameter
        is a tuple of `(length, value)` signifying the number of bytes to pad,
        and the particular byte to use for the padding.
        """
        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            # Check if we should add padding, which is just pad[0] copies of the
            # same byte (pad[1]).
            if pad:
                extra = bytes([pad[1]] * pad[0])
                binary = binary + extra

            self.channel.flash_binary(address, binary)

            # Flash command can optionally set attributes.
            if self.args.set_attribute != None:
                for k, v in self.args.set_attribute:
                    logging.debug("Setting attribute {}={}".format(k, v))
                    ret = self._set_attribute(k, v, log_status=False)

                    if ret:
                        logging.debug("Unable to set attribute after flash command.")
                        logging.debug(ret)

    def list_apps(self, verbose, quiet, map, verify_credentials_public_keys):
        """
        Query the chip's flash to determine which apps are installed.

        - `verbose` - bool: Show details about TBF.
        - `quiet` - bool: Just show the app name.
        - `map` - bool: Show a diagram listing apps with addresses.
        - `verify_credentials_public_keys`: Either `None`, meaning do not verify
          any credentials, or a list of public keys binaries to use to help
          verify credentials. The list can be empty and all credentials that can
          be checked without keys will be verified.
        """
        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            # Only get the entire app to verify credentials if requested.
            extract_app_binary = False
            if not verify_credentials_public_keys == None:
                extract_app_binary = True
                # Need to force verbose mode to actually show the result.
                verbose = True

            # Get all apps based on their header
            apps = self._extract_all_app_headers(verbose, extract_app_binary)

            if not verify_credentials_public_keys == None:
                for app in apps:
                    app.verify_credentials(verify_credentials_public_keys)

            if self.args.output_format == "json":
                displayer = display.JSONDisplay()
            else:
                displayer = display.HumanReadableDisplay()

            if map:
                displayer.show_app_map_actual_address(apps)
            else:
                displayer.list_apps(apps, verbose, quiet)

            print(displayer.get())

    def install(self, tabs, replace="yes", erase=False, sticky=False, layout=None):
        """
        Add or update TABs on the board.

        - `replace` can be "yes", "no", or "only"
        - `erase` if true means erase all other apps before installing
        - `layout` is a layout string for specifying how apps should be installed
        """
        # Check if we have any apps to install. If not, then we can quit early.
        if len(tabs) == 0:
            raise TockLoaderException("No TABs to install")

        # Check for the `--preserve-order` flag that `--erase` was also specified.
        # We don't know

        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            # This is the architecture we need for the board.
            arch = self.channel.get_board_arch()
            if arch == None:
                raise TockLoaderException(
                    "Need known arch to install apps. Perhaps use `--arch` flag."
                )

            # Check if a specific layout was specified. If so, we don't want to
            # use any app layout helpers (e.g. alignment and size requirements).
            # We set this early because we don't want the TAB apps to be
            # modified based on these settings.
            if layout:
                logging.info(
                    "Layout specified, disabling any app size or alignment constraints."
                )
                self.app_settings["size_constraint"] = None
                self.app_settings["alignment_constraint"] = None

            # Start with the apps we are searching for.
            replacement_apps = self._extract_apps_from_tabs(tabs, arch)

            # What apps we want after this command completes
            resulting_apps = []

            # Check if the user specified a very specific layout for installed
            # apps. This is probably not for normal operation but for testing.
            # In this case, we force --erase and --force, ignore anything
            # already installed, and just setup the layout as specified.
            if layout:
                m = re.findall(r"(T)?(p[0-9]+)?", layout)
                layout_items = list(filter(lambda x: len(x) > 0, itertools.chain(*m)))

                # Debugging output
                display_items = []
                for l in layout_items:
                    if l[0] == "T":
                        display_items.append("TBF")
                    elif l[0] == "p":
                        padding_size = int(l[1:])
                        display_items.append(f"PaddingApp {padding_size} bytes")
                display_str = ", ".join(display_items)
                logging.info(f"Using layout: {display_str}")

                app_index = 0
                for l in layout_items:
                    if l[0] == "T":
                        if len(replacement_apps) <= app_index:
                            logging.error(
                                f"Insufficient TABs specified for layout: {layout}"
                            )
                            raise TockLoaderException("Cannot install specified layout")
                        resulting_apps.append(replacement_apps[app_index])
                        app_index += 1
                    elif l[0] == "p":
                        padding_size = int(l[1:])
                        resulting_apps.append(PaddingApp(padding_size))

                self._reshuffle_apps(resulting_apps, preserve_order=True)
                return

            # If we want to install these as sticky apps, mark that now.
            if sticky:
                logging.info("Marking apps as sticky.")
                for app in replacement_apps:
                    app.set_sticky()

            # Get a list of installed apps
            existing_apps = self._extract_all_app_headers()

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
            if replace == "yes" or replace == "only":
                for existing_app in existing_apps:
                    for replacement_app in replacement_apps:
                        if existing_app.get_name() == replacement_app.get_name():
                            resulting_apps.append(copy.deepcopy(replacement_app))
                            changed = True
                            break
                    else:
                        # We did not find a replacement app. That means we want
                        # to keep the original.
                        resulting_apps.append(existing_app)

                # Now, if we want a true install, and not an update, make sure
                # we add all apps that did not find a replacement on the board.
                if replace == "yes":
                    for replacement_app in replacement_apps:
                        for resulting_app in resulting_apps:
                            if replacement_app.get_name() == resulting_app.get_name():
                                break
                        else:
                            # We did not find the name in the resulting apps.
                            # Add it.
                            resulting_apps.append(replacement_app)
                            changed = True

            elif replace == "no":
                # Just add the apps
                resulting_apps = existing_apps + replacement_apps
                changed = True

            if changed:
                # Since something is now different, update all of the apps
                self._reshuffle_apps(
                    resulting_apps, preserve_order=self.args.preserve_order
                )
            else:
                # Nothing changed, so we can raise an error
                raise TockLoaderException("Nothing found to update")

    def uninstall_app(self, app_names):
        """
        If an app by this name exists, remove it from the chip. If no name is
        given, present the user with a list of apps to remove.
        """
        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            # Get a list of installed apps
            apps = self._extract_all_app_headers()

            # Candidate apps to remove.
            candidate_apps = []

            # If the user didn't specify an app list...
            if len(app_names) == 0:
                if len(apps) == 0:
                    raise TockLoaderException("No apps are installed on the board")
                elif len(apps) == 1:
                    # If there's only one app, delete it
                    candidate_apps = apps
                    logging.info("Only one app on board.")
                else:
                    options = ["** Delete all"]
                    options.extend([app.get_name() for app in apps])
                    app_indices = helpers.menu_multiple_indices(
                        options, prompt="Select app to uninstall "
                    )

                    if 0 in app_indices:
                        # Delete all
                        candidate_apps = apps
                    else:
                        for app_index in app_indices:
                            candidate_apps.append(apps[app_index - 1])
            else:
                # User did specify an app list.
                for app in apps:
                    if app.get_name() in app_names:
                        candidate_apps.append(app)

            logging.status("Attempting to uninstall:")
            for app in candidate_apps:
                logging.status("  - {}".format(app.get_name()))

            #
            # Uninstall apps by replacing their TBF header with one that is just
            # padding for the same total size.
            #

            # Get a list of apps to remove respecting the sticky bit.
            remove_apps = []
            for app in candidate_apps:
                # Only remove apps that are marked for uninstall, unless they
                # are sticky without force being set.
                if app.is_sticky():
                    if self.args.force:
                        logging.info(
                            'Removing sticky app "{}" because --force was used.'.format(
                                app
                            )
                        )
                        remove_apps.append(app)
                    else:
                        logging.info(
                            'Not removing app "{}" because it is sticky.'.format(app)
                        )
                        logging.info(
                            "To remove this you need to include the --force option."
                        )
                else:
                    # Normal uninstall
                    remove_apps.append(app)

            if len(remove_apps) > 0:
                # Uninstall apps by replacing them all with padding.
                for remove_app in remove_apps:
                    self._replace_with_padding(remove_app)

                logging.status("Uninstall complete.")

                if self.args.debug:
                    # And let the user know the state of the world now that we're done
                    apps = self._extract_all_app_headers()
                    if len(apps):
                        app_names = ", ".join(map(lambda x: x.get_name(), apps))
                        logging.info(
                            "After uninstall, remaining apps on board: {}".format(
                                app_names
                            )
                        )
                    else:
                        logging.info("After uninstall, no apps on board.")

            else:
                raise TockLoaderException(
                    "Could not find any apps on the board to uninstall."
                )

    def erase_apps(self):
        """
        Erase flash where apps go. All apps are not actually cleared, we just
        overwrite the header of the first app.
        """
        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            # On force we can just eliminate all apps
            if self.args.force:
                # Erase the first page where apps go. This will cause the first
                # header to be invalid and effectively removes all apps.
                address = self._get_apps_start_address()
                self.channel.clear_bytes(address)

            else:
                # Get a list of installed apps
                apps = self._extract_all_app_headers()

                keep_apps = []
                for app in apps:
                    if app.is_sticky():
                        keep_apps.append(app)
                        logging.info(
                            'Not erasing app "{}" because it is sticky.'.format(app)
                        )

                if len(keep_apps) == 0:
                    address = self._get_apps_start_address()
                    self.channel.clear_bytes(address)

                    logging.info("All apps have been erased.")
                else:
                    self._reshuffle_apps(keep_apps)

                    logging.info("After erasing apps, remaining apps on board: ")
                    self._print_apps(apps, verbose=False, quiet=True)

    def set_flag(self, app_names, flag_name, flag_value):
        """
        Set a flag in the TBF header.
        """
        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            # Get a list of installed apps
            apps = self._extract_all_app_headers()

            if len(apps) == 0:
                raise TockLoaderException("No apps are installed on the board")

            # User did not specify apps. Pick from list.
            if len(app_names) == 0:
                options = ["** All"]
                options.extend([app.get_name() for app in apps])
                name = helpers.menu(
                    options,
                    return_type="value",
                    prompt="Select app to configure ",
                    title="Which apps to configure?",
                )
                if name == "** All":
                    app_names = [app.get_name() for app in apps]
                else:
                    app_names = [name]

            # Configure all selected apps
            changed = False
            for app in apps:
                if app.get_name() in app_names:
                    app.get_header().set_flag(flag_name, flag_value)
                    changed = True

            if changed:
                self._reshuffle_apps(apps)
                logging.info(
                    'Set flag "{}" to "{}" for apps: {}'.format(
                        flag_name, flag_value, ", ".join(app_names)
                    )
                )
            else:
                logging.info("No matching apps found. Nothing changed.")

    def list_attributes(self):
        """
        Download all attributes stored on the board.
        """
        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            if not self._bootloader_is_present():
                raise TockLoaderException(
                    "No bootloader found! That means there is nowhere for attributes to go."
                )

            attributes = self.channel.get_all_attributes()

            if self.args.output_format == "json":
                displayer = display.JSONDisplay()
            else:
                displayer = display.HumanReadableDisplay()

            displayer.list_attributes(attributes)
            print(displayer.get())

    def set_attribute(self, key, value):
        """
        Change an attribute stored on the board.
        """

        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            # Use helper function to do all of the work.
            ret = self._set_attribute(key, value)

            if ret:
                # Some error occurred!
                raise TockLoaderException(ret)

    def remove_attribute(self, key):
        """
        Remove an existing attribute already stored on the board.
        """
        # Do some checking
        if len(key.encode("utf-8")) > 8:
            raise TockLoaderException("Key is too long. Must be 8 bytes or fewer.")

        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            if not self._bootloader_is_present():
                raise TockLoaderException(
                    "No bootloader found! That means there is nowhere for attributes to go."
                )

            # Create a null buffer to overwrite with
            out = bytes([0] * 9)

            # Find if this attribute key already exists
            for index, attribute in enumerate(self.channel.get_all_attributes()):
                if attribute and attribute["key"] == key:
                    logging.status(
                        "Found existing key at slot {}. Removing.".format(index)
                    )
                    self.channel.set_attribute(index, out)
                    break
            else:
                raise TockLoaderException("Error: Attribute does not exist.")

    def set_start_address(self, address):
        """
        Set the address that the bootloader jumps to to run kernel code.
        """

        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            if not self._bootloader_is_present():
                raise TockLoaderException(
                    "No bootloader found! That means there is nowhere for attributes to go."
                )

            self.channel.set_start_address(address)

    def info(self):
        """
        Print all info about this board.
        """
        # Enter bootloader mode to get things started
        with self._start_communication_with_board():
            if self.args.output_format == "json":
                displayer = display.JSONDisplay()
            elif self.args.output_format == "visual":
                displayer = display.VisualDisplay()
            else:
                displayer = display.HumanReadableDisplay(show_headers=True)

            # Print all apps
            apps = self._extract_all_app_headers()
            displayer.list_apps(apps, True, False)

            if self._bootloader_is_present():
                # Print all attributes
                attributes = self.channel.get_all_attributes()
                displayer.list_attributes(attributes)

                # Show bootloader version
                version = self.channel.get_bootloader_version()
                if version == None:
                    version = "unknown"
                displayer.bootloader_version(version)

            # Try to show kernel attributes
            app_start_flash = self._get_apps_start_address()
            kernel_attr_binary = self.channel.read_range(app_start_flash - 100, 100)
            kernel_attrs = KernelAttributes(kernel_attr_binary, app_start_flash)
            displayer.kernel_attributes(kernel_attrs)

            print(displayer.get())

    def dump_flash_page(self, page_num):
        """
        Print one page of flash contents.
        """
        with self._start_communication_with_board():
            page_size = self.channel.get_page_size()
            address = page_size * page_num
            print("Page number: {} ({:#08x})".format(page_num, address))

            try:
                flash = self.channel.read_range(address, page_size)
            except ChannelAddressErrorException:
                try:
                    from .nrfjprog import nrfjprog
                except:
                    logging.error("Unable to use backup nrfjprog channel")
                    logging.error("You may need to `pip install pynrfjprog`")
                    raise TockLoaderException("Unable to use nrfjprog backup channel")

                self.args.board = self.channel.get_board_name()
                backup_channel = nrfjprog(self.args)
                backup_channel.open_link_to_board()
                flash = backup_channel.read_range(address, page_size)

            print(helpers.print_flash(address, flash))

    def read_flash(self, address, length):
        """
        Print some flash contents.
        """
        with self._start_communication_with_board():
            try:
                flash = self.channel.read_range(address, length)
            except ChannelAddressErrorException:
                try:
                    from .nrfjprog import nrfjprog
                except:
                    logging.error("Unable to use backup nrfjprog channel")
                    logging.error("You may need to `pip install pynrfjprog`")
                    raise TockLoaderException("Unable to use nrfjprog backup channel")

                self.args.board = self.channel.get_board_name()
                backup_channel = nrfjprog(self.args)
                backup_channel.open_link_to_board()
                flash = backup_channel.read_range(address, length)

            print(helpers.print_flash(address, flash))

    def write_flash(self, address, length, value):
        """
        Write a byte to some flash contents.
        """
        with self._start_communication_with_board():
            to_write = bytes([value] * length)

            try:
                self.channel.flash_binary(address, to_write, pad=False)
            except ChannelAddressErrorException:
                try:
                    from .nrfjprog import nrfjprog
                except:
                    logging.error("Unable to use backup nrfjprog channel")
                    logging.error("You may need to `pip install pynrfjprog`")
                    raise TockLoaderException("Unable to use nrfjprog backup channel")

                self.args.board = self.channel.get_board_name()
                backup_channel = nrfjprog(self.args)
                backup_channel.open_link_to_board()
                backup_channel.flash_binary(address, to_write, pad=False)

    def tickv_get(self, key):
        """
        Read a key, value pair from a TicKV database on a board.
        """

        with self._start_communication_with_board():
            tickv_db = self._tickv_get_database()
            kv_object = tickv_db.get(key)
            print(kv_object)

    def tickv_dump(self):
        """
        Display all of the contents of a TicKV database.
        """
        with self._start_communication_with_board():
            tickv_db = self._tickv_get_database()
            print(tickv_db.dump())

    def tickv_invalidate(self, key):
        """
        Invalidate a particular key in the database.
        """
        with self._start_communication_with_board():
            tickv_db = self._tickv_get_database()
            tickv_db.invalidate(key)
            self._tickv_write_database(tickv_db)

    def tickv_append(self, key, value=None, write_id=0):
        """
        Add a key,value pair to the database. The first argument can a list of
        key, value pairs.
        """
        with self._start_communication_with_board():
            tickv_db = self._tickv_get_database()

            # Check if we got a list of key-value pairs or just one.
            if isinstance(key, list):
                for k, v in key:
                    tickv_db.append(k, v, write_id)
            else:
                tickv_db.append(key, value, write_id)

            self._tickv_write_database(tickv_db)

    def tickv_cleanup(self):
        """
        Clean the database by remove invalid objects and re-storing valid
        objects.
        """
        with self._start_communication_with_board():
            tickv_db = self._tickv_get_database()
            tickv_db.cleanup()
            self._tickv_write_database(tickv_db)

    def tickv_reset(self):
        """
        Reset the database by erasing it and re-initializing.
        """
        with self._start_communication_with_board():
            tickv_db = self._tickv_get_database()
            tickv_db.reset()
            self._tickv_write_database(tickv_db)

    def tickv_hash(self, key):
        """
        Return the hash of the specified key.
        """
        tickv_db = TockTicKV([], 1)
        return tickv_db._hash_key_int(key)

    def run_terminal(self):
        """
        Create an interactive terminal session with the board.

        This is a special-case use of Tockloader where this is really a helper
        function for running some sort of underlying terminal-like operation.
        Therefore, how we set this up is a little different from other
        tockloader commands. In particular, we do _not_ want `tockloader.open()`
        to have been called at this point.
        """
        # By default, we use the serial connection and serial terminal. However,
        # tockloader supports other terminals, and we choose the correct one
        # here. There is no need to save the channel, since
        # `channel.run_terminal()` never returns.
        if self.args.rtt:
            if self.args.openocd:
                channel = OpenOCD(self.args)
            else:
                channel = JLinkExe(self.args)

        else:
            channel = BootloaderSerial(self.args)
            channel.open_link_to_board(listen=True)

        channel.run_terminal()

    def print_known_boards(self):
        """
        Simple function to print to console the boards that are hardcoded
        into Tockloader to make them easier to use.
        """
        BoardInterface(self.args).print_known_boards()

    ############################################################################
    ## Internal Helper Functions for Communicating with Boards
    ############################################################################

    @contextlib.contextmanager
    def _start_communication_with_board(self):
        """
        Based on the transport method used, there may be some setup required
        to connect to the board. This function runs the setup needed to connect
        to the board. It also times the operation.

        For the bootloader, the board needs to be reset and told to enter the
        bootloader mode. For JTAG, this is unnecessary.
        """
        # Time the operation
        then = time.time()
        try:
            if not self.args.no_bootloader_entry:
                logging.debug("start: Enter bootloader mode")
                self.channel.enter_bootloader_mode()
            else:
                time.sleep(0.2)

            # Now that we have connected to the board and the bootloader
            # if necessary, make sure we know what kind of board we are
            # talking to.
            logging.debug("start: Determine current board")
            self.channel.determine_current_board()

            # Set any board-specific options that tockloader needs to use.
            logging.debug("start: Update board specific options")
            self._update_board_specific_options()

            yield

            if platform.system() == "Windows":
                for file in collect_temp_files:
                    os.remove(file)

            now = time.time()
            logging.info("Finished in {:0.3f} seconds".format(now - then))
        except Exception as e:
            raise (e)
        finally:
            self.channel.exit_bootloader_mode()

    def _bootloader_is_present(self):
        """
        Check if a bootloader exists on this board. It is specified by the
        string "TOCKBOOTLOADER" being at address 0x400.
        """
        # Check to see if the channel already knows this. For example,
        # if you are connected via a serial link to the bootloader,
        # then obviously the bootloader is present.
        if self.channel.bootloader_is_present() == True:
            return True

        # Otherwise check for the bootloader flag in the flash.

        # Constants for the bootloader flag
        address = self._convert_offset_to_absolute_flash_address(0x400)
        length = 14
        flag = self.channel.read_range(address, length)
        flag_str = flag.decode("utf-8", "ignore")
        logging.debug("Read from flags location: {}".format(flag_str))
        return flag_str == "TOCKBOOTLOADER"

    def _update_board_specific_options(self):
        """
        This uses the name of the board to update any hard-coded options about
        how Tockloader should function. This is a convenience mechanism, as it
        prevents users from having to pass them in through command line arguments.
        """

        # Get the arch and name of the board if they are known.
        arch = None
        board = None
        if hasattr(self, "channel"):
            # We have configured a channel to a board, and that channel may
            # have read off of the board which board it actually is.
            arch = self.channel.get_board_arch()
            board = self.channel.get_board_name()
        else:
            arch = getattr(self.args, "arch", None)
            board = getattr(self.args, "board", None)

        # Start by updating settings using the architecture.
        if arch:
            # Loop through the arch string for generic versions.
            for i in range(4, len(arch) + 1):
                try_arch = arch[0:i]
                if try_arch in self.TOCKLOADER_APP_SETTINGS["arch"]:
                    self.app_settings.update(
                        self.TOCKLOADER_APP_SETTINGS["arch"][try_arch]
                    )
                    # Remove the options so they do not get set twice.
                    del self.TOCKLOADER_APP_SETTINGS["arch"][try_arch]

        # Configure settings for the board if possible.
        if board and board in self.TOCKLOADER_APP_SETTINGS["boards"]:
            self.app_settings.update(self.TOCKLOADER_APP_SETTINGS["boards"][board])
            # Remove the options so they do not get set twice.
            del self.TOCKLOADER_APP_SETTINGS["boards"][board]

        # Allow boards to specify command line arguments by default so that
        # users do not have to pass them in every time.
        if "cmd_flags" in self.app_settings:
            for flag, setting in self.app_settings["cmd_flags"].items():
                logging.info(
                    'Hardcoding command line argument "{}" to "{}" for board {}.'.format(
                        flag, setting, board
                    )
                )
                setattr(self.args, flag, setting)

    def _get_apps_start_address(self):
        """
        Return the address in flash where applications start on this platform.
        This might be set on the board itself, in the command line arguments
        to Tockloader, or just be the default.
        """

        # First check if we have a cached value. We might need to lookup the
        # start address a lot, so we don't want to have to query the board for
        # it each time. We also do not use `self.app_settings['start_address']`
        # as the cache because a board attribute may supersede it, and we don't
        # have a good way to mark it as unset since
        # app_settings['start_address'] is set by default.
        cached = getattr(self, "apps_start_address", None)
        if cached:
            return cached

        # Highest priority is the command line argument. If the user specifies
        # that, we use that unconditionally.
        cmdline_app_address = getattr(self.args, "app_address", None)
        if cmdline_app_address:
            self.apps_start_address = cmdline_app_address
            return cmdline_app_address

        # Next we check if the attached board can tell us.
        if self.channel:
            channel_apps_start_address = self.channel.get_apps_start_address()
            if channel_apps_start_address:
                self.apps_start_address = channel_apps_start_address
                return channel_apps_start_address

        # Lastly we default to what was configured using the
        # `TOCKLOADER_APP_SETTINGS` variable.
        return self.app_settings["start_address"]

    def _get_flash_start_address(self):
        """
        Return the address where flash starts.
        """

        # Check if the attached board can tell us.
        if self.channel:
            channel_flash_address = self.channel.get_flash_address()
            if channel_flash_address:
                return channel_flash_address

        # In the default case flash starts at address 0.
        return 0

    def _get_memory_start_address(self):
        """
        Return the address in memory where application RAM starts on this
        platform. We mostly don't know this, so it may be None.
        """

        # First check if we have a cached value. We might need to lookup the
        # app RAM address often, so we don't want to have to query the board for
        # it each time.
        cached = getattr(self, "app_ram_address", None)
        if cached:
            return cached

        # Next we check for kernel attributes.
        if self.channel:
            app_start_flash = self._get_apps_start_address()
            kernel_attr_binary = self.channel.read_range(app_start_flash - 100, 100)
            kernel_attrs = KernelAttributes(kernel_attr_binary, app_start_flash)
            app_ram = kernel_attrs.get_app_memory_region()
            if app_ram != None:
                app_ram_start_address = app_ram[0]
                self.app_ram_address = app_ram_start_address
                return app_ram_start_address

        # Finally we use a saved setting in tockloader itself.
        if "app_ram_address" in self.app_settings:
            return self.app_settings["app_ram_address"]
        else:
            return None

    def _convert_offset_to_absolute_flash_address(self, offset):
        """
        Compute the absolute flash address for an offset for the attached board.
        """
        return self._get_flash_start_address() + offset

    ############################################################################
    ## Helper Functions for Shared Code
    ############################################################################

    def _set_attribute(self, key, value, log_status=True):
        """
        Internal function for setting an attribute stored on the board.

        Bootloader mode must be active.

        Returns None if successful and an error string if not.
        """
        # By default log status. However, that is not always appropriate, so
        # if `log_status` is False then send that to debug output.
        logging_fn = logging.status
        if log_status == False:
            logging_fn = logging.debug

        # Do some checking
        if len(key.encode("utf-8")) > 8:
            return "Key is too long. Must be 8 bytes or fewer."
        if len(value.encode("utf-8")) > 55:
            return "Value is too long. Must be 55 bytes or fewer."

        # Check for the bootloader, and importantly the attributes section.
        if not self._bootloader_is_present():
            return (
                "No bootloader found! That means there is nowhere for attributes to go."
            )

        # Create the buffer to write as the attribute
        out = bytes([])
        # Add key
        out += key.encode("utf-8")
        out += bytes([0] * (8 - len(out)))
        # Add length
        out += bytes([len(value.encode("utf-8"))])
        # Add value
        out += value.encode("utf-8")

        # Find if this attribute key already exists
        open_index = -1
        for index, attribute in enumerate(self.channel.get_all_attributes()):
            if attribute:
                if attribute["key"] == key:
                    if attribute["value"] == value:
                        logging_fn(
                            "Found existing key,value at slot {}. Nothing to do.".format(
                                index
                            )
                        )
                    else:
                        logging_fn(
                            "Found existing key at slot {}. Overwriting.".format(index)
                        )
                        self.channel.set_attribute(index, out)
                    break
            else:
                # Save where we should put this attribute if it does not
                # already exist.
                if open_index == -1:
                    open_index = index
        else:
            if open_index == -1:
                return "No open space to save this attribute."
            else:
                logging_fn(
                    "Key not found. Writing new attribute to slot {}".format(open_index)
                )
                self.channel.set_attribute(open_index, out)

    def _tickv_get_database(self):
        """
        Read the flash for a TicKV database. Since this might be stored on
        external flash, we might need to use a backup mechanism to read the
        flash.
        """
        # Get parameters from command line.
        tickv_address = getattr(self.args, "start_address", -1)
        region_size = getattr(self.args, "region_size", 0)
        number_regions = getattr(self.args, "number_regions", 0)

        # If needed, fill in settings from known values.
        if tickv_address == -1 or region_size == 0 or number_regions == 0:
            if not "tickv" in self.app_settings:
                raise TockLoaderException("TicKV settings not specified")

            if tickv_address == -1:
                tickv_address = self.app_settings["tickv"]["start_address"]
            if region_size == 0:
                region_size = self.app_settings["tickv"]["region_size"]
            if number_regions == 0:
                number_regions = self.app_settings["tickv"]["number_regions"]

        tickv_size = region_size * number_regions

        try:
            tickv_db = self.channel.read_range(tickv_address, tickv_size)
        except ChannelAddressErrorException:
            try:
                from .nrfjprog import nrfjprog
            except:
                logging.error("Unable to use backup nrfjprog channel")
                logging.error("You may need to `pip install pynrfjprog`")
                raise TockLoaderException("Unable to use nrfjprog backup channel")

            self.args.board = self.channel.get_board_name()
            backup_channel = nrfjprog(self.args)
            backup_channel.open_link_to_board()
            tickv_db = backup_channel.read_range(tickv_address, tickv_size)

        return TockTicKV(tickv_db, region_size)

    def _tickv_write_database(self, tickv_db):
        """
        Write a TicKV database back to flash, overwriting the existing database.
        """
        # Get parameters from command line.
        tickv_address = getattr(self.args, "start_address", -1)

        # If needed, fill in settings from known values.
        if tickv_address == -1:
            if not "tickv" in self.app_settings:
                raise TockLoaderException("TicKV settings not specified")

            tickv_address = self.app_settings["tickv"]["start_address"]

        try:
            logging.info("Writing TicKV database back to flash")
            tickv_db = self.channel.flash_binary(tickv_address, tickv_db.get_binary())
        except ChannelAddressErrorException:
            try:
                from .nrfjprog import nrfjprog
            except:
                logging.error("Unable to use backup nrfjprog channel")
                logging.error("You may need to `pip install pynrfjprog`")
                raise TockLoaderException("Unable to use nrfjprog backup channel")

            self.args.board = self.channel.get_board_name()
            backup_channel = nrfjprog(self.args)
            backup_channel.open_link_to_board()
            tickv_db = backup_channel.flash_binary(tickv_address, tickv_db.get_binary())

    ############################################################################
    ## Helper Functions for Manipulating Binaries and TBF
    ############################################################################

    def _reshuffle_apps(self, apps, preserve_order=False):
        """
        Given an array of apps, some of which are new and some of which exist,
        sort them so we can write them to flash.

        This function is really the driver of tockloader, and is responsible for
        setting up applications in a way that can be successfully used by the
        board.

        If `preserve_order` is set to `True` this won't actually do any
        shuffling, and will instead load apps with padding in the order they are
        in the array.
        """

        #
        # JUNE 2020: This function can be really complicated (balancing apps
        # compiled for a fixed address, MPU alignment concerns, ordering
        # concerns, handling apps from TABs and already installed etc.) and by
        # no means is the current implementation arriving at an optimal
        # solution. An interested contributor could probably find many
        # improvements and optimizations.
        #

        # Get where the apps live in flash.
        address = self._get_apps_start_address()

        # Get where app memory might start.
        ram_start_address = self._get_memory_start_address()

        # elf2tab can produce TBFs which have a fixed flash start
        # address, but not a fixed RAM start address, in which case
        # the above is `None`. Preformat it in case it is a number,
        # otherwise print as "None":
        if ram_start_address is None:
            ram_start_address_hex = "None"
        else:
            ram_start_address_hex = "{:#x}".format(ram_start_address)

        logging.debug(
            "Shuffling apps. Flash={:#x} RAM={}".format(address, ram_start_address_hex)
        )

        # First, we are going to split the work into three cases:
        #
        # 1. All apps are fixed address, meaning they have to be loaded at very
        #    specific addresses.
        # 2. All apps are position independent, and can be put at any address.
        # 3. There is a mix of fixed address and position independent apps.
        #
        # Then we can handle organizing the apps in each case separately.

        # Default to mixed, and only if all are one type be specific.
        app_position_scenario = "mixed"
        if all(map(lambda x: x.has_fixed_addresses(), apps)):
            app_position_scenario = "fixed"
        elif all(map(lambda x: not x.has_fixed_addresses(), apps)):
            app_position_scenario = "independent"

        if app_position_scenario == "mixed":
            # Currently unsupported. This could (should?) be added in the
            # future.
            raise TockLoaderException(
                "Mixing fixed address and position-independent apps is currently unsupported."
            )

        if app_position_scenario == "fixed":
            #
            # This is the fixed addresses case
            #

            if preserve_order:
                raise TockLoaderException(
                    "Cannot preserve order with fixed-address apps."
                )

            def brad_sort(slices):
                """
                Get an ordering of apps where the fixed start addresses are
                respected and the apps do not overlap.

                Brute force method!
                """

                def is_valid(slices):
                    """
                    Check if the list of app regions (slices) can fit correctly.
                    """
                    slices = list(slices)
                    slices.sort(key=lambda x: x[0])
                    end = 0
                    for s in slices:
                        if s[0] < end:
                            return False
                        end = s[0] + s[1]
                    return True

                # Get a list of all possible orderings.
                options = itertools.product(*slices)
                # See if any work.
                for o in options:
                    if is_valid(o):
                        return o

                # Couldn't find a valid ordering.
                return None

            # First, if we can, filter all TBFs in each TAB for only TBFs which
            # are plausibly within the app RAM region on the board.
            if ram_start_address != None:
                for app in apps:
                    app.filter_fixed_ram_address(ram_start_address)

            # Get a list of all possible start and length pairs for each app to
            # flash. Also keep around the index of the app in original array.
            slices = []
            for i, app in enumerate(apps):
                apps_in_flash = app.get_fixed_addresses_flash_and_sizes()
                app_slices = []
                for starting_address, size in apps_in_flash:
                    if starting_address < address:
                        # Can't use an app below the start of apps address.
                        continue
                    # HACK! Let's assume no board has more than 2 MB of flash.
                    if starting_address > (address + 0x200000):
                        logging.debug(
                            "Ignoring start address {:#x} as too large.".format(
                                starting_address
                            )
                        )
                        continue

                    logging.debug(
                        f"Considering App {app.get_name()} (flash:{starting_address:#02x} size:{size:#02x})"
                    )
                    app_slices.append([starting_address, size, i])
                slices.append(app_slices)

            # See if we can find an ordering that works.
            valid_order = brad_sort(slices)
            if valid_order == None:
                logging.error("Could not meet fixed address requirements.")
                if self.args.debug:
                    for app in apps:
                        logging.debug("{}".format(app.info(True)))
                raise TockLoaderException(
                    "Unable to find a valid sort order to flash apps."
                )

            # Get sorted apps array.
            logging.info("Found sort order:")
            sorted_apps = []
            for order in sorted(valid_order, key=lambda a: a[0]):
                app = apps[order[2]]
                logging.info(
                    '  App "{}" at Flash={:#x}'.format(app.get_name(), order[0])
                )
                sorted_apps.append(app)
            apps = sorted_apps

            # Iterate all of the apps, and see if we can make this work based on
            # having apps compiled for the correct addresses. If so, great! If
            # not, error for now.
            to_flash_apps = []
            app_address = address
            for app in apps:
                # Get a version of that app that we can put at a desirable address.
                next_loadable_address = app.fix_at_next_loadable_address(app_address)

                if next_loadable_address == app_address:
                    to_flash_apps.append(app)
                    app_address += app.get_size()

                elif next_loadable_address != None:
                    # Need to add padding.
                    padding_app = PaddingApp(next_loadable_address - app_address)
                    to_flash_apps.append(padding_app)
                    app_address += padding_app.get_size()

                    to_flash_apps.append(app)
                    app_address += app.get_size()

                else:
                    logging.error('Trying to find a location for app "{}"'.format(app))
                    logging.error("  Address to use is {:#x}".format(app_address))
                    raise TockLoaderException(
                        "Could not load apps due to address mismatches"
                    )

            logging.info("App Layout:")
            displayer = display.HumanReadableDisplay()
            displayer.show_app_map_from_address(to_flash_apps, address)
            app_layout = displayer.get()
            for l in app_layout.splitlines():
                logging.info(l)

            # Actually write apps to the board.
            app_address = address
            if self.args.bundle_apps:
                # Tockloader has been configured to bundle all apps as a single
                # binary. Here we concatenate all apps and then call flash once.
                #
                # This should be compatible with all boards, but if there
                # several existing apps they have to be re-flashed, and that
                # could add significant overhead. So, we prefer to flash only
                # what has changed and special case this bundle operation.
                app_bundle = bytearray()
                for app in to_flash_apps:
                    app_bundle += app.get_binary(app_address)
                    app_address += app.get_size()
                logging.info(
                    "Installing app bundle. Size: {} bytes.".format(len(app_bundle))
                )
                self.channel.flash_binary(address, app_bundle)
            else:
                # Flash only apps that have been modified. The only way an app
                # would not be modified is if it was read off the board and
                # nothing changed.
                for app in to_flash_apps:
                    # If we get a binary, then we need to flash it. Otherwise,
                    # the app is already installed.
                    optional_binary = app.get_binary(app_address)
                    if optional_binary:
                        self.channel.flash_binary(app_address, optional_binary)
                    app_address = app_address + app.get_size()

            # Then erase the next page if we have not already rewritten all
            # existing apps. This ensures that flash is clean at the end of the
            # installed apps and makes sure the kernel will find the correct end
            # of applications.
            self.channel.clear_bytes(app_address)

            # Handled fixed address case, do not continue on to run the
            # non-fixed address case.
            return

        #
        # This is the normal PIC case
        #

        # We are given an array of apps. First we need to order them based on
        # the ordering requested by this board (or potentially the user).
        if preserve_order:
            # We already have our sort order if we are preserving the order.
            # We use the order the apps were given to us.
            pass
        elif self.app_settings["order"] == "size_descending":
            apps.sort(key=lambda app: app.get_size(), reverse=True)
        elif self.app_settings["order"] == None:
            # Any order is fine.
            pass
        else:
            raise TockLoaderException("Unknown sort order. This is a tockloader bug.")

        # Decide if we need to read the existing binary from flash into memory.
        # We can need to do this for various reasons:
        #
        # 1. If the app location has changed, and we will need to write it to
        #    its new location.
        # 2. If we are flashing all apps at once as a bundle.
        # 3. If the TBF header has changed and we need to update it in flash.
        #
        # If apps are moving then we need to read their contents off the board
        # so we can re-flash them in their new spot. Also, tockloader supports
        # flashing all apps as a single binary, as some boards have
        # flash controllers that require an erase before any writes, and the
        # erase covers a large area of flash. In that case, we must read all
        # apps and then re-write them, since otherwise they will be erased.
        #
        # So, we iterate through all apps and read them into memory if we are
        # doing an erase and re-flash cycle or if the app has moved.
        app_address = address
        for app in apps:
            # If we do not already have a binary, and any of the conditions are
            # met, we need to read the app binary from the board.
            if (not app.has_app_binary()) and (
                self.args.bundle_apps
                or app.get_address() != app_address
                or app.is_modified()
            ):
                logging.info("Reading app {} binary from board.".format(app))
                entire_app = self.channel.read_range(app.address, app.get_size())
                in_flash_tbfh = TBFHeader(entire_app)
                app.set_app_binary(entire_app[in_flash_tbfh.get_header_size() :])

            app_address += app.get_size()

        # Need to know the address we are putting each app at.
        app_address = address

        # Actually write apps to the board.
        if self.args.bundle_apps:
            # Tockloader has been configured to bundle all apps as a single
            # binary. Here we concatenate all apps and then call flash once.
            #
            # This should be compatible with all boards, but if there several
            # existing apps they have to be re-flashed, and that could add
            # significant overhead. So, we prefer to flash only what has changed
            # and special case this bundle operation.
            app_bundle = bytearray()
            for app in apps:
                # Check if we might need to insert a padding app.
                if self.app_settings["alignment_constraint"]:
                    if self.app_settings["alignment_constraint"] == "size":
                        # We need to make sure the app is aligned to a multiple
                        # of its size.
                        size = app.get_size()
                        multiple = app_address // size
                        if multiple * size != app_address:
                            # Not aligned. Insert padding app.
                            new_address = ((app_address + size) // size) * size
                            gap_size = new_address - app_address
                            padding = PaddingApp(gap_size)
                            app_bundle += padding
                            app_address = new_address

                app_bundle += app.get_binary(app_address)
                app_address += app.get_size()

            # Add blank at the end to make sure we clear the end of the list of
            # apps.
            app_bundle += bytes([0xFF] * 8)

            logging.info(
                "Installing app bundle. Size: {} bytes.".format(len(app_bundle))
            )
            self.channel.flash_binary(address, app_bundle)
        else:
            # Flash only apps that have been modified. The only way an app would
            # not be modified is if it was read off the board and nothing
            # changed.
            for app in apps:
                # Check if we might need to insert a padding app.
                if self.app_settings["alignment_constraint"]:
                    if self.app_settings["alignment_constraint"] == "size":
                        # We need to make sure the app is aligned to a multiple
                        # of its size.
                        size = app.get_size()
                        multiple = app_address // size
                        if multiple * size != app_address:
                            # Not aligned. Insert padding app.
                            new_address = ((app_address + size) // size) * size
                            gap_size = new_address - app_address
                            padding = PaddingApp(gap_size)

                            logging.info("Flashing padding to board.")
                            self.channel.flash_binary(
                                app_address, padding.get_binary(app_address)
                            )
                            app_address = new_address

                # If we get a binary, then we need to flash it. Otherwise,
                # the app is already installed.
                optional_binary = app.get_binary(app_address)
                if optional_binary:
                    logging.info("Flashing app {} binary to board.".format(app))
                    self.channel.flash_binary(app_address, optional_binary)
                app_address = app_address + app.get_size()

            # Then erase the next page if we have not already rewritten all
            # existing apps. This ensures that flash is clean at the end of the
            # installed apps and makes sure the kernel will find the correct end
            # of applications.
            self.channel.clear_bytes(app_address)

    def _replace_with_padding(self, app):
        """
        Update the TBF header of installed app `app` with a padding header
        to effectively uninstall it.
        """
        # Create replacement padding app.
        size = app.get_size()
        padding = PaddingApp(size)
        address = app.get_address()

        logging.debug(
            "Flashing padding app header (total size:{}) at {:#x} to uninstall {}".format(
                size, address, app
            )
        )
        self.channel.flash_binary(address, padding.get_tbfh().get_binary())

    def _extract_all_app_headers(self, verbose=False, extract_app_binary=False):
        """
        Iterate through the flash on the board for the header information about
        each app.

        Options:
        - `verbose`: Show ALL apps, including padding apps.
        - `extract_app_binary`: Get the actual app binary in addition to the
          headers.
        """
        apps = []

        # This can be the default, it can be configured in the attributes on
        # the hardware, or it can be passed in to Tockloader.
        address = self._get_apps_start_address()

        # Jump through the linked list of apps
        while True:
            header_length = 200  # Version 2
            logging.debug(
                "Reading for app header @{:#x}, {} bytes".format(address, header_length)
            )
            flash = self.channel.read_range(address, header_length)

            # if there was an error, the binary array will be empty
            if len(flash) < header_length:
                break

            # Get all the fields from the header
            tbfh = TBFHeader(flash)

            if tbfh.is_valid():
                if tbfh.is_app():
                    # This app could have a footer. If so, we need to extract it
                    # and include it.
                    tbff = None
                    app_binary = None
                    if tbfh.has_footer():
                        footer_start = address + tbfh.get_binary_end_offset()
                        footer_length = tbfh.get_footer_size()
                        logging.debug(
                            "Reading for app footer @{:#x}, {} bytes".format(
                                footer_start, footer_length
                            )
                        )
                        flash = self.channel.read_range(footer_start, footer_length)
                        tbff = TBFFooter(tbfh, None, flash)

                    if extract_app_binary:
                        app_binary_start = address + tbfh.get_header_size()
                        app_binary_len = (
                            tbfh.get_binary_end_offset() - tbfh.get_header_size()
                        )
                        app_binary = self.channel.read_range(
                            app_binary_start, app_binary_len
                        )

                    app = InstalledApp(tbfh, tbff, address, app_binary)
                    apps.append(app)
                else:
                    app = InstalledPaddingApp(tbfh, address)
                    if verbose:
                        # In verbose mode include padding
                        apps.append(app)

                address += app.get_size()

            else:
                break

        if self.args.debug:
            logging.debug(
                "Found {} app{} on the board.".format(
                    len(apps), helpers.plural(len(apps))
                )
            )
            for i, app in enumerate(apps):
                logging.debug("  {}. {}".format(i + 1, app))

        return apps

    def _extract_apps_from_tabs(self, tabs, arch):
        """
        Iterate through the list of TABs and create the app object for each.
        """
        apps = []

        for tab in tabs:
            # Check if this app is specifically marked as compatible with
            # certain boards, and if so, if the board being programmed is one of
            # them.
            if not self.args.force and not tab.is_compatible_with_board(
                self.channel.get_board_name()
            ):
                # App is marked for certain boards, and this is not one.
                logging.info(
                    'App "{}" is not compatible with your board.'.format(
                        tab.get_app_name()
                    )
                )
                if self.args.debug:
                    logging.debug(
                        'Supported boards for app "{}":'.format(tab.get_app_name())
                    )
                    for board in tab.get_compatible_boards():
                        logging.debug("- {}".format(board))
                continue

            # Check if this app was compiled for the version of the Tock kernel
            # currently on the board. If not, print a notice.
            if not self.args.force and not tab.is_compatible_with_kernel_version(
                self.channel.get_kernel_version()
            ):
                # App needs a different kernel version than what is on the board.
                logging.info(
                    'App "{}" requires kernel version "2", but tockloader determined your kernel version is "{}".'.format(
                        tab.get_app_name(), self.channel.get_kernel_version()
                    )
                )
                continue

            # This app is good to install, continue the process.

            app = tab.extract_app(arch)
            if app == None:
                raise TockLoaderException(
                    "Unable to locate a valid application binary matching the target architecture ({})".format(
                        arch
                    )
                )

            # Enforce other sizing constraints here.
            app.set_size_constraint(self.app_settings["size_constraint"])

            if self.args.corrupt_tbf:
                app.corrupt_tbf(
                    self.args.corrupt_tbf[0], int(self.args.corrupt_tbf[1], 0)
                )

            apps.append(app)

        if len(apps) == 0:
            raise TockLoaderException(
                "No valid apps for this board were provided. Use --force to override."
            )

        return apps

    def _app_is_aligned_correctly(self, address, size):
        """
        Check if putting an app at this address will be OK with the MPU.
        """
        # The rule for the MPU is that the size of the protected region must be
        # a power of two, and that the region is aligned on a multiple of that
        # size.

        if self.app_settings["size_constraint"]:
            if self.app_settings["size_constraint"] == "powers_of_two":
                # Check if size is not a power of two.
                if (size & (size - 1)) != 0:
                    return False

        if self.app_settings["alignment_constraint"]:
            if self.app_settings["alignment_constraint"] == "size":
                # Check that address is a multiple of size.
                multiple = address // size
                if multiple * size != address:
                    return False

        return True

    ############################################################################
    ## Printing helper functions
    ############################################################################

    def _print_apps(self, apps, verbose, quiet):
        """
        Print information about a list of apps
        """
        if not quiet:
            # Print info about each app
            for i, app in enumerate(apps):
                if app.is_app():
                    print(helpers.text_in_box("App {}".format(i), 52))

                    # Check if this app is OK with the MPU region requirements.
                    if not self._app_is_aligned_correctly(
                        app.get_address(), app.get_size()
                    ):
                        print("  [WARNING] App is misaligned for the MPU")

                    print(textwrap.indent(app.info(verbose), "  "))
                    print("")
                else:
                    # Display padding
                    print(helpers.text_in_box("Padding", 52))
                    print(textwrap.indent(app.info(verbose), "  "))
                    print("")

            if len(apps) == 0:
                logging.info("No found apps.")

        else:
            # In quiet mode just show the names.
            print(" ".join([app.get_name() for app in apps]))


def is_known_board(board):
    return BoardInterface.is_known_board(board)


def set_local_board(
    board,
    arch=None,
    app_address=None,
    flash_address=None,
    flush_command=None,
    binary_path=None,
):
    flash_file.set_local_board(
        board, arch, app_address, flash_address, flush_command, binary_path
    )


def unset_local_board():
    flash_file.unset_local_board()


def get_local_board_path():
    flash_file_channel = FlashFile(None)
    if flash_file_channel.attached_board_exists():
        flash_file_channel.open_link_to_board()
        return flash_file_channel.get_local_board_path()
    else:
        return ""


def flush_local_board(args):
    flash_file_channel = FlashFile(args)
    flash_file_channel.open_link_to_board()
    flash_file_channel.flush()
