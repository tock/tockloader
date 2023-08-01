import logging
import struct
import textwrap

from .exceptions import TockLoaderException


class TabTbf:
    """
    Representation of a compiled app in the Tock Binary Format for use in
    Tockloader.

    This correlates to a specific .tbf file storing a .tab file.
    """

    def __init__(self, filename, tbfh, binary, tbff):
        """
        - `filename` is the identifier used in the .tab.
        - `tbfh` is the header object
        - `binary` is the actual compiled binary code
        """
        self.filename = filename
        self.tbfh = tbfh
        self.binary = binary
        self.tbff = tbff


class TabApp:
    """
    Representation of a Tock app for a specific architecture and board from a
    TAB file. This is different from a TAB, since a TAB can include compiled
    binaries for a range of architectures, or compiled for various scenarios,
    which may not be applicable for a particular board.

    A TabApp need not be a single TabTbf, as an app from a TAB can include
    multiple TabTbfs if the app was compiled multiple times. This could be for
    any reason (e.g. it was signed with different keys, or it uses different
    compiler optimizations), but typically this is because it is compiled for
    specific addresses in flash and RAM, and there are multiple linked versions
    present in the TAB. If so, there will be multiple TabTbfs included in this
    App object, and the correct one for the board will be used later.
    """

    def __init__(self, tbfs):
        """
        Create a `TabApp` from a list of TabTbfs.
        """
        if len(tbfs) == 0:
            raise TockLoaderException(
                "There must be at least one TBF to create a TabApp"
            )

        self.tbfs = tbfs  # A list of TabTbfs.

        # Address where RAM for apps starts on the board. This is useful for
        # filtering TBFs that are fixed address to remove TBFs which have
        # potentially good flash addresses but wrong RAM addresses.
        self.ram_address_filter = None

    def get_name(self):
        """
        Return the app name.
        """
        app_names = set([tbf.tbfh.get_app_name() for tbf in self._get_tbfs()])
        if len(app_names) > 1:
            raise TockLoaderException("Different names inside the same TAB?")
        elif len(app_names) == 0:
            raise TockLoaderException("No name in the TBF binaries")

        return app_names.pop()

    def is_modified(self):
        """
        Returns whether this app needs to be flashed on to the board. Since this
        is a TabApp, we did not get this app from the board and therefore we
        have to flash this to the board.
        """
        return True

    def set_sticky(self):
        """
        Mark this app as "sticky" in the app's header. This makes it harder to
        accidentally remove this app if it is a core service or debug app.
        """
        for tbf in self._get_tbfs():
            tbf.tbfh.set_flag("sticky", True)

    def get_header(self):
        """
        Return a header if there is only one.
        """
        if len(self._get_tbfs()) == 1:
            return self._get_tbfs()[0].tbfh
        return None

    def get_footers(self):
        """
        Return the footers if there are any.
        """
        if len(self._get_tbfs()) == 1:
            return self._get_tbfs()[0].tbff
        return None

    def get_size(self):
        """
        Return the total size (including TBF header) of this app in bytes.

        This is only valid if there is only one TBF.
        """
        if len(self._get_tbfs()) == 1:
            return self._get_tbfs()[0].tbfh.get_app_size()
        else:
            raise TockLoaderException("Size only valid with one TBF")

    def get_app_version(self):
        """
        Return the version number stored in a program header.

        This is only valid if there is only one TBF.
        """
        if len(self._get_tbfs()) == 1:
            return self._get_tbfs()[0].tbfh.get_app_version()
        else:
            raise TockLoaderException("Version number only valid with one TBF")

    def set_size(self, size):
        """
        Force the entire app to be a certain size. If `size` is smaller than the
        actual app an error will be thrown.
        """
        for tbf in self._get_tbfs():
            header_size = tbf.tbfh.get_header_size()
            binary_size = len(tbf.binary)
            current_size = header_size + binary_size
            if size < current_size:
                raise TockLoaderException(
                    "Cannot make app smaller. Current size: {} bytes".format(
                        current_size
                    )
                )
            tbf.tbfh.set_app_size(size)

    def set_minimum_size(self, size):
        """
        Force each version of the entire app to be a certain size. If `size` is
        smaller than the actual app nothing happens.
        """
        for tbf in self._get_tbfs():
            header_size = tbf.tbfh.get_header_size()
            binary_size = len(tbf.binary)
            current_size = header_size + binary_size
            if size > current_size:
                tbf.tbfh.set_app_size(size)

    def set_size_constraint(self, constraint):
        """
        Change the entire app size for each compilation and architecture based
        on certain rules.

        Valid rules:
        - None: do nothing
        - 'powers_of_two': make sure the entire size is a power of two.
        - ('multiple', value): make sure the entire size is a multiple of value.
        """
        if constraint == "powers_of_two":
            # Make sure the total app size is a power of two.
            for tbf in self._get_tbfs():
                current_size = tbf.tbfh.get_app_size()
                if (current_size & (current_size - 1)) != 0:
                    # This is not a power of two, but should be.
                    count = 0
                    while current_size != 0:
                        current_size >>= 1
                        count += 1
                    tbf.tbfh.set_app_size(1 << count)
                    logging.debug(
                        "Rounding app up to ^2 size ({} bytes)".format(1 << count)
                    )

        elif type(constraint) is tuple:
            if constraint[0] == "multiple":
                size_multiple = constraint[1]
                for tbf in self._get_tbfs():
                    current_size = tbf.tbfh.get_app_size()
                    if (current_size % size_multiple) != 0:
                        # This is not a multiple of the proper size, but should
                        # be.
                        new_size = ((current_size // size_multiple) + 1) * size_multiple
                        tbf.tbfh.set_app_size(new_size)
                        logging.debug(
                            "Rounding app up to multiple of {} bytes. Now {} bytes in size.".format(
                                size_multiple, new_size
                            )
                        )

    def has_fixed_addresses(self):
        """
        Return true if any TBF binary in this app is compiled for a fixed
        address. That likely implies _all_ binaries are compiled for a fixed
        address.
        """
        has_fixed_addresses = False
        for tbf in self._get_tbfs():
            if tbf.tbfh.has_fixed_addresses():
                has_fixed_addresses = True
                break
        return has_fixed_addresses

    def filter_fixed_ram_address(self, ram_address):
        """
        Specify the start of RAM to filter TBFs in this TAB. TBFs with fixed RAM
        addresses that are not reasonably able to fit with the available RAM are
        ignored from the TAB.
        """
        self.ram_address_filter = ram_address

    def get_fixed_addresses_flash_and_sizes(self):
        """
        Return a list of tuples of all addresses in flash this app is compiled
        for and the size of the app at that address.

        [(address, size), (address, size), ...]
        """
        apps_in_flash = []
        for tbf in self._get_tbfs():
            apps_in_flash.append(
                (tbf.tbfh.get_fixed_addresses()[1], tbf.tbfh.get_app_size())
            )
        return apps_in_flash

    def is_loadable_at_address(self, address):
        """
        Check if it is possible to load this app at the given address. Returns
        True if it is possible, False otherwise.
        """
        if not self.has_fixed_addresses():
            # No fixed addresses means we can put the app anywhere.
            return True

        # Otherwise, see if we have a TBF which can go at the requested address.
        for tbf in self._get_tbfs():
            fixed_flash_address = tbf.tbfh.get_fixed_addresses()[1]
            tbf_header_length = tbf.tbfh.get_header_size()

            # Ok, we have to be a little tricky here. What we actually care
            # about is ensuring that the application binary itself ends up at
            # the requested fixed address. However, what this function has to do
            # is see if the start of the TBF header can go at the requested
            # address. We have some flexibility, since we can make the header
            # larger so that it pushes the application binary to the correct
            # address. So, we want to see if we can reasonably do that. If we
            # are within 128 bytes, we say that we can.
            if (
                fixed_flash_address >= (address + tbf_header_length)
                and (address + tbf_header_length + 128) > fixed_flash_address
            ):
                return True

        return False

    def fix_at_next_loadable_address(self, address):
        """
        Calculate the next reasonable address where we can put this app where
        the address is greater than or equal to `address`. The `address`
        argument is the earliest address the app can be at, either the start of
        apps or immediately after a previous app. Then return that address.
        If we can't satisfy the request, return None.

        The "fix" part means remove all TBFs except for the one that we used
        to meet the address requirements.

        If the app doesn't have a fixed address, then we can put it anywhere,
        and we just return the address. If the app is compiled with fixed
        addresses, then we need to calculate an address. We do a little bit of
        "reasonable assuming" here. Fixed addresses are based on where the _app
        binary_ must be located. Therefore, the start of the app where the TBF
        header goes must be before that. This can be at any address (as long as
        the header will fit), but we want to make this simpler, so we just
        assume the TBF header should start on a 1024 byte alignment.
        """
        if not self.has_fixed_addresses():
            # No fixed addresses means we can put the app anywhere.
            return address

        def align_down_to(v, a):
            """
            Calculate the address correctly aligned to `a` that is lower than or
            equal to `v`.
            """
            return v - (v % a)

        # Find the binary with the lowest valid address that is above `address`.
        best_address = None
        best_index = None
        for i, tbf in enumerate(self._get_tbfs()):
            fixed_flash_address = tbf.tbfh.get_fixed_addresses()[1]

            # Align to get a reasonable address for this app.
            wanted_address = align_down_to(fixed_flash_address, 1024)

            if wanted_address >= address:
                if best_address == None:
                    best_address = wanted_address
                    best_index = i
                elif wanted_address < best_address:
                    best_address = wanted_address
                    best_index = i

        if best_index != None:
            self.tbfs = [self._get_tbfs()[best_index]]
            return best_address
        else:
            return None

    def delete_tlv(self, tlvid):
        """
        Delete a particular TLV from each TBF header and footer.
        """
        for tbf in self._get_tbfs():
            tbf.tbfh.delete_tlv(tlvid)
            tbf.tbff.delete_tlv(tlvid)

    def modify_tbfh_tlv(self, tlvid, field, value):
        """
        Modify a particular TLV from each TBF header to set field=value.
        """
        for tbf in self._get_tbfs():
            tbf.tbfh.modify_tlv(tlvid, field, value)

    def add_tbfh_tlv(self, tlvid, parameters):
        """
        Add a particular TLV to each TBF's header.
        """
        for tbf in self._get_tbfs():
            tbf.tbfh.add_tlv(tlvid, parameters)

    def add_credential(self, credential_type, public_key, private_key, cleartext_id):
        """
        Add a credential by type to the TBF footer.
        """
        for tbf in self._get_tbfs():
            integrity_blob = tbf.tbfh.get_binary() + tbf.binary
            tbf.tbff.add_credential(
                credential_type, public_key, private_key, integrity_blob, cleartext_id
            )

    def delete_credential(self, credential_type):
        """
        Remove a credential by ID from the TBF footer.
        """
        for tbf in self._get_tbfs():
            tbf.tbff.delete_credential(credential_type)

    def verify_credentials(self, public_keys):
        """
        Using an optional array of public_key binaries, try to check any
        contained credentials to verify they are valid.
        """
        for tbf in self._get_tbfs():
            integrity_blob = tbf.tbfh.get_binary() + tbf.binary
            tbf.tbff.verify_credentials(public_keys, integrity_blob)

    def corrupt_tbf(self, field_name, value):
        """
        Modify the TBF root header just before installing the application.
        """
        for tbf in self._get_tbfs():
            tbf.tbfh.corrupt_tbf(field_name, value)

    def has_app_binary(self):
        """
        Return true if we have an application binary with this app.
        """
        # By definition, a TabApp will have an app binary.
        return True

    def get_binary(self, address):
        """
        Return the binary array comprising the entire application.

        This is only valid if there is one TBF file.

        `address` is the address of flash the _start_ of the app will be placed
        at. This means where the TBF header will go.
        """

        if len(self._get_tbfs()) == 1:
            tbfh = self._get_tbfs()[0].tbfh
            app_binary = self._get_tbfs()[0].binary
            tbff = self._get_tbfs()[0].tbff

            # If the TBF is compiled for a fixed address, then we make sure the
            # addresses are lined up.
            if tbfh.has_fixed_addresses() == True:
                tbfh.adjust_starting_address(address)

            # Check that the binary is not longer than it is supposed to be.
            # This might happen if the size was changed, but any code using this
            # binary has no way to check. If the binary is too long, we truncate
            # the actual binary blob (which should just be padding) to the
            # correct length. If it is too short it is ok, since the board
            # shouldn't care what is in the flash memory the app is not using.
            binary = self._concatenate_and_truncate_binary(tbfh, app_binary, tbff)

            return binary

        else:
            raise ("Only valid for one TBF file.")

    def get_names_and_binaries(self):
        """
        Return (filename, binary) tuples for each contained TBF. This is for
        updating a .tab file.
        """
        out = []
        for tbf in self._get_tbfs():
            # Truncate in case the header grew and elf2tab padded the binary.
            binary = self._concatenate_and_truncate_binary(
                tbf.tbfh, tbf.binary, tbf.tbff
            )
            out.append((tbf.filename, binary))
        return out

    def _get_tbfs(self):
        """
        Helper function so we can implement TBF filtering.

        For normal TBFs (aka PIC TBFs), this doesn't do anything. For fixed
        address TBFs, this filters the list of TBFs within the TAB to only those
        that are plausibly within the app memory region for the board.
        """
        if self.ram_address_filter == None:
            return self.tbfs
        else:
            tbfs = []
            for tbf in self.tbfs:
                fixed_addresses = tbf.tbfh.get_fixed_addresses()
                if fixed_addresses != None:
                    if fixed_addresses[0] < self.ram_address_filter or fixed_addresses[
                        0
                    ] > (self.ram_address_filter + 0x200000):
                        pass
                    else:
                        tbfs.append(tbf)
                else:
                    tbfs.append(tbf)
            return tbfs

    def _concatenate_and_truncate_binary(self, header, program_binary, footer):
        size = self.get_size()

        header_binary = header.get_binary()
        footer_binary = footer.get_binary()

        binary = header_binary + program_binary + footer_binary

        if len(binary) > size:
            logging.info(
                "Binary is larger header indicates. Actual:{}, expected:{}".format(
                    len(binary), size
                )
            )

            # First try to shrink the footer to recover the space.
            extra = len(binary) - size
            footer.shrink(extra)
            footer_binary = footer.get_binary()
            binary = header_binary + program_binary + footer_binary

            # If that was not enough, then try to truncate the actual program
            # binary, which was likely padded with zeros by elf2tab.
            if len(binary) > size:
                raise TockLoaderException(
                    "Unable to make binary fit size. Compile with larger footer."
                )

        return binary

    def get_crt0_header_str(self):
        """
        Return a string representation of the crt0 header some apps use for
        doing PIC fixups. We assume this header is positioned immediately
        after the TBF header (AKA at the beginning of the application binary).
        """
        tbfh = self._get_tbfs()[0].tbfh
        app_binary = self._get_tbfs()[0].binary

        crt0 = struct.unpack("<IIIIIIIIII", app_binary[0:40])

        # Also display the number of relocations in the binary.
        reldata_start = crt0[8]
        reldata_len = struct.unpack(
            "<I", app_binary[reldata_start : reldata_start + 4]
        )[0]

        out = ""
        out += "{:<20}: {:>10} {:>#12x}\n".format("got_sym_start", crt0[0], crt0[0])
        out += "{:<20}: {:>10} {:>#12x}\n".format("got_start", crt0[1], crt0[1])
        out += "{:<20}: {:>10} {:>#12x}\n".format("got_size", crt0[2], crt0[2])
        out += "{:<20}: {:>10} {:>#12x}\n".format("data_sym_start", crt0[3], crt0[3])
        out += "{:<20}: {:>10} {:>#12x}\n".format("data_start", crt0[4], crt0[4])
        out += "{:<20}: {:>10} {:>#12x}\n".format("data_size", crt0[5], crt0[5])
        out += "{:<20}: {:>10} {:>#12x}\n".format("bss_start", crt0[6], crt0[6])
        out += "{:<20}: {:>10} {:>#12x}\n".format("bss_size", crt0[7], crt0[7])
        out += "{:<20}: {:>10} {:>#12x}\n".format("reldata_start", crt0[8], crt0[8])
        out += "  {:<18}: {:>10} {:>#12x}\n".format(
            "[reldata_len]", reldata_len, reldata_len
        )
        out += "{:<20}: {:>10} {:>#12x}\n".format("stack_size", crt0[9], crt0[9])

        return out

    def info(self, verbose=False):
        """
        Get a string describing various properties of the app.
        """
        out = ""
        out += "Name:                  {}\n".format(self.get_name())
        out += "Version:               {}\n".format(self.get_app_version())
        out += "Total Size in Flash:   {} bytes\n".format(self.get_size())

        if verbose:
            for tbf in self._get_tbfs():
                out += textwrap.indent(str(tbf.tbfh), "  ")
        return out

    def __str__(self):
        return self.get_name()
