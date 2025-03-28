#!/usr/bin/env python3

"""
### Main command line interface for Tockloader.

Each `tockloader` command is mapped to a function which calls the correct
tockloader class function. This file also handles discovering and reading in TAB
files.
"""

import argparse
import atexit
import binascii
import functools
import glob
import logging
import os
import subprocess
import sys
import textwrap
import time
import urllib.parse

import argcomplete
import crcmod

from . import helpers
from .exceptions import TockLoaderException
from .tab import TAB
from .tickv import TicKV, TockTicKV
from .tockloader import TockLoader
from . import tbfh
from .tbfh import get_addable_tlvs
from ._version import __version__


def check_and_run_make(args):
    """
    Checks for a Makefile, and it it exists runs `make`.
    """

    if hasattr(args, "make") and args.make:
        if os.path.isfile("./Makefile"):
            logging.status("Running `make`...")
            p = subprocess.Popen(["make"])
            out, err = p.communicate()
            if p.returncode != 0:
                logging.error("Error running make.")
                sys.exit(1)


def collect_tabs(args):
    """
    Load in Tock Application Bundle (TAB) files. If none are specified, this
    searches for them in subfolders.

    Also allow downloading apps by name from a server.
    """

    tab_names = args.tab

    # Check if any tab files were specified. If not, find them based
    # on where this tool is being run.
    if len(tab_names) == 0 or tab_names[0] == "":
        logging.info("No TABs passed to tockloader.")
        logging.status("Searching for TABs in subdirectories.")

        # First check to see if things could be built that haven't been
        if os.path.isfile("./Makefile"):
            p = subprocess.Popen(["make", "-n"], stdout=subprocess.PIPE)
            out, err = p.communicate()
            # Check for the name of the compiler to see if there is work
            # to be done
            if "arm-none-eabi-gcc" in out.decode("utf-8"):
                logging.warning("Warning! There are uncompiled changes!")
                logging.warning(
                    "You may want to run `make` before loading the application."
                )

        # Search for ".tab" files
        tab_names = glob.glob("./**/*.tab", recursive=True)
        if len(tab_names) == 0:
            raise TockLoaderException("No TAB files found.")

        # If there are multiple tabs and they are all in the local directory
        # then we assume the user wants to use all of them. If at least one tab
        # is NOT in the local directory, we assume the user did not know which
        # tabs would be found and ask them to specify which to use.
        if len(tab_names) > 1:
            if len(list(filter(lambda x: os.path.dirname(x) != ".", tab_names))) > 0:
                # At least one tab path has a subdirectory in it.
                tab_names = helpers.menu_multiple(
                    tab_names, prompt="Which TAB files do you want to use?"
                )

        if len(tab_names) == 0:
            raise TockLoaderException("No TAB files selected.")

        logging.info("Using: {}".format(tab_names))

    # Concatenate the binaries.
    tabs = []
    for tab_name in tab_names:
        # Check if this is a TAB locally, or if we should check for it
        # on a remote hosting server.
        if not urllib.parse.urlparse(tab_name).scheme and not os.path.exists(tab_name):
            logging.info('Could not find TAB named "{}" locally.'.format(tab_name))
            use_app_store = helpers.menu_new_yes_no(
                prompt="Would you like to check the online TAB repository for that app?",
            )
            if use_app_store:
                # User said yes, create that URL and try to load the TAB.
                tab_name = "https://www.tockos.org/assets/tabs/{}.tab".format(tab_name)
            else:
                # User said no, skip this tab_name.
                continue

        try:
            tabs.append(TAB(tab_name, args))
        except Exception as e:
            if args.debug:
                logging.debug("Exception: {}".format(e))
            logging.error('Error opening and reading "{}"'.format(tab_name))

    if len(tabs) == 0:
        raise TockLoaderException("No valid TABs to use.")

    return tabs


def command_listen(args):
    tock_loader = TockLoader(args)
    tock_loader.run_terminal()


def command_list(args):
    # Optimistically try to verify any included credentials if asked to. We have
    # to read in the actual key contents.
    public_keys = None
    if args.verify_credentials != None:
        public_keys = []
        if args.verify_credentials:
            for key_path in args.verify_credentials:
                with open(key_path, "rb") as f:
                    public_keys.append(f.read())

    verbose = args.verbose
    if args.map:
        # We always want verbose if showing the map so we see all apps including
        # padding.
        verbose = True

    tock_loader = TockLoader(args)
    tock_loader.open()
    tock_loader.list_apps(verbose, args.quiet, args.map, public_keys)


def command_install(args):
    check_and_run_make(args)

    # Load in all TABs
    tabs = collect_tabs(args)

    # Install the apps on the board
    tock_loader = TockLoader(args)
    tock_loader.open()

    # Figure out how we want to do updates
    replace = "yes"
    if args.no_replace:
        replace = "no"
    if args.preserve_order:
        # We are just going to append all specified apps in the order they are
        # included on the command line.
        replace = "no"

    layout = None
    if args.layout:
        layout = args.layout[0]

    logging.status("Installing app{} on the board...".format(helpers.plural(len(tabs))))
    tock_loader.install(
        tabs, replace=replace, erase=args.erase, sticky=args.sticky, layout=layout
    )


def command_update(args):
    check_and_run_make(args)
    tabs = collect_tabs(args)

    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status(
        "Updating application{} on the board...".format(helpers.plural(len(tabs)))
    )
    tock_loader.install(tabs, replace="only")


