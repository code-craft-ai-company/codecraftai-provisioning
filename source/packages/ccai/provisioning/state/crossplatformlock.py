"""
    .. module:: crossplatformlock
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Cross-platform advisory file lock context manager.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os
import sys
import time

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from ccai.provisioning.state.provisioninglocktimeouterror import (
    ProvisioningLockTimeoutError
)


@contextmanager
def cross_platform_lock(*, path: Path,
                        timeout_seconds: float = 30.0,
                        poll_interval_seconds: float = 0.1
                        ) -> Iterator[None]:
    """
        Acquire an advisory file lock backed by exclusive file creation.

        Implementation uses ``O_EXCL`` create for portability — works on
        POSIX, Windows, and tmpfs.  Releases the lock by removing the file
        on context exit, including on exception.

        :param path: Lock file Path.
        :param timeout_seconds: Maximum wait before raising.
        :param poll_interval_seconds: Sleep between attempts.

        :raises: ProvisioningLockTimeoutError
    """
    deadline = time.monotonic() + timeout_seconds
    fd = -1
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                         0o644)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                err_msg = (
                    "Timed out waiting for provisioning index lock "
                    "({}s) at {}".format(timeout_seconds, path)
                )
                raise ProvisioningLockTimeoutError(err_msg) from None
            time.sleep(poll_interval_seconds)

    try:
        os.write(fd, "{}\n{}\n".format(os.getpid(),
                                       sys.executable).encode("utf-8"))
        os.close(fd)
        yield
    finally:
        try:
            os.unlink(str(path))
        except FileNotFoundError:
            pass
    return
