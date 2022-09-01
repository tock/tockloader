"""
Utilities for creating output in various formats.
"""

import json
import textwrap

from . import helpers


class Display:
    def __init__(self):
        pass

    def list_apps(self, apps, verbose, quiet):
        """
        Show information about a list of apps.
        """
        pass

    def get(self):
        return self.out


class HumanReadableDisplay(Display):
    """
    Format output as a string meant to be human readable.
    """

    def __init__(self):
        self.out = ""

    def list_apps(self, apps, verbose, quiet):
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
                    self.out += helpers.text_in_box("Padding", 52)
                    self.out += textwrap.indent(app.info(verbose), "  ") + "\n\n"

            if len(apps) == 0:
                logging.info("No found apps.")

        else:
            # In quiet mode just show the names.
            self.out += " ".join([app.get_name() for app in apps])


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

    def get(self):
        return json.dumps(self.object, indent=2)
