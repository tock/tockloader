"""
Manage and use a TicKV formatted database.

TicKV: https://github.com/tock/tock/tree/master/libraries/tickv
"""

import binascii
import logging
import struct
import textwrap

import crcmod
import siphash

from .exceptions import TockLoaderException

# This hashed key is used as a sentinel that the DB is initialized. We don't
# know what string created it.
MAGIC_INIT_HASHED_KEY = 0x7BC9F7FF4F76F244


class TicKVObjectHeader:
    """
    The base header for an item in a TicKV database.
    """

    def __init__(self, hashed_key, version=1, flags=0x8):
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
        total_length = length + self.length() + 4

        flags_length = (self.flags << 12) | total_length
        return struct.pack(">BHQ", self.version, flags_length, self.hashed_key)


class TicKVObjectHeaderFlash(TicKVObjectHeader):
    """
    An item header read from an existing database. This handles parsing the
    structure from a byte array.
    """

    def __init__(self, binary):
        object_header_fields = struct.unpack(">BHQ", binary[0:11])

        version = object_header_fields[0]
        flags = object_header_fields[1] >> 12
        length = object_header_fields[1] & 0xFFF
        hashed_key = object_header_fields[2]

        if version != 1:
            raise TockLoaderException("Invalid object")

        super().__init__(hashed_key, version, flags)

        self.total_length = length

    def get_value_length(self):
        return self.total_length - self.length() - 4


class TicKVObjectBase:
    """
    Shared class representing an item in a TicKV database.
    """

    def __init__(self, header, checksum=None):
        self.header = header
        self.checksum = checksum

        # These arguments don't exactly match (init should be 0), but the actual
        # CRC values seem to work.
        self.crc_fn = crcmod.mkCrcFun(
            poly=0x104C11DB7, rev=False, initCrc=0xFFFFFFFF, xorOut=0xFFFFFFFF
        )

    def length(self):
        """
        Return the total length of this object in the database in bytes.
        """
        # Size is header length + value length + checksum length (4)
        return self.header.length() + len(self.get_value_bytes()) + 4

    def is_valid(self):
        return self.header.is_valid()

    def invalidate(self):
        self.header.invalidate()

    def get_hashed_key(self):
        return self.header.hashed_key

    def get_checksum(self):
        if self.checksum != None:
            return self.checksum
        else:
            object_bytes = self._get_object_bytes()
            return self._calculate_checksum(object_bytes)

    def get_binary(self):
        object_bytes = self._get_object_bytes()

        checksum = self._calculate_checksum(object_bytes)
        checksum_bytes = struct.pack("<I", checksum)

        return object_bytes + checksum_bytes

    def _calculate_checksum(self, object_bytes):
        return self.crc_fn(object_bytes)

    def _get_object_bytes(self):
        main_bytes = self.get_value_bytes()
        header_bytes = self.header.get_binary(len(main_bytes))
        object_bytes = header_bytes + main_bytes
        return object_bytes

    def __str__(self):
        out = ""
        out += "TicKV Object hash={:#x} version={} flags={} length={} valid={} checksum={:#x}\n".format(
            self.header.hashed_key,
            self.header.version,
            self.header.flags,
            self.length(),
            self.header.is_valid(),
            self.get_checksum(),
        )
        v = binascii.hexlify(self.get_value_bytes()).decode("utf-8")
        out += "  Value: {}\n".format(v)

        return out

    def object(self):
        out = {
            "version": self.header.version,
            "hashed_key": self.header.hashed_key,
            "flags": self.flags,
            "valid": self.header.is_valid(),
            "checksum": self.get_checksum(),
            "value": binascii.hexlify(self.get_value_bytes()).decode("utf-8"),
        }
        return out


class TicKVObjectFlash(TicKVObjectBase):
    """
    A TicKV object that is read off of the flash.
    """

    def __init__(self, binary):
        header = TicKVObjectHeaderFlash(binary)
        value_length = header.get_value_length()
        checksum_bytes = binary[
            header.length() + value_length : header.length() + value_length + 4
        ]
        checksum = struct.unpack("<I", checksum_bytes)[0]

        super().__init__(header, checksum)
        self.value_bytes = binary[header.length() : header.length() + value_length]

    def get_value_bytes(self):
        return self.value_bytes


