"""
    .. module:: ntxerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Nutanix venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class NtxValidationError(ValueError):
    """
        Raised when the Nutanix provisioner refuses a spec at
        validate-time — for example a requested object bucket without
        Nutanix Objects configured, a load balancer, a DNS record, or an
        HPC interconnect that Prism Central cannot realise.
    """


class NtxConflictError(RuntimeError):
    """
        Raised when a Nutanix resource the run intends to create already
        exists on Prism Central with an incompatible shape and cannot be
        reconciled idempotently.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
