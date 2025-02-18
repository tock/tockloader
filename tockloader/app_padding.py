import textwrap

from .tbfh import TBFHeaderPadding


class PaddingApp:
    """
    Representation of a placeholder app that is only padding between other apps.
    """

    def __init__(self, size, address=None):
        """
        Create a `PaddingApp` based on the amount of size needing in the
        padding.
        """
        self.tbfh = TBFHeaderPadding(size)
        self.address = address

    def is_app(self):
        """
        Whether this is an app or padding.
        """
        return False

    def get_header(self):
        """
        Return the header for this padding.
        """
        return self.tbfh

    def get_size(self):
        """
        Return the total size of the padding in bytes.
        """
        return self.tbfh.get_app_size()

    def get_tbfh(self):
        """
        Return the TBF header.
        """
        return self.tbfh

    def verify_credentials(self, public_keys):
        """
        Padding apps do not have credentials, so we ignore this.
        """
        pass

    def has_fixed_addresses(self):
        """
        A padding app is not an executable so can be placed anywhere.
        """
        return False

    def get_address(self):
        """
        Get the address of where on the board this padding app is.
        """
        return self.address

    def has_app_binary(self):
        """
        We can always return the binary for a padding app, so we can always
        return true.
        """
        return True

    def get_binary(self, address=None):
        """
        Return the binary array comprising the header and the padding between
        apps.
        """
        tbfh_binary = self.tbfh.get_binary()
        # Calculate the padding length.
        padding_binary_size = self.get_size() - len(tbfh_binary)
        return tbfh_binary + b"\0" * padding_binary_size

    def info(self, verbose=False):
        """
        Get a string describing various properties of the padding.
        """
        out = ""
        out += "Total Size in Flash:   {} bytes\n".format(self.get_size())

        if verbose:
            out += textwrap.indent(str(self.tbfh), "  ")
        return out

    def __str__(self):
        return "PaddingApp({})".format(self.get_size())


class InstalledPaddingApp(PaddingApp):
    """
    Representation of a placeholder app that is only padding between other apps
    that was extracted from a board.
    """

    def __init__(self, tbfh, address):
        """
        Create a `InstalledPaddingApp` from an extracted TBFH.
        """
        self.tbfh = tbfh
        self.address = address

    def info(self, verbose=False):
        """
        Get a string describing various properties of the padding.
        """
        out = ""
        out += "Total Size in Flash:   {} bytes\n".format(self.get_size())

        if verbose:
            out += "Address in Flash:      {:#x}\n".format(self.address)
            out += textwrap.indent(self.tbfh.to_str_at_address(self.address), "  ")
        return out

    def __str__(self):
        return "PaddingApp({})".format(self.get_size())