class TicKVObject(TicKVObjectBase):
    """
    A TicKV object that is created in tockloader.
    """

    def __init__(self, header, value_bytes):
        if len(value_bytes) > 4096:
            raise TockLoaderException(
                "Cannot create TicKV object (length {} > 4096)".format(len(value_bytes))
            )

        super().__init__(header)
        self.value_bytes = value_bytes

    def get_value_bytes(self):
        return self.value_bytes


class TockStorageObject:
    """
    This is the item stored in a TicKV value that Tock processes/kernel can
    access.
    """

    def __init__(self, value_bytes, write_id=0, version=0):
        if len(value_bytes) + 9 > 4096:
            raise TockLoaderException(
                "Cannot create TockStorageObject object (length {} > 4087)".format(
                    len(value_bytes)
                )
            )

        self.value_bytes = value_bytes
        self.version = version
        self.write_id = write_id

    def length(self):
        return 9 + len(self.value_bytes)

    def get_binary(self):
        return (
            struct.pack("<BII", self.version, len(self.value_bytes), self.write_id)
            + self.value_bytes
        )

    def __str__(self):
        out = "TockTicKV Object version={} write_id={} length={}\n".format(
            self.version,
            self.write_id,
            len(self.value_bytes),
        )
        v = binascii.hexlify(self.value_bytes).decode("utf-8")
        out += "  Value: {}\n".format(v)
        return out


class TockStorageObjectFlash(TockStorageObject):
    """
    Tock-formatted K-V object read from a flash binary.

    This is useful when reading a Tock K-V from a board.
    """

    def __init__(self, binary):
        kv_tock_header_fields = struct.unpack("<BII", binary[0:9])
        version = kv_tock_header_fields[0]
        length = kv_tock_header_fields[1]
        write_id = kv_tock_header_fields[2]

        value_bytes = binary[9 : 9 + length]

        super().__init__(value_bytes, write_id, version)


class TicKVObjectTock(TicKVObjectBase):
    """
    Tock-formatted object stored in TicKV.
    """

    def __init__(self, header, storage_object, padding=0, checksum=None):
        super().__init__(header, checksum)

        self.storage_object = storage_object
        self.padding = padding

    def get_value_bytes(self):
        object_bytes = self.storage_object.get_binary()
        padding_bytes = b"\0" * self.padding
        return object_bytes + padding_bytes

    def __str__(self):
        out = super().__str__()
        out += textwrap.indent(str(self.storage_object), "  ")

        return out

    def object(self):
        out = {
            "version": self.header.version,
            "hashed_key": self.header.hashed_key,
            "flags": self.flags,
            "valid": self.header.is_valid(),
            "checksum": self.get_checksum(),
            "tock_object": {
                "version": self.storage_object.version,
                "write_id": self.storage_object.write_id,
                "value": binascii.hexlify(self.storage_object.value_bytes).decode(
                    "utf-8"
                ),
            },
        }
        return out


class TicKVObjectTockFlash(TicKVObjectTock):
    """
    Tock-formatted object stored in TicKV and read from flash.
    """

    def __init__(self, tickv_object):
        value_bytes = tickv_object.get_value_bytes()
        storage_object = TockStorageObjectFlash(value_bytes)
        padding = len(value_bytes) - storage_object.length()

        super().__init__(
            tickv_object.header, storage_object, padding, tickv_object.checksum
        )


