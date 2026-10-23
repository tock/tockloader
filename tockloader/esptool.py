"""
Interface for Espressif boards using esptool.

Espressif chips have a serial bootloader in their mask ROM. Tockloader uses
the Python API of esptool to access the external SPI flash of the chip through
this bootloader. The chip stays in its ROM bootloader while Tockloader reads
and writes flash, and is reset into the Tock kernel afterwards.
"""

import logging

import serial.tools.list_ports

from .board_interface import BoardInterface
from .exceptions import TockLoaderException

# USB VID:PID pairs that indicate an attached Espressif chip.
#
# Espressif's own VID is used by the USB Serial/JTAG controller integrated into
# newer chips. The other entries are USB-UART bridges used on Espressif's
# development kits. Many unrelated boards use these bridges as well, so we only
# select such a port after esptool has confirmed that a supported chip is
# attached to it.
ESPRESSIF_USB_VID = 0x303A
USB_UART_BRIDGES = [
    (0x10C4, 0xEA60),  # Silicon Labs CP210x (e.g., ESP32-C3-DevKitM-1)
    (0x1A86, 0x55D3),  # WCH CH343 (e.g., ESP32-C3-DevKitC-02 v1.1)
    (0x1A86, 0x7523),  # WCH CH340
]

# Mapping from esptool-reported chip to Tock board name, for chips attached
# through a USB-UART bridge.
DEFAULT_BOARD_FOR_CHIP = {
    "ESP32-C3": "esp32-c3-devkitm-1",
}

# Mapping from esptool-reported chip to Tock board name, for chips attached
# through their integrated USB Serial/JTAG controller (Espressif's USB VID).
DEFAULT_BOARD_FOR_CHIP_NATIVE_USB = {
    "ESP32-C3": "esp32-c3-devkit-rust-2",
}


