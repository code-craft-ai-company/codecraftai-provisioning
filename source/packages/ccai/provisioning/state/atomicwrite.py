"""
    .. module:: atomicwrite
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Atomic write-then-rename helper for state files.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from pathlib import Path


def write_tmp_then_rename(*, path: Path, content: str) -> None:
    """
        Write content to ``<path>.tmp`` then atomically replace ``<path>``.

        Guarantees a reader never sees a partial file even on crash mid-write.

        :param path: The final destination Path.
        :param content: The full content to write.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content)
    os.replace(tmp, path)
    return
