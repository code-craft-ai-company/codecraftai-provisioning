"""
    .. module:: nebiuscloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NebiusCloudProvisioner — concrete CloudProvisioner for Nebius.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import ipaddress
import json
import os

from typing import Any, Dict, List, Optional

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
from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.provisioning.venues.nebius.nebiusapplystages import (
    NebiusApplyStages
)
from ccai.provisioning.venues.nebius.nebiusdestroystages import (
    NebiusDestroyStages
)
from ccai.provisioning.venues.nebius.nebiuserrors import (
    ConfirmationRequiredError, NebiusValidationError
)
from ccai.provisioning.venues.nebius.nebiusinventory import (
    NebiusInventory
)
from ccai.provisioning.venues.nebius.nebiuslabeltranslator import (
    NebiusLabelTranslator
)
from ccai.provisioning.venues.nebius.nebiusplanbuilder import (
    NebiusPlanBuilder
)
from ccai.provisioning.venues.nebius.nebiusresolver import NebiusResolver
from ccai.provisioning.venues.nebius.nebiusspec import NebiusSpec
from ccai.provisioning.venues.nebius.nebiususerdatarenderer import (
    NebiusUserDataRenderer
)


# Neutral interconnect kinds that map onto a Nebius GPU Cluster.
_IB_INTERCONNECT_KINDS = frozenset({
    "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR",
})


class NebiusCloudProvisioner(CloudProvisioner):
    """
        Nebius-venue concrete :class:`CloudProvisioner` implementation.

        Realises the neutral resource model on Nebius: CloudNetwork→VPC,
        CloudSubnet→subnet, CloudSecurityGroup→security-group,
        CloudInstance→VM (GPU SKU via the accelerator catalog),
        CloudStorageVolume→disk, CloudInterconnect(InfiniBand)→IB-enabled
        placement group (GPU Cluster), CloudSharedFilesystem→Nebius native
        shared filesystem (attach-only in v1).

        All API calls go through the :class:`NebiusClient` from
        ``codecraftai-interop-nebius``; every lifecycle method accepts an
        ``aspects`` argument.  CloudLoadBalancer and provisioned (non-attach)
        shared filesystems and CloudObjectBucket are rejected at validate.
    """

    VENUE_NAME: str = "nebius"

    def __init__(self, *, venue: CloudVenue, client: Any,
                 spec: Optional[NebiusSpec] = None,
                 catalog: Optional[CloudAcceleratorCatalog] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a NebiusCloudProvisioner.

            :param venue: CloudVenue.
            :param client: A :class:`NebiusClient` (or compatible mock).
            :param spec: Optional NebiusSpec.
            :param catalog: Optional accelerator catalog (defaults to the
                packaged singleton).
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                destroy uses this to de-register VPN-joined devices.
        """
        super().__init__(venue=venue, spec=spec)
        self._client: Any = client

        if catalog is not None:
            self._catalog: CloudAcceleratorCatalog = catalog
        else:
            self._catalog = default_accelerator_catalog()

        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        self._labels: NebiusLabelTranslator = NebiusLabelTranslator()
        self._resolver: NebiusResolver = NebiusResolver(
            catalog=self._catalog,
        )
        self._user_data: NebiusUserDataRenderer = NebiusUserDataRenderer()
        self._plan_builder: NebiusPlanBuilder = NebiusPlanBuilder(
            client=client, resolver=self._resolver,
        )
        self._apply_stages: NebiusApplyStages = NebiusApplyStages(
            client=client, label_translator=self._labels,
            resolver=self._resolver, user_data_renderer=self._user_data,
        )
        self._destroy_stages: NebiusDestroyStages = NebiusDestroyStages(
            client=client, vpn_control_plane=vpn_control_plane,
        )
        self._inventory: NebiusInventory = NebiusInventory(
            client=client, label_translator=self._labels,
        )

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    @property
    def last_vpn_records(self) -> List[Dict[str, Any]]:
        """
            Return the recorded VPN device records from the last apply.

            :returns: A defensive copy of the records.
        """
        rtnval = [dict(entry) for entry in self._last_vpn_records]
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the NebiusSpec without any remote calls.

            :param aspects: Aspects (ProvisioningAspects or compatible).

            :returns: A ValidationResult with ok=True on success.

            :raises: NebiusValidationError
        """
        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        if spec.parent_id is None or len(spec.parent_id) == 0:
            errors.append({"resource": "<spec>",
                           "error": "NebiusSpec.parent_id must be set."})

        network_cidrs: Dict[str, str] = {}
        for net in spec.networks:
            network_cidrs[net.name] = net.cidr

        # Load balancers are unsupported in v1.
        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("Nebius venue does not support CloudLoadBalancer "
                          "in v1."),
            })

        # Object Storage buckets are not exposed by the v1 Nebius interop
        # client; reject so the spec author substitutes an external bucket.
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("Nebius Object Storage is not exposed by the v1 "
                          "interop client; CloudObjectBucket is rejected."),
            })

        # Shared filesystems are attach-only — existing_id required.
        for sfs in spec.shared_filesystems:
            if sfs.existing_id is None or len(sfs.existing_id) == 0:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Nebius shared FS is attach-only in v1; set "
                              "existing_id."),
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

        # Per-instance: accelerator resolution + IB-platform compatibility.
        for instance in spec.instances:
            accelerators = instance.accelerators if instance.accelerators is not None else []
            resolved_preset: Optional[str] = None
            if len(accelerators) > 0:
                first = accelerators[0]
                try:
                    resolved_preset = self._catalog.resolve(
                        neutral_name=first.model, venue=self.VENUE_NAME,
                    )
                except SchemaSemanticError as xcpt:
                    errors.append({
                        "resource": instance.name,
                        "error": "Accelerator not on Nebius: {}".format(
                            xcpt
                        ),
                    })

            if instance.interconnect is not None:
                ic_kind = instance.interconnect.kind
                if ic_kind in _IB_INTERCONNECT_KINDS:
                    platform_source = resolved_preset
                    if platform_source is None:
                        platform_source = instance.size
                    platform = self._resolver.platform_for_preset(
                        preset=platform_source,
                    )
                    if not self._resolver.is_ib_eligible(platform=platform):
                        errors.append({
                            "resource": instance.name,
                            "error": ("CloudInterconnect kind {} requested "
                                      "but platform {} is not IB-eligible "
                                      "(no GPU Cluster support).").format(
                                          ic_kind, platform
                                      ),
                        })

        if len(errors) > 0:
            err_msg_lines = ["NebiusCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise NebiusValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan.

            Performs read-only listing filtered by the run-id label; no
            mutation.

            :param aspects: Aspects.

            :returns: A ProvisioningPlan.
        """
        spec = self._spec
        if spec is None:
            rtnval = ProvisioningPlan(actions=[])
            return rtnval

        run_id = self._run_id(aspects=aspects)
        rtnval = self._plan_builder.plan(spec=spec, run_id=run_id,
                                         aspects=aspects)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stage order: VPC → Subnet → Security Group → SSH keys → GPU
            Cluster → Instances → Disks → File-storage attach.  Re-applying
            an already-applied spec makes no mutating create calls.

            :param aspects: Aspects.

            :returns: A ProvisioningResult.
        """
        spec = self._spec
        if spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id

        confirm = self._aspect_attr(aspects=aspects, name="confirm",
                                    default=False)
        plan = self._plan_builder.plan(spec=spec, run_id=run_id,
                                       aspects=aspects)
        destructive_intents = (PlannedActionIntent.UPDATE.value,
                               PlannedActionIntent.DELETE.value)
        has_destructive = False
        for action in plan.actions:
            if action.intent in destructive_intents:
                has_destructive = True
        if has_destructive is True and confirm is not True:
            err_msg = (
                "NebiusCloudProvisioner.apply has UPDATE-by-recreate or "
                "DELETE actions which require aspects.confirm=True."
            )
            raise ConfirmationRequiredError(err_msg)

        created: List[ProvisionedResource] = []
        skipped: List[str] = []

        network_state = self._apply_stages.apply_network_and_security(
            spec=spec, run_id=run_id, aspects=aspects,
        )
        created.extend(network_state["created"])
        skipped.extend(network_state["skipped"])

        compute_state = self._apply_stages.apply_instances_and_disks(
            spec=spec, run_id=run_id, network_state=network_state,
            authkey_for=self._authkey_for, aspects=aspects,
        )
        created.extend(compute_state["created"])
        skipped.extend(compute_state["skipped"])

        # The storage stage needs the subnet-id map for mount targets.
        compute_state["subnet"] = network_state["subnet"]
        storage_state = self._apply_stages.apply_storage_and_dns(
            spec=spec, run_id=run_id, compute_state=compute_state,
            aspects=aspects,
        )
        created.extend(storage_state["created"])
        skipped.extend(storage_state["skipped"])

        self._last_vpn_records = compute_state["vpn_records"]
        self._persist_inventory(run_id=run_id, created=created,
                                skipped=skipped)

        rtnval = ProvisioningResult(created=created, updated=[],
                                    skipped=skipped, errors=[])
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Destroy every owned resource in reverse dependency order.

            :param aspects: Aspects.
        """
        spec = self._spec
        if spec is None:
            return

        run_id = self._run_id(aspects=aspects)
        self._destroy_stages.destroy(spec=spec, run_id=run_id,
                                     vpn_records=self._last_vpn_records,
                                     aspects=aspects)
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate run-id-labelled resources for the run.

            :param aspects: Aspects.

            :returns: A list of ProvisionedResource entries.
        """
        spec = self._spec
        if spec is None:
            rtnval: List[ProvisionedResource] = []
            return rtnval

        run_id = self._run_id(aspects=aspects)
        rtnval = self._inventory.list_run(spec=spec, run_id=run_id,
                                          aspects=aspects)
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance so destroy can
            de-register it.

            :param instance_name: Neutral instance name.
            :param device_id: Provider-assigned device id.

            :returns: ``None``.
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

    def _authkey_for(self, instance_name: str) -> str:
        """
            Resolve the VPN auth key for an instance.

            The control plane (when supplied) exposes a minted auth key; in
            its absence an empty string is used so the cloud-init renderer
            still produces a deterministic document.

            :param instance_name: Neutral instance name.

            :returns: The auth-key string (possibly empty).
        """
        if self._vpn_control_plane is None:
            rtnval = ""
            return rtnval
        candidate = getattr(self._vpn_control_plane, "minted_authkey", None)
        if candidate is None:
            rtnval = ""
            return rtnval
        rtnval = candidate
        return rtnval

    def _persist_inventory(self, *, run_id: str,
                           created: List[ProvisionedResource],
                           skipped: List[str]) -> None:
        """
            Persist the apply inventory to the run-state output directory.

            :param run_id: The provisioning run identifier.
            :param created: Created ProvisionedResources.
            :param skipped: Names of skipped resources.

            :returns: ``None``.
        """
        out_dir = os.path.join(".output", "provisioning", run_id)
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError:
            return

        document = {
            "run_id": run_id,
            "venue": self.VENUE_NAME,
            "created": [r.to_dict() for r in created],
            "skipped": list(skipped),
        }
        out_path = os.path.join(out_dir, "nebius-inventory.json")
        try:
            with open(out_path, "w", encoding="utf-8") as fh:
                json.dump(document, fh, indent=2, sort_keys=True)
        except OSError:
            return
        return

    def _run_id(self, *, aspects: Any) -> str:
        """
            Resolve the run identifier from aspects or fall back to venue.

            :param aspects: Aspects.

            :returns: A non-empty run id string.
        """
        candidate = self._aspect_attr(aspects=aspects, name="runid",
                                      default=None)
        if candidate is not None and len(candidate) > 0:
            rtnval = candidate
            return rtnval
        rtnval = "nebius-{}".format(self._venue.name)
        return rtnval
