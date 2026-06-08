"""
    .. module:: llerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Lambda Labs venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class LlValidationError(ValueError):
    """
        Raised when the Lambda Labs provisioner refuses a spec at
        validate-time — for example a requested object bucket, load
        balancer, or DNS record that Lambda Labs cannot realise.
    """


class LlCapacityError(RuntimeError):
    """
        Raised when Lambda Labs reports insufficient capacity for the
        requested instance type in the requested region.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