class TicKV:
    """
    Interface to a generic TicKV database.
    """

    def __init__(self, storage_binary, region_size):
        """
        Create a new TicKV object with a given binary buffer representing
        the storage.
        """
        self.storage_binary = bytearray(storage_binary)
        self.region_size = region_size

        # The storage binary must be a multiple of the region size for the storage to be valid.
        if len(self.storage_binary) % self.region_size != 0:
            raise TockLoaderException(
                "ERROR: TicKV storage not a multiple of region size."
            )

    def get(self, hashed_key):
        """
        Retrieve a key-value object from a TicKV database.
        """
        # Iterate all pages starting with the indented page given the key.
        for region_index in self._region_range(self._get_starting_region(hashed_key)):
            region_binary = self._get_region_binary(region_index)

            offset = 0
            while True:
                try:
                    ex_obj = TicKVObjectFlash(region_binary[offset:])
                except:
                    break

                if ex_obj.is_valid() and ex_obj.get_hashed_key() == hashed_key:
                    return ex_obj

                offset += ex_obj.length()

    def get_all(self, region_index):
        """
        Retrieve all key-value objects from a TicKV database.
        """
        return self._get_all(region_index, False)

    def invalidate(self, hashed_key):
        """
        Mark a key-value object as deleted in a TicKV database.
        """
        self._invalidate_hashed_key(hashed_key)

    def append(self, hashed_key, value):
        """
        Add a key-value pair to a TicKV database.
        """
        header = TicKVObjectHeader(hashed_key)
        kv_object = TicKVObject(header, value)
        self._append_object(kv_object)

    def reset(self):
        """
        Reset the database back to an initialized state.
        """
        logging.info("Resetting TicKV database")
        self._reset()

    def _reset(self):
        db_len = len(self.storage_binary)
        self.storage_binary = bytearray(b"\xFF" * db_len)

        # Add the known initialize key, value. I don't know what this key
        # is from, but it is the standard.
        header = TicKVObjectHeader(MAGIC_INIT_HASHED_KEY)
        kv_object = TicKVObject(header, b"")
        self._append_object(kv_object)

    def cleanup(self):
        """
        Remove all invalid keys and re-write existing valid objects.
        """
        logging.info("Cleaning TicKV database")

        # First collect all existing valid objects.
        all_objects = []
        for region_index in self._region_range(0):
            region_objects = self._get_all(region_index, True)

            # Do not add the special init object, that will be written by reset.
            for region_object in region_objects:
                if region_object.get_hashed_key() != MAGIC_INIT_HASHED_KEY:
                    all_objects.append(region_object)

        logging.debug(
            "Found {} valid objects to re-store in database".format(len(all_objects))
        )

        # Then reset the db.
        self._reset()

        # Now re-write all valid objects.
        for obj in all_objects:
            self._append_object(obj)

    def get_binary(self):
        """
        Return the TicKV database as a binary object that can be written to the
        board.
        """
        return self.storage_binary

    def _get_all(self, region_index, valid_only):
        region_binary = self._get_region_binary(region_index)

        kv_objects = []

        offset = 0
        while True:
            try:
                ex_obj = TicKVObjectFlash(region_binary[offset:])
            except:
                break

            if not valid_only or ex_obj.is_valid():
                kv_objects.append(ex_obj)
            offset += ex_obj.length()

        return kv_objects

    def _invalidate_hashed_key(self, hashed_key):
        # Iterate all pages starting with the indented page given the key.
        for region_index in self._region_range(self._get_starting_region(hashed_key)):
            region_binary = self._get_region_binary(region_index)

            # Track if we need to write this page back to the storage.
            modified = False

            # Find the first open spot in this page.
            offset = 0
            while True:
                try:
                    ex_obj = TicKVObjectFlash(region_binary[offset:])
                except:
                    break

                if ex_obj.is_valid() and ex_obj.get_hashed_key() == hashed_key:
                    # We found a matching key that is valid.
                    logging.info(
                        "Invaliding object with hkey={:#x} at page {} index {}".format(
                            hashed_key, region_index, offset
                        )
                    )

                    length = ex_obj.length()
                    ex_obj.invalidate()
                    object_binary = ex_obj.get_binary()
                    region_binary[offset : offset + len(object_binary)] = object_binary
                    modified = True

                offset += ex_obj.length()

            if modified:
                self._update_region_binary(region_index, region_binary)

    def _append_object(self, kv_object):
        hashed_key = kv_object.get_hashed_key()

        # First we need to invalidate all matching keys.
        self._invalidate_hashed_key(hashed_key)

        # What we are trying to store.
        object_binary = kv_object.get_binary()

        # Iterate all pages starting with the indented page given the key.
        for region_index in self._region_range(self._get_starting_region(hashed_key)):
            region_binary = self._get_region_binary(region_index)

            # Find the first open spot in this page.
            offset = 0
            while True:
                try:
                    existing_object = TicKVObjectFlash(region_binary[offset:])
                except:
                    break

                offset += existing_object.length()

            # Check if there is room here to write this object.
            if len(region_binary) - offset >= len(object_binary):
                # Found place to add this object, write it and we are finished.
                logging.debug(
                    "Writing object with hkey {:#x} to page {} index {}".format(
                        hashed_key, region_index, offset
                    )
                )

                region_binary[offset : offset + len(object_binary)] = object_binary

                # Update our memory copy of the entire DB.
                self._update_region_binary(region_index, region_binary)

                break

        else:
            # We were unable to write this key, no where to store it.
            logging.error(
                "Unable to append hkey={:#x} with length {}".format(
                    hashed_key, len(object_binary)
                )
            )
            raise TockLoaderException("No space to append TicKV object")

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

    def _get_starting_region(self, hashed_key):
        """
        We use the lowest two bytes to determine the page we should try to find
        or store this key on.
        """
        return (hashed_key & 0xFFFF) % self._get_number_regions()

    def _region_range(self, starting_region):
        """
        Provide an iterator for iterating all pages in the database starting
        with a specific page.
        """
        stop = starting_region + self._get_number_regions()
        modulo = self._get_number_regions()
        for i in range(starting_region, stop):
            yield i % modulo


