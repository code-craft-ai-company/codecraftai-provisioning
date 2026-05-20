"""
    .. module:: hetznererrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Hetzner Cloud venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class HetznerValidationError(ValueError):
    """
        Raised when the Hetzner provisioner refuses a spec at validate-time.
    """


class HetznerConflictError(RuntimeError):
    """
        Raised when the Hetzner provisioner finds drifted state that cannot
        be safely reconciled (e.g. an owner-label collision).
    """


class HetznerCapacityError(RuntimeError):
    """
        Raised when Hetzner reports insufficient capacity for the requested
        server type or location constraint.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
