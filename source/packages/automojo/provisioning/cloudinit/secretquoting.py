"""
    .. module:: secretquoting
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Shell-safe quoting helpers for cloud-init rendering.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict


def quote_for_shell(*, value: str) -> str:
    """
        Quote a value for inclusion in a double-quoted shell position.

        Uses POSIX-safe single-quote wrapping so embedded $, backticks, and
        backslashes never reach the shell's interpretation pass.

        :param value: The raw value.

        :returns: A single-quoted shell-safe string.
    """
    inner = value.replace("'", "'\\''")
    rtnval = "'{}'".format(inner)
    return rtnval


def write_authkey_file_block(*, authkey: str) -> Dict[str, Any]:
    """
        Build the cloud-init write_files entry for the auth-key file.

        The auth key is written verbatim to a root-only file; the shell
        never sees the key directly.

        :param authkey: The minted auth key.

        :returns: A dict ready to be appended to write_files.
    """
    rtnval = {
        "path": "/etc/tailscale/authkey",
        "owner": "root:root",
        "permissions": "0400",
        "content": authkey,
    }
    return rtnval
