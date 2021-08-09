import logging
import struct

from .exceptions import TockLoaderException


def roundup(x, to):
    return x if x % to == 0 else x + to - x % to


class TBFTLV:
    def get_tlvid(self):
        return self.TLVID

    def get_size(self):
        return len(self.pack())


class TBFTLVUnknown(TBFTLV):
    def __init__(self, tipe, buffer):
        self.tipe = tipe
        self.buffer = buffer

    def get_tlvid(self):
        return self.tipe

    def pack(self):
        out = struct.pack("<HH", self.tipe, len(self.buffer))
        out += self.buffer
        return out


class TBFTLVMain(TBFTLV):
    TLVID = 0x01

    def __init__(self, buffer):
        self.valid = False

        if len(buffer) == 12:
            base = struct.unpack("<III", buffer)
            self.init_fn_offset = base[0]
            self.protected_size = base[1]
            self.minimum_ram_size = base[2]
            self.valid = True

    def pack(self):
        return struct.pack(
            "<HHIII",
            self.TLVID,
            12,
            self.init_fn_offset,
            self.protected_size,
            self.minimum_ram_size,
        )

    def __str__(self):
        out = "TLV: Main ({})\n".format(self.TLVID)
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "init_fn_offset", self.init_fn_offset, self.init_fn_offset
        )
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "protected_size", self.protected_size, self.protected_size
        )
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "minimum_ram_size", self.minimum_ram_size, self.minimum_ram_size
        )
        return out


class TBFTLVWriteableFlashRegions(TBFTLV):
    TLVID = 0x02

    def __init__(self, buffer):
        self.valid = False

        # Must be a multiple of 8 bytes
        if len(buffer) % 8 == 0:
            self.writeable_flash_regions = []
            for i in range(0, int(len(buffer) / 8)):
                base = struct.unpack("<II", buffer[i * 8 : (i + 1) * 8])
                # Add offset,length.
                self.writeable_flash_regions.append((base[0], base[1]))

    def pack(self):
        out = struct.pack("<HH", self.TLVID, len(self.writeable_flash_regions) * 8)
        for wfr in self.writeable_flash_regions:
            out += struct.pack("<II", wfr[0], wfr[1])
        return out

    def __str__(self):
        out = "TLV: Writeable Flash Regions ({})\n".format(
            self.HEADER_TYPE_WRITEABLE_FLASH_REGIONS
        )
        for i, wfr in enumerate(self.writeable_flash_regions):
            out += "  writeable flash region {}\n".format(i)
            out += "    {:<18}: {:>8} {:>#12x}\n".format("offset", wfr[0], wfr[0])
            out += "    {:<18}: {:>8} {:>#12x}\n".format("length", wfr[1], wfr[1])
        return out


class TBFTLVPackageName(TBFTLV):
    TLVID = 0x03

    def __init__(self, buffer):
        self.package_name = buffer.decode("utf-8")
        self.valid = True

    def pack(self):
        encoded_name = self.package_name.encode("utf-8")
        out = struct.pack("<HH", self.TLVID, len(encoded_name))
        out += encoded_name
        # May need to add padding.
        padding_length = roundup(len(encoded_name), 4) - len(encoded_name)
        if padding_length > 0:
            out += b"\0" * padding_length
        return out

    def __str__(self):
        out = "TLV: Package Name ({})\n".format(self.TLVID)
        out += "  {:<20}: {}\n".format("package_name", self.package_name)
        return out


class TBFTLVPicOption1(TBFTLV):
    TLVID = 0x04

    def __init__(self, buffer):
        self.valid = False

        if len(buffer) == 40:
            base = struct.unpack("<IIIIIIIIII", buffer)
            self.text_offset = base[0]
            self.data_offset = base[1]
            self.data_size = base[2]
            self.bss_memory_offset = base[3]
            self.bss_size = base[4]
            self.relocation_data_offset = base[5]
            self.relocation_data_size = base[6]
            self.got_offset = base[7]
            self.got_size = base[8]
            self.minimum_stack_length = base[9]

            self.valid = True

    def pack(self):
        return struct.pack(
            "<HHIIIIIIIIII",
            self.TLVID,
            40,
            self.text_offset,
            self.data_offset,
            self.data_size,
            self.bss_memory_offset,
            self.bss_size,
            self.relocation_data_offset,
            self.relocation_data_size,
            self.got_offset,
            self.got_size,
            self.minimum_stack_length,
        )

    def __str__(self):
        out = "TLV: PIC Option 1 ({})\n".format(self.TLVID)
        out += "  {:<20}: {}\n".format("PIC", "C Style")
        return out


