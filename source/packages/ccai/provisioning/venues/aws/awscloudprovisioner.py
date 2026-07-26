"""
    .. module:: awscloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AwsCloudProvisioner — concrete CloudProvisioner for AWS.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import ipaddress
import os

from typing import Any, Dict, List, Optional

from ccai.credentials.awsaccesskeycredential import AwsAccessKeyCredential
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
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.venues.vpncleanup import delete_vpn_device

from ccai.provisioning.venues.aws.awsboto3sessionfactory import (
    AwsBoto3SessionFactory
)
from ccai.provisioning.venues.aws.awserrors import AwsValidationError
from ccai.provisioning.venues.aws.awsregionconfig import AwsRegionConfig
from ccai.provisioning.venues.aws.awsspec import AwsSpec
from ccai.provisioning.venues.aws.awstagging import (
    AWS_TAG_VALUE_MAX, AWS_TAG_KEY_MAX
)
from ccai.provisioning.venues.aws.resources.bucketmanager import (
    BucketManager
)
from ccai.provisioning.venues.aws.resources.dnsmanager import DnsManager
from ccai.provisioning.venues.aws.resources.fsxmanager import FsxManager
from ccai.provisioning.venues.aws.resources.imageresolver import (
    ImageResolver
)
from ccai.provisioning.venues.aws.resources.instancemanager import (
    InstanceManager, is_efa_capable
)
from ccai.provisioning.venues.aws.resources.keypairmanager import (
    KeyPairManager
)
from ccai.provisioning.venues.aws.resources.networkmanager import (
    NetworkManager
)
from ccai.provisioning.venues.aws.resources.placementgroupmanager import (
    PlacementGroupManager
)
from ccai.provisioning.venues.aws.resources.securitygroupmanager import (
    SecurityGroupManager
)
from ccai.provisioning.venues.aws.resources.subnetmanager import (
    SubnetManager
)
from ccai.provisioning.venues.aws.resources.volumemanager import (
    VolumeManager
)


_UNSUPPORTED_FS_KINDS = frozenset({"WEKA", "VAST", "GPFS", "BEEGFS",
                                   "VENUE_NATIVE"})

_REJECTED_INTERCONNECTS = frozenset({"INFINIBAND_HDR", "INFINIBAND_NDR",
                                     "INFINIBAND_XDR", "OCI_RDMA"})


def _all_tags_of(spec: AwsSpec) -> List[Dict[str, str]]:
    """
        Flatten every tag dict declared anywhere in an AwsSpec.

        :param spec: The AwsSpec.

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


