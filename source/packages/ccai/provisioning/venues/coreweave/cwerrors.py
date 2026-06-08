"""
    .. module:: cwerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the CoreWeave workload provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class CwValidationError(ValueError):
    """
        Raised when the CoreWeave workload provisioner refuses a spec at
        validate-time.
    """


class CwKubeconfigError(RuntimeError):
    """
        Raised when the CoreWeave provisioner cannot acquire a usable
        kubeconfig — typically a missing or mis-typed credential.
    """


class CwConflictError(RuntimeError):
    """
        Raised when the CoreWeave provisioner finds drifted state that
        cannot be safely reconciled.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
