"""
Utilities for creating output in various formats.
"""

import json
import logging
import textwrap

from . import helpers
from .app_installed import InstalledApp
from .app_padding import PaddingApp
from .app_tab import TabApp


class Display:
    def __init__(self, show_headers):
        """
        Arguments:
        - show_headers: bool, if True, label each section in the display output.
        """
        pass

    def list_apps(self, apps, verbose, quiet):
        """
        Show information about a list of apps.
        """
        pass

    def list_attributes(self, attributes):
        """
        Show the key value pairs for a list of attributes.
        """
        pass

    def bootloader_version(self, version):
        """
        Show the bootloader version stored in the bootloader itself.
        """
        pass

    def kernel_attributes(self, kern_attrs):
        """
        Show the kernel attributes stored in the kernel binary.
        """
        pass

    def get(self):
        return self.out


def choose(b, t, f):
    if b:
        return t
    return f


def start_of_app(width, address):
    return "{:>#10x}┬{}┐\n".format(address, "─" * width)


def end_of_app(width, address, continuing):
    left_corner = choose(continuing, "┼", "┴")
    right_corner = choose(continuing, "┤", "┘")
    return "{:>#10x}{}{}{}\n".format(address, left_corner, "─" * width, right_corner)


def app_bracket(width, left, right):
    if len(left) + len(right) >= (width - 1):
        room_for_left = width - 1 - 1 - len(right)
        left = "{}…".format(left[0:room_for_left])
    left_size = width - len(right)
    content = "{:<{left_size}}{}".format(left, right, left_size=left_size)
    return "{}│{}│\n".format(" " * 10, content)


class HumanReadableDisplay(Display):
    """
    Format output as a string meant to be human readable.
    """

    def __init__(self, show_headers=False):
        self.out = ""
        self.show_headers = show_headers

    def list_apps(self, apps, verbose, quiet):
        if self.show_headers:
            self.out += "Apps:\n"

        if not quiet:
            # Print info about each app
            for i, app in enumerate(apps):
                if app.is_app():
                    self.out += helpers.text_in_box("App {}".format(i), 52) + "\n"

                    # # Check if this app is OK with the MPU region requirements.
                    # # TODO: put this back!
                    # if not self._app_is_aligned_correctly(
                    #     app.get_address(), app.get_size()
                    # ):
                    #     self.out += "  [WARNING] App is misaligned for the MPU\n"

                    self.out += textwrap.indent(app.info(verbose), "  ") + "\n\n"
                else:
                    # Display padding
                    self.out += helpers.text_in_box("Padding", 52) + "\n"
                    self.out += textwrap.indent(app.info(verbose), "  ") + "\n\n"

            if len(apps) == 0:
                logging.info("No found apps.")

        else:
            # In quiet mode just show the names.
            self.out += " ".join([app.get_name() for app in apps])

    def show_app_map_from_address(self, apps, start_address):
        """
        Print a layout map of apps assuming they are located back-to-back
        starting from `start_address`. Example:

        ```
        0x30000┬──────────────────────────────────────────────────┐
               │App: blink                             [Installed]│
               │  Length: 16384 (0x4000)                          │
        0x34000┼──────────────────────────────────────────────────┤
               │App: blink                             [Installed]│
               │  Length: 16384 (0x4000)                          │
        0x3c000┴──────────────────────────────────────────────────┘
        ```
        """
        out = ""
        address = start_address
        for i, app in enumerate(apps):
            continuing = i < len(apps) - 1
            size = app.get_size()

            if i == 0:
                out += start_of_app(50, address)

            if isinstance(app, TabApp):
                title = "App: {}".format(app.get_name())
                out += app_bracket(50, title, "[From TAB]")
            elif isinstance(app, InstalledApp):
                title = "App: {}".format(app.get_name())
                out += app_bracket(50, title, "[Installed]")
            elif isinstance(app, PaddingApp):
                out += app_bracket(50, "Padding", "")

            address += size

            out += app_bracket(50, "  Length: {} ({:#x})".format(size, size), "")
            out += end_of_app(50, address, continuing)

        self.out += out

    def show_app_map_actual_address(self, apps):
        """
        Show a map of installed applications with known addresses. Example:

        ```
        0x30000┬──────────────────────────────────────────────────┐
               │App: blink                             [Installed]│
               │  Length: 16384 (0x4000)                          │
        0x34000┴──────────────────────────────────────────────────┘
        0x38000┬──────────────────────────────────────────────────┐
               │App: blink                             [Installed]│
               │  Length: 16384 (0x4000)                          │
        0x3c000┴──────────────────────────────────────────────────┘
        ```
        """

        out = ""
        prev_address = -1
        for i, app in enumerate(apps):
            size = app.get_size()
            active_address = app.get_address()

            if active_address != prev_address:
                out += start_of_app(50, active_address)

            if isinstance(app, TabApp):
                title = "App: {}".format(app.get_name())
                out += app_bracket(50, title, "[From TAB]")
            elif isinstance(app, InstalledApp):
                title = "App: {}".format(app.get_name())
                out += app_bracket(50, title, "[Installed]")
            elif isinstance(app, PaddingApp):
                out += app_bracket(50, "Padding", "")
            out += app_bracket(50, "  Length: {} ({:#x})".format(size, size), "")

            prev_address = active_address + size

            # Check if the next app starts at the address the current app ends
            # at.
            immediately_after = False
            if i < len(apps) - 1:
                next_address = apps[i + 1].get_address()
                immediately_after = prev_address == next_address

            out += end_of_app(50, prev_address, immediately_after)

        self.out += out

    def show_board_visual(self, apps):
        def horizontal_add(existing, new):
            existing_lines = existing.split("\n")
            new_lines = existing.split("\n")
            out = ""
            for i, l in enumerate(existing_lines):
                out += "{} {}\n".format(l, new_lines[i])
            return out

        out = ""
        for i, app in enumerate(apps):
            name = app.get_name()
            box_width = len(name) + 4
            box = helpers.text_in_box(name, box_width, 10)
            if i == 0:
                out = box
            else:
                out = horizontal_add(out, box)

        self.out = out

    def list_attributes(self, attributes):
        if self.show_headers:
            self.out += "Attributes:\n"

        for index, attribute in enumerate(attributes):
            if attribute:
                self.out += "{:02d}: {:>8} = {}\n".format(
                    index, attribute["key"], attribute["value"]
                )

            else:
                self.out += "{:02d}:\n".format(index)

    def bootloader_version(self, version):
        self.out += "Bootloader version: {}\n".format(version)

    def kernel_attributes(self, kern_attrs):
        self.out += kern_attrs.info()