class TockTicKV(TicKV):
    """
    Extension of a TicKV database that adds an additional header with a
    `write_id` to enable enforcing access control.
    """

    def get(self, key):
        """
        Get the Tock-formatted value from the database given the key.
        """
        logging.info('Finding key "{}" in Tock-style TicKV database.'.format(key))

        hashed_key = self._hash_key_int(key)

        kv_object = super().get(hashed_key)
        if kv_object == None:
            return None

        try:
            tock_kv_object = TicKVObjectTockFlash(kv_object)
        except:
            tock_kv_object = None

        return tock_kv_object

    def get_all(self, region_index):
        """
        Get all Tock objects from the database and assume they are all Tock
        formatted.
        """
        kv_objects = super().get_all(region_index)
        logging.debug("Found {} TicKV objects".format(len(kv_objects)))

        tock_kv_objects = []
        for kv_object in kv_objects:
            try:
                tock_kv_object = TicKVObjectTockFlash(kv_object)
            except:
                tock_kv_object = None

            if tock_kv_object != None:
                tock_kv_objects.append(tock_kv_object)
            else:
                tock_kv_objects.append(kv_object)

        return tock_kv_objects

    def invalidate(self, key):
        """
        Delete a key-value pair from the database.
        """
        hashed_key = self._hash_key_int(key)
        super().invalidate(hashed_key)

    def append(self, key, value, write_id):
        """
        Add a key-value pair to the database.
        """
        logging.info("Appending TockTicKV object {}={}".format(key, value))
        hashed_key = self._hash_key_int(key)
        header = TicKVObjectHeader(hashed_key)
        if isinstance(value, str):
            value = value.encode("utf-8")
        storage_object = TockStorageObject(value, write_id)
        tock_kv_object = TicKVObjectTock(header, storage_object)

        super()._append_object(tock_kv_object)

    def dump(self):
        """
        Display the entire contents of the database.
        """
        logging.info("Dumping entire contents of Tock-style TicKV database.")

        out = ""
        for region_index in range(0, self._get_number_regions()):
            tock_kv_objects = self.get_all(region_index)

            out += "REGION {}\n".format(region_index)
            for tock_kv_object in tock_kv_objects:
                out += str(tock_kv_object)

            out += "\n"

        return out

    def reset(self):
        """
        Reset the database back to an initialized state.
        """
        super().reset()

    def cleanup(self):
        """
        Remove all invalid keys and re-store valid key-value pairs.
        """
        super().cleanup()

    def _hash_key(self, key):
        """
        Compute the SipHash24 for the given key.
        """
        key_buffer = key.encode("utf-8")
        return siphash.SipHash_2_4(bytearray(16), key_buffer).digest()

    def _hash_key_int(self, key):
        """
        Compute the SipHash24 for the given key. Return as u64.
        """
        hashed_key_buf = self._hash_key(key)
        return struct.unpack(">Q", hashed_key_buf)[0]
