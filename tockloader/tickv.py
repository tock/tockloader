"""
Manage and use a TicKV formatted database.
"""

import binascii
import logging
import struct

import zlib

import crcmod
import siphash24

from .exceptions import TockLoaderException


class TicKVObjectHeader:
    def __init__(self, version, flags, hashed_key):
        self.version = version
        self.flags = flags
        self.hashed_key = hashed_key

    def length(self):
        return 11

    def invalidate(self):
        self.flags &= 0x7

    def is_valid(self):
        return (self.flags >> 3) & 0x1 == 0x1

    def get_binary(self, length):
        flags_length = (self.flags << 12) | length
        return struct.pack(">BHQ", self.version, flags_length, self.hashed_key)


class TicKVObject:
    def __init__(self, header, value_buffer, checksum):
        self.header = header
        self.value_buffer = value_buffer
        self.checksum = checksum

    def length(self):
        """
        Return the total length of this object in the database in bytes.
        """
        # Size is header length + value length + checksum length (4)
        return self.header.length() + len(self.value_buffer) + 4

    def invalidate(self):
        self.header.invalidate()

    def get_header(self):
        return self.header

    def get_hashed_key(self):
        return self.header.hashed_key

    def get_checksum(self):
        return self.checksum

    def get_value_bytes(self):
        return self.value_buffer

    def get_binary(self):
        return bytearray(
            self.header.get_binary(self.length())
            + self.value_buffer
            + struct.pack("<I", self.checksum)
        )

    def __str__(self):
        out = ""
        out += "TicKV Object version={} flags={} length={} checksum={:#x}\n".format(
            self.header.version, self.header.flags, self.length(), self.checksum
        )
        v = binascii.hexlify(self.value_buffer).decode("utf-8")
        out += "  Value: {}\n".format(v)

        return out


class TockTicKVObject:
    def __init__(self, header, checksum, version, write_id, value_buffer):
        self.header = header
        self.value_buffer = value_buffer
        self.checksum = checksum
        self.version = version
        self.write_id = write_id

    def __str__(self):
        out = ""
        out += "TicKV Object version={} flags={} valid={} checksum={:#x}\n".format(
            self.header.version,
            self.header.flags,
            self.header.is_valid(),
            self.checksum,
        )
        out += "  TockTicKV Object version={} write_id={} length={}\n".format(
            self.version, self.write_id, len(self.value_buffer)
        )
        v = binascii.hexlify(self.value_buffer).decode("utf-8")
        out += "    Value: {}\n".format(v)

        return out


class TicKV:
    def __init__(self, storage_binary, region_size):
        """
        Create a new TicKV object with a given binary buffer representing
        the storage.
        """

        # These arguments don't exactly match (init should be 0), but the actual
        # CRC values seem to work.
        self.crc_fn = crcmod.mkCrcFun(
            poly=0x104C11DB7, rev=False, initCrc=0xFFFFFFFF, xorOut=0xFFFFFFFF
        )
        self.storage_binary = bytearray(storage_binary)
        self.region_size = region_size

        # The storage binary must be a multiple of the region size for the storage to be valid.
        if len(self.storage_binary) % self.region_size != 0:
            raise TockLoaderException(
                "ERROR: TicKV storage not a multiple of region size."
            )

    def _get_number_regions(self):
        return len(self.storage_binary) // self.region_size

    def _get_region_binary(self, region_index):
        return self.storage_binary[
            region_index * self.region_size : (region_index + 1) * self.region_size
        ]

    def _update_region_binary(self, region_index, region_binary):
        self.storage_binary[
            region_index * self.region_size : (region_index + 1) * self.region_size
        ] = region_binary

    def _parse_object(self, buffer):
        object_header_bytes = buffer[0:11]
        object_header_fields = struct.unpack(">BHQ", object_header_bytes)

        version = object_header_fields[0]
        flags = object_header_fields[1] >> 12
        length = object_header_fields[1] & 0xFFF
        hashed_key = object_header_fields[2]

        if version != 1:
            return None

        header = TicKVObjectHeader(version, flags, hashed_key)

        value_length = length - 11 - 4
        object_value_bytes = buffer[11 : 11 + value_length]
        object_checksum_bytes = buffer[length - 4 : length]
        object_checksum = struct.unpack("<I", object_checksum_bytes)[0]

        return TicKVObject(header, object_value_bytes, object_checksum)

    def get(self, hashed_key):
        region_index = (hashed_key & 0xFFFF) % self._get_number_regions()
        region_binary = self._get_region_binary(region_index)

        offset = 0
        while True:
            kv_object = self._parse_object(region_binary[offset:])

            if kv_object == None:
                break

            if kv_object.get_hashed_key() != hashed_key:
                offset += kv_object.length()
                continue

            return kv_object

    def get_all(self, region_index):
        region_binary = self._get_region_binary(region_index)

        kv_objects = []

        offset = 0
        while True:
            kv_object = self._parse_object(region_binary[offset:])
            if kv_object != None:
                kv_objects.append(kv_object)
                offset += kv_object.length()
            else:
                break

        return kv_objects

    def invalidate(self, hashed_key):
        region_index = (hashed_key & 0xFFFF) % self._get_number_regions()
        region_binary = self._get_region_binary(region_index)

        offset = 0
        while True:
            kv_object = self._parse_object(region_binary[offset:])

            if kv_object == None:
                break

            if kv_object.get_hashed_key() == hashed_key:
                length = kv_object.length()
                kv_object.invalidate()
                updated_object_binary = kv_object.get_binary()
                for i in range(0, length):
                    region_binary[offset + i] = updated_object_binary[i]
                break

        self._update_region_binary(region_index, region_binary)

    def __str__(self):
        out = "\n"
        k = binascii.hexlify(self.trial()).decode("utf-8")
        out += "{}\n".format(k)

        k = binascii.hexlify(self._hash_key("mythirdkey")).decode("utf-8")
        out += "{}\n".format(k)

        for i in range(0, self._get_number_regions()):
            self.parse_region(i)
        return out


