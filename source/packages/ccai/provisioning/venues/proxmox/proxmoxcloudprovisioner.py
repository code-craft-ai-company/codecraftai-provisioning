"""
    .. module:: proxmoxcloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: ProxmoxCloudProvisioner — concrete CloudProvisioner for the
               Proxmox Virtual Environment venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

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

from ccai.provisioning.venues.proxmox.pveapplystages import (
    PveApplyResult, PveApplyStages
)
from ccai.provisioning.venues.proxmox.pvedestroystages import (
    PveDestroyStages
)
from ccai.provisioning.venues.proxmox.pveerrors import (
    ConfirmationRequiredError, PveValidationError
)
from ccai.provisioning.venues.proxmox.pveinventory import PveInventory
from ccai.provisioning.venues.proxmox.pveplanbuilder import PvePlanBuilder
from ccai.provisioning.venues.proxmox.pveresolver import PveResolver
from ccai.provisioning.venues.proxmox.proxmoxspec import ProxmoxSpec

from ccai.credentials.proxmoxapitokencredential import (
    ProxmoxApiTokenCredential
)


# Interconnect kinds Proxmox cannot realise; an instance carrying one of
# these (anything other than NONE) is a validate-error.
_INTERCONNECT_NONE = "NONE"

# Shared-FS classes Proxmox can attach via an existing NFS/CIFS mount.
_SUPPORTED_SHARED_FS_KINDS = frozenset({"NFS", "CIFS", "SMB"})


class ProxmoxCloudProvisioner(CloudProvisioner):
    """
        Proxmox-VE-venue concrete :class:`CloudProvisioner`.

        Proxmox VE is a self-hosted virtualization venue.  This provisioner
        maps the neutral resource model onto Proxmox primitives via the
        ``codecraftai-interop-proxmox`` :class:`ProxmoxClient`: CloudNetwork to
        a Linux bridge, CloudInstance to a QEMU VM cloned from a template,
        CloudStorageVolume to a virtual disk, CloudKeyPair to cloud-init SSH
        keys, and ``VPNJoinSpec`` to an uploaded cloud-init snippet.

        Proxmox has no object storage and no load balancing, so
        CloudObjectBucket and CloudLoadBalancer are validate-errors; HPC
        interconnects are likewise validate-errors.  DNS records produce a
        warning.  Every method accepts ``aspects`` and propagates it to the
        interop client.
    """

    VENUE_NAME: str = "proxmox"

    def __init__(self, *, venue: CloudVenue,
                 credential: ProxmoxApiTokenCredential,
                 client: Any,
                 spec: Optional[ProxmoxSpec] = None,
                 resolver: Optional[PveResolver] = None,
                 vpn_control_plane: Optional[Any] = None,
                 output_root: str = ".output") -> None:
        """
            Construct a ProxmoxCloudProvisioner.

            :param venue: The :class:`CloudVenue`.
            :param credential: A :class:`ProxmoxApiTokenCredential`.
            :param client: The Proxmox interop client (a
                :class:`ProxmoxClient` or a test double).
            :param spec: Optional :class:`ProxmoxSpec`.
            :param resolver: Optional :class:`PveResolver`; defaults to a
                fresh resolver bound to the packaged catalog.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                destroy uses this to de-register VPN devices.
            :param output_root: The output root directory for inventory
                files.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: ProxmoxApiTokenCredential = credential
        self._client: Any = client
        if resolver is not None:
            self._resolver: PveResolver = resolver
        else:
            self._resolver = PveResolver()
        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        self._output_root: str = output_root

        self._plan_builder = PvePlanBuilder(client=client,
                                            resolver=self._resolver)
        self._apply_stages = PveApplyStages(client=client,
                                            resolver=self._resolver)
        self._destroy_stages = PveDestroyStages(client=client)
        self._inventory = PveInventory(client=client,
                                       output_root=output_root)

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    @property
    def last_vpn_records(self) -> List[Dict[str, Any]]:
        """
            Return the VPN-device records captured during the last apply.

            :returns: A defensive copy of the records.
        """
        rtnval = [dict(entry) for entry in self._last_vpn_records]
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the :class:`ProxmoxSpec` without any remote I/O.

            :param aspects: Aspects controlling validation behaviour.

            :returns: A :class:`ValidationResult` with ok=True on success.

            :raises: :class:`PveValidationError` when the spec contains
                resources Proxmox cannot realise.
        """
        # `aspects` is accepted for interface uniformity; validate does no
        # remote I/O so there is no behaviour to control.
        _ = aspects

        if not isinstance(self._credential, ProxmoxApiTokenCredential):
            err_msg_lines = [
                "ProxmoxCloudProvisioner requires a "
                "ProxmoxApiTokenCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise PveValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        self._validate_unsupported(spec=spec, errors=errors,
                                   warnings=warnings)
        self._validate_instances(spec=spec, errors=errors)

        if len(errors) > 0:
            err_msg_lines = [
                "ProxmoxCloudProvisioner.validate found errors."
            ]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise PveValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

    def _validate_unsupported(self, *, spec: ProxmoxSpec,
                              errors: List[Dict[str, Any]],
                              warnings: List[Dict[str, Any]]) -> None:
        """
            Append errors / warnings for resources Proxmox cannot realise.

            :param spec: The :class:`ProxmoxSpec`.
            :param errors: The error accumulator.
            :param warnings: The warning accumulator.

            :returns: ``None``.
        """
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("Proxmox has no object-storage service; "
                          "CloudObjectBucket cannot be realised."),
            })
        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("Proxmox has no load-balancing service; "
                          "CloudLoadBalancer cannot be realised."),
            })
        for record in spec.dns_records:
            warnings.append({
                "resource": record.name,
                "warning": ("Proxmox manages no DNS zone; CloudDnsRecord "
                            "is ignored — provision DNS externally."),
            })
        for sfs in spec.shared_filesystems:
            kind = getattr(sfs, "kind", None)
            existing_id = getattr(sfs, "existing_id", None)
            attachable = False
            if kind is not None and kind in _SUPPORTED_SHARED_FS_KINDS:
                attachable = True
            if existing_id is not None and len(str(existing_id)) > 0:
                attachable = True
            if attachable is not True:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Proxmox can attach only an existing NFS/CIFS "
                              "share; this CloudSharedFilesystem kind has "
                              "no realisation."),
                })
        return

    def _validate_instances(self, *, spec: ProxmoxSpec,
                            errors: List[Dict[str, Any]]) -> None:
        """
            Append per-instance validation errors.

            :param spec: The :class:`ProxmoxSpec`.
            :param errors: The error accumulator.

            :returns: ``None``.
        """
        for inst in spec.instances:
            interconnect = inst.interconnect
            if interconnect is not None:
                kind = getattr(interconnect, "kind", _INTERCONNECT_NONE)
                kind_value = getattr(kind, "value", kind)
                if kind_value not in (_INTERCONNECT_NONE, "none"):
                    errors.append({
                        "resource": inst.name,
                        "error": ("Proxmox has no HPC interconnect fabric; "
                                  "CloudInterconnect kind {!r} cannot be "
                                  "realised.").format(kind_value),
                    })

            node = self._resolver.resolve_node(instance=inst)
            if node is None:
                errors.append({
                    "resource": inst.name,
                    "error": ("Proxmox VM has no resolvable target node; "
                              "set the instance 'placement_group' field or "
                              "configure a resolver default node."),
                })

            try:
                self._resolver.image_to_template_or_url(image=inst.image)
            except PveValidationError as xcpt:
                errors.append({
                    "resource": inst.name,
                    "error": "Image not resolvable on Proxmox: {}".format(
                        xcpt
                    ),
                })

            try:
                self._resolver.size_to_hardware(size_hint=inst.size)
            except PveValidationError as xcpt:
                errors.append({
                    "resource": inst.name,
                    "error": "Size not resolvable on Proxmox: {}".format(
                        xcpt
                    ),
                })
        return

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan.

            :param aspects: Aspects controlling planning behaviour.

            :returns: A :class:`ProvisioningPlan`.
        """
        run_id = self._run_id(aspects=aspects)
        rtnval = self._plan_builder.plan(spec=self._spec, run_id=run_id,
                                         aspects=aspects)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: ensure bridges, then clone-from-template each VM,
            attach disks, render and reference a cloud-init snippet (the M6
            renderer when the VM carries a ``vpn_join`` spec), tag, and
            power-on.

            :param aspects: Aspects controlling apply behaviour.

            :returns: A :class:`ProvisioningResult`.

            :raises: :class:`ConfirmationRequiredError` when the plan
                contains an UPDATE-by-recreate action and
                ``aspects.confirm`` is false.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id

        plan = self._plan_builder.plan(spec=self._spec, run_id=run_id,
                                       aspects=aspects)
        confirm = self._aspect_attr(aspects=aspects, name="confirm",
                                    default=False)
        for action in plan.actions:
            if action.intent == PlannedActionIntent.UPDATE.value:
                if confirm is not True:
                    err_msg_lines = [
                        "Proxmox apply requires aspects.confirm=True for "
                        "a VM-hardware UPDATE."
                    ]
                    err_msg_lines.append("RESOURCE: {}".format(
                        action.resource_name
                    ))
                    err_msg = os.linesep.join(err_msg_lines)
                    raise ConfirmationRequiredError(err_msg)

        result = PveApplyResult()
        self._apply_stages.apply_networking(spec=self._spec, result=result,
                                            aspects=aspects)
        self._apply_stages.apply_vms(
            spec=self._spec, run_id=run_id, result=result,
            vpn_control_plane=self._vpn_control_plane, aspects=aspects,
        )

        self._last_vpn_records = result.vpn_records

        rtnval = ProvisioningResult(created=result.created,
                                    updated=result.updated,
                                    skipped=result.skipped, errors=[])
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Stop and delete run-owned VMs and de-register VPN devices.

            :param aspects: Aspects controlling destroy behaviour.

            :returns: ``None``.
        """
        run_id = self._run_id(aspects=aspects)
        self._destroy_stages.destroy(
            spec=self._spec, run_id=run_id,
            vpn_records=self._last_vpn_records,
            vpn_control_plane=self._vpn_control_plane, aspects=aspects,
        )
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate run-owned Proxmox resources.

            :param aspects: Aspects controlling inventory behaviour.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        run_id = self._run_id(aspects=aspects)
        resources = self._inventory.list_run(run_id=run_id, aspects=aspects)
        self._inventory.persist(run_id=run_id, resources=resources)
        rtnval = resources
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
        rtnval = "proxmox-{}".format(self._venue.name)
        return rtnval
