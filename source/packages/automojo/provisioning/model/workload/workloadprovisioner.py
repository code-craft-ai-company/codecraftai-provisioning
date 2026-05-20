"""
    .. module:: workloadprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Abstract base class for workload venue provisioners.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from abc import ABC, abstractmethod
from typing import Any, List, Optional

from automojo.provisioning.model.workload.workloadvenue import WorkloadVenue


class WorkloadProvisioner(ABC):
    """
        Abstract base for workload venue provisioners.

        The five-verb lifecycle (validate / plan / apply / destroy / inventory)
        mirrors CloudProvisioner.  In Phase 1a only the signatures exist;
        Phase 2 fills in concrete bodies.  Optional ``cloud_provisioner``
        composition supports the self-hosted case (the engine drives cloud
        apply first and destroys in reverse).
    """

    def __init__(self, *, venue: WorkloadVenue,
                 cloud_provisioner: Optional[Any] = None) -> None:
        """
            Initialise the workload provisioner.

            :param venue: WorkloadVenue this provisioner operates on.
            :param cloud_provisioner: Optional CloudProvisioner composition
                                      for the self-hosted case.
        """
        self._venue: WorkloadVenue = venue
        self._cloud_provisioner: Optional[Any] = cloud_provisioner
        return

    @property
    def venue(self) -> WorkloadVenue:
        """
            Return the WorkloadVenue this provisioner is bound to.

            :returns: The WorkloadVenue.
        """
        rtnval = self._venue
        return rtnval

    @property
    def cloud_provisioner(self) -> Optional[Any]:
        """
            Return the optional composed CloudProvisioner, if any.

            :returns: The composed CloudProvisioner or None.
        """
        rtnval = self._cloud_provisioner
        return rtnval

    @abstractmethod
    def validate(self, *, aspects: Any) -> None:
        """
            Run shape + semantic validation across the declared workload
            resources.

            :param aspects: Aspects controlling validation behaviour.
        """
        raise NotImplementedError(
            "{}.validate is not implemented in Phase 1a.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def plan(self, *, aspects: Any) -> Any:
        """
            Produce a ProvisioningPlan for the declared resources.

            :param aspects: Aspects controlling planning behaviour.
        """
        raise NotImplementedError(
            "{}.plan is not implemented in Phase 1a.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def apply(self, *, aspects: Any) -> Any:
        """
            Apply the plan and produce a ProvisioningResult.

            :param aspects: Aspects controlling apply behaviour.
        """
        raise NotImplementedError(
            "{}.apply is not implemented in Phase 1a.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def destroy(self, *, aspects: Any) -> None:
        """
            Destroy previously-applied resources.

            :param aspects: Aspects controlling destroy behaviour.
        """
        raise NotImplementedError(
            "{}.destroy is not implemented in Phase 1a.".format(
                type(self).__name__
            )
        )

    @abstractmethod
    def inventory(self, *, aspects: Any) -> List[Any]:
        """
            Return an inventory of currently-known resources.

            :param aspects: Aspects controlling inventory behaviour.
        """
        raise NotImplementedError(
            "{}.inventory is not implemented in Phase 1a.".format(
                type(self).__name__
            )
        )
