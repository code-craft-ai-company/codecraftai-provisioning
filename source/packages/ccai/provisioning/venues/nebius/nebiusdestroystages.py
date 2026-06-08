"""
    .. module:: nebiusdestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NebiusDestroyStages — reverse-order teardown for a NebiusSpec.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.venues.vpncleanup import delete_vpn_device


class NebiusDestroyStages:
    """
        Reverse-order teardown for a NebiusSpec.

        Destroy reverses the apply order: Instances → Disks → GPU Cluster →
        SSH keys → Security Groups → Subnets → VPCs.  Mount targets attached
        to caller-owned filesystems are removed; the filesystems themselves
        are attach-only and left intact.  After instances are terminated the
        VPN control plane (when supplied) de-registers each joined device.
    """

    def __init__(self, *, client: Any, vpn_control_plane: Any = None
                 ) -> None:
        """
            Construct a NebiusDestroyStages.

            :param client: The NebiusClient (or mock).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
        """
        self._client: Any = client
        self._vpn_control_plane: Any = vpn_control_plane
        return

    @staticmethod
    def _is_owned(*, record: Any, run_id: str) -> bool:
        """
            Return whether a Nebius record carries the run-id ownership
            label.

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

    def destroy(self, *, spec: Any, run_id: str,
                vpn_records: List[Dict[str, Any]], aspects: Any) -> None:
        """
            Tear down every owned resource in reverse dependency order.

            :param spec: The NebiusSpec.
            :param run_id: The provisioning run identifier.
            :param vpn_records: VPN device records captured during apply.
            :param aspects: Aspects.

            :returns: ``None``.
        """
        parent_id = spec.parent_id

        # 1. Instances — terminate every owned VM, then de-register devices.
        existing_vms = self._client.vms.list(project_id=parent_id,
                                             aspects=aspects)
        terminated_vm_ids: List[str] = []
        for vm in existing_vms:
            if self._is_owned(record=vm, run_id=run_id):
                self._client.vms.terminate(vm_id=vm.id, aspects=aspects)
                terminated_vm_ids.append(vm.id)

        # 2. VPN control-plane device cleanup.
        if self._vpn_control_plane is not None:
            for record in vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(
                    vpn_control_plane=self._vpn_control_plane,
                    device_id=device_id, aspects=aspects)

        # 3. Disks.
        existing_disks = self._client.disks.list(project_id=parent_id,
                                                 aspects=aspects)
        for disk in existing_disks:
            if self._is_owned(record=disk, run_id=run_id):
                self._client.disks.delete(disk_id=disk.id, aspects=aspects)

        # 4. GPU Clusters (placement groups).
        existing_pgs = self._client.placement_groups.list(
            project_id=parent_id, aspects=aspects,
        )
        for pg in existing_pgs:
            if self._is_owned(record=pg, run_id=run_id):
                self._client.placement_groups.delete(
                    placement_group_id=pg.id, aspects=aspects,
                )

        # 5. SSH keys.
        for kp in spec.keypairs:
            existing_keys = self._client.ssh_keys.list(aspects=aspects)
            for key in existing_keys:
                if key.name == kp.name:
                    self._client.ssh_keys.delete(key_id=key.id,
                                                 aspects=aspects)

        # 6. Security groups + 7. Subnets — scoped per owned VPC.
        existing_vpcs = self._client.vpcs.list(project_id=parent_id,
                                               aspects=aspects)
        owned_vpcs = [vpc for vpc in existing_vpcs
                      if self._is_owned(record=vpc, run_id=run_id)]

        for vpc in owned_vpcs:
            existing_sgs = self._client.security_groups.list(
                vpc_id=vpc.id, aspects=aspects,
            )
            for sg in existing_sgs:
                if self._is_owned(record=sg, run_id=run_id):
                    self._client.security_groups.delete(sg_id=sg.id,
                                                        aspects=aspects)

            existing_subnets = self._client.subnets.list(vpc_id=vpc.id,
                                                         aspects=aspects)
            for subnet in existing_subnets:
                if self._is_owned(record=subnet, run_id=run_id):
                    self._client.subnets.delete(subnet_id=subnet.id,
                                                aspects=aspects)

        # 8. VPCs.
        for vpc in owned_vpcs:
            self._client.vpcs.delete(vpc_id=vpc.id, aspects=aspects)

        return
