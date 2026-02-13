"""
Interface for boards using nrfutil.
"""

import json
import logging
import os
import pprint
import shutil
import subprocess
import tempfile
import textwrap
import pathlib

import intelhex

from .board_interface import BoardInterface
from .exceptions import TockLoaderException


class NrfUtil(BoardInterface):
    def __init__(self, args):
        super().__init__(args)

        # Indicate that we are not bound to a given device serial number yet:
        self._opened_board_serial = None
        self._opened_board_code_page_size = None
        self._opened_board_vcom0_device = None

    def _ensure_nrfutil_installed(self):
        # This argument may not be installed on all commands that instantiate
        # `NrfUtil`. For instance, it is not present when running `tockloader
        # listen`, which will nonetheless instantiate this object for
        # discovering the VCOM0 device. Therefore, use `None` as default:
        self._nrfutil_path = getattr(self.args, "nrfutil_cmd", None)

        # Fallback to discovering nrfutil in PATH:
        if self._nrfutil_path is None:
            self._nrfutil_path = shutil.which("nrfutil")

        # Need the `nrfutil` binary to be installed:
        if not self._nrfutil_path:
            raise TockLoaderException(
                "Cannot find nrfutil executable, please install it."
            )

        # Try executing nrfutil and ensure that it is callable:
        out = self._run_nrfutil(["--version", "--json"], init=True, as_json=True)
        info_msg = self._get_nrfutil_json_msg(out, "info")
        assert info_msg["data"]["name"] == "nrfutil"

        # Ensure that the `device` command is installed:
        try:
            out = self._run_nrfutil(
                ["device", "--version", "--json"],
                init=True,
                as_json=True,
            )
            info_msg = self._get_nrfutil_json_msg(out, "info")
            assert info_msg["data"]["name"] == "nrfutil-device"
        except:
            logging.debug("The `nrfutil device` command is not installed.")
            logging.debug("Install it by running `nrfutil install device`.")
            raise TockLoaderException("nrfutil device not installed")

        # Ensure that the `device` command is new enough. Older versions did not
        # have a `read` command.
        try:
            out = self._run_nrfutil(
                ["device", "read", "--help"],
                init=True,
            )
        except:
            logging.debug("The `nrfutil device` command is too old.")
            logging.debug("Update it by running `nrfutil install device --force`.")
            raise TockLoaderException("nrfutil device out of date")

    def _run_nrfutil(self, args, as_json=False, custom_error=None, init=False):
        if not init:
            self._ensure_nrfutil_installed()

        cmd = [self._nrfutil_path] + args
        cmd_str = " ".join(
            map(
                lambda arg: (
                    arg if type(arg) == str else arg.decode("utf-8", errors="replace")
                ),
                cmd,
            )
        )
        logging.debug(f"Running: {cmd_str}")

        try:
            cmd = subprocess.run(cmd, capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            stdout = e.stdout.decode("utf-8", errors="replace")
            stderr = e.stderr.decode("utf-8", errors="replace")
            logging.debug(
                (
                    f"nrfutil command failed.\n"
                    + f"    Command:\n{cmd_str}\n"
                    + f"    Stdout:\n{stdout}\n"
                    + f"    Stderr:\n{stderr}"
                )
            )
            raise TockLoaderException(
                "nrfutil command failed. You may need to update nrfutil."
            )

        if as_json:
            # We expect the output to be lines of valid JSON, where each message
            # contains at least a "type" key:
            messages = []

            for line in cmd.stdout.strip().splitlines():
                try:
                    msg = json.loads(line)
                except ValueError:
                    raise TockLoaderException(
                        f"nrfutil returned invalid JSON: {line.decode('utf-8')}"
                    )

                if "type" not in msg:
                    raise TockLoaderException(
                        'nrfutil JSON output does not contain "type" key: '
                        + line.decode("utf-8")
                    )

                messages.append(msg)

            return messages
        else:
            return cmd.stdout

    def _get_nrfutil_json_msg(self, json_messages, message_type):
        try:
            msg = next((msg for msg in json_messages if msg["type"] == message_type))
        except StopIteration:
            raise TockLoaderException(
                "nrfutil JSON output did not contain message of type "
                + f'"{message_type}":\n{pprint.pformat(json_messages)}'
            )
        return msg

    def _first_attached_board_serial(self):
        """
        Check if an nRF device is attached.
        """
        # list devices and check output
        out = self._run_nrfutil(["device", "list", "--json"], as_json=True)
        info_msg = self._get_nrfutil_json_msg(out, "info")

        # Sanity check the output:
        if (
            "data" not in info_msg
            or "devices" not in info_msg["data"]
            or type(info_msg["data"]["devices"]) != list
        ):
            raise TockLoaderException(
                "`nrfutil device list --json` output in unexpected format:\n"
                + pprint.pformat(info_msg)
            )

        # If we have at least one device attached, return its serial number:
        if len(info_msg["data"]["devices"]) > 0:
            return info_msg["data"]["devices"][0]["serialNumber"]

    def _ensure_board_link_open(self):
        if self._opened_board_serial is None:
            raise TockLoaderException(
                "Cannot perform nrfutil operation without first opening link "
                + "to board"
            )

    def nrfutil_installed(self):
        try:
            self._ensure_nrfutil_installed()
            return True
        except TockLoaderException:
            return False

    def attached_board_exists(self):
        if self.nrfutil_installed():
            return self._first_attached_board_serial() != None
        else:
            return False

    def open_link_to_board(self):
        # Refuse if we already have another link "opened":
        if self._opened_board_serial is not None:
            raise TockLoaderException(
                "nrfutil channel already has an open connection to device with "
                + f"serial number {self._opened_board_serial}"
            )

        # Try to bind to a given device serial number.
        #
        # If one is provided through the `--nrfutil-serial-number` argument, use
        # that one. We'll make sure that this device is actually attached below,
        # when trying to determine its VCOM0 device path.
        #
        # This argument may not be installed on all commands that instantiate
        # `NrfUtil`. For instance, it is not present when running `tockloader
        # listen`, which will nonetheless instantiate this object for
        # discovering the VCOM0 device. Therefore, use `None` as default:
        self._opened_board_serial = getattr(self.args, "nrfutil_serial_number", None)

        # Otherwise, fall back to the first attached device:
        if self._opened_board_serial is None:
            self._opened_board_serial = self._first_attached_board_serial()

        # If we don't have any devices, throw an error:
        if self._opened_board_serial is None:
            raise TockLoaderException("No nRF device attached.")

        # Determine the device's VCOM0 serial port path. Currently, the only way
        # to get this information through a "list", which we then search for our
        # board's serial number:
        out = self._run_nrfutil(["device", "list", "--json"], as_json=True)
        info_msg = self._get_nrfutil_json_msg(out, "info")

        # Sanity check the output:
        if (
            "data" not in info_msg
            or "devices" not in info_msg["data"]
            or type(info_msg["data"]["devices"]) != list
        ):
            raise TockLoaderException(
                "`nrfutil device list --json` output in unexpected format:\n"
                + pprint.pformat(info_msg)
            )

        # Find our device:
        try:
            device = next(
                (
                    dev
                    for dev in info_msg["data"]["devices"]
                    if dev["serialNumber"] == self._opened_board_serial
                )
            )
        except StopIteration:
            raise TockLoaderException(
                "`nrfutil device list --json` did not contain the requested "
                + f"board with serial {self._opened_board_serial}:\n"
                + pprint.pformat(info_msg)
            )

        # Check if we have a VCOM 0 serial port and, if we do, store its
        # "comName". If this isn't present, we simply return None for queries of
        # this serial port.
        if "serialPorts" in device and type(device["serialPorts"]) == list:
            port = next(
                filter(lambda sp: sp["vcom"] == 0, device["serialPorts"]),
                None,
            )
            if port is not None:
                self._opened_board_vcom0_device = port["comName"]

        # We've found a/our target device!
        logging.info(
            "Opened nrfutil link to board with serial {}".format(
                self._opened_board_serial
            )
        )

        # If possible, determine the board that is attached. `nrfutil` doesn't
        # give us an actual devboard name, but if we see a deviceFamily of
        # "NRF52_FAMILY" and a `jlinkObFirmwareVersion` is set, we assume this
        # is a `nrf52dk` (which covers both the actual nRF52DK and the
        # nRF52840DK):
        out = self._run_nrfutil(
            [
                "device",
                "device-info",
                "--serial-number",
                self._opened_board_serial,
                "--json",
            ],
            as_json=True,
        )
        info_msg = self._get_nrfutil_json_msg(out, "info")

        # Sanity check the output:
        if (
            "data" not in info_msg
            or "devices" not in info_msg["data"]
            or type(info_msg["data"]["devices"]) != list
            or len(info_msg["data"]["devices"]) != 1
            or "deviceInfo" not in info_msg["data"]["devices"][0]
        ):
            raise TockLoaderException(
                "`nrfutil device core-info --json` output unexpected:\n"
                + pprint.pformat(info_msg)
            )

        # Check if we can determine that this is an `nrf52dk`:
        deviceInfo = info_msg["data"]["devices"][0]["deviceInfo"]
        if (
            "jlink" in deviceInfo
            and "deviceFamily" in deviceInfo["jlink"]
            and deviceInfo["jlink"]["deviceFamily"] == "NRF52_FAMILY"
            and "jlinkObFirmwareVersion" in deviceInfo["jlink"]
        ):
            logging.info(
                "Attached to an nRF52DK-series board, configuring from KNOWN_BOARDS"
            )
            self.board = "nrf52dk"
            self._configure_from_known_boards()

            # TODO: at this point, it looks like we should need to load a
            # chip-specific external memory configuration file to access the SPI
            # flash. However, at least for the nRF52840DK, this seems to work
            # out of the box?
            #
            # https://docs.nordicsemi.com/bundle/nrfutil/page/nrfutil-device/guides/programming_external_memory.html

        # Determine the device's code page size, which we use for
        # read+modify+write cycles when writing flash:
        out = self._run_nrfutil(
            [
                "device",
                "core-info",
                "--serial-number",
                self._opened_board_serial,
                "--json",
            ],
            as_json=True,
        )
        info_msg = self._get_nrfutil_json_msg(out, "info")

        # Sanity check the output:
        if (
            "data" not in info_msg
            or "devices" not in info_msg["data"]
            or type(info_msg["data"]["devices"]) != list
            or len(info_msg["data"]["devices"]) != 1
            or "codePageSize" not in info_msg["data"]["devices"][0]
            or type(info_msg["data"]["devices"][0]["codePageSize"]) != int
            or info_msg["data"]["devices"][0]["codePageSize"] < 1
        ):
            raise TockLoaderException(
                "`nrfutil device core-info --json` output unexpected:\n"
                + pprint.pformat(info_msg)
            )

        # Remember the code page size:
        self._opened_board_code_page_size = info_msg["data"]["devices"][0][
            "codePageSize"
        ]

    def determine_current_board(self):
        # All this work is already done in `open_link_to_board`:
        if self._opened_board_serial is None:
            raise TockLoaderException("Cannot determine current board, no link opened.")

    def vcom0_device(self):
        return self._opened_board_vcom0_device

    def read_range(self, address, length):
        """
        Read using nrfutil.
        """

        self._ensure_board_link_open()

        # Temporary directory for `nrfutil` to write output into:
        with tempfile.TemporaryDirectory(
            prefix="tockloader_nrfutil_", delete=False
        ) as tmpdir:
            output_file = pathlib.Path(tmpdir) / "read.hex"

            # Using 'device memory read' based on online docs
            self._run_nrfutil(
                [
                    "device",
                    "read",
                    "--serial-number",
                    self._opened_board_serial,
                    "--address",
                    f"{address:#x}",
                    "--bytes",
                    str(length),
                    # Always perform byte-wise reads. This does not seem to have
                    # a significant (if any) performance impact in practice, but
                    # specifying larger values breaks when the address or length
                    # are not aligned.
                    "--width",
                    "8",
                    "--to-file",
                    os.fsencode(output_file),
                ]
            )

            ih = intelhex.IntelHex()
            ih.loadhex(output_file)
            return bytes(ih.tobinarray())

    # TODO: this method is not well specified, we're just doing what
    # other channels do...
    def clear_bytes(self, address):
        """
        Clear bytes by writing 0xFFs.
        """
        logging.debug("Clearing bytes starting at {:#0x}".format(address))

        binary = bytes([0xFF] * 8)
        self.flash_binary(address, binary)

    def flash_binary(self, address, binary, pad=False):
        """
        Write using nrfutil.
        """
        # TODO: ignores pad arg!

        self._ensure_board_link_open()

        # NrfUtil does feature the option to only
        # "ERASE_RANGES_TOUCHED_BY_FIRMWARE", but that only works up to page
        # granularity. Within a single page we have to perform a
        # read-modify-write cycle. So, we have to---potentially---extend the
        # range covered by `address` and `binary` to the next lower and higher
        # page boundary with contents read from the device:
        lower_pad_len = address % self._opened_board_code_page_size
        if lower_pad_len != 0:
            logging.debug(
                f"Start address of write ({address:x}) is not aligned to code "
                + f"flash page size ({self._opened_board_code_page_size}). "
                + "Performing read-modify-write cycle, reading "
                + f"{lower_pad_len} bytes at address "
                + f"{address - lower_pad_len:x}"
            )
            address -= lower_pad_len
            lower_pad_bytes = self.read_range(address, lower_pad_len)
            binary = lower_pad_bytes + binary

        # Same for the upper bound:
        upper_pad_len = (
            self._opened_board_code_page_size
            - ((address + len(binary)) % self._opened_board_code_page_size)
        ) % self._opened_board_code_page_size
        if upper_pad_len != 0:
            logging.debug(
                f"End address of write ({address + len(binary):x}) is not "
                + "aligned to code flash page size "
                + f"({self._opened_board_code_page_size}). Performing "
                + f"read-modify-write cycle, reading {upper_pad_len} bytes at "
                + f"address {address + len(binary):x}"
            )
            upper_pad_bytes = self.read_range(address + len(binary), upper_pad_len)
            binary = binary + upper_pad_bytes

        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix="tockloader_nrfutil_",
            suffix=".hex",
            delete_on_close=False,
        ) as input_file:
            # Dump `binary` to a hex file:
            ih = intelhex.IntelHex()
            ih.frombytes(binary, offset=address)
            ih.write_hex_file(input_file)
            input_file.close()

            # Now, write this to the board flash:
            self._run_nrfutil(
                [
                    "device",
                    "program",
                    "--serial-number",
                    self._opened_board_serial,
                    "--firmware",
                    input_file.name,
                    "--options",
                    "chip_erase_mode=ERASE_RANGES_TOUCHED_BY_FIRMWARE",
                ]
            )
