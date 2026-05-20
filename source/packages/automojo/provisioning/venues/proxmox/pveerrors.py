"""
    .. module:: pveerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Proxmox VE venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class PveValidationError(ValueError):
    """
        Raised when the Proxmox VE provisioner refuses a spec at
        validate-time — for example a requested object bucket, load
        balancer, or HPC interconnect that Proxmox cannot realise, or a
        VM whose target node / storage pool / image cannot be resolved.
    """


class PveConflictError(RuntimeError):
    """
        Raised when a Proxmox VE apply hits a venue-side conflict — for
        example a requested VMID that is already owned by a foreign run.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
