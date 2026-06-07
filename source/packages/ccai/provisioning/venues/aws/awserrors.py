"""
    .. module:: awserrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the AWS venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class AwsValidationError(ValueError):
    """
        Raised when the AWS provisioner refuses a spec at validate-time.
    """


class AwsConflictError(RuntimeError):
    """
        Raised when the AWS provisioner finds drifted state that cannot be
        safely reconciled (e.g. an owner-tag collision).
    """


class AwsCapacityError(RuntimeError):
    """
        Raised when AWS reports insufficient capacity for the requested SKU
        or placement constraint.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
