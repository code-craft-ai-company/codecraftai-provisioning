"""
    .. module:: vultrcloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VultrCloudProvisioner — concrete CloudProvisioner for Vultr.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.credentials.vultrapikeycredential import VultrApiKeyCredential
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
from automojo.provisioning.venues.vpncleanup import delete_vpn_device

from automojo.provisioning.venues.vultr.vultrapplystages import (
    VultrApplyStages
)
from automojo.provisioning.venues.vultr.vultrclient import VultrClient
from automojo.provisioning.venues.vultr.vultrdestroystages import (
    VultrDestroyStages
)
from automojo.provisioning.venues.vultr.vultrerrors import (
    VultrValidationError
)
from automojo.provisioning.venues.vultr.vultrinventory import VultrInventory
from automojo.provisioning.venues.vultr.vultrplanbuilder import (
    VultrPlanBuilder
)
from automojo.provisioning.venues.vultr.vultrresolver import VultrResolver
from automojo.provisioning.venues.vultr.vultrspec import VultrSpec


# HPC interconnect kinds Vultr cannot realise (anything other than NONE).
_REJECTED_INTERCONNECTS = frozenset({
    "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR", "OCI_RDMA",
    "EFA", "NVSWITCH", "NVLINK",
})

# WEKA / Lustre-class shared filesystems Vultr has no managed service for.
_REJECTED_FS_KINDS = frozenset({
    "LUSTRE", "WEKA", "VAST", "GPFS", "EFS", "FILESTORE",
})


class VultrCloudProvisioner(CloudProvisioner):
    """
        Vultr-venue concrete :class:`CloudProvisioner` implementation.

        Realises the neutral resource model on Vultr via the Vultr v2 REST
        API (``api.vultr.com/v2``) called directly with Bearer auth — there
        is no first-party Vultr SDK, so the venue talks REST itself.

        Mapping: CloudNetwork→VPC 2.0, CloudSecurityGroup→Firewall Group +
        rules, CloudKeyPair→SSH Key, CloudInstance→Instance,
        CloudStorageVolume→Block Storage, CloudObjectBucket→Object Storage,
        CloudDnsRecord→Domain record.  VPNJoinSpec is rendered into the
        base64 ``user_data`` body.
    """

    VENUE_NAME: str = "vultr"

    def __init__(self, *, venue: CloudVenue,
                 credential: VultrApiKeyCredential,
                 spec: Optional[VultrSpec] = None,
                 client: Optional[VultrClient] = None,
                 default_tags: Optional[Dict[str, str]] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a VultrCloudProvisioner.

            :param venue: The CloudVenue this provisioner targets.
            :param credential: VultrApiKeyCredential carrying the API key.
            :param spec: Optional VultrSpec bundle of neutral resources.
            :param client: Optional pre-built VultrClient (tests inject one).
            :param default_tags: Optional venue default neutral tags.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl used
                                      by destroy to de-register VPN devices.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: VultrApiKeyCredential = credential
        if client is not None:
            self._client: VultrClient = client
        else:
            self._client = VultrClient(token=credential.token)

        if default_tags is not None:
            self._default_tags: Dict[str, str] = dict(default_tags)
        else:
            self._default_tags = {}

        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        self._resolver: VultrResolver = VultrResolver(client=self._client)
        self._plan_builder: VultrPlanBuilder = VultrPlanBuilder(
            client=self._client
        )
        self._apply_stages: VultrApplyStages = VultrApplyStages(
            client=self._client, resolver=self._resolver
        )
        self._destroy_stages: VultrDestroyStages = VultrDestroyStages(
            client=self._client
        )
        self._inventory: VultrInventory = VultrInventory(client=self._client)

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Validate the VultrSpec.

            Rejects HPC interconnect kinds and WEKA/Lustre-class shared
            filesystems, and confirms every instance region resolves.

            :param aspects: Aspects controlling validation behaviour.

            :returns: A ValidationResult with ok=True on success.
            :raises: VultrValidationError
        """
        if not isinstance(self._credential, VultrApiKeyCredential):
            err_msg_lines = [
                "VultrCloudProvisioner requires a VultrApiKeyCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise VultrValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        # Confirm every declared network region resolves to a real Vultr
        # region so an unresolvable region fails validate, not apply.
        for net in spec.networks:
            region = getattr(net, "region", None)
            if region is None or len(region) == 0:
                errors.append({
                    "resource": net.name,
                    "error": "CloudNetwork has no region; a Vultr region "
                             "slug is required.",
                })
                continue
            if not self._resolver.region_is_known(region=region):
                errors.append({
                    "resource": net.name,
                    "error": ("Region {!r} does not resolve to a known "
                              "Vultr region.").format(region),
                })

        for sfs in spec.shared_filesystems:
            if sfs.kind in _REJECTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Vultr has no managed shared-FS service of "
                              "the WEKA/Lustre class; kind={} is not "
                              "supported.").format(sfs.kind),
                })

        for instance in spec.instances:
            if instance.interconnect is not None:
                kind = instance.interconnect.kind
                if kind != "NONE":
                    errors.append({
                        "resource": instance.name,
                        "error": ("Vultr has no HPC interconnect; "
                                  "CloudInterconnect kind={} is not "
                                  "supported.").format(kind),
                    })

            if instance.image.family.lower() not in (
                "ubuntu", "debian", "rhel", "fedora", "almalinux", "centos"
            ):
                errors.append({
                    "resource": instance.name,
                    "error": ("OS family {!r} is unknown to the Vultr "
                              "resolver.").format(instance.image.family),
                })

            accelerators = (instance.accelerators
                            if instance.accelerators is not None else [])
            if len(accelerators) > 0:
                model = accelerators[0].model
                if model not in VultrResolver.accelerator_models():
                    errors.append({
                        "resource": instance.name,
                        "error": ("Accelerator model {!r} is not available "
                                  "on Vultr.").format(model),
                    })

        if len(errors) > 0:
            err_msg_lines = ["VultrCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise VultrValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan.

            Reads Vultr state filtered by owner tag; performs no mutation.

            :param aspects: Aspects controlling planning behaviour.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        rtnval = self._plan_builder.plan(spec=self._spec, run_id=run_id)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stage order: VPC → Firewall Group → SSH Key → Instance → Block
            Storage → Object Storage → DNS.

            :param aspects: Aspects controlling apply behaviour.

            :returns: A ProvisioningResult.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id

        created: List[ProvisionedResource] = []
        skipped: List[str] = []

        stage1 = self._apply_stages.apply_network_and_firewall(
            spec=self._spec, run_id=run_id, default_tags=self._default_tags,
        )
        created.extend(stage1["created"])
        skipped.extend(stage1["skipped"])

        authkey = ""
        if self._vpn_control_plane is not None:
            authkey = getattr(self._vpn_control_plane, "minted_authkey", "")
            if authkey is None:
                authkey = ""

        stage2 = self._apply_stages.apply_instances_and_blocks(
            spec=self._spec, run_id=run_id, default_tags=self._default_tags,
            networks=stage1["networks"], firewalls=stage1["firewalls"],
            keypairs=stage1["keypairs"], authkey=authkey,
        )
        created.extend(stage2["created"])
        skipped.extend(stage2["skipped"])
        self._last_vpn_records = stage2["vpn_records"]

        stage3 = self._apply_stages.apply_object_storage_and_dns(
            spec=self._spec, run_id=run_id,
        )
        created.extend(stage3["created"])
        skipped.extend(stage3["skipped"])

        rtnval = ProvisioningResult(created=created, updated=[],
                                    skipped=skipped, errors=[])
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Destroy every owned resource in reverse dependency order.

            :param aspects: Aspects controlling destroy behaviour.
        """
        run_id = self._run_id(aspects=aspects)
        terminated = self._destroy_stages.destroy(spec=self._spec,
                                                  run_id=run_id)

        if self._vpn_control_plane is not None:
            self._cleanup_vpn_devices(records=self._last_vpn_records,
                                      aspects=aspects)
            self._cleanup_vpn_devices(records=terminated, aspects=aspects)
        return

    def _cleanup_vpn_devices(self, *, records: List[Dict[str, Any]],
                             aspects: Any) -> None:
        """
            De-register VPN devices for a list of VPN records.

            :param records: VPN device records.
            :param aspects: Aspects.
        """
        for record in records:
            device_id = record.get("vpn_device_id", None)
            if device_id is None or len(str(device_id)) == 0:
                continue
            delete_vpn_device(vpn_control_plane=self._vpn_control_plane,
                              device_id=device_id, aspects=aspects)
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any = None) -> List[ProvisionedResource]:
        """
            Enumerate owned resources for the run.

            :param aspects: Aspects controlling inventory behaviour.

            :returns: A list of ProvisionedResource entries.
        """
        run_id = self._run_id(aspects=aspects)
        resources = self._inventory.list_run(run_id=run_id)
        try:
            self._inventory.persist(run_id=run_id, resources=resources)
        except OSError:
            pass
        rtnval = resources
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
        rtnval = "vultr-{}".format(self._venue.name)
        return rtnval
