"""
    .. module:: doerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the DigitalOcean venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class DoValidationError(ValueError):
    """
        Raised when the DigitalOcean provisioner refuses a spec at
        validate-time.
    """


class DoConflictError(RuntimeError):
    """
        Raised when the DigitalOcean provisioner finds drifted state that
        cannot be safely reconciled (e.g. an owner-tag collision).
    """


class DoCapacityError(RuntimeError):
    """
        Raised when DigitalOcean reports insufficient capacity for the
        requested size slug or region.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
