"""
    .. module:: nebiuserrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Nebius venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class NebiusValidationError(ValueError):
    """
        Raised when the Nebius provisioner refuses a spec at validate-time.
    """


class NebiusConflictError(RuntimeError):
    """
        Raised when the Nebius provisioner finds drifted state that cannot be
        safely reconciled (e.g. a run-id label collision).
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
