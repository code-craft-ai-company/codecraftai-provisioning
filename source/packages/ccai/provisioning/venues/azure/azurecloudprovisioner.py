"""
    .. module:: azurecloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AzureCloudProvisioner — concrete CloudProvisioner for Azure.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import ipaddress
import os

from typing import Any, Dict, List, Optional

from ccai.credentials.azuremanagedidentitycredential import (
    AzureManagedIdentityCredential
)
from ccai.credentials.azureserviceprincipalcredential import (
    AzureServicePrincipalCredential
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
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.provisioning.venues.vpncleanup import delete_vpn_device

from ccai.provisioning.venues.azure.azureerrors import (
    AzureValidationError
)
from ccai.provisioning.venues.azure.azureregionconfig import (
    AzureRegionConfig
)
from ccai.provisioning.venues.azure.azuresessionfactory import (
    AzureSessionFactory
)
from ccai.provisioning.venues.azure.azurespec import AzureSpec
from ccai.provisioning.venues.azure.azuretagging import (
    AZURE_TAG_KEY_MAX, AZURE_TAG_VALUE_MAX
)
from ccai.provisioning.venues.azure.azuretask import resolve_poller
from ccai.provisioning.venues.azure.resources.blobmanager import (
    BlobManager, storage_account_name
)
from ccai.provisioning.venues.azure.resources.diskmanager import (
    DiskManager
)
from ccai.provisioning.venues.azure.resources.dnsmanager import DnsManager
from ccai.provisioning.venues.azure.resources.imageresolver import (
    ImageResolver
)
from ccai.provisioning.venues.azure.resources.lustremanager import (
    LustreManager
)
from ccai.provisioning.venues.azure.resources.nicmanager import NicManager
from ccai.provisioning.venues.azure.resources.nsgmanager import NsgManager
from ccai.provisioning.venues.azure.resources.placement import (
    PlacementManager
)
from ccai.provisioning.venues.azure.resources.resourcegroupmanager import (
    ResourceGroupManager
)
from ccai.provisioning.venues.azure.resources.subnetmanager import (
    SubnetManager
)
from ccai.provisioning.venues.azure.resources.vmmanager import (
    is_infiniband_sku, VmManager
)
from ccai.provisioning.venues.azure.resources.vnetmanager import (
    VnetManager
)


_UNSUPPORTED_FS_KINDS = frozenset({"WEKA", "VAST", "GPFS", "BEEGFS",
                                   "EFS", "FILESTORE", "VENUE_NATIVE"})

# Interconnect kinds the Azure venue refuses (EFA is AWS-only; OCI_RDMA is
# Oracle-only).  Azure exposes RDMA only through InfiniBand on NDv5 / NCv4.
_REJECTED_INTERCONNECTS = frozenset({"EFA", "OCI_RDMA"})

_INFINIBAND_INTERCONNECTS = frozenset({"INFINIBAND_HDR", "INFINIBAND_NDR",
                                       "INFINIBAND_XDR"})


def _all_tags_of(spec: AzureSpec) -> List[Dict[str, str]]:
    """
        Flatten every tag dict declared anywhere in an AzureSpec.

        :param spec: The AzureSpec.

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


