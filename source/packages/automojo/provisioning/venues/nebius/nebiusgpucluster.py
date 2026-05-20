"""
    .. module:: nebiusgpucluster
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Ensure-and-attach helper for Nebius GPU Clusters (IB-enabled
        placement groups).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.venues.nebius.nebiusspec import NebiusSpec


# Neutral interconnect kinds that map onto a Nebius GPU Cluster.
_IB_INTERCONNECT_KINDS = frozenset({
    "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR",
})


def _interconnect_group_of(*, instance: CloudInstance) -> Optional[str]:
    """
        Return the interconnect-group key for an instance, if any.

        The neutral model carries the grouping via ``placement_group``; an
        instance with an IB interconnect and a placement-group name shares a
        GPU Cluster with siblings carrying the same name.

        :param instance: The CloudInstance.

        :returns: The grouping key string, or ``None``.
    """
    if instance.interconnect is None:
        rtnval: Optional[str] = None
        return rtnval
    if instance.interconnect.kind not in _IB_INTERCONNECT_KINDS:
        rtnval = None
        return rtnval
    if instance.placement_group is None:
        rtnval = None
        return rtnval
    if len(instance.placement_group) == 0:
        rtnval = None
        return rtnval
    rtnval = instance.placement_group
    return rtnval


class NebiusGpuCluster:
    """
        Ensure-and-attach helper for the Nebius GPU Cluster (IB-enabled
        placement group).

        Instances that share an ``interconnect_group`` and carry an
        InfiniBand interconnect are placed into one GPU Cluster.  The cluster
        is looked up by name before create so re-applies are idempotent.
    """

    def __init__(self, *, client: Any, label_translator: Any) -> None:
        """
            Construct a NebiusGpuCluster helper.

            :param client: The NebiusClient (or mock).
            :param label_translator: A NebiusLabelTranslator.
        """
        self._client: Any = client
        self._label_translator: Any = label_translator
        return

    def grouped_instances(self, *, spec: NebiusSpec
                          ) -> Dict[str, List[CloudInstance]]:
        """
            Group spec instances by their interconnect-group key.

            :param spec: The NebiusSpec.

            :returns: A dict mapping group key to the instances in it.
        """
        groups: Dict[str, List[CloudInstance]] = {}
        for instance in spec.instances:
            group_key = _interconnect_group_of(instance=instance)
            if group_key is None:
                continue
            members = groups.setdefault(group_key, [])
            members.append(instance)
        rtnval = groups
        return rtnval

    def ensure_and_attach(self, *, spec: NebiusSpec, run_id: str,
                          aspects: Any) -> Dict[str, str]:
        """
            Ensure a GPU Cluster exists for every interconnect group and
            return a mapping from group key to the Nebius placement-group id.

            :param spec: The NebiusSpec.
            :param run_id: The provisioning run identifier.
            :param aspects: Aspects.

            :returns: A dict mapping interconnect-group key to Nebius
                placement-group id.
        """
        from automojo.interop.nebius.specs.nebiusplacementgroupspec import (
            NebiusPlacementGroupSpec
        )

        groups = self.grouped_instances(spec=spec)
        out: Dict[str, str] = {}
        for group_key, members in groups.items():
            cluster_name = "{}-{}".format(run_id, group_key)
            labels = self._label_translator.base_labels(
                run_id=run_id, resource_name=cluster_name,
                resource_kind="placement_group",
            )
            pg_spec = NebiusPlacementGroupSpec(
                parent_id=spec.parent_id, name=cluster_name,
                interconnect="infiniband", labels=labels,
            )
            placement_group = self._client.placement_groups.create(
                spec=pg_spec, aspects=aspects,
            )
            out[group_key] = placement_group.id
        rtnval = out
        return rtnval

    def placement_group_id_for(self, *, instance: CloudInstance,
                               group_ids: Dict[str, str]) -> Optional[str]:
        """
            Return the GPU Cluster id an instance should be placed into.

            :param instance: The CloudInstance.
            :param group_ids: The group-key → placement-group-id map.

            :returns: The placement-group id, or ``None`` when the instance
                is not part of an IB group.
        """
        group_key = _interconnect_group_of(instance=instance)
        if group_key is None:
            rtnval: Optional[str] = None
            return rtnval
        rtnval = group_ids.get(group_key, None)
        return rtnval
