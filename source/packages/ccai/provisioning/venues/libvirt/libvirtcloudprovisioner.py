"""
    .. module:: libvirtcloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LibvirtCloudProvisioner — concrete CloudProvisioner for a
               libvirt / KVM host (or a small farm of them).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

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

from ccai.provisioning.venues.libvirt.libvirtspec import LibvirtSpec
from ccai.provisioning.venues.libvirt.libvirtvenueconfig import (
    LibvirtVenueConfig
)
from ccai.provisioning.venues.libvirt.lvapplystages import (
    LvApplyResult, LvApplyStages
)
from ccai.provisioning.venues.libvirt.lvdestroystages import (
    LvDestroyStages
)
from ccai.provisioning.venues.libvirt.lverrors import (
    ConfirmationRequiredError, LvValidationError
)
from ccai.provisioning.venues.libvirt.lvinventory import LvInventory
from ccai.provisioning.venues.libvirt.lvplanbuilder import LvPlanBuilder
from ccai.provisioning.venues.libvirt.lvseedisobuilder import (
    LvSeedIsoBuilder
)


class LibvirtCloudProvisioner(CloudProvisioner):
    """
        libvirt-venue concrete :class:`CloudProvisioner`.

        libvirt realises VMs on a single hypervisor host (or a small farm
        addressed by per-URI connections) through the ``libvirt-python``
        native bindings surfaced by ``codecraftai-interop-libvirt`` — there
        is no REST involved.

        The neutral resource model maps onto libvirt primitives as
        follows: :class:`CloudNetwork` becomes a libvirt virtual network;
        :class:`CloudInstance` becomes a Domain defined from XML with a
        boot disk cloned from a base cloud-image; :class:`CloudKeyPair`
        public keys are injected into the cloud-init seed ISO;
        :class:`CloudStorageVolume` becomes a qcow2 volume in a pool;
        and a :class:`VPNJoinSpec` is rendered into the seed ISO's
        ``user-data`` cloud-init document.  libvirt has no native object
        storage, load balancer, or HPC interconnect — those produce
        validate-errors.

        Every method accepts ``aspects`` and propagates it to the
        interop client; ``None`` substitutes the engine default.
    """

    VENUE_NAME: str = "libvirt"

    def __init__(self, *, venue: CloudVenue, client: Any,
                 config: Optional[LibvirtVenueConfig] = None,
                 spec: Optional[LibvirtSpec] = None,
                 vpn_control_plane: Optional[Any] = None,
                 output_root: str = ".output") -> None:
        """
            Construct a LibvirtCloudProvisioner.

            :param venue: The :class:`CloudVenue`.
            :param client: The libvirt interop client (a
                :class:`LibvirtClient` or a test double).
            :param config: Optional :class:`LibvirtVenueConfig`;
                defaults to a fresh config targeting ``qemu:///system``.
            :param spec: Optional :class:`LibvirtSpec`.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                destroy uses this to de-register VPN devices.
            :param output_root: The output root directory for inventory
                snapshots.
        """
        super().__init__(venue=venue, spec=spec)
        self._client: Any = client
        if config is not None:
            self._config: LibvirtVenueConfig = config
        else:
            self._config = LibvirtVenueConfig()
        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        self._output_root: str = output_root

        self._plan_builder = LvPlanBuilder(client=client,
                                           config=self._config)
        seed_builder = LvSeedIsoBuilder(staging_root=output_root)
        self._apply_stages = LvApplyStages(client=client,
                                           config=self._config,
                                           seed_builder=seed_builder)
        self._destroy_stages = LvDestroyStages(client=client,
                                               config=self._config)
        self._inventory = LvInventory(client=client, config=self._config,
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
            Validate the :class:`LibvirtSpec` without any remote I/O.

            :param aspects: Aspects controlling validation behaviour.

            :returns: A :class:`ValidationResult` with ok=True on
                success.

            :raises: :class:`LvValidationError` when the spec contains
                resources libvirt cannot realise.
        """
        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        self._validate_unsupported_kinds(spec=spec, errors=errors,
                                         warnings=warnings)
        self._validate_instances(spec=spec, errors=errors)

        if len(errors) > 0:
            err_msg_lines = [
                "LibvirtCloudProvisioner.validate found errors."
            ]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise LvValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

    def _validate_unsupported_kinds(self, *, spec: LibvirtSpec,
                                    errors: List[Dict[str, Any]],
                                    warnings: List[Dict[str, Any]]
                                    ) -> None:
        """
            Append errors for kinds libvirt cannot realise.

            :param spec: The :class:`LibvirtSpec`.
            :param errors: The accumulating error list.
            :param warnings: The accumulating warning list.

            :returns: ``None``.
        """
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("libvirt has no object-storage service; "
                          "CloudObjectBucket cannot be realised."),
            })
        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("libvirt has no load-balancing service; "
                          "CloudLoadBalancer cannot be realised."),
            })
        for record in spec.dns_records:
            errors.append({
                "resource": record.name,
                "error": ("libvirt has no DNS service; CloudDnsRecord "
                          "cannot be realised."),
            })

        for sfs in spec.shared_filesystems:
            if sfs.existing_id is None or len(sfs.existing_id) == 0:
                errors.append({
                    "resource": sfs.name,
                    "error": ("libvirt cannot provision a managed shared "
                              "filesystem; CloudSharedFilesystem must "
                              "carry an existing_id (attach-only)."),
                })

        for sg in spec.security_groups:
            warnings.append({
                "resource": sg.name,
                "warning": ("libvirt exposes no native firewall / "
                            "security-group model; CloudSecurityGroup "
                            "rules are not applied by this venue."),
            })
        for record in spec.dns_records:
            warnings.append({
                "resource": record.name,
                "warning": ("DNS records are external to libvirt and "
                            "are not managed by this venue."),
            })
        return

    def _validate_instances(self, *, spec: LibvirtSpec,
                            errors: List[Dict[str, Any]]) -> None:
        """
            Append errors for instance-level validation failures.

            :param spec: The :class:`LibvirtSpec`.
            :param errors: The accumulating error list.

            :returns: ``None``.
        """
        for instance in spec.instances:
            if instance.interconnect is not None:
                kind = instance.interconnect.kind
                if kind is not None and kind != "NONE":
                    errors.append({
                        "resource": instance.name,
                        "error": ("libvirt cannot realise an HPC "
                                  "interconnect ({}); CloudInterconnect "
                                  "must be NONE.").format(kind),
                    })

            uri = self._config.connection_uri
            if uri is None or len(uri) == 0:
                errors.append({
                    "resource": instance.name,
                    "error": ("Instance has no resolvable libvirt "
                              "connection URI."),
                })

            pool = self._config.boot_disk_pool
            if pool is None or len(pool) == 0:
                errors.append({
                    "resource": instance.name,
                    "error": ("Instance has no resolvable libvirt "
                              "storage pool."),
                })

            try:
                self._config.base_image_volume_for(
                    family=instance.image.family,
                    version=instance.image.version,
                )
            except LvValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": str(xcpt),
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

            Stages run in dependency order: Networks define+start →
            Volumes create → boot-volume clone + seed-ISO build →
            Domain define+start.  A ``vpn_join`` spec is rendered into
            the seed ISO via the M6 cloud-init renderer.

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
            if action.intent == "update" and confirm is not True:
                err_msg_lines = [
                    "libvirt apply requires aspects.confirm=True for an "
                    "UPDATE-by-recreate of a drifted domain."
                ]
                err_msg_lines.append("RESOURCE: {}".format(
                    action.resource_name
                ))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfirmationRequiredError(err_msg)

        result = LvApplyResult()

        self._apply_stages.apply_networks_and_pools(
            spec=self._spec, run_id=run_id, result=result, aspects=aspects
        )
        self._apply_stages.apply_volumes(
            spec=self._spec, run_id=run_id, result=result, aspects=aspects
        )
        self._apply_stages.apply_domains(
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
            Tear down run-owned domains, volumes, and networks.

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
            Enumerate run-owned libvirt domains.

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
            Resolve the run identifier from aspects or fall back to
            venue.

            :param aspects: Aspects.

            :returns: A non-empty run id string.
        """
        candidate = self._aspect_attr(aspects=aspects, name="runid",
                                      default=None)
        if candidate is not None and len(candidate) > 0:
            rtnval = candidate
            return rtnval
        rtnval = "libvirt-{}".format(self._venue.name)
        return rtnval
