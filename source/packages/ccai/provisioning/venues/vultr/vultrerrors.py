"""
    .. module:: vultrerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Vultr venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class VultrValidationError(ValueError):
    """
        Raised when the Vultr provisioner refuses a spec at validate-time.
    """


class VultrConflictError(RuntimeError):
    """
        Raised when the Vultr provisioner finds drifted state that cannot be
        safely reconciled (e.g. an owner-tag collision).
    """


class VultrApiError(RuntimeError):
    """
        Raised when a Vultr REST API call returns a non-success status.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
