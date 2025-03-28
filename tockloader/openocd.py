"""
Interface for boards using OpenOCD.

This interface has a special option called `openocd_options` which is just a
list of strings that are interpreted as flags to the OpenOCD class in this file.
These allow individual boards to have custom operations in a semi-reasonable
way. Note, I just made up the string (flag) names; they are not passed to
OpenOCD directly.
"""

import logging
import platform
import shlex
import socket
import subprocess
import tempfile
import time

from .board_interface import BoardInterface
from .exceptions import TockLoaderException

# global static variable for collecting temp files for Windows
collect_temp_files = []


class OpenOCD(BoardInterface):
    def __init__(self, args):
        # Must call the generic init first.
        super().__init__(args)

        # Command can be passed in as an argument, otherwise use default.
        self.openocd_cmd = getattr(self.args, "openocd_cmd")

        # Store the serial number if provided
        self.openocd_serial_number = getattr(self.args, "openocd_serial_number")

    def attached_board_exists(self):
        # Get a list of attached devices, check if that list has at least
        # one entry.
        emulators = self._list_emulators()
        return len(emulators) > 0

    def open_link_to_board(self):
        # Use command line arguments to set the necessary settings.
        self.openocd_board = getattr(self.args, "openocd_board")
        self.openocd_options = getattr(self.args, "openocd_options")
        self.openocd_commands = getattr(self.args, "openocd_commands")
        self.openocd_prefix = ""

        # It's very important that we know the openocd_board. There are three
        # ways we can learn that: 1) use the known boards struct, 2) have it
        # passed in via a command line option, 3) guess it from what we can see
        # attached to the host. If options 1 and 2 aren't done, then we try
        # number 3!
        if self.board == None and self.openocd_board == None:
            emulators = self._list_emulators()
            if len(emulators) > 0:
                # Just use the first one. Should be good enough to just assume
                # there is only one for now.
                self.board = emulators[0]

        # If the user specified a board, use that configuration to fill in any
        # missing settings.
        if self.board and self.board in self.KNOWN_BOARDS:
            logging.info('Using settings from KNOWN_BOARDS["{}"]'.format(self.board))
            board = self.KNOWN_BOARDS[self.board]

            # Set required settings

            # `openocd_board` is the .cfg file to use.
            if self.openocd_board == None:
                if "openocd" in board:
                    if "cfg" in board["openocd"]:
                        self.openocd_board = board["openocd"]["cfg"]
                    else:
                        # No .cfg file listed, use "external" as a way to denote
                        # this.
                        self.openocd_board = "external"

            # Set optional settings
            if self.openocd_options == [] and "options" in board["openocd"]:
                self.openocd_options = board["openocd"]["options"]
            if self.openocd_prefix == "" and "prefix" in board["openocd"]:
                self.openocd_prefix = board["openocd"]["prefix"]
            if self.openocd_commands == {} and "commands" in board["openocd"]:
                self.openocd_commands = board["openocd"]["commands"]

            # And we may need to setup other common board settings.
            self._configure_from_known_boards()

        if self.openocd_board == None:
            raise TockLoaderException(
                "Unknown OpenOCD board name. You must pass --openocd-board."
            )

    def _gather_openocd_cmdline(self, commands, binary, write=True, exit=True):
        """
        - `commands`: List of openocd commands. Use {binary} for where the name
          of the binary file should be substituted.
        - `binary`: A bytes() object that will be used to write to the board.
        - `write`: Set to true if the command writes binaries to the board. Set
          to false if the command will read bits from the board.
        - `exit`: When `True`, openocd will exit after executing commands.
        """

        # in Windows, you can't mark delete bc they delete too fast
        delete = platform.system() != "Windows"
        if self.args.debug:
            delete = False

        if binary or not write:
            temp_bin = tempfile.NamedTemporaryFile(
                mode="w+b", suffix=".bin", delete=delete
            )
            if write:
                temp_bin.write(binary)

            temp_bin.flush()

            if platform.system() == "Windows":
                # For Windows, forward slashes need to be escaped
                temp_bin.name = temp_bin.name.replace("\\", "\\\\\\")
                # For Windows, files need to be manually deleted
                global collect_temp_files
                collect_temp_files += [temp_bin.name]

            # Update the commands with the name of the binary file
            commands = [command.format(binary=temp_bin.name) for command in commands]
        else:
            temp_bin = None

        # Create the actual openocd command and run it. All of this can be
        # customized if needed for an unusual board.

        # Defaults.
        prefix = ""
        source = "source [find board/{board}];".format(board=self.openocd_board)

        cmd_prefix = "init; reset init; halt;"
        cmd_suffix = ""
        serial_no_cmd = ""

        # Add serial number specification if provided
        if hasattr(self, "openocd_serial_number") and self.openocd_serial_number:
            serial_no_cmd = "adapter serial {};".format(self.openocd_serial_number)

        # Do the customizations
        if "workareazero" in self.openocd_options:
            prefix = "set WORKAREASIZE 0;"
        if self.openocd_prefix:
            prefix = self.openocd_prefix
        if self.openocd_board == "external":
            source = ""
        if "noreset" in self.openocd_options:
            cmd_prefix = "init; halt;"
        if "nocmdprefix" in self.openocd_options:
            cmd_prefix = ""
        if "resume" in self.openocd_options:
            cmd_suffix = "soft_reset_halt; resume;"
        if exit:
            cmd_suffix += "exit"

        command_param = (
            "{prefix} {serial_no_cmd} {source} {cmd_prefix} {cmd} {cmd_suffix}".format(
                prefix=prefix,
                serial_no_cmd=serial_no_cmd,
                source=source,
                cmd_prefix=cmd_prefix,
                cmd="; ".join(commands),
                cmd_suffix=cmd_suffix,
            )
        )

        return (
            "{openocd_cmd} -c {cmd} --debug".format(
                openocd_cmd=self.openocd_cmd,
                cmd=shlex.quote(command_param),
            ),
            temp_bin,
        )

    def _run_openocd_commands(self, commands, binary, write=True):
        openocd_command, temp_bin = self._gather_openocd_cmdline(
            [commands], binary, write
        )

        logging.debug('Running "{}".'.format(openocd_command.replace("$", "\\$")))

        def print_output(subp):
            response = ""
            if subp.stdout:
                response += subp.stdout.decode("utf-8")
            if subp.stderr:
                response += subp.stderr.decode("utf-8")
            logging.info(response)
            return response

        p = subprocess.run(
            shlex.split(openocd_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if p.returncode != 0:
            logging.error(
                "ERROR: openocd returned with error code " + str(p.returncode)
            )
            out = print_output(p)
            if "Can't find board/" in out:
                raise TockLoaderException(
                    "ERROR: Cannot find the board configuration file. \
You may need to update OpenOCD to the version in latest git master."
                )
            raise TockLoaderException("openocd error")
        elif self.args.debug:
            print_output(p)

        # check that there was a JTAG programmer and that it found a device
        stdout = p.stdout.decode("utf-8")
        if "Error: No J-Link device found." in stdout:
            raise TockLoaderException("ERROR: Cannot find hardware. Is USB attached?")

        if write == False:
            # Wanted to read binary, so lets pull that
            temp_bin.seek(0, 0)
            return temp_bin.read()

    def _list_emulators(self):
        """
        Return a list of board names that are attached to the host.
        """
        openocd_commands = []

        # I'm not sure there is a magic way to discover all attached OpenOCD
        # compatible devices. So, we do our best and try some.
        openocd_commands.append(
            '{openocd_cmd} -c "interface jlink"'.format(openocd_cmd=self.openocd_cmd)
        )
        openocd_commands.append(
            '{openocd_cmd} -c "interface cmsis-dap; transport select swd; source [find target/nrf52.cfg]; init; exit;"'.format(
                openocd_cmd=self.openocd_cmd
            )
        )
        openocd_commands.append(
            '{openocd_cmd} -c "source [find interface/ftdi/digilent-hs1.cfg]; ftdi_device_desc \\"Digilent USB Device\\"; adapter_khz 10000; transport select jtag; init; exit"'.format(
                openocd_cmd=self.openocd_cmd
            )
        )
        openocd_commands.append(
            '{openocd_cmd} -c "source [find interface/stlink.cfg]; transport select hla_swd; source [find target/stm32f4x.cfg]; init; exit;"'.format(
                openocd_cmd=self.openocd_cmd
            )
        )

        # These are the magic strings in the output of openocd we are looking
        # for. If there is a better way to do this then we should change. But,
        # this is the best I got for now. Magic string is what we want to see in
        # openocd output, board is the name in the known boards struct.
        magic_strings_boards = [
            ("J-Link OB-SAM3U128-V2-NordicSemi", "nrf52dk"),
            ("J-Link OB-nRF5340-NordicSemi", "nrf52dk"),
            ("(mfg: 0x049 (Xilinx), part: 0x3631, ver: 0x1)", "arty"),
            ("SWD DPIDR 0x2ba01477", "microbit_v2"),
            ("stm32f4x.cpu", "stm32f4discovery"),
        ]

        emulators = []

        def print_output(subp):
            response = ""
            if subp.stdout:
                response += subp.stdout.decode("utf-8")
            if subp.stderr:
                response += subp.stderr.decode("utf-8")
            logging.info(response)
            return response

        try:
            for openocd_command in openocd_commands:
                logging.debug('Running "{}".'.format(openocd_command))
                p = subprocess.run(
                    shlex.split(openocd_command),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if self.args.debug:
                    print_output(p)

                # Parse all output to look for a device.
                stdouterr = p.stdout.decode("utf-8") + p.stderr.decode("utf-8")

                for magic_string, board in magic_strings_boards:
                    if magic_string in stdouterr:
                        emulators.append(board)
        except FileNotFoundError as e:
            if self.args.debug:
                logging.debug("OpenOCD does not seem to exist.")
                logging.debug(e)
        except:
            # Any other error just ignore...this is only for convenience.
            pass

        return emulators

    def flash_binary(self, address, binary, pad=False):
        """
        Write using openocd `program` command.
        """
        # The "normal" flash command uses `program`.
        command = "program {{binary}} verify {address:#x}; reset;"

        # Check if the configuration wants to override the default program command.
        if "program" in self.openocd_commands:
            command = self.openocd_commands["program"]
        logging.debug('Using program command: "{}"'.format(command))

        # Now we workaround some openocd annoyances. Basically, not all chips
        # have openocd support that permits arbitrary writes of arbitrary sizes.
        # Some pass the flash limitations on to us as users. So, we are stuck
        # implementing read-then-write to make flash happy.
        address, binary = self._align_and_stretch_to_page(address, binary)

        # Translate the address from MCU address space to OpenOCD
        # command addressing.
        address = self.translate_address(address)

        # Substitute the key arguments.
        command = command.format(address=address)

        logging.debug('Expanded program command: "{}"'.format(command))

        self._run_openocd_commands(command, binary)

    def read_range(self, address, length):
        # The normal read command uses `dump_image`.
        command = "dump_image {{binary}} {address:#x} {length};"

        # Check if the configuration wants to override the default read command.
        if "read" in self.openocd_commands:
            command = self.openocd_commands["read"]

        # Translate the address from MCU address space to OpenOCD
        # command addressing.
        address = self.translate_address(address)

        logging.debug('Using read command: "{}"'.format(command))

        # Substitute the key arguments.
        command = command.format(address=address, length=length)

        logging.debug('Expanded read command: "{}"'.format(command))

        # Always return a valid byte array (like the serial version does)
        read = bytes()
        result = self._run_openocd_commands(command, None, write=False)
        if result:
            read += result

        # Check to make sure we didn't get too many
        if len(read) > length:
            read = read[0:length]

        return read

    def clear_bytes(self, address):
        logging.debug("Clearing bytes starting at {:#0x}".format(address))

        binary = bytes([0xFF] * 8)
        self.flash_binary(address, binary)

    def determine_current_board(self):
        if self.board and self.arch and self.openocd_board and self.page_size > 0:
            # These are already set! Yay we are done.
            return

        # If we get to here, we still have unknown settings and we need to
        # retrieve them from the board itself. If they exist, they will be
        # stored as attributes in the flash of the board.
        attributes = self.get_all_attributes()
        for attribute in attributes:
            if attribute and attribute["key"] == "board" and self.board == None:
                self.board = attribute["value"]
            if attribute and attribute["key"] == "arch" and self.arch == None:
                self.arch = attribute["value"]
            if attribute and attribute["key"] == "openocd":
                self.openocd_board = attribute["value"]
            if attribute and attribute["key"] == "pagesize" and self.page_size == 0:
                self.page_size = attribute["value"]

        # We might need to fill in if we only got a "board" attribute.
        self._configure_from_known_boards()

        # Check that we learned what we needed to learn.
        if self.board is None:
            raise TockLoaderException("Could not determine the current board")
        if self.arch is None:
            raise TockLoaderException("Could not determine the current arch")
        if self.openocd_board == "cortex-m0":
            raise TockLoaderException(
                "Could not determine the current openocd board name"
            )
        if self.page_size == 0:
            raise TockLoaderException("Could not determine the current page size")

    def run_terminal(self):
        self.open_link_to_board()
        logging.status("Starting OpenOCD RTT connection.")
        openocd_command, _ = self._gather_openocd_cmdline(
            [
                'rtt setup 0x20000000 65536 "SEGGER RTT"',
                "init",
                "rtt start",
                "rtt server start 9999 0",
                "reset run",
            ],
            None,
            exit=False,
        )

        logging.debug('Running "{}".'.format(openocd_command.replace("$", "\\$")))

        cleanup = []
        try:
            # This won't print messages from OpenOCD,
            # to avoid interfering with the console.
            ocd_p = subprocess.Popen(
                shlex.split(openocd_command),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            cleanup.append(ocd_p.wait)
            cleanup.append(ocd_p.kill)

            listener = socket.socket()
            MAX_TRIES = 3
            for i in range(MAX_TRIES):
                # Delay to give the connection time to start before running
                # the RTT listener.
                time.sleep(1)
                if ocd_p.poll():
                    return
                try:
                    listener.connect(("127.0.0.1", 9999))
                    logging.debug("Connecting to OpenOCD, attempt {}.".format(i))
                    break
                except ConnectionRefusedError:
                    if i == MAX_TRIES - 1:
                        raise

            cleanup.append(listener.close)
            logging.status("Listening for messages.")

            out = listener.makefile(mode="rb")
            cleanup.append(out.close)
            for out_line in iter(out.readline, ""):
                l = out_line.decode("utf-8", errors="replace")
                if not l.startswith("###RTT Client: *"):
                    print(l, end="")
        finally:
            logging.status("Stopping")
            for f in reversed(cleanup):
                f()

            openocd_command, _ = self._gather_openocd_cmdline(
                [
                    "init",
                    "reset halt",
                ],
                None,
            )
            subprocess.run(
                shlex.split(openocd_command),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
