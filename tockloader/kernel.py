import argparse
import io
import logging
import os
import shutil
import struct
import tempfile
import textwrap
import urllib.request

import toml

from . import display
from .exceptions import TockLoaderException
from .kernel_attributes import KernelAttributes


class Kernel:
    """
    Tock binary kernel object.
    """

    def __init__(self, kernel_path, args=argparse.Namespace()):
        self.args = args
        self.kernel_path = kernel_path

        if os.path.exists(kernel_path):
            # Fetch it from the local filesystem.
            self.kernel = open(kernel_path, "rb")
            self.binary = self.kernel.read()
            self.attrs = KernelAttributes(self.binary, len(self.binary))
        else:
            raise TockLoaderException("Could not open kernel binary.")

    def add_attribute(self, tlvname, parameters):
        self.attrs.add_tlv(tlvname, parameters)

    def get_attributes(self):
        return self.attrs

    def update(self):
        """
        Save an updated kernel binary.
        """

        # Close the kernel we have open since we need to re-open it for writing.
        self.kernel.close()

        # Now need to open kernel binary for writing.
        k = open(self.kernel_path, "wb")

        attrs = self.attrs.get_binary()
        binary = self.binary[0 : -len(attrs)] + attrs
        k.write(binary)

        # Close the version for writing.
        k.close()

        # Re-open the read version
        self.kernel = open(self.kernel_path, "rb")
