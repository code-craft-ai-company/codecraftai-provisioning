"""
    .. module:: xcpngcloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XcpngCloudProvisioner — concrete :class:`CloudProvisioner` for
        XCP-ng / Citrix Hypervisor (XenServer) Pools.

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

from ccai.provisioning.venues.xcpng.xenapplystages import (
    XenApplyResult, XenApplyStages
)
from ccai.provisioning.venues.xcpng.xencloudinitrenderer import (
    XenCloudInitRenderer
)
from ccai.provisioning.venues.xcpng.xendestroystages import (
    XenDestroyStages
)
from ccai.provisioning.venues.xcpng.xenerrors import (
    ConfirmationRequiredError, XenValidationError
)
from ccai.provisioning.venues.xcpng.xeninventory import XenInventory
from ccai.provisioning.venues.xcpng.xenplanbuilder import XenPlanBuilder
from ccai.provisioning.venues.xcpng.xenresolver import XenResolver
from ccai.provisioning.venues.xcpng.xcpngspec import XcpngSpec


# HPC interconnect kinds XCP-ng cannot realise; only NONE / unset is
# acceptable.  A non-NONE interconnect is a validate-error.
_REJECTED_INTERCONNECT_KINDS = frozenset({
    "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR",
    "ROCE", "NVLINK", "NVSWITCH", "EFA", "OCI_RDMA",
})


class XcpngCloudProvisioner(CloudProvisioner):
    """
        XCP-ng / XenServer concrete :class:`CloudProvisioner`.

        XCP-ng realises VMs (cloned from a Template), XAPI Networks, and VDIs
        on a Storage Repository through the ``codecraftai-interop-xen``
        :class:`XenClient`.  It is honest about every gap: security-group
        and DNS resources produce warnings (security-group intent is recorded
        in VM tags), while object buckets and load balancers — and any
        non-NONE HPC interconnect — produce validate-errors.

        The spec is an :class:`XcpngSpec` bundle of neutral resource objects.
        Every method accepts ``aspects`` and propagates it to the interop
        client.
    """

    VENUE_NAME: str = "xcpng"

    def __init__(self, *, venue: CloudVenue, client: Any,
                 spec: Optional[XcpngSpec] = None,
                 resolver: Optional[XenResolver] = None,
                 vpn_control_plane: Optional[Any] = None,
                 output_root: str = ".output") -> None:
        """
            Construct an XcpngCloudProvisioner.

            :param venue: The :class:`CloudVenue`.
            :param client: The XCP-ng interop client (a ``XenClient`` or a
                           test double exposing the same api-group surface).
            :param spec: Optional :class:`XcpngSpec`.
            :param resolver: Optional :class:`XenResolver`; defaults to a
                             fresh resolver.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                                      destroy uses this to de-register VPN
                                      devices.
            :param output_root: The output root directory for inventory
                                snapshots.
        """
        super().__init__(venue=venue, spec=spec)
        self._client: Any = client
        if resolver is not None:
            self._resolver: XenResolver = resolver
        else:
            self._resolver = XenResolver()
        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        self._output_root: str = output_root

        self._cloud_init_renderer = XenCloudInitRenderer()
        self._plan_builder = XenPlanBuilder(client=client,
                                            resolver=self._resolver)
        self._apply_stages = XenApplyStages(
            client=client, resolver=self._resolver,
            cloud_init_renderer=self._cloud_init_renderer)
        self._destroy_stages = XenDestroyStages(client=client)
        self._inventory = XenInventory(client=client,
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
            Validate the :class:`XcpngSpec` without any remote I/O.

            :param aspects: Aspects controlling validation behaviour.

            :returns: A :class:`ValidationResult` with ok=True on success.

            :raises: :class:`XenValidationError` when the spec contains
                resources XCP-ng cannot realise.
        """
        _ = aspects
        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        self._validate_unsupported_kinds(spec=spec, errors=errors)
        self._validate_warned_kinds(spec=spec, warnings=warnings)
        self._validate_instances(spec=spec, errors=errors,
                                 warnings=warnings)

        if len(errors) > 0:
            err_msg_lines = [
                "XcpngCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]))
            err_msg = os.linesep.join(err_msg_lines)
            raise XenValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

    @staticmethod
    def _validate_unsupported_kinds(*, spec: XcpngSpec,
                                    errors: List[Dict[str, Any]]) -> None:
        """
            Append validate-errors for resource kinds XCP-ng cannot realise.

            :param spec: The :class:`XcpngSpec`.
            :param errors: The accumulating error list.
        """
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("XCP-ng has no object-storage service; "
                          "CloudObjectBucket cannot be realised."),
            })
        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("XCP-ng has no load-balancing service; "
                          "CloudLoadBalancer cannot be realised."),
            })
        return

    @staticmethod
    def _validate_warned_kinds(*, spec: XcpngSpec,
                               warnings: List[Dict[str, Any]]) -> None:
        """
            Append validate-warnings for the kinds XCP-ng folds or ignores.

            :param spec: The :class:`XcpngSpec`.
            :param warnings: The accumulating warning list.
        """
        for sg in spec.security_groups:
            warnings.append({
                "resource": sg.name,
                "warning": ("XCP-ng exposes no native firewall; "
                            "CloudSecurityGroup intent is recorded in VM "
                            "tags only."),
            })
        for record in spec.dns_records:
            warnings.append({
                "resource": record.name,
                "warning": ("XCP-ng has no DNS service; CloudDnsRecord must "
                            "be realised by an external DNS provider."),
            })
        for subnet in spec.subnets:
            warnings.append({
                "resource": subnet.name,
                "warning": ("XCP-ng folds CloudSubnet into cloud-init "
                            "DHCP/static configuration."),
            })
        return

    def _validate_instances(self, *, spec: XcpngSpec,
                            errors: List[Dict[str, Any]],
                            warnings: List[Dict[str, Any]]) -> None:
        """
            Validate each instance's size and interconnect.

            :param spec: The :class:`XcpngSpec`.
            :param errors: The accumulating error list.
            :param warnings: The accumulating warning list.
        """
        _ = warnings
        for inst in spec.instances:
            try:
                self._resolver.size_to_hardware(size_hint=inst.size)
            except XenValidationError as xcpt:
                errors.append({
                    "resource": inst.name,
                    "error": "Unresolvable size: {}".format(xcpt),
                })

            if inst.interconnect is not None:
                kind = inst.interconnect.kind
                if kind in _REJECTED_INTERCONNECT_KINDS:
                    errors.append({
                        "resource": inst.name,
                        "error": ("XCP-ng does not support the HPC "
                                  "interconnect {!r}; only NONE is "
                                  "acceptable.").format(kind),
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

            Stages: ensure Networks + verify an SR is reachable, then clone
            each VM from its Template, apply hardware + tags, attach VDIs,
            push cloud-init through the xenstore ``vm-data/cloud-init`` keys,
            and start the VM.

            :param aspects: Aspects controlling apply behaviour.

            :returns: A :class:`ProvisioningResult`.

            :raises: :class:`ConfirmationRequiredError` when the plan
                contains a DELETE / UPDATE action and ``aspects.confirm`` is
                false.
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
            intent = action.intent_enum
            destructive = (intent == PlannedActionIntent.DELETE
                           or intent == PlannedActionIntent.UPDATE)
            if destructive and confirm is not True:
                err_msg_lines = [
                    "XCP-ng apply requires aspects.confirm=True for a "
                    "destructive plan action."]
                err_msg_lines.append("RESOURCE: {}".format(
                    action.resource_name))
                err_msg_lines.append("INTENT: {}".format(intent.value))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfirmationRequiredError(err_msg)

        result = XenApplyResult()
        self._apply_stages.apply_networks_and_sr_validation(
            spec=self._spec, result=result, aspects=aspects)
        self._apply_stages.apply_vms(
            spec=self._spec, run_id=run_id, result=result,
            vpn_control_plane=self._vpn_control_plane, aspects=aspects)

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
            Tear down run-owned VMs and de-register VPN devices.

            :param aspects: Aspects controlling destroy behaviour.
        """
        run_id = self._run_id(aspects=aspects)
        self._destroy_stages.destroy(
            spec=self._spec, run_id=run_id,
            vpn_records=self._last_vpn_records,
            vpn_control_plane=self._vpn_control_plane, aspects=aspects)
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate run-owned XCP-ng resources across the Pool.

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
        rtnval = "xcpng-{}".format(self._venue.name)
        return rtnval
