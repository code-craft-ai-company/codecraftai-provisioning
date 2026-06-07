"""
    .. module:: lambdalabscloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LambdalabsCloudProvisioner — concrete CloudProvisioner for
               the Lambda Labs GPU cloud.

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

from ccai.provisioning.venues.lambdalabs.llapplystages import (
    LlApplyResult, LlApplyStages
)
from ccai.provisioning.venues.lambdalabs.lldestroystages import (
    LlDestroyStages
)
from ccai.provisioning.venues.lambdalabs.llerrors import (
    ConfirmationRequiredError, LlValidationError
)
from ccai.provisioning.venues.lambdalabs.llinventory import LlInventory
from ccai.provisioning.venues.lambdalabs.llplanbuilder import (
    LlPlanBuilder
)
from ccai.provisioning.venues.lambdalabs.llresolver import LlResolver
from ccai.provisioning.venues.lambdalabs.llsidecartag import LlSidecarTag
from ccai.provisioning.venues.lambdalabs.lambdalabsspec import (
    LambdalabsSpec
)

from ccai.credentials.lambdalabsapikeycredential import (
    LambdalabsApiKeyCredential
)


# Interconnect kinds Lambda Labs cannot realise as plain instances; they
# must instead resolve to a 1-Click Cluster offering for the GPU type.
_INFINIBAND_KINDS = frozenset({
    "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR",
})


class LambdalabsCloudProvisioner(CloudProvisioner):
    """
        Lambda-Labs-venue concrete :class:`CloudProvisioner`.

        Lambda Labs is a simple on-demand GPU venue — instances, SSH keys,
        attach-only file systems, and 1-Click Clusters.  It has no VPC,
        firewall, object storage, DNS, or load balancing.  This provisioner
        is honest about every gap: it warns on network/subnet/security-group
        resources and errors on object buckets, load balancers, and DNS
        records.

        The spec is a :class:`LambdalabsSpec` bundle of neutral resource
        objects.  Every method accepts ``aspects`` and propagates it to the
        interop client.
    """

    VENUE_NAME: str = "lambdalabs"

    def __init__(self, *, venue: CloudVenue,
                 credential: LambdalabsApiKeyCredential,
                 client: Any,
                 spec: Optional[LambdalabsSpec] = None,
                 resolver: Optional[LlResolver] = None,
                 vpn_control_plane: Optional[Any] = None,
                 output_root: str = ".output") -> None:
        """
            Construct a LambdalabsCloudProvisioner.

            :param venue: The :class:`CloudVenue`.
            :param credential: A :class:`LambdalabsApiKeyCredential`.
            :param client: The Lambda Labs interop client (a
                :class:`LambdalabsClient` or a test double).
            :param spec: Optional :class:`LambdalabsSpec`.
            :param resolver: Optional :class:`LlResolver`; defaults to a
                fresh resolver bound to the packaged catalog.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl;
                destroy uses this to de-register VPN devices.
            :param output_root: The output root directory for sidecar tag
                and inventory files.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: LambdalabsApiKeyCredential = credential
        self._client: Any = client
        if resolver is not None:
            self._resolver: LlResolver = resolver
        else:
            self._resolver = LlResolver()
        self._vpn_control_plane: Optional[Any] = vpn_control_plane
        self._output_root: str = output_root

        self._plan_builder = LlPlanBuilder(client=client,
                                           resolver=self._resolver)
        self._apply_stages = LlApplyStages(client=client,
                                           resolver=self._resolver)
        self._destroy_stages = LlDestroyStages(client=client)
        self._inventory = LlInventory(client=client,
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

    @classmethod
    def supports_preemption(cls) -> bool:
        """
            Lambda Labs offers interruptible capacity, so this venue can
            preempt instances.

            :returns: True.
        """
        rtnval = True
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the :class:`LambdalabsSpec` without any remote I/O.

            :param aspects: Aspects controlling validation behaviour.

            :returns: A :class:`ValidationResult` with ok=True on success.

            :raises: :class:`LlValidationError` when the spec contains
                resources Lambda Labs cannot realise.
        """
        if not isinstance(self._credential, LambdalabsApiKeyCredential):
            err_msg_lines = [
                "LambdalabsCloudProvisioner requires a "
                "LambdalabsApiKeyCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise LlValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        # Lambda Labs has no object storage / DNS / load balancing.
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("Lambda Labs has no object-storage service; "
                          "CloudObjectBucket cannot be realised."),
            })
        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("Lambda Labs has no load-balancing service; "
                          "CloudLoadBalancer cannot be realised."),
            })
        for record in spec.dns_records:
            errors.append({
                "resource": record.name,
                "error": ("Lambda Labs has no DNS service; CloudDnsRecord "
                          "cannot be realised."),
            })

        # Lambda Labs has no network model — warn and ignore.
        for network in spec.networks:
            warnings.append({
                "resource": network.name,
                "warning": ("Lambda Labs exposes no VPC/network model; "
                            "CloudNetwork is ignored."),
            })
        for subnet in spec.subnets:
            warnings.append({
                "resource": subnet.name,
                "warning": ("Lambda Labs exposes no subnet model; "
                            "CloudSubnet is ignored."),
            })
        for sg in spec.security_groups:
            warnings.append({
                "resource": sg.name,
                "warning": ("Lambda Labs exposes no firewall/security-group "
                            "model; CloudSecurityGroup is ignored."),
            })

        # Per-instance: region + instance-type / accelerator resolution.
        for inst in spec.instances:
            region = inst.subnet
            if region is None or len(region) == 0:
                errors.append({
                    "resource": inst.name,
                    "error": ("Lambda Labs needs a region; set the "
                              "instance 'subnet' field to a Lambda region."),
                })

            try:
                resolution = self._resolver.resolve_instance_type(
                    instance=inst
                )
            except LlValidationError as xcpt:
                errors.append({
                    "resource": inst.name,
                    "error": "Accelerator not on Lambda Labs: {}".format(
                        xcpt
                    ),
                })
                resolution = None

            if resolution is None:
                if inst.size is None or len(inst.size) == 0:
                    errors.append({
                        "resource": inst.name,
                        "error": ("Instance carries neither a resolvable "
                                  "accelerator nor a Lambda Labs size slug."),
                    })

            if inst.interconnect is not None:
                if inst.interconnect.kind in _INFINIBAND_KINDS:
                    if resolution is not None:
                        warnings.append({
                            "resource": inst.name,
                            "warning": ("InfiniBand interconnect resolves to "
                                        "a Lambda Labs 1-Click Cluster for "
                                        "{}.").format(
                                            resolution.instance_type_slug
                                        ),
                        })

        if len(errors) > 0:
            err_msg_lines = [
                "LambdalabsCloudProvisioner.validate found errors."
            ]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise LlValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

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

            Stages: ensure SSH keys → launch instances / 1-Click Clusters,
            rendering the launch ``user_data`` field from the M6 cloud-init
            renderer when an instance carries a ``vpn_join`` spec.

            :param aspects: Aspects controlling apply behaviour.

            :returns: A :class:`ProvisioningResult`.

            :raises: :class:`ConfirmationRequiredError` when the plan
                contains a DELETE / UPDATE-by-recreate action and
                ``aspects.confirm`` is false.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id

        # An UPDATE-by-recreate is destructive; gate it on confirm.
        plan = self._plan_builder.plan(spec=self._spec, run_id=run_id,
                                       aspects=aspects)
        confirm = self._aspect_attr(aspects=aspects, name="confirm",
                                    default=False)
        for action in plan.actions:
            if action.intent == "update" and confirm is not True:
                err_msg_lines = [
                    "Lambda Labs apply requires aspects.confirm=True for "
                    "an instance-type UPDATE-by-recreate."
                ]
                err_msg_lines.append("RESOURCE: {}".format(
                    action.resource_name
                ))
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfirmationRequiredError(err_msg)

        sidecar = LlSidecarTag(runid=run_id, output_root=self._output_root)
        result = LlApplyResult()

        self._apply_stages.ensure_ssh_keys(spec=self._spec, result=result,
                                           aspects=aspects)
        self._apply_stages.apply_instances(
            spec=self._spec, run_id=run_id, result=result,
            vpn_control_plane=self._vpn_control_plane, sidecar=sidecar,
            aspects=aspects,
        )

        self._last_vpn_records = result.vpn_records

        rtnval = ProvisioningResult(created=result.created,
                                    updated=[],
                                    skipped=result.skipped, errors=[])
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Terminate run-owned instances and de-register VPN devices.

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
            Enumerate run-owned Lambda Labs resources.

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
        rtnval = "lambdalabs-{}".format(self._venue.name)
        return rtnval
