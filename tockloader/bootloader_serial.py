"""
Interface with a board over serial that is using the
[Tock Bootloader](https://github.com/tock/tock-bootloader).
"""

import atexit
import crcmod
import datetime
import hashlib
import json
import logging
import os
import platform
import socket
import struct
import sys
import time
import threading

# Windows support in tockloader is currently experimental. Please report bugs,
# and ideally rough paths to fixing them. The core maintainers have limited
# access to Windows machines, and support in testing fixes/updates is helpful.
if platform.system() != "Windows":
    import fcntl

    _IS_WINDOWS = False
else:
    _IS_WINDOWS = True

import serial
import serial.tools.list_ports
import serial.tools.miniterm

from . import helpers
from .board_interface import BoardInterface
from .exceptions import TockLoaderException

from tqdm import tqdm  # Used for printing progress bars


class BootloaderSerial(BoardInterface):
    """
    Implementation of `BoardInterface` for the Tock Bootloader over serial.
    """

    # "This was chosen as it is infrequent in .bin files" - immesys
    ESCAPE_CHAR = 0xFC

    # Commands from this tool to the bootloader.
    # The "X" commands are for external flash.
    COMMAND_PING = 0x01
    COMMAND_INFO = 0x03
    COMMAND_ID = 0x04
    COMMAND_RESET = 0x05
    COMMAND_ERASE_PAGE = 0x06
    COMMAND_WRITE_PAGE = 0x07
    COMMAND_XEBLOCK = 0x08
    COMMAND_XWPAGE = 0x09
    COMMAND_CRCRX = 0x10
    COMMAND_READ_RANGE = 0x11
    COMMAND_XRRANGE = 0x12
    COMMAND_SET_ATTRIBUTE = 0x13
    COMMAND_GET_ATTRIBUTE = 0x14
    COMMAND_CRC_INTERNAL_FLASH = 0x15
    COMMAND_CRCEF = 0x16
    COMMAND_XEPAGE = 0x17
    COMMAND_XFINIT = 0x18
    COMMAND_CLKOUT = 0x19
    COMMAND_WUSER = 0x20
    COMMAND_CHANGE_BAUD_RATE = 0x21
    COMMAND_EXIT = 0x22
    COMMAND_SET_START_ADDRESS = 0x23

    # Responses from the bootloader.
    RESPONSE_OVERFLOW = 0x10
    RESPONSE_PONG = 0x11
    RESPONSE_BADADDR = 0x12
    RESPONSE_INTERROR = 0x13
    RESPONSE_BADARGS = 0x14
    RESPONSE_OK = 0x15
    RESPONSE_UNKNOWN = 0x16
    RESPONSE_XFTIMEOUT = 0x17
    RESPONSE_XFEPE = 0x18
    RESPONSE_CRCRX = 0x19
    RESPONSE_READ_RANGE = 0x20
    RESPONSE_XRRANGE = 0x21
    RESPONSE_GET_ATTRIBUTE = 0x22
    RESPONSE_CRC_INTERNAL_FLASH = 0x23
    RESPONSE_CRCXF = 0x24
    RESPONSE_INFO = 0x25
    RESPONSE_CHANGE_BAUD_FAIL = 0x26

    # Tell the bootloader to reset its buffer to handle a new command.
    SYNC_MESSAGE = bytes([0x00, 0xFC, 0x05])

    def __init__(self, args):
        super().__init__(args)

        # The Tock serial bootloader only uses 512 byte pages to simplify the
        # implementations and reduce uncertainty. Chips implementing the
        # bootloader are expected to handle data being written or erased in 512
        # byte chunks.
        self.page_size = 512

        # The Tock bootloader always has an attribute table.
        self.no_attribute_table = False

        # We cache attributes so we don't read them more than once. Create a
        # local data structure to hold them.
        self.attributes = ["uncached"] * 16

    def _determine_port(self, any=False):
        """
        Helper function to determine which serial port on the host to use to
        connect to the board.

        Set `any` to true to return a device without prompting the user (i.e.
        just return any port if there are multiple).
        """
        # Check to see if the user specified a serial port or a specific name,
        # or if we should find a serial port to use.
        if self.args.port == None:
            # The user did not specify a specific port to use, so we look for
            # something marked as "Tock". If we can't find something, we will
            # fall back to using any serial port.
            device_name = "tock"
            must_match = False
            logging.info(
                'No device name specified. Using default name "{}".'.format(device_name)
            )
        else:
            # Since the user specified, make sure we connect to that particular
            # port or something that matches it.
            device_name = self.args.port
            must_match = True

        # Look for a matching port
        ports = sorted(list(serial.tools.list_ports.grep(device_name)))
        if must_match:
            # In the most specific case a user specified a full path that exists
            # and we should use that specific serial port. We need to do more checking, however, as
            # something like `/dev/ttyUSB5` will also match
            # `/dev/ttyUSB55`, but it is clear that user expected to use the
            # serial port specified by the full path.
            for i, p in enumerate(ports):
                if p.device == device_name:
                    # We found an exact name match. Use that.
                    index = i
                    break
            else:
                # We found no match. If we get here, then the user did not
                # specify a full path to a serial port, and we couldn't find
                # anything on the board that matches what they specified (which
                # may have just been a short name). Since the user put in the
                # effort of specifically choosing a port, we error here rather
                # than just (arbitrarily) choosing something they didn't
                # specify.
                raise TockLoaderException(
                    'Could not find a board matching "{}".'.format(device_name)
                )
        elif len(ports) == 1:
            # Easy case, use the one that matches.
            index = 0
        elif len(ports) > 1:
            if any:
                index = 0
            else:
                # If we get multiple matches then we ask the user to choose from
                # a list.
                index = helpers.menu(
                    ports,
                    return_type="index",
                    title="Multiple matching serial port options found. Which would you like to use?",
                )
        else:
            # Just find any port. If one, use that. If multiple, ask user.
            ports = list(serial.tools.list_ports.comports())

            # New and improved in September 2025!
            #
            # A couple things have changed over time since tockloader started:
            #
            # 1. Many fewer boards use the serial tock-bootloader for
            #    programming. There are a couple, e.g., hail, imix, wm1110dev.
            #    However, these are not widely used.
            # 2. We now have many different ways to program boards, e.g.,
            #    openocd, jlink, probe-rs, stlink, and via a flash-file binary.
            # 3. Most users of this file (bootloader_serial) are using
            #    `tockloader listen`.
            # 4. More users are using windows.
            #
            # This means that tockloader's standard practice of trying to
            # default to using a serial port is increasingly not useful. To try
            # to balance utility with backwards compatibility, we are switching
            # to a new mechanism for determining when to use a serial port. This
            # has two parts:
            #
            # 1. We look for serial ports that match boards we recognize.
            # 2. We ignore all serial ports that don't look like physical
            #    hardware.
            #
            # The hope is this means tockloader still works for existing use
            # cases, while not always trying to use miscellaneous serial ports
            # present on a machine that are not actual boards.

            # Drop all serial ports that do not have a PID and VID. This should
            # ignore miscellaneous serial ports that are not actual boards.
            ports = [p for p in ports if not p.vid == None]
            ports = [p for p in ports if not p.pid == None]
            index = None

            if len(ports) == 0:
                raise TockLoaderException(
                    "No serial ports found. Is the board connected?"
                )

            # Attempt to workaround the issue with the nRF52840dk (PCA10056),
            # particularly newer revisions of that board, that open two serial
            # ports by detecting which one is the correct port.
            #
            # We first try to only run this if we think that the user actually
            # has a nRF52840dk plugged in. We check that by looking for two
            # devices that both have "J-Link - CDC" in the name.
            #
            # If we find that, we use the `nrfjprog --com` command which lists
            # attached ports and their VCOM indices. We want VCOM0. We use the
            # pynrfjprog to run the same operation as `--com`. `nrfjprog --com`
            # has output that looks like:
            #
            # ```
            # $ nrfjprog --com
            # 1050288520    /dev/tty.usbmodem0010502885201    VCOM0
            # 1050288520    /dev/tty.usbmodem0010502885203    VCOM1
            # ```
            jlink_cdc_ports = [p for p in ports if "J-Link - CDC" in p.description]
            if len(jlink_cdc_ports) == 2:
                # It looks like the user has the nRF52840dk connected.
                try:
                    import pynrfjprog
                    from pynrfjprog import LowLevel

                    api = pynrfjprog.LowLevel.API()
                    if not api.is_open():
                        api.open()

                    vcom0_path = None
                    jtag_emulators = api.enum_emu_con_info()
                    for jtag_emulator in jtag_emulators:
                        jtag_emulator_ports = api.enum_emu_com_ports(
                            jtag_emulator.serial_number
                        )
                        for jtag_emulator_port in jtag_emulator_ports:
                            # We want to see VCOM == 0
                            if jtag_emulator_port.vcom == 0:
                                vcom0_path = jtag_emulator_port.path
                                break
                        # Only support one connected nRF52840dk for now.
                        break

                    if vcom0_path != None:
                        # On mac, the nrfjprog tool uses the /dev/tty* paths,
                        # and we need the /dev/cu* paths. We just hack in a
                        # substitution here which will only have an effect on
                        # the mac paths.
                        vcom0_path_standarized = vcom0_path.replace(
                            "/dev/tty.usbmodem", "/dev/cu.usbmodem"
                        )

                        # Update list of ports to just the one we found for
                        # VCOM0.
                        ports = [p for p in ports if vcom0_path_standarized in p.device]
                        index = 0
                        logging.info(
                            'Discovered "{}" as nRF52840dk VCOM0.'.format(
                                vcom0_path_standarized
                            )
                        )

                    # Must close this to end the underlying pynrfjprog process.
                    # Otherwise on my machine it sits at 100% CPU.
                    api.close()
                except:
                    # Any error with nrfjprog we just don't use this
                    # optimization.
                    pass

            # Attempt to find other known boards based on their serial port
            # characteristics

            # The wm1110dev board has an onboard USB-to-Serial adapter we use
            # with the tock-bootloader. We don't have it re-programmed to
            # include "tock" in the description, so we find it based on the
            # description, VID, and PID.
            wm1110dev_ports = [
                p
                for p in ports
                if "USB Serial" in p.description and p.vid == 0x1A86 and p.pid == 0x7523
            ]
            if len(wm1110dev_ports) > 0:
                logging.info("Found serial ports matching the wm1110dev board.")
                if len(wm1110dev_ports) == 1:
                    index = 0
                else:
                    # If multiple matches then ask the user to choose.
                    index = helpers.menu(
                        wm1110dev_ports,
                        return_type="index",
                        title="Multiple matching serial port options found. Which would you like to use?",
                    )

            # Continue searching if our special-case discovery did not find
            # anything.
            if index == None:
                logging.info(
                    'No serial port with device name "{}" found.'.format(device_name)
                )
                logging.info(
                    "Found {} serial port{}.".format(
                        len(ports), ("s", "")[len(ports) == 1]
                    )
                )

                if len(ports) == 1 or any:
                    index = 0
                else:
                    index = helpers.menu(
                        ports,
                        return_type="index",
                        title="Multiple serial port options found. Which would you like to use?",
                    )

        # Choose port. This should be a serial.ListPortInfo type.
        port = ports[index]

        logging.info('Using "{}".'.format(port))

        # Save the serial number. This might help us reconnect later if say we
        # have to boot into the bootloader and the OS assigns a new port name to
        # the same physical board. On _some_ USB devices there is no serial
        # number. This was first found on the WM1110-dev board. In that case we
        # fall back the port name.
        self.sp_serial_number = port.serial_number or port.name

        # Improve UI for users
        helpers.set_terminal_title_from_port_info(port)

        # Return serial port device name
        return port.device

    def _configure_serial_port(self, port):
        """
        Helper function to configure the serial port so we can read/write with
        it.
        """
        # Open the actual serial port
        self.sp = serial.Serial()

        # We need to monkey patch the serial library so that it does not clear
        # our receive buffer. For FTDI devices this is not necessary. However,
        # for CDC-ACM devices, the board can send back data before we are
        # finished configuring it. We don't want to lose that data, so we
        # replace the `reset_input_buffer()` function with a no-op.
        def dummy_function():
            pass

        self.sp.reset_input_buffer = dummy_function

        self.sp.port = port
        self.sp.baudrate = 115200
        self.sp.parity = serial.PARITY_NONE
        self.sp.stopbits = 1
        self.sp.xonxoff = 0
        self.sp.rtscts = 0
        self.sp.timeout = 0.5
        # Try to set initial conditions, but not all platforms support them.
        # https://github.com/pyserial/pyserial/issues/124#issuecomment-227235402
        self.sp.dtr = 0
        self.sp.rts = 0

    def _open_serial_port(self):
        """
        Helper function for calling `self.sp.open()`.

        Serial ports on different OSes and systems can be finicky, and this
        enables retries to try to hide failures.
        """
        # On ubuntu 20.04 in Jan 2021, sometimes connecting to the serial port
        # fails the first several times. This attempts to address that by simply
        # retrying a whole bunch. On most systems this should just work and
        # doesn't add any overhead.
        saved_exception = None
        for i in range(0, 15):
            try:
                self.sp.open()
                break
            except Exception as e:
                saved_exception = e
                if self.args.debug:
                    logging.debug(
                        "Retrying opening serial port (attempt {})".format(i + 1)
                    )
                time.sleep(0.1)
        else:
            # Opening failed 15 times. I guess this is a real problem??
            logging.error("Failed to open serial port.")
            logging.error("Error: {}".format(saved_exception))
            raise TockLoaderException("Unable to open serial port")

    def attached_board_exists(self):
        try:
            # If `_determine_port()` returns, then it found a port, if it
            # raises an exception then it did not.
            self._determine_port(any=True)
            return True
        except:
            return False

    def open_link_to_board(self, listen=False):
        """
        Open the serial port to the chip/bootloader.

        Also sets up a local port for determining when two Tockloader instances
        are running simultaneously.

        Set the argument `listen` to true if the serial port is being setup
        because we are planning to run `run_terminal`.
        """
        port = self._determine_port()
        self._configure_serial_port(port)

        # Only one process at a time can talk to a serial port (reliably).
        # Before connecting, check whether there is another tockloader process
        # running, and if it's a listen, pause that listen (unless we are also
        # doing a listen), otherwise bail out.

        # Windows has only partial unix socket support, so Python rejects them.
        # Work around this by listening on a reasonably-unlikely-to-collide
        # localhost port derived from the serial port name.
        if _IS_WINDOWS:
            self.comm_port = self._get_serial_port_hashed_to_ip_port()
            self.client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.client_sock.connect(("localhost", self.comm_port))
                logging.debug("Connected to existing `tockloader listen`")
            except ConnectionRefusedError:
                logging.debug(
                    f"No other listen instances running (tried localhost::{self.comm_port})"
                )
                self.client_sock = None
        else:
            self.comm_path = "/tmp/tockloader." + self._get_serial_port_hash()
            if os.path.exists(self.comm_path):
                self.client_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    self.client_sock.connect(self.comm_path)
                except ConnectionRefusedError:
                    logging.warning("Found stale tockloader server, removing.")
                    logging.warning(
                        "This may occur if a previous tockloader instance crashed."
                    )
                    os.unlink(self.comm_path)
                    self.client_sock = None
            else:
                self.client_sock = None

        # Check if another tockloader instance exists based on whether we were
        # able to create a socket to it.
        if self.client_sock:
            # If we could connect, and we are trying to do a listen on the same
            # serial port, then we should exit and notify the user there is
            # already an active tockloader process.
            if listen:
                # We tell the other tockloader not to mind us and then print
                # an error to the user.
                self.client_sock.sendall("Version 1\n".encode("utf-8"))
                self.client_sock.sendall("Ignore\n".encode("utf-8"))
                self.client_sock.close()
                raise TockLoaderException(
                    "Another tockloader process is already running"
                )

            self.client_sock.sendall("Version 1\n".encode("utf-8"))
            self.client_sock.sendall("Stop Listening\n".encode("utf-8"))

            r = ""
            while True:
                while "\n" not in r:
                    r += self.client_sock.recv(100).decode("utf-8")

                if r[: len("Busy\n")] == "Busy\n":
                    r = r[len("Busy\n") :]
                    raise TockLoaderException(
                        "Another tockloader process is active on this serial port"
                    )

                if r[: len("Pausing\n")] == "Pausing\n":
                    r = r[len("Pausing\n") :]

                    def restart_listener(path):
                        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                        try:
                            sock.connect(path)
                            sock.sendall("Version 1\n".encode("utf-8"))
                            sock.sendall("Start Listening\n".encode("utf-8"))
                            sock.close()
                            logging.info("Resumed other tockloader listen session")
                        except:
                            logging.warning(
                                "Error restarting other tockloader listen process."
                            )
                            logging.warning(
                                "You may need to manually begin listening again."
                            )

                    atexit.register(restart_listener, self.comm_path)

                if r[: len("Paused\n")] == "Paused\n":
                    r = r[len("Paused\n") :]
                    logging.info(
                        "Paused an active tockloader listen in another session."
                    )
                    break

        else:
            # We seem to be the only tockloader instance. In that case, we want
            # to spawn a background thread that listens on a socket in case
            # another tockloader instance starts.
            #
            # This thread will handle two cases. In case one, this instance of
            # tockloader is performing an active task, like installing a new app
            # or listing the already installed apps. In that case we will tell
            # the new tockloader instance to wait until we are finished.
            #
            # In case two, we are doing a passive listen on the socket for
            # `printf()` messages from the board. In this case we will pause our
            # listen, allow the other tockloader instance to complete, and then
            # resume listening.

            if _IS_WINDOWS:
                self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_sock.bind(("localhost", self.comm_port))
                logging.debug(f"listening on localhost::{self.comm_port}")
            else:
                # Create the socket we will listen on.
                self.server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

                # Close the file descriptor if exec() is called (apparently). I'm
                # not sure why we need this (or if we do).
                flags = fcntl.fcntl(self.server_sock, fcntl.F_GETFD)
                fcntl.fcntl(self.server_sock, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)

                self.server_sock.bind(self.comm_path)

            # Finish setting up the socket, and spawn a thread to listen on that
            # socket.
            self.server_sock.listen(1)
            self.server_event = threading.Event()
            self.server_thread = threading.Thread(
                target=self._server_thread,
                daemon=True,
                name="Tockloader server listen thread",
            )
            self.server_thread.start()

            # Set function to run when tockloader finishes that closes the
            # thread and removes the unix socket path.
            def server_cleanup():
                if self.server_sock is not None:
                    self.server_sock.close()
                    if not _IS_WINDOWS:
                        os.unlink(self.comm_path)

            atexit.register(server_cleanup)

        self._open_serial_port()

        # Do a delay if we are skipping the bootloader entry process (which
        # would normally have a delay in it). We need to send a dummy message
        # because that seems to cause the serial to reset the board, and then
        # wait to make sure the bootloader is booted and ready.
        if hasattr(self.args, "no_bootloader_entry") and self.args.no_bootloader_entry:
            # Writing a bogus message seems to start the counter.
            self.sp.write(self.SYNC_MESSAGE)
            time.sleep(0.1)

    # While tockloader has a serial connection open, it leaves a unix socket
    # open for other tockloader processes. For most of the time, this will
    # simply report 'Busy\n' and new tockloader processes will back off and not
    # steal the serial port. If miniterm is active, however, this process will:
    #
    # 1. Send back 'Pausing\n'
    # 2. Stop the miniterm session and close the serial port.
    # 3. Send 'Paused\n'
    # 4. Wait until a new socket connection is made to receive further
    #    instructions.
    def _server_thread(self):
        while True:
            try:
                connection, client_address = self.server_sock.accept()
            except Exception:
                # `accept()` seems to throw an exception on some platforms
                # when `self.server_sock.close()` is called. If this happens,
                # we just call it quits on this listen.
                return

            r = ""
            while "\n" not in r:
                r += connection.recv(100).decode("utf-8")

            if r[: len("Version 1\n")] != "Version 1\n":
                logging.warning("Got unexpected connection: >{}< ; dropping".format(r))
                connection.close()
                continue

            r = r[len("Version 1\n") :]
            while "\n" not in r:
                r += connection.recv(100).decode("utf-8")

            if r == "Start Listening\n":
                self.server_event.set()
                continue

            if r == "Ignore\n":
                # The other tockloader was just checking to see if we exist.
                # We can just close the connection on our end and keep waiting.
                connection.close()
                continue

            # The only other command is 'Stop Listening'
            if r != "Stop Listening\n":
                logging.warning("Got unexpected command: >{}< ; dropping".format(r))
                connection.close()
                continue

            if not hasattr(self, "miniterm"):
                # Running something other than listen, reject other tockloader
                connection.sendall("Busy\n".encode("utf-8"))
                connection.close()
                continue

            # If we get here, stop `tockloader listen` for a bit, and resume
            # with other tockloader session is finished.

            # Notify other tockloader we are working on it.
            connection.sendall("Pausing\n".encode("utf-8"))

            # Set the reason so the main thread knows what to do.
            self.miniterm.miniterm_exit_reason = "paused_another_tockloader"

            # Stop miniterm. We do this in a very specific way so that miniterm
            # ends up in the correct state and we can exit with ctrl-c as
            # expected.
            self.miniterm._stop_reader()
            self.miniterm.stop()
            self.miniterm.console.cancel()

            # Close the serial port since we want to release this so the other
            # tockloader can use it.
            self.sp.close()

            # Now tell the other tockloader we have paused.
            connection.sendall("Paused\n".encode("utf-8"))

            # That's it for this connection.
            connection.close()

    def _get_serial_port_hash(self):
        """
        Get an identifier that will be consistent for this serial port on this
        machine that is also guaranteed to not have any special characters (like
        slashes) that would interfere with using as a file name.
        """
        return hashlib.sha1(self.sp.port.encode("utf-8")).hexdigest()

    def _get_serial_port_hashed_to_ip_port(self):
        """
        This is a bit of a hack, but it's means to find a reasonably unlikely
        to collide port number based on the serial port used to talk to the
        board.
        """
        return int(self._get_serial_port_hash(), 16) % 40000 + 10000

    def _toggle_bootloader_entry_DTR_RTS(self):
        """
        Use the DTR and RTS lines on UART to reset the chip and assert the
        bootloader select pin to enter bootloader mode so that the chip will
        start in bootloader mode.
        """
        # Reset the SAM4L
        self.sp.dtr = 1
        # Set RTS to make the SAM4L go into bootloader mode
        self.sp.rts = 1
        # Wait for the reset to take effect
        time.sleep(0.1)
        # Let the SAM4L startup
        self.sp.dtr = 0
        # Wait for 500 ms to make sure the bootloader enters bootloader mode
        time.sleep(0.5)
        # The select line can go back high
        self.sp.rts = 0

    def _wait_for_serial_port(self):
        """
        Wait for the serial port to re-appear, aka the bootloader has started.
        """
        for i in range(0, 30):
            # We start by sleeping. On Linux the serial port does not
            # immediately disappear, so if we do not wait we will immediately
            # discover the serial port again. So we have to wait to give the OS
            # a chance to remove the serial port before we try to re-discover it
            # once the bootloader has started.
            time.sleep(0.5)

            # Try to increase reliability by trying different ways of
            # re-discovering the serial port.
            if i < 10:
                # To start we try to find a serial device with the same serial
                # number as the one that we connected to originally.
                ports = list(serial.tools.list_ports.grep(self.sp_serial_number))

            elif i < 20:
                # If that isn't working, it is possible that the serial number
                # is different between the kernel (which we connected to first)
                # and the bootloader (which is what is now setting up the serial
                # port). The bootloader should have the name "tock" in it,
                # however, so we look for that.
                #
                # Note, this can be problematic if the user has multiple tock
                # boards connected to the computer, since this might find a
                # different board leading to weird behavior.
                ports = list(serial.tools.list_ports.grep("tock"))

            else:
                # In the last case, we try to connect to any available serial port
                # and hope that it is the tock bootloader.
                ports = list(serial.tools.list_ports.comports())
                # Macs will report Bluetooth devices with serial, which is
                # almost certainly never what you want, so drop those.
                ports = [p for p in ports if "Bluetooth-Incoming-Port" not in p.device]

            if len(ports) > 0:
                if self.args.debug:
                    logging.debug(
                        "  On iteration {} found {} port{}".format(
                            i, len(ports), helpers.plural(len(ports))
                        )
                    )
                break
            else:
                if self.args.debug:
                    logging.debug("  Waited iteration {}... Found 0 ports".format(i))

        else:
            raise TockLoaderException("Bootloader did not start")

        # Use the first port.
        port = ports[0].device

        if self.args.debug:
            logging.debug("  Using port {} for the bootloader".format(port))

        return port

    def _toggle_bootloader_entry_baud_rate(self):
        """
        Set the baud rate to 1200 so that the chip will restart into the
        bootloader (if that feature exists).

        Returns `True` if it successfully started the bootloader, `False`
        otherwise.
        """

        # Change the baud rate to tell the board to reset into the bootloader.
        self.sp.baudrate = 1200

        # Now try to read from the serial port. If the changed baud rate caused
        # the chip to reset into bootloader mode, this read should fail. If it
        # doesn't fail, then either this chip doesn't support the baud rate chip
        # (e.g. it has an FTDI chip) or it is already in the bootloader.
        try:
            # Give the chip some time to reset
            time.sleep(0.1)
            # Read which should timeout quickly.
            test_read = self.sp.read(10)
            # If we get here, looks like this entry mode won't work, so we can
            # exit now.
            if self.args.debug:
                logging.debug("Baud rate bootloader entry no-op.")
                if len(test_read) > 0:
                    logging.debug('Read "{}" from board'.format(test_read))

            # Need to reset the baud rate to its original value.
            self.sp.baudrate = 115200
            return False
        except:
            # Read failed. This should mean the chip reset. Continue with this
            # function.
            pass

        logging.info("Waiting for the bootloader to start")
        port = self._wait_for_serial_port()
        self._configure_serial_port(port)
        self._open_serial_port()

        # Board restarted into the bootloader (or at least a new serial port)
        # and we re-setup self.sp to use it.
        return True

    def enter_bootloader_mode(self):
        """
        Reset the chip and assert the bootloader select pin to enter bootloader
        mode. Handle retries if necessary.
        """
        # Try baud rate trick first.
        entered_bootloader = self._toggle_bootloader_entry_baud_rate()
        if not entered_bootloader:
            # If that didn't work, either because the bootloader already active
            # or board doesn't support it, try the DTR/RTS method.
            try:
                # Wrap in try block because this can fail if the serial port was
                # _actually_ closed in the
                # `_toggle_bootloader_entry_baud_rate()` step, but that function
                # did not detect it. This code is all a bunch of data races and
                # balancing not making users wait a long time. So we insert
                # various sleeps, but they may not always be long enough, so
                # there can be false/missed detections.
                self._toggle_bootloader_entry_DTR_RTS()
            except:
                # If we could not toggle DTR/RTS then there is something wrong
                # with the serial port. Hopefully this means that we are in the
                # bootloader and can continue normally. If not, then the
                # PING/PONG check below should catch it. Let's be optimistic.
                #
                # Find bootloader port and try to use it.
                logging.info("Waiting for the bootloader to start")
                port = self._wait_for_serial_port()
                self._configure_serial_port(port)
                self._open_serial_port()

        # Make sure the bootloader is actually active and we can talk to it.
        try:
            self._ping_bootloader_and_wait_for_response()
        except KeyboardInterrupt:
            raise TockLoaderException("Exiting.")
        except:
            try:
                # Give it another go
                time.sleep(1)
                self._toggle_bootloader_entry_DTR_RTS()
                self._ping_bootloader_and_wait_for_response()
            except KeyboardInterrupt:
                raise TockLoaderException("Exiting.")
            except:
                logging.error('Error connecting to bootloader. No "pong" received.')
                logging.error("Things that could be wrong:")
                logging.error("  - The bootloader is not flashed on the chip")
                logging.error("  - The DTR/RTS lines are not working")
                logging.error("  - The serial port being used is incorrect")
                logging.error("  - The bootloader API has changed")
                logging.error("  - There is a bug in this script")
                raise TockLoaderException("Could not attach to the bootloader")

        # Speculatively try to get a faster baud rate.
        if self.args.baud_rate != 115200:
            self._change_baud_rate(self.args.baud_rate)

    def exit_bootloader_mode(self):
        """
        Reset the chip to exit bootloader mode.
        """
        if self.args.jtag:
            return

        # Try to exit with a command to the bootloader. This is a relatively
        # new feature (as of bootloader v1.1.0), so this may not work on many
        # boards.
        self._exit_bootloader()

        # Also try the "reset to exit" method. This works if the DTR line is
        # connected to the reset pin on the MCU.
        try:
            # Wrap all of this in a try block in case the `_exit_bootloader()`
            # method worked, at which point the serial port may be invalid when
            # we get here.
            self.sp.dtr = 1
            # Make sure this line is de-asserted (high)
            self.sp.rts = 0
            # Let the reset take effect
            time.sleep(0.1)
            # Let the SAM4L startup
            self.sp.dtr = 0
        except:
            # I've seen OSError and BrokenPipeError get thrown if the serial
            # port is invalid. I'm not sure there is any viable way to handle
            # different errors, and it probably doesn't matter. These are basic
            # UART config settings, and if they don't work then the chip
            # hopefully has exited the bootloader.
            return

    def _ping_bootloader_and_wait_for_response(self):
        """
        Throws an exception if the device does not respond with a PONG.
        """
        for i in range(30):
            # Try to ping the SAM4L to ensure it is in bootloader mode
            ping_pkt = bytes([self.ESCAPE_CHAR, self.COMMAND_PING])
            self.sp.write(ping_pkt)

            # Read much more than we need in case something got in the
            # serial channel that we need to clear.
            ret = self.sp.read(200)

            if len(ret) == 2 and ret[1] == self.RESPONSE_PONG:
                return
        raise TockLoaderException("No PONG received")

    def _issue_command(
        self, command, message, sync, response_len, response_code, show_errors=True
    ):
        """
        Setup a command to send to the bootloader and handle the response.
        """

        # Generate the message to send to the bootloader
        escaped_message = message.replace(
            bytes([self.ESCAPE_CHAR]), bytes([self.ESCAPE_CHAR, self.ESCAPE_CHAR])
        )
        pkt = escaped_message + bytes([self.ESCAPE_CHAR, command])

        # If there should be a sync/reset message, prepend the outgoing message
        # with it.
        if sync:
            pkt = self.SYNC_MESSAGE + pkt

        # Write the command message.
        self.sp.write(pkt)

        # Response has a two byte header, then response_len bytes. Keeping in
        # mind that bytes can be escaped, keep track of how how many bytes we
        # need to read in.
        bytes_to_read = 2 + response_len

        # Receive the header bytes. Try up to three times in case the command
        # takes longer than we expect.
        ret = b""
        for attempt in range(0, 3):
            # Loop to read in that number of bytes. Only unescape the newest
            # bytes. Start with the header we know we are going to get. This
            # makes checking for dangling escape characters easier.
            ret = self.sp.read(2)

            # Check if we got two bytes. Otherwise, try the read again.
            if len(ret) == 2:
                break

        # Check for errors in the header we just got. We have to stop at this
        # point since otherwise we loop waiting on data we will not get.
        if len(ret) < 2:
            if show_errors:
                logging.error("No response after issuing command")
            return (False, bytes())
        if ret[0] != self.ESCAPE_CHAR:
            if show_errors:
                logging.error("Invalid response from bootloader (no escape character)")
            return (False, ret[0:2])
        if ret[1] != response_code:
            if show_errors:
                logging.error(
                    "Expected return type {:x}, got return {:x}".format(
                        response_code, ret[1]
                    )
                )
            return (False, ret[0:2])

        while bytes_to_read - len(ret) > 0:
            new_data = self.sp.read(bytes_to_read - len(ret))

            # Escape characters are tricky here. We need to make sure that if
            # the last character is an an escape character that it isn't
            # escaping the next character we haven't read yet.
            if new_data.count(self.ESCAPE_CHAR) % 2 == 1:
                # Odd number of escape characters. These can only come in pairs,
                # so read another byte.
                new_data += self.sp.read(1)

            # De-escape, and add to array of read in bytes.
            ret += new_data.replace(
                bytes([self.ESCAPE_CHAR, self.ESCAPE_CHAR]), bytes([self.ESCAPE_CHAR])
            )

        if len(ret) != 2 + response_len:
            if show_errors:
                logging.error(
                    "Incorrect number of bytes received. Expected {}, got {}.".format(
                        2 + response_len, len(ret)
                    )
                )
            return (False, ret[0:2])

        return (True, ret[2:])

    def _change_baud_rate(self, baud_rate):
        """
        If the bootloader on the board supports it and if it succeeds, try to
        increase the baud rate to make everything faster.
        """
        pkt = struct.pack("<BI", 0x01, baud_rate)
        success, ret = self._issue_command(
            self.COMMAND_CHANGE_BAUD_RATE,
            pkt,
            True,
            0,
            self.RESPONSE_OK,
            show_errors=False,
        )

        if success:
            # The bootloader is new enough to support this.
            # Increase the baud rate
            self.sp.baudrate = baud_rate
            # Now confirm that everything is working.
            pkt = struct.pack("<BI", 0x02, baud_rate)
            success, ret = self._issue_command(
                self.COMMAND_CHANGE_BAUD_RATE,
                pkt,
                False,
                0,
                self.RESPONSE_OK,
                show_errors=False,
            )

            if not success:
                # Something went wrong. Go back to old baud rate
                self.sp.baudrate = 115200

    def _exit_bootloader(self):
        """
        Tell the bootloader on the board to exit so the main software can run.

        This uses a command sent over the serial port to the bootloader.
        """
        exit_pkt = bytes([self.ESCAPE_CHAR, self.COMMAND_EXIT])
        self.sp.write(exit_pkt)

    def flash_binary(self, address, binary, pad=True):
        """
        Write pages until a binary has been flashed. binary must have a length
        that is a multiple of page size.
        """
        # Make sure the binary is a multiple of the page size by padding 0xFFs
        if len(binary) % self.page_size != 0:
            remaining = self.page_size - (len(binary) % self.page_size)
            if pad:
                binary += bytes([0xFF] * remaining)
                logging.info("Padding binary with {} 0xFFs.".format(remaining))
            else:
                # Don't pad, actually use the bytes already on the chip
                missing = self.read_range(address + len(binary), remaining)
                binary += missing
                logging.info(
                    "Padding binary with {} bytes already on chip.".format(remaining)
                )

        # Get indices of pages that have valid data to write.
        valid_pages = []
        for i in range(len(binary) // self.page_size):
            if not all(
                b == 0 for b in binary[i * self.page_size : (i + 1) * self.page_size]
            ):
                valid_pages.append(i)

        # Make sure that there is at least one valid page. If we are only trying
        # to write 0s then all pages would have been removed. In that case, we
        # want to write all requested pages.
        if len(valid_pages) == 0:
            for i in range(len(binary) // self.page_size):
                valid_pages.append(i)

        # Make sure to always include one blank page (if exists) after the end
        # of a valid page. There might be a usable 0 on the next page. It's
        # unlikely there is more than entire page of valid 0s on the next page.
        ending_pages = []
        for i in valid_pages:
            if (not (i + 1) in valid_pages) and (
                (i + 1) < (len(binary) // self.page_size)
            ):
                ending_pages.append(i + 1)
        valid_pages = valid_pages + ending_pages

        # Loop through the binary by pages at a time until it has been flashed
        # to the chip.
        for i in tqdm(valid_pages):
            # Create the packet that we send to the bootloader. First four
            # bytes are the address of the page.
            pkt = struct.pack("<I", address + (i * self.page_size))

            # Next are the bytes that go into the page.
            pkt += binary[i * self.page_size : (i + 1) * self.page_size]

            # Write to bootloader
            success, ret = self._issue_command(
                self.COMMAND_WRITE_PAGE, pkt, True, 0, self.RESPONSE_OK
            )

            if not success:
                logging.error("Error when flashing page")
                if ret[1] == self.RESPONSE_BADADDR:
                    raise TockLoaderException(
                        "Error: RESPONSE_BADADDR: Invalid address for page to write (address: 0x{:X})".format(
                            address + (i * self.page_size)
                        )
                    )
                elif ret[1] == self.RESPONSE_INTERROR:
                    raise TockLoaderException(
                        "Error: RESPONSE_INTERROR: Internal error when writing flash"
                    )
                elif ret[1] == self.RESPONSE_BADARGS:
                    raise TockLoaderException(
                        "Error: RESPONSE_BADARGS: Invalid length for flash page write"
                    )
                else:
                    raise TockLoaderException("Error: 0x{:X}".format(ret[1]))

            if self.args.debug:
                logging.debug(
                    "  [{}] Wrote page {}/{}".format(
                        datetime.datetime.now(), i, len(binary) // self.page_size
                    )
                )

        # And check the CRC
        self._check_crc(address, binary, valid_pages)

    def read_range(self, address, length):
        # Can only read up to 4095 bytes at a time.
        MAX_READ = 4095
        read = bytes()
        this_length = 0
        remaining = length
        while remaining > 0:
            if remaining > MAX_READ:
                this_length = MAX_READ
                remaining -= MAX_READ
            else:
                this_length = remaining
                remaining = 0

            message = struct.pack("<IH", address, this_length)
            success, flash = self._issue_command(
                self.COMMAND_READ_RANGE,
                message,
                True,
                this_length,
                self.RESPONSE_READ_RANGE,
            )

            if not success:
                return b""
            else:
                read += flash

            address += this_length

        return read

    def clear_bytes(self, address):
        logging.debug("Clearing bytes starting at {:#0x}".format(address))

        # If this is paged aligned, then this is easy.
        if address % self.page_size == 0:
            # We can just erase the entire page.
            self.erase_page(address)

        else:
            # Otherwise, we write a few 0xFF as an entire page.
            binary = bytes([0xFF] * 8)
            address, binary = self.__align_and_stretch_to_page(binary, address)
            self.flash_binary(address, binary)

    def erase_page(self, address):
        message = struct.pack("<I", address)
        success, ret = self._issue_command(
            self.COMMAND_ERASE_PAGE, message, True, 0, self.RESPONSE_OK
        )

        if not success:
            if ret[1] == self.RESPONSE_BADADDR:
                raise TockLoaderException(
                    "Error: Page erase address was not on a page boundary."
                )
            elif ret[1] == self.RESPONSE_BADARGS:
                raise TockLoaderException(
                    "Error: Need to supply erase page with correct 4 byte address."
                )
            elif ret[1] == self.RESPONSE_INTERROR:
                raise TockLoaderException(
                    "Error: Internal error when erasing flash page."
                )
            else:
                raise TockLoaderException("Error: 0x{:X}".format(ret[1]))

    def set_start_address(self, address):
        message = struct.pack("<I", address)
        success, ret = self._issue_command(
            self.COMMAND_SET_START_ADDRESS, message, True, 0, self.RESPONSE_OK
        )

        if not success:
            if ret[1] == self.RESPONSE_BADARGS:
                raise TockLoaderException("Error: Need to supply start address.")
            else:
                raise TockLoaderException("Error: 0x{:X}".format(ret[1]))

    def _get_crc_internal_flash(self, address, length):
        """
        Get the bootloader to compute a CRC.
        """
        message = struct.pack("<II", address, length)
        success, crc = self._issue_command(
            self.COMMAND_CRC_INTERNAL_FLASH,
            message,
            True,
            4,
            self.RESPONSE_CRC_INTERNAL_FLASH,
        )

        # There is a bug in a version of the bootloader where the CRC returns 6
        # bytes and not just 4. Need to read just in case to grab those extra
        # bytes.
        self.sp.read(2)

        if not success:
            if crc[1] == self.RESPONSE_BADADDR:
                raise TockLoaderException(
                    "Error: RESPONSE_BADADDR: Invalid address for CRC (address: 0x{:X})".format(
                        address
                    )
                )
            elif crc[1] == self.RESPONSE_BADARGS:
                raise TockLoaderException(
                    "Error: RESPONSE_BADARGS: Invalid length for CRC check"
                )
            else:
                raise TockLoaderException("Error: 0x{:X}".format(crc[1]))

        return crc

    def _check_crc(self, address, binary, valid_pages):
        """
        Compares the CRC of the local binary to the one calculated by the
        bootloader.
        """

        def get_sequences(l):
            """
            Find the start and end of sequences in `l`. [0, 1, 2, 5, 6, 11]
            would return: [(0, 3), (5, 7), (11, 12)].
            """
            sequences = []
            start = -1
            last = -1
            for i in l:
                if start == -1:
                    start = i
                else:
                    if i - 1 == start or i - 1 == last:
                        last = i
                    else:
                        if last == -1:
                            last = start + 1
                        sequences.append((start, last))
                        start = i
                        last = -1
            sequences.append((start, l[-1] + 1))
            return sequences

        # Compute the CRC for each stretch of pages in the flashed binary.
        crcs = []
        for start, last in get_sequences(valid_pages):
            # Found end of a run. Check CRC.
            crc_address = address + (start * self.page_size)
            crc_length = (last - start) * self.page_size

            # Check the CRC
            crc_data = self._get_crc_internal_flash(crc_address, crc_length)

            # Now interpret the returned bytes as the CRC
            crc_bootloader = struct.unpack("<I", crc_data[0:4])[0]

            # Calculate the CRC locally
            crc_function = crcmod.mkCrcFun(0x104C11DB7, initCrc=0, xorOut=0xFFFFFFFF)
            crc_loader = crc_function(
                binary[start * self.page_size : last * self.page_size], 0
            )

            # Add to list of crcs to compare
            crcs.append((crc_bootloader, crc_loader))

        # Check each run of pages.
        for crc_bootloader, crc_loader in crcs:
            if crc_bootloader != crc_loader:
                raise TockLoaderException(
                    "Error: CRC check failed. Expected: 0x{:04x}, Got: 0x{:04x}".format(
                        crc_loader, crc_bootloader
                    )
                )
        logging.info("CRC check passed. Binaries successfully loaded.")

    def get_attribute(self, index):
        # Check for cached value.
        if self.attributes[index] != "uncached":
            return self.attributes[index]

        # Otherwise read from board.
        message = struct.pack("<B", index)
        success, ret = self._issue_command(
            self.COMMAND_GET_ATTRIBUTE, message, True, 64, self.RESPONSE_GET_ATTRIBUTE
        )

        if not success:
            if ret[1] == self.RESPONSE_BADADDR:
                raise TockLoaderException("Error: Attribute number is invalid.")
            elif ret[1] == self.RESPONSE_BADARGS:
                raise TockLoaderException(
                    "Error: Need to supply a correct attribute index."
                )
            else:
                raise TockLoaderException("Error: 0x{:X}".format(ret[1]))
        attribute = self._decode_attribute(ret)

        # Cache attribute
        self.attributes[index] = attribute

        return attribute

    def get_all_attributes(self):
        attributes = []
        for index in range(0, 16):
            attributes.append(self.get_attribute(index))
        return attributes

    def set_attribute(self, index, raw):
        # Clear cached entry just in case.
        self.attributes[index] = "uncached"

        message = struct.pack("<B", index) + raw
        success, ret = self._issue_command(
            self.COMMAND_SET_ATTRIBUTE, message, True, 0, self.RESPONSE_OK
        )

        if not success:
            if ret[1] == self.RESPONSE_BADADDR:
                raise TockLoaderException("Error: Attribute number is invalid.")
            elif ret[1] == self.RESPONSE_BADARGS:
                raise TockLoaderException(
                    "Error: Wrong length of attribute set packet."
                )
            elif ret[1] == self.RESPONSE_INTERROR:
                raise TockLoaderException(
                    "Error: Internal error when setting attribute."
                )
            else:
                raise TockLoaderException("Error: 0x{:X}".format(ret[1]))

    def bootloader_is_present(self):
        """
        For this communication protocol we can safely say the bootloader is
        present.
        """
        return True

    def get_bootloader_version(self):
        success, ret = self._issue_command(
            self.COMMAND_INFO, bytes(), True, 193, self.RESPONSE_INFO
        )

        if not success:
            raise TockLoaderException("Error: 0x{:X}".format(ret[1]))

        length = ret[0]
        json_data = ret[1 : 1 + length].decode("utf-8")
        try:
            info = json.loads(json_data)

            if self.args.debug:
                logging.debug(info)

            return info["version"]
        except:
            # Could not get a valid version from the board.
            # In this case we don't know what the version is.
            return None

    def determine_current_board(self):
        if self.board and self.arch and self.page_size > 0:
            # These are already set! Yay we are done.
            return

        # If settings aren't set yet, we need to see if they are set on the
        # board. The primary (only?) way to do this is to look at attributes.
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
        if self.board == None:
            logging.error('The bootloader does not have a "board" attribute.')
            logging.error(
                "Please update the bootloader or specify a board; e.g. --board hail"
            )
        if self.arch == None:
            logging.error('The bootloader does not have an "arch" attribute.')
            logging.error(
                "Please update the bootloader or specify an arch; e.g. --arch cortex-m4"
            )
        if self.page_size == 0:
            logging.error('The bootloader does not have an "pagesize" attribute.')
            logging.error(
                "Please update the bootloader or specify a page size for flash; e.g. --page-size 512"
            )

        if self.board == None or self.arch == None or self.page_size == 0:
            raise TockLoaderException(
                "Could not determine the board and/or architecture"
            )

    def run_terminal(self):
        """
        Run miniterm for receiving data from the board.
        """
        logging.info("Listening for serial output.")

        # Create a custom filter for miniterm that prepends the date.
        class timestamper(serial.tools.miniterm.Transform):
            """Prepend output lines with timestamp"""

            def __init__(self):
                self.last = None

            def rx(self, text):
                # Only prepend the date if the last character returned
                # was a \n.
                last = self.last
                self.last = text[-1]
                if last == "\n" or last == None:
                    return "[{}] {}".format(datetime.datetime.now(), text)
                else:
                    return text

        # Create a custom filter for miniterm that prepends the number of
        # printed messages.
        class counter(serial.tools.miniterm.Transform):
            """Prepend output lines with a message count"""

            def __init__(self):
                self.last = None
                self.count = 0

            def rx(self, text):
                # Only prepend the date if the last character returned
                # was a \n.
                last = self.last
                self.last = text[-1]
                if last == "\n" or last == None:
                    count = self.count
                    self.count += 1
                    return "[{:>6}] {}".format(count, text)
                else:
                    return text

        # Add our custom filter to the list that miniterm knows about
        serial.tools.miniterm.TRANSFORMATIONS["timestamper"] = timestamper
        serial.tools.miniterm.TRANSFORMATIONS["counter"] = counter

        # Choose the miniterm filter we want to use. Normally we just use
        # default, which just prints to terminal, but we can also print
        # timestamps.
        filters = ["default"]
        if self.args.timestamp:
            filters.append("timestamper")
        if self.args.count:
            filters.append("counter")

        # Hack the miniterm library for two reasons:
        #
        # 1. We want to know _why_ the miniterm session ended. If it ended
        #    because the user hit ctrl-c, then we want to just exit. However, if
        #    it ended because the serial port failed, then we want to try to
        #    reconnect. The serial port can come-and-go if the device is running
        #    a CDC over UART stack on the microcontroller, and the device was
        #    reset (i.e. the reset button was pressed). That will cause the USB
        #    stack to reset and the serial port to dissapear until the stack is
        #    reinitialized. Rather than force the user to re-run `tockloader
        #    listen`, we try to automatically reconnect.
        #
        # 2. We need to catch the exception that comes with the serial port
        #    failing (i.e. disappearing). If we don't, then it crashes. Miniterm
        #    just raises this exception and crashes by default.
        r = serial.tools.miniterm.Miniterm.reader

        def my_miniterm_reader(self):
            try:
                # Run the existing reader function.
                r(self)
            except Exception as e:
                # Mark that the failure occurred on the read side (this occurs
                # if the serial port is closed/removed).
                self.miniterm_exit_reason = "serial_port_failure"

        serial.tools.miniterm.Miniterm.reader = my_miniterm_reader

        # Use trusty miniterm
        self.miniterm = serial.tools.miniterm.Miniterm(
            self.sp, echo=False, eol="crlf", filters=filters
        )

        # Ctrl+c to exit.
        self.miniterm.exit_character = serial.tools.miniterm.unichr(0x03)

        # Set encoding.
        self.miniterm.set_rx_encoding("UTF-8")
        self.miniterm.set_tx_encoding("UTF-8")

        # Hack to add our own flag. If this is `None` then miniterm exited for
        # normal reasons (i.e. a ctrl-c) and we want to exit. However, we set
        # this value if miniterm exists for other reasons, and this lets us know
        # when to try to reconnect.
        self.miniterm.miniterm_exit_reason = None

        # And go!
        self.miniterm.start()

        def reconnect_terminal(self):
            logging.info(" ----- Waiting for serial port to reconnect...")

            # Now we have to wait for the serial port to come back. When it
            # does, configure it and open it.
            new_port = self._wait_for_serial_port()
            self._configure_serial_port(new_port)
            self._open_serial_port()

            # We have a new object for the serial port at this point. Notify
            # miniterm of the new sp object.
            self.miniterm.serial = self.sp

            # And finally we can re-start the listener.
            self.miniterm.start()

        # Now wait for miniterm to finish in a loop. This allows us to try again
        # as needed.
        while True:
            self.miniterm.join(True)

            # If we get here, miniterm ended. We want to find out why, so we can
            # maybe restart.
            if self.miniterm.miniterm_exit_reason == "serial_port_failure":
                # Failure happened due to a closed serial port (or some other
                # serial port exception). Try to reconnect and resume listening.

                # Reset flag.
                self.miniterm.miniterm_exit_reason = None

                # Notify user.
                logging.info(" ----- Serial port crashed. Waiting to reconnect...")

                # Close the port on our end. This fixes up internal pyserial
                # state, since the OS-level serial port is gone, but pyserial
                # won't let us reconnect if it thinks the port is already open.
                self.sp.close()

                # Restart miniterm
                reconnect_terminal(self)

            elif self.miniterm.miniterm_exit_reason == "paused_another_tockloader":
                # Miniterm exited because of another tockloader instance trying
                # to run and use the same serial port. We wait until the other
                # tockloader has finished.

                # Reset flag.
                self.miniterm.miniterm_exit_reason = None

                logging.info(" ----- Paused listen for another tockloader session...")

                # This is our wait flag. When this flag is set and `wait()`
                # returns we can continue listening.
                self.server_event.wait()
                self.server_event.clear()

                logging.info(" ----- Resuming listen...")

                # Restart miniterm
                reconnect_terminal(self)

            else:
                # Normal exit (ctrl-c).
                break

        # Done with the serial port, close everything for miniterm.
        self.miniterm.close()
