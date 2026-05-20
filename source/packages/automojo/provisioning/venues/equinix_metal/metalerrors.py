"""
    .. module:: metalerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the Equinix Metal venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class MetalValidationError(ValueError):
    """
        Raised when the Equinix Metal provisioner refuses a spec at
        validate-time.
    """


class MetalConflictError(RuntimeError):
    """
        Raised when the Equinix Metal provisioner finds drifted state that
        cannot be safely reconciled (e.g. an owner-tag collision).
    """


class MetalCapacityError(RuntimeError):
    """
        Raised when Equinix Metal reports that a plan is not available in the
        requested metro, or device provisioning fails to reach an active
        state inside the aspects-controlled timeout.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """
