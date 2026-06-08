"""
    .. module:: vserrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the VSphere venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class VsValidationError(ValueError):
    """
        Raised when the VSphere provisioner refuses a spec at validate-time.
    """


class VsConflictError(RuntimeError):
    """
        Raised when the VSphere provisioner finds drifted state that cannot
        be safely reconciled (e.g. an owner-tag collision).
    """


class VsCapacityError(RuntimeError):
    """
        Raised when vSphere reports no datastore or host able to satisfy the
        requested placement or size constraint.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
