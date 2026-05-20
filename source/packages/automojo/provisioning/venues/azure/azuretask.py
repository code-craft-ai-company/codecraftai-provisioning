"""
    .. module:: azuretask
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Aspects-controlled wait helpers wrapping azure-mgmt LROPollers.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any


class AzureWaitTimeoutError(RuntimeError):
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


def resolve_poller(*, poller: Any, aspects: Any, description: str) -> Any:
    """
        Resolve an Azure long-running operation poller to its result.

        Azure ``begin_*`` calls return an ``LROPoller``; this helper calls
        ``.result(...)`` with the aspects-derived timeout.  Plain (already
        resolved) return values are passed straight through so mock clients
        that return the resource directly continue to work.

        :param poller: An LROPoller, or an already-resolved resource.
        :param aspects: Aspects controlling the timeout.
        :param description: Free-text used in timeout error messages.

        :returns: The resolved resource.
        :raises: AzureWaitTimeoutError
    """
    result_attr = getattr(poller, "result", None)
    if result_attr is None or not callable(result_attr):
        rtnval = poller
        return rtnval

    timeout_s = _aspect_attr(aspects=aspects, name="verify_timeout",
                             default=600.0)

    try:
        resolved = result_attr(timeout=float(timeout_s))
    except TypeError:
        # Mock pollers / SDK shims whose result() takes no timeout kwarg.
        resolved = result_attr()
    except Exception as xcpt:
        err_msg_lines = ["Azure long-running operation failed."]
        err_msg_lines.append("DESCRIPTION: {}".format(description))
        err_msg_lines.append("CAUSE: {}".format(xcpt))
        err_msg = os.linesep.join(err_msg_lines)
        raise AzureWaitTimeoutError(err_msg) from None

    rtnval = resolved
    return rtnval
