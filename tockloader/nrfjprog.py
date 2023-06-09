"""
Interface for boards using nrfjprog.
"""

import logging
import struct

import pynrfjprog
from pynrfjprog import HighLevel, Parameters

from .board_interface import BoardInterface
from .exceptions import TockLoaderException


class nrfjprog(BoardInterface):
    def __init__(self, args):
        # Must call the generic init first.
        super().__init__(args)

    def open_link_to_board(self):
        qspi_size = 0

        # Get board-specific properties we need.
        if self.board and self.board in self.KNOWN_BOARDS:
            logging.info('Using settings from KNOWN_BOARDS["{}"]'.format(self.board))
            board = self.KNOWN_BOARDS[self.board]

            if "nrfjprog" in board:
                if "qspi_size" in board["nrfjprog"]:
                    qspi_size = board["nrfjprog"]["qspi_size"]

        # pynrfjprog does a lot of logging, at this point too much, so we don't
        # enable it.
        nrfjprog_logging = False
        # if self.args.debug:
        #     nrfjprog_logging = True

        # First create the base API, this is how pynrfjprog works.
        api = pynrfjprog.HighLevel.API()
        if not api.is_open():
            api.open()
        # try:
        #     api.open()
        # except:
        #     # If this is called twice it throws an exception that we can ignore.
        #     pass

        # Need to provide the serial number of the board to connect to,
        # easy enough to get. In the future maybe this would be specified.
        serial_numbers = api.get_connected_probes()
        if len(serial_numbers) == 0:
            raise TockLoaderException("No nrfjprog device connected")

        # Actually create the object we will use to read/write the board.
        self.nrfjprog = pynrfjprog.HighLevel.DebugProbe(
            api, serial_numbers[0], log=nrfjprog_logging
        )

        # Optionally setup the QSPI if we know its size.
        if qspi_size > 0:
            self.nrfjprog.setup_qspi(qspi_size)

    def flash_binary(self, address, binary, pad=False):
        """
        Write using nrfjprog.
        """

        # We need to erase first, so make sure we are page aligned.
        original_address = address
        original_length = len(binary)
        address, binary = self._align_and_stretch_to_page(address, binary)
        if address != original_address or len(binary) != original_length:
            logging.debug(
                "Stretched write to {:#x}:{:#x} (length: {} bytes)".format(
                    address, address + len(binary), len(binary)
                )
            )

        # Since pynrfjprog is hopelessly broken:
        #
        # - https://github.com/NordicSemiconductor/pynrfjprog/issues/31
        # - https://devzone.nordicsemi.com/f/nordic-q-a/100613/pynrfjprog-using-pynrfjprog-to-write-qspi-with-buffer-writes-wrong-data
        #
        # this is SUPER slow. So, it's worth not writing pages that are already
        # correct in flash. Therefore, we do this page by page rather than
        # erasing all flash at the start and then writing all values.
        for index in range(0, len(binary), 4096):
            sector_start = index + address

            # Get current values of this page.
            current = self.read_range(sector_start, 4096)
            # Get desired values of the page.
            desired = binary[index : index + 4096]

            if current != desired:
                # Erase first
                logging.debug("Erasing sector @{:#x}".format(sector_start))
                self.nrfjprog.erase(
                    erase_action=pynrfjprog.Parameters.EraseAction.ERASE_SECTOR,
                    start_address=sector_start,
                    end_address=sector_start + 4096,
                )

                # Then write word-by-word values which aren't all 0xFF.
                for i in range(0, len(desired), 4):
                    word = struct.unpack("<I", desired[i : i + 4])[0]

                    # Skip writing all 0xff since the flash is already erased.
                    if word == 0xFFFFFFFF:
                        continue

                    logging.debug(
                        "Writing word {:#010x} @{:#x}".format(word, sector_start + i)
                    )
                    self.nrfjprog.write(address=sector_start + i, data=word)

    def read_range(self, address, length):
        """
        Read using nrfjprog.
        """
        return self.nrfjprog.read(address=address, data_len=length)

    def clear_bytes(self, address):
        logging.debug("Clearing bytes starting at {:#0x}".format(address))

        binary = bytes([0xFF] * 8)
        self.flash_binary(address, binary)
