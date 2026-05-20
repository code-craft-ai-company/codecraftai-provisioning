"""
    .. module:: nebiusapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NebiusApplyStages — staged idempotent apply for a NebiusSpec.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.nebius.nebiusgpucluster import (
    NebiusGpuCluster
)
from automojo.provisioning.venues.nebius.nebiusspec import NebiusSpec


class NebiusApplyStages:
    """
        Staged idempotent apply for a NebiusSpec.

        The apply order is VPC → Subnet → Security Group → SSH keys → GPU
        Cluster → Instances → Disks → File-storage attach → Object Storage
        bucket.  Every stage reads existing run-id-labelled resources before
        creating so re-applies make no mutating calls.
    """

    def __init__(self, *, client: Any, label_translator: Any,
                 resolver: Any, user_data_renderer: Any) -> None:
        """
            Construct a NebiusApplyStages.

            :param client: The NebiusClient (or mock).
            :param label_translator: A NebiusLabelTranslator.
            :param resolver: A NebiusResolver.
            :param user_data_renderer: A NebiusUserDataRenderer.
        """
        self._client: Any = client
        self._labels: Any = label_translator
        self._resolver: Any = resolver
        self._user_data: Any = user_data_renderer
        self._gpu_cluster: NebiusGpuCluster = NebiusGpuCluster(
            client=client, label_translator=label_translator,
        )
        return

    def _find_owned(self, *, records: List[Any], run_id: str,
                    resource_name: str) -> Optional[Any]:
        """
            Find an owned record by run-id and resource-name labels.

            :param records: A list of typed Nebius records.
            :param run_id: The provisioning run identifier.
            :param resource_name: The neutral resource name.

            :returns: The matching record, or ``None``.
        """
        rtnval: Optional[Any] = None
        for record in records:
            labels = getattr(record, "labels", None)
            if labels is None:
                continue
            if labels.get("automojo-run-id", None) != run_id:
                continue
            if labels.get("automojo-resource-name", None) != resource_name:
                continue
            rtnval = record
            break
        return rtnval

    def apply_network_and_security(self, *, spec: NebiusSpec, run_id: str,
                                   aspects: Any) -> Dict[str, Any]:
        """
            Apply the VPC, subnet, security-group, and SSH-key stages.

            :param spec: The NebiusSpec.
            :param run_id: The provisioning run identifier.
            :param aspects: Aspects.

            :returns: A dict carrying ``created``, ``skipped``, and the
                resolved ``vpc``, ``subnet``, ``sg``, ``keypair`` id maps.
        """
        from automojo.restclient.nebius.specs.nebiusvpcspec import NebiusVpcSpec
        from automojo.restclient.nebius.specs.nebiussubnetspec import (
            NebiusSubnetSpec
        )
        from automojo.restclient.nebius.specs.nebiussecuritygroupspec import (
            NebiusSecurityGroupSpec
        )

        created: List[ProvisionedResource] = []
        skipped: List[str] = []

        vpc_ids: Dict[str, str] = {}
        existing_vpcs = self._client.vpcs.list(project_id=spec.parent_id,
                                               aspects=aspects)
        for net in spec.networks:
            existed = self._find_owned(records=existing_vpcs, run_id=run_id,
                                       resource_name=net.name) is not None
            labels = self._labels.base_labels(
                run_id=run_id, resource_name=net.name,
                resource_kind="network", extra=list(net.tags),
            )
            vpc_spec = NebiusVpcSpec(parent_id=spec.parent_id, name=net.name,
                                     ipv4_cidr_block=net.cidr, labels=labels)
            vpc = self._client.vpcs.create(spec=vpc_spec, aspects=aspects)
            vpc_ids[net.name] = vpc.id
            if existed:
                skipped.append(net.name)
            else:
                created.append(ProvisionedResource(
                    kind="network", name=net.name, venue_id=vpc.id,
                    attributes={"vpc_id": vpc.id, "cidr": net.cidr},
                ))

        subnet_ids: Dict[str, str] = {}
        for subnet in spec.subnets:
            vpc_id = vpc_ids.get(subnet.network, None)
            if vpc_id is None:
                continue
            existing_subnets = self._client.subnets.list(vpc_id=vpc_id,
                                                         aspects=aspects)
            existed = self._find_owned(records=existing_subnets,
                                       run_id=run_id,
                                       resource_name=subnet.name) is not None
            labels = self._labels.base_labels(
                run_id=run_id, resource_name=subnet.name,
                resource_kind="subnet", extra=list(subnet.tags),
            )
            subnet_spec = NebiusSubnetSpec(
                vpc_id=vpc_id, name=subnet.name,
                ipv4_cidr_block=subnet.cidr, zone_id=subnet.zone,
                labels=labels,
            )
            created_subnet = self._client.subnets.create(spec=subnet_spec,
                                                         aspects=aspects)
            subnet_ids[subnet.name] = created_subnet.id
            if existed:
                skipped.append(subnet.name)
            else:
                created.append(ProvisionedResource(
                    kind="subnet", name=subnet.name,
                    venue_id=created_subnet.id,
                    attributes={"subnet_id": created_subnet.id,
                                "cidr": subnet.cidr},
                ))

        sg_ids: Dict[str, str] = {}
        for sg in spec.security_groups:
            vpc_id = vpc_ids.get(sg.network, None)
            if vpc_id is None:
                continue
            existing_sgs = self._client.security_groups.list(vpc_id=vpc_id,
                                                             aspects=aspects)
            existed = self._find_owned(records=existing_sgs, run_id=run_id,
                                       resource_name=sg.name) is not None
            labels = self._labels.base_labels(
                run_id=run_id, resource_name=sg.name,
                resource_kind="security_group", extra=list(sg.tags),
            )
            sg_spec = NebiusSecurityGroupSpec(
                vpc_id=vpc_id, name=sg.name, labels=labels,
            )
            created_sg = self._client.security_groups.create(spec=sg_spec,
                                                             aspects=aspects)
            sg_ids[sg.name] = created_sg.id
            if existed:
                skipped.append(sg.name)
            else:
                created.append(ProvisionedResource(
                    kind="sg", name=sg.name, venue_id=created_sg.id,
                    attributes={"sg_id": created_sg.id},
                ))

        keypair_ids: Dict[str, str] = {}
        existing_keys = self._client.ssh_keys.list(aspects=aspects)
        for kp in spec.keypairs:
            existed = False
            for key in existing_keys:
                if key.name == kp.name:
                    existed = True
                    break
            registered = self._client.ssh_keys.register(
                name=kp.name, public_key=kp.public_key_material,
                aspects=aspects,
            )
            keypair_ids[kp.name] = registered.id
            if existed:
                skipped.append(kp.name)
            else:
                created.append(ProvisionedResource(
                    kind="keypair", name=kp.name, venue_id=registered.id,
                    attributes={"ssh_key_id": registered.id},
                ))

        rtnval = {
            "created": created,
            "skipped": skipped,
            "vpc": vpc_ids,
            "subnet": subnet_ids,
            "sg": sg_ids,
            "keypair": keypair_ids,
        }
        return rtnval

    def apply_instances_and_disks(self, *, spec: NebiusSpec, run_id: str,
                                  network_state: Dict[str, Any],
                                  authkey_for: Any,
                                  aspects: Any) -> Dict[str, Any]:
        """
            Apply the GPU Cluster, instance, and disk stages.

            :param spec: The NebiusSpec.
            :param run_id: The provisioning run identifier.
            :param network_state: The dict returned by
                :meth:`apply_network_and_security`.
            :param authkey_for: Callable mapping an instance name to a VPN
                auth key (or ``None``).
            :param aspects: Aspects.

            :returns: A dict carrying ``created``, ``skipped``, and the
                ``vpn_records`` list.
        """
        from automojo.restclient.nebius.specs.nebiusvmspec import NebiusVmSpec
        from automojo.restclient.nebius.specs.nebiusdiskspec import (
            NebiusDiskSpec
        )

        created: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []

        gpu_group_ids = self._gpu_cluster.ensure_and_attach(
            spec=spec, run_id=run_id, aspects=aspects,
        )

        subnet_ids = network_state["subnet"]
        keypair_ids = network_state["keypair"]

        existing_vms = self._client.vms.list(project_id=spec.parent_id,
                                             aspects=aspects)
        instance_ids: Dict[str, str] = {}
        for inst in spec.instances:
            existed = self._find_owned(records=existing_vms, run_id=run_id,
                                       resource_name=inst.name) is not None

            subnet_id = subnet_ids.get(inst.subnet, None)
            if subnet_id is None:
                continue

            preset = self._resolver.size_to_preset(
                size_hint=inst.size, accelerators=inst.accelerators,
                interconnect=inst.interconnect,
            )
            platform = self._resolver.platform_for_preset(preset=preset)
            image_id = self._resolver.image_to_id(
                family=inst.image.family, version=inst.image.version,
                architecture=inst.image.architecture,
            )

            ssh_key_ids: List[str] = []
            if inst.keypair is not None:
                key_id = keypair_ids.get(inst.keypair, None)
                if key_id is not None:
                    ssh_key_ids.append(key_id)

            metadata: Dict[str, Any] = {}
            authkey = authkey_for(inst.name)
            user_data = self._user_data.render(instance=inst,
                                               authkey=authkey)
            if user_data is not None:
                metadata["user-data"] = user_data

            placement_group_id = self._gpu_cluster.placement_group_id_for(
                instance=inst, group_ids=gpu_group_ids,
            )

            labels = self._labels.base_labels(
                run_id=run_id, resource_name=inst.name,
                resource_kind="vm", extra=list(inst.tags),
            )
            vm_spec = NebiusVmSpec(
                parent_id=spec.parent_id, name=inst.name, platform=platform,
                preset=preset, subnet_id=subnet_id, image_id=image_id,
                region_id=spec.region_id, ssh_key_ids=ssh_key_ids,
                placement_group_id=placement_group_id, metadata=metadata,
                labels=labels,
            )
            vm, handle = self._client.vms.launch(spec=vm_spec,
                                                 aspects=aspects)
            instance_ids[inst.name] = vm.id

            if existed:
                skipped.append(inst.name)
            else:
                created.append(ProvisionedResource(
                    kind="instance", name=inst.name, venue_id=vm.id,
                    attributes={"vm_id": vm.id, "platform": platform,
                                "preset": preset,
                                "has_user_data": "user-data" in metadata},
                ))
                if inst.vpn_join is not None:
                    vpn_records.append({
                        "instance_name": inst.name,
                        "instance_id": vm.id,
                        "vpn_provider": inst.vpn_join.provider,
                        "vpn_device_id": None,
                    })

        for vol in spec.volumes:
            existing_disks = self._client.disks.list(
                project_id=spec.parent_id, aspects=aspects,
            )
            existed = self._find_owned(records=existing_disks, run_id=run_id,
                                       resource_name=vol.name) is not None
            if existed:
                skipped.append(vol.name)
                continue

            labels = self._labels.base_labels(
                run_id=run_id, resource_name=vol.name,
                resource_kind="disk", extra=list(vol.tags),
            )
            disk_spec = NebiusDiskSpec(
                parent_id=spec.parent_id, name=vol.name,
                size_bytes=int(vol.size_gb) * 1_000_000_000,
                type=vol.type, labels=labels,
            )
            disk, disk_handle = self._client.disks.create(spec=disk_spec,
                                                          aspects=aspects)
            if vol.attached_to is not None:
                target_id = instance_ids.get(vol.attached_to, None)
                if target_id is not None:
                    self._client.disks.attach(disk_id=disk.id,
                                              instance_id=target_id,
                                              aspects=aspects)
            created.append(ProvisionedResource(
                kind="volume", name=vol.name, venue_id=disk.id,
                attributes={"disk_id": disk.id, "size_gb": vol.size_gb},
            ))

        rtnval = {
            "created": created,
            "skipped": skipped,
            "vpn_records": vpn_records,
            "instance": instance_ids,
        }
        return rtnval

    def apply_storage_and_dns(self, *, spec: NebiusSpec, run_id: str,
                              compute_state: Dict[str, Any],
                              aspects: Any) -> Dict[str, Any]:
        """
            Apply the shared-filesystem attach stage.

            Shared filesystems are attach-only in v1 — an existing Nebius
            native filesystem is looked up by ``existing_id`` and a mount
            target is created per requested subnet.  Object Storage is not
            exposed by the v1 Nebius interop client; buckets are rejected at
            validate-time.

            :param spec: The NebiusSpec.
            :param run_id: The provisioning run identifier.
            :param compute_state: The dict returned by
                :meth:`apply_instances_and_disks`.
            :param aspects: Aspects.

            :returns: A dict carrying ``created`` and ``skipped``.
        """
        from automojo.restclient.nebius.specs.nebiusmounttargetspec import (
            NebiusMountTargetSpec
        )

        created: List[ProvisionedResource] = []
        skipped: List[str] = []

        subnet_ids = compute_state.get("subnet", {})

        for sfs in spec.shared_filesystems:
            existing_fs = self._client.filesystems.get(
                filesystem_id=sfs.existing_id, aspects=aspects,
            )
            mount_targets = sfs.mount_targets if sfs.mount_targets is not None else []
            for mount in mount_targets:
                subnet_ref = mount.get("subnet", "") if isinstance(mount, dict) else getattr(mount, "subnet", "")
                subnet_id = subnet_ids.get(subnet_ref, None)
                if subnet_id is None:
                    continue
                mount_path = mount.get("mount_path", None) if isinstance(mount, dict) else getattr(mount, "mount_path", None)
                mt_spec = NebiusMountTargetSpec(
                    filesystem_id=existing_fs.id, subnet_id=subnet_id,
                    mount_path=mount_path,
                )
                self._client.mount_targets.create(spec=mt_spec,
                                                  aspects=aspects)
            created.append(ProvisionedResource(
                kind="shared_filesystem", name=sfs.name,
                venue_id=existing_fs.id,
                attributes={"filesystem_id": existing_fs.id,
                            "attach_only": True},
            ))

        rtnval = {"created": created, "skipped": skipped}
        return rtnval
