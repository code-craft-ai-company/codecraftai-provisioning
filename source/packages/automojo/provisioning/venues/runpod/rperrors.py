"""
    .. module:: rperrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the RunPod workload provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class RpValidationError(ValueError):
    """
        Raised when the RunPod workload provisioner refuses a spec at
        validate-time — for example a bucket / load-balancer / DNS / inter-pod
        interconnect resource RunPod cannot realise.
    """


class RpCapacityError(RuntimeError):
    """
        Raised when the requested GPU type + tier + region has no RunPod
        capacity.
    """


class ConfirmationRequiredError(RuntimeError):
    """
        Raised when a destroy / DELETE-bearing apply is invoked without
        ``aspects.confirm=True``.
    """


__all__ = ["RpValidationError", "RpCapacityError", "ConfirmationRequiredError"]