class VisualDisplay(Display):
    """
    Format output as an ASCII art string.

    ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────┐
    │         | │         | │         | │       |
    │         | │         | │         | │       |
    │         | │         | │         | │       |
    │ version | │ version | │ version | │ blink |
    │         | │         | │         | │       |
    │         | │         | │         | │       |
    │         | │         | │         | │       |
    │         | │         | │         | │       |
    └─────────┘ └─────────┘ └─────────┘ └───────┘
    ┌───────────────────────────────────────────┐
    │ Kernel                                    |
    └───────────────────────────────────────────┘
    """

    def __init__(self):
        self.out = ""

    def list_apps(self, apps, verbose, quiet):
        def horizontal_add(existing, new):
            existing_lines = existing.split("\n")
            new_lines = new.split("\n")
            out = ""
            for i, l in enumerate(existing_lines):
                if len(l) > 0:
                    out += "{} {}\n".format(l, new_lines[i])
            return out[:-1]

        out = ""
        for i, app in enumerate(apps):
            name = app.get_name()
            box_width = len(name) + 4
            box = helpers.text_in_box(name, box_width, 10) + "\n"
            if i == 0:
                out = box
            else:
                out = horizontal_add(out, box)

        self.out += out

    def list_attributes(self, attributes):
        pass

    def bootloader_version(self, version):
        pass

    def kernel_attributes(self, kern_attrs):
        width = self._width()
        out = "\n"
        out += helpers.text_in_box("Tock Kernel", width)
        self.out += out

    def _width(self):
        width = 0
        for l in self.out.split("\n"):
            if len(l) > width:
                width = len(l)
        return width


class JSONDisplay(Display):
    """
    Format output as JSON.
    """

    def __init__(self):
        self.object = {}

    def list_apps(self, apps, verbose, quiet):
        self.object["apps"] = []

        for app in apps:
            self.object["apps"].append(app.object())

    def list_attributes(self, attributes):
        self.object["attributes"] = []
        for index, attribute in enumerate(attributes):
            if attribute:
                self.object["attributes"].append((attribute["key"], attribute["value"]))
            else:
                self.object["attributes"].append(None)

    def bootloader_version(self, version):
        self.object["bootloader_version"] = version

    def get(self):
        return json.dumps(self.object, indent=2)
