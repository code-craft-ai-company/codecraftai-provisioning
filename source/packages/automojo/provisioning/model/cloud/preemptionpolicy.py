"""
    .. module:: preemptionpolicy
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Enum describing how the framework reacts to instance preemption.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from enum import Enum


class PreemptionPolicy(str, Enum):
    """
        Policy governing how the framework reacts when a venue reclaims an
        instance.

        - FAIL: raise an error; the default.  No silent reacquisition.
        - REACQUIRE: recreate the instance with the same spec.
        - BEST_EFFORT: drop the instance from inventory and continue.
    """
    FAIL = "FAIL"
    REACQUIRE = "REACQUIRE"
    BEST_EFFORT = "BEST_EFFORT"