class TBFTLVFixedAddress(TBFTLV):
    TLVID = 0x05

    def __init__(self, buffer):
        self.valid = False

        if len(buffer) == 8:
            base = struct.unpack("<II", buffer)
            self.fixed_address_ram = base[0]
            self.fixed_address_flash = base[1]
            self.valid = True

    def pack(self):
        return struct.pack(
            "<HHII", self.TLVID, 8, self.fixed_address_ram, self.fixed_address_flash
        )

    def __str__(self):
        out = "TLV: Fixed Addresses ({})\n".format(self.TLVID)
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "fixed_address_ram", self.fixed_address_ram, self.fixed_address_ram
        )
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "fixed_address_flash", self.fixed_address_flash, self.fixed_address_flash
        )
        return out


class TBFTLVKernelVersion(TBFTLV):
    TLVID = 0x08

    def __init__(self, buffer):
        self.valid = False

        if len(buffer) == 4:
            base = struct.unpack("<HH", buffer)
            self.kernel_major = base[0]
            self.kernel_minor = base[1]
            self.valid = True

    def pack(self):
        return struct.pack("<HHHH", self.TLVID, 4, self.kernel_major, self.kernel_minor)

    def __str__(self):
        out = "TLV: Kernel Version ({})\n".format(self.TLVID)
        out += "  {:<20}: {}\n".format("kernel_major", self.kernel_major)
        out += "  {:<20}: {}\n".format("kernel_minor", self.kernel_minor)
        out += "  {:<20}: ^{}.{}\n".format(
            "kernel version", self.kernel_major, self.kernel_minor
        )
        return out


