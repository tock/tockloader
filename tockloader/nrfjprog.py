"""
Interface for boards using nrfjprog.
"""

import logging
import struct

import pynrfjprog
from pynrfjprog import LowLevel, Parameters

from .board_interface import BoardInterface
from .exceptions import TockLoaderException


class nrfjprog(BoardInterface):
    def __init__(self, args):
        # Must call the generic init first.
        super().__init__(args)

    def open_link_to_board(self):
        qspi_size = 0
        self.qspi_address = 0

        # Get board-specific properties we need.
        if self.board and self.board in self.KNOWN_BOARDS:
            logging.info('Using settings from KNOWN_BOARDS["{}"]'.format(self.board))
            board = self.KNOWN_BOARDS[self.board]

            if "nrfjprog" in board:
                if "qspi_size" in board["nrfjprog"]:
                    qspi_size = board["nrfjprog"]["qspi_size"]
                if "qspi_address" in board["nrfjprog"]:
                    self.qspi_address = board["nrfjprog"]["qspi_address"]

        # pynrfjprog does a lot of logging, at this point too much, so we don't
        # enable it.
        nrfjprog_logging = False
        # if self.args.debug:
        #     nrfjprog_logging = True

        # First create the base API, this is how pynrfjprog works.
        api = pynrfjprog.LowLevel.API()
        if not api.is_open():
            api.open()
        # try:
        #     api.open()
        # except:
        #     # If this is called twice it throws an exception that we can ignore.
        #     pass

        api.connect_to_emu_without_snr()
        api.qspi_configure()
        api.qspi_init()

        self.nrfjprog = api

    def flash_binary(self, address, binary, pad=False):
        """
        Write using nrfjprog.
        """
        self.nrfjprog.qspi_write(address - self.qspi_address, binary)

    def read_range(self, address, length):
        """
        Read using nrfjprog.
        """
        return self.nrfjprog.qspi_read(address - self.qspi_address, length)

    def clear_bytes(self, address):
        logging.debug("Clearing bytes starting at {:#0x}".format(address))

        binary = bytes([0xFF] * 8)
        self.flash_binary(address, binary)
