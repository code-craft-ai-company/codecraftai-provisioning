"""
    .. module:: ocitask
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Aspects-controlled wait helpers for OCI lifecycle-state polling.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os
import time

from typing import Any, Callable


class OciWaitTimeoutError(RuntimeError):
    """
        Raised when a wait helper exceeds its aspects-derived timeout.
    """


def _aspect_attr(*, aspects: Any, name: str, default: Any) -> Any:
    """
        Read an attribute from an aspects object or dict.

        :param aspects: Aspects object or dict.
        :param name: Attribute name.
        :param default: Default value when missing.

        :returns: The attribute value or default.
    """
    if aspects is None:
        rtnval = default
        return rtnval
    if isinstance(aspects, dict):
        rtnval = aspects.get(name, default)
        return rtnval
    rtnval = getattr(aspects, name, default)
    return rtnval


def wait_until(*, predicate: Callable[[], bool], aspects: Any,
               description: str) -> None:
    """
        Block until ``predicate()`` returns True, polling on aspects intervals.

        :param predicate: Zero-arg callable returning bool.
        :param aspects: Aspects controlling timeout and interval.
        :param description: Free-text used in timeout error messages.

        :raises: OciWaitTimeoutError
    """
    timeout_s = _aspect_attr(aspects=aspects, name="verify_timeout",
                             default=600.0)
    interval_s = _aspect_attr(aspects=aspects, name="verify_interval",
                              default=2.0)

    if interval_s <= 0:
        interval_s = 0.1

    deadline = time.monotonic() + float(timeout_s)
    while True:
        try:
            done = predicate()
        except Exception as xcpt:
            err_msg_lines = ["Wait predicate raised."]
            err_msg_lines.append("DESCRIPTION: {}".format(description))
            err_msg_lines.append("CAUSE: {}".format(xcpt))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciWaitTimeoutError(err_msg) from None

        if done is True:
            return

        if time.monotonic() >= deadline:
            err_msg_lines = ["Wait predicate timed out."]
            err_msg_lines.append("DESCRIPTION: {}".format(description))
            err_msg_lines.append("TIMEOUT_SECONDS: {}".format(timeout_s))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciWaitTimeoutError(err_msg)

        time.sleep(interval_s)
