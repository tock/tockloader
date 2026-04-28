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
        displayer = display.HumanReadableDisplay(show_headers=True)
        kernel_attr_binary = self.kernel.read()
        kernel_attrs = KernelAttributes(kernel_attr_binary, len(kernel_attr_binary))
        kernel_attrs.add_public_key([])
        displayer.kernel_attributes(kernel_attrs)

        print(displayer.get())
