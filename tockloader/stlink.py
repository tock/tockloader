"""
Interface for boards using STLink.
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


class STLink(BoardInterface):
    def __init__(self, args):
        # Must call the generic init first.
        super().__init__(args)

        # Command can be passed in as an argument, otherwise use default.
        self.stinfo_cmd = getattr(self.args, "stinfo_cmd")
        self.stflash_cmd = getattr(self.args, "stflash_cmd")

    def attached_board_exists(self):
        # Get a list of attached devices, check if that list has at least
        # one entry.
        emulators = self._list_emulators()
        return len(emulators) > 0

    def open_link_to_board(self):
        # It's very important that we know the board. There are three ways we
        # can learn that: 1) use the known boards struct, 2) have it passed in
        # via a command line option, 3) guess it from what we can see attached
        # to the host. If options 1 and 2 aren't done, then we try number 3!
        if self.board == None:
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

            # And we may need to setup other common board settings.
            self._configure_from_known_boards()

    def _gather_stlink_cmdline(self, command, binary, write=True):
        """
        - `command`: st-flash command. Use {binary} for where the name of the
          binary file should be substituted.
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

            # Update the command with the name of the binary file
            command = command.format(binary=temp_bin.name)
        else:
            temp_bin = None

        return (
            "{stflash_cmd} --connect-under-reset {cmd}".format(
                stflash_cmd=self.stflash_cmd,
                cmd=command,
            ),
            temp_bin,
        )

    def _run_stlink_command(self, command, binary, write=True):
        stlink_command, temp_bin = self._gather_stlink_cmdline(command, binary, write)

        logging.debug('Running "{}".'.format(stlink_command.replace("$", "\$")))

        def print_output(subp):
            response = ""
            if subp.stdout:
                response += subp.stdout.decode("utf-8")
            if subp.stderr:
                response += subp.stderr.decode("utf-8")
            logging.info(response)
            return response

        p = subprocess.run(
            shlex.split(stlink_command), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if p.returncode != 0:
            logging.error(
                "ERROR: st-flash returned with error code " + str(p.returncode)
            )
            out = print_output(p)
            raise TockLoaderException("st-flash error")
        elif self.args.debug:
            print_output(p)

        # check that there was a JTAG programmer and that it found a device
        stdout = p.stdout.decode("utf-8")
        if "Couldn't find any ST-Link devices" in stdout:
            raise TockLoaderException("ERROR: Cannot find hardware. Is USB attached?")

        if write == False:
            # Wanted to read binary, so lets pull that
            temp_bin.seek(0, 0)
            return temp_bin.read()

    def _list_emulators(self):
        """
        Return a list of board names that are attached to the host.
        """
        stlink_command = "{stinfo_cmd} --descr --connect-under-reset".format(
            stinfo_cmd=self.stinfo_cmd
        )

        # These are the magic strings in the output of st-info we are looking
        # for.
        magic_strings_boards = [
            ("STM32F42x_F43x", "stm32f4discovery"),
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
            logging.debug('Running "{}".'.format(stlink_command))
            p = subprocess.run(
                shlex.split(stlink_command),
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
                logging.debug("st-info does not seem to exist.")
                logging.debug(e)
        except:
            # Any other error just ignore...this is only for convenience.
            pass

        return emulators

    def flash_binary(self, address, binary, pad=False):
        """
        Write using st-flash `write` command.
        """
        # st-flash write command
        command = "write {{binary}} {address:#x}"

        # Substitute the key arguments.
        command = command.format(address=address)

        logging.debug('Expanded program command: "{}"'.format(command))

        self._run_stlink_command(command, binary)

    def read_range(self, address, length):
        # st-flash read
        command = "read {{binary}} {address:#x} {length}"

        logging.debug('Using read command: "{}"'.format(command))

        # Substitute the key arguments.
        command = command.format(address=address, length=length)

        logging.debug('Expanded read command: "{}"'.format(command))

        # Always return a valid byte array (like the serial version does)
        read = bytes()
        result = self._run_stlink_command(command, None, write=False)
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
        if self.board and self.arch and self.page_size > 0:
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
            if attribute and attribute["key"] == "pagesize" and self.page_size == 0:
                self.page_size = attribute["value"]

        # We might need to fill in if we only got a "board" attribute.
        self._configure_from_known_boards()

        # Check that we learned what we needed to learn.
        if self.board is None:
            raise TockLoaderException("Could not determine the current board")
        if self.arch is None:
            raise TockLoaderException("Could not determine the current arch")
        if self.page_size == 0:
            raise TockLoaderException("Could not determine the current page size")