class TockTicKV(TicKV):
    """
    Extension of a TicKV database that adds an additional header with a
    `write_id` to enable enforcing access control.
    """

    def _hash_key(self, key):
        """
        Compute the SipHash24 for the given key. We always pad the key to
        be 64 bytes by adding zeros.
        """

        key_buffer = key.encode("utf-8")
        key_buffer += b"\0" * (64 - len(key_buffer))
        h = siphash24.siphash24()
        h.update(data=key_buffer)
        return h.digest()

    def _hash_key_int(self, key):
        """
        Compute the SipHash24 for the given key. Return as u64.
        """

        hashed_key_buf = self._hash_key(key)
        return struct.unpack(">Q", hashed_key_buf)[0]

    def _parse_tock_object(self, kv_object):
        if len(kv_object.get_value_bytes()) >= 9:
            kv_tock_header_fields = struct.unpack(
                "<BII", kv_object.get_value_bytes()[0:9]
            )
            version = kv_tock_header_fields[0]
            length = kv_tock_header_fields[1]
            write_id = kv_tock_header_fields[2]

            value_bytes = kv_object.get_value_bytes()[9 : 9 + length]

            tock_kv_object = TockTicKVObject(
                kv_object.get_header(),
                kv_object.get_checksum(),
                version,
                write_id,
                value_bytes,
            )

            return tock_kv_object
        else:
            return None

    def get(self, key):
        logging.debug('Finding key "{}" in Tock-style TicKV database.'.format(key))

        hashed_key = self._hash_key_int(key)

        kv_object = super().get(hashed_key)
        if kv_object == None:
            return None

        return self._parse_tock_object(kv_object)

    def get_all(self, region_index):
        logging.debug(
            "Finding all objects in region {} of a Tock-style TicKV database.".format(
                region_index
            )
        )

        kv_objects = super().get_all(region_index)

        tock_kv_objects = []
        for kv_object in kv_objects:
            tock_kv_object = self._parse_tock_object(kv_object)
            if tock_kv_object != None:
                tock_kv_objects.append(tock_kv_object)

        return tock_kv_objects

    def invalidate(self, key):
        hashed_key = self._hash_key_int(key)
        super().invalidate(hashed_key)

    def dump(self):
        logging.info("Dumping entire contents of Tock-style TicKV database.")

        out = ""
        for region_index in range(0, self._get_number_regions()):
            tock_kv_objects = self.get_all(region_index)

            out += "REGION {}\n".format(region_index)
            for tock_kv_object in tock_kv_objects:
                out += str(tock_kv_object)

            out += "\n"

        return out
