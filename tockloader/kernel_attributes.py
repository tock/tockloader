import struct


class KATLV:
    TYPE_APP_MEMORY = 0x0101

    def get_tlvid(self):
        return self.TLVID

    def get_size(self):
        return len(self.pack())


class KATLVAppMemory(KATLV):
    TLVID = KATLV.TYPE_APP_MEMORY

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
        out = "KATLV: App Memory ({})\n".format(self.TLVID)
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


class KernelAttributes:
    """
    Represent attributes stored at the end of the kernel image that contain metadata
    about the installed kernel.
    """

    def __init__(self, buffer):
        self.tlvs = []

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

        while len(buffer) > 4:
            # Now try to parse TLVs, but going backwards in flash.
            t, l = struct.unpack("<HH", buffer[-4:])
            buffer = buffer[:-4]

            if t == KATLV.TYPE_APP_MEMORY:
                if len(buffer) >= 8 and l == 8:
                    self.tlvs.append(KATLVAppMemory(buffer[-8:]))
                    buffer = buffer[:-8]
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
