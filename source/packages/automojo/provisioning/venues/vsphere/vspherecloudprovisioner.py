"""
    .. module:: vspherecloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VSphereCloudProvisioner — concrete CloudProvisioner for the
        VMware vSphere VM-hypervisor venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.credentials.vspherecredential import VSphereCredential
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
from automojo.provisioning.venues.vsphere.vsapplystages import VsApplyStages
from automojo.provisioning.venues.vsphere.vsdestroystages import (
    VsDestroyStages
)
from automojo.provisioning.venues.vsphere.vserrors import (
    ConfirmationRequiredError, VsValidationError
)
from automojo.provisioning.venues.vsphere.vsguestcustomrenderer import (
    VsGuestCustomRenderer
)
from automojo.provisioning.venues.vsphere.vsinventory import VsInventory
from automojo.provisioning.venues.vsphere.vsplanbuilder import VsPlanBuilder
from automojo.provisioning.venues.vsphere.vsphereops import VSphereOps
from automojo.provisioning.venues.vsphere.vspherespec import VSphereSpec
from automojo.provisioning.venues.vsphere.vspherevenueconfig import (
    VSphereVenueConfig
)
from automojo.provisioning.venues.vsphere.vsresolver import VsResolver


_UNSUPPORTED_FS_KINDS = frozenset({"LUSTRE", "WEKA", "VAST", "GPFS",
                                   "BEEGFS"})

_REJECTED_INTERCONNECT_TOPOLOGIES = frozenset({"INFINIBAND_HDR",
                                               "INFINIBAND_NDR",
                                               "INFINIBAND_XDR",
                                               "EFA", "OCI_RDMA",
                                               "RAIL_OPTIMIZED"})


class VSphereCloudProvisioner(CloudProvisioner):
    """
        VSphere-venue concrete :class:`CloudProvisioner` implementation.

        Maps the neutral resource model onto vSphere primitives through the
        ``automojo-interop-vsphere`` client (wrapped by :class:`VSphereOps`).
        Resources with no faithful vSphere realisation — object buckets,
        NSX-less load balancers, HPC interconnects, managed parallel
        filesystems — are rejected loudly at ``validate`` time.

        Every long-running vCenter operation is awaited through the task
        handle's ``wait(aspects=...)`` inside :class:`VSphereOps`, keeping the
        five-verb lifecycle synchronous with respect to ``Aspects``.
    """

    VENUE_NAME: str = "vsphere"

    def __init__(self, *, venue: CloudVenue,
                 credential: VSphereCredential,
                 config: VSphereVenueConfig,
                 spec: Optional[VSphereSpec] = None,
                 ops: Optional[VSphereOps] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a VSphereCloudProvisioner.

            :param venue: The CloudVenue this provisioner targets.
            :param credential: A VSphereCredential.
            :param config: The VSphereVenueConfig (placement + connection).
            :param spec: Optional VSphereSpec bundle of neutral resources.
            :param ops: Optional pre-built VSphereOps facade.  When omitted a
                        live facade is built from ``credential`` + ``config``.
                        Tests inject a mock-backed facade here.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl used
                                      by destroy to de-register VPN devices.

            :raises: VsValidationError
        """
        super().__init__(venue=venue, spec=spec)

        if not isinstance(credential, VSphereCredential):
            err_msg_lines = [
                "VSphereCloudProvisioner requires a VSphereCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise VsValidationError(err_msg)

        self._credential: VSphereCredential = credential
        self._config: VSphereVenueConfig = config
        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        if ops is not None:
            self._ops: VSphereOps = ops
        else:
            self._ops = VSphereOps.from_credential(
                host=config.host, credential=credential, port=config.port,
            )

        self._resolver: VsResolver = VsResolver(ops=self._ops,
                                                config=config)
        self._guest_renderer: VsGuestCustomRenderer = VsGuestCustomRenderer()
        self._plan_builder: VsPlanBuilder = VsPlanBuilder(ops=self._ops,
                                                          config=config)
        self._apply_stages: VsApplyStages = VsApplyStages(
            ops=self._ops, config=config, resolver=self._resolver,
            guest_renderer=self._guest_renderer,
        )
        self._destroy_stages: VsDestroyStages = VsDestroyStages(
            ops=self._ops,
        )
        self._inventory: VsInventory = VsInventory(ops=self._ops)

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Validate the VSphereSpec without any vCenter I/O.

            Rejects CloudObjectBucket (no native object storage),
            CloudLoadBalancer when NSX is absent, CloudInterconnect with a
            non-NONE kind, and managed parallel filesystems lacking an
            existing NFS-datastore id.

            :param aspects: ProvisioningAspects (unused; validate is offline).

            :returns: A ValidationResult with ok=True on success.
            :raises: VsValidationError
        """
        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        # CloudObjectBucket — no native vSphere object storage.
        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("vSphere has no native object-storage primitive; "
                          "CloudObjectBucket cannot be realised on this "
                          "venue."),
            })

        # CloudLoadBalancer — needs NSX.
        for lb in spec.load_balancers:
            if self._config.nsx_available is not True:
                errors.append({
                    "resource": lb.name,
                    "error": ("CloudLoadBalancer requires NSX-T; NSX is not "
                              "configured for this venue.  See "
                              "automojo-interop-nsx (PLAN M14)."),
                })

        # CloudInterconnect — vSphere has no HPC fabric.
        for instance in spec.instances:
            interconnect = instance.interconnect
            if interconnect is not None:
                kind = interconnect.kind
                topology = getattr(interconnect, "topology", "NONE")
                if kind != "NONE" or topology in _REJECTED_INTERCONNECT_TOPOLOGIES:
                    errors.append({
                        "resource": instance.name,
                        "error": ("vSphere does not expose an HPC "
                                  "interconnect; CloudInterconnect kind={} "
                                  "is unsupported.").format(kind),
                    })

        # Shared filesystems — managed parallel FS unsupported; NFS attach
        # only when existing_id is supplied.
        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                if sfs.existing_id is None or len(sfs.existing_id) == 0:
                    errors.append({
                        "resource": sfs.name,
                        "error": ("vSphere cannot provision a managed {} "
                                  "filesystem; supply existing_id to attach "
                                  "an NFS datastore instead.").format(
                                      sfs.kind
                                  ),
                    })

        # DNS records — documented out-of-band for vSphere.
        for record in spec.dns_records:
            errors.append({
                "resource": record.name,
                "error": ("vCenter has no DNS authority; CloudDnsRecord is "
                          "out-of-band for the vSphere venue and must be "
                          "removed from the spec."),
            })

        # Image resolvability — every instance size must map to hardware.
        for instance in spec.instances:
            try:
                self._resolver.size_to_hardware(size_hint=instance.size)
            except VsValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": str(xcpt).splitlines()[0],
                })

        if len(errors) > 0:
            err_msg_lines = ["VSphereCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise VsValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningPlan.
        """
        effective_aspects = self._effective_aspects(aspects=aspects)
        run_id = self._run_id(aspects=effective_aspects)
        rtnval = self._plan_builder.plan(
            spec=self._spec, run_id=run_id, aspects=effective_aspects,
        )
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: distributed port groups -> Content Library / template
            image resolution -> VM clone-or-create -> disk attach -> guest
            customisation -> power-on.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningResult.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        effective_aspects = self._effective_aspects(aspects=aspects)
        run_id = self._run_id(aspects=effective_aspects)
        self._last_run_id = run_id

        created: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []

        # Networking.
        subnet_state = self._apply_stages.apply_networking(
            spec=self._spec, run_id=run_id, aspects=effective_aspects,
            created=created, skipped=skipped,
        )

        # Key pair material — vSphere has no first-class keypair resource;
        # the public key is injected into guest customisation.
        keypair_map: Dict[str, str] = {}
        for keypair in self._spec.keypairs:
            keypair_map[keypair.name] = keypair.public_key_material

        # VPN auth-key (minted by the control plane when present).
        authkey: Optional[str] = None
        if self._vpn_control_plane is not None:
            authkey = getattr(self._vpn_control_plane, "minted_authkey", None)

        # Compute.
        instance_state = self._apply_stages.apply_vms(
            spec=self._spec, run_id=run_id, aspects=effective_aspects,
            subnet_state=subnet_state, keypair_map=keypair_map,
            authkey=authkey, created=created, skipped=skipped,
            vpn_records=vpn_records,
        )

        # Disks.
        self._apply_stages.apply_disks(
            spec=self._spec, run_id=run_id, aspects=effective_aspects,
            instance_state=instance_state, created=created, skipped=skipped,
        )

        self._last_vpn_records = vpn_records

        rtnval = ProvisioningResult(created=created, updated=[],
                                    skipped=skipped, errors=[])
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Tear down every owned resource in reverse dependency order.

            :param aspects: ProvisioningAspects.
        """
        effective_aspects = self._effective_aspects(aspects=aspects)
        run_id = self._run_id(aspects=effective_aspects)

        self._destroy_stages.destroy(
            spec=self._spec, run_id=run_id, aspects=effective_aspects,
            vpn_control_plane=self._vpn_control_plane,
            vpn_records=self._last_vpn_records,
        )
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any = None) -> List[ProvisionedResource]:
        """
            Enumerate VMs and port groups owned by the run.

            :param aspects: ProvisioningAspects.

            :returns: A list of ProvisionedResource entries.
        """
        effective_aspects = self._effective_aspects(aspects=aspects)
        run_id = self._run_id(aspects=effective_aspects)
        rtnval = self._inventory.list_run(
            spec=self._spec, run_id=run_id, aspects=effective_aspects,
        )
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance.

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

    @staticmethod
    def _effective_aspects(*, aspects: Any) -> Any:
        """
            Return the supplied aspects or a default ProvisioningAspects.

            :param aspects: Caller-supplied aspects or None.

            :returns: An aspects object.
        """
        if aspects is not None:
            rtnval = aspects
            return rtnval

        from automojo.provisioning.aspects.provisioningaspects import (
            ProvisioningAspects
        )
        rtnval = ProvisioningAspects()
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
        rtnval = "vsphere-{}".format(self._venue.name)
        return rtnval
