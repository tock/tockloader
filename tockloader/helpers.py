"""
Various helper functions that tockloader uses. Mostly for interacting with
users in a nice way.
"""

import argparse
import binascii
import string
import sys

import colorama
import questionary


def set_terminal_title(title):
    if sys.stdout.isatty():
        sys.stdout.write(colorama.ansi.set_title(title))
        sys.stdout.flush()


def set_terminal_title_from_port_info(info):
    """
    Set a terminal title from a `pyserial` object.
    """
    extras = ["Tockloader"]
    if info.manufacturer and info.manufacturer != "n/a":
        extras.append(info.manufacturer)
    if info.name and info.name != "n/a":
        extras.append(info.name)
    if info.description and info.description != "n/a":
        extras.append(info.description)
    # if info.hwid and info.hwid != 'n/a':
    #  extras.append(info.hwid)
    if info.product and info.product != "n/a":
        if info.product != info.description:
            extras.append(info.product)
    title = " : ".join(extras)

    set_terminal_title(title)


def set_terminal_title_from_port(port):
    """
    Set the title of the user's terminal for Tockloader.
    """
    set_terminal_title("Tockloader : {}".format(port))


def menu_new(options, *, return_type, default_index=None, prompt="", title=""):
    """
    Present an interactive menu of choices to a user.

    `options` should be a like-list object whose iterated objects can be coerced
    into strings.

    `return_type` must be set to one of:
      - "index" - for the index into the options array
      - "value" - for the option value chosen

    `default_index` is the index to present as the default value (what happens
    if the user simply presses enter). Passing `None` disables default
    selection.
    """

    prompt_to_show = prompt
    if len(title) > len(prompt_to_show):
        prompt_to_show = title

    default = None
    if default_index:
        default = options[default_index]

    response = questionary.select(
        prompt_to_show, choices=options, default=default, qmark=""
    ).ask()

    if return_type == "index":
        return options.index(response)
    elif return_type == "value":
        return response
    else:
        raise NotImplementedError("Menu caller asked for bad return_type")


def menu(options, *, return_type, default_index=0, prompt="Which option? ", title=""):
    """
    Present a menu of choices to a user

    `options` should be a like-list object whose iterated objects can be coerced
    into strings.

    `return_type` must be set to one of
      - "index" - for the index into the options array
      - "value" - for the option value chosen

    `default_index` is the index to present as the default value (what happens
    if the user simply presses enter). Passing `None` disables default
    selection.
    """
    prompt_to_show = prompt
    print(title)
    for i, opt in enumerate(options):
        print("[{}]\t{}".format(i, opt))
    if default_index is not None:
        prompt_to_show += "[{}] ".format(default_index)
    print()

    resp = input(prompt_to_show)
    if resp == "":
        resp = default_index
    else:
        try:
            resp = int(resp)
            if resp < 0 or resp >= len(options):
                raise ValueError
        except:
            return menu(
                options,
                return_type=return_type,
                default_index=default_index,
                prompt=prompt,
                title=title,
            )

    if return_type == "index":
        return resp
    elif return_type == "value":
        return options[resp]
    else:
        raise NotImplementedError("Menu caller asked for bad return_type")


def plural(value):
    """
    Return '' or 's' based on whether the `value` means a string should have
    a plural word.

    `value` can be a list or a number. If the number or the length of the list
    is 1, then '' will be returned. Otherwise 's'.
    """
    try:
        value = len(value)
    except:
        pass
    if value == 1:
        return ""
    else:
        return "s"


def text_in_box(string, box_width):
    """
    Return a string like:
    ```
    ┌───────────────┐
    │ str           │
    └───────────────┘
    ```
    """
    string_len = box_width - 4
    truncated_str = (
        (string[: string_len - 3] + "...") if len(string) > string_len else string
    )
    out = "┌{}┐\n".format("─" * (box_width - 2))
    out += "│ {} |\n".format(truncated_str.ljust(string_len))
    out += "└{}┘".format("─" * (box_width - 2))
    return out


class ListToDictAction(argparse.Action):
    """
    `argparse` action to convert `[['key', 'val'], ['key2', 'val2']]` to
    `{'key': 'val', 'key2': 'val2'}`.

    This will also do the following conversions:
    - `[[]]` -> `{}`
    - `[['k': 'v'], []]` -> `{'k': 'v'}`
    - `[['k': 'v'], ['']]` -> `{'k': 'v'}`
    - `[['k': 'v'], ['a']]` -> `{'k': 'v', 'a': ''}`
    """

    def __call__(self, parser, namespace, values, option_string=None):
        # Remove any empty values.
        values = list(filter(None, values))
        values = list(filter(lambda x: len(x[0]), values))

        # Correct any bad values.
        for item in values:
            print(item)
            if len(item) == 1:
                item.append("")
            elif len(item) > 2:
                item = item[0:2]

        # Convert to dict and set as argument attribute.
        setattr(namespace, self.dest, dict(values))


def print_flash(address, flash):
    """
    Return binary data in a nice hexdump format.
    """

    def chunks(l, n):
        for i in range(0, len(l), n):
            yield l[i : i + n]

    def dump_line(addr, bytes):
        k = binascii.hexlify(bytes).decode("utf-8")
        b = " ".join(list(chunks(k, 2)))
        if len(b) >= 26:
            # add middle space
            b = "{} {}".format(b[0:24], b[24:])
        # Add right padding for not full lines
        if len(b) < 48:
            b = "{0: <48}".format(b)
        printable = string.ascii_letters + string.digits + string.punctuation + " "
        t = "".join([chr(i) if chr(i) in printable else "." for i in bytes])
        return "{:08x}  {}  |{}|\n".format(addr, b, t)

    out = ""
    for i, chunk in enumerate(chunks(flash, 16)):
        out += dump_line(address + (i * 16), chunk)

    return out