class EspTool(BoardInterface):
    def __init__(self, args):
        # Must call the generic init first.
        super().__init__(args)

        self.port = getattr(self.args, "port", None)

        # The `ESPLoader` connection to the chip's ROM bootloader. `None` while
        # the chip is not in its ROM bootloader.
        self.esp = None

    def _import_esptool(self):
        """
        Import esptool lazily, such that it is only required for users of this
        channel.
        """
        try:
            import esptool.cmds
            from esptool.logger import log
        except ImportError:
            raise TockLoaderException(
                "Tockloader esptool support requires esptool >= 5.0. "
                "Install it with `pip install esptool` or `pipx inject tockloader esptool`."
            )

        # esptool prints to stdout by default. Only show its output when
        # tockloader is running in debug mode.
        log.set_verbosity("verbose" if self.args.debug else "silent")

        return esptool.cmds

    def _candidate_ports(self):
        """
        Return the serial ports that an Espressif chip may be attached to.
        """
        if self.port is not None:
            return [self.port]

        ports = []
        for port in serial.tools.list_ports.comports():
            if (
                port.vid == ESPRESSIF_USB_VID
                or (port.vid, port.pid) in USB_UART_BRIDGES
            ):
                ports.append(port.device)
        return ports

    def _is_native_usb(self, port):
        """
        Return whether `port` is the USB Serial/JTAG controller integrated into
        an Espressif chip, rather than a USB-UART bridge.
        """
        for info in serial.tools.list_ports.comports():
            if info.device == port:
                return info.vid == ESPRESSIF_USB_VID
        return False

    def _connect(self, port):
        """
        Reset the chip attached to `port` into its ROM bootloader, and return an
        `ESPLoader` with the stub flasher running.
        """
        cmds = self._import_esptool()
        logging.debug('Connecting to Espressif chip on "{}".'.format(port))
        esp = cmds.detect_chip(port=port, connect_attempts=1)
        logging.debug("Detected {}.".format(esp.CHIP_NAME))
        esp = cmds.run_stub(esp)
        cmds.attach_flash(esp)
        return esp

    def _disconnect(self):
        """
        Reset the chip into the Tock kernel and close the serial port.
        """
        if self.esp is None:
            return

        cmds = self._import_esptool()
        try:
            cmds.reset_chip(self.esp, "hard-reset")
        finally:
            self.esp._port.close()
            self.esp = None

    def _expected_chip(self):
        """
        Return the chip we expect esptool to report for the selected board, or
        `None` if the board does not specify one.
        """
        if self.board and self.board in self.KNOWN_BOARDS:
            return self.KNOWN_BOARDS[self.board].get("esptool", {}).get("chip")
        return None

    def attached_board_exists(self):
        # Probe each candidate port with esptool. This resets the attached chip,
        # so we keep the connection open for `open_link_to_board()`.
        try:
            self._import_esptool()
        except TockLoaderException:
            logging.debug("No esptool installed.")
            return False

        for port in self._candidate_ports():
            try:
                esp = self._connect(port)
            except Exception as e:
                logging.debug('No Espressif chip on "{}": {}'.format(port, e))
                continue

            if esp.CHIP_NAME in DEFAULT_BOARD_FOR_CHIP:
                self.port = port
                self.esp = esp
                return True

            esp._port.close()

        return False

    def open_link_to_board(self):
        if self.port is None:
            ports = self._candidate_ports()
            if len(ports) == 0:
                raise TockLoaderException(
                    "No Espressif serial port found. Pass --port to select one."
                )
            if len(ports) > 1:
                raise TockLoaderException(
                    "Multiple candidate serial ports found ({}). Pass --port to "
                    "select one.".format(", ".join(ports))
                )
            self.port = ports[0]

        self.enter_bootloader_mode()

        # The chip does not tell us which board it is on. If the user did not
        # specify the board, assume the default board for this chip and the
        # kind of USB port it is attached through.
        if self.board is None:
            if self._is_native_usb(self.port):
                defaults = DEFAULT_BOARD_FOR_CHIP_NATIVE_USB
            else:
                defaults = DEFAULT_BOARD_FOR_CHIP
            self.board = defaults.get(self.esp.CHIP_NAME)

        if self.board and self.board in self.KNOWN_BOARDS:
            logging.info('Using settings from KNOWN_BOARDS["{}"]'.format(self.board))
            self._configure_from_known_boards()

        expected_chip = self._expected_chip()
        if expected_chip is not None and expected_chip != self.esp.CHIP_NAME:
            self._disconnect()
            raise TockLoaderException(
                'Board "{}" requires an {}, but esptool detected an {}.'.format(
                    self.board, expected_chip, self.esp.CHIP_NAME
                )
            )

    def enter_bootloader_mode(self):
        if self.esp is None:
            self.esp = self._connect(self.port)

    def exit_bootloader_mode(self):
        self._disconnect()

    def translate_address(self, address):
        # esptool addresses the external flash by offset. Tock boards link
        # against the address where the chip maps the flash.
        flash_address = self.get_flash_address() or 0
        if address < flash_address:
            raise TockLoaderException(
                "Address {:#x} is not contained in flash".format(address)
            )
        return address - flash_address

    def flash_binary(self, address, binary, pad=False):
        # esptool erases whole flash sectors before writing them. Extend the
        # write to sector boundaries with the current flash contents, such that
        # data next to `binary` is preserved.
        address, binary = self._align_and_stretch_to_page(address, binary)

        cmds = self._import_esptool()
        cmds.write_flash(
            self.esp,
            # esptool accepts `bytes`, but not `bytearray`.
            [(self.translate_address(address), bytes(binary))],
            no_progress=not self.args.debug,
        )

    def read_range(self, address, length):
        logging.debug(
            "DEBUG => Read Range, address: {:#010x}, length: {}".format(address, length)
        )
        if length == 0:
            return bytes()

        cmds = self._import_esptool()
        return cmds.read_flash(
            self.esp, self.translate_address(address), length, no_progress=True
        )

    def clear_bytes(self, address):
        logging.debug("Clearing bytes starting at {:#0x}".format(address))

        binary = bytes([0xFF] * 8)
        self.flash_binary(address, binary)

    def determine_current_board(self):
        # We might need to fill in settings if we only know the board name.
        self._configure_from_known_boards()

        # Check that we learned what we needed to learn.
        if self.board is None:
            raise TockLoaderException("Could not determine the current board")
        if self.arch is None:
            raise TockLoaderException("Could not determine the current arch")
        if self.page_size == 0:
            raise TockLoaderException("Could not determine the current page size")
