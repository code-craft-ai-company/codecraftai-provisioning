"""
    .. module:: oraclecloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OracleCloudProvisioner — concrete CloudProvisioner for Oracle
               Cloud Infrastructure (OCI).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import ipaddress
import os

from typing import Any, Dict, List, Optional

from ccai.credentials.oraclecloudapikeycredential import (
    OracleCloudApiKeyCredential
)
from ccai.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog, default_accelerator_catalog
)
from ccai.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from ccai.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from ccai.provisioning.model.cloud.validationresult import ValidationResult
from ccai.provisioning.model.cloud.acceleratornotofferederror import (
    AcceleratorNotOfferedOnVenueError
)
from ccai.provisioning.venues.vpncleanup import delete_vpn_device

from ccai.provisioning.venues.oracle.ocierrors import OciValidationError
from ccai.provisioning.venues.oracle.ociregionconfig import OciRegionConfig
from ccai.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from ccai.provisioning.venues.oracle.ocispec import OciSpec
from ccai.provisioning.venues.oracle.ocitagging import (
    OCI_TAG_KEY_MAX, OCI_TAG_VALUE_MAX
)
from ccai.provisioning.venues.oracle.resources.blockvolumemanager import (
    BlockVolumeManager
)
from ccai.provisioning.venues.oracle.resources.clusternetworkmanager import (
    ClusterNetworkManager
)
from ccai.provisioning.venues.oracle.resources.computemanager import (
    ComputeManager, is_bm_gpu_shape
)
from ccai.provisioning.venues.oracle.resources.dnsmanager import DnsManager
from ccai.provisioning.venues.oracle.resources.filestoragemanager import (
    FileStorageManager
)
from ccai.provisioning.venues.oracle.resources.imageresolver import (
    ImageResolver
)
from ccai.provisioning.venues.oracle.resources.internetgatewaymanager import (
    InternetGatewayManager
)
from ccai.provisioning.venues.oracle.resources.keypairmanager import (
    KeyPairManager
)
from ccai.provisioning.venues.oracle.resources.objectstoragemanager import (
    ObjectStorageManager
)
from ccai.provisioning.venues.oracle.resources.routetablemanager import (
    RouteTableManager
)
from ccai.provisioning.venues.oracle.resources.securitylistmanager import (
    SecurityListManager
)
from ccai.provisioning.venues.oracle.resources.subnetmanager import (
    SubnetManager
)
from ccai.provisioning.venues.oracle.resources.vcnmanager import VcnManager


# Shared-FS kinds OCI cannot realise.
_UNSUPPORTED_FS_KINDS = frozenset({"WEKA", "VAST", "GPFS", "BEEGFS", "EFS",
                                   "AZUREFILES"})

# Interconnect kinds OCI rejects — OCI exposes RDMA only via OCI_RDMA.
_REJECTED_INTERCONNECTS = frozenset({"EFA", "INFINIBAND_HDR",
                                     "INFINIBAND_NDR", "INFINIBAND_XDR"})


def _all_tags_of(spec: OciSpec) -> List[Dict[str, str]]:
    """
        Flatten every tag dict declared anywhere in an OciSpec.

        :param spec: The OciSpec.

        :returns: A list of single-entry tag dicts.
    """
    out: List[Dict[str, str]] = []
    for collection in (spec.networks, spec.subnets, spec.security_groups,
                       spec.instances, spec.volumes, spec.buckets):
        for entry in collection:
            tags = getattr(entry, "tags", None)
            if tags is not None:
                for tag in tags:
                    out.append(tag)
    rtnval = out
    return rtnval


def _rdma_group_key(*, instance: Any) -> Optional[str]:
    """
        Return the RDMA cluster-network group key for an instance.

        An instance participates in an RDMA cluster network when it carries
        ``CloudInterconnect(kind=OCI_RDMA)``.  Instances sharing the same
        ``placement_group`` label land in the same cluster network.

        :param instance: A CloudInstance.

        :returns: A group key string, or None when not RDMA.
    """
    if instance.interconnect is None:
        rtnval: Optional[str] = None
        return rtnval
    if instance.interconnect.kind != "OCI_RDMA":
        rtnval = None
        return rtnval
    if instance.placement_group is not None and len(instance.placement_group) > 0:
        rtnval = instance.placement_group
        return rtnval
    rtnval = "{}-rdma".format(instance.name)
    return rtnval


class OracleCloudProvisioner(CloudProvisioner):
    """
        Oracle-Cloud-venue concrete :class:`CloudProvisioner`.

        Composes the per-resource managers behind a five-verb lifecycle.  The
        spec is an :class:`OciSpec` bundle of neutral resource objects.  OCI's
        HPC differentiator — RoCEv2 RDMA cluster networks — is realised for
        instances carrying ``CloudInterconnect(kind=OCI_RDMA)``.
    """

    VENUE_NAME: str = "oracle"

    def __init__(self, *, venue: CloudVenue,
                 credential: OracleCloudApiKeyCredential,
                 region_config: OciRegionConfig,
                 spec: Optional[OciSpec] = None,
                 catalog: Optional[CloudAcceleratorCatalog] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct an OracleCloudProvisioner.

            :param venue: CloudVenue.
            :param credential: OracleCloudApiKeyCredential used for the
                               ``oci`` SDK.
            :param region_config: OciRegionConfig.
            :param spec: Optional OciSpec.
            :param catalog: Optional accelerator catalog (defaults to the
                            packaged singleton).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                                      destroy uses this to de-register
                                      Tailscale / Twingate devices.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: OracleCloudApiKeyCredential = credential
        self._region_config: OciRegionConfig = region_config
        self._session_factory: OciSessionFactory = OciSessionFactory(
            credential=credential, region_config=region_config
        )
        if catalog is not None:
            self._catalog: CloudAcceleratorCatalog = catalog
        else:
            self._catalog = default_accelerator_catalog()

        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        self._vcn_mgr: VcnManager = VcnManager(
            session_factory=self._session_factory
        )
        self._igw_mgr: InternetGatewayManager = InternetGatewayManager(
            session_factory=self._session_factory
        )
        self._route_mgr: RouteTableManager = RouteTableManager(
            session_factory=self._session_factory
        )
        self._subnet_mgr: SubnetManager = SubnetManager(
            session_factory=self._session_factory
        )
        self._seclist_mgr: SecurityListManager = SecurityListManager(
            session_factory=self._session_factory
        )
        self._keypair_mgr: KeyPairManager = KeyPairManager()
        self._image_resolver: ImageResolver = ImageResolver(
            session_factory=self._session_factory
        )
        self._cluster_mgr: ClusterNetworkManager = ClusterNetworkManager(
            session_factory=self._session_factory
        )
        self._compute_mgr: ComputeManager = ComputeManager(
            session_factory=self._session_factory,
            image_resolver=self._image_resolver,
            catalog=self._catalog,
        )
        self._volume_mgr: BlockVolumeManager = BlockVolumeManager(
            session_factory=self._session_factory
        )
        self._bucket_mgr: ObjectStorageManager = ObjectStorageManager(
            session_factory=self._session_factory
        )
        self._dns_mgr: DnsManager = DnsManager(
            session_factory=self._session_factory
        )
        self._fs_mgr: FileStorageManager = FileStorageManager(
            session_factory=self._session_factory
        )

        # Tracked across apply / destroy.
        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    @classmethod
    def supports_preemption(cls) -> bool:
        """
            Oracle Cloud offers Preemptible Instances, so this venue can
            preempt instances.

            :returns: True.
        """
        rtnval = True
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Validate the OciSpec without any ``oci`` SDK calls.

            :param aspects: ProvisioningAspects (or compatible).

            :returns: A ValidationResult with ok=True on success.
            :raises: OciValidationError
        """
        if not isinstance(self._credential, OracleCloudApiKeyCredential):
            err_msg_lines = [
                "OracleCloudProvisioner requires an "
                "OracleCloudApiKeyCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        compartment_id = self._region_config.compartment_id
        availability_domain = self._region_config.availability_domain

        network_cidrs: Dict[str, str] = {}
        for net in spec.networks:
            network_cidrs[net.name] = net.cidr

        # Every instance needs a resolvable compartment + availability domain.
        if compartment_id is None or len(compartment_id) == 0:
            for instance in spec.instances:
                errors.append({
                    "resource": instance.name,
                    "error": "No compartment OCID resolved for instance.",
                })
        if availability_domain is None or len(availability_domain) == 0:
            for instance in spec.instances:
                errors.append({
                    "resource": instance.name,
                    "error": "No availability domain resolved for instance.",
                })

        # Shared FS kind acceptance.
        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("OCI realises shared-FS through OCI File "
                              "Storage.  Substitute kind=VENUE_NATIVE for "
                              "{}, or kind=LUSTRE with existing_id.").format(
                                  sfs.kind
                              ),
                })
            elif sfs.kind == "LUSTRE":
                if sfs.existing_id is None or len(sfs.existing_id) == 0:
                    errors.append({
                        "resource": sfs.name,
                        "error": ("OCI managed Lustre v1 is attach-only; "
                                  "set existing_id."),
                    })

        # Per-instance: interconnect + accelerator + RDMA-shape check.
        for instance in spec.instances:
            if instance.interconnect is not None:
                if instance.interconnect.kind in _REJECTED_INTERCONNECTS:
                    errors.append({
                        "resource": instance.name,
                        "error": ("OCI exposes RDMA only via OCI_RDMA "
                                  "cluster networks; use kind=OCI_RDMA "
                                  "instead of {}.").format(
                                      instance.interconnect.kind
                                  ),
                    })

            # Accelerator resolution + size conflict.
            accelerators = instance.accelerators if instance.accelerators is not None else []
            resolved_shape: Optional[str] = None
            if len(accelerators) > 0:
                first = accelerators[0]
                shape: Optional[str] = None
                try:
                    shape = self._catalog.resolve(
                        neutral_name=first.model, venue=self.VENUE_NAME
                    )
                # Only the venue-capability finding is aggregated here.  A
                # SchemaSemanticError from the catalog means the spec named an
                # accelerator that does not exist at all; that is information the
                # run cannot rely on, so it is deliberately NOT caught and halts.
                except AcceleratorNotOfferedOnVenueError as xcpt:
                    errors.append({
                        "resource": instance.name,
                        "error": "Accelerator not on OCI: {}".format(xcpt),
                    })

                if shape is not None:
                    resolved_shape = shape
                    if instance.size is not None and len(instance.size) > 0:
                        if instance.size != shape and instance.size != first.model:
                            errors.append({
                                "resource": instance.name,
                                "error": ("Instance.size {!r} conflicts "
                                          "with resolved accelerator shape "
                                          "{!r}.").format(instance.size,
                                                          shape),
                            })

            if resolved_shape is None:
                resolved_shape = instance.size

            # RDMA cluster networks require a BM.GPU shape.
            if instance.interconnect is not None and instance.interconnect.kind == "OCI_RDMA":
                if resolved_shape is None or not is_bm_gpu_shape(
                    shape=resolved_shape
                ):
                    errors.append({
                        "resource": instance.name,
                        "error": ("OCI_RDMA cluster networks require a "
                                  "BM.GPU shape; got {!r}.").format(
                                      resolved_shape
                                  ),
                    })

        # Tag length checks.
        for entry in _all_tags_of(spec=spec):
            for key, value in entry.items():
                if len(key) > OCI_TAG_KEY_MAX:
                    errors.append({
                        "resource": "<tags>",
                        "error": "Tag key exceeds 100 chars: {!r}".format(
                            key
                        ),
                    })
                if len(value) > OCI_TAG_VALUE_MAX:
                    errors.append({
                        "resource": "<tags>",
                        "error": "Tag value exceeds 256 chars: key={}.".format(
                            key
                        ),
                    })

        # Subnet containment.
        for subnet in spec.subnets:
            parent_cidr = network_cidrs.get(subnet.network, None)
            if parent_cidr is None:
                errors.append({
                    "resource": subnet.name,
                    "error": "Subnet references unknown network: {}.".format(
                        subnet.network
                    ),
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
                                      subnet.cidr, parent_cidr
                                  ),
                    })
            except (TypeError, ValueError) as xcpt:
                errors.append({
                    "resource": subnet.name,
                    "error": "Subnet/Network CIDR parse error: {}.".format(
                        xcpt
                    ),
                })

        if len(errors) > 0:
            err_msg_lines = ["OracleCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE/DELETE plan.

            Performs read-only list calls; no mutation.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        spec = self._spec
        actions = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        for net in spec.networks:
            existing = self._vcn_mgr.find(run_id=run_id, name=net.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=net.name,
                ))
            elif self._vcn_mgr.matches(existing=existing, desired=net):
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=net.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="network", resource_name=net.name,
                    diff={"before": {"cidr": getattr(existing,
                                                     "cidr_block", "")},
                          "after": {"cidr": net.cidr}},
                ))

        for subnet in spec.subnets:
            existing = self._subnet_mgr.find(run_id=run_id, name=subnet.name)
            intent = (PlannedActionIntent.SKIP if existing is not None
                      else PlannedActionIntent.CREATE)
            actions.append(self._planned_action_for(
                intent=intent, resource_kind="subnet",
                resource_name=subnet.name,
            ))

        for sg in spec.security_groups:
            existing = self._seclist_mgr.find(run_id=run_id, name=sg.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="security_group", resource_name=sg.name,
                ))
            elif self._seclist_mgr.rules_drifted(existing=existing,
                                                 desired=sg):
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="security_group", resource_name=sg.name,
                    diff={"note": "Security-list rule drift."},
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="security_group", resource_name=sg.name,
                ))

        for inst in spec.instances:
            existing = self._compute_mgr.find(run_id=run_id, name=inst.name)
            intent = (PlannedActionIntent.SKIP if existing is not None
                      else PlannedActionIntent.CREATE)
            actions.append(self._planned_action_for(
                intent=intent, resource_kind="instance",
                resource_name=inst.name,
            ))

        for vol in spec.volumes:
            existing = self._volume_mgr.find(run_id=run_id, name=vol.name)
            intent = (PlannedActionIntent.SKIP if existing is not None
                      else PlannedActionIntent.CREATE)
            actions.append(self._planned_action_for(
                intent=intent, resource_kind="volume",
                resource_name=vol.name,
            ))

        for bucket in spec.buckets:
            existing = self._bucket_mgr.find(run_id=run_id, name=bucket.name)
            intent = (PlannedActionIntent.SKIP if existing is not None
                      else PlannedActionIntent.CREATE)
            actions.append(self._planned_action_for(
                intent=intent, resource_kind="bucket",
                resource_name=bucket.name,
            ))

        for record in spec.dns_records:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.CREATE,
                resource_kind="dns", resource_name=record.name,
            ))

        for lb in spec.load_balancers:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.SKIP,
                resource_kind="lb", resource_name=lb.name,
                diff={"note": "Load balancer apply is deferred to v1.5."},
            ))

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: VCN → Subnet → Internet Gateway + Route Table →
            Security List → Cluster Network → Instance → Block Volume →
            File Storage attach → Object Storage → DNS.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningResult.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id
        default_tags = self._region_config.default_tags

        created: List[ProvisionedResource] = []
        updated: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []

        spec = self._spec
        self._keypair_mgr.register(keypairs=spec.keypairs)

        # --- networking: VCN + IGW + route table ---
        network_state: Dict[str, ProvisionedResource] = {}
        network_route: Dict[str, str] = {}
        for net in spec.networks:
            existed = self._vcn_mgr.find(run_id=run_id,
                                         name=net.name) is not None
            resource = self._vcn_mgr.ensure(
                desired=net, run_id=run_id, default_tags=default_tags,
                aspects=aspects,
            )
            network_state[net.name] = resource
            vcn_id = resource.attributes.get("vcn_id", "")
            igw_id = self._igw_mgr.ensure(
                run_id=run_id, network_name=net.name, vcn_id=vcn_id,
                default_tags=default_tags, aspects=aspects,
            )
            rt_id = self._route_mgr.ensure_public(
                run_id=run_id, network_name=net.name, vcn_id=vcn_id,
                igw_id=igw_id, default_tags=default_tags, aspects=aspects,
            )
            network_route[net.name] = rt_id
            if existed:
                skipped.append(net.name)
            else:
                created.append(resource)

        # --- security lists (created before subnets so subnets reference) ---
        sg_state: Dict[str, ProvisionedResource] = {}
        sg_for_network: Dict[str, List[str]] = {}
        for sg in spec.security_groups:
            parent = network_state.get(sg.network, None)
            if parent is None:
                continue
            vcn_id = parent.attributes.get("vcn_id", "")
            existed = self._seclist_mgr.find(run_id=run_id,
                                             name=sg.name) is not None
            resource = self._seclist_mgr.ensure(
                desired=sg, run_id=run_id, vcn_id=vcn_id,
                default_tags=default_tags, aspects=aspects,
            )
            sg_state[sg.name] = resource
            seclist_id = resource.attributes.get("security_list_id", "")
            sg_for_network.setdefault(sg.network, []).append(seclist_id)
            if existed:
                skipped.append(sg.name)
            else:
                created.append(resource)

        # --- subnets ---
        subnet_state: Dict[str, ProvisionedResource] = {}
        for subnet in spec.subnets:
            parent = network_state.get(subnet.network, None)
            if parent is None:
                continue
            vcn_id = parent.attributes.get("vcn_id", "")
            route_id = None
            if subnet.public is True:
                route_id = network_route.get(subnet.network, None)
            seclist_ids = sg_for_network.get(subnet.network, [])
            existed = self._subnet_mgr.find(run_id=run_id,
                                            name=subnet.name) is not None
            resource = self._subnet_mgr.ensure(
                desired=subnet, run_id=run_id, vcn_id=vcn_id,
                route_table_id=route_id, security_list_ids=seclist_ids,
                default_tags=default_tags, aspects=aspects,
            )
            subnet_state[subnet.name] = resource
            if existed:
                skipped.append(subnet.name)
            else:
                created.append(resource)

        # --- RDMA cluster networks ---
        cluster_for_group: Dict[str, str] = {}
        group_members: Dict[str, List[Any]] = {}
        for inst in spec.instances:
            group_key = _rdma_group_key(instance=inst)
            if group_key is not None:
                group_members.setdefault(group_key, []).append(inst)

        for group_key, members in group_members.items():
            head = members[0]
            subnet_res = subnet_state.get(head.subnet, None)
            if subnet_res is None:
                continue
            subnet_id = subnet_res.attributes.get("subnet_id", "")
            shape = self._compute_mgr.resolve_shape(instance=head)
            image_id = self._image_resolver.resolve(image=head.image)
            topology = "NONE"
            if head.interconnect is not None:
                topology = head.interconnect.topology
            cluster_info = self._cluster_mgr.ensure(
                run_id=run_id, group_name=group_key, shape=shape,
                topology=topology,
                availability_domain=self._region_config.availability_domain,
                subnet_id=subnet_id, image_id=image_id,
                member_count=len(members), default_tags=default_tags,
                aspects=aspects,
            )
            cluster_for_group[group_key] = cluster_info[
                "cluster_network_id"
            ]

        # --- compute instances + volumes ---
        instance_state: Dict[str, ProvisionedResource] = {}
        for inst in spec.instances:
            subnet_res = subnet_state.get(inst.subnet, None)
            if subnet_res is None:
                continue
            subnet_id = subnet_res.attributes.get("subnet_id", "")
            image_id = self._image_resolver.resolve(image=inst.image)

            authorized_keys = self._keypair_mgr.authorized_keys_for(
                name=inst.keypair
            )

            cluster_id: Optional[str] = None
            group_key = _rdma_group_key(instance=inst)
            if group_key is not None:
                cluster_id = cluster_for_group.get(group_key, None)

            authkey: Optional[str] = None
            if inst.vpn_join is not None and self._vpn_control_plane is not None:
                authkey = getattr(self._vpn_control_plane, "minted_authkey",
                                  None)

            existed = self._compute_mgr.find(run_id=run_id,
                                             name=inst.name) is not None
            resource, info = self._compute_mgr.ensure(
                desired=inst, run_id=run_id, subnet_id=subnet_id,
                image_id=image_id, authorized_keys=authorized_keys,
                cluster_network_id=cluster_id, default_tags=default_tags,
                authkey=authkey, aspects=aspects,
            )
            instance_state[inst.name] = resource

            if existed:
                skipped.append(inst.name)
            else:
                created.append(resource)
                if inst.vpn_join is not None:
                    vpn_records.append({
                        "instance_name": inst.name,
                        "instance_id": resource.attributes.get(
                            "instance_id", ""
                        ),
                        "vpn_provider": inst.vpn_join.provider,
                        "vpn_device_id": info.get("vpn_device_id", None),
                    })

        for vol in spec.volumes:
            attach_id: Optional[str] = None
            if vol.attached_to is not None:
                target = instance_state.get(vol.attached_to, None)
                if target is not None:
                    attach_id = target.attributes.get("instance_id", "")

            existed = self._volume_mgr.find(run_id=run_id,
                                            name=vol.name) is not None
            resource = self._volume_mgr.ensure(
                desired=vol, run_id=run_id, default_tags=default_tags,
                attach_instance_id=attach_id, aspects=aspects,
            )
            if existed:
                skipped.append(vol.name)
            else:
                created.append(resource)

        # --- shared filesystems (attach-only) ---
        for sfs in spec.shared_filesystems:
            resource = self._fs_mgr.attach(desired=sfs, aspects=aspects)
            created.append(resource)

        # --- object storage + dns ---
        for bucket in spec.buckets:
            existed = self._bucket_mgr.find(run_id=run_id,
                                            name=bucket.name) is not None
            resource = self._bucket_mgr.ensure(
                desired=bucket, run_id=run_id, default_tags=default_tags,
                aspects=aspects,
            )
            if existed:
                skipped.append(bucket.name)
            else:
                created.append(resource)

        for record in spec.dns_records:
            resource = self._dns_mgr.ensure(
                desired=record, run_id=run_id, aspects=aspects,
            )
            created.append(resource)

        self._last_vpn_records = vpn_records

        rtnval = ProvisioningResult(created=created, updated=updated,
                                    skipped=skipped, errors=[])
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Destroy every owned resource in reverse dependency order.

            :param aspects: ProvisioningAspects.
        """
        run_id = self._run_id(aspects=aspects)

        # 1. DNS records — undo upserts.
        if self._spec is not None:
            for record in self._spec.dns_records:
                self._dns_mgr.destroy_record(desired=record, aspects=aspects)

        # 2. Object Storage buckets.
        self._bucket_mgr.destroy(run_id=run_id, aspects=aspects)

        # 3. Block Volumes.
        self._volume_mgr.destroy(run_id=run_id, aspects=aspects)

        # 4. Instances — capture vpn device ids first.
        terminated = self._compute_mgr.destroy(run_id=run_id,
                                               aspects=aspects)

        # 5. VPN control-plane device cleanup.
        if self._vpn_control_plane is not None:
            for record in self._last_vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(
                    vpn_control_plane=self._vpn_control_plane,
                    device_id=device_id, aspects=aspects)
            for record in terminated:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(
                    vpn_control_plane=self._vpn_control_plane,
                    device_id=device_id, aspects=aspects)

        # 6. RDMA cluster networks.
        self._cluster_mgr.destroy(run_id=run_id, aspects=aspects)

        # 7. Security Lists.
        self._seclist_mgr.destroy(run_id=run_id, aspects=aspects)

        # 8. Subnets.
        self._subnet_mgr.destroy(run_id=run_id, aspects=aspects)

        # 9. Route tables.
        self._route_mgr.destroy(run_id=run_id, aspects=aspects)

        # 10. Internet Gateways.
        self._igw_mgr.destroy(run_id=run_id, aspects=aspects)

        # 11. VCNs.
        self._vcn_mgr.destroy(run_id=run_id, aspects=aspects)

        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any = None) -> List[ProvisionedResource]:
        """
            Enumerate owned resources for the run.

            :param aspects: ProvisioningAspects.

            :returns: A list of ProvisionedResource entries.
        """
        run_id = self._run_id(aspects=aspects)
        out: List[ProvisionedResource] = []
        out.extend(self._vcn_mgr.list_owned(run_id=run_id))
        out.extend(self._subnet_mgr.list_owned(run_id=run_id))
        out.extend(self._seclist_mgr.list_owned(run_id=run_id))
        out.extend(self._compute_mgr.list_owned(run_id=run_id))
        out.extend(self._volume_mgr.list_owned(run_id=run_id))
        out.extend(self._bucket_mgr.list_owned(run_id=run_id))
        rtnval = out
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance.

            :param instance_name: Neutral instance name.
            :param device_id: Provider-assigned device id.
        """
        for record in self._last_vpn_records:
            if record.get("instance_name", "") == instance_name:
                record["vpn_device_id"] = device_id
                return
        self._last_vpn_records.append({
            "instance_name": instance_name,
            "vpn_device_id": device_id,
        })
        return

    @property
    def last_vpn_records(self) -> List[Dict[str, Any]]:
        """
            Return the recorded VPN device records from the last apply.

            :returns: A defensive copy of the records.
        """
        rtnval = [dict(entry) for entry in self._last_vpn_records]
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
        rtnval = "oci-{}".format(self._venue.name)
        return rtnval
