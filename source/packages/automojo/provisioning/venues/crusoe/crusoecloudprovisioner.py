"""
    .. module:: crusoecloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CrusoeCloudProvisioner — concrete CloudProvisioner for the
        Crusoe Cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import ipaddress
import json
import os

from typing import Any, Dict, List, Optional

from automojo.restclient.crusoe.crusoeclient import CrusoeClient
from automojo.restclient.crusoe.specs.crusoediskspec import CrusoeDiskSpec
from automojo.restclient.crusoe.specs.crusoesecuritygroupspec import (
    CrusoeSecurityGroupSpec
)
from automojo.restclient.crusoe.specs.crusoesubnetspec import CrusoeSubnetSpec
from automojo.restclient.crusoe.specs.crusoevmlaunchspec import CrusoeVmLaunchSpec
from automojo.restclient.crusoe.specs.crusoevpcspec import CrusoeVpcSpec

from automojo.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog, default_accelerator_catalog
)
from automojo.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from automojo.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from automojo.provisioning.model.cloud.validationresult import ValidationResult
from automojo.provisioning.model.exceptions import SchemaSemanticError

from automojo.provisioning.venues.crusoe.crusoeerrors import (
    CrusoeValidationError
)
from automojo.provisioning.venues.crusoe.crusoeibpartition import (
    CrusoeIbPartition, interconnect_group_of
)
from automojo.provisioning.venues.crusoe.crusoelabeltranslator import (
    CrusoeLabelTranslator
)
from automojo.provisioning.venues.crusoe.crusoeprojectconfig import (
    CrusoeProjectConfig
)
from automojo.provisioning.venues.crusoe.crusoeresolver import CrusoeResolver
from automojo.provisioning.venues.crusoe.crusoespec import CrusoeSpec
from automojo.provisioning.venues.crusoe.crusoeuserdatarenderer import (
    CrusoeUserDataRenderer
)


_RUN_ID_LABEL = "automojo-run-id"

# Filesystem kinds the Crusoe venue does not realise.  VENUE_NATIVE is
# supported attach-only (existing_id required).
_UNSUPPORTED_FS_KINDS = frozenset({
    "WEKA", "VAST", "GPFS", "BEEGFS", "EFS", "FILESTORE", "AZUREFILES",
    "LUSTRE"
})


class CrusoeCloudProvisioner(CloudProvisioner):
    """
        Crusoe-venue concrete :class:`CloudProvisioner` implementation.

        Crusoe Cloud is the closest of the AI clouds to AWS in shape: it
        offers a full VPC / subnet / security-group / VM / disk surface plus
        InfiniBand-enabled placement.  This provisioner maps the neutral
        resource model onto those primitives through the
        :class:`CrusoeClient` interop client and realises the five-verb
        ``validate / plan / apply / destroy / inventory`` lifecycle.
    """

    VENUE_NAME: str = "crusoe"

    def __init__(self, *, venue: CloudVenue, client: CrusoeClient,
                 project_config: CrusoeProjectConfig,
                 spec: Optional[CrusoeSpec] = None,
                 catalog: Optional[CloudAcceleratorCatalog] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a CrusoeCloudProvisioner.

            :param venue: The CloudVenue this provisioner targets.
            :param client: The :class:`CrusoeClient` interop client.
            :param project_config: CrusoeProjectConfig (project + location).
            :param spec: Optional CrusoeSpec resource bundle.
            :param catalog: Optional accelerator catalog (defaults to the
                packaged singleton).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl used
                by destroy to de-register VPN devices.
        """
        super().__init__(venue=venue, spec=spec)

        self._client: CrusoeClient = client
        self._project_config: CrusoeProjectConfig = project_config

        if catalog is not None:
            self._catalog: CloudAcceleratorCatalog = catalog
        else:
            self._catalog = default_accelerator_catalog()

        self._resolver: CrusoeResolver = CrusoeResolver(catalog=self._catalog)
        self._labels: CrusoeLabelTranslator = CrusoeLabelTranslator()
        self._userdata: CrusoeUserDataRenderer = CrusoeUserDataRenderer()
        self._ib: CrusoeIbPartition = CrusoeIbPartition(
            client=client, resolver=self._resolver)

        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the CrusoeSpec without any remote I/O.

            :param aspects: ProvisioningAspects (or compatible).

            :returns: A ValidationResult with ok=True on success.

            :raises: CrusoeValidationError on any rejection.
        """
        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        # Crusoe has no native object storage and no load balancer surface.
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("Crusoe Cloud has no native object storage; "
                          "CloudObjectBucket is unsupported."),
            })
        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("Crusoe Cloud exposes no load balancer surface; "
                          "CloudLoadBalancer is unsupported."),
            })

        # Shared filesystem: only VENUE_NATIVE attach-only is supported.
        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Crusoe realises shared-FS through its native "
                              "storage-disk file-system; substitute "
                              "kind=VENUE_NATIVE for {}.").format(sfs.kind),
                })
            elif sfs.kind == "VENUE_NATIVE":
                if sfs.existing_id is None or len(sfs.existing_id) == 0:
                    errors.append({
                        "resource": sfs.name,
                        "error": ("Crusoe shared-FS v1 supports attach-only; "
                                  "set existing_id."),
                    })

        # Per-instance: location, instance type, and IB eligibility.
        network_cidrs: Dict[str, str] = {}
        for net in spec.networks:
            network_cidrs[net.name] = net.cidr

        for instance in spec.instances:
            self._validate_instance(instance=instance, errors=errors)

        # Subnet containment.
        for subnet in spec.subnets:
            parent_cidr = network_cidrs.get(subnet.network, None)
            if parent_cidr is None:
                errors.append({
                    "resource": subnet.name,
                    "error": "Subnet references unknown network: {}.".format(
                        subnet.network),
                })
                continue
            try:
                parent_net = ipaddress.ip_network(parent_cidr, strict=False)
                child_net = ipaddress.ip_network(subnet.cidr, strict=False)
                if not child_net.subnet_of(parent_net):
                    errors.append({
                        "resource": subnet.name,
                        "error": ("Subnet CIDR {} is not contained in "
                                  "network CIDR {}.").format(
                                      subnet.cidr, parent_cidr),
                    })
            except (TypeError, ValueError) as xcpt:
                errors.append({
                    "resource": subnet.name,
                    "error": "Subnet/Network CIDR parse error: {}.".format(
                        xcpt),
                })

        if len(errors) > 0:
            err_msg_lines = ["CrusoeCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]))
            err_msg = os.linesep.join(err_msg_lines)
            raise CrusoeValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    def _validate_instance(self, *, instance: Any,
                           errors: List[Dict[str, Any]]) -> None:
        """
            Validate a single instance's location, type, and IB eligibility.

            :param instance: The neutral CloudInstance.
            :param errors: The accumulating error list.

            :returns: ``None``.
        """
        # Image family must resolve to a Crusoe alias.
        try:
            self._resolver.image_to_alias(
                family=instance.image.family,
                version=instance.image.version,
                arch=instance.image.architecture)
        except SchemaSemanticError as xcpt:
            errors.append({
                "resource": instance.name,
                "error": "Image not resolvable on Crusoe: {}".format(xcpt),
            })

        # Resolve the instance type.
        resolved_type: Optional[str] = None
        try:
            resolved_type = self._resolver.size_to_instance_type(
                size_hint=instance.size,
                accelerators=instance.accelerators,
                interconnect=instance.interconnect)
        except SchemaSemanticError as xcpt:
            errors.append({
                "resource": instance.name,
                "error": "Instance type not resolvable on Crusoe: {}".format(
                    xcpt),
            })

        # InfiniBand requested but the resolved type is not IB-eligible.
        wants_ib = self._resolver.interconnect_is_infiniband(
            interconnect=instance.interconnect)
        if wants_ib is True and resolved_type is not None:
            ib_ok = self._resolver.instance_type_supports_ib(
                instance_type=resolved_type)
            if ib_ok is False:
                errors.append({
                    "resource": instance.name,
                    "error": ("InfiniBand interconnect requested but the "
                              "resolved instance type {!r} is not "
                              "IB-eligible.").format(resolved_type),
                })
        return

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan with read-only describes.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        spec = self._spec
        actions: List[Any] = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        project_id = self._project_config.project_id
        existing_vpcs = self._index_by_name(
            self._client.vpcs.list(project_id=project_id))

        for net in spec.networks:
            existing = existing_vpcs.get(net.name, None)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=net.name))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=net.name))

        for subnet in spec.subnets:
            parent = existing_vpcs.get(subnet.network, None)
            existing = None
            if parent is not None:
                subnets = self._index_by_name(
                    self._client.subnets.list(vpc_id=parent.vpc_id))
                existing = subnets.get(subnet.name, None)
            self._append_create_or_skip(actions=actions, kind="subnet",
                                        name=subnet.name, existing=existing)

        for sg in spec.security_groups:
            parent = existing_vpcs.get(sg.network, None)
            existing = None
            if parent is not None:
                groups = self._index_by_name(
                    self._client.security_groups.list(vpc_id=parent.vpc_id))
                existing = groups.get(sg.name, None)
            self._append_create_or_skip(actions=actions, kind="sg",
                                        name=sg.name, existing=existing)

        existing_keys = self._index_by_name(
            self._client.ssh_keys.list(project_id=project_id))
        for kp in spec.keypairs:
            self._append_create_or_skip(actions=actions, kind="keypair",
                                        name=kp.name,
                                        existing=existing_keys.get(kp.name,
                                                                   None))

        existing_vms = self._index_by_name(
            self._client.vms.list(project_id=project_id))
        for inst in spec.instances:
            existing = existing_vms.get(inst.name, None)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance", resource_name=inst.name))
            else:
                resolved_type = self._resolver.size_to_instance_type(
                    size_hint=inst.size, accelerators=inst.accelerators,
                    interconnect=inst.interconnect)
                if existing.instance_type != resolved_type:
                    actions.append(self._planned_action_for(
                        intent=PlannedActionIntent.UPDATE,
                        resource_kind="instance", resource_name=inst.name,
                        diff={"before": {"instance_type":
                                         existing.instance_type},
                              "after": {"instance_type": resolved_type},
                              "note": "instance_type drift: UPDATE-by-recreate"
                              }))
                else:
                    actions.append(self._planned_action_for(
                        intent=PlannedActionIntent.SKIP,
                        resource_kind="instance", resource_name=inst.name))

        existing_disks = self._index_by_name(
            self._client.disks.list(project_id=project_id))
        for vol in spec.volumes:
            self._append_create_or_skip(actions=actions, kind="volume",
                                        name=vol.name,
                                        existing=existing_disks.get(vol.name,
                                                                    None))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _append_create_or_skip(self, *, actions: List[Any], kind: str,
                               name: str, existing: Any) -> None:
        """
            Append a CREATE or SKIP action depending on existence.

            :param actions: The accumulating action list.
            :param kind: The resource kind string.
            :param name: The resource name.
            :param existing: The existing record, or ``None``.

            :returns: ``None``.
        """
        if existing is None:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.CREATE,
                resource_kind=kind, resource_name=name))
        else:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.SKIP,
                resource_kind=kind, resource_name=name))
        return

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: VPC -> Subnet -> Security Groups -> SSH Keys -> IB
            Partition -> Instances -> Disks.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningResult.
        """
        spec = self._spec
        if spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id
        project_id = self._project_config.project_id

        created: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []

        run_labels = {_RUN_ID_LABEL: run_id}

        # --- networking ---
        existing_vpcs = self._index_by_name(
            self._client.vpcs.list(project_id=project_id))
        vpc_state: Dict[str, Any] = {}
        for net in spec.networks:
            existed = net.name in existing_vpcs
            if existed:
                record = existing_vpcs[net.name]
                skipped.append(net.name)
            else:
                vpc_spec = CrusoeVpcSpec(name=net.name, cidr=net.cidr,
                                         project_id=project_id,
                                         labels=self._labels_for(net.tags,
                                                                  run_labels))
                record = self._client.vpcs.create(spec=vpc_spec)
                created.append(self._provisioned(kind="network",
                               name=net.name, venue_id=record.vpc_id))
            vpc_state[net.name] = record

        subnet_state: Dict[str, Any] = {}
        for subnet in spec.subnets:
            parent = vpc_state.get(subnet.network, None)
            if parent is None:
                continue
            existing_subnets = self._index_by_name(
                self._client.subnets.list(vpc_id=parent.vpc_id))
            existed = subnet.name in existing_subnets
            if existed:
                record = existing_subnets[subnet.name]
                skipped.append(subnet.name)
            else:
                subnet_spec = CrusoeSubnetSpec(
                    name=subnet.name, cidr=subnet.cidr,
                    vpc_id=parent.vpc_id, vpc_cidr=parent.cidr,
                    location=self._location_for_zone(zone=subnet.zone),
                    labels=self._labels_for(subnet.tags, run_labels))
                record = self._client.subnets.create(spec=subnet_spec)
                created.append(self._provisioned(kind="subnet",
                               name=subnet.name, venue_id=record.subnet_id))
            subnet_state[subnet.name] = record

        sg_state: Dict[str, Any] = {}
        for sg in spec.security_groups:
            parent = vpc_state.get(sg.network, None)
            if parent is None:
                continue
            existing_sgs = self._index_by_name(
                self._client.security_groups.list(vpc_id=parent.vpc_id))
            existed = sg.name in existing_sgs
            if existed:
                record = existing_sgs[sg.name]
                skipped.append(sg.name)
            else:
                sg_spec = CrusoeSecurityGroupSpec(
                    name=sg.name, vpc_id=parent.vpc_id,
                    ingress_rules=self._ingress_payload(sg=sg),
                    egress_rules=self._egress_payload(sg=sg),
                    labels=self._labels_for(sg.tags, run_labels))
                record = self._client.security_groups.create(spec=sg_spec)
                created.append(self._provisioned(kind="sg", name=sg.name,
                               venue_id=record.security_group_id))
            sg_state[sg.name] = record

        key_state: Dict[str, Any] = {}
        existing_keys = self._index_by_name(
            self._client.ssh_keys.list(project_id=project_id))
        for kp in spec.keypairs:
            existed = kp.name in existing_keys
            if existed:
                record = existing_keys[kp.name]
                skipped.append(kp.name)
            else:
                record = self._client.ssh_keys.register(
                    project_id=project_id, name=kp.name,
                    public_key=kp.public_key_material)
                created.append(self._provisioned(kind="keypair",
                               name=kp.name, venue_id=record.ssh_key_id))
            key_state[kp.name] = record

        # --- IB partitions for InfiniBand-grouped instances ---
        ib_partition_ids: Dict[str, str] = {}
        for inst in spec.instances:
            group_key = interconnect_group_of(instance=inst)
            wants_ib = self._resolver.interconnect_is_infiniband(
                interconnect=inst.interconnect)
            if wants_ib is True and len(group_key) > 0:
                if group_key not in ib_partition_ids:
                    partition_id = self._ib.ensure(
                        project_id=project_id, group_key=group_key,
                        run_id=run_id, aspects=aspects)
                    ib_partition_ids[group_key] = partition_id

        # --- instances + disks ---
        existing_vms = self._index_by_name(
            self._client.vms.list(project_id=project_id))
        instance_state: Dict[str, Any] = {}
        for inst in spec.instances:
            existed = inst.name in existing_vms
            if existed:
                record = existing_vms[inst.name]
                instance_state[inst.name] = record
                skipped.append(inst.name)
                continue

            record = self._launch_instance(
                inst=inst, project_id=project_id, run_labels=run_labels,
                subnet_state=subnet_state, sg_state=sg_state,
                key_state=key_state, ib_partition_ids=ib_partition_ids,
                aspects=aspects)
            instance_state[inst.name] = record
            created.append(self._provisioned(kind="instance", name=inst.name,
                           venue_id=record.vm_id))

            if inst.vpn_join is not None:
                vpn_records.append({
                    "instance_name": inst.name,
                    "instance_id": record.vm_id,
                    "vpn_provider": inst.vpn_join.provider,
                    "vpn_device_id": None,
                })

        existing_disks = self._index_by_name(
            self._client.disks.list(project_id=project_id))
        for vol in spec.volumes:
            existed = vol.name in existing_disks
            if existed:
                skipped.append(vol.name)
                disk_record = existing_disks[vol.name]
            else:
                disk_spec = CrusoeDiskSpec(
                    name=vol.name, size_gib=vol.size_gb,
                    location=self._project_config.location,
                    labels=self._labels_for(vol.tags, run_labels))
                disk_record, _ = self._client.disks.create(
                    project_id=project_id, spec=disk_spec)
                created.append(self._provisioned(kind="volume",
                               name=vol.name, venue_id=disk_record.disk_id))

            if vol.attached_to is not None and not existed:
                target = instance_state.get(vol.attached_to, None)
                if target is not None:
                    self._client.disks.attach(project_id=project_id,
                                              disk_id=disk_record.disk_id,
                                              instance_id=target.vm_id)

        self._last_vpn_records = vpn_records

        rtnval = ProvisioningResult(created=created, updated=[],
                                    skipped=skipped, errors=[])
        return rtnval

    def _launch_instance(self, *, inst: Any, project_id: str,
                         run_labels: Dict[str, str],
                         subnet_state: Dict[str, Any],
                         sg_state: Dict[str, Any],
                         key_state: Dict[str, Any],
                         ib_partition_ids: Dict[str, str],
                         aspects: Any) -> Any:
        """
            Launch a single instance, folding in IB placement and user-data.

            :param inst: The neutral CloudInstance.
            :param project_id: The Crusoe project identifier.
            :param run_labels: The run-id label dict.
            :param subnet_state: Map of subnet name -> Crusoe subnet record.
            :param sg_state: Map of sg name -> Crusoe security group record.
            :param key_state: Map of keypair name -> Crusoe SSH key record.
            :param ib_partition_ids: Map of IB group key -> partition id.
            :param aspects: ProvisioningAspects.

            :returns: The launched :class:`CrusoeVm` record.
        """
        subnet_record = subnet_state.get(inst.subnet, None)
        subnet_id = ""
        if subnet_record is not None:
            subnet_id = subnet_record.subnet_id

        sg_ids: List[str] = []
        ref_sgs = inst.security_groups if inst.security_groups is not None else []
        for sg_name in ref_sgs:
            sg_record = sg_state.get(sg_name, None)
            if sg_record is not None:
                sg_ids.append(sg_record.security_group_id)

        ssh_key_ids: List[str] = []
        if inst.keypair is not None:
            key_record = key_state.get(inst.keypair, None)
            if key_record is not None:
                ssh_key_ids.append(key_record.ssh_key_id)

        instance_type = self._resolver.size_to_instance_type(
            size_hint=inst.size, accelerators=inst.accelerators,
            interconnect=inst.interconnect)
        supports_ib = self._resolver.instance_type_supports_ib(
            instance_type=instance_type)

        placement_group_id: Optional[str] = None
        placement_interconnect: Optional[str] = None
        wants_ib = self._resolver.interconnect_is_infiniband(
            interconnect=inst.interconnect)
        if wants_ib is True:
            group_key = interconnect_group_of(instance=inst)
            placement_group_id = ib_partition_ids.get(group_key, None)
            if placement_group_id is not None:
                placement_interconnect = "infiniband"

        image_alias = self._resolver.image_to_alias(
            family=inst.image.family, version=inst.image.version,
            arch=inst.image.architecture)

        authkey = self._minted_authkey(instance=inst)
        user_data = self._userdata.render(instance=inst, authkey=authkey)

        launch_spec = CrusoeVmLaunchSpec(
            name=inst.name, instance_type=instance_type,
            location=self._project_config.location,
            image_id=image_alias, subnet_id=subnet_id,
            ssh_key_ids=ssh_key_ids, security_group_ids=sg_ids,
            placement_group_id=placement_group_id,
            placement_group_interconnect=placement_interconnect,
            instance_type_supports_ib=supports_ib,
            user_data=user_data,
            labels=self._labels_for(inst.tags, run_labels))

        record, _ = self._client.vms.launch(project_id=project_id,
                                             spec=launch_spec)
        rtnval = record
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Destroy every owned resource in reverse apply order.

            :param aspects: ProvisioningAspects.

            :returns: ``None``.
        """
        run_id = self._run_id(aspects=aspects)
        project_id = self._project_config.project_id

        # 1. Disks.
        for disk in self._client.disks.list(project_id=project_id):
            if self._owned(labels=disk.labels, run_id=run_id):
                self._client.disks.delete(project_id=project_id,
                                          disk_id=disk.disk_id)

        # 2. Instances — terminate then de-register VPN devices.
        terminated_vms: List[Any] = []
        for vm in self._client.vms.list(project_id=project_id):
            if self._owned(labels=vm.labels, run_id=run_id):
                self._client.vms.terminate(project_id=project_id,
                                           vm_id=vm.vm_id)
                terminated_vms.append(vm)

        if self._vpn_control_plane is not None:
            for record in self._last_vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                self._vpn_control_plane.delete_device(device_id=device_id,
                                                      aspects=aspects)

        # 3. IB partitions.
        for partition in self._client.placement_groups.list(
                project_id=project_id):
            if self._owned(labels=partition.labels, run_id=run_id):
                self._client.placement_groups.delete(
                    project_id=project_id,
                    placement_group_id=partition.placement_group_id)

        # 4. SSH keys.
        if self._spec is not None:
            for kp in self._spec.keypairs:
                for key in self._client.ssh_keys.list(project_id=project_id):
                    if key.name == kp.name:
                        self._client.ssh_keys.delete(
                            project_id=project_id, ssh_key_id=key.ssh_key_id)

        # 5. Security groups + 6. Subnets + 7. VPCs.
        for vpc in self._client.vpcs.list(project_id=project_id):
            if not self._owned(labels=vpc.labels, run_id=run_id):
                continue
            for sg in self._client.security_groups.list(vpc_id=vpc.vpc_id):
                self._client.security_groups.delete(
                    vpc_id=vpc.vpc_id,
                    security_group_id=sg.security_group_id)
            for subnet in self._client.subnets.list(vpc_id=vpc.vpc_id):
                self._client.subnets.delete(vpc_id=vpc.vpc_id,
                                            subnet_id=subnet.subnet_id)
            self._client.vpcs.delete(project_id=project_id,
                                     vpc_id=vpc.vpc_id)
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate run-id-labelled resources for the run.

            :param aspects: ProvisioningAspects.

            :returns: A list of ProvisionedResource entries.
        """
        run_id = self._run_id(aspects=aspects)
        project_id = self._project_config.project_id
        out: List[ProvisionedResource] = []

        for vpc in self._client.vpcs.list(project_id=project_id):
            if self._owned(labels=vpc.labels, run_id=run_id):
                out.append(self._provisioned(kind="network", name=vpc.name,
                           venue_id=vpc.vpc_id))
                for subnet in self._client.subnets.list(vpc_id=vpc.vpc_id):
                    out.append(self._provisioned(kind="subnet",
                               name=subnet.name, venue_id=subnet.subnet_id))

        for vm in self._client.vms.list(project_id=project_id):
            if self._owned(labels=vm.labels, run_id=run_id):
                out.append(self._provisioned(kind="instance", name=vm.name,
                           venue_id=vm.vm_id))

        for disk in self._client.disks.list(project_id=project_id):
            if self._owned(labels=disk.labels, run_id=run_id):
                out.append(self._provisioned(kind="volume", name=disk.name,
                           venue_id=disk.disk_id))

        for partition in self._client.placement_groups.list(
                project_id=project_id):
            if self._owned(labels=partition.labels, run_id=run_id):
                out.append(self._provisioned(
                    kind="placement_group", name=partition.name,
                    venue_id=partition.placement_group_id))

        rtnval = out
        return rtnval

    def persist_inventory(self, *, aspects: Any,
                          output_root: str = ".output") -> str:
        """
            Write the run inventory to a JSON file under the output root.

            The file is written to
            ``<output_root>/provisioning/<runid>/crusoe-inventory.json``.

            :param aspects: ProvisioningAspects.
            :param output_root: The base output directory.

            :returns: The path of the written inventory file.
        """
        run_id = self._run_id(aspects=aspects)
        items = self.inventory(aspects=aspects)

        run_dir = os.path.join(output_root, "provisioning", run_id)
        os.makedirs(run_dir, exist_ok=True)
        out_path = os.path.join(run_dir, "crusoe-inventory.json")

        records: List[Dict[str, Any]] = []
        for item in items:
            records.append({
                "kind": item.kind,
                "name": item.name,
                "venue_id": item.venue_id,
            })

        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump({"run_id": run_id, "resources": records}, fh, indent=2)

        rtnval = out_path
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance post-apply.

            :param instance_name: Neutral instance name.
            :param device_id: Provider-assigned device id.

            :returns: ``None``.
        """
        for record in self._last_vpn_records:
            if record.get("instance_name", "") == instance_name:
                record["vpn_device_id"] = device_id
                return
        self._last_vpn_records.append({"instance_name": instance_name,
                                       "vpn_device_id": device_id})
        return

    @property
    def last_vpn_records(self) -> List[Dict[str, Any]]:
        """
            Return the recorded VPN device records from the last apply.

            :returns: A defensive copy of the records.
        """
        rtnval = [dict(entry) for entry in self._last_vpn_records]
        return rtnval

    def _minted_authkey(self, *, instance: Any) -> Optional[str]:
        """
            Resolve a minted VPN auth key for an instance, if available.

            :param instance: The neutral CloudInstance.

            :returns: The auth key string, or ``None``.
        """
        rtnval: Optional[str] = None
        if instance.vpn_join is not None and self._vpn_control_plane is not None:
            rtnval = getattr(self._vpn_control_plane, "minted_authkey", None)
        return rtnval

    def _labels_for(self, tags: Optional[Dict[str, str]],
                    run_labels: Dict[str, str]) -> Dict[str, str]:
        """
            Build the Crusoe label dict for a resource from neutral tags.

            :param tags: The neutral tag dict, or ``None``.
            :param run_labels: The run-id label dict.

            :returns: A merged Crusoe label dict.
        """
        effective_tags = tags if tags is not None else {}
        labels = self._labels.to_crusoe(neutral_tags=effective_tags)
        labels.update(run_labels)
        rtnval = labels
        return rtnval

    def _owned(self, *, labels: Dict[str, str], run_id: str) -> bool:
        """
            Report whether a resource is owned by this run.

            :param labels: The resource's label dict.
            :param run_id: The provisioning run identifier.

            :returns: ``True`` when the run-id label matches.
        """
        rtnval = False
        if labels is not None:
            rtnval = labels.get(_RUN_ID_LABEL, None) == run_id
        return rtnval

    def _provisioned(self, *, kind: str, name: str,
                     venue_id: str) -> ProvisionedResource:
        """
            Build a ProvisionedResource record.

            :param kind: The resource kind string.
            :param name: The resource name.
            :param venue_id: The Crusoe-side identifier.

            :returns: A ProvisionedResource.
        """
        rtnval = ProvisionedResource(kind=kind, name=name, venue_id=venue_id,
                                     attributes={}, tags={})
        return rtnval

    def _ingress_payload(self, *, sg: Any) -> List[Dict[str, Any]]:
        """
            Translate neutral ingress rules into Crusoe rule dicts.

            :param sg: The neutral CloudSecurityGroup.

            :returns: A list of ingress rule dicts.
        """
        rtnval: List[Dict[str, Any]] = []
        rules = sg.ingress_rules if sg.ingress_rules is not None else []
        for rule in rules:
            rtnval.append({
                "protocol": rule.protocol,
                "from_port": rule.from_port,
                "to_port": rule.to_port,
                "source_cidrs": list(rule.source_cidrs),
            })
        return rtnval

    def _egress_payload(self, *, sg: Any) -> List[Dict[str, Any]]:
        """
            Translate neutral egress rules into Crusoe rule dicts.

            :param sg: The neutral CloudSecurityGroup.

            :returns: A list of egress rule dicts.
        """
        rtnval: List[Dict[str, Any]] = []
        rules = sg.egress_rules if sg.egress_rules is not None else []
        for rule in rules:
            rtnval.append({
                "protocol": rule.protocol,
                "from_port": rule.from_port,
                "to_port": rule.to_port,
                "dest_cidrs": list(rule.dest_cidrs),
            })
        return rtnval

    def _location_for_zone(self, *, zone: str) -> str:
        """
            Resolve a neutral subnet zone into a Crusoe location.

            :param zone: The neutral zone identifier.

            :returns: The Crusoe location string.
        """
        rtnval = zone
        if zone is None or len(zone) == 0:
            rtnval = self._project_config.location
        return rtnval

    @staticmethod
    def _index_by_name(records: List[Any]) -> Dict[str, Any]:
        """
            Index a list of records by their ``name`` attribute.

            :param records: The record list.

            :returns: A name -> record dict.
        """
        rtnval: Dict[str, Any] = {}
        for record in records:
            rtnval[record.name] = record
        return rtnval

    def _run_id(self, *, aspects: Any) -> str:
        """
            Resolve the run identifier from aspects or fall back to venue.

            :param aspects: ProvisioningAspects.

            :returns: A non-empty run id string.
        """
        candidate = self._aspect_attr(aspects=aspects, name="runid",
                                      default=None)
        if candidate is not None and len(candidate) > 0:
            rtnval = candidate
            return rtnval
        rtnval = "crusoe-{}".format(self._venue.name)
        return rtnval
