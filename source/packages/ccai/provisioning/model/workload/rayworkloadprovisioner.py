"""
    .. module:: rayworkloadprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RayWorkloadProvisioner — reserved-but-not-implemented
        WorkloadProvisioner for the RAY venue kind.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, List

from ccai.provisioning.model.workload.workloadprovisioner import (
    WorkloadProvisioner
)


# Stable issue-tracker pointer cited by every not-implemented message.  Per
# PLAN §7.6 the Ray enumerant lands day one but is not implemented in v1;
# adding it later is purely additive against the locked public surface.
RAY_TRACKING_ISSUE = "ccai/codecraftai-provisioning#WORKLOAD-RAY-V2"


def _ray_not_implemented(*, verb: str) -> NotImplementedError:
    """
        Build the stable :class:`NotImplementedError` for a Ray verb.

        :param verb: The lifecycle verb name.

        :returns: A :class:`NotImplementedError` with a stable message.
    """
    err_msg_lines = ["RayWorkloadProvisioner.{} is not implemented in "
                     "v1.".format(verb)]
    err_msg_lines.append("Per PLAN-VPN-AND-CLOUD-PROVISIONING.md §7.6 the "
                         "RAY venue kind ships as an enumerant only; "
                         "Kubernetes is the sole v1 implementation.")
    err_msg_lines.append("TRACKING ISSUE: {}".format(RAY_TRACKING_ISSUE))
    err_msg = os.linesep.join(err_msg_lines)
    rtnval = NotImplementedError(err_msg)
    return rtnval


class RayWorkloadProvisioner(WorkloadProvisioner):
    """
        Reserved-but-not-implemented :class:`WorkloadProvisioner` for the
        ``RAY`` workload-venue kind.

        Per PLAN §7.6 the RAY enumerant ships day one so the public surface
        is locked, but every lifecycle verb raises
        :class:`NotImplementedError` with a pointer to the tracking issue.
        A future v2 implementation is purely additive.
    """

    def validate(self, *, aspects: Any = None) -> Any:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _ray_not_implemented(verb="validate")

    def plan(self, *, aspects: Any = None) -> Any:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _ray_not_implemented(verb="plan")

    def apply(self, *, aspects: Any = None) -> Any:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _ray_not_implemented(verb="apply")

    def destroy(self, *, aspects: Any = None) -> None:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _ray_not_implemented(verb="destroy")

    def inventory(self, *, aspects: Any = None) -> List[Any]:
        """
            Not implemented in v1.

            :param aspects: Behaviour control (ignored).

            :raises: NotImplementedError
        """
        raise _ray_not_implemented(verb="inventory")


__all__ = ["RayWorkloadProvisioner", "RAY_TRACKING_ISSUE"]
