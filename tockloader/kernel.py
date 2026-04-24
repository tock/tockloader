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
        else:
            raise TockLoaderException("Could not download open kernel binary.")

    def get_attributes(self):
        displayer = display.HumanReadableDisplay(show_headers=True)
        kernel_attr_binary = self.kernel.read()
        kernel_attrs = KernelAttributes(kernel_attr_binary, len(kernel_attr_binary))
        displayer.kernel_attributes(kernel_attrs)

        print(displayer.get())
