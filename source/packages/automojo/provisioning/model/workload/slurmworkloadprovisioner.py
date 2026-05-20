"""
    .. module:: slurmworkloadprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: SlurmWorkloadProvisioner — reserved-but-not-implemented
        WorkloadProvisioner for the SLURM venue kind.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, List

from automojo.provisioning.model.workload.workloadprovisioner import (
    WorkloadProvisioner
)


# Stable issue-tracker pointer cited by every not-implemented message.  Per
# PLAN §7.6 the Slurm enumerant lands day one but is not implemented in v1;
# adding it later is purely additive against the locked public surface.
SLURM_TRACKING_ISSUE = "automojo/automojo-provisioning#WORKLOAD-SLURM-V2"


def _slurm_not_implemented(*, verb: str) -> NotImplementedError:
    """
        Build the stable :class:`NotImplementedError` for a Slurm verb.

        :param verb: The lifecycle verb name.

        :returns: A :class:`NotImplementedError` with a stable message.
    """
    err_msg_lines = ["SlurmWorkloadProvisioner.{} is not implemented in "
                     "v1.".format(verb)]
    err_msg_lines.append("Per PLAN-VPN-AND-CLOUD-PROVISIONING.md §7.6 the "
                         "SLURM venue kind ships as an enumerant only; "
                         "Kubernetes is the sole v1 implementation.")
    err_msg_lines.append("TRACKING ISSUE: {}".format(SLURM_TRACKING_ISSUE))
    err_msg = os.linesep.join(err_msg_lines)
    rtnval = NotImplementedError(err_msg)
    return rtnval


class SlurmWorkloadProvisioner(WorkloadProvisioner):
    """
        Reserved-but-not-implemented :class:`WorkloadProvisioner` for the
        ``SLURM`` workload-venue kind.

        Per PLAN §7.6 the SLURM enumerant ships day one so the public
        surface is locked, but every lifecycle verb raises
        :class:`NotImplementedError` with a pointer to the tracking issue.
        A future v2 implementation is purely additive — no caller signature
        changes.
    """

    def validate(self, *, aspects: Any = None) -> Any:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _slurm_not_implemented(verb="validate")

    def plan(self, *, aspects: Any = None) -> Any:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _slurm_not_implemented(verb="plan")

    def apply(self, *, aspects: Any = None) -> Any:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _slurm_not_implemented(verb="apply")

    def destroy(self, *, aspects: Any = None) -> None:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _slurm_not_implemented(verb="destroy")

    def inventory(self, *, aspects: Any = None) -> List[Any]:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _slurm_not_implemented(verb="inventory")


__all__ = ["SlurmWorkloadProvisioner", "SLURM_TRACKING_ISSUE"]