class AwsCloudProvisioner(CloudProvisioner):
    """
        AWS-venue concrete :class:`CloudProvisioner` implementation.

        Composes the per-resource managers behind a five-verb lifecycle.
        The spec is an :class:`AwsSpec` bundle of neutral resource objects.
    """

    VENUE_NAME: str = "aws"

    def __init__(self, *, venue: CloudVenue,
                 credential: AwsAccessKeyCredential,
                 region_config: AwsRegionConfig,
                 spec: Optional[AwsSpec] = None,
                 catalog: Optional[CloudAcceleratorCatalog] = None,
                 vpn_control_plane: Optional[Any] = None,
                 session_factory: Optional[Any] = None) -> None:
        """
            Construct an AwsCloudProvisioner.

            :param venue: CloudVenue.
            :param credential: AwsAccessKeyCredential used to sign requests.
            :param region_config: AwsRegionConfig.
            :param spec: Optional AwsSpec.
            :param catalog: Optional accelerator catalog (defaults to the
                            packaged singleton).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                                      destroy uses this to de-register
                                      Tailscale / Twingate devices.
            :param session_factory: Optional pre-built session factory,
                                    carrying injected service clients.  This
                                    is the seam every other venue in this
                                    package already has, and the one the AWS
                                    tests need in order to stop mocking at
                                    the SDK layer.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: AwsAccessKeyCredential = credential
        self._region_config: AwsRegionConfig = region_config
        if session_factory is not None:
            self._session_factory: Any = session_factory
        else:
            self._session_factory = AwsBoto3SessionFactory(
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
        self._sg_mgr: SecurityGroupManager = SecurityGroupManager(
            session_factory=self._session_factory
        )
        self._keypair_mgr: KeyPairManager = KeyPairManager(
            session_factory=self._session_factory
        )
        self._image_resolver: ImageResolver = ImageResolver(
            session_factory=self._session_factory
        )
        self._placement_mgr: PlacementGroupManager = PlacementGroupManager(
            session_factory=self._session_factory
        )
        self._instance_mgr: InstanceManager = InstanceManager(
            session_factory=self._session_factory,
            image_resolver=self._image_resolver,
            placement_manager=self._placement_mgr,
            catalog=self._catalog,
        )
        self._volume_mgr: VolumeManager = VolumeManager(
            session_factory=self._session_factory
        )
        self._bucket_mgr: BucketManager = BucketManager(
            session_factory=self._session_factory
        )
        self._dns_mgr: DnsManager = DnsManager(
            session_factory=self._session_factory
        )
        self._fsx_mgr: FsxManager = FsxManager(
            session_factory=self._session_factory
        )

        # Tracked across apply / destroy.
        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    @classmethod
    def supports_preemption(cls) -> bool:
        """
            AWS offers Spot Instances, so this venue can preempt instances.

            :returns: True.
        """
        rtnval = True
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the AwsSpec without any boto3 calls.

            :param aspects: ProvisioningAspects (or compatible).

            :returns: A ValidationResult with ok=True on success.
            :raises: SchemaSemanticError, AwsValidationError
        """
        if not isinstance(self._credential, AwsAccessKeyCredential):
            err_msg_lines = [
                "AwsCloudProvisioner requires an AwsAccessKeyCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(type(self._credential).__name__))
            err_msg = os.linesep.join(err_msg_lines)
            raise AwsValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        # Pre-collect names for cross-resource refs.
        network_cidrs: Dict[str, str] = {}
        for net in spec.networks:
            network_cidrs[net.name] = net.cidr

        # Name-reference sets used to reject dangling references: a spec that
        # points an instance at a nonexistent subnet (or a security group at a
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

        # Bucket region check (model already mandates; defensive).
        for bucket in spec.buckets:
            if bucket.region is None or len(bucket.region) == 0:
                errors.append({"resource": bucket.name,
                               "error": "S3 bucket region is required."})

        # Shared FS kind acceptance.
        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("AWS realises shared-FS through FSx for "
                              "Lustre.  Substitute kind=LUSTRE for {}.").format(
                                  sfs.kind
                              ),
                })
            elif sfs.kind == "LUSTRE":
                if sfs.existing_id is None or len(sfs.existing_id) == 0:
                    errors.append({
                        "resource": sfs.name,
                        "error": ("FSx for Lustre v1 supports attach-only; "
                                  "set existing_id."),
                    })

        # Per-instance: interconnect + accelerator + EFA family check.
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
                if instance.interconnect.kind in _REJECTED_INTERCONNECTS:
                    errors.append({
                        "resource": instance.name,
                        "error": ("AWS exposes only EFA for HPC "
                                  "interconnect; got {}.").format(
                                      instance.interconnect.kind
                                  ),
                    })

            # Accelerator resolution + size conflict.
            accelerators = instance.accelerators if instance.accelerators is not None else []
            resolved_type: Optional[str] = None
            if len(accelerators) > 0:
                first = accelerators[0]
                sku: Optional[str] = None
                try:
                    sku = self._catalog.resolve(
                        neutral_name=first.model, venue=self.VENUE_NAME
                    )
                except SchemaSemanticError as xcpt:
                    errors.append({
                        "resource": instance.name,
                        "error": "Accelerator not on AWS: {}".format(xcpt),
                    })

                if sku is not None:
                    resolved_type = sku
                    if instance.size is not None and len(instance.size) > 0:
                        if instance.size != sku and instance.size != first.model:
                            errors.append({
                                "resource": instance.name,
                                "error": ("Instance.size {!r} conflicts "
                                          "with resolved accelerator SKU "
                                          "{!r}.").format(instance.size, sku),
                            })

            if resolved_type is None:
                resolved_type = instance.size

            # EFA must run on EFA-capable family.
            if instance.interconnect is not None and instance.interconnect.kind == "EFA":
                if not is_efa_capable(instance_type=resolved_type):
                    errors.append({
                        "resource": instance.name,
                        "error": ("EFA requested but instance family is "
                                  "not EFA-capable: {}.").format(resolved_type),
                    })

        # Tag value length check on every declared resource.
        for entry in _all_tags_of(spec=spec):
            for key, value in entry.items():
                if len(key) > AWS_TAG_KEY_MAX:
                    errors.append({
                        "resource": "<tags>",
                        "error": "Tag key exceeds 128 chars: {!r}".format(key),
                    })
                if len(value) > AWS_TAG_VALUE_MAX:
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
                    "error": "Subnet/Network CIDR parse error: {}.".format(xcpt),
                })

        if len(errors) > 0:
            err_msg_lines = ["AwsCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise AwsValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE/DELETE plan.

            Performs read-only describes; no mutation.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        spec = self._spec
        actions = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        # Networks.
        for net in spec.networks:
            existing = self._network_mgr.find(run_id=run_id, name=net.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=net.name,
                ))
            elif self._network_mgr.matches(existing=existing, desired=net):
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=net.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="network", resource_name=net.name,
                    diff={"before": {"cidr": existing.get("CidrBlock", "")},
                          "after": {"cidr": net.cidr}},
                ))

        # Subnets.
        for subnet in spec.subnets:
            existing = self._subnet_mgr.find(run_id=run_id, name=subnet.name)
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

        # Security groups.
        for sg in spec.security_groups:
            existing = self._sg_mgr.find(run_id=run_id, name=sg.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="sg", resource_name=sg.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="sg", resource_name=sg.name,
                ))

        # Key pairs.
        for kp in spec.keypairs:
            existing = self._keypair_mgr.find(run_id=run_id, name=kp.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="keypair", resource_name=kp.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="keypair", resource_name=kp.name,
                ))

        # Instances.
        for inst in spec.instances:
            existing = self._instance_mgr.find(run_id=run_id, name=inst.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance", resource_name=inst.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="instance", resource_name=inst.name,
                ))

        # Volumes.
        for vol in spec.volumes:
            existing = self._volume_mgr.find(run_id=run_id, name=vol.name)
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

        # Buckets.
        for bucket in spec.buckets:
            existing = self._bucket_mgr.find(run_id=run_id, name=bucket.name)
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

        # DNS records (no read-side check in v1; emit CREATE every plan).
        for record in spec.dns_records:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.CREATE,
                resource_kind="dns", resource_name=record.name,
            ))

        # Load balancers are emit-skip until v1.5.
        for lb in spec.load_balancers:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.SKIP,
                resource_kind="lb", resource_name=lb.name,
                diff={"note": "Load balancer apply is deferred to v1.5."},
            ))

        # Owned-orphan scan: any resource still tagged ccai:owner=<run_id>
        # that no longer appears in the desired spec is an orphan and is
        # planned for DELETE.  The destroy path already tears these down by
        # tag; surfacing them in plan makes the drift visible up front.
        orphan_actions = self._plan_owned_orphans(run_id=run_id, spec=spec)
        for action in orphan_actions:
            actions.append(action)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_owned_orphans(self, *, run_id: str, spec: AwsSpec
                            ) -> List[PlannedAction]:
        """
            Build DELETE actions for owner-tagged resources absent from spec.

            Enumerates the run's owned AWS resources through each per-kind
            manager's ``list_owned`` and emits a ``DELETE`` PlannedAction for
            every resource whose ``(kind, name)`` pair is not declared in the
            desired spec.

            :param run_id: The provisioning run identifier.
            :param spec: The desired AwsSpec.

            :returns: A list of DELETE PlannedAction entries.
        """
        desired_by_kind: Dict[str, set] = {
            "network": {net.name for net in spec.networks},
            "subnet": {subnet.name for subnet in spec.subnets},
            "sg": {sg.name for sg in spec.security_groups},
            "keypair": {kp.name for kp in spec.keypairs},
            "instance": {inst.name for inst in spec.instances},
            "volume": {vol.name for vol in spec.volumes},
            "bucket": {bucket.name for bucket in spec.buckets},
        }

        owned: List[ProvisionedResource] = []
        owned.extend(self._network_mgr.list_owned(run_id=run_id))
        owned.extend(self._subnet_mgr.list_owned(run_id=run_id))
        owned.extend(self._sg_mgr.list_owned(run_id=run_id))
        owned.extend(self._keypair_mgr.list_owned(run_id=run_id))
        owned.extend(self._instance_mgr.list_owned(run_id=run_id))
        owned.extend(self._volume_mgr.list_owned(run_id=run_id))
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

            Stages: networking (vpc+subnet+sg+keypair) → compute (instance,
            volume, fsx attach) → dns/storage (bucket, route53).

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
            existed = self._network_mgr.find(run_id=run_id, name=net.name) is not None
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
            vpc_id = parent.attributes.get("vpc_id", "")
            igw_id = parent.attributes.get("igw_id", "")
            existed = self._subnet_mgr.find(run_id=run_id, name=subnet.name) is not None
            resource = self._subnet_mgr.ensure(
                desired=subnet, run_id=run_id, vpc_id=vpc_id,
                igw_id=igw_id, default_tags=default_tags, aspects=aspects,
            )
            subnet_state[subnet.name] = resource
            if existed:
                skipped.append(subnet.name)
            else:
                created.append(resource)

        sg_state: Dict[str, ProvisionedResource] = {}
        for sg in spec.security_groups:
            parent = network_state.get(sg.network, None)
            if parent is None:
                errors.append({
                    "resource": sg.name,
                    "error": ("Security group references unknown network "
                              "{!r}; not created.").format(sg.network),
                })
                continue
            vpc_id = parent.attributes.get("vpc_id", "")
            existed = self._sg_mgr.find(run_id=run_id, name=sg.name) is not None
            resource = self._sg_mgr.ensure(
                desired=sg, run_id=run_id, vpc_id=vpc_id,
                default_tags=default_tags, aspects=aspects,
            )
            sg_state[sg.name] = resource
            if existed:
                skipped.append(sg.name)
            else:
                created.append(resource)

        kp_state: Dict[str, ProvisionedResource] = {}
        for kp in spec.keypairs:
            existed = self._keypair_mgr.find(run_id=run_id, name=kp.name) is not None
            resource = self._keypair_mgr.ensure(
                desired=kp, run_id=run_id, default_tags=default_tags,
                aspects=aspects,
            )
            kp_state[kp.name] = resource
            if existed:
                skipped.append(kp.name)
            else:
                created.append(resource)

        # --- compute ---
        instance_state: Dict[str, ProvisionedResource] = {}
        for inst in spec.instances:
            subnet_res = subnet_state.get(inst.subnet, None)
            if subnet_res is None:
                errors.append({
                    "resource": inst.name,
                    "error": ("Instance references unresolved subnet {!r}; "
                              "not launched.").format(inst.subnet),
                })
                continue
            subnet_id = subnet_res.attributes.get("subnet_id", "")

            sg_ids: List[str] = []
            ref_sgs = inst.security_groups if inst.security_groups is not None else []
            for sg_name in ref_sgs:
                sg_res = sg_state.get(sg_name, None)
                if sg_res is not None:
                    sg_ids.append(sg_res.attributes.get("sg_id", ""))

            keypair_aws_name = None
            if inst.keypair is not None:
                kp_res = kp_state.get(inst.keypair, None)
                if kp_res is not None:
                    keypair_aws_name = kp_res.attributes.get("aws_key_name",
                                                             None)

            authkey: Optional[str] = None
            if inst.vpn_join is not None and self._vpn_control_plane is not None:
                authkey = getattr(self._vpn_control_plane, "minted_authkey",
                                  None)

            existed = self._instance_mgr.find(run_id=run_id, name=inst.name) is not None
            resource, info = self._instance_mgr.ensure(
                desired=inst, run_id=run_id, subnet_id=subnet_id,
                sg_ids=sg_ids, keypair_aws_name=keypair_aws_name,
                default_tags=default_tags, authkey=authkey, aspects=aspects,
            )
            instance_state[inst.name] = resource

            if existed:
                skipped.append(inst.name)
            else:
                created.append(resource)
                if inst.vpn_join is not None:
                    vpn_records.append({
                        "instance_name": inst.name,
                        "instance_id": resource.attributes.get("instance_id", ""),
                        "vpn_provider": inst.vpn_join.provider,
                        "vpn_device_id": info.get("vpn_device_id", None),
                    })

        # Volumes.
        for vol in spec.volumes:
            attach_id: Optional[str] = None
            if vol.attached_to is not None:
                target = instance_state.get(vol.attached_to, None)
                if target is not None:
                    attach_id = target.attributes.get("instance_id", "")

            existed = self._volume_mgr.find(run_id=run_id, name=vol.name) is not None
            resource = self._volume_mgr.ensure(
                desired=vol, run_id=run_id,
                availability_zone=self._region_config.availability_zone,
                default_tags=default_tags,
                attach_instance_id=attach_id, aspects=aspects,
            )
            if existed:
                skipped.append(vol.name)
            else:
                created.append(resource)

        # Shared filesystems (attach-only).
        for sfs in spec.shared_filesystems:
            resource = self._fsx_mgr.attach(desired=sfs, aspects=aspects)
            created.append(resource)

        # --- dns + storage ---
        for bucket in spec.buckets:
            existed = self._bucket_mgr.find(run_id=run_id, name=bucket.name) is not None
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

        # 1. DNS records — undo upserts.
        if self._spec is not None:
            for record in self._spec.dns_records:
                self._dns_mgr.destroy_record(desired=record, aspects=aspects)

        # 2. Buckets.
        self._bucket_mgr.destroy(run_id=run_id, aspects=aspects)

        # 3. Volumes (detached + deleted).
        self._volume_mgr.destroy(run_id=run_id, aspects=aspects)

        # 4. Instances — capture vpn device ids first.
        terminated = self._instance_mgr.destroy(run_id=run_id, aspects=aspects)

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

        # 6. Placement groups.
        self._placement_mgr.destroy(run_id=run_id, aspects=aspects)

        # 7. KeyPairs.
        self._keypair_mgr.destroy(run_id=run_id, aspects=aspects)

        # 8. Security groups.
        self._sg_mgr.destroy(run_id=run_id, aspects=aspects)

        # 9. Subnets + route tables.
        self._subnet_mgr.destroy(run_id=run_id, aspects=aspects)

        # 10. VPCs + IGWs.
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
        out: List[ProvisionedResource] = []
        out.extend(self._network_mgr.list_owned(run_id=run_id))
        out.extend(self._subnet_mgr.list_owned(run_id=run_id))
        out.extend(self._sg_mgr.list_owned(run_id=run_id))
        out.extend(self._keypair_mgr.list_owned(run_id=run_id))
        out.extend(self._instance_mgr.list_owned(run_id=run_id))
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

            Allows external code (the control-plane integration layer) to
            register the device id post-apply so destroy can de-register it.

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
        rtnval = "aws-{}".format(self._venue.name)
        return rtnval
