"""
    .. module:: gcperrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the GCP venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class GcpValidationError(ValueError):
    """
        Raised when the GCP provisioner refuses a spec at validate-time.
    """


class GcpConflictError(RuntimeError):
    """
        Raised when the GCP provisioner finds drifted state that cannot be
        safely reconciled (e.g. an owner-label collision).
    """


class GcpCapacityError(RuntimeError):
    """
        Raised when GCP reports insufficient capacity for the requested SKU
        or placement constraint.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
