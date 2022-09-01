#!/usr/bin/env python3

import pydoc
import os, sys

# This script generates mkdocs friendly Markdown documentation from a python package.
# It is based on the the following blog post by Christian Medina
# https://medium.com/python-pandemonium/python-introspection-with-the-inspect-module-2c85d5aa5a48#.twcmlyack
# https://gist.github.com/dvirsky/30ffbd3c7d8f37d4831b30671b681c24

module_header = "# Package {} Documentation\n"
class_header = "## Class {}"
function_header = "### {}"


def getmarkdown(module):
    output = [module_header.format(module.__name__)]

    if module.__doc__:
        output.append(module.__doc__)

    output.extend(getclasses(module))
    output.extend(getfunctions(module))
    return "\n".join((str(x) for x in output))


def getclasses(item, depth=0):
    output = []
    for cl in pydoc.inspect.getmembers(item, pydoc.inspect.isclass):

        # Make sure we are only getting classes in this file
        if depth == 0:
            if item.__name__ != cl[1].__module__:
                continue

        # Ignore bogus stuff
        if cl[0] == "__class__" or cl[0].startswith("_"):
            continue

        # Consider anything that starts with _ private
        # and don't document it
        output.append(class_header.format(cl[0]))
        # Get the docstring
        output.append(pydoc.inspect.getdoc(cl[1]))
        # Get the functions
        output.extend(getfunctions(cl[1]))
        # Recurse into any subclasses
        output.extend(getclasses(cl[1], depth + 1))
        output.append("\n")
    return output


def getfunctions(item):
    output = []
    at_end = []
    for func in pydoc.inspect.getmembers(item, pydoc.inspect.isfunction):
        out = output
        if func[0].startswith("_") and func[0] != "__init__":
            out = at_end

        out.append(function_header.format(func[0].replace("_", "\\_")))

        # Get the signature
        out.append("```py\n")
        out.append(
            "def {}{}\n".format(
                func[0],
                pydoc.inspect.formatargspec(*pydoc.inspect.getfullargspec(func[1])),
            )
        )
        out.append("```\n")

        # get the docstring
        if pydoc.inspect.getdoc(func[1]):
            out.append("\n")
            out.append(pydoc.inspect.getdoc(func[1]))

        out.append("\n")
    return output + at_end


def generatedocs(module, filename):
    try:
        sys.path.insert(0, os.getcwd() + "/..")
        # Attempt import
        mod = pydoc.safeimport(module)
        if mod is None:
            print("Module not found")

        # Module imported correctly, let's create the docs
        with open(filename, "w") as f:
            f.write(getmarkdown(mod))
    except pydoc.ErrorDuringImport as e:
        print("Error while trying to import " + module)


# if __name__ == '__main__':
generatedocs("tockloader.main", "main.md")
generatedocs("tockloader.tockloader", "tockloader.md")
generatedocs("tockloader.board_interface", "board_interface.md")
generatedocs("tockloader.bootloader_serial", "bootloader_serial.md")
generatedocs("tockloader.jlinkexe", "jlinkexe.md")
generatedocs("tockloader.openocd", "openocd.md")
generatedocs("tockloader.flash_file", "flash_file.md")
generatedocs("tockloader.tab", "tab.md")
generatedocs("tockloader.app_installed", "app_installed.md")
generatedocs("tockloader.app_tab", "app_tab.md")
generatedocs("tockloader.app_padding", "app_padding.md")
generatedocs("tockloader.tbfh", "tbfh.md")
generatedocs("tockloader.exceptions", "exceptions.md")
generatedocs("tockloader.helpers", "helpers.md")
generatedocs("tockloader.display", "display.md")

# Make index from readme
with open("../README.md") as infile:
    with open("index.md", "w") as outfile:
        outfile.write(infile.read())
