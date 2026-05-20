"""
    .. module:: runstatus
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RunStatus enum for persisted provisioning runs.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from enum import Enum


class RunStatus(Enum):
    """
        Terminal-and-progress status values for a persisted run.
    """

    STARTED = "started"
    APPLIED = "applied"
    FAILED = "failed"
    DESTROYED = "destroyed"
