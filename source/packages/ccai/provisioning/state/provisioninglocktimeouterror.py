"""
    .. module:: provisioninglocktimeouterror
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Lock-acquisition timeout error.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


class ProvisioningLockTimeoutError(TimeoutError):
    """
        Raised when the engine cannot acquire the index lock in time.
    """
