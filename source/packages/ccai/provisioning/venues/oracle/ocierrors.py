"""
    .. module:: ocierrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Oracle Cloud venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class OciValidationError(ValueError):
    """
        Raised when the Oracle Cloud provisioner refuses a spec at
        validate-time.
    """


class OciConflictError(RuntimeError):
    """
        Raised when the Oracle Cloud provisioner finds drifted state that
        cannot be safely reconciled (e.g. an owner-tag collision).
    """


class OciCapacityError(RuntimeError):
    """
        Raised when OCI reports insufficient capacity for the requested
        shape or availability domain.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
