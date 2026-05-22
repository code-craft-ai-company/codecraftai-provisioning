"""
    .. module:: nutanixcloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NutanixCloudProvisioner — concrete CloudProvisioner for a
               Nutanix AHV cluster fronted by Prism Central.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

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

from automojo.provisioning.venues.nutanix.nutanixspec import NutanixSpec
from automojo.provisioning.venues.nutanix.nutanixvenueconfig import (
    NutanixVenueConfig
)
from automojo.provisioning.venues.nutanix.ntxapplystages import (
    NtxApplyResult, NtxApplyStages
)
from automojo.provisioning.venues.nutanix.ntxdestroystages import (
    NtxDestroyStages
)
from automojo.provisioning.venues.nutanix.ntxerrors import (
    ConfirmationRequiredError, NtxValidationError
)
from automojo.provisioning.venues.nutanix.ntxinventory import NtxInventory
from automojo.provisioning.venues.nutanix.ntxplanbuilder import NtxPlanBuilder
from automojo.provisioning.venues.nutanix.ntxresolver import NtxResolver


class NutanixCloudProvisioner(CloudProvisioner):
    """
        Nutanix-venue concrete :class:`CloudProvisioner`.

        Nutanix realises VMs on an AHV cluster fronted by Prism Central
        through the v3 REST API surfaced by ``automojo-interop-nutanix``.

        The neutral resource model maps onto Nutanix primitives as
        follows: :class:`CloudNetwork` becomes a Flow VPC;
        :class:`CloudSubnet` becomes a Prism subnet (VLAN or VPC overlay);
        :class:`CloudSecurityGroup` becomes a Flow security policy;
        :class:`CloudInstance` becomes a VM cloned from a registered Prism
        image; :class:`CloudStorageVolume` becomes a volume group;
        :class:`CloudKeyPair` public keys are injected into the VM's
        cloud-init ``user_data``; and a :class:`VPNJoinSpec` is rendered
        into the VM's ``guest_customization.cloud_init.user_data``
        (base64-encoded) via the M6 cloud-init renderer.  Nutanix exposes
        no public object storage in Prism (unless Nutanix Objects is
        configured), no load balancer, and no HPC interconnect — those
        produce validate-errors.

        Every method accepts ``aspects`` and propagates it to the interop
        client; ``None`` substitutes the engine default.
    """

    VENUE_NAME: str = "nutanix"

    def __init__(self, *, venue: CloudVenue, client: Any,
                 config: Optional[NutanixVenueConfig] = None,
                 spec: Optional[NutanixSpec] = None,
                 vpn_control_plane: Optional[Any] = None,
                 output_root: str = ".output") -> None:
        """
            Construct a NutanixCloudProvisioner.

            :param venue: The :class:`CloudVenue`.
            :param client: The Nutanix interop client (a
                :class:`NutanixClient` or a test double).
            :param config: Optional :class:`NutanixVenueConfig`; defaults
                to a fresh config that picks the first cluster.
            :param spec: Optional :class:`NutanixSpec`.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                destroy uses this to de-register VPN devices.
            :param output_root: The output root directory for inventory
                snapshots.
        """
        super().__init__(venue=venue, spec=spec)
        self._client: Any = client
        if config is not None:
            self._config: NutanixVenueConfig = config
        else:
            self._config = NutanixVenueConfig()
        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        self._output_root: str = output_root

        self._resolver = NtxResolver(client=client, config=self._config)
        self._plan_builder = NtxPlanBuilder(client=client,
                                            config=self._config,
                                            resolver=self._resolver)
        self._apply_stages = NtxApplyStages(client=client,
                                            config=self._config,
                                            resolver=self._resolver)
        self._destroy_stages = NtxDestroyStages(client=client,
                                                config=self._config)
        self._inventory = NtxInventory(client=client, config=self._config,
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
            Validate the :class:`NutanixSpec` without any remote I/O.

            :param aspects: Aspects controlling validation behaviour.

            :returns: A :class:`ValidationResult` with ok=True on
                success.

            :raises: :class:`NtxValidationError` when the spec contains
                resources Nutanix cannot realise.
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
                "NutanixCloudProvisioner.validate found errors."
            ]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise NtxValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

    def _validate_unsupported_kinds(self, *, spec: NutanixSpec,
                                    errors: List[Dict[str, Any]],
                                    warnings: List[Dict[str, Any]]
                                    ) -> None:
        """
            Append errors for kinds Nutanix cannot realise.

            :param spec: The :class:`NutanixSpec`.
            :param errors: The accumulating error list.
            :param warnings: The accumulating warning list.

            :returns: ``None``.
        """
        for bucket in spec.buckets:
            if self._config.objects_configured is True:
                warnings.append({
                    "resource": bucket.name,
                    "warning": ("CloudObjectBucket is realised via Nutanix "
                                "Objects; bucket provisioning is an "
                                "extension and is not applied by the core "
                                "venue apply."),
                })
            else:
                errors.append({
                    "resource": bucket.name,
                    "error": ("Nutanix Objects is not configured in the "
                              "apod; CloudObjectBucket cannot be "
                              "realised."),
                })

        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("Prism Central has no load-balancing service; "
                          "CloudLoadBalancer cannot be realised."),
            })

        for record in spec.dns_records:
            errors.append({
                "resource": record.name,
                "error": ("Prism Central has no DNS service; "
                          "CloudDnsRecord cannot be realised."),
            })

        for sfs in spec.shared_filesystems:
            if sfs.existing_id is None or len(sfs.existing_id) == 0:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Nutanix cannot provision a managed shared "
                              "filesystem; CloudSharedFilesystem must "
                              "carry an existing_id (Nutanix Files "
                              "attach-only)."),
                })
        return

    def _validate_instances(self, *, spec: NutanixSpec,
                            errors: List[Dict[str, Any]]) -> None:
        """
            Append errors for instance-level validation failures.

            :param spec: The :class:`NutanixSpec`.
            :param errors: The accumulating error list.

            :returns: ``None``.
        """
        for instance in spec.instances:
            if instance.interconnect is not None:
                kind = instance.interconnect.kind
                if kind is not None and kind != "NONE":
                    errors.append({
                        "resource": instance.name,
                        "error": ("Nutanix cannot realise an HPC "
                                  "interconnect ({}); CloudInterconnect "
                                  "must be NONE.").format(kind),
                    })

            try:
                self._resolver.image_to_uuid(
                    family=instance.image.family,
                    version=instance.image.version,
                    arch=instance.image.architecture, aspects=None,
                )
            except NtxValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": str(xcpt),
                })

            try:
                self._resolver.size_to_hardware(size_hint=instance.size)
            except NtxValidationError as xcpt:
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

            Stages run in dependency order: Flow VPCs / Subnets / Flow
            security policies → Volume Groups → Image verification + VM
            clone (cloud-init guest customisation) → power-on.  A
            ``vpn_join`` spec is rendered into the VM's
            ``guest_customization.cloud_init.user_data``.

            :param aspects: Aspects controlling apply behaviour.

            :returns: A :class:`ProvisioningResult`.

            :raises: :class:`ConfirmationRequiredError` when the plan
                contains a DELETE action and ``aspects.confirm`` is false.
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
            if action.intent == "delete" and confirm is not True:
                err_msg_lines = [
                    "Nutanix apply requires aspects.confirm=True for a "
                    "DELETE action."
                ]
                err_msg_lines.append("RESOURCE: {}".format(
                    action.resource_name
                ))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfirmationRequiredError(err_msg)

            update_instance = (action.intent == "update"
                               and action.resource_kind == "instance")
            if update_instance is True and confirm is not True:
                err_msg_lines = [
                    "Nutanix apply requires aspects.confirm=True for an "
                    "in-place VM resize (UPDATE) — AHV applies the new "
                    "vCPU / memory intent spec at the next power cycle."
                ]
                err_msg_lines.append("RESOURCE: {}".format(
                    action.resource_name
                ))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfirmationRequiredError(err_msg)

        result = NtxApplyResult()

        self._apply_stages.apply_network_and_flow_policies(
            spec=self._spec, run_id=run_id, result=result, aspects=aspects
        )
        self._apply_stages.apply_volumes(
            spec=self._spec, run_id=run_id, result=result, aspects=aspects
        )
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
            Tear down run-owned VMs, volume groups, security policies,
            subnets and VPCs.

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
            Enumerate run-owned Prism Central VMs.

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
        rtnval = "nutanix-{}".format(self._venue.name)
        return rtnval
