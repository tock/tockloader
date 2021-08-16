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

        # Boards can limit the size of their virtual flash, otherwise it will
        # grow automatically.
        self.max_size = None

        # Load custom settings for the flash-file from the board definition.
        if self.board and self.board in self.KNOWN_BOARDS:
            logging.info('Using settings from KNOWN_BOARDS["{}"]'
                         .format(self.board))
            board = self.KNOWN_BOARDS[self.board]
            flash_file_opts = board["flash_file"] if "flash_file" in board else {}

            if "max_size" in flash_file_opts:
                self.max_size = flash_file_opts["max_size"]

        # Log the most important, finalized settings to the user
        logging.info('Operating on flash file at "{}"'.format(self.filepath))
        logging.info('Limiting flash size to 0x{:x} bytes'.format(self.max_size))


    def attached_board_exists(self):
        """
        Determine whether the "attached board" in form of the flash file exists
        based on whether the passed path is a file and we can read and write it.
        """
        if os.path.isfile(self.filepath) and \
           os.access(self.filepath, os.R_OK | os.W_OK):
            return True
        else:
            return False

    def open_link_to_board(self):
        """
        Open a link to the board by opening the flash file for reading and
        writing.
        """
        # Don't catch exceptions, given attached_board_exists is responsible for
        # checking access to the board. In case the permissions changed in
        # between, it's fine to throw an error.
        self.file_handle = open(self.filepath, 'r+b')

        def file_handle_cleanup():
            if self.file_handle is not None:
                self.file_handle.close()

        atexit.register(file_handle_cleanup)

    def enter_bootloader_mode(self):
        return

    def exit_bootloader_mode(self):
        return

    def flash_binary(self, address, binary):
        # Write the passed binary data to the given address. This will
        # automatically extend the file size if necessary. Thus we must be
        # careful to not write past the end of our virtual flash, if one is
        # defined.
        address = self.translate_address(address)

        if self.max_size is not None:
            write_len = max(min(0, self.max_size - address), len(binary))
        else:
            write_len = len(binary)

        self.file_handle.seek(address)
        self.file_handle.write(binary[:write_len])

    def read_range(self, address, length):
        # Read from the given address in the file. Specifying an invalid address
        # will not cause the file to be extended automatically. Nonetheless we
        # should respect the end of our virtual flash, if one is defined.
        address = self.translate_address(address)

        if self.max_size is not None:
            read_len = max(min(0, self.max_size - address), length)
        else:
            read_len = length

        self.file_handle.seek(address)
        return self.file_handle.read(read_len)

    def clear_bytes(self, address):
        # For this simple implementation, given we are not operating on a real
        # flash, it's fine to just set the single byte at the specified address
        # to zero.
        self.flash_binary(address, bytes([0]))
