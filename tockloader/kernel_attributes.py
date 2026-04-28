"""
Parse kernel attributes at the end of the kernel flash region.
"""

import logging
import struct


class KATLV:
    TYPE_APP_MEMORY = 0x0101
    TYPE_KERNEL_BINARY = 0x0102
    TYPE_KERNEL_VERSION = 0x0103
    TYPE_PUBLIC_KEY = 0x0104

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


class KATLVKernelVersion(KATLV):
    TLVID = KATLV.TYPE_KERNEL_VERSION
    SIZE = 8

    def __init__(self, buffer):
        self.valid = False

        if len(buffer) == 8:
            base = struct.unpack("<HHHH", buffer)
            self.kernel_version_major = base[0]
            self.kernel_version_minor = base[1]
            self.kernel_version_patch = base[2]
            self.kernel_version_prerelease = base[3]
            self.valid = True

    def pack(self):
        return struct.pack(
            "<HHHHHH",
            self.kernel_version_major,
            self.kernel_version_minor,
            self.kernel_version_patch,
            self.kernel_version_prerelease,
            self.TLVID,
            8,
        )

    def __str__(self):
        out = "KATLV: Kernel Version ({:#x})\n".format(self.TLVID)

        labels = ["", "-dev", "-alpha", "-beta"]
        if self.kernel_version_prerelease > 3:
            end = f"-pre-release{self.kernel_version_prerelease}"
        else:
            end = labels[self.kernel_version_prerelease]

        out += "  {:<20}: {}.{}.{}{}\n".format(
            "kernel_version",
            self.kernel_version_major,
            self.kernel_version_minor,
            self.kernel_version_patch,
            end,
        )

        return out

    def object(self):
        return {
            "type": "kernel_version",
            "id": self.TLVID,
            "kernel_version_major": self.kernel_version_major,
            "kernel_version_minor": self.kernel_version_minor,
            "kernel_version_patch": self.kernel_version_patch,
            "kernel_version_prerelease": self.kernel_version_prerelease,
        }


class KATLVPublicKey(KATLV):
    TLVID = KATLV.TYPE_PUBLIC_KEY
    SIZE = 8
    NUMBER_PARAMETERS = 3
    PARAMETER_HELP = "<algorithm name> <key use> <key file>"

    PUBLIC_KEY_TYPE_ECDSAP256 = 0x06

    PUBLIC_KEY_TYPES = {0x6: CREDENTIALS_TYPE_ECDSAP256}
    PUBLIC_KEY_NAMES = {"ecdsap256": PUBLIC_KEY_TYPE_ECDSAP256}

    PUBLIC_KEY_USE_APPS = 0x1
    PUBLIC_KEY_USE_SERVICES = 0x2

    PUBLIC_KEY_USES = {0x1: PUBLIC_KEY_USE_APPS, 0x2: PUBLIC_KEY_USE_SERVICES}
    PUBLIC_KEY_USE_NAMES = {
        "app": PUBLIC_KEY_USE_APPS,
        "service": PUBLIC_KEY_USE_SERVICES,
    }

    def __init__(self, buffer, parameters=[]):
        self.valid = False

        if len(buffer) > 4:
            base = struct.unpack("<HH", buffer[-4:])
            self.public_key_algorithm = base[0]
            self.public_key_use = base[1]
            buffer = buffer[:-4]

            if self.public_key_algorithm == 0x6:
                if len(buffer) == 64:
                    self.public_key = buffer
                    self.valid = True
        else:
            public_key_algorithm_name = parameters[0]
            public_key_use = parameters[1]
            public_key_path = parameters[2]

            # See if the name matches a public key type we know about.
            if public_key_algorithm_name in self.PUBLIC_KEY_NAMES:
                self.public_key_algorithm = self.PUBLIC_KEY_NAMES[
                    public_key_algorithm_name
                ]

                self.public_key_algorithm = parameters[0]
                self.public_key_use = parameters[1]
                self.public_key = parameters[2]
                self.valid = True
            else:
                raise TockLoaderException("Unknown public key name")

    def pack(self):
        return struct.pack(
            "<sHHHH",
            self.public_key,
            self.public_key_algorithm,
            self.public_key_use,
            self.TLVID,
            4 + len(self.public_key),
        )

    def __str__(self):
        out = "KATLV: Public Key ({:#x})\n".format(self.TLVID)

        out += "  {:<20}: {} {}\n".format(
            "public_key",
            self.public_key_algorithm,
            self.public_key_use,
        )

        return out

    # def object(self):
    #     return {
    #         "type": "kernel_version",
    #         "id": self.TLVID,
    #         "kernel_version_major": self.kernel_version_major,
    #         "kernel_version_minor": self.kernel_version_minor,
    #         "kernel_version_patch": self.kernel_version_patch,
    #         "kernel_version_prerelease": self.kernel_version_prerelease,
    #     }


