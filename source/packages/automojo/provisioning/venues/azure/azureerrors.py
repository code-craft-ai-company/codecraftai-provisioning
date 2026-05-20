"""
    .. module:: azureerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Azure venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class AzureValidationError(ValueError):
    """
        Raised when the Azure provisioner refuses a spec at validate-time.
    """


class AzureConflictError(RuntimeError):
    """
        Raised when the Azure provisioner finds drifted state that cannot be
        safely reconciled (e.g. an owner-tag collision).
    """


class AzureCapacityError(RuntimeError):
    """
        Raised when Azure reports insufficient capacity for the requested SKU
        or placement constraint.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
