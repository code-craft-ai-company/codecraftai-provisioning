"""
    .. module:: googlecloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GoogleCloudProvisioner — concrete CloudProvisioner for GCP.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import ipaddress
import os

from typing import Any, Dict, List, Optional, Union

from ccai.credentials.gcpserviceaccountkeycredential import (
    GcpServiceAccountKeyCredential
)
from ccai.credentials.gcpworkloadidentitycredential import (
    GcpWorkloadIdentityCredential
)
from ccai.provisioning.model.cloud.cloudacceleratorcatalog import (
    CloudAcceleratorCatalog, default_accelerator_catalog
)
from ccai.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.model.cloud.plannedaction import PlannedAction
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
from ccai.provisioning.model.exceptions import SchemaSemanticError
from ccai.provisioning.venues.vpncleanup import delete_vpn_device

from ccai.provisioning.venues.google.gcperrors import GcpValidationError
from ccai.provisioning.venues.google.gcpregionconfig import GcpRegionConfig
from ccai.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory
)
from ccai.provisioning.venues.google.gcpspec import GcpSpec
from ccai.provisioning.venues.google.gcptagging import (
    GCP_LABEL_KEY_MAX, GCP_LABEL_VALUE_MAX
)
from ccai.provisioning.venues.google.resources.bucketmanager import (
    BucketManager
)
from ccai.provisioning.venues.google.resources.diskmanager import (
    DiskManager
)
from ccai.provisioning.venues.google.resources.dnsmanager import DnsManager
from ccai.provisioning.venues.google.resources.firewallmanager import (
    FirewallManager
)
from ccai.provisioning.venues.google.resources.instancemanager import (
    InstanceManager, is_a3_machine_type
)
from ccai.provisioning.venues.google.resources.networkmanager import (
    NetworkManager
)
from ccai.provisioning.venues.google.resources.placement import (
    PlacementManager
)
from ccai.provisioning.venues.google.resources.subnetmanager import (
    SubnetManager, _region_of_zone
)
from ccai.provisioning.venues.google.resources.tpunodemanager import (
    TpuNodeManager, is_tpu_instance
)


_UNSUPPORTED_FS_KINDS = frozenset({"WEKA", "VAST", "GPFS", "BEEGFS",
                                   "VENUE_NATIVE", "EFS", "AZUREFILES"})

_REJECTED_INTERCONNECTS = frozenset({"INFINIBAND_HDR", "INFINIBAND_NDR",
                                     "INFINIBAND_XDR", "OCI_RDMA"})

_GcpCredential = Union[GcpServiceAccountKeyCredential,
                       GcpWorkloadIdentityCredential]


def _all_tags_of(spec: GcpSpec) -> List[Dict[str, str]]:
    """
        Flatten every tag dict declared anywhere in a GcpSpec.

        :param spec: The GcpSpec.

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