TLV_MAPPINGS = {
    "public_key": KATLVPublicKey,
}


def get_tlv_names():
    """
    Return a list of all TLV names.
    """
    return list(TLV_MAPPINGS.keys())


def get_addable_tlvs():
    """
    Return a list of (tlv_name, #parameters) tuples for all TLV types that
    tockloader can add.
    """
    addable_tlvs = []
    for k, v in TLV_MAPPINGS.items():
        try:
            addable_tlvs.append((k, v.NUMBER_PARAMETERS, v.PARAMETER_HELP))
        except:
            pass
    return addable_tlvs


def get_tlvid_from_name(tlvname):
    return TLV_MAPPINGS[tlvname].TLVID


class KernelAttributes:
    """
    Represent attributes stored at the end of the kernel image that contain metadata
    about the installed kernel.
    """

    KATLV_TYPES = [
        KATLVAppMemory,
        KATLVKernelBinary,
        KATLVKernelVersion,
        KATLVPublicKey,
    ]

    def __init__(self, buffer, address):
        self.tlvs = []
        self.address = address
        self.modified = False

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
        return None

    def get_kernel_binary_size(self):
        """
        Get the length of the actual kernel binary in bytes.

        Returns `None` if the kernel binary header is not present.
        """
        tlv = self._get_tlv(KATLV.TYPE_KERNEL_BINARY)
        if tlv:
            return tlv.kernel_binary_len
        return None

    def add_tlv(self, tlvname, parameters):
        logging.info(
            "Adding TLV {} with {} parameters".format(tlvname, len(parameters))
        )
        tlv_obj = TLV_MAPPINGS[tlvname]

        # Need to add an entirely new TLV.
        new_tlv = tlv_obj(b"", parameters)
        size = len(new_tlv.pack())
        self.tlvs.append(new_tlv)
        self.modified = True

    def add_public_key(
        self,
        public_key,
    ):
        key = bytearray(
            [
                0xE0,
                0x13,
                0x3A,
                0x90,
                0xA7,
                0x4A,
                0x35,
                0x61,
                0x51,
                0x8E,
                0xE1,
                0x44,
                0x09,
                0xF1,
                0x69,
                0xC1,
                0xCF,
                0x6A,
                0xDB,
                0x7F,
                0x7E,
                0x52,
                0xF8,
                0xB7,
                0x41,
                0x79,
                0xE2,
                0x4D,
                0x57,
                0x41,
                0x23,
                0x52,
                0x2E,
                0xB6,
                0x12,
                0x03,
                0xB3,
                0x85,
                0x10,
                0xE5,
                0xF3,
                0x25,
                0x07,
                0x62,
                0x8F,
                0x54,
                0x95,
                0x82,
                0x57,
                0x45,
                0x50,
                0xBD,
                0xA3,
                0xE2,
                0x17,
                0xE8,
                0x34,
                0x30,
                0x89,
                0x26,
                0x4C,
                0x23,
                0x62,
                0xB1,
            ]
        )

        attr = KATLVPublicKey([], [0x6, 0, key])

        self.tlvs.append(attr)

    def _get_tlv(self, tlvid):
        """
        Return the TLV from the self.tlvs array if it exists.
        """
        for tlv in self.tlvs:
            if tlv.get_tlvid() == tlvid:
                return tlv
        return None

    def get_binary(self):
        """
        Get the kernel attributes in a bytes array.
        """
        buf = bytearray()
        for tlv in self.tlvs:
            buf += tlv.pack()

        return buf

    def get_size(self):
        """
        Get the size of the kernel attributes in bytes.
        """
        kernel_attrs_size = 0
        for tlv in self.tlvs:
            kernel_attrs_size += tlv.get_size()
        return footkernel_attrs_sizeer_size

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

    def object(self):
        out = {"version": self.version, "attributes": []}
        for tlv in self.tlvs:
            out["attributes"].append(tlv.object())
        return out
