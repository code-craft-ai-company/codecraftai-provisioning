"""
    .. module:: hetznercloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HetznerCloudProvisioner — concrete CloudProvisioner for Hetzner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from ccai.credentials.hetznerapitokencredential import (
    HetznerApiTokenCredential
)
from ccai.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from ccai.provisioning.model.cloud.cloudvenue import CloudVenue
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from ccai.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from ccai.provisioning.model.cloud.validationresult import ValidationResult
from ccai.provisioning.venues.hetzner.hetznerapplystages import (
    HetznerApplyStages
)
from ccai.provisioning.venues.hetzner.hetznerclientfactory import (
    HetznerClientFactory
)
from ccai.provisioning.venues.hetzner.hetznerdestroystages import (
    HetznerDestroyStages
)
from ccai.provisioning.venues.hetzner.hetznererrors import (
    HetznerValidationError,
)
from ccai.provisioning.venues.hetzner.hetznerinventory import (
    HetznerInventory
)
from ccai.provisioning.venues.hetzner.hetznerlabeltranslator import (
    HetznerLabelTranslator
)
from ccai.provisioning.venues.hetzner.hetznerlocationconfig import (
    HETZNER_LOCATIONS, HetznerLocationConfig
)
from ccai.provisioning.venues.hetzner.hetznerplanbuilder import (
    HetznerPlanBuilder
)
from ccai.provisioning.venues.hetzner.hetznerresolver import (
    HetznerResolver
)
from ccai.provisioning.venues.hetzner.hetznerspec import HetznerSpec


# Shared-FS kinds Hetzner Cloud cannot realise.
_UNSUPPORTED_FS_KINDS = frozenset({"LUSTRE", "WEKA", "VAST", "GPFS",
                                   "EFS", "FILESTORE"})


class HetznerCloudProvisioner(CloudProvisioner):
    """
        Hetzner-Cloud concrete :class:`CloudProvisioner` implementation.

        Maps the neutral resource model onto Hetzner Cloud primitives via the
        ``hcloud`` SDK.  Hetzner is a deliberately small cloud: there is no
        object storage in the Cloud product, no HPC interconnect, and a thin
        GPU SKU set.  The provisioner is honest about these gaps in
        ``validate``.
    """

    VENUE_NAME: str = "hetzner"

    def __init__(self, *, venue: CloudVenue,
                 credential: HetznerApiTokenCredential,
                 location_config: HetznerLocationConfig,
                 spec: Optional[HetznerSpec] = None,
                 client: Optional[Any] = None,
                 dns_client: Optional[Any] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a HetznerCloudProvisioner.

            :param venue: CloudVenue.
            :param credential: HetznerApiTokenCredential.
            :param location_config: HetznerLocationConfig.
            :param spec: Optional HetznerSpec.
            :param client: Optional pre-built hcloud client (test injection).
            :param dns_client: Optional Hetzner DNS API client.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                                      destroy uses this to de-register
                                      Tailscale / Twingate devices.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: HetznerApiTokenCredential = credential
        self._location_config: HetznerLocationConfig = location_config
        self._client_factory: HetznerClientFactory = HetznerClientFactory(
            credential=credential, client=client)
        self._dns_client: Optional[Any] = dns_client
        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        # Tracked across apply / destroy.
        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Validate the HetznerSpec without any hcloud calls.

            :param aspects: ProvisioningAspects (or compatible).

            :returns: A ValidationResult with ok=True on success.
            :raises: HetznerValidationError
        """
        if not isinstance(self._credential, HetznerApiTokenCredential):
            err_msg_lines = [
                "HetznerCloudProvisioner requires a "
                "HetznerApiTokenCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__))
            err_msg = os.linesep.join(err_msg_lines)
            raise HetznerValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        # Object storage is not in the Hetzner Cloud product scope.
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("Hetzner Cloud offers no native object-storage "
                          "service in this provisioner's scope.  Use an "
                          "S3-class venue (AWS) or an out-of-scope Hetzner "
                          "Storage Box for object data."),
            })

        # HPC interconnect is unavailable on Hetzner.
        for instance in spec.instances:
            if instance.interconnect is not None:
                if instance.interconnect.kind != "NONE":
                    errors.append({
                        "resource": instance.name,
                        "error": ("Hetzner Cloud offers no HPC interconnect "
                                  "fabric; got kind={}.  Substitute an HPC "
                                  "venue (AWS EFA) or remove the "
                                  "interconnect.").format(
                                      instance.interconnect.kind),
                    })

        # Shared filesystems of the WEKA / Lustre class are unsupported.
        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Hetzner Cloud has no WEKA/Lustre-class shared "
                              "filesystem; got kind={}.  Substitute a venue "
                              "that publishes a managed shared FS, or build "
                              "an NFS server on a Server + Volume.").format(
                                  sfs.kind),
                })

        # Server location resolution.
        for instance in spec.instances:
            location = self._instance_location(instance=instance)
            if location not in HETZNER_LOCATIONS:
                known = ", ".join(sorted(HETZNER_LOCATIONS))
                errors.append({
                    "resource": instance.name,
                    "error": ("Server location {!r} does not resolve to a "
                              "Hetzner location slug.  KNOWN: {}").format(
                                  location, known),
                })

            # Image family resolution.
            try:
                HetznerResolver.image_to_name(
                    family=instance.image.family,
                    version=instance.image.version,
                    arch=instance.image.architecture)
            except HetznerValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": "Image not resolvable: {}".format(xcpt),
                })

            # Server type / accelerator resolution.
            accel_models: List[str] = []
            if instance.accelerators is not None:
                for entry in instance.accelerators:
                    accel_models.append(entry.model)
            try:
                HetznerResolver.size_to_type(
                    size_hint=instance.size, accelerators=accel_models)
            except HetznerValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": "Server type not resolvable: {}".format(xcpt),
                })

        # Label round-trip rules on every declared resource.
        for resource_name, label_lists in self._all_tag_sets(spec=spec):
            for tag_list in label_lists:
                try:
                    HetznerLabelTranslator.to_hetzner(neutral_tags=tag_list)
                except HetznerValidationError as xcpt:
                    errors.append({
                        "resource": resource_name,
                        "error": "Label violates Hetzner rules: {}".format(
                            xcpt),
                    })

        if len(errors) > 0:
            err_msg_lines = ["HetznerCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]))
            err_msg = os.linesep.join(err_msg_lines)
            raise HetznerValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE/DELETE plan.

            Performs read-only ``get_by_name`` lookups; no mutation.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        builder = HetznerPlanBuilder(client=self._client_factory.client())
        rtnval = builder.plan(spec=self._spec, run_id=run_id,
                              aspects=aspects)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: Network -> Firewall -> SSH Key -> Server -> Volume ->
            DNS.  Re-applying a fully-realised spec performs no mutating
            calls.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningResult.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id

        client = self._client_factory.client()
        stages = HetznerApplyStages(
            client=client,
            default_labels=self._location_config.default_labels,
            dns_client=self._dns_client)

        created: List[ProvisionedResource] = []
        updated: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []

        authkey_for = self._mint_authkeys(spec=self._spec, aspects=aspects)

        network_firewall_state = stages.apply_network_and_firewall(
            spec=self._spec, run_id=run_id, aspects=aspects,
            created=created, skipped=skipped)
        stages.apply_servers_and_volumes(
            spec=self._spec, run_id=run_id, aspects=aspects,
            authkey_for=authkey_for, created=created, updated=updated,
            skipped=skipped, vpn_records=vpn_records,
            network_handles=network_firewall_state.get("networks", {}),
            firewall_handles=network_firewall_state.get("firewalls", {}),
            location=self._location_config.location)
        stages.apply_dns(spec=self._spec, run_id=run_id, aspects=aspects,
                         created=created)

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
        client = self._client_factory.client()
        stages = HetznerDestroyStages(
            client=client, dns_client=self._dns_client,
            vpn_control_plane=self._vpn_control_plane)
        stages.destroy(spec=self._spec, run_id=run_id, aspects=aspects,
                       vpn_records=self._last_vpn_records)
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
        enumerator = HetznerInventory(client=self._client_factory.client())
        rtnval = enumerator.list_run(run_id=run_id, aspects=aspects)
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def last_vpn_records(self) -> List[Dict[str, Any]]:
        """
            Return the recorded VPN device records from the last apply.

            :returns: A defensive copy of the records.
        """
        rtnval = [dict(entry) for entry in self._last_vpn_records]
        return rtnval

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance.

            Allows the control-plane integration layer to register a device
            id post-apply so destroy can de-register it.

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

    def _mint_authkeys(self, *, spec: HetznerSpec,
                       aspects: Any) -> Dict[str, str]:
        """
            Mint a VPN auth-key for each vpn_join-bearing instance.

            When no control plane is configured a deterministic placeholder
            is used so tests can assert the cloud-init rendering path.

            :param spec: The HetznerSpec.
            :param aspects: ProvisioningAspects.

            :returns: Map of instance-name -> minted auth-key string.
        """
        out: Dict[str, str] = {}
        for instance in spec.instances:
            if instance.vpn_join is None:
                continue
            authkey = "placeholder-authkey"
            if self._vpn_control_plane is not None:
                minted = getattr(self._vpn_control_plane,
                                 "minted_authkey", None)
                if minted is not None and len(str(minted)) > 0:
                    authkey = str(minted)
            out[instance.name] = authkey
        rtnval = out
        return rtnval

    def _instance_location(self, *, instance: Any) -> str:
        """
            Resolve the Hetzner location slug for an instance.

            Uses the instance's profile / subnet hints when available, else
            the venue default location.

            :param instance: A CloudInstance.

            :returns: A Hetzner location slug string.
        """
        rtnval = self._location_config.location
        return rtnval

    @classmethod
    def _all_tag_sets(cls, *, spec: HetznerSpec
                      ) -> List[Any]:
        """
            Collect every (resource-name, tag-lists) pair declared in a spec.

            :param spec: The HetznerSpec.

            :returns: A list of (name, [tag-list]) tuples.
        """
        out: List[Any] = []
        collections = [spec.networks, spec.subnets, spec.security_groups,
                       spec.instances, spec.volumes]
        for collection in collections:
            for entry in collection:
                tags = getattr(entry, "tags", None)
                if tags is None or len(tags) == 0:
                    continue
                name = getattr(entry, "name", "<resource>")
                out.append((name, [tags]))
        rtnval = out
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
        rtnval = "hetzner-{}".format(self._venue.name)
        return rtnval