class GoogleCloudProvisioner(CloudProvisioner):
    """
        GCP-venue concrete :class:`CloudProvisioner` implementation.

        Composes the per-resource managers behind the five-verb lifecycle.
        The spec is a :class:`GcpSpec` bundle of neutral resource objects.

        The defining structural choice for GCP is the project as the apex
        container — every resource is scoped to a project, and the
        ``ccai_owner`` label is the per-run discriminator inside it.
        TPU resources are a distinct resource type, not a VM accelerator:
        a :class:`CloudInstance` whose first accelerator has ``kind=TPU`` is
        branched to the TPU apply path.
    """

    VENUE_NAME: str = "gcp"

    def __init__(self, *, venue: CloudVenue,
                 credential: _GcpCredential,
                 region_config: GcpRegionConfig,
                 spec: Optional[GcpSpec] = None,
                 catalog: Optional[CloudAcceleratorCatalog] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a GoogleCloudProvisioner.

            :param venue: CloudVenue.
            :param credential: GCP service-account-key or workload-identity
                               credential.
            :param region_config: GcpRegionConfig.
            :param spec: Optional GcpSpec.
            :param catalog: Optional accelerator catalog (defaults to the
                            packaged singleton).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                                      destroy uses this to de-register
                                      Tailscale / Twingate devices.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: _GcpCredential = credential
        self._region_config: GcpRegionConfig = region_config
        self._session_factory: GcpSessionFactory = GcpSessionFactory(
            credential=credential, region_config=region_config
        )
        if catalog is not None:
            self._catalog: CloudAcceleratorCatalog = catalog
        else:
            self._catalog = default_accelerator_catalog()

        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        self._network_mgr: NetworkManager = NetworkManager(
            session_factory=self._session_factory
        )
        self._subnet_mgr: SubnetManager = SubnetManager(
            session_factory=self._session_factory
        )
        self._firewall_mgr: FirewallManager = FirewallManager(
            session_factory=self._session_factory
        )
        self._placement_mgr: PlacementManager = PlacementManager(
            session_factory=self._session_factory
        )
        self._instance_mgr: InstanceManager = InstanceManager(
            session_factory=self._session_factory, catalog=self._catalog
        )
        self._tpu_mgr: TpuNodeManager = TpuNodeManager(
            session_factory=self._session_factory, catalog=self._catalog
        )
        self._disk_mgr: DiskManager = DiskManager(
            session_factory=self._session_factory
        )
        self._bucket_mgr: BucketManager = BucketManager(
            session_factory=self._session_factory
        )
        self._dns_mgr: DnsManager = DnsManager(
            session_factory=self._session_factory
        )

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    @property
    def session_factory(self) -> GcpSessionFactory:
        """
            Return the bound GcpSessionFactory.

            :returns: The GcpSessionFactory.
        """
        rtnval = self._session_factory
        return rtnval

    @classmethod
    def supports_preemption(cls) -> bool:
        """
            GCP offers Preemptible / Spot VMs, so this venue can preempt
            instances.

            :returns: True.
        """
        rtnval = True
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the GcpSpec without any Google API calls.

            :param aspects: ProvisioningAspects (or compatible).

            :returns: A ValidationResult with ok=True on success.
            :raises: GcpValidationError
        """
        if not isinstance(self._credential,
                          (GcpServiceAccountKeyCredential,
                           GcpWorkloadIdentityCredential)):
            err_msg_lines = [
                "GoogleCloudProvisioner requires a GCP credential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        network_cidrs: Dict[str, str] = {}
        for net in spec.networks:
            network_cidrs[net.name] = net.cidr

        # Name-reference sets used to reject dangling references: a spec that
        # points an instance at a nonexistent subnet (or a firewall at a
        # nonexistent network) must fail validate() rather than silently drop
        # the resource at apply and still report success.
        network_names = {net.name for net in spec.networks}
        subnet_names = {subnet.name for subnet in spec.subnets}
        security_group_names = {sg.name for sg in spec.security_groups}

        for sg in spec.security_groups:
            if sg.network not in network_names:
                errors.append({
                    "resource": sg.name,
                    "error": ("Security group references unknown network: "
                              "{}.").format(sg.network),
                })

        # Shared FS kind acceptance.
        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("GCP realises shared-FS through Filestore or "
                              "Parallelstore.  Substitute kind=LUSTRE "
                              "(Parallelstore) or kind=FILESTORE for "
                              "{}.").format(sfs.kind),
                })
            elif sfs.kind in ("LUSTRE", "FILESTORE"):
                if sfs.existing_id is None or len(sfs.existing_id) == 0:
                    errors.append({
                        "resource": sfs.name,
                        "error": ("GCP shared-FS v1 supports attach-only; "
                                  "set existing_id (Parallelstore for "
                                  "LUSTRE, Filestore for FILESTORE)."),
                    })

        # Load balancers are deferred to v1.5.
        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": "GCLB provisioning is deferred to v1.5.",
            })

        # Per-instance: interconnect / accelerator / TPU / placement checks.
        compact_groups: Dict[str, List[str]] = {}
        for instance in spec.instances:
            if instance.subnet not in subnet_names:
                errors.append({
                    "resource": instance.name,
                    "error": ("Instance references unknown subnet: "
                              "{}.").format(instance.subnet),
                })

            declared_sgs = (
                instance.security_groups
                if instance.security_groups is not None else []
            )
            for sg_ref in declared_sgs:
                if sg_ref not in security_group_names:
                    errors.append({
                        "resource": instance.name,
                        "error": ("Instance references unknown security "
                                  "group: {}.").format(sg_ref),
                    })

            if instance.interconnect is not None:
                kind = instance.interconnect.kind
                if kind == "EFA":
                    errors.append({
                        "resource": instance.name,
                        "error": ("EFA is AWS-only; GCP exposes compact "
                                  "placement policy and GPUDirect-TCPX/RDMA, "
                                  "not EFA."),
                    })
                elif kind in _REJECTED_INTERCONNECTS:
                    errors.append({
                        "resource": instance.name,
                        "error": ("GCP uses compact placement, not "
                                  "InfiniBand fabric; got {}.").format(kind),
                    })

            zone = instance.subnet
            # Resolve the instance's zone from its subnet.
            for subnet in spec.subnets:
                if subnet.name == instance.subnet:
                    zone = subnet.zone

            is_tpu = is_tpu_instance(instance=instance)
            if is_tpu is True:
                accelerators = (
                    instance.accelerators
                    if instance.accelerators is not None else []
                )
                first = accelerators[0]
                if first.model is None or len(first.model) == 0:
                    errors.append({
                        "resource": instance.name,
                        "error": ("TPU resource requires accelerator model "
                                  "(e.g. TPU_V5P)."),
                    })
                else:
                    try:
                        self._tpu_mgr.resolve_tpu_type(instance=instance)
                    except GcpValidationError as xcpt:
                        errors.append({
                            "resource": instance.name,
                            "error": str(xcpt),
                        })
                # TPU nodes attach to a subnet via the VPC; certain models
                # reject VPC attachment.  v1 model accepts subnet for v5.
                continue

            # GPU resolution / size conflict.
            accelerators = (
                instance.accelerators
                if instance.accelerators is not None else []
            )
            gpu_accels = [a for a in accelerators if a.kind == "GPU"]
            resolved_type: Optional[str] = None
            if len(gpu_accels) > 0:
                first = gpu_accels[0]
                try:
                    sku = self._catalog.resolve(
                        neutral_name=first.model, venue=self.VENUE_NAME
                    )
                    resolved_type = sku
                except SchemaSemanticError as xcpt:
                    errors.append({
                        "resource": instance.name,
                        "error": "Accelerator not on GCP: {}".format(xcpt),
                    })

                if resolved_type is not None:
                    if instance.size is not None and len(instance.size) > 0:
                        if (instance.size != resolved_type
                                and instance.size != first.model):
                            errors.append({
                                "resource": instance.name,
                                "error": ("Instance.size {!r} conflicts with "
                                          "resolved accelerator SKU "
                                          "{!r}.").format(
                                              instance.size, resolved_type
                                          ),
                            })

            if resolved_type is None:
                resolved_type = instance.size

            # Compact-placement group tracking + zone capability check.
            if instance.interconnect is not None:
                topology = instance.interconnect.topology
                if topology in ("RAIL_OPTIMIZED", "FAT_TREE", "DRAGONFLY"):
                    group_key = (
                        instance.placement_group
                        if instance.placement_group is not None
                        else instance.name
                    )
                    compact_groups.setdefault(group_key, []).append(
                        instance.name
                    )
                    if is_a3_machine_type(machine_type=resolved_type):
                        if not self._region_config.\
                                zone_supports_compact_placement(zone=zone):
                            errors.append({
                                "resource": instance.name,
                                "error": ("Zone {!r} does not support "
                                          "compact placement for the A3 "
                                          "family.").format(zone),
                            })

        # Label length checks on every declared resource.
        for entry in _all_tags_of(spec=spec):
            for key, value in entry.items():
                if len(key) > GCP_LABEL_KEY_MAX:
                    errors.append({
                        "resource": "<labels>",
                        "error": "Label key exceeds 63 chars: {!r}".format(
                            key
                        ),
                    })
                if len(value) > GCP_LABEL_VALUE_MAX:
                    errors.append({
                        "resource": "<labels>",
                        "error": "Label value exceeds 63 chars: key={}.".format(
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
            err_msg_lines = ["GoogleCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise GcpValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE/DELETE plan.

            Performs read-only ``get`` probes; no mutation.

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
            existing = self._network_mgr.find(run_id=run_id, name=net.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=net.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=net.name,
                ))

        for subnet in spec.subnets:
            existing = self._subnet_mgr.find(run_id=run_id,
                                             name=subnet.name,
                                             zone=subnet.zone)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="subnet", resource_name=subnet.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="subnet", resource_name=subnet.name,
                ))

        for sg in spec.security_groups:
            existing = self._firewall_mgr.find(run_id=run_id, name=sg.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="firewall", resource_name=sg.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="firewall", resource_name=sg.name,
                ))

        for inst in spec.instances:
            zone = self._zone_for_instance(spec=spec, instance=inst)
            if is_tpu_instance(instance=inst):
                exists = self._tpu_mgr.plan_exists(run_id=run_id,
                                                   name=inst.name,
                                                   zone=zone)
                kind = "tpu"
            else:
                exists = self._instance_mgr.find(
                    run_id=run_id, name=inst.name, zone=zone
                ) is not None
                kind = "instance"
            if exists is False:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind=kind, resource_name=inst.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind=kind, resource_name=inst.name,
                ))

        for vol in spec.volumes:
            existing = self._disk_mgr.find(run_id=run_id, name=vol.name,
                                           zone=self._region_config.zone)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="volume", resource_name=vol.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="volume", resource_name=vol.name,
                ))

        for bucket in spec.buckets:
            existing = self._bucket_mgr.find(run_id=run_id,
                                             name=bucket.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="bucket", resource_name=bucket.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="bucket", resource_name=bucket.name,
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

        # Owned-orphan scan: any resource still tagged ccai:owner=<run_id>
        # that no longer appears in the desired spec is an orphan and is
        # planned for DELETE.  Mirrors the AWS venue's approach so that drift
        # is surfaced up front.
        orphan_actions = self._plan_owned_orphans(run_id=run_id, spec=spec)
        for action in orphan_actions:
            actions.append(action)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_owned_orphans(self, *, run_id: str, spec: GcpSpec
                            ) -> List[PlannedAction]:
        """
            Build DELETE actions for owner-tagged resources absent from spec.

            Enumerates the run's owned GCP resources through each per-kind
            manager's ``list_owned`` and emits a ``DELETE`` PlannedAction for
            every resource whose ``(kind, name)`` pair is not declared in the
            desired spec.

            :param run_id: The provisioning run identifier.
            :param spec: The desired GcpSpec.

            :returns: A list of DELETE PlannedAction entries.
        """
        zone = self._region_config.zone
        region = self._region_config.region

        # Instances and TPU nodes both originate from spec.instances; the
        # owned-resource kind is "instance" or "tpu" depending on the node.
        instance_names = {inst.name for inst in spec.instances}
        desired_by_kind: Dict[str, set] = {
            "network": {net.name for net in spec.networks},
            "subnet": {subnet.name for subnet in spec.subnets},
            "firewall": {sg.name for sg in spec.security_groups},
            "instance": instance_names,
            "tpu": instance_names,
            "volume": {vol.name for vol in spec.volumes},
            "bucket": {bucket.name for bucket in spec.buckets},
        }

        owned: List[ProvisionedResource] = []
        owned.extend(self._network_mgr.list_owned(run_id=run_id))
        owned.extend(self._subnet_mgr.list_owned(run_id=run_id,
                                                 region=region))
        owned.extend(self._firewall_mgr.list_owned(run_id=run_id))
        owned.extend(self._instance_mgr.list_owned(run_id=run_id, zone=zone))
        owned.extend(self._tpu_mgr.list_owned(run_id=run_id, zone=zone))
        owned.extend(self._disk_mgr.list_owned(run_id=run_id, zone=zone))
        owned.extend(self._bucket_mgr.list_owned(run_id=run_id))

        out: List[PlannedAction] = []
        for resource in owned:
            declared = desired_by_kind.get(resource.kind, set())
            if resource.name in declared:
                continue
            out.append(self._planned_action_for(
                intent=PlannedActionIntent.DELETE,
                resource_kind=resource.kind, resource_name=resource.name,
                diff={"reason": ("Owner-tagged resource is absent from the "
                                 "desired spec."),
                      "venue_id": resource.venue_id},
            ))

        rtnval = out
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: network → subnet → firewall → instance → PD → TPU →
            GCS → DNS.

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
        errors: List[Dict[str, Any]] = []
        vpn_records: List[Dict[str, Any]] = []

        spec = self._spec

        # --- networking ---
        network_state: Dict[str, ProvisionedResource] = {}
        for net in spec.networks:
            existed = self._network_mgr.find(
                run_id=run_id, name=net.name
            ) is not None
            resource = self._network_mgr.ensure(
                desired=net, run_id=run_id, default_tags=default_tags,
                aspects=aspects,
            )
            network_state[net.name] = resource
            if existed:
                skipped.append(net.name)
            else:
                created.append(resource)

        subnet_state: Dict[str, ProvisionedResource] = {}
        for subnet in spec.subnets:
            parent = network_state.get(subnet.network, None)
            if parent is None:
                errors.append({
                    "resource": subnet.name,
                    "error": ("Subnet references unknown network {!r}; not "
                              "created.").format(subnet.network),
                })
                continue
            network_link = parent.attributes.get("self_link", "")
            existed = self._subnet_mgr.find(
                run_id=run_id, name=subnet.name, zone=subnet.zone
            ) is not None
            resource = self._subnet_mgr.ensure(
                desired=subnet, run_id=run_id,
                network_self_link=network_link,
                default_tags=default_tags, aspects=aspects,
            )
            subnet_state[subnet.name] = resource
            if existed:
                skipped.append(subnet.name)
            else:
                created.append(resource)

        # --- firewall ---
        for sg in spec.security_groups:
            parent = network_state.get(sg.network, None)
            if parent is None:
                errors.append({
                    "resource": sg.name,
                    "error": ("Security group references unknown network "
                              "{!r}; firewall not created.").format(sg.network),
                })
                continue
            network_link = parent.attributes.get("self_link", "")
            existed = self._firewall_mgr.find(
                run_id=run_id, name=sg.name
            ) is not None
            resource = self._firewall_mgr.ensure(
                desired=sg, run_id=run_id,
                network_self_link=network_link,
                default_tags=default_tags, aspects=aspects,
            )
            if existed:
                skipped.append(sg.name)
            else:
                created.append(resource)

        # --- compute (instance / TPU) ---
        # Compute compact-placement groups first.
        compact_members = self._compact_placement_members(spec=spec)
        placement_for: Dict[str, str] = {}
        for group_key, members in compact_members.items():
            if len(members) < 1:
                continue
            sample = members[0]
            zone = self._zone_for_instance(spec=spec, instance=sample)
            region = _region_of_zone(zone=zone)
            policy_name = self._placement_mgr.ensure(
                run_id=run_id, logical_name=group_key, region=region,
                default_tags=default_tags, aspects=aspects,
            )
            for member in members:
                placement_for[member.name] = policy_name

        instance_state: Dict[str, ProvisionedResource] = {}
        for inst in spec.instances:
            zone = self._zone_for_instance(spec=spec, instance=inst)
            region = _region_of_zone(zone=zone)

            if is_tpu_instance(instance=inst):
                existed = self._tpu_mgr.find(
                    run_id=run_id, name=inst.name, zone=zone
                ) is not None
                resource = self._tpu_mgr.ensure(
                    desired=inst, run_id=run_id, zone=zone,
                    default_tags=default_tags, aspects=aspects,
                )
                instance_state[inst.name] = resource
                if existed:
                    skipped.append(inst.name)
                else:
                    created.append(resource)
                continue

            subnet_res = subnet_state.get(inst.subnet, None)
            if subnet_res is None:
                errors.append({
                    "resource": inst.name,
                    "error": ("Instance references unresolved subnet {!r}; "
                              "not launched.").format(inst.subnet),
                })
                continue
            subnet_link = subnet_res.attributes.get("self_link", "")
            parent_net = None
            for net_name, net_res in network_state.items():
                for subnet in spec.subnets:
                    if (subnet.name == inst.subnet
                            and subnet.network == net_name):
                        parent_net = net_res
            network_link = (
                parent_net.attributes.get("self_link", "")
                if parent_net is not None else ""
            )

            authkey: Optional[str] = None
            if (inst.vpn_join is not None
                    and self._vpn_control_plane is not None):
                authkey = getattr(self._vpn_control_plane,
                                  "minted_authkey", None)

            existed = self._instance_mgr.find(
                run_id=run_id, name=inst.name, zone=zone
            ) is not None
            resource, info = self._instance_mgr.ensure(
                desired=inst, run_id=run_id, zone=zone,
                subnet_self_link=subnet_link,
                network_self_link=network_link,
                default_tags=default_tags, authkey=authkey,
                placement_policy_name=placement_for.get(inst.name, None),
                region=region, aspects=aspects,
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

        # --- persistent disks ---
        for vol in spec.volumes:
            zone = self._region_config.zone
            existed = self._disk_mgr.find(
                run_id=run_id, name=vol.name, zone=zone
            ) is not None
            resource = self._disk_mgr.ensure(
                desired=vol, run_id=run_id, zone=zone,
                default_tags=default_tags, aspects=aspects,
            )
            if existed:
                skipped.append(vol.name)
            else:
                created.append(resource)

        # --- storage + dns ---
        for bucket in spec.buckets:
            existed = self._bucket_mgr.find(
                run_id=run_id, name=bucket.name
            ) is not None
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
                                    skipped=skipped, errors=errors)
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
        zone = self._region_config.zone
        region = self._region_config.region

        # 1. DNS records.
        if self._spec is not None:
            for record in self._spec.dns_records:
                self._dns_mgr.destroy_record(desired=record, aspects=aspects)

        # 2. Buckets.
        self._bucket_mgr.destroy(run_id=run_id, aspects=aspects)

        # 3. Persistent disks.
        self._disk_mgr.destroy(run_id=run_id, zone=zone, aspects=aspects)

        # 4. TPU nodes.
        self._tpu_mgr.destroy(run_id=run_id, zone=zone, aspects=aspects)

        # 5. Instances.
        terminated = self._instance_mgr.destroy(run_id=run_id, zone=zone,
                                                aspects=aspects)

        # 6. VPN control-plane device cleanup.
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

        # 7. Compact-placement ResourcePolicies.
        self._placement_mgr.destroy(run_id=run_id, region=region,
                                    aspects=aspects)

        # 8. Firewall rules.
        self._firewall_mgr.destroy(run_id=run_id, aspects=aspects)

        # 9. Subnetworks.
        self._subnet_mgr.destroy(run_id=run_id, region=region,
                                 aspects=aspects)

        # 10. VPC networks.
        self._network_mgr.destroy(run_id=run_id, aspects=aspects)

        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate owned resources for the run.

            :param aspects: ProvisioningAspects.

            :returns: A list of ProvisionedResource entries.
        """
        run_id = self._run_id(aspects=aspects)
        zone = self._region_config.zone
        region = self._region_config.region
        out: List[ProvisionedResource] = []
        out.extend(self._network_mgr.list_owned(run_id=run_id))
        out.extend(self._subnet_mgr.list_owned(run_id=run_id, region=region))
        out.extend(self._firewall_mgr.list_owned(run_id=run_id))
        out.extend(self._instance_mgr.list_owned(run_id=run_id, zone=zone))
        out.extend(self._tpu_mgr.list_owned(run_id=run_id, zone=zone))
        out.extend(self._disk_mgr.list_owned(run_id=run_id, zone=zone))
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

    def _zone_for_instance(self, *, spec: GcpSpec,
                           instance: Any) -> str:
        """
            Resolve the zone an instance launches in via its subnet.

            :param spec: The GcpSpec.
            :param instance: The CloudInstance.

            :returns: The zone string (falls back to the config default).
        """
        for subnet in spec.subnets:
            if subnet.name == instance.subnet:
                rtnval = subnet.zone
                return rtnval
        rtnval = self._region_config.zone
        return rtnval

    def _compact_placement_members(self, *, spec: GcpSpec
                                   ) -> Dict[str, List[Any]]:
        """
            Group instances that should share a compact ResourcePolicy.

            Membership is keyed by ``placement_group`` (or the interconnect
            topology being a tightly-coupled topology with a shared group).

            :param spec: The GcpSpec.

            :returns: A dict mapping group key to member instances.
        """
        groups: Dict[str, List[Any]] = {}
        for instance in spec.instances:
            if is_tpu_instance(instance=instance):
                continue
            if instance.interconnect is None:
                continue
            topology = instance.interconnect.topology
            if topology not in ("RAIL_OPTIMIZED", "FAT_TREE", "DRAGONFLY"):
                continue
            group_key = (
                instance.placement_group
                if instance.placement_group is not None
                else instance.name
            )
            groups.setdefault(group_key, []).append(instance)
        rtnval = groups
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
        rtnval = "gcp-{}".format(self._venue.name)
        return rtnval
