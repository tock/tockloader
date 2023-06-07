import binascii
import struct

import zlib

import crcmod
import siphash24

from .exceptions import TockLoaderException


class TicKV:
    def __init__(self, storage_binary, region_size):
        """
        Create a new TicKV object with a given binary buffer representing
        the storage.
        """

        # ///     poly: 0x04c11db7
        # ///     init: 0x00000000
        # ///     refin: false
        # ///     refout: false
        # ///     xorout: 0xffffffff

        self.crc_fn = crcmod.mkCrcFun(
            poly=0x104C11DB7, rev=False, initCrc=0xFFFFFFFF, xorOut=0xFFFFFFFF
        )
        self.storage_binary = storage_binary
        self.region_size = region_size

        # The storage binary must be a multiple of the region size for the storage to be valid.
        if len(self.storage_binary) % self.region_size != 0:
            raise TockLoaderException(
                "ERROR: TicKV storage not a multiple of region size."
            )

    def _get_number_regions(self):
        return len(self.storage_binary) // self.region_size

    def _hash_key(self, key):
        key_buffer = key.encode("utf-8")
        key_buffer += b"\0" * (64 - len(key_buffer))
        h = siphash24.siphash24()
        h.update(data=key_buffer)
        return h.digest()

    def trial(self):
        key = "tickv-super-key"
        return self._hash_key(key)

    def parse_region(self, region_index):
        region_binary = self.storage_binary[
            region_index * self.region_size : (region_index + 1) * self.region_size
        ]

        objects = []

        print("REGION {}".format(region_index))

        offset = 0
        while True:

            object_header_bytes = region_binary[offset : offset + 11]
            object_header_fields = struct.unpack(
                ">BH8s", region_binary[offset : offset + 11]
            )
            object_header = {
                "version": object_header_fields[0],
                "flags": object_header_fields[1] >> 12,
                "len": object_header_fields[1] & 0xFFF,
                "hashed_key": object_header_fields[2],
            }
            offset += 11

            if object_header["version"] == 1:
                value_length = object_header["len"] - 11 - 4
                object_value_bytes = region_binary[offset : offset + value_length]
                offset += value_length
                object_checksum = region_binary[offset : offset + 4]
                offset += 4

                if len(object_value_bytes) > 9:
                    kv_tock_header_fields = struct.unpack(
                        "<BII", object_value_bytes[0:9]
                    )
                    object_value = {
                        "version": kv_tock_header_fields[0],
                        "length": kv_tock_header_fields[1],
                        "write_id": kv_tock_header_fields[2],
                    }
                    object_value["value"] = object_value_bytes[
                        9 : 9 + object_value["length"]
                    ]
                else:
                    object_value = {
                        "value": object_value_bytes,
                    }

                objects.append(
                    {
                        "header": object_header,
                        "value": object_value,
                        "checksum": object_checksum,
                        "calculated_checksum": self.crc_fn(
                            object_header_bytes + object_value_bytes
                        ),
                    }
                )
            else:
                break

        for o in objects:
            print(o["header"])
            print(binascii.hexlify(o["header"]["hashed_key"]).decode("utf-8"))
            print(o["value"])
            print(binascii.hexlify(o["value"]["value"]).decode("utf-8"))
            print(binascii.hexlify(o["checksum"]).decode("utf-8"))
            print(
                binascii.hexlify(o["calculated_checksum"].to_bytes(4, "little")).decode(
                    "utf-8"
                )
            )

    def __str__(self):
        out = "\n"
        k = binascii.hexlify(self.trial()).decode("utf-8")
        out += "{}\n".format(k)

        k = binascii.hexlify(self._hash_key("mythirdkey")).decode("utf-8")
        out += "{}\n".format(k)

        for i in range(0, self._get_number_regions()):
            self.parse_region(i)
        return out