def command_uninstall(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    if len(args.name) != 0:
        logging.status("Removing app(s) {} from board...".format(", ".join(args.name)))
    else:
        logging.status("Preparing to uninstall apps...")
    tock_loader.uninstall_app(args.name)


def command_erase_apps(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Removing apps...")
    tock_loader.erase_apps()


def command_enable_app(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Enabling apps...")
    tock_loader.set_flag(args.name, "enable", True)


def command_disable_app(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Disabling apps...")
    tock_loader.set_flag(args.name, "enable", False)


def command_sticky_app(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Making apps sticky...")
    tock_loader.set_flag(args.name, "sticky", True)


def command_unsticky_app(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Making apps no longer sticky...")
    tock_loader.set_flag(args.name, "sticky", False)


def command_flash(args):
    check_and_run_make(args)

    # Load in all binaries
    binary = bytes()
    count = 0
    for binary_name in args.binary:
        # check that file isn't a `.hex` file
        if binary_name.endswith(".hex"):
            exception_string = 'Error: Cannot flash ".hex" files.'
            exception_string += ' Likely you meant to use a ".bin" file but used an intel hex file by accident.'
            raise TockLoaderException(exception_string)

        # add contents to binary
        with open(binary_name, "rb") as f:
            binary += f.read()
        count += 1

    # Check if the user asked us to pad the binary with some additional bytes.
    pad = None
    if args.pad:
        # First arg is the length, second arg is the value
        pad = (args.pad[0], args.pad[1])
        if pad[1] < 0 or pad[1] > 255:
            raise TockLoaderException("Padding value must be only one byte")

    # Flash the binary to the chip
    tock_loader = TockLoader(args)
    tock_loader.open()

    plural = "y"
    if count > 1:
        plural = "ies"
    logging.status("Flashing binar{} to board...".format(plural))
    tock_loader.flash_binary(binary, args.address, pad=pad)


def command_read(args):
    """
    Read the correct flash range from the chip.
    """
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Reading flash from the board...")
    logging.status("  Address: {:#x}".format(args.address))
    logging.status("  Length:  {} bytes".format(args.length))
    tock_loader.read_flash(args.address, args.length)


def command_write(args):
    """
    Write flash range on the chip with a specific value.
    """
    tock_loader = TockLoader(args)
    tock_loader.open()

    # Only write a single byte.
    if args.value < 0 or args.value > 0xFF:
        raise TockLoaderException("Can only write multiple copies of a single byte")

    logging.status("Writing flash on the board...")
    logging.status("  Address: {:#x}".format(args.address))
    logging.status("  Length:  {} bytes".format(args.length))
    logging.status("  Value:   {:#x}".format(args.value))
    tock_loader.write_flash(args.address, args.length, args.value)


def command_list_attributes(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Listing attributes...")
    tock_loader.list_attributes()


def command_set_attribute(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Setting attribute...")
    tock_loader.set_attribute(args.key, args.value)


def command_remove_attribute(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Removing attribute...")
    tock_loader.remove_attribute(args.key)


def command_set_start_address(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Setting bootloader jump address...")
    tock_loader.set_start_address(args.address)


def command_info(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    print("tockloader version: {}".format(__version__))
    logging.status("Showing all properties of the board...")
    tock_loader.info()


def command_inspect_tab(args):
    tabs = collect_tabs(args)

    if len(tabs) == 0:
        raise TockLoaderException("No TABs found to inspect")

    logging.status("Inspecting TABs...")
    for tab in tabs:
        # Print the basic information that is true about the TAB and all
        # contained TBF binaries.
        print(tab)

        # Ask the user if they want to see more detail about a certain TBF.
        tbf_names = tab.get_tbf_names()
        index = helpers.menu_new(
            tbf_names + ["None"],
            return_type="index",
            title="Which TBF to inspect further?",
        )
        if index < len(tbf_names):
            app = tab.extract_tbf(tbf_names[index])

            # Optimistically try to verify any included credentials.
            # We have to read in the actual key contents.
            public_keys = []
            if args.verify_credentials:
                for key_path in args.verify_credentials:
                    with open(key_path, "rb") as f:
                        public_keys.append(f.read())

            # We may have a footer in this app, it may be possible to verify
            # any contained credentials now.
            app.verify_credentials(public_keys)

            print("")
            print("{}:".format(tbf_names[index]))
            print(textwrap.indent(str(app.get_header()), "  "))

            # If the user asked for the crt0 header, display that for the
            # architecture
            if args.crt0_header:
                print("  crt0 header")
                print(textwrap.indent(app.get_crt0_header_str(), "    "))

            print("TBF Footers")
            print(textwrap.indent(str(app.get_footers()), "  "))

            # If the user asked for the entire TBF, display that for the
            # architecture.
            if args.tbf_binary:
                print("  tbf binary")
                print(
                    textwrap.indent(helpers.print_flash(0, app.get_binary(0)), "    ")
                )
        print("")


def command_tbf_tlv_delete(args):
    tabs = collect_tabs(args)

    if len(tabs) == 0:
        raise TockLoaderException("No TABs found, no TBF to process")

    tlvname = args.tlvname
    logging.status("Removing TLV ID {} from TBF...".format(tlvname))
    for tab in tabs:
        # Ask the user which TBF binaries to update.
        tbf_names = tab.get_tbf_names()
        index = helpers.menu_new(
            tbf_names + ["All"],
            return_type="index",
            title="Which TBF to delete TLV from?",
            default_index=len(tbf_names),
        )
        for i, tbf_name in enumerate(tbf_names):
            if i == index or index == len(tbf_names):
                app = tab.extract_tbf(tbf_name)
                app.delete_tlv(tlvname)
                tab.update_tbf(app)


def command_tbf_tlv_modify(args):
    tabs = collect_tabs(args)

    if len(tabs) == 0:
        raise TockLoaderException("No TABs found, no TBF headers to process")

    tlvname = args.tlvname
    field = args.field
    value = args.value
    logging.status("Modifying TLV ID {} to set {}={}...".format(tlvname, field, value))
    for tab in tabs:
        # Ask the user which TBF binaries to update.
        tbf_names = tab.get_tbf_names()
        index = helpers.menu_new(
            tbf_names + ["All"],
            return_type="index",
            title="Which TBF to modify TLV?",
            default_index=len(tbf_names),
        )
        for i, tbf_name in enumerate(tbf_names):
            if i == index or index == len(tbf_names):
                app = tab.extract_tbf(tbf_name)
                app.modify_tbfh_tlv(tlvname, field, value)
                tab.update_tbf(app)


def command_tbf_tlv_add(args):
    tabs = collect_tabs(args)

    if len(tabs) == 0:
        raise TockLoaderException("No TABs found, no TBF headers to process")

    tlvname = args.subsubsubcommand
    parameters = args.parameters
    logging.status("Adding TLV {}...".format(tlvname))
    for tab in tabs:
        # Ask the user which TBF binaries to update.
        tbf_names = tab.get_tbf_names()
        index = helpers.menu_new(
            tbf_names + ["All"],
            return_type="index",
            title="Which TBF to modify TLV?",
            default_index=len(tbf_names),
        )
        for i, tbf_name in enumerate(tbf_names):
            if i == index or index == len(tbf_names):
                app = tab.extract_tbf(tbf_name)
                app.add_tbfh_tlv(tlvname, parameters)
                tab.update_tbf(app)


def command_tbf_credential_add(args):
    tabs = collect_tabs(args)

    if len(tabs) == 0:
        raise TockLoaderException("No TABs found, no TBF footers to process")

    credential_type = args.credential_type
    logging.status(
        "Adding Credential type '{}' to the TBF footer...".format(credential_type)
    )

    # Get CleartextID, if provided
    cleartext_id = None
    if args.cleartext_id:
        cleartext_id = args.cleartext_id[0]

    # Get keys
    pub_key = None
    pri_key = None
    if args.public_key != None:
        with open(args.public_key[0], "rb") as f:
            pub_key = f.read()
    if args.private_key != None:
        with open(args.private_key[0], "rb") as f:
            pri_key = f.read()

    for tab in tabs:
        # Ask the user which TBF binaries to update.
        tbf_names = tab.get_tbf_names()
        index = helpers.menu_new(
            tbf_names + ["All"],
            return_type="index",
            title="Which TBF to modify TLV?",
            default_index=len(tbf_names),
        )
        for i, tbf_name in enumerate(tbf_names):
            if i == index or index == len(tbf_names):
                app = tab.extract_tbf(tbf_name)
                app.add_credential(credential_type, pub_key, pri_key, cleartext_id)
                tab.update_tbf(app)


def command_tbf_credential_delete(args):
    tabs = collect_tabs(args)

    if len(tabs) == 0:
        raise TockLoaderException("No TABs found, no TBF footers to process")

    credential_type = args.credential_type
    logging.status(
        "Removing Credential Type {} from TBF footer...".format(credential_type)
    )
    for tab in tabs:
        # Ask the user which TBF binaries to update.
        tbf_names = tab.get_tbf_names()
        index = helpers.menu_new(
            tbf_names + ["All"],
            return_type="index",
            title="Which TBF to modify TLV?",
            default_index=len(tbf_names),
        )
        for i, tbf_name in enumerate(tbf_names):
            if i == index or index == len(tbf_names):
                app = tab.extract_tbf(tbf_name)
                app.delete_credential(credential_type)
                tab.update_tbf(app)


def command_dump_flash_page(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Getting page of flash...")
    tock_loader.dump_flash_page(args.page)


def command_tickv_get(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Fetching TicKV key...")
    tock_loader.tickv_get(args.key)


def command_tickv_dump(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Dumping entire TicKV database...")
    tock_loader.tickv_dump()


def command_tickv_invalidate(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Invalidating TicKV key...")
    tock_loader.tickv_invalidate(args.key)


def command_tickv_append(args):
    # We support appending a string from the command line or reading in a file
    # and using its contents.
    if args.value_file != None and args.value != None:
        raise TockLoaderException(
            "Cannot append both a string value and value from file"
        )

    append_bytes = b""
    if args.value_file != None:
        with open(args.value_file, "rb") as f:
            append_bytes = f.read()
    else:
        append_bytes = args.value.encode("utf-8")

    # By default our write_id is 0, but the write id can be specified on the
    # command line. This allows tockloader to append k-v pairs as though they
    # were written by an app.
    write_id = args.write_id

    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Appending TicKV key...")
    tock_loader.tickv_append(args.key, append_bytes, write_id)


def command_tickv_append_rsa_key(args):
    """
    Helper operation to store an RSA public key in a TicKV database. This adds
    two key-value pairs:

    1. `rsa<bits>-key-n`
    2. `rsa<bits>-key-e`

    where `<bits>` is the size of the key. So, for 2048 bit RSA keys the two
    TicKV keys will be `rsa2048-key-n` and `rsa2048-key-e`.

    The actual values for n and e are stored as byte arrays.
    """

    key_file = b""
    with open(args.rsa_key_file, "rb") as f:
        key_file = f.read()

    import Crypto
    from Crypto.PublicKey import RSA

    key = RSA.importKey(key_file)

    pairs = [
        ("rsa{}-key-n".format(key.size_in_bits()), key._n.to_bytes()),
        ("rsa{}-key-e".format(key.size_in_bits()), key._e.to_bytes()),
    ]

    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Appending RSA keys in TicKV...")
    tock_loader.tickv_append(pairs)


def command_tickv_cleanup(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Cleaning TicKV database...")
    tock_loader.tickv_cleanup()


def command_tickv_reset(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Resetting TicKV database...")
    tock_loader.tickv_reset()


def command_tickv_hash(args):
    tock_loader = TockLoader(args)
    tock_loader.open()

    logging.status("Hashing a TicKV key...")
    hash = tock_loader.tickv_hash(args.key)
    print("Original key: {}".format(args.key))
    print("Hashed key:   {:#x}".format(hash))


def command_list_known_boards(args):
    tock_loader = TockLoader(args)
    tock_loader.print_known_boards()


################################################################################
## Setup and parse command line arguments
################################################################################


def main():
    """
    Read in command line arguments and call the correct command function.
    """

    # Cleanup any title the program may set
    atexit.register(helpers.set_terminal_title, "")

    # Setup logging for displaying background information to the user.
    logging.basicConfig(
        style="{", format="[{levelname:<7}] {message}", level=logging.INFO
    )
    # Add a custom status level for logging what tockloader is doing.
    logging.addLevelName(25, "STATUS")
    logging.Logger.status = functools.partialmethod(logging.Logger.log, 25)
    logging.status = functools.partial(logging.log, 25)

    # Create a common parent parser for arguments shared by all subparsers. In
    # practice there are very few of these since tockloader supports a range of
    # operations.
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--debug", action="store_true", help="Print additional debugging information"
    )
    parent.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="Print Tockloader version and exit",
    )

    # Get the list of arguments before any command
    before_command_args = parent.parse_known_args()

    # The top-level parser object
    parser = argparse.ArgumentParser(parents=[parent])

    # Parser for all app related commands
    parent_apps = argparse.ArgumentParser(add_help=False)
    parent_apps.add_argument(
        "--app-address",
        "-a",
        help="Address where apps are located",
        type=lambda x: int(x, 0),
    )
    parent_apps.add_argument(
        "--force",
        help="Allow apps on boards that are not listed as compatible",
        action="store_true",
    )
    parent_apps.add_argument(
        "--bundle-apps",
        help="Concatenate apps and flash all together, re-flashing apps as needed",
        action="store_true",
    )

    # Parser for commands that configure the communication channel between
    # tockloader and the board. By default tockloader uses the serial channel.
    # If a board wants to use another option (like a JTAG connection) then
    # tockloader requires a flag so it knows to use a different channel.
    parent_channel = argparse.ArgumentParser(add_help=False)
    parent_channel.add_argument(
        "--port",
        "-p",
        "--device",
        "-d",
        help="The serial port or device name to use",
        metavar="STR",
    )
    parent_channel.add_argument(
        "--serial", action="store_true", help="Use the serial bootloader to flash."
    )
    parent_channel.add_argument(
        "--jtag",
        action="store_true",
        help="Use JTAG and JLinkExe to flash. Deprecated. Use --jlink instead.",
    )
    parent_channel.add_argument(
        "--jlink", action="store_true", help="Use JLinkExe to flash."
    )
    parent_channel.add_argument(
        "--openocd", action="store_true", help="Use OpenOCD to flash."
    )
    parent_channel.add_argument(
        "--stlink", action="store_true", help="Use ST-Link tools to flash."
    )
    parent_channel.add_argument(
        "--jtag-device",
        default="cortex-m0",
        help="The device type to pass to JLinkExe. Useful for initial commissioning. Deprecated. Use --jlink-device instead.",
    )
    parent_channel.add_argument(
        "--jlink-device",
        default="cortex-m0",
        help="The device type to pass to JLinkExe. Useful for initial commissioning.",
    )
    parent_channel.add_argument("--jlink-cmd", help="The JLinkExe binary to invoke.")
    parent_channel.add_argument(
        "--jlink-speed", help="The JLink speed to pass to JLinkExe."
    )
    parent_channel.add_argument(
        "--jlink-if", help="The interface type to pass to JLinkExe."
    )
    parent_channel.add_argument(
        "--jlink-serial-number",
        default=None,
        help="Specify a specific JLink via serial number. Useful when multiple JLinks are connected to the same machine.",
    )
    parent_channel.add_argument(
        "--openocd-serial-number",
        default=None,
        help="Specify a specific board via serial number when using OpenOCD. Useful when multiple identical boards are connected.",
    )
    parent_channel.add_argument(
        "--openocd-board", help="The cfg file in OpenOCD `board` folder."
    )
    parent_channel.add_argument(
        "--openocd-cmd", default="openocd", help="The openocd binary to invoke."
    )
    parent_channel.add_argument(
        "--openocd-options",
        default=[],
        help="Tockloader-specific flags to direct how Tockloader uses OpenOCD.",
        nargs="*",
    )
    parent_channel.add_argument(
        "--openocd-commands",
        default={},
        type=lambda kv: kv.split("=", 1),
        action=helpers.ListToDictAction,
        help='Directly specify which OpenOCD commands to use for "program", "read", or "erase" actions. Example: "program=flash write_image erase {{binary}} {address:#x};verify_image {{binary}} {address:#x};"',
        nargs="*",
    )
    parent_channel.add_argument(
        "--stinfo-cmd", default="st-info", help="The st-info binary to invoke."
    )
    parent_channel.add_argument(
        "--stflash-cmd", default="st-flash", help="The st-flash binary to invoke."
    )
    parent_channel.add_argument(
        "--flash-file",
        help="Operate on a binary flash file instead of a proper board.",
    )
    parent_channel.add_argument(
        "--board",
        default=None,
        help="Explicitly specify the board that is being targeted.",
    )
    parent_channel.add_argument(
        "--arch",
        default=None,
        help="Explicitly specify the architecture of the board that is being targeted.",
    )
    parent_channel.add_argument(
        "--page-size",
        default=0,
        type=int,
        help="Explicitly specify how many bytes in a flash page.",
    )
    parent_channel.add_argument(
        "--baud-rate",
        default=115200,
        type=int,
        help="If using serial, set the target baud rate.",
    )
    parent_channel.add_argument(
        "--no-bootloader-entry",
        action="store_true",
        help="Tell Tockloader to assume the bootloader is already active.",
    )

    # Parser for all output formatting related flags shared by multiple
    # commands.
    parent_format = argparse.ArgumentParser(add_help=False)
    parent_format.add_argument(
        "--output-format",
        help="Address where apps are located",
        choices=["terminal", "visual", "json"],
        default="terminal",
    )

    # Support multiple commands for this tool
    subparser = parser.add_subparsers(
        title="Commands", metavar="                    ", dest="command"
    )

    # Command Groups
    #
    # Python argparse doesn't support grouping commands in subparsers as of
    # January 2021 :(. The best we can do now is order them logically.

    listen = subparser.add_parser(
        "listen", parents=[parent], help="Open a terminal to receive UART data"
    )
    listen.add_argument(
        "--port",
        "-p",
        "--device",
        "-d",
        help="The serial port or device name to use",
        metavar="STR",
    )
    listen.add_argument(
        "--timestamp", help="Prepend output with a timestamp", action="store_true"
    )
    listen.add_argument(
        "--count", help="Prepend output with a message counter", action="store_true"
    )
    listen.add_argument("--rtt", action="store_true", help="Use Segger RTT to listen.")
    listen.add_argument(
        "--board",
        default=None,
        help="Specify the board that is being read from. Only used with --rtt.",
    )
    listen.add_argument(
        "--jlink", action="store_true", help="Use JLinkExe. Only used with --rtt."
    )
    listen.add_argument(
        "--openocd", action="store_true", help="Use OpenOCD. Only used with --rtt."
    )
    listen.add_argument(
        "--jlink-cmd", help="The JLinkExe binary to invoke. Only used with --rtt."
    )
    listen.add_argument(
        "--jlink-rtt-cmd",
        help="The JLinkRTTClient binary to invoke. Only used with --rtt.",
    )
    listen.add_argument(
        "--jlink-device",
        default="cortex-m0",
        help="The device type to pass to JLinkExe. Only used with --rtt.",
    )
    listen.add_argument(
        "--jlink-speed",
        default=1200,
        help="The JLink speed to pass to JLinkExe. Only used with --rtt.",
    )
    listen.add_argument(
        "--jlink-if",
        default="swd",
        help="The interface type to pass to JLinkExe. Only used with --rtt.",
    )
    listen.add_argument(
        "--openocd-board",
        help="The cfg file in OpenOCD `board` folder. Only used with --rtt.",
    )
    listen.add_argument(
        "--openocd-cmd",
        default="openocd",
        help="The openocd binary to invoke. Only used with --rtt.",
    )
    listen.add_argument(
        "--openocd-options",
        default=[],
        help="Tockloader-specific flags to direct how Tockloader uses OpenOCD. Only used with --rtt.",
        nargs="*",
    )
    listen.add_argument(
        "--openocd-commands",
        default={},
        type=lambda kv: kv.split("=", 1),
        action=helpers.ListToDictAction,
        help='Directly specify which OpenOCD commands to use for "program", "read", or "erase" actions. Example: "program=flash write_image erase {{binary}} {address:#x};verify_image {{binary}} {address:#x};" Only used with --rtt.',
        nargs="*",
    )
    listen.set_defaults(func=command_listen)

    install = subparser.add_parser(
        "install",
        parents=[parent, parent_apps, parent_channel],
        help="Install apps on the board",
    )
    install.set_defaults(func=command_install)
    install.add_argument("tab", help="The TAB or TABs to install", nargs="*")
    install.add_argument(
        "--no-replace",
        help="Install apps again even if they are already there",
        action="store_true",
    )
    install.add_argument(
        "--make", help="Run `make` before loading an application", action="store_true"
    )
    install.add_argument(
        "--erase",
        help="Erase all existing apps before installing.",
        action="store_true",
    )
    install.add_argument(
        "--sticky", help="Make the installed app(s) sticky.", action="store_true"
    )
    install.add_argument(
        "--corrupt-tbf",
        help="Modify the root TBF header when installing an app.",
        nargs=2,
    )
    install.add_argument(
        "--preserve-order",
        help="Install all specified TABs in the order they are on command line.",
        action="store_true",
    )
    install.add_argument(
        "--layout",
        help="Specify layout of installed apps. Implies --erase and --force. Use T and p<size>.",
        nargs=1,
    )

    update = subparser.add_parser(
        "update",
        parents=[parent, parent_apps, parent_channel],
        help="Update an existing app with this version",
    )
    update.set_defaults(func=command_update)
    update.add_argument("tab", help="The TAB or TABs to replace", nargs="*")

    uninstall = subparser.add_parser(
        "uninstall",
        parents=[parent, parent_apps, parent_channel],
        help="Remove an already flashed app",
    )
    uninstall.set_defaults(func=command_uninstall)
    uninstall.add_argument("name", help="The name of the app(s) to remove", nargs="*")

    listcmd = subparser.add_parser(
        "list",
        parents=[parent, parent_apps, parent_channel, parent_format],
        help="List the apps installed on the board",
    )
    listcmd.set_defaults(func=command_list)
    listcmd.add_argument(
        "--verbose", "-v", help="Print more information", action="store_true"
    )
    listcmd.add_argument(
        "--quiet",
        "-q",
        help="Print just a list of application names",
        action="store_true",
    )
    listcmd.add_argument(
        "--map",
        help="Print a table with apps and addresses",
        action="store_true",
    )
    listcmd.add_argument(
        "--verify-credentials",
        help="Check credentials with a list of public keys",
        nargs="*",
    )

    info = subparser.add_parser(
        "info",
        parents=[parent, parent_apps, parent_channel, parent_format],
        help="Verbose information about the connected board",
    )
    info.set_defaults(func=command_info)

    eraseapps = subparser.add_parser(
        "erase-apps",
        parents=[parent, parent_apps, parent_channel],
        help="Delete apps from the board",
    )
    eraseapps.set_defaults(func=command_erase_apps)

    enableapp = subparser.add_parser(
        "enable-app",
        parents=[parent, parent_apps, parent_channel],
        help="Enable an app so the kernel runs it",
    )
    enableapp.set_defaults(func=command_enable_app)
    enableapp.add_argument("name", help="The name of the app(s) to enable", nargs="*")

    disableapp = subparser.add_parser(
        "disable-app",
        parents=[parent, parent_apps, parent_channel],
        help="Disable an app so it will not be started",
    )
    disableapp.set_defaults(func=command_disable_app)
    disableapp.add_argument("name", help="The name of the app(s) to disable", nargs="*")

    stickyapp = subparser.add_parser(
        "sticky-app",
        parents=[parent, parent_apps, parent_channel],
        help="Make an app sticky so it is hard to erase",
    )
    stickyapp.set_defaults(func=command_sticky_app)
    stickyapp.add_argument("name", help="The name of the app(s) to sticky", nargs="*")

    unstickyapp = subparser.add_parser(
        "unsticky-app",
        parents=[parent, parent_apps, parent_channel],
        help="Make an app unsticky (the normal setting)",
    )
    unstickyapp.set_defaults(func=command_unsticky_app)
    unstickyapp.add_argument(
        "name", help="The name of the app(s) to unsticky", nargs="*"
    )

    flash = subparser.add_parser(
        "flash", parents=[parent, parent_channel], help="Flash binaries to the chip"
    )
    flash.set_defaults(func=command_flash)
    flash.add_argument(
        "binary", help="The binary file or files to flash to the chip", nargs="+"
    )
    flash.add_argument(
        "--address",
        "-a",
        help="Address to flash the binary at",
        type=lambda x: int(x, 0),
        default=0x30000,
    )
    flash.add_argument(
        "--pad",
        help="Optional number of bytes to pad and value to use",
        nargs=2,
        type=lambda x: int(x, 0),
    )
    flash.add_argument(
        "--set-attribute",
        help="Key-value attribute pair to set if not already set",
        nargs=2,
        action="append",
    )

    read = subparser.add_parser(
        "read", parents=[parent, parent_channel], help="Read arbitrary flash memory"
    )
    read.set_defaults(func=command_read)
    read.add_argument(
        "address",
        help="Address to read from",
        type=lambda x: int(x, 0),
        default=0x30000,
    )
    read.add_argument(
        "length", help="Number of bytes to read", type=lambda x: int(x, 0), default=512
    )

    write = subparser.add_parser(
        "write",
        parents=[parent, parent_channel],
        help="Write arbitrary flash memory with constant value",
    )
    write.set_defaults(func=command_write)
    write.add_argument(
        "address", help="Address to write to", type=lambda x: int(x, 0), default=0x30000
    )
    write.add_argument(
        "length", help="Number of bytes to write", type=lambda x: int(x, 0), default=512
    )
    write.add_argument(
        "value", help="Value to write", type=lambda x: int(x, 0), default=0xFF
    )

    dump_flash_page = subparser.add_parser(
        "dump-flash-page",
        parents=[parent, parent_channel],
        help="Read a page of flash from the board",
    )
    dump_flash_page.set_defaults(func=command_dump_flash_page)
    dump_flash_page.add_argument(
        "page", help="The number of the page to read", type=lambda x: int(x, 0)
    )

    listattributes = subparser.add_parser(
        "list-attributes",
        parents=[parent, parent_channel, parent_format],
        help="List attributes stored on the board",
    )
    listattributes.set_defaults(func=command_list_attributes)

    setattribute = subparser.add_parser(
        "set-attribute",
        parents=[parent, parent_channel],
        help="Store attribute on the board",
    )
    setattribute.set_defaults(func=command_set_attribute)
    setattribute.add_argument("key", help="Attribute key")
    setattribute.add_argument("value", help="Attribute value")

    removeattribute = subparser.add_parser(
        "remove-attribute",
        parents=[parent, parent_channel],
        help="Remove attribute from the board",
    )
    removeattribute.set_defaults(func=command_remove_attribute)
    removeattribute.add_argument("key", help="Attribute key")

    setstartaddress = subparser.add_parser(
        "set-start-address",
        parents=[parent, parent_channel],
        help="Set bootloader jump address",
    )
    setstartaddress.set_defaults(func=command_set_start_address)
    setstartaddress.add_argument(
        "address", help="Start address", type=lambda x: int(x, 0), default=0x10000
    )

    inspect_tab = subparser.add_parser(
        "inspect-tab", parents=[parent], help="Get details about a TAB"
    )
    inspect_tab.set_defaults(func=command_inspect_tab)
    inspect_tab.add_argument(
        "--crt0-header", help="Dump crt0 header as well", action="store_true"
    )
    inspect_tab.add_argument(
        "--verify-credentials",
        help="Check credentials with a list of public keys",
        nargs="+",
    )
    inspect_tab.add_argument(
        "--tbf-binary", help="Dump the entire TBF binary", action="store_true"
    )
    inspect_tab.add_argument("tab", help="The TAB or TABs to inspect", nargs="*")

    #########
    ## TBF ##
    #########

    tbf = subparser.add_parser(
        "tbf",
        help="Commands for interacting with TBFs inside of TAB files",
    )

    tbf_subparser = tbf.add_subparsers(
        title="Commands", metavar="            ", dest="subcommand"
    )

    ##############
    ## TBF TLVS ##
    ##############

    tbf_tlv = tbf_subparser.add_parser(
        "tlv",
        help="Commands for interacting with TLV structures in TBFs",
    )

    tbf_tlv_subparser = tbf_tlv.add_subparsers(
        title="Commands", metavar="", dest="subsubcommand"
    )

    ## ADD

    tbf_tlv_add = tbf_tlv_subparser.add_parser(
        "add",
        help="Add a TLV to the TBF header",
    )
    tbf_tlv_add_subparser = tbf_tlv_add.add_subparsers(
        title="Commands", metavar="", dest="subsubsubcommand"
    )

    # Add subcommands for adding each TLV so we can specify number of arguments.
    for tlvname, nargs, param_help in tbfh.get_addable_tlvs():
        tbf_tlv_add_tlv = tbf_tlv_add_subparser.add_parser(
            tlvname,
            parents=[parent],
            help="Add a {} TLV to the TBF header".format(tlvname),
        )
        tbf_tlv_add_tlv.set_defaults(func=command_tbf_tlv_add)
        tbf_tlv_add_tlv.add_argument("parameters", help=param_help, nargs=nargs)
        tbf_tlv_add_tlv.add_argument("tab", help="The TAB or TABs to modify", nargs="*")

    ## MODIFY

    tbf_tlv_modify = tbf_tlv_subparser.add_parser(
        "modify",
        parents=[parent],
        help="Modify a field in a TLV in the TBF header",
    )
    tbf_tlv_modify.set_defaults(func=command_tbf_tlv_modify)
    tbf_tlv_modify.add_argument(
        "tlvname",
        help="TLV name",
        choices=["base"] + tbfh.get_tlv_names(),
    )
    tbf_tlv_modify.add_argument("field", help="TLV field name")
    tbf_tlv_modify.add_argument(
        "value", help="TLV field new value", type=helpers.number_or
    )
    tbf_tlv_modify.add_argument("tab", help="The TAB or TABs to modify", nargs="*")

    ## DELETE

    tbf_tlv_delete = tbf_tlv_subparser.add_parser(
        "delete", parents=[parent], help="Delete a TLV from the TBF header"
    )
    tbf_tlv_delete.set_defaults(func=command_tbf_tlv_delete)
    tbf_tlv_delete.add_argument(
        "tlvname",
        help="TLV name",
        choices=tbfh.get_tlv_names(),
    )
    tbf_tlv_delete.add_argument("tab", help="The TAB or TABs to modify", nargs="*")

    #####################
    ## TBF CREDENTIALS ##
    #####################

    parent_tbf_credential = argparse.ArgumentParser(add_help=False)
    parent_tbf_credential.add_argument(
        "credential_type",
        help="Credential type to add",
        choices=[
            "cleartext_id",
            "sha256",
            "sha384",
            "sha512",
            "ecdsap256",
            "hmac_sha256",
            "rsa4096",
            "rsa2048",
        ],
    )

    tbf_credential = tbf_subparser.add_parser(
        "credential",
        help="Commands for interacting with credentials in TBFs",
    )

    tbf_credential_subparser = tbf_credential.add_subparsers(
        title="Commands", metavar=""
    )

    tbf_credential_add = tbf_credential_subparser.add_parser(
        "add",
        parents=[parent_tbf_credential, parent],
        help="Add a credential TLV from the TBF footer",
    )
    tbf_credential_add.set_defaults(func=command_tbf_credential_add)
    tbf_credential_add.add_argument(
        "--public-key",
        help="Public key to use in signature credential",
        nargs=1,
    )
    tbf_credential_add.add_argument(
        "--private-key",
        help="Private key to use in signing credential",
        nargs=1,
    )
    tbf_credential_add.add_argument(
        "--cleartext-id",
        help="ID to use as credential",
        nargs=1,
        type=lambda x: int(x, 0),
    )
    tbf_credential_add.add_argument("tab", help="The TAB or TABs to modify", nargs="*")

    tbf_credential_delete = tbf_credential_subparser.add_parser(
        "delete",
        parents=[parent_tbf_credential, parent],
        help="Delete a credential TLV from the TBF footer",
    )
    tbf_credential_delete.set_defaults(func=command_tbf_credential_delete)
    tbf_credential_delete.add_argument(
        "tab", help="The TAB or TABs to modify", nargs="*"
    )

    ###########
    ## TICKV ##
    ###########

    parent_tickv = argparse.ArgumentParser(add_help=False)
    parent_tickv.add_argument(
        "--tickv-file", help="The binary file containing the TicKV database"
    )
    parent_tickv.add_argument(
        "--start-address",
        help="Location in flash of the start of the TicKV database",
        type=lambda x: int(x, 0),
        default=-1,
    )
    parent_tickv.add_argument(
        "--region-size",
        help="Size in bytes of each TicKV region",
        type=lambda x: int(x, 0),
        default=0,
    )
    parent_tickv.add_argument(
        "--number-regions",
        help="Number of regions in the TicKV database",
        type=lambda x: int(x, 0),
        default=0,
    )

    tickv = subparser.add_parser(
        "tickv", help="Commands for interacting with a TicKV database"
    )

    tickv_subparser = tickv.add_subparsers(title="Commands", metavar="")

    tickv_get = tickv_subparser.add_parser(
        "get",
        parents=[parent, parent_channel, parent_format, parent_tickv],
        help="Get a key, value pair from a tickv database",
    )
    tickv_get.set_defaults(func=command_tickv_get)
    tickv_get.add_argument(
        "key",
        help="Key to fetch from the TicKV database",
    )

    tickv_dump = tickv_subparser.add_parser(
        "dump",
        parents=[parent, parent_channel, parent_format, parent_tickv],
        help="Display the contents of a tickv database",
    )
    tickv_dump.set_defaults(func=command_tickv_dump)

    tickv_invalidate = tickv_subparser.add_parser(
        "invalidate",
        parents=[parent, parent_channel, parent_format, parent_tickv],
        help="Invalidate an item in a tickv database",
    )
    tickv_invalidate.set_defaults(func=command_tickv_invalidate)
    tickv_invalidate.add_argument(
        "key",
        help="Key to invalidate from the TicKV database",
    )

    tickv_append = tickv_subparser.add_parser(
        "append",
        parents=[parent, parent_channel, parent_format, parent_tickv],
        help="Add a key,value pair to a tickv database",
    )
    tickv_append.set_defaults(func=command_tickv_append)
    tickv_append.add_argument(
        "key",
        help="Key to append to the TicKV database",
    )
    tickv_append.add_argument(
        "value", help="Value to append to the TicKV database", nargs="?"
    )
    tickv_append.add_argument(
        "--value-file",
        help="Filepath of contents to append from the TicKV database",
    )
    tickv_append.add_argument(
        "--write-id",
        help="ID number to use when writing the key-value object",
        type=lambda x: int(x, 0),
        default=0,
    )

    tickv_append_rsa_key = tickv_subparser.add_parser(
        "append-rsa-key",
        parents=[parent, parent_channel, parent_format, parent_tickv],
        help="Add a public RSA key to a tickv database",
    )
    tickv_append_rsa_key.set_defaults(func=command_tickv_append_rsa_key)
    tickv_append_rsa_key.add_argument(
        "rsa_key_file",
        help="Filepath of the RSA key",
    )

    tickv_cleanup = tickv_subparser.add_parser(
        "cleanup",
        parents=[parent, parent_channel, parent_format, parent_tickv],
        help="Cleanup a tickv database by removing invalid objects",
    )
    tickv_cleanup.set_defaults(func=command_tickv_cleanup)

    tickv_reset = tickv_subparser.add_parser(
        "reset",
        parents=[parent, parent_channel, parent_format, parent_tickv],
        help="Reset/erase a tickv database",
    )
    tickv_reset.set_defaults(func=command_tickv_reset)

    tickv_hash = tickv_subparser.add_parser(
        "hash",
        parents=[parent, parent_channel, parent_format, parent_tickv],
        help="Hash a key for a tickv database",
    )
    tickv_hash.set_defaults(func=command_tickv_hash)
    tickv_hash.add_argument(
        "key",
        help="Key to hash",
    )

    #############################
    # UNDERSTANDING TOCKLOADER ##
    #############################

    list_known_boards = subparser.add_parser(
        "list-known-boards",
        help="List the boards that Tockloader explicitly knows about",
    )
    list_known_boards.set_defaults(func=command_list_known_boards)

    ############################
    # END OF OPTIONS/COMMANDS ##
    ############################

    argcomplete.autocomplete(parser)
    args, unknown_args = parser.parse_known_args()

    # Warn about unknown arguments, suggest tockloader update.
    if len(unknown_args) > 0:
        logging.warning("Unknown arguments passed. You may need to update tockloader.")
        for unknown_arg in unknown_args:
            logging.warning('Unknown argument "{}"'.format(unknown_arg))

    # Concat the args before the command with those that were specified
    # after the command. This is a workaround because for some reason python
    # won't parse a set of parent options before the "command" option
    # (or it is getting overwritten).
    for key, value in vars(before_command_args[0]).items():
        if getattr(args, key) != value:
            setattr(args, key, value)

    # Change logging level if `--debug` was supplied.
    if args.debug:
        logging.getLogger("").setLevel(logging.DEBUG)

    # Handle deprecated arguments.
    # --jtag is now --jlink. If --jtag was passed copy it to --jlink.
    if hasattr(args, "jtag") and args.jtag:
        logging.warning("Deprecation Notice! --jtag has been replaced with --jlink.")
        setattr(args, "jlink", args.jtag)
    if hasattr(args, "jtag_device") and args.jtag_device != "cortex-m0":
        setattr(args, "jlink_device", args.jtag_device)

    if hasattr(args, "func"):
        try:
            args.func(args)
        except TockLoaderException as e:
            logging.error(e)
            sys.exit(1)
    else:
        logging.error("Missing Command.\n")

        if hasattr(args, "command") and getattr(args, "command") != None:

            def print_help_command(a, title, p):
                """
                Recurse the parser tree to print the help for the command which
                is incomplete

                a = args
                p = parser
                """
                if hasattr(a, title):
                    subtitle = "{}{}".format("sub", title)
                    title_value = getattr(a, title)
                    for action in p._actions:
                        if isinstance(action, argparse._SubParsersAction):
                            if not hasattr(a, subtitle) or getattr(a, subtitle) == None:
                                print(action.choices[title_value].format_help())
                            else:
                                print_help_command(
                                    a, subtitle, action.choices[title_value]
                                )

            # If this is a invocation with subcommands, print the relevant help
            # at the layer of the incorrect subcommand.
            print_help_command(args, "command", parser)
        else:
            parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
