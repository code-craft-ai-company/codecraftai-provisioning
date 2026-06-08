"""
    .. module:: nebiusinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NebiusInventory — enumerate run-id-labelled Nebius resources.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, List

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)


class NebiusInventory:
    """
        Enumerator for run-id-labelled Nebius resources.

        Lists VPCs, subnets, security groups, placement groups, VMs, and
        disks owned by a run and emits :class:`ProvisionedResource` records.
    """

    def __init__(self, *, client: Any, label_translator: Any) -> None:
        """
            Construct a NebiusInventory.

            :param client: The NebiusClient (or mock).
            :param label_translator: A NebiusLabelTranslator.
        """
        self._client: Any = client
        self._labels: Any = label_translator
        return

    @staticmethod
    def _is_owned(*, record: Any, run_id: str) -> bool:
        """
            Return whether a record carries the run-id ownership label.

            :param record: A typed Nebius record.
            :param run_id: The provisioning run identifier.

            :returns: ``True`` when the record is owned by the run.
        """
        labels = getattr(record, "labels", None)
        if labels is None:
            rtnval = False
            return rtnval
        rtnval = (labels.get("codecraftai-run-id", None) == run_id)
        return rtnval

    @staticmethod
    def _name_of(*, record: Any) -> str:
        """
            Return the neutral resource name carried in a record's labels.

            :param record: A typed Nebius record.

            :returns: The neutral resource name, or the record's own name.
        """
        labels = getattr(record, "labels", None)
        if labels is not None:
            name = labels.get("codecraftai-resource-name", None)
            if name is not None:
                rtnval = name
                return rtnval
        rtnval = getattr(record, "name", "")
        return rtnval

    def list_run(self, *, spec: Any, run_id: str,
                 aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate every run-id-labelled resource for the run.

            :param spec: The NebiusSpec.
            :param run_id: The provisioning run identifier.
            :param aspects: Aspects.

            :returns: A list of ProvisionedResource records.
        """
        parent_id = spec.parent_id
        out: List[ProvisionedResource] = []

        for vpc in self._client.vpcs.list(project_id=parent_id,
                                          aspects=aspects):
            if self._is_owned(record=vpc, run_id=run_id):
                out.append(ProvisionedResource(
                    kind="network", name=self._name_of(record=vpc),
                    venue_id=vpc.id,
                    attributes={"vpc_id": vpc.id},
                ))

        for vpc in self._client.vpcs.list(project_id=parent_id,
                                          aspects=aspects):
            if not self._is_owned(record=vpc, run_id=run_id):
                continue
            for subnet in self._client.subnets.list(vpc_id=vpc.id,
                                                    aspects=aspects):
                if self._is_owned(record=subnet, run_id=run_id):
                    out.append(ProvisionedResource(
                        kind="subnet", name=self._name_of(record=subnet),
                        venue_id=subnet.id,
                        attributes={"subnet_id": subnet.id},
                    ))
            for sg in self._client.security_groups.list(vpc_id=vpc.id,
                                                        aspects=aspects):
                if self._is_owned(record=sg, run_id=run_id):
                    out.append(ProvisionedResource(
                        kind="sg", name=self._name_of(record=sg),
                        venue_id=sg.id,
                        attributes={"sg_id": sg.id},
                    ))

        for pg in self._client.placement_groups.list(project_id=parent_id,
                                                     aspects=aspects):
            if self._is_owned(record=pg, run_id=run_id):
                out.append(ProvisionedResource(
                    kind="placement_group", name=self._name_of(record=pg),
                    venue_id=pg.id,
                    attributes={"placement_group_id": pg.id},
                ))

        for vm in self._client.vms.list(project_id=parent_id,
                                        aspects=aspects):
            if self._is_owned(record=vm, run_id=run_id):
                out.append(ProvisionedResource(
                    kind="instance", name=self._name_of(record=vm),
                    venue_id=vm.id,
                    attributes={"vm_id": vm.id},
                ))

        for disk in self._client.disks.list(project_id=parent_id,
                                            aspects=aspects):
            if self._is_owned(record=disk, run_id=run_id):
                out.append(ProvisionedResource(
                    kind="volume", name=self._name_of(record=disk),
                    venue_id=disk.id,
                    attributes={"disk_id": disk.id},
                ))

        rtnval = out
        return rtnval
