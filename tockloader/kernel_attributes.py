"""
Parse kernel attributes at the end of the kernel flash region.
"""

import struct


class KATLV:
    TYPE_APP_MEMORY = 0x0101
    TYPE_KERNEL_BINARY = 0x0102

    def get_tlvid(self):
        return self.TLVID

    def get_size(self):
        return len(self.pack())


class KATLVAppMemory(KATLV):
    TLVID = KATLV.TYPE_APP_MEMORY
    SIZE = 8

    def __init__(self, buffer):
        self.valid = False

        if len(buffer) == 8:
            base = struct.unpack("<II", buffer)
            self.app_memory_start = base[0]
            self.app_memory_len = base[1]
            self.valid = True

    def pack(self):
        return struct.pack(
            "<IIHH",
            self.app_memory_start,
            self.app_memory_len,
            self.TLVID,
            8,
        )

    def __str__(self):
        out = "KATLV: App Memory ({:#x})\n".format(self.TLVID)
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "app_memory_start", self.app_memory_start, self.app_memory_start
        )
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "app_memory_len", self.app_memory_len, self.app_memory_len
        )
        return out

    def object(self):
        return {
            "type": "app_memory",
            "id": self.TLVID,
            "app_memory_start": self.app_memory_start,
            "app_memory_len": self.app_memory_len,
        }


class KATLVKernelBinary(KATLV):
    TLVID = KATLV.TYPE_KERNEL_BINARY
    SIZE = 8

    def __init__(self, buffer):
        self.valid = False

        if len(buffer) == 8:
            base = struct.unpack("<II", buffer)
            self.kernel_binary_start = base[0]
            self.kernel_binary_len = base[1]
            self.valid = True

    def pack(self):
        return struct.pack(
            "<IIHH",
            self.kernel_binary_start,
            self.kernel_binary_len,
            self.TLVID,
            8,
        )

    def __str__(self):
        out = "KATLV: Kernel Binary ({:#x})\n".format(self.TLVID)
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "kernel_binary_start", self.kernel_binary_start, self.kernel_binary_start
        )
        out += "  {:<20}: {:>10} {:>#12x}\n".format(
            "kernel_binary_len", self.kernel_binary_len, self.kernel_binary_len
        )
        return out

    def object(self):
        return {
            "type": "kernel_binary",
            "id": self.TLVID,
            "kernel_binary_start": self.kernel_binary_start,
            "kernel_binary_len": self.kernel_binary_len,
        }


class KernelAttributes:
    """
    Represent attributes stored at the end of the kernel image that contain metadata
    about the installed kernel.
    """

    KATLV_TYPES = [KATLVAppMemory, KATLVKernelBinary]

    def __init__(self, buffer, address):
        self.tlvs = []
        self.address = address

        # Check for sentinel at the end. It should be "TOCK".
        sentinel_bytes = buffer[-4:]
        try:
            sentinel_string = sentinel_bytes.decode("utf-8")
        except:
            # Kernel attributes not present.
            return
        if sentinel_string != "TOCK":
            return
        buffer = buffer[:-4]

        # Parse the version number.
        self.version = struct.unpack("<B", buffer[-1:])[0]
        # Skip the version and three reserved bytes.
        buffer = buffer[:-4]

        if self.version == 1:
            while len(buffer) > 4:
                # Now try to parse TLVs, but going backwards in flash.
                t, l = struct.unpack("<HH", buffer[-4:])
                buffer = buffer[:-4]

                for katlv_type in self.KATLV_TYPES:
                    if t == katlv_type.TLVID:
                        katlv_len = katlv_type.SIZE
                        if len(buffer) >= katlv_len and l == katlv_len:
                            self.tlvs.append(katlv_type(buffer[-1 * katlv_len :]))
                            buffer = buffer[: -1 * katlv_len]
                        break
                else:
                    break

    def get_app_memory_region(self):
        """
        Get a tuple of the RAM region for apps. If unknown, return None.

        (app_memory_start_address, app_memory_length_bytes)
        """
        tlv = self._get_tlv(KATLV.TYPE_APP_MEMORY)
        if tlv:
            return (tlv.app_memory_start, tlv.app_memory_len)
        else:
            return None

            return ""

    def _get_tlv(self, tlvid):
        """
        Return the TLV from the self.tlvs array if it exists.
        """
        for tlv in self.tlvs:
            if tlv.get_tlvid() == tlvid:
                return tlv
        return None

    def __str__(self):
        return self.info()

    def info(self):
        out = ""

        # Check if we found kernel attributes at all. If not, return early.
        if not hasattr(self, "version"):
            return out

        address = self.address
        index = 0

        ka = "Kernel Attributes"
        absolute_address = " [{:<#9x}]".format(address + index) if address else ""
        out += "{:<48}[{:<#5x}]{}\n".format(ka, index, absolute_address)
        index -= 4

        sentinel = "  {:<20}: {}".format("sentinel", "TOCK")
        absolute_address = " [{:<#9x}]".format(address + index) if address else ""
        out += "{:<48}[{:<#5x}]{}\n".format(sentinel, index, absolute_address)
        index -= 4

        version = "  {:<20}: {}".format("version", self.version)
        absolute_address = " [{:<#9x}]".format(address + index) if address else ""
        out += "{:<48}[{:<#5x}]{}\n".format(version, index, absolute_address)

        for tlv in self.tlvs:
            # Decrement the byte index FIRST so we get the beginning address.
            index -= tlv.get_size()

            # Format the offset so we know the size.
            offset = "[{:<#5x}]".format(index)
            absolute_address = " [{:<#9x}]".format(address + index) if address else ""
            # Create the base TLV format.
            tlv_str = str(tlv)
            # Insert the address at the end of the first line of the TLV str.
            lines = tlv_str.split("\n")
            lines[0] = "{:<48}{}{}".format(lines[0], offset, absolute_address)
            # Recreate string.
            out += "\n".join(lines)

        return out
