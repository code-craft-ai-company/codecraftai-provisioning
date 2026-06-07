"""
    .. module:: lverrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the libvirt venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class LvValidationError(ValueError):
    """
        Raised when the libvirt provisioner refuses a spec at
        validate-time — for example a requested object bucket, load
        balancer, DNS record, or HPC interconnect that libvirt cannot
        realise.
    """


class LvConflictError(RuntimeError):
    """
        Raised when a libvirt resource the run intends to create already
        exists on the host with an incompatible shape and cannot be
        reconciled idempotently.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
