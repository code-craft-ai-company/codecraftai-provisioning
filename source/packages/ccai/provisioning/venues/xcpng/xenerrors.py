"""
    .. module:: xenerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the XCP-ng / XenServer venue
        provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class XenValidationError(ValueError):
    """
        Raised when the XCP-ng provisioner refuses a spec at validate-time.

        Examples are a requested object bucket, load balancer, or DNS
        record that XCP-ng cannot realise, a non-NONE HPC interconnect, or
        an image that resolves to neither a Template nor an importable XVA.
    """


class XenConflictError(RuntimeError):
    """
        Raised when an apply stage finds the venue in a state that conflicts
        with the spec — for example two VMs already carrying the deterministic
        run-scoped name_label.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
