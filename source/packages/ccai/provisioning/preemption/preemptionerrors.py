"""
    .. module:: preemptionerrors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types raised by the preemption-handling machinery.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class ProvisioningPreemptionError(RuntimeError):
    """
        Raised when a `FAIL`-policy instance is reclaimed by its venue.

        Per the §7.6 plan decision the framework adopts a fail-loud default:
        a silent reacquisition during `apply` would mask capacity problems
        behind quietly-degraded reruns.  This error surfaces the preemption
        to the caller so the failure is visible rather than swallowed.
    """
