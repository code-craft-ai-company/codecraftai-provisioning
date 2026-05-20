"""
    .. module:: crusoeibpartition
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CrusoeIbPartition — ensure-and-attach helper for InfiniBand
        placement groups shared by IB-grouped instances.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict

from automojo.restclient.crusoe.specs.crusoeplacementgroupspec import (
    CrusoePlacementGroupSpec
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.venues.crusoe.crusoeresolver import CrusoeResolver


def interconnect_group_of(*, instance: CloudInstance) -> str:
    """
        Resolve the InfiniBand grouping key for an instance.

        An explicit ``placement_group`` wins; otherwise instances that share
        an InfiniBand interconnect are grouped by their interconnect kind so
        a single IB partition spans the cohort.

        :param instance: The neutral CloudInstance.

        :returns: The grouping key string, or an empty string when the
            instance does not request InfiniBand placement.
    """
    if instance.placement_group is not None and len(instance.placement_group) > 0:
        rtnval = instance.placement_group
        return rtnval

    interconnect = instance.interconnect
    if interconnect is None:
        rtnval = ""
        return rtnval

    rtnval = "ib-{}".format(interconnect.kind.lower())
    return rtnval


class CrusoeIbPartition:
    """
        Ensures a Crusoe IB partition exists for an InfiniBand-grouped cohort
        of instances and supplies its identifier for instance attachment.
    """

    def __init__(self, *, client: Any, resolver: CrusoeResolver) -> None:
        """
            Construct a CrusoeIbPartition helper.

            :param client: The :class:`CrusoeClient` instance.
            :param resolver: The :class:`CrusoeResolver`.
        """
        self._client: Any = client
        self._resolver: CrusoeResolver = resolver
        return

    def ensure(self, *, project_id: str, group_key: str, run_id: str,
               aspects: Any) -> str:
        """
            Ensure an IB partition named for ``group_key`` exists, creating
            it idempotently and tagging it with the run id.

            :param project_id: The Crusoe project identifier.
            :param group_key: The InfiniBand grouping key.
            :param run_id: The provisioning run identifier.
            :param aspects: Aspects (unused for the interop calls; the interop
                client carries its own aspects).

            :returns: The Crusoe IB partition identifier.
        """
        partition_name = "{0}-{1}".format(run_id, group_key)
        labels: Dict[str, str] = {"automojo-run-id": run_id}

        spec = CrusoePlacementGroupSpec(name=partition_name,
                                        project_id=project_id,
                                        interconnect="infiniband",
                                        labels=labels)
        record = self._client.placement_groups.create(spec=spec)
        rtnval = record.placement_group_id
        return rtnval
