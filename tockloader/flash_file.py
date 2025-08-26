"""
Interface to a board's flash file. This module does not directly interface to a
proper board, but can be used to manipulate a board's flash dump.
"""

import atexit
import logging
import os
import shlex
import subprocess

import appdirs
import toml

from .board_interface import BoardInterface
from .exceptions import TockLoaderException


class FlashFile(BoardInterface):
    """
    Implementation of `BoardInterface` for flash files.
    """

    LOCAL_BOARD_NAME_PATH = os.path.join(
        appdirs.user_data_dir("tockloader", "Tock"), "tockloader-local-board-v1"
    )
    LOCAL_BOARD_IMG_PATH = appdirs.user_data_dir("tockloader", "Tock")

    def __init__(self, args):
        super().__init__(args)

        # Store the passed filepath. If we are auto-discovering the board from
        # a know location on the user's filesystem, then this will be None.
        self.filepath = getattr(args, "flash_file", None)

        # Boards should limit the file size to match their flash. However, we
        # don't want users to accidentally create gigantic files using the
        # `--flash-file` flag, so we set a cap at 128 MB. If a future Tock board
        # needs more than that...well we can revisit this then.
        self.max_size = 0x8000000

        # Flash files almost certainly do not have bootloaders with an attribute
        # table. They could, but we don't really need to query the parameters
        # from that table because we should know it ourselves, since we would
        # also be what wrote the bootloader and attribute table to the flash
        # file.
        self.no_attribute_table = True

    def attached_board_exists(self):
        # For the flash file we are looking for a file with the
        # name "tockloader-local-board-v1". If that file exists then we use
        # the name of the board stored in the file as the "attached board".
        return os.path.exists(self.LOCAL_BOARD_NAME_PATH)

    def open_link_to_board(self):
        """
        Open a link to the board by opening the flash file for reading and
        writing.
        """
        if self.filepath == None:
            with open(self.LOCAL_BOARD_NAME_PATH, "r") as f:
                local_board = toml.load(f)

            for k, v in local_board.items():
                if k == "filepath":
                    self.filepath = os.path.join(self.LOCAL_BOARD_IMG_PATH, v)
                else:
                    setattr(self, k, v)

        # Load custom settings for the flash-file from the board definition.
        if self.board and self.board in self.KNOWN_BOARDS:
            logging.info('Using settings from KNOWN_BOARDS["{}"]'.format(self.board))
            board = self.KNOWN_BOARDS[self.board]
            flash_file_opts = board["flash_file"] if "flash_file" in board else {}

            if "flash_address" in flash_file_opts:
                self.flash_address = flash_file_opts["flash_address"]
            if "max_size" in flash_file_opts:
                self.max_size = flash_file_opts["max_size"]
            if "flush_command" in flash_file_opts:
                self.flush_command = flash_file_opts["flush_command"]

        # Log the most important, finalized settings to the user
        if self.filepath != None:
            logging.info('Operating on flash file "{}".'.format(self.filepath))
        if self.max_size != None:
            logging.info("Limiting flash size to {:#x} bytes.".format(self.max_size))
        self._configure_from_known_boards()

        try:
            # We want to preserve the flash contents in the file.
            self.file_handle = open(self.filepath, "r+b")
        except:
            # But if the file doesn't exist, create it.
            self.file_handle = open(self.filepath, "w+b")

        def file_handle_cleanup():
            if self.file_handle is not None:
                self.file_handle.close()

        atexit.register(file_handle_cleanup)

    def get_local_board_path(self):
        return self.filepath

    def translate_address(self, address):
        # For the flash file, we start the flash file at the beginning of flash
        # and continue as needed. The argument `address` is an absolute address,
        # so we need to convert it to an offset from the beginning of the file.
        flash_address = self.get_flash_address()
        if flash_address == None:
            logging.info("Assuming flash_address is 0x0.")
            flash_address = 0
        return address - flash_address

    def get_flash_address(self):
        if self.flash_address:
            return self.flash_address
        return None

    def flash_binary(self, address, binary):
        # Write the passed binary data to the given address. This will
        # automatically extend the file size if necessary. Thus we must be
        # careful to not write past the end of our virtual flash, if one is
        # defined.
        address = self.translate_address(address)

        # Cap the write size to respect the `max_size` setting.
        write_len = max(min(self.max_size - address, len(binary)), 0)
        if not write_len == len(binary):
            logging.warning("Truncating write due to maximum flash-file size limits")

        self.file_handle.seek(address)
        self.file_handle.write(binary[:write_len])

    def read_range(self, address, length):
        # Read from the given address in the file. Specifying an invalid address
        # will not cause the file to be extended automatically. Nonetheless we
        # should respect the end of our virtual flash, if one is defined.
        address = self.translate_address(address)

        # Cap the read size to respect the `max_size` setting.
        read_len = max(min(self.max_size - address, length), 0)
        if not read_len == length:
            logging.warning("Truncating read due to maximum flash-file size limits")

        self.file_handle.seek(address)
        return self.file_handle.read(read_len)

    def clear_bytes(self, address):
        # For this simple implementation, given we are not operating on a real
        # flash, it's fine to just set the single byte at the specified address
        # to zero.
        self.flash_binary(address, bytes([0]))

    def _run_flush_command(self, command):
        # Try to execute the flush command for the user.

        def print_output(subp, debug):
            if subp.stdout:
                logging.info(subp.stdout.decode("utf-8"))
            if subp.stderr and debug:
                logging.debug(subp.stderr.decode("utf-8"))

        logging.debug(f'Running command "{command}"')

        p = subprocess.run(
            shlex.split(command), stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if p.returncode != 0:
            logging.error(
                "ERROR: Flush command returned with error code " + str(p.returncode)
            )
            print_output(p, logging.info)
            raise TockLoaderException("Flush command error")
        else:
            print_output(p, self.args.debug)

    def flush(self):
        # Write the local board binary file to the board.
        file_path_arg = f"'{self.filepath}'"
        flush_command = self.flush_command.format(binary=file_path_arg)
        self._run_flush_command(flush_command)


def set_local_board(
    board,
    arch=None,
    app_address=None,
    flash_address=None,
    flush_command=None,
    binary_path=None,
):
    p = FlashFile.LOCAL_BOARD_NAME_PATH

    # Make directory if needed
    os.makedirs(os.path.dirname(p), exist_ok=True)

    # We default to a binary file in the same appdir unless the user specified
    # something else.
    filepath = f"{board}.bin"
    if binary_path:
        filepath = os.path.abspath(binary_path)

    local_board = {"board": board, "filepath": filepath}
    if arch:
        local_board["arch"] = arch
    if app_address:
        local_board["app_address"] = app_address
    if flash_address:
        local_board["flash_address"] = flash_address
    if flush_command:
        local_board["flush_command"] = flush_command

    with open(p, "w") as f:
        toml.dump(local_board, f)


def unset_local_board():
    p = FlashFile.LOCAL_BOARD_NAME_PATH
    os.remove(p)
