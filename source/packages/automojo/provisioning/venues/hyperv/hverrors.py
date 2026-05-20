"""
    .. module:: hverrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Hyper-V venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class HvValidationError(ValueError):
    """
        Raised when the Hyper-V provisioner refuses a spec at validate-time.
    """


class HvConflictError(RuntimeError):
    """
        Raised when the Hyper-V provisioner finds drifted state that cannot
        be safely reconciled (e.g. a run-id ownership collision).
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
