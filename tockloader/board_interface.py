"""
Generic interface for communicating with boards.

While it would be nice if there was only a single method to communicate with
boards, in practice that is not feasible. So, this file includes the interface
that different communication methods must implement to effectively support
tockloader.
"""

import logging
import os

from .exceptions import TockLoaderException


class BoardInterface:
    """
    Base class for interacting with hardware boards. All of the class functions
    should be overridden to support a new method of interacting with a board.
    """

    KNOWN_BOARDS = {
        "hail": {
            "description": "Hail development module.",
            "arch": "cortex-m4",
            "page_size": 512,
            "jlink": {
                "device": "ATSAM4LC8C",
            },
        },
        "imix": {
            "description": "Low-power IoT research platform",
            "arch": "cortex-m4",
            "page_size": 512,
            "jlink": {
                "device": "ATSAM4LC8C",
            },
        },
        "nrf51dk": {
            "description": "Nordic nRF51-based development kit",
            "arch": "cortex-m0",
            "page_size": 1024,
            "no_attribute_table": True,
            "jlink": {
                "device": "nrf51422",
            },
            "openocd": {
                "cfg": "nordic_nrf51_dk.cfg",
                "options": ["workareazero"],
            },
        },
        "nrf52dk": {
            "description": "Nordic nRF52-based development kit",
            "arch": "cortex-m4",
            "page_size": 4096,
            "no_attribute_table": True,
            "jlink": {
                "device": "nrf52",
            },
            "openocd": {
                "cfg": "nordic_nrf52_dk.cfg",
            },
        },
        "nano33ble": {
            "description": "Arduino Nano 33 BLE board",
            "arch": "cortex-m4",
            "page_size": 4096,
        },
        "launchxl-cc26x2r1": {
            "description": "TI CC26x2-based launchpad",
            "arch": "cortex-m4",
            "page_size": 512,
            "no_attribute_table": True,
            "jlink": {
                "device": "cc2652r1f",
                "speed": 4000,
                "if": "jtag",
            },
            "openocd": {
                "cfg": "ti_cc26x2_launchpad.cfg",
                "options": ["noreset", "resume"],
                "commands": {
                    "program": "flash write_image erase {{binary}} {address:#x};\
                                verify_image {{binary}} {address:#x};"
                },
            },
        },
        "ek-tm4c1294xl": {
            "description": "TI TM4C1294-based launchpad",
            "arch": "cortex-m4",
            "page_size": 512,
            "no_attribute_table": True,
            "openocd": {
                "cfg": "ek-tm4c1294xl.cfg",
            },
        },
        "arty": {
            "description": "Arty FPGA running SiFive RISC-V core",
            "arch": "rv32imac",
            # arty exposes just the flash to openocd, this does the mapping
            # from the address map to what openocd must use.
            "address_translator": lambda addr: addr - 0x40000000,
            "page_size": 0x10000,
            "no_attribute_table": True,
            "openocd": {
                "options": ["nocmdprefix"],
                "prefix": "interface ftdi;\
                           ftdi_vid_pid 0x0403 0x6010;\
                           ftdi_channel 0;\
                           ftdi_layout_init 0x0088 0x008b;\
                           reset_config none;\
                           adapter_khz 10000;\
                           transport select jtag;\
                           source [find cpld/xilinx-xc7.cfg];\
                           source [find cpld/jtagspi.cfg];\
                           proc jtagspi_read {{fname offset len}} {{\
                             global _FLASHNAME;\
                             flash read_bank $_FLASHNAME $fname $offset $len;\
                           }};\
                           init;\
                           jtagspi_init 0 {bitfile};".format(
                    bitfile=os.path.join(  # Need path to bscan_spi_xc7a100t.bit
                        os.path.dirname(os.path.realpath(__file__)),
                        "static",
                        "bscan_spi_xc7a100t.bit",
                    )
                ),
                "commands": {
                    "program": "jtagspi_program {{binary}} {address:#x};",
                    "read": "jtagspi_read {{binary}} {address:#x} {length};",
                },
            },
        },
        "litex_arty": {
            "description": "LiteX SoC running on an Arty-A7 board",
            "arch": "rv32imc",
            # Tockloader is currently only supported through the flash file
            # board interface. The file being operated on is loaded into RAM by
            # the LiteX bootloader into the main SDRAM. This does the address
            # translation to the memory-mapped SDRAM bus address.
            "address_translator": lambda addr: addr - 0x40000000,
            "no_attribute_table": True,
            "flash_file": {
                # Set to the maximum RAM size, as the LiteX bootloader will
                # update the flash image into RAM.
                "max_size": 0x10000000,
            },
        },
        "litex_sim": {
            "description": "LiteX SoC running on Verilated simulation",
            "arch": "rv32imc",
            "no_attribute_table": True,
            "flash_file": {
                # This corresponds to the --integrated-rom-size when starting
                # the `litex_sim` Verilated simulation.
                "max_size": 0x00100000,
            },
        },
        "qemu_rv32_virt": {
            "description": "QEMU RISC-V 32 bit virt Platform",
            "arch": "rv32imac",
            # The QEMU-provided binary will be loaded at address 0x80000000
            "address_translator": lambda addr: addr - 0x80000000,
            "no_attribute_table": True,
            "flash_file": {
                # Size of the ROM and PROG region combined, where the resulting
                # binary will be loaded into by QEMU:
                "max_size": 0x00200000,
            },
        },
        "stm32f3discovery": {
            "description": "STM32F3-based Discovery Boards",
            "arch": "cortex-m4",
            "page_size": 2048,
            "no_attribute_table": True,
            "openocd": {
                "prefix": 'interface hla; \
                           hla_layout stlink; \
                           hla_device_desc "ST-LINK/V2-1"; \
                           hla_vid_pid 0x0483 0x374b; \
                           set WORKAREASIZE 0xC000; \
                           source [find target/stm32f3x.cfg];',
            },
        },
        "stm32f4discovery": {
            "description": "STM32F4-based Discovery Boards",
            "arch": "cortex-m4",
            "page_size": 2048,
            "no_attribute_table": True,
            "openocd": {
                "prefix": 'interface hla; \
                           hla_layout stlink; \
                           hla_device_desc "ST-LINK/V2-1"; \
                           hla_vid_pid 0x0483 0x374b; \
                           set WORKAREASIZE 0x40000; \
                           source [find target/stm32f4x.cfg];',
            },
        },
        "nucleof4": {
            "description": "STM32f4-based Nucleo development boards",
            "arch": "cortex-m4",
            "page_size": 2048,
            "no_attribute_table": True,
            "openocd": {
                "cfg": "st_nucleo_f4.cfg",
            },
        },
        "hifive1": {
            "description": "SiFive HiFive1 development board",
            "arch": "rv32imac",
            "page_size": 512,
            "no_attribute_table": True,
            "openocd": {
                "cfg": "sifive-hifive1.cfg",
            },
        },
        "hifive1b": {
            "description": "SiFive HiFive1b development board",
            "arch": "rv32imac",
            "page_size": 512,
            "no_attribute_table": True,
            "jlink": {
                "device": "FE310",
                "if": "jtag",
            },
            "openocd": {
                "cfg": "sifive-hifive1-revb.cfg",
            },
        },
        "edu-ciaa": {
            "description": "Educational NXP board, from the CIAA project",
            "arch": "cortex-m4",
            "page_size": 512,
            "no_attribute_table": True,
            "openocd": {
                "cfg": "ftdi_lpc4337.cfg",
                "options": ["noreset"],
                "commands": {
                    "program": "flash write_image erase {{binary}} {address:#x};verify_image {{binary}} {address:#x};",
                },
            },
        },
        "microbit_v2": {
            "description": "BBC Micro:bit v2",
            "arch": "cortex-m4",
            "page_size": 4096,
            "no_attribute_table": True,
            "openocd": {
                "prefix": "source [find interface/cmsis-dap.cfg]; \
                           transport select swd; \
                           source [find target/nrf52.cfg]; \
                           set WORKAREASIZE 0x40000; \
                           $_TARGETNAME configure -work-area-phys 0x20000000 -work-area-size $WORKAREASIZE -work-area-backup 0; \
                           catch { flash bank $_CHIPNAME.flash nrf51 0x00000000 0 1 1 $_TARGETNAME } err;",
            },
        },
        "raspberry_pi_pico": {
            "description": "Raspberry Pi Pico",
            "arch": "cortex-m0",
            "page_size": 4096,
            "no_attribute_table": True,
            "openocd": {
                "prefix": "source [find interface/raspberrypi-swd.cfg]; \
                           source [find target/rp2040.cfg];",
            },
        },
        "sma_q3": {
            "description": "SMA Q3 smart watch (Bangle.js 2, Jazda)",
            "arch": "cortex-m4",
            "page_size": 4096,
            "no_attribute_table": True,
            "openocd": {
                "prefix": "source [find interface/stlink.cfg]; \
                           interface hla; \
                           source [find target/nrf52.cfg];",
            },
        },
        "particle_boron": {
            "description": "nRF52-based cellular enabled development kit",
            "arch": "cortex-m4",
            "page_size": 4096,
            "no_attribute_table": True,
            "jlink": {
                "device": "nrf52",
            },
        },
    }

    def __init__(self, args):
        self.args = args

        # These settings allow tockloader to correctly communicate with and
        # program the attached hardware platform. They can be set through the
        # following methods:
        #
        # 1. Command line arguments to tockloader.
        # 2. Hardcoded values in the `KNOWN_BOARDS` array.
        # 3. Attributes stored in flash on the hardware board itself.
        #
        # Tockloader looks for these setting in this order, and once a value has
        # been determined, tockloader will stop searching and use that value.
        # For example, if `arch` is set using the `--arch` argument to
        # tockloader, then that will override anything set in `KNOWN_BOARDS` or
        # in the on-board attributes.

        # Start by looking for command line arguments.
        self.board = getattr(self.args, "board", None)
        self.arch = getattr(self.args, "arch", None)
        self.page_size = getattr(self.args, "page_size", 0)

        # Set defaults.
        self.no_attribute_table = False  # We assume this is a full tock board.
        self.address_translator = None

        # Next try to use `KNOWN_BOARDS`.
        self._configure_from_known_boards()

    def _configure_from_known_boards(self):
        """
        If we know the name of the board we are interfacing with, this function
        tries to use the `KNOWN_BOARDS` array to populate other needed settings
        if they have not already been set from other methods.

        This can be used in multiple locations. First, it is used when
        tockloader first starts because if a user passes in the `--board`
        argument then we know the board and can try to pull in settings from
        KNOWN_BOARDS. Ideally, however, the user doesn't have to pass in any
        arguments, but then we won't know what board until after we have had a
        chance to read its attributes. The board at least needs the "board"
        attribute to be set, and then we can use KNOWN_BOARDS to fill in the
        rest.
        """
        if self.board and self.board in self.KNOWN_BOARDS:
            board = self.KNOWN_BOARDS[self.board]
            if self.arch == None and "arch" in board:
                self.arch = board["arch"]
            if self.page_size == 0 and "page_size" in board:
                self.page_size = board["page_size"]
            if self.no_attribute_table == False and "no_attribute_table" in board:
                self.no_attribute_table = board["no_attribute_table"]
            if self.address_translator == None and "address_translator" in board:
                self.address_translator = board["address_translator"]

        # This init only includes the generic settings that all communication
        # methods need. There may be flags specific to a particular
        # communication interface.

    def translate_address(self, address):
        """
        Translate an address from MCU address space to the address required for
        the board interface. This is used for boards where the address passed to
        the board interface is not the address where this region is exposed in
        the MCU address space. This method must be called from the board
        interface implementation prior to memory accesses.
        """
        if self.address_translator is not None:
            translated = self.address_translator(address)

            # Make sure that the translated address is still positive, a
            # negative number would mean accessing before the start of flash
            if translated < 0:
                raise TockLoaderException(
                    "Address {:#02x} not contained in flash".format(address)
                )
        else:
            translated = address

        return translated

    def attached_board_exists(self):
        """
        For this particular board communication channel, check if there appears
        to be a valid board attached to the host that tockloader can communicate
        with.
        """
        return False

    def open_link_to_board(self):
        """
        Open a connection to the board.
        """
        return

    def enter_bootloader_mode(self):
        """
        Get to a mode where we can read & write flash.
        """
        return

    def exit_bootloader_mode(self):
        """
        Get out of bootloader mode and go back to running main code.
        """
        return

    def flash_binary(self, address, binary):
        """
        Write a binary to the address given.
        """
        return

    def read_range(self, address, length):
        """
        Read a specific range of flash.

        If this fails for some reason this should return an empty binary array.
        """
        logging.debug(
            "DEBUG => Read Range, address: {:#010x}, length: {}".format(address, length)
        )

    def clear_bytes(self, address):
        """
        Clear at least one byte starting at `address`.

        This API is designed to support "ending the linked list of apps", or
        clearing flash enough so that the flash after the last valid app will
        not parse as a valid TBF header.

        Different chips with different mechanisms for writing/erasing flash make
        implementing specific erase behavior difficult. Instead, we provide this
        rough API, which is sufficient for the task of ending the linked list,
        but doesn't guarantee exactly how many bytes after address will be
        cleared, or how they will be cleared.
        """
        return

    def get_attribute(self, index):
        """
        Get a single attribute. Returns a dict with two keys: `key` and `value`.
        """
        if self.no_attribute_table:
            return None

        # Default implementation to get an attribute. Reads flash directly and
        # extracts the attribute.
        address = 0x600 + (64 * index)
        attribute_raw = self.read_range(address, 64)
        return self._decode_attribute(attribute_raw)

    def get_all_attributes(self):
        """
        Get all attributes on a board. Returns an array of attribute dicts.
        """
        # Check for cached attributes.
        if hasattr(self, "attributes"):
            return self.attributes

        if self.no_attribute_table:
            return []

        # Read the entire block of attributes directly from flash.
        # This is much faster.
        def chunks(l, n):
            for i in range(0, len(l), n):
                yield l[i : i + n]

        raw = self.read_range(0x600, 64 * 16)
        attributes = [self._decode_attribute(r) for r in chunks(raw, 64)]

        # Cache what we get in case this gets called again.
        self.attributes = attributes

        return attributes

    def set_attribute(self, index, raw):
        """
        Set a single attribute.
        """
        # Remove any cached attributes
        del self.attributes

        address = 0x600 + (64 * index)
        self.flash_binary(address, raw)

    def set_start_address(self, address):
        """
        Set the address the bootloader jumps to to start the actual code.
        """
        # This is only valid if there is a bootloader and this function is
        # re-implemented.
        raise TockLoaderException("No bootloader, cannot set start address.")

    def _decode_attribute(self, raw):
        try:
            key = raw[0:8].decode("utf-8").strip(bytes([0]).decode("utf-8"))
            vlen = raw[8]
            if vlen > 55 or vlen == 0:
                return None
            value = raw[9 : 9 + vlen].decode("utf-8")
            return {"key": key, "value": value}
        except Exception as e:
            return None

    def bootloader_is_present(self):
        """
        Check for the Tock bootloader. Returns `True` if it is present, `False`
        if not, and `None` if unsure.
        """
        return None

    def get_bootloader_version(self):
        """
        Return the version string of the bootloader. Should return a value
        like `0.5.0`, or `None` if it is unknown.
        """
        address = 0x40E
        version_raw = self.read_range(address, 8)
        try:
            return version_raw.decode("utf-8")
        except:
            return None

    def get_kernel_version(self):
        """
        Return the kernel ABI version installed on the board. If the version
        cannot be determined, return `None`.
        """
        # Check if there is an attribute we can use.
        attributes = self.get_all_attributes()
        for attribute in attributes:
            if attribute and attribute["key"] == "kernver":
                kernver = attribute["value"].strip()
                logging.debug('Determined kernel version is "{}".'.format(kernver))
                return kernver

        # If not in an attribute we give up and return None.
        logging.debug("Could not determine kernel version.")
        return None

    def determine_current_board(self):
        """
        Figure out which board we are connected to. Most likely done by reading
        the attributes. Doesn't return anything.
        """
        return

    def get_board_name(self):
        """
        Return the name of the board we are connected to.
        """
        return self.board

    def get_board_arch(self):
        """
        Return the architecture of the board we are connected to.
        """
        return self.arch

    def get_page_size(self):
        """
        Return the size of the page in bytes for the connected board.
        """
        return self.page_size

    def print_known_boards(self):
        """
        Display the boards that have settings configured in tockloader.
        """
        print("Known boards:")
        for board in sorted(self.KNOWN_BOARDS.keys()):
            print(
                "  - {:<20} {}".format(board, self.KNOWN_BOARDS[board]["description"])
            )

    def run_terminal(self):
        raise TockLoaderException(
            "No terminal mechanism implemented for this host->board communication method."
        )

    def _align_and_stretch_to_page(self, address, binary):
        """
        Return a new (address, binary) that is a multiple of the page size
        and is aligned to page boundaries.
        """
        # We want to be aligned and a multiple of this value.
        page_size = self.page_size

        # How much before `address` do we need to start from.
        before = address % page_size
        # How much after the end do we also need to write.
        end = address + len(binary)
        after = (((end + (page_size - 1)) // page_size) * page_size) - end

        if before > 0:
            before_address = address - before
            before_binary = self.read_range(before_address, before)
            binary = before_binary + binary
            address = before_address

        if after > 0:
            after_binary = self.read_range(end, after)
            binary = binary + after_binary

        return (address, binary)