class TBFHeader:
    """
    Tock Binary Format header class. This can parse TBF encoded headers and
    return various properties of the application.
    """

    HEADER_TYPE_MAIN = 0x01
    HEADER_TYPE_WRITEABLE_FLASH_REGIONS = 0x02
    HEADER_TYPE_PACKAGE_NAME = 0x03
    HEADER_TYPE_PIC_OPTION_1 = 0x04
    HEADER_TYPE_FIXED_ADDRESSES = 0x05
    HEADER_TYPE_KERNEL_VERSION = 0x08

    def __init__(self, buffer):
        # Flag that records if this TBF header is valid. This is calculated once
        # when a new TBF header is read in. Any manipulations that tockloader
        # does will not make a TBF header invalid, so we do not need to
        # re-calculate this.
        self.valid = False
        # Whether this TBF header is for an app, or is just padding (or perhaps
        # something else). Tockloader will not change this after the TBF header
        # is initially parsed, so we do not need to re-calculate this and can
        # used a flag here.
        self.app = False
        # Whether the TBF header has been modified from when it was first
        # created (by calling `__init__`). This might happen, for example, if a
        # new flag was set. We keep track of this so that we know if we need to
        # re-flash the TBF header to the board.
        self.modified = False

        # The base fields in the TBF header.
        self.fields = {}
        # A list of TLV entries.
        self.tlvs = []

        full_buffer = buffer

        # Need at least a version number
        if len(buffer) < 2:
            return

        # Get the version number
        self.version = struct.unpack("<H", buffer[0:2])[0]
        buffer = buffer[2:]

        if self.version == 1 and len(buffer) >= 74:
            checksum = self._checksum(full_buffer[0:72])
            buffer = buffer[2:]
            base = struct.unpack("<IIIIIIIIIIIIIIIIII", buffer[0:72])
            buffer = buffer[72:]
            self.fields["total_size"] = base[0]
            self.fields["entry_offset"] = base[1]
            self.fields["rel_data_offset"] = base[2]
            self.fields["rel_data_size"] = base[3]
            self.fields["text_offset"] = base[4]
            self.fields["text_size"] = base[5]
            self.fields["got_offset"] = base[6]
            self.fields["got_size"] = base[7]
            self.fields["data_offset"] = base[8]
            self.fields["data_size"] = base[9]
            self.fields["bss_mem_offset"] = base[10]
            self.fields["bss_mem_size"] = base[11]
            self.fields["min_stack_len"] = base[12]
            self.fields["min_app_heap_len"] = base[13]
            self.fields["min_kernel_heap_len"] = base[14]
            self.fields["package_name_offset"] = base[15]
            self.fields["package_name_size"] = base[16]
            self.fields["checksum"] = base[17]
            self.app = True

            if checksum == self.fields["checksum"]:
                self.valid = True

        elif self.version == 2 and len(buffer) >= 14:
            base = struct.unpack("<HIII", buffer[0:14])
            buffer = buffer[14:]
            self.fields["header_size"] = base[0]
            self.fields["total_size"] = base[1]
            self.fields["flags"] = base[2]
            self.fields["checksum"] = base[3]

            if (
                len(full_buffer) >= self.fields["header_size"]
                and self.fields["header_size"] >= 16
            ):
                # Zero out checksum for checksum calculation.
                nbuf = bytearray(self.fields["header_size"])
                nbuf[:] = full_buffer[0 : self.fields["header_size"]]
                struct.pack_into("<I", nbuf, 12, 0)
                checksum = self._checksum(nbuf)

                remaining = self.fields["header_size"] - 16

                # Now check to see if this is an app or padding.
                if remaining > 0 and len(buffer) >= remaining:
                    # This is an application. That means we need more parsing.
                    self.app = True

                    while remaining >= 4:
                        base = struct.unpack("<HH", buffer[0:4])
                        buffer = buffer[4:]
                        tipe = base[0]
                        length = base[1]

                        remaining -= 4

                        if tipe == self.HEADER_TYPE_MAIN:
                            if remaining >= 12 and length == 12:
                                self.tlvs.append(TBFTLVMain(buffer[0:12]))

                        elif tipe == self.HEADER_TYPE_WRITEABLE_FLASH_REGIONS:
                            if remaining >= length:
                                self.tlvs.append(
                                    TBFTLVWriteableFlashRegions(buffer[0:length])
                                )

                        elif tipe == self.HEADER_TYPE_PACKAGE_NAME:
                            if remaining >= length:
                                self.tlvs.append(TBFTLVPackageName(buffer[0:length]))

                        elif tipe == self.HEADER_TYPE_PIC_OPTION_1:
                            if remaining >= 40 and length == 40:
                                self.tlvs.append(TBFTLVPicOption1(buffer[0:40]))

                        elif tipe == self.HEADER_TYPE_FIXED_ADDRESSES:
                            if remaining >= 8 and length == 8:
                                self.tlvs.append(TBFTLVFixedAddress(buffer[0:8]))

                        elif tipe == self.HEADER_TYPE_KERNEL_VERSION:
                            if remaining >= 4 and length == 4:
                                self.tlvs.append(TBFTLVKernelVersion(buffer[0:4]))

                        else:
                            logging.warning("Unknown TLV block in TBF header.")
                            logging.warning("You might want to update tockloader.")

                            # Add the unknown data to the stored state so we can
                            # put it back afterwards.
                            self.tlvs.append(TBFTLVUnknown(tipe, buffer[0:length]))

                        # All blocks are padded to four byte, so we may need to
                        # round up.
                        length = roundup(length, 4)
                        buffer = buffer[length:]
                        remaining -= length

                    if checksum == self.fields["checksum"]:
                        self.valid = True
                    else:
                        logging.error(
                            "Checksum mismatch. in packet: {:#x}, calculated: {:#x}".format(
                                self.fields["checksum"], checksum
                            )
                        )

                else:
                    # This is just padding and not an app.
                    if checksum == self.fields["checksum"]:
                        self.valid = True

    def is_valid(self):
        """
        Whether the CRC and other checks passed for this header.
        """
        return self.valid

    def is_app(self):
        """
        Whether this is an app or padding.
        """
        return self.app

    def is_modified(self):
        """
        Whether the TBF header has been modified by Tockloader after it was
        initially read in (either from a new TAB or from the board).
        """
        return self.modified

    def is_enabled(self):
        """
        Whether the application is marked as enabled. Enabled apps start when
        the board boots, and disabled ones do not.
        """
        if not self.valid:
            return False
        elif self.version == 1:
            # Version 1 apps don't have this bit so they are just always enabled
            return True
        else:
            return self.fields["flags"] & 0x01 == 0x01

    def is_sticky(self):
        """
        Whether the app is marked sticky and won't be erase during normal app
        erases.
        """
        if not self.valid:
            return False
        elif self.version == 1:
            # No sticky bit in version 1, so they are not sticky
            return False
        else:
            return self.fields["flags"] & 0x02 == 0x02

    def set_flag(self, flag_name, flag_value):
        """
        Set a flag in the TBF header.

        Valid flag names: `enable`, `sticky`
        """
        if self.version == 1 or not self.valid:
            return

        if flag_name == "enable":
            if flag_value:
                self.fields["flags"] |= 0x01
            else:
                self.fields["flags"] &= ~0x01
            self.modified = True

        elif flag_name == "sticky":
            if flag_value:
                self.fields["flags"] |= 0x02
            else:
                self.fields["flags"] &= ~0x02
            self.modified = True

    def get_app_size(self):
        """
        Get the total size the app takes in bytes in the flash of the chip.
        """
        return self.fields["total_size"]

    def set_app_size(self, size):
        """
        Set the total size the app takes in bytes in the flash of the chip.

        Since this does not change the header size we do not need to update
        any other fields in the header.
        """
        self.fields["total_size"] = size
        self.modified = True

    def get_header_size(self):
        """
        Get the size of the header in bytes. This includes any alignment
        padding at the end of the header.
        """
        if self.version == 1:
            return 74
        else:
            return self.fields["header_size"]

    def get_size_before_app(self):
        """
        Get the number of bytes before the actual app binary in the .tbf file.
        """
        if self.version == 1:
            return 74
        else:
            header_size = self.fields["header_size"]

            main_tlv = self._get_tlv(self.HEADER_TYPE_MAIN)
            protected_size = main_tlv.protected_size

            return header_size + protected_size

    def get_app_name(self):
        """
        Return the package name if it was encoded in the header, otherwise
        return a tuple of (package_name_offset, package_name_size).
        """
        tlv = self._get_tlv(self.HEADER_TYPE_PACKAGE_NAME)
        if tlv:
            return tlv.package_name
        elif (
            "package_name_offset" in self.fields and "package_name_size" in self.fields
        ):
            return (
                self.fields["package_name_offset"],
                self.fields["package_name_size"],
            )
        else:
            return ""

    def has_fixed_addresses(self):
        """
        Return true if this TBF header includes the fixed addresses TLV.
        """
        return self._get_tlv(self.HEADER_TYPE_FIXED_ADDRESSES) != None

    def get_fixed_addresses(self):
        """
        Return (fixed_address_ram, fixed_address_flash) if there are fixed
        addresses, or None.
        """
        tlv = self._get_tlv(self.HEADER_TYPE_FIXED_ADDRESSES)
        if tlv:
            return (tlv.fixed_address_ram, tlv.fixed_address_flash)
        else:
            return None

    def has_kernel_version(self):
        """
        Return true if this TBF header includes the kernel version TLV.
        """
        return self._get_tlv(self.HEADER_TYPE_KERNEL_VERSION) != None

    def get_kernel_version(self):
        """
        Return (kernel_major, kernel_minor) if there is kernel version present,
        or None.
        """
        tlv = self._get_tlv(self.HEADER_TYPE_KERNEL_VERSION)
        if tlv:
            return (tlv.kernel_major, tlv.kernel_minor)
        else:
            return None

    def delete_tlv(self, tlvid):
        """
        Delete a particular TLV by ID if it exists.
        """
        indices = []
        size = 0
        for i, tlv in enumerate(self.tlvs):
            if tlv.get_tlvid() == tlvid:
                # Reverse the list
                indices.insert(0, i)
                # Keep track of how much smaller we are making the header.
                size += tlv.get_size()
        # Pop starting with the last match
        for index in indices:
            logging.debug("Removing TLV at index {}".format(index))
            self.tlvs.pop(index)
            self.modified = True

        # Now update the base information since we have changed the length.
        self.fields["header_size"] -= size

        # Increase the protected size so that the actual application
        # binary hasn't moved.
        tlv_main = self._get_tlv(self.HEADER_TYPE_MAIN)
        tlv_main.protected_size += size
        #####
        ##### NOTE! Based on how things are implemented in the Tock
        ##### universe, it seems we also need to increase the
        ##### `init_fn_offset`, which is calculated from the end of
        ##### the TBF header everywhere, and NOT the beginning of
        ##### the actual application binary (like the documentation
        ##### indicates it should be).
        #####
        tlv_main.init_fn_offset += size

    def modify_tlv(self, tlvid, field, value):
        """
        Modify a TLV by setting a particular field in the TLV object to value.
        """
        # 0 is a special id for the root fields
        if tlvid == 0:
            self.fields[field] = value
        else:
            for tlv in self.tlvs:
                if tlv.get_tlvid() == tlvid:
                    try:
                        getattr(tlv, field)
                    except:
                        raise TockLoaderException(
                            'Field "{}" is not in TLV {}'.format(field, tlvid)
                        )
                    setattr(tlv, field, value)
                    self.modified = True

    def adjust_starting_address(self, address):
        """
        Alter this TBF header so the fixed address in flash will be correct
        if the entire TBF binary is loaded at address `address`.
        """
        # Check if we can even do anything. No fixed address means this is
        # meaningless.
        tlv_fixed_addr = self._get_tlv(self.HEADER_TYPE_FIXED_ADDRESSES)
        if tlv_fixed_addr:
            tlv_main = self._get_tlv(self.HEADER_TYPE_MAIN)
            # Now see if the header is already the right length.
            if (
                address + self.fields["header_size"] + tlv_main.protected_size
                != tlv_fixed_addr.fixed_address_flash
            ):
                # Make sure we need to make the header bigger
                if (
                    address + self.fields["header_size"] + tlv_main.protected_size
                    < tlv_fixed_addr.fixed_address_flash
                ):
                    # The header is too small, so we can fix it.
                    delta = tlv_fixed_addr.fixed_address_flash - (
                        address + self.fields["header_size"] + tlv_main.protected_size
                    )
                    # Increase the protected size to match this.
                    tlv_main.protected_size += delta

                    #####
                    ##### NOTE! Based on how things are implemented in the Tock
                    ##### universe, it seems we also need to increase the
                    ##### `init_fn_offset`, which is calculated from the end of
                    ##### the TBF header everywhere, and NOT the beginning of
                    ##### the actual application binary (like the documentation
                    ##### indicates it should be).
                    #####
                    tlv_main.init_fn_offset += delta

                else:
                    # The header actually needs to shrink, which we can't do.
                    # We should never hit this case.
                    raise TockLoaderException(
                        "Cannot shrink the header. This is a tockloader bug."
                    )

    # Return a buffer containing the header repacked as a binary buffer
    def get_binary(self):
        """
        Get the TBF header in a bytes array.
        """
        if self.version == 1:
            buf = struct.pack(
                "<IIIIIIIIIIIIIIIIIII",
                self.version,
                self.fields["total_size"],
                self.fields["entry_offset"],
                self.fields["rel_data_offset"],
                self.fields["rel_data_size"],
                self.fields["text_offset"],
                self.fields["text_size"],
                self.fields["got_offset"],
                self.fields["got_size"],
                self.fields["data_offset"],
                self.fields["data_size"],
                self.fields["bss_mem_offset"],
                self.fields["bss_mem_size"],
                self.fields["min_stack_len"],
                self.fields["min_app_heap_len"],
                self.fields["min_kernel_heap_len"],
                self.fields["package_name_offset"],
                self.fields["package_name_size"],
            )
            checksum = self._checksum(buf)
            buf += struct.pack("<I", checksum)

        elif self.version == 2:
            buf = struct.pack(
                "<HHIII",
                self.version,
                self.fields["header_size"],
                self.fields["total_size"],
                self.fields["flags"],
                0,
            )
            if self.app:
                for tlv in self.tlvs:
                    buf += tlv.pack()

            nbuf = bytearray(len(buf))
            nbuf[:] = buf
            buf = nbuf

            checksum = self._checksum(buf)
            struct.pack_into("<I", buf, 12, checksum)

            tlv_main = self._get_tlv(self.HEADER_TYPE_MAIN)
            if tlv_main and tlv_main.protected_size > 0:
                # Add padding to this header binary to account for the
                # protected region between the header and the application
                # binary.
                buf += b"\0" * tlv_main.protected_size

        return buf

    def _checksum(self, buffer):
        """
        Calculate the TBF header checksum.
        """
        # Add 0s to the end to make sure that we are multiple of 4.
        padding = len(buffer) % 4
        if padding != 0:
            padding = 4 - padding
            buffer += bytes([0] * padding)

        # Loop throw
        checksum = 0
        for i in range(0, len(buffer), 4):
            checksum ^= struct.unpack("<I", buffer[i : i + 4])[0]

        return checksum

    def _get_tlv(self, tlvid):
        """
        Return the TLV from the self.tlvs array if it exists.
        """
        for tlv in self.tlvs:
            if tlv.get_tlvid() == tlvid:
                return tlv
        return None

    def __str__(self):
        out = ""

        if not self.valid:
            out += "INVALID!\n"

        out += "{:<22}: {}\n".format("version", self.version)

        # Special case version 1. However, at this point (May 2020), I would be
        # shocked if this ever gets run on a version 1 TBFH.
        if self.version == 1:
            for k, v in sorted(self.fields.items()):
                if k == "checksum":
                    out += "{:<22}:            {:>#12x}\n".format(k, v)
                else:
                    out += "{:<22}: {:>10} {:>#12x}\n".format(k, v, v)

                if k == "flags":
                    values = ["No", "Yes"]
                    out += "  {:<20}: {}\n".format("enabled", values[(v >> 0) & 0x01])
                    out += "  {:<20}: {}\n".format("sticky", values[(v >> 1) & 0x01])
            return out

        # Base fields that always exist.
        out += "{:<22}: {:>10} {:>#12x}\n".format(
            "header_size", self.fields["header_size"], self.fields["header_size"]
        )
        out += "{:<22}: {:>10} {:>#12x}\n".format(
            "total_size", self.fields["total_size"], self.fields["total_size"]
        )
        out += "{:<22}:            {:>#12x}\n".format(
            "checksum", self.fields["checksum"]
        )
        out += "{:<22}: {:>10} {:>#12x}\n".format(
            "flags", self.fields["flags"], self.fields["flags"]
        )
        out += "  {:<20}: {}\n".format(
            "enabled", ["No", "Yes"][(self.fields["flags"] >> 0) & 0x01]
        )
        out += "  {:<20}: {}\n".format(
            "sticky", ["No", "Yes"][(self.fields["flags"] >> 1) & 0x01]
        )

        for tlv in self.tlvs:
            out += str(tlv)

        return out


class TBFHeaderPadding(TBFHeader):
    """
    TBF Header that is only padding between apps. Since apps are packed as
    linked-list, this allows apps to be pushed to later addresses while
    preserving the linked-list structure.
    """

    def __init__(self, size):
        """
        Create the TBF header. All we need to know is how long the entire
        padding should be.
        """
        self.valid = True
        self.app = False
        self.modified = False
        self.fields = {}
        self.tlvs = []

        self.version = 2
        # self.fields['header_size'] = 14 # this causes interesting bugs...
        self.fields["header_size"] = 16
        self.fields["total_size"] = size
        self.fields["flags"] = 0
        self.fields["checksum"] = self._checksum(self.get_binary())
