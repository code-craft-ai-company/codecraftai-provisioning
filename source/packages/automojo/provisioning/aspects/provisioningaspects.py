"""
    .. module:: provisioningaspects
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: ProvisioningAspects — behaviour bundle for provisioning calls.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Optional


class ProvisioningAspects:
    """
        Aspect bundle controlling provisioning behaviour.

        Following the project Aspects pattern: callers pass behaviour as a
        single parameter rather than via decorators.
    """

    def __init__(self, *, dry_run: bool = False, confirm: bool = False,
                 runid: Optional[str] = None,
                 verify_timeout: float = 600.0,
                 verify_interval: float = 10.0,
                 lock_timeout_seconds: float = 30.0) -> None:
        """
            Construct a ProvisioningAspects bundle.

            :param dry_run: When True, the engine halts at the end of PLAN.
            :param confirm: When True, destroy is permitted.
            :param runid: Optional run identifier for state-persistence.
            :param verify_timeout: Total timeout for the VERIFY stage.
            :param verify_interval: Polling interval for VERIFY.
            :param lock_timeout_seconds: Index-file lock wait timeout.
        """
        self.dry_run: bool = dry_run
        self.confirm: bool = confirm
        self.runid: Optional[str] = runid
        self.verify_timeout: float = verify_timeout
        self.verify_interval: float = verify_interval
        self.lock_timeout_seconds: float = lock_timeout_seconds
        return
