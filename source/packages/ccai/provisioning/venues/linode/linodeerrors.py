"""
    .. module:: linodeerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Linode venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class LinodeValidationError(ValueError):
    """
        Raised when the Linode provisioner refuses a spec at validate-time.
    """


class LinodeConflictError(RuntimeError):
    """
        Raised when the Linode provisioner finds drifted state that cannot
        be safely reconciled (e.g. an owner-tag collision).
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
