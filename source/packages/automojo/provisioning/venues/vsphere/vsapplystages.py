"""
    .. module:: vsapplystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VsApplyStages — staged, idempotent apply for the VSphere venue
        (port groups -> image resolution -> VM -> disks -> guest
        customisation -> power-on).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.vsphere.vsguestcustomrenderer import (
    VsGuestCustomRenderer
)
from automojo.provisioning.venues.vsphere.vsresolver import (
    LibraryItemRef, VsResolver
)
from automojo.provisioning.venues.vsphere.vspherevenueconfig import (
    VSphereVenueConfig
)
from automojo.provisioning.venues.vsphere.vstagtranslator import (
    base_resource_tags
)


class VsApplyStages:
    """
        Idempotent apply stages for the VSphere venue.

        Each stage performs read-before-create against the venue inventory,
        keyed by the run-id tag; an already-present resource is reused and
        reported as skipped.
    """

    def __init__(self, *, ops: Any, config: VSphereVenueConfig,
                 resolver: VsResolver,
                 guest_renderer: VsGuestCustomRenderer) -> None:
        """
            Construct a VsApplyStages.

            :param ops: A VSphereOps facade.
            :param config: The VSphereVenueConfig.
            :param resolver: A VsResolver.
            :param guest_renderer: A VsGuestCustomRenderer.
        """
        self._ops: Any = ops
        self._config: VSphereVenueConfig = config
        self._resolver: VsResolver = resolver
        self._guest_renderer: VsGuestCustomRenderer = guest_renderer
        return

    def apply_networking(self, *, spec: Any, run_id: str, aspects: Any,
                         created: List[ProvisionedResource],
                         skipped: List[str]) -> Dict[str, ProvisionedResource]:
        """
            Create distributed port groups for each CloudSubnet.

            Each CloudNetwork maps to a distributed virtual switch (reused by
            name); each CloudSubnet maps to a distributed port group carrying
            the subnet's VLAN id.

            :param spec: The VSphereSpec.
            :param run_id: Run identifier.
            :param aspects: Behaviour controls.
            :param created: Output list of newly created resources.
            :param skipped: Output list of skipped resource names.

            :returns: A mapping ``subnet_name -> ProvisionedResource``.
        """
        existing_networks = self._ops.list_networks(aspects=aspects)
        existing_names = set()
        for net in existing_networks:
            net_name = getattr(net, "name", None)
            if net_name is not None:
                existing_names.add(net_name)

        subnet_state: Dict[str, ProvisionedResource] = {}
        vlan_map = self._config.subnet_vlan_ids

        for subnet in spec.subnets:
            pg_name = "{}-{}".format(run_id, subnet.name)
            switch = subnet.network
            vlan_id = vlan_map.get(subnet.name, 0)

            if pg_name in existing_names:
                skipped.append(subnet.name)
                resource = ProvisionedResource(
                    kind="subnet", name=subnet.name, venue_id=pg_name,
                    attributes={"port_group": pg_name, "vlan_id": vlan_id,
                                "switch": switch},
                    tags=base_resource_tags(
                        run_id=run_id, resource_name=subnet.name,
                        resource_kind="subnet", extra=list(subnet.tags),
                        defaults=self._config.default_tags,
                    ),
                )
                subnet_state[subnet.name] = resource
                continue

            pg = self._ops.create_port_group(
                name=pg_name, vlan_id=vlan_id, switch=switch, aspects=aspects,
            )
            pg_id = pg.get("network", pg_name) if isinstance(pg, dict) else pg_name
            resource = ProvisionedResource(
                kind="subnet", name=subnet.name, venue_id=pg_id,
                attributes={"port_group": pg_name, "vlan_id": vlan_id,
                            "switch": switch},
                tags=base_resource_tags(
                    run_id=run_id, resource_name=subnet.name,
                    resource_kind="subnet", extra=list(subnet.tags),
                    defaults=self._config.default_tags,
                ),
            )
            subnet_state[subnet.name] = resource
            created.append(resource)

        return subnet_state

    def apply_vms(self, *, spec: Any, run_id: str, aspects: Any,
                  subnet_state: Dict[str, ProvisionedResource],
                  keypair_map: Dict[str, str],
                  authkey: Optional[str],
                  created: List[ProvisionedResource],
                  skipped: List[str],
                  vpn_records: List[Dict[str, Any]]
                  ) -> Dict[str, ProvisionedResource]:
        """
            Realise each CloudInstance as a VM (Content Library clone or
            VmCreateSpec build), attach extra disks, apply guest
            customisation and power it on.

            :param spec: The VSphereSpec.
            :param run_id: Run identifier.
            :param aspects: Behaviour controls.
            :param subnet_state: Mapping from apply_networking.
            :param keypair_map: Mapping ``keypair_name -> public key``.
            :param authkey: Optional minted VPN auth-key.
            :param created: Output list of newly created resources.
            :param skipped: Output list of skipped resource names.
            :param vpn_records: Output list of VPN device records.

            :returns: A mapping ``instance_name -> ProvisionedResource``.
        """
        existing_vms = self._ops.list_vms(aspects=aspects)
        existing_by_name: Dict[str, Any] = {}
        for vm in existing_vms:
            vm_name = getattr(vm, "name", None)
            if vm_name is not None:
                existing_by_name[vm_name] = vm

        instance_state: Dict[str, ProvisionedResource] = {}

        for instance in spec.instances:
            vm_name = "{}-{}".format(run_id, instance.name)

            if vm_name in existing_by_name:
                skipped.append(instance.name)
                existing_vm = existing_by_name[vm_name]
                resource = ProvisionedResource(
                    kind="instance", name=instance.name,
                    venue_id=getattr(existing_vm, "vm", vm_name),
                    attributes={"vm_name": vm_name},
                    tags=base_resource_tags(
                        run_id=run_id, resource_name=instance.name,
                        resource_kind="instance", extra=list(instance.tags),
                        defaults=self._config.default_tags,
                    ),
                )
                instance_state[instance.name] = resource
                continue

            image_ref = self._resolver.image_to_library_or_template(
                family=instance.image.family,
                version=instance.image.version,
                architecture=instance.image.architecture,
                aspects=aspects,
            )
            hardware = self._resolver.size_to_hardware(size_hint=instance.size)
            datastore = self._resolver.pick_datastore(
                required_gb=float(hardware.disk_gb), aspects=aspects,
            )
            datastore_id = getattr(datastore, "datastore", "datastore-0")

            keypair_material: Optional[str] = None
            if instance.keypair is not None:
                keypair_material = keypair_map.get(instance.keypair, None)

            customization = self._guest_renderer.render(
                instance=instance, keypair_material=keypair_material,
                authkey=authkey,
            )

            port_group = ""
            subnet_resource = subnet_state.get(instance.subnet, None)
            if subnet_resource is not None:
                port_group = subnet_resource.attributes.get("port_group", "")

            if isinstance(image_ref, LibraryItemRef):
                deploy_payload = self._ops.deploy_library_item(
                    item_id=image_ref.item_id,
                    target={"folder": self._config.folder,
                            "cluster": self._config.cluster,
                            "datastore": datastore_id},
                    deploy_spec={"name": vm_name,
                                 "port_group": port_group,
                                 "vcpu_count": hardware.vcpu_count,
                                 "memory_mb": hardware.memory_mb},
                    aspects=aspects,
                )
                vm_id = deploy_payload.get("resource_id", vm_name)
                provisioned_via = "content-library"
            else:
                create_payload = self._ops.create_vm(
                    spec={"name": vm_name,
                          "guest_os": instance.image.family,
                          "placement": {"folder": self._config.folder,
                                        "cluster": self._config.cluster,
                                        "datastore": datastore_id},
                          "cpu": {"count": hardware.vcpu_count},
                          "memory": {"size_mib": hardware.memory_mb},
                          "disks": [{"new_vmdk": {"capacity":
                                                  hardware.disk_gb}}],
                          "nics": [{"network": port_group}],
                          "template_vm": image_ref.vm_id},
                    aspects=aspects,
                )
                vm_id = create_payload.get("resource_id", vm_name)
                provisioned_via = "vm-create-spec"

            self._ops.apply_guest_customization(
                vm_id=vm_id,
                spec={"hostname": customization.hostname,
                      "cloud_init_user_data":
                      customization.cloud_init_user_data},
                guest_os_family=customization.guest_os_family,
                aspects=aspects,
            )

            self._ops.power(vm_id=vm_id, action="start", aspects=aspects)

            attributes: Dict[str, Any] = {
                "vm_name": vm_name,
                "vm_id": vm_id,
                "provisioned_via": provisioned_via,
                "port_group": port_group,
                "datastore_id": datastore_id,
                "hostname": customization.hostname,
                "vcpu_count": hardware.vcpu_count,
                "memory_mb": hardware.memory_mb,
            }
            resource = ProvisionedResource(
                kind="instance", name=instance.name, venue_id=vm_id,
                attributes=attributes,
                tags=base_resource_tags(
                    run_id=run_id, resource_name=instance.name,
                    resource_kind="instance", extra=list(instance.tags),
                    defaults=self._config.default_tags,
                ),
            )
            instance_state[instance.name] = resource
            created.append(resource)

            if instance.vpn_join is not None:
                vpn_records.append({
                    "instance_name": instance.name,
                    "vm_id": vm_id,
                    "vpn_provider": instance.vpn_join.provider,
                    "vpn_device_id": None,
                })

        return instance_state

    def apply_disks(self, *, spec: Any, run_id: str, aspects: Any,
                    instance_state: Dict[str, ProvisionedResource],
                    created: List[ProvisionedResource],
                    skipped: List[str]) -> None:
        """
            Attach additional virtual disks for each CloudStorageVolume.

            :param spec: The VSphereSpec.
            :param run_id: Run identifier.
            :param aspects: Behaviour controls.
            :param instance_state: Mapping from apply_vms.
            :param created: Output list of newly created resources.
            :param skipped: Output list of skipped resource names.
        """
        for volume in spec.volumes:
            target_vm_id: Optional[str] = None
            if volume.attached_to is not None:
                target = instance_state.get(volume.attached_to, None)
                if target is not None:
                    target_vm_id = target.attributes.get("vm_id", None)

            if target_vm_id is None:
                skipped.append(volume.name)
                continue

            datastore = self._resolver.pick_datastore(
                required_gb=float(volume.size_gb), aspects=aspects,
            )
            datastore_id = getattr(datastore, "datastore", "datastore-0")

            disk_payload = self._ops.attach_disk(
                vm_id=target_vm_id, datastore_id=datastore_id,
                size_gb=volume.size_gb, aspects=aspects,
            )
            disk_id = disk_payload.get("resource_id", volume.name)
            resource = ProvisionedResource(
                kind="volume", name=volume.name, venue_id=disk_id,
                attributes={"size_gb": volume.size_gb,
                            "datastore_id": datastore_id,
                            "attached_to_vm": target_vm_id},
                tags=base_resource_tags(
                    run_id=run_id, resource_name=volume.name,
                    resource_kind="volume", extra=list(volume.tags),
                    defaults=self._config.default_tags,
                ),
            )
            created.append(resource)
        return
