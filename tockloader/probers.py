"""
Interface for boards using probe-rs.
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


class ProbeRs(BoardInterface):
    def __init__(self, args):
        # Must call the generic init first.
        super().__init__(args)

        # Command can be passed in as an argument, otherwise use default.
        self.probers_cmd = getattr(self.args, "probers_cmd")

        # Store the serial number if provided
        self.probers_probe = getattr(self.args, "probers_probe")

    def open_link_to_board(self):
        # Use command line arguments to set the necessary settings.
        self.probers_board = getattr(self.args, "probers_board")
        self.probers_prefix = ""

        # If the user specified a board, use that configuration to fill in any
        # missing settings.
        if self.board and self.board in self.KNOWN_BOARDS:
            logging.info('Using settings from KNOWN_BOARDS["{}"]'.format(self.board))
            board = self.KNOWN_BOARDS[self.board]

            # Set required settings

            # `probers_board` is the --chip to use.
            if self.probers_board == None:
                if "probers" in board:
                    if "chip" in board["probers"]:
                        self.probers_board = board["probers"]["chip"]

            # And we may need to setup other common board settings.
            self._configure_from_known_boards()

        if self.probers_board == None:
            raise TockLoaderException(
                "Unknown probe-rs board name. You must pass --probers-board."
            )

    def _list_probes(self):
        """
        Return a list of board names that are attached to the host.
        """
        probers_command = f"{self.probers_cmd} --list"

        # These are the magic strings in the output of probe-rs we are looking
        # for.
        magic_strings_boards = [
            ("J-Link OB-SAM3U128-V2-NordicSemi", "nrf52dk"),
            ("J-Link OB-nRF5340-NordicSemi", "nrf52dk"),
        ]

        probes = []

        def print_output(subp):
            response = ""
            if subp.stdout:
                response += subp.stdout.decode("utf-8")
            if subp.stderr:
                response += subp.stderr.decode("utf-8")
            logging.info(response)
            return response

        try:
            logging.debug('Running "{}".'.format(probers_command))
            p = subprocess.run(
                shlex.split(probers_command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if self.args.debug:
                print_output(p)

            # Parse all output to look for a device.
            stdouterr = p.stdout.decode("utf-8") + p.stderr.decode("utf-8")

            for magic_string, board in magic_strings_boards:
                if magic_string in stdouterr:
                    probes.append(board)
        except FileNotFoundError as e:
            if self.args.debug:
                logging.debug("probe-rs does not seem to exist.")
                logging.debug(e)
        except:
            # Any other error just ignore...this is only for convenience.
            pass

        return probes

    def _gather_probers_cmdline(self, command, binary, write=True):
        """
        - `commands`: List of probe-rs commands. Use {binary} for where the name
          of the binary file should be substituted.
        - `binary`: A bytes() object that will be used to write to the board.
        - `write`: Set to true if the command writes binaries to the board. Set
          to false if the command will read bits from the board.
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
            command = command.format(binary=temp_bin.name)
        else:
            temp_bin = None

        # Add a specific probe if provided
        specific_probe = ""
        if hasattr(self, "probers_probe") and self.probers_probe:
            specific_probe = "--probe {};".format(self.probers_probe)

        return (
            f"{self.probers_cmd} {command} --chip {self.probers_board} {specific_probe}",
            temp_bin,
        )

    def _run_probers_commands(self, command, binary, write=True):
        probers_command, temp_bin = self._gather_probers_cmdline(command, binary, write)

        logging.debug('Running "{}".'.format(probers_command.replace("$", "\\$")))

        stderr = ""
        with subprocess.Popen(
            shlex.split(probers_command),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
        ) as p:
            for line in p.stdout:
                print(line, end="")
            for line in p.stderr:
                stderr += line

        if p.returncode != 0:
            logging.error(
                "ERROR: probe-rs returned with error code " + str(p.returncode)
            )
            logging.info(stderr)
            raise TockLoaderException("probe-rs error")
        elif self.args.debug:
            logging.debug(stderr)

        if write == False:
            # Wanted to read binary, so lets pull that
            temp_bin.seek(0, 0)
            return temp_bin.read()

    def flash_binary(self, address, binary, pad=False):
        """
        Write using probe-rs `download` command.
        """
        # The "normal" flash command uses `program`.
        command = "download {{binary}} --binary-format bin --base-address {address:#x}"

        # Translate the address from MCU address space to probe-rs
        # command addressing.
        address = self.translate_address(address)

        # Substitute the key arguments.
        command = command.format(address=address)

        logging.debug('Expanded program command: "{}"'.format(command))

        self._run_probers_commands(command, binary)

    def read_range(self, address, length):
        # The normal read command uses `dump_image`.
        command = "read --output {{binary}} --format binary b8 {address:#x} {length} "

        # Translate the address from MCU address space to probe-rs
        # command addressing.
        address = self.translate_address(address)

        logging.debug('Using read command: "{}"'.format(command))

        # Substitute the key arguments.
        command = command.format(address=address, length=length)

        logging.debug('Expanded read command: "{}"'.format(command))

        # Always return a valid byte array (like the serial version does)
        read = bytes()
        result = self._run_probers_commands(command, None, write=False)
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
        if self.board and self.arch and self.probers_board and self.page_size > 0:
            # These are already set! Yay we are done.
            return

        # We might need to fill in if we only got a "board" attribute.
        self._configure_from_known_boards()

        # Check that we learned what we needed to learn.
        if self.board is None:
            raise TockLoaderException("Could not determine the current board")
        if self.arch is None:
            raise TockLoaderException("Could not determine the current arch")
