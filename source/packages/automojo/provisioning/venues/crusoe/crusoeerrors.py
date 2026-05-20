"""
    .. module:: crusoeerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Crusoe venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class CrusoeValidationError(ValueError):
    """
        Raised when the Crusoe provisioner refuses a spec at validate-time.
    """


class CrusoeConflictError(RuntimeError):
    """
        Raised when the Crusoe provisioner finds drifted state that cannot be
        safely reconciled (e.g. an owner-label collision).
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
