"""
    .. module:: equinixmetalcloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: EquinixMetalCloudProvisioner — concrete CloudProvisioner for
               the Equinix Metal bare-metal venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.credentials.equinixmetalapitokencredential import (
    EquinixMetalApiTokenCredential
)
from automojo.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from automojo.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from automojo.provisioning.model.cloud.validationresult import ValidationResult
from automojo.provisioning.venues.equinix_metal.metalapplystages import (
    MetalApplyStages
)
from automojo.provisioning.venues.equinix_metal.metalclient import MetalClient
from automojo.provisioning.venues.equinix_metal.metaldestroystages import (
    MetalDestroyStages
)
from automojo.provisioning.venues.equinix_metal.metalerrors import (
    MetalValidationError
)
from automojo.provisioning.venues.equinix_metal.metalinventory import (
    MetalInventory
)
from automojo.provisioning.venues.equinix_metal.metalplanbuilder import (
    MetalPlanBuilder
)
from automojo.provisioning.venues.equinix_metal.metalprojectconfig import (
    MetalProjectConfig
)
from automojo.provisioning.venues.equinix_metal.metalresolver import (
    MetalResolver
)
from automojo.provisioning.venues.equinix_metal.metalspec import MetalSpec


# Interconnect kinds Equinix Metal cannot realise between Devices in a
# metro.  Only NONE is acceptable in the bare-metal v1 venue.
_REJECTED_INTERCONNECTS = frozenset({
    "ROCE", "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR",
    "EFA", "OCI_RDMA",
})


class EquinixMetalCloudProvisioner(CloudProvisioner):
    """
        Equinix-Metal-venue concrete :class:`CloudProvisioner`.

        Equinix Metal is a bare-metal venue.  The unit of provisioning is a
        Device — a physical server — not a VM, which has implications:
        provisioning latency is measured in minutes; not every plan is
        available in every metro; and in-place "resize" is not a concept.

        The neutral resource model maps onto Metal primitives as follows:

        - ``CloudNetwork``  → project VLAN / Layer-2 network.
        - ``CloudSubnet``   → VLAN + IP Reservation.
        - ``CloudKeyPair``  → project-level SSH key.
        - ``CloudInstance`` → Device (bare-metal server).
        - ``VPNJoinSpec``   → cloud-init rendered into the Device ``userdata``.

        What bare metal lacks is rejected at ``validate``:

        - ``CloudSecurityGroup`` — no cloud security-group concept.
        - ``CloudObjectBucket`` — Metal has no native object storage.
        - ``CloudLoadBalancer`` — unsupported in v1.
        - ``CloudInterconnect != NONE`` — no HPC RDMA fabric between Devices.
        - ``CloudSharedFilesystem`` — unsupported.
        - ``CloudStorageVolume`` — block storage is a separate product;
          attach-existing only (``existing_id`` set), else a validate-error.

        Following the same pattern as the AWS venue (boto3 directly), the
        Equinix Metal SDK is used inside the venue via :class:`MetalClient`
        with no separate interop package.
    """

    VENUE_NAME: str = "equinix-metal"

    def __init__(self, *, venue: CloudVenue,
                 credential: EquinixMetalApiTokenCredential,
                 project_config: MetalProjectConfig,
                 spec: Optional[MetalSpec] = None,
                 client: Optional[MetalClient] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct an EquinixMetalCloudProvisioner.

            :param venue: CloudVenue.
            :param credential: EquinixMetalApiTokenCredential.
            :param project_config: MetalProjectConfig (project id + metro +
                                   default tags).
            :param spec: Optional MetalSpec.
            :param client: Optional MetalClient; tests inject a fully-mocked
                           client so the SDK is never imported.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                                      destroy uses this to de-register
                                      Tailscale / Twingate devices.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: EquinixMetalApiTokenCredential = credential
        self._project_config: MetalProjectConfig = project_config
        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        if client is not None:
            self._client: MetalClient = client
        else:
            self._client = MetalClient(
                api_token=credential.token,
                project_id=project_config.project_id,
            )

        self._resolver: MetalResolver = MetalResolver()
        self._stages: MetalApplyStages = MetalApplyStages(
            client=self._client, resolver=self._resolver,
            metro=project_config.metro,
            default_tags=project_config.default_tags,
        )
        self._plan_builder: MetalPlanBuilder = MetalPlanBuilder(
            stages=self._stages
        )
        self._destroy_stages: MetalDestroyStages = MetalDestroyStages(
            client=self._client
        )
        self._inventory: MetalInventory = MetalInventory(
            client=self._client, stages=self._stages
        )

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the MetalSpec without any SDK calls.

            :param aspects: Aspects (or compatible).

            :returns: A ValidationResult with ok=True on success.
            :raises: MetalValidationError
        """
        if not isinstance(self._credential, EquinixMetalApiTokenCredential):
            err_msg_lines = [
                "EquinixMetalCloudProvisioner requires an "
                "EquinixMetalApiTokenCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise MetalValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        # Object storage is not a Metal product.
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("Equinix Metal has no native object storage; "
                          "CloudObjectBucket is unsupported."),
            })

        # Load balancers are unsupported in the v1 bare-metal venue.
        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("Equinix Metal v1 has no managed load balancer; "
                          "CloudLoadBalancer is unsupported."),
            })

        # Cloud security groups have no bare-metal equivalent.
        for sg in spec.security_groups:
            warnings.append({
                "resource": sg.name,
                "error": ("Equinix Metal has no cloud security-group "
                          "concept; firewall rules must be host-managed. "
                          "The group is recorded in tags only."),
            })

        # Shared filesystems are unsupported.
        for sfs in spec.shared_filesystems:
            if sfs.kind != "VENUE_NATIVE":
                errors.append({
                    "resource": sfs.name,
                    "error": ("Equinix Metal does not provide a managed "
                              "shared filesystem; got kind={}.").format(
                                  sfs.kind
                              ),
                })
            else:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Equinix Metal has no venue-native shared "
                              "filesystem product."),
                })

        # Block storage volumes — attach-existing only.
        for volume in spec.volumes:
            existing_id = getattr(volume, "existing_id", None)
            if existing_id is None or len(str(existing_id)) == 0:
                errors.append({
                    "resource": volume.name,
                    "error": ("Equinix Metal block storage is a separate "
                              "product not provisioned in v1; set "
                              "existing_id to attach an existing volume."),
                })

        # Per-device checks.
        for instance in spec.instances:
            # Metro resolution.
            metro_hint = self._project_config.metro
            try:
                resolved_metro = self._resolver.metro_slug(
                    metro_hint=metro_hint
                )
            except MetalValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": "Metro does not resolve: {}".format(xcpt),
                })
                resolved_metro = metro_hint

            # Interconnect rejection.
            if instance.interconnect is not None:
                if instance.interconnect.kind in _REJECTED_INTERCONNECTS:
                    errors.append({
                        "resource": instance.name,
                        "error": ("Equinix Metal does not provide an HPC "
                                  "RDMA fabric between Devices; got "
                                  "interconnect kind={}.").format(
                                      instance.interconnect.kind
                                  ),
                    })

            # Image OS slug resolution.
            try:
                self._resolver.image_to_os_slug(
                    family=instance.image.family,
                    version=instance.image.version,
                    arch=instance.image.architecture,
                )
            except MetalValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": "Image does not resolve: {}".format(xcpt),
                })

            # Plan (Metal SKU) resolution.
            accelerator_models: List[str] = []
            accelerators = instance.accelerators if instance.accelerators is not None else []
            for accelerator in accelerators:
                accelerator_models.append(accelerator.model)
            try:
                self._resolver.size_to_plan(
                    size_hint=instance.size,
                    accelerators=accelerator_models,
                    metro=resolved_metro,
                )
            except MetalValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": "Plan does not resolve: {}".format(xcpt),
                })

        if len(errors) > 0:
            err_msg_lines = [
                "EquinixMetalCloudProvisioner.validate found errors."
            ]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise MetalValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan via read-only SDK listings.

            :param aspects: Aspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        rtnval = self._plan_builder.plan(
            spec=self._spec, run_id=run_id, aspects=aspects
        )
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: VLAN → IP Reservation → SSH Key → Device.  Every stage
            is owner-tagged read-before-create so ``apply ∘ apply`` makes no
            mutating calls.

            :param aspects: Aspects.

            :returns: A ProvisioningResult.
        """
        spec = self._spec
        if spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id

        created: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []

        # --- VLANs ---
        for network in spec.networks:
            existed = self._stages.find_vlan(
                run_id=run_id, name=network.name
            ) is not None
            resource = self._stages.ensure_vlan(
                desired=network, run_id=run_id, aspects=aspects
            )
            if existed:
                skipped.append(network.name)
            else:
                created.append(resource)

        # --- IP reservations ---
        for subnet in spec.subnets:
            existed = self._stages.find_ip_reservation(
                run_id=run_id, name=subnet.name
            ) is not None
            resource = self._stages.ensure_ip_reservation(
                desired=subnet, run_id=run_id, aspects=aspects
            )
            if existed:
                skipped.append(subnet.name)
            else:
                created.append(resource)

        # --- SSH keys ---
        ssh_key_ids: Dict[str, str] = {}
        for keypair in spec.keypairs:
            existed = self._stages.find_ssh_key(
                run_id=run_id, name=keypair.name
            ) is not None
            resource = self._stages.ensure_ssh_key(
                desired=keypair, run_id=run_id, aspects=aspects
            )
            ssh_key_ids[keypair.name] = resource.attributes.get(
                "ssh_key_id", ""
            )
            if existed:
                skipped.append(keypair.name)
            else:
                created.append(resource)

        # --- Devices ---
        for instance in spec.instances:
            existed = self._stages.find_device(
                run_id=run_id, name=instance.name
            ) is not None

            key_ids: List[str] = []
            if instance.keypair is not None:
                resolved = ssh_key_ids.get(instance.keypair, None)
                if resolved is not None and len(resolved) > 0:
                    key_ids.append(resolved)

            authkey: Optional[str] = None
            if instance.vpn_join is not None and self._vpn_control_plane is not None:
                authkey = getattr(self._vpn_control_plane,
                                  "minted_authkey", None)

            resource = self._stages.ensure_device(
                desired=instance, run_id=run_id, ssh_key_ids=key_ids,
                authkey=authkey, aspects=aspects,
            )

            if existed:
                skipped.append(instance.name)
            else:
                created.append(resource)
                if instance.vpn_join is not None:
                    vpn_records.append({
                        "instance_name": instance.name,
                        "device_id": resource.attributes.get(
                            "device_id", ""
                        ),
                        "vpn_provider": instance.vpn_join.provider,
                        "vpn_device_id": resource.attributes.get(
                            "vpn_device_id", None
                        ),
                    })

        self._last_vpn_records = vpn_records

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
        run_id = self._run_id(aspects=aspects)

        vpn_records = self._destroy_stages.destroy(
            run_id=run_id, aspects=aspects
        )

        if self._vpn_control_plane is not None:
            seen_ids: List[str] = []
            for record in vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                seen_ids.append(str(device_id))
            for record in self._last_vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                if str(device_id) not in seen_ids:
                    seen_ids.append(str(device_id))
            for device_id in seen_ids:
                try:
                    self._vpn_control_plane.delete_device(
                        device_id=device_id, aspects=aspects
                    )
                except Exception:
                    pass

        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate owned resources for the run.

            :param aspects: Aspects.

            :returns: A list of ProvisionedResource entries.
        """
        run_id = self._run_id(aspects=aspects)
        rtnval = self._inventory.list_run(run_id=run_id, aspects=aspects)
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance.

            :param instance_name: Neutral instance name.
            :param device_id: VPN-provider-assigned device id.
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

            :param aspects: Aspects.

            :returns: A non-empty run id string.
        """
        candidate = self._aspect_attr(aspects=aspects, name="runid",
                                      default=None)
        if candidate is not None and len(candidate) > 0:
            rtnval = candidate
            return rtnval
        rtnval = "metal-{}".format(self._venue.name)
        return rtnval
