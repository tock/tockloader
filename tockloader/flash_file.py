"""
Interface to a board's flash file. This module does not directly interface to a
proper board, but can be used to manipulate a board's flash dump.
"""

import atexit
import logging
import os

from .board_interface import BoardInterface
from .exceptions import TockLoaderException


class FlashFile(BoardInterface):
    """
    Implementation of `BoardInterface` for flash files.
    """

    def __init__(self, args):
        super().__init__(args)

        # Store the passed filepath
        self.filepath = args.flash_file

        # Boards should limit the file size to match their flash. However, we
        # don't want users to accidentally create gigantic files using the
        # `--flash-file` flag, so we set a cap at 128 MB. If a future Tock board
        # needs more than that...well we can revisit this then.
        self.max_size = 0x8000000

        # Load custom settings for the flash-file from the board definition.
        if self.board and self.board in self.KNOWN_BOARDS:
            logging.info('Using settings from KNOWN_BOARDS["{}"]'.format(self.board))
            board = self.KNOWN_BOARDS[self.board]
            flash_file_opts = board["flash_file"] if "flash_file" in board else {}

            if "max_size" in flash_file_opts:
                self.max_size = flash_file_opts["max_size"]

        # Log the most important, finalized settings to the user
        logging.info('Operating on flash file "{}".'.format(self.filepath))
        if self.max_size != None:
            logging.info("Limiting flash size to {:#x} bytes.".format(self.max_size))

    def open_link_to_board(self):
        """
        Open a link to the board by opening the flash file for reading and
        writing.
        """
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