class AzureCloudProvisioner(CloudProvisioner):
    """
        Azure-venue concrete :class:`CloudProvisioner` implementation.

        Composes the per-resource managers behind a five-verb lifecycle.
        The spec is an :class:`AzureSpec` bundle of neutral resource
        objects.  The Azure ResourceGroup is the apex container; it is
        created first on apply and removed last on destroy.
    """

    VENUE_NAME: str = "azure"

    def __init__(self, *, venue: CloudVenue,
                 credential: Any,
                 region_config: AzureRegionConfig,
                 spec: Optional[AzureSpec] = None,
                 session_factory: Optional[AzureSessionFactory] = None,
                 catalog: Optional[CloudAcceleratorCatalog] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct an AzureCloudProvisioner.

            :param venue: CloudVenue.
            :param credential: AzureServicePrincipalCredential or
                               AzureManagedIdentityCredential.
            :param region_config: AzureRegionConfig.
            :param spec: Optional AzureSpec.
            :param session_factory: Optional AzureSessionFactory; supplied by
                                    tests with mock azure-mgmt clients.
            :param catalog: Optional accelerator catalog (defaults to the
                            packaged singleton).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                                      destroy uses this to de-register
                                      Tailscale / Twingate devices.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: Any = credential
        self._region_config: AzureRegionConfig = region_config

        if session_factory is not None:
            self._session_factory: AzureSessionFactory = session_factory
        else:
            self._session_factory = AzureSessionFactory(
                credential=credential, region_config=region_config
            )

        if catalog is not None:
            self._catalog: CloudAcceleratorCatalog = catalog
        else:
            self._catalog = default_accelerator_catalog()

        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        self._rg_mgr: ResourceGroupManager = ResourceGroupManager(
            session_factory=self._session_factory
        )
        self._vnet_mgr: VnetManager = VnetManager(
            session_factory=self._session_factory
        )
        self._subnet_mgr: SubnetManager = SubnetManager(
            session_factory=self._session_factory
        )
        self._nsg_mgr: NsgManager = NsgManager(
            session_factory=self._session_factory
        )
        self._nic_mgr: NicManager = NicManager(
            session_factory=self._session_factory
        )
        self._image_resolver: ImageResolver = ImageResolver()
        self._placement_mgr: PlacementManager = PlacementManager(
            session_factory=self._session_factory
        )
        self._vm_mgr: VmManager = VmManager(
            session_factory=self._session_factory,
            image_resolver=self._image_resolver,
            placement_manager=self._placement_mgr,
            catalog=self._catalog,
        )
        self._disk_mgr: DiskManager = DiskManager(
            session_factory=self._session_factory
        )
        self._blob_mgr: BlobManager = BlobManager(
            session_factory=self._session_factory
        )
        self._dns_mgr: DnsManager = DnsManager(
            session_factory=self._session_factory
        )
        self._lustre_mgr: LustreManager = LustreManager(
            session_factory=self._session_factory
        )

        # Tracked across apply / destroy.
        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    @classmethod
    def supports_preemption(cls) -> bool:
        """
            Azure offers Spot VMs, so this venue can preempt instances.

            :returns: True.
        """
        rtnval = True
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the AzureSpec without any azure-mgmt calls.

            :param aspects: ProvisioningAspects (or compatible).

            :returns: A ValidationResult with ok=True on success.
            :raises: AzureValidationError
        """
        is_sp = isinstance(self._credential, AzureServicePrincipalCredential)
        is_mi = isinstance(self._credential, AzureManagedIdentityCredential)
        if not is_sp and not is_mi:
            err_msg_lines = [
                "AzureCloudProvisioner requires an "
                "AzureServicePrincipalCredential or an "
                "AzureManagedIdentityCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise AzureValidationError(err_msg)

        # Every resource is anchored to a resolvable ResourceGroup name.
        resource_group = self._region_config.resource_group
        if resource_group is None or len(resource_group) == 0:
            raise AzureValidationError(
                "AzureCloudProvisioner.validate: every resource must be "
                "anchored to a ResourceGroup; region_config.resource_group "
                "is empty."
            )

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        network_cidrs: Dict[str, str] = {}
        for net in spec.networks:
            network_cidrs[net.name] = net.cidr

        # Shared FS kind acceptance.
        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Azure realises shared-FS through Azure "
                              "Managed Lustre (kind=LUSTRE) or Azure NetApp "
                              "Files (kind=AZUREFILES).  Substitute for "
                              "{}.").format(sfs.kind),
                })
            elif sfs.kind in ("LUSTRE", "AZUREFILES"):
                if sfs.existing_id is None or len(sfs.existing_id) == 0:
                    errors.append({
                        "resource": sfs.name,
                        "error": ("Azure shared-FS v1 supports attach-only; "
                                  "set existing_id."),
                    })

        # Per-instance: interconnect + accelerator checks.
        for instance in spec.instances:
            if instance.interconnect is not None:
                ic_kind = instance.interconnect.kind
                if ic_kind in _REJECTED_INTERCONNECTS:
                    errors.append({
                        "resource": instance.name,
                        "error": ("Azure exposes RDMA only through "
                                  "InfiniBand on NDv5/NCv4 SKUs; got "
                                  "{}.").format(ic_kind),
                    })

            resolved_size: Optional[str] = None
            accelerators = instance.accelerators if instance.accelerators is not None else []
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
                        "error": "Accelerator not on Azure: {}".format(xcpt),
                    })

                if sku is not None:
                    resolved_size = sku
                    if instance.size is not None and len(instance.size) > 0:
                        if instance.size != sku and instance.size != first.model:
                            errors.append({
                                "resource": instance.name,
                                "error": ("Instance.size {!r} conflicts "
                                          "with resolved accelerator SKU "
                                          "{!r}.").format(
                                              instance.size, sku),
                            })

            if resolved_size is None:
                resolved_size = instance.size

            # InfiniBand interconnect requires an IB-capable Azure SKU.
            if instance.interconnect is not None:
                ic_kind = instance.interconnect.kind
                if ic_kind in _INFINIBAND_INTERCONNECTS:
                    if not is_infiniband_sku(vm_size=resolved_size):
                        errors.append({
                            "resource": instance.name,
                            "error": ("InfiniBand requested but the resolved "
                                      "VM size {!r} is not InfiniBand-"
                                      "capable; use an NDv5/NCv4 "
                                      "SKU.").format(resolved_size),
                        })
                    elif instance.placement_group is None or len(
                        instance.placement_group
                    ) == 0:
                        warnings.append({
                            "resource": instance.name,
                            "warning": ("InfiniBand SKU has no "
                                        "placement_group; a Proximity "
                                        "Placement Group will be created "
                                        "automatically."),
                        })

        # Tag length checks on every declared resource.
        for entry in _all_tags_of(spec=spec):
            for key, value in entry.items():
                if len(key) > AZURE_TAG_KEY_MAX:
                    errors.append({
                        "resource": "<tags>",
                        "error": "Tag key exceeds 512 chars: {!r}".format(
                            key
                        ),
                    })
                if len(value) > AZURE_TAG_VALUE_MAX:
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
                                      subnet.cidr, parent_cidr),
                    })
            except (TypeError, ValueError) as xcpt:
                errors.append({
                    "resource": subnet.name,
                    "error": "Subnet/Network CIDR parse error: {}.".format(
                        xcpt
                    ),
                })

        if len(errors) > 0:
            err_msg_lines = ["AzureCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise AzureValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE/DELETE plan.

            Performs read-only ``.get(...)`` calls; no mutation.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        resource_group = self._region_config.resource_group
        location = self._region_config.location
        spec = self._spec
        actions = []

        if spec is None:
            rtnval = ProvisioningPlan(actions=actions)
            return rtnval

        # ResourceGroup.
        rg_existing = self._rg_mgr.find(name=resource_group)
        if rg_existing is None:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.CREATE,
                resource_kind="resource_group",
                resource_name=resource_group,
            ))
        elif self._rg_mgr.matches(existing=rg_existing, location=location):
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.SKIP,
                resource_kind="resource_group",
                resource_name=resource_group,
            ))
        else:
            actions.append(self._planned_action_for(
                intent=PlannedActionIntent.UPDATE,
                resource_kind="resource_group",
                resource_name=resource_group,
            ))

        # Networks.
        for net in spec.networks:
            existing = self._vnet_mgr.find(resource_group=resource_group,
                                           name=net.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="network", resource_name=net.name,
                ))
            elif self._vnet_mgr.matches(existing=existing, desired=net):
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="network", resource_name=net.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="network", resource_name=net.name,
                    diff={"after": {"cidr": net.cidr}},
                ))

        # Subnets.
        for subnet in spec.subnets:
            existing = self._subnet_mgr.find(
                resource_group=resource_group, vnet_name=subnet.network,
                name=subnet.name,
            )
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

        # Security groups (NSG).
        for sg in spec.security_groups:
            existing = self._nsg_mgr.find(resource_group=resource_group,
                                          name=sg.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="sg", resource_name=sg.name,
                ))
            elif self._nsg_mgr.matches(existing=existing, desired=sg):
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.SKIP,
                    resource_kind="sg", resource_name=sg.name,
                ))
            else:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.UPDATE,
                    resource_kind="sg", resource_name=sg.name,
                    diff={"note": "NSG rule drift detected."},
                ))

        # Instances (VM).  A VM size change across family is UPDATE-by-
        # recreate; Azure cannot resize across families with attached disks.
        for inst in spec.instances:
            existing = self._vm_mgr.find(resource_group=resource_group,
                                         name=inst.name)
            if existing is None:
                actions.append(self._planned_action_for(
                    intent=PlannedActionIntent.CREATE,
                    resource_kind="instance", resource_name=inst.name,
                ))
            else:
                desired_size = self._vm_mgr.resolve_vm_size(instance=inst)
                hardware = getattr(existing, "hardware_profile", None)
                live_size = ""
                if hardware is not None:
                    live_size = getattr(hardware, "vm_size", "")
                if live_size != "" and live_size != desired_size:
                    actions.append(self._planned_action_for(
                        intent=PlannedActionIntent.UPDATE,
                        resource_kind="instance", resource_name=inst.name,
                        diff={"note": "VM size change is recreate-by-update.",
                              "before": {"vm_size": live_size},
                              "after": {"vm_size": desired_size}},
                    ))
                else:
                    actions.append(self._planned_action_for(
                        intent=PlannedActionIntent.SKIP,
                        resource_kind="instance", resource_name=inst.name,
                    ))

        # Volumes (managed disk).
        for vol in spec.volumes:
            existing = self._disk_mgr.find(resource_group=resource_group,
                                           name=vol.name)
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

        # Buckets (blob).
        for bucket in spec.buckets:
            account = storage_account_name(run_id=run_id, name=bucket.name)
            existing = self._blob_mgr.find(resource_group=resource_group,
                                           account_name=account)
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
                diff={"note": "Azure Load Balancer apply is deferred to "
                              "v1.5."},
            ))

        # Owned-orphan scan: any resource still tagged ccai:owner=<run_id>
        # that no longer appears in the desired spec is an orphan and is
        # planned for DELETE.  Mirrors the AWS venue's approach so that drift
        # is surfaced up front.
        orphan_actions = self._plan_owned_orphans(
            run_id=run_id, resource_group=resource_group, spec=spec)
        for action in orphan_actions:
            actions.append(action)

        rtnval = ProvisioningPlan(actions=actions)
        return rtnval

    def _plan_owned_orphans(self, *, run_id: str, resource_group: str,
                            spec: AzureSpec) -> List[PlannedAction]:
        """
            Build DELETE actions for owner-tagged resources absent from spec.

            Enumerates the run's owned Azure resources through each per-kind
            manager's ``list_owned`` and emits a ``DELETE`` PlannedAction for
            every resource whose ``(kind, name)`` pair is not declared in the
            desired spec.

            :param run_id: The provisioning run identifier.
            :param resource_group: The Azure resource group name.
            :param spec: The desired AzureSpec.

            :returns: A list of DELETE PlannedAction entries.
        """
        desired_by_kind: Dict[str, set] = {
            "network": {net.name for net in spec.networks},
            "subnet": {subnet.name for subnet in spec.subnets},
            "sg": {sg.name for sg in spec.security_groups},
            "instance": {inst.name for inst in spec.instances},
            "volume": {vol.name for vol in spec.volumes},
            "bucket": {bucket.name for bucket in spec.buckets},
        }

        owned: List[ProvisionedResource] = []
        owned_vnets = self._vnet_mgr.list_owned(
            resource_group=resource_group, run_id=run_id)
        owned.extend(owned_vnets)
        for vnet_resource in owned_vnets:
            owned.extend(self._subnet_mgr.list_owned(
                resource_group=resource_group,
                vnet_name=vnet_resource.name))
        owned.extend(self._nsg_mgr.list_owned(
            resource_group=resource_group, run_id=run_id))
        owned.extend(self._vm_mgr.list_owned(
            resource_group=resource_group, run_id=run_id))
        owned.extend(self._disk_mgr.list_owned(
            resource_group=resource_group, run_id=run_id))
        owned.extend(self._blob_mgr.list_owned(
            resource_group=resource_group, run_id=run_id))

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

            Stages: ResourceGroup → networking (vnet+subnet+nsg) → compute
            (nic+vm+disk) → storage (blob) → dns.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningResult.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id
        resource_group = self._region_config.resource_group
        location = self._region_config.location
        default_tags = self._region_config.default_tags

        created: List[ProvisionedResource] = []
        updated: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []

        spec = self._spec

        # --- ResourceGroup (apex container, created first) ---
        rg_existed = self._rg_mgr.find(name=resource_group) is not None
        rg_resource = self._rg_mgr.ensure(
            name=resource_group, location=location, run_id=run_id,
            default_tags=default_tags, aspects=aspects,
        )
        if rg_existed:
            skipped.append(resource_group)
        else:
            created.append(rg_resource)

        # --- networking ---
        vnet_state: Dict[str, ProvisionedResource] = {}
        for net in spec.networks:
            existed = self._vnet_mgr.find(resource_group=resource_group,
                                          name=net.name) is not None
            resource = self._vnet_mgr.ensure(
                desired=net, resource_group=resource_group,
                location=location, run_id=run_id,
                default_tags=default_tags, aspects=aspects,
            )
            vnet_state[net.name] = resource
            if existed:
                skipped.append(net.name)
            else:
                created.append(resource)

        nsg_state: Dict[str, ProvisionedResource] = {}
        for sg in spec.security_groups:
            existed = self._nsg_mgr.find(resource_group=resource_group,
                                         name=sg.name) is not None
            resource = self._nsg_mgr.ensure(
                desired=sg, resource_group=resource_group,
                location=location, run_id=run_id,
                default_tags=default_tags, aspects=aspects,
            )
            nsg_state[sg.name] = resource
            if existed:
                skipped.append(sg.name)
            else:
                created.append(resource)

        subnet_state: Dict[str, ProvisionedResource] = {}
        for subnet in spec.subnets:
            parent = vnet_state.get(subnet.network, None)
            if parent is None:
                continue
            # First NSG in the parent network (if any) decorates the subnet.
            nsg_id: Optional[str] = None
            for sg in spec.security_groups:
                if sg.network == subnet.network:
                    nsg_res = nsg_state.get(sg.name, None)
                    if nsg_res is not None:
                        nsg_id = nsg_res.venue_id
                    break

            existed = self._subnet_mgr.find(
                resource_group=resource_group, vnet_name=subnet.network,
                name=subnet.name,
            ) is not None
            resource = self._subnet_mgr.ensure(
                desired=subnet, resource_group=resource_group,
                vnet_name=subnet.network, nsg_id=nsg_id, aspects=aspects,
            )
            subnet_state[subnet.name] = resource
            if existed:
                skipped.append(subnet.name)
            else:
                created.append(resource)

        # Key pairs carry no native Azure resource; the public key material
        # is injected into the VM admin SSH configuration.
        keypair_material: Dict[str, str] = {}
        for kp in spec.keypairs:
            keypair_material[kp.name] = kp.public_key_material

        # --- compute ---
        vm_state: Dict[str, ProvisionedResource] = {}
        for inst in spec.instances:
            subnet_res = subnet_state.get(inst.subnet, None)
            if subnet_res is None:
                continue
            subnet_id = subnet_res.venue_id

            public_ip_id: Optional[str] = None
            if inst.public_ip is True:
                public_ip_id = self._ensure_public_ip(
                    instance_name=inst.name, resource_group=resource_group,
                    location=location, run_id=run_id,
                    default_tags=default_tags, aspects=aspects,
                )

            nic_existed = self._nic_mgr.find(
                resource_group=resource_group, instance_name=inst.name,
            ) is not None
            nic_resource = self._nic_mgr.ensure(
                instance_name=inst.name, resource_group=resource_group,
                location=location, subnet_id=subnet_id,
                public_ip_id=public_ip_id, run_id=run_id,
                default_tags=default_tags, aspects=aspects,
            )
            if nic_existed:
                skipped.append(nic_resource.name)
            else:
                created.append(nic_resource)

            admin_public_key: Optional[str] = None
            if inst.keypair is not None:
                admin_public_key = keypair_material.get(inst.keypair, None)

            authkey: Optional[str] = None
            if inst.vpn_join is not None and self._vpn_control_plane is not None:
                authkey = getattr(self._vpn_control_plane, "minted_authkey",
                                  None)

            vm_existed = self._vm_mgr.find(resource_group=resource_group,
                                           name=inst.name) is not None
            resource, info = self._vm_mgr.ensure(
                desired=inst, resource_group=resource_group,
                location=location, run_id=run_id,
                nic_id=nic_resource.venue_id,
                admin_public_key=admin_public_key,
                default_tags=default_tags, authkey=authkey, aspects=aspects,
            )
            vm_state[inst.name] = resource

            if vm_existed:
                skipped.append(inst.name)
            else:
                created.append(resource)
                if inst.vpn_join is not None:
                    vpn_records.append({
                        "instance_name": inst.name,
                        "vm_name": inst.name,
                        "vpn_provider": inst.vpn_join.provider,
                        "vpn_device_id": info.get("vpn_device_id", None),
                    })

        # Volumes (managed disk).
        for vol in spec.volumes:
            attach_vm_name: Optional[str] = None
            if vol.attached_to is not None:
                target = vm_state.get(vol.attached_to, None)
                if target is not None:
                    attach_vm_name = target.name

            existed = self._disk_mgr.find(resource_group=resource_group,
                                          name=vol.name) is not None
            resource = self._disk_mgr.ensure(
                desired=vol, resource_group=resource_group,
                location=location, run_id=run_id,
                default_tags=default_tags,
                attach_vm_name=attach_vm_name, aspects=aspects,
            )
            if existed:
                skipped.append(vol.name)
            else:
                created.append(resource)

        # Shared filesystems (attach-only).
        for sfs in spec.shared_filesystems:
            resource = self._lustre_mgr.attach(desired=sfs, aspects=aspects)
            created.append(resource)

        # --- storage ---
        for bucket in spec.buckets:
            account = storage_account_name(run_id=run_id, name=bucket.name)
            existed = self._blob_mgr.find(resource_group=resource_group,
                                          account_name=account) is not None
            resource = self._blob_mgr.ensure(
                desired=bucket, resource_group=resource_group,
                location=location, run_id=run_id,
                default_tags=default_tags, aspects=aspects,
            )
            if existed:
                skipped.append(bucket.name)
            else:
                created.append(resource)

        # --- dns ---
        for record in spec.dns_records:
            resource = self._dns_mgr.ensure(
                desired=record, resource_group=resource_group,
                run_id=run_id, aspects=aspects,
            )
            created.append(resource)

        self._last_vpn_records = vpn_records

        rtnval = ProvisioningResult(created=created, updated=updated,
                                    skipped=skipped, errors=[])
        return rtnval

    def _ensure_public_ip(self, *, instance_name: str, resource_group: str,
                          location: str, run_id: str,
                          default_tags: List[Dict[str, str]],
                          aspects: Any) -> str:
        """
            Create or reuse a public IP address for a VM NIC.

            :param instance_name: Neutral instance name.
            :param resource_group: ResourceGroup name.
            :param location: Azure location.
            :param run_id: Run identifier.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: The public IP resource id.
        """
        from ccai.provisioning.venues.azure.azureidempotency import (
            get_or_none
        )
        from ccai.provisioning.venues.azure.azuretagging import (
            azure_tags_for
        )

        client = self._session_factory.network_client()
        pip_name = "{}-pip".format(instance_name)
        existing = get_or_none(getter=client.public_ip_addresses.get,
                               resource_group_name=resource_group,
                               public_ip_address_name=pip_name)
        if existing is None:
            tags = azure_tags_for(run_id=run_id, resource_name=pip_name,
                                  resource_kind="public_ip",
                                  defaults=default_tags)
            params: Dict[str, Any] = {
                "location": location,
                "public_ip_allocation_method": "Static",
                "sku": {"name": "Standard"},
                "tags": tags,
            }
            poller = client.public_ip_addresses.begin_create_or_update(
                resource_group_name=resource_group,
                public_ip_address_name=pip_name, parameters=params,
            )
            existing = resolve_poller(
                poller=poller, aspects=aspects,
                description="create public ip {}".format(pip_name),
            )

        rtnval = getattr(existing, "id", pip_name)
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
        resource_group = self._region_config.resource_group

        # 1. DNS records — undo upserts.
        if self._spec is not None:
            for record in self._spec.dns_records:
                self._dns_mgr.destroy_record(
                    desired=record, resource_group=resource_group,
                    aspects=aspects,
                )

        # 2. Blob storage accounts.
        self._blob_mgr.destroy(resource_group=resource_group,
                               run_id=run_id, aspects=aspects)

        # 3. VMs — capture vpn device records first.
        terminated = self._vm_mgr.destroy(resource_group=resource_group,
                                          run_id=run_id, aspects=aspects)

        # 4. VPN control-plane device cleanup.
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

        # 5. NICs.
        self._nic_mgr.destroy(resource_group=resource_group,
                              run_id=run_id, aspects=aspects)

        # 6. Managed disks.
        self._disk_mgr.destroy(resource_group=resource_group,
                               run_id=run_id, aspects=aspects)

        # 7. Proximity Placement Groups.
        self._placement_mgr.destroy(resource_group=resource_group,
                                    run_id=run_id, aspects=aspects)

        # 8. NSGs.
        self._nsg_mgr.destroy(resource_group=resource_group,
                              run_id=run_id, aspects=aspects)

        # 9. Subnets.
        if self._spec is not None:
            subnets_by_vnet: Dict[str, List[str]] = {}
            for subnet in self._spec.subnets:
                bucket = subnets_by_vnet.setdefault(subnet.network, [])
                bucket.append(subnet.name)
            for vnet_name, subnet_names in subnets_by_vnet.items():
                self._subnet_mgr.destroy(
                    resource_group=resource_group, vnet_name=vnet_name,
                    subnet_names=subnet_names, aspects=aspects,
                )

        # 10. VNets.
        self._vnet_mgr.destroy(resource_group=resource_group,
                               run_id=run_id, aspects=aspects)

        # 11. ResourceGroup — only when empty and owned by the run-id.
        self._rg_mgr.destroy(name=resource_group, run_id=run_id,
                             aspects=aspects)
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
        resource_group = self._region_config.resource_group
        out: List[ProvisionedResource] = []
        out.extend(self._rg_mgr.list_owned(name=resource_group,
                                           run_id=run_id))
        owned_vnets = self._vnet_mgr.list_owned(
            resource_group=resource_group, run_id=run_id)
        out.extend(owned_vnets)

        # Subnets carry no tags; enumerate them under each owned VNet.
        for vnet_resource in owned_vnets:
            out.extend(self._subnet_mgr.list_owned(
                resource_group=resource_group,
                vnet_name=vnet_resource.name))

        out.extend(self._nsg_mgr.list_owned(resource_group=resource_group,
                                            run_id=run_id))
        out.extend(self._nic_mgr.list_owned(resource_group=resource_group,
                                            run_id=run_id))
        out.extend(self._placement_mgr.list_owned(
            resource_group=resource_group, run_id=run_id))
        out.extend(self._vm_mgr.list_owned(resource_group=resource_group,
                                           run_id=run_id))
        out.extend(self._disk_mgr.list_owned(resource_group=resource_group,
                                             run_id=run_id))
        out.extend(self._blob_mgr.list_owned(resource_group=resource_group,
                                             run_id=run_id))
        rtnval = out
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance.

            Allows the control-plane integration layer to register the
            device id post-apply so destroy can de-register it.

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
        rtnval = "azure-{}".format(self._venue.name)
        return rtnval
