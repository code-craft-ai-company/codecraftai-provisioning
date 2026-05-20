"""
    .. module:: provisioningverifyerror
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: ProvisioningVerifyError raised by the VERIFY stage.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


class ProvisioningVerifyError(RuntimeError):
    """
        Raised when an instance does not reach the expected state in time.
    """
