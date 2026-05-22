"""
    .. module:: hypervcloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HypervCloudProvisioner — concrete CloudProvisioner for the
        Microsoft Hyper-V venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.interop.hyperv.aspectshyperv import DEFAULT_HYPERV_ASPECTS
from automojo.interop.hyperv.hypervclient import HypervClient

from automojo.provisioning.model.cloud.cloudprovisioner import CloudProvisioner
from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.model.cloud.provisioningplan import ProvisioningPlan
from automojo.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from automojo.provisioning.model.cloud.validationresult import ValidationResult

from automojo.provisioning.venues.hyperv.hvapplystages import HvApplyStages
from automojo.provisioning.venues.hyperv.hvcloudinitrenderer import (
    HvCloudInitRenderer
)
from automojo.provisioning.venues.hyperv.hvdestroystages import (
    HvDestroyStages
)
from automojo.provisioning.venues.hyperv.hverrors import (
    ConfirmationRequiredError, HvValidationError
)
from automojo.provisioning.venues.hyperv.hvhostconfig import HvHostConfig
from automojo.provisioning.venues.hyperv.hvinventory import HvInventory
from automojo.provisioning.venues.hyperv.hvnotestranslator import (
    HvNotesTranslator
)
from automojo.provisioning.venues.hyperv.hvplanbuilder import HvPlanBuilder
from automojo.provisioning.venues.hyperv.hvresolver import HvResolver
from automojo.provisioning.venues.hyperv.hypervspec import HypervSpec


# Shared-FS kinds the Hyper-V venue does not realise.  VENUE_NATIVE means
# an SMB share mounted attach-only inside the guest.
_UNSUPPORTED_FS_KINDS = frozenset({
    "WEKA", "VAST", "GPFS", "BEEGFS", "EFS", "FILESTORE", "LUSTRE"
})

# Interconnect kinds that cannot be realised on Hyper-V at all.
_UNSUPPORTED_INTERCONNECT = frozenset({
    "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR",
    "EFA", "GPUDIRECT_RDMA",
})


class HypervCloudProvisioner(CloudProvisioner):
    """
        Hyper-V-venue concrete :class:`CloudProvisioner` implementation.

        Microsoft Hyper-V offers no REST API; the venue drives the
        ``Hyper-V`` PowerShell module through the :class:`HypervClient`
        interop client.  The neutral resource model maps onto Hyper-V
        primitives as: ``CloudNetwork`` -> VMSwitch, ``CloudInstance`` -> VM
        (``New-VM`` plus a differencing boot VHDX), ``CloudStorageVolume``
        -> VHDX, ``CloudKeyPair`` -> cloud-init ssh keys, and
        ``VPNJoinSpec`` -> cloud-init delivered via an attached NoCloud ISO
        (Linux) or a ``SetupComplete.cmd`` unattend script (Windows).

        Hyper-V has no native object storage, load balancer, HPC
        interconnect or DNS surface; the corresponding neutral resources are
        rejected at ``validate`` time.  Tags and run-id ownership are
        encoded as a JSON envelope in the VM ``Notes`` field.
    """

    VENUE_NAME: str = "hyperv"

    def __init__(self, *, venue: CloudVenue, client: HypervClient,
                 host_config: HvHostConfig,
                 spec: Optional[HypervSpec] = None,
                 vpn_control_plane: Optional[Any] = None) -> None:
        """
            Construct a HypervCloudProvisioner.

            :param venue: The CloudVenue this provisioner targets.
            :param client: The :class:`HypervClient` interop client.
            :param host_config: The HvHostConfig describing the host paths
                and the optional External-switch physical adapter.
            :param spec: Optional HypervSpec resource bundle.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl used
                by destroy to de-register VPN devices and by apply to mint
                auth keys.
        """
        super().__init__(venue=venue, spec=spec)

        self._client: HypervClient = client
        self._host_config: HvHostConfig = host_config
        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        self._resolver: HvResolver = HvResolver(
            image_root=host_config.image_root)
        self._notes: HvNotesTranslator = HvNotesTranslator()
        self._cloud_init: HvCloudInitRenderer = HvCloudInitRenderer()

        self._plan_builder: HvPlanBuilder = HvPlanBuilder(
            client=client, host_config=host_config, resolver=self._resolver,
            notes=self._notes)
        self._apply_stages: HvApplyStages = HvApplyStages(
            client=client, host_config=host_config, resolver=self._resolver,
            notes=self._notes, cloud_init=self._cloud_init)
        self._destroy_stages: HvDestroyStages = HvDestroyStages(
            client=client, host_config=host_config, resolver=self._resolver,
            notes=self._notes)
        self._inventory: HvInventory = HvInventory(client=client,
                                                   notes=self._notes)

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any = None) -> ValidationResult:
        """
            Validate the HypervSpec without any remote I/O.

            :param aspects: ProvisioningAspects (or compatible).

            :returns: A ValidationResult with ok=True on success.

            :raises: HvValidationError on any rejection.
        """
        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []

        for bucket in spec.buckets:
            errors.append({
                "resource": bucket.name,
                "error": ("Hyper-V has no native object storage; "
                          "CloudObjectBucket is unsupported."),
            })

        for lb in spec.load_balancers:
            errors.append({
                "resource": lb.name,
                "error": ("Hyper-V exposes no load balancer surface; "
                          "CloudLoadBalancer is unsupported."),
            })

        for dns in spec.dns_records:
            warnings.append({
                "resource": dns.name,
                "warning": ("Hyper-V has no DNS surface; CloudDnsRecord "
                            "must be realised externally."),
            })

        for sg in spec.security_groups:
            warnings.append({
                "resource": sg.name,
                "warning": ("Hyper-V has no native security-group surface; "
                            "CloudSecurityGroup is recorded in VM.Notes "
                            "only."),
            })

        for sfs in spec.shared_filesystems:
            if sfs.kind in _UNSUPPORTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Hyper-V realises shared-FS only as an "
                              "attach-only SMB share; substitute "
                              "kind=VENUE_NATIVE for {}.").format(sfs.kind),
                })
            elif sfs.kind == "VENUE_NATIVE":
                if sfs.existing_id is None or len(sfs.existing_id) == 0:
                    errors.append({
                        "resource": sfs.name,
                        "error": ("Hyper-V shared-FS supports attach-only; "
                                  "set existing_id to an SMB share path."),
                    })

        for inst in spec.instances:
            self._validate_instance(instance=inst, errors=errors)

        if len(errors) > 0:
            err_msg_lines = ["HypervCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]))
            err_msg = os.linesep.join(err_msg_lines)
            raise HvValidationError(err_msg)

        rtnval = ValidationResult(ok=True, warnings=warnings)
        return rtnval

    def _validate_instance(self, *, instance: Any,
                           errors: List[Dict[str, Any]]) -> None:
        """
            Validate a single instance's image, size and interconnect.

            :param instance: The neutral CloudInstance.
            :param errors: The accumulating error list.

            :returns: ``None``.
        """
        try:
            self._resolver.image_to_parent_vhd(
                family=instance.image.family,
                version=instance.image.version,
                arch=instance.image.architecture)
        except HvValidationError as xcpt:
            errors.append({
                "resource": instance.name,
                "error": "Image not resolvable on Hyper-V: {}".format(xcpt),
            })

        try:
            self._resolver.size_to_hardware(size_hint=instance.size)
        except HvValidationError as xcpt:
            errors.append({
                "resource": instance.name,
                "error": "Size not resolvable on Hyper-V: {}".format(xcpt),
            })

        interconnect = instance.interconnect
        if interconnect is not None:
            if interconnect.kind in _UNSUPPORTED_INTERCONNECT:
                errors.append({
                    "resource": instance.name,
                    "error": ("Hyper-V cannot realise the requested HPC "
                              "interconnect {!r}.").format(interconnect.kind),
                })
        return

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any = None) -> ProvisioningPlan:
        """
            Compute a CREATE / SKIP / UPDATE plan with read-only describes.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        runner = self._runner_aspects(aspects=aspects)
        rtnval = self._plan_builder.plan(spec=self._spec, run_id=run_id,
                                         aspects=runner)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any = None) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: VMSwitch ensure -> parent VHD verification ->
            differencing boot VHDX -> ``New-VM`` -> processor / memory
            sizing -> data VHDX attach -> network adapter -> ``Set-VM``
            notes -> cloud-init ISO mount -> ``Start-VM``.

            :param aspects: ProvisioningAspects.

            :returns: A ProvisioningResult.

            :raises: ConfirmationRequiredError when a DELETE is planned
                without ``aspects.confirm=True``.
        """
        spec = self._spec
        if spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        runner = self._runner_aspects(aspects=aspects)
        self._last_run_id = run_id

        plan = self._plan_builder.plan(spec=spec, run_id=run_id,
                                       aspects=runner)
        confirm = self._aspect_attr(aspects=aspects, name="confirm",
                                    default=False)
        for action in plan.actions:
            if action.intent == PlannedActionIntent.DELETE.value:
                if confirm is not True:
                    err_msg_lines = [
                        "HypervCloudProvisioner.apply has a planned DELETE."
                    ]
                    err_msg_lines.append(
                        "    {}: {}".format(action.resource_kind,
                                            action.resource_name))
                    err_msg_lines.append(
                        "Re-run with aspects.confirm=True to proceed.")
                    err_msg = os.linesep.join(err_msg_lines)
                    raise ConfirmationRequiredError(err_msg)

            update_instance = (
                action.intent == PlannedActionIntent.UPDATE.value
                and action.resource_kind == "instance")
            if update_instance is True and confirm is not True:
                err_msg_lines = [
                    "HypervCloudProvisioner.apply has a planned in-place "
                    "VM resize (UPDATE)."
                ]
                err_msg_lines.append(
                    "    {}: {}".format(action.resource_kind,
                                        action.resource_name))
                err_msg_lines.append(
                    "Set-VMProcessor / Set-VMMemory require the VM to be "
                    "stopped; re-run with aspects.confirm=True to proceed.")
                err_msg = os.linesep.join(err_msg_lines)
                raise ConfirmationRequiredError(err_msg)

        created: List[ProvisionedResource] = []
        updated: List[ProvisionedResource] = []
        skipped: List[str] = []
        vpn_records: List[Dict[str, Any]] = []
        vpn_authkeys = self._mint_authkeys(spec=spec, aspects=aspects)

        switch_state = self._apply_stages.apply_switches(
            spec=spec, run_id=run_id, created=created, skipped=skipped,
            aspects=runner)
        self._apply_stages.apply_vms(
            spec=spec, run_id=run_id, switch_state=switch_state,
            created=created, updated=updated, skipped=skipped,
            vpn_records=vpn_records, vpn_authkeys=vpn_authkeys,
            aspects=runner)

        self._last_vpn_records = vpn_records

        rtnval = ProvisioningResult(created=created, updated=updated,
                                    skipped=skipped, errors=[])
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: destroy
    # ------------------------------------------------------------------

    def _destroy_impl(self, *, aspects: Any) -> None:
        """
            Destroy every run-id-owned resource in reverse apply order.

            :param aspects: ProvisioningAspects (confirm already gated).

            :returns: ``None``.
        """
        run_id = self._run_id(aspects=aspects)
        runner = self._runner_aspects(aspects=aspects)
        self._destroy_stages.destroy(
            spec=self._spec, run_id=run_id,
            vpn_records=self._last_vpn_records,
            vpn_control_plane=self._vpn_control_plane, aspects=runner)
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any = None) -> List[ProvisionedResource]:
        """
            Enumerate run-id-owned VMs for the run.

            :param aspects: ProvisioningAspects.

            :returns: A list of ProvisionedResource entries.
        """
        run_id = self._run_id(aspects=aspects)
        runner = self._runner_aspects(aspects=aspects)
        rtnval = self._inventory.list_run(run_id=run_id, aspects=runner)
        return rtnval

    def persist_inventory(self, *, aspects: Any = None,
                          output_root: str = ".output") -> str:
        """
            Write the run inventory to a JSON file under the output root.

            :param aspects: ProvisioningAspects.
            :param output_root: The base output directory.

            :returns: The path of the written inventory file.
        """
        run_id = self._run_id(aspects=aspects)
        runner = self._runner_aspects(aspects=aspects)
        rtnval = self._inventory.persist(run_id=run_id, aspects=runner,
                                         output_root=output_root)
        return rtnval

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def record_vpn_device(self, *, instance_name: str,
                          device_id: str) -> None:
        """
            Record the VPN device id minted for an instance post-apply.

            :param instance_name: Neutral instance name.
            :param device_id: Provider-assigned device id.

            :returns: ``None``.
        """
        for record in self._last_vpn_records:
            if record.get("instance_name", "") == instance_name:
                record["vpn_device_id"] = device_id
                return
        self._last_vpn_records.append({"instance_name": instance_name,
                                       "vpn_device_id": device_id})
        return

    @property
    def last_vpn_records(self) -> List[Dict[str, Any]]:
        """
            Return the recorded VPN device records from the last apply.

            :returns: A defensive copy of the records.
        """
        rtnval = [dict(entry) for entry in self._last_vpn_records]
        return rtnval

    def _mint_authkeys(self, *, spec: Any,
                       aspects: Any) -> Dict[str, str]:
        """
            Mint VPN auth keys for every VPN-joined instance.

            :param spec: The HypervSpec.
            :param aspects: ProvisioningAspects.

            :returns: A map of instance name -> minted auth key.
        """
        rtnval: Dict[str, str] = {}
        if self._vpn_control_plane is None:
            return rtnval

        for inst in spec.instances:
            if inst.vpn_join is None:
                continue
            mint = getattr(self._vpn_control_plane, "mint_authkey", None)
            if mint is None:
                rtnval[inst.name] = getattr(self._vpn_control_plane,
                                            "minted_authkey", "")
            else:
                rtnval[inst.name] = mint(spec=inst.vpn_join,
                                         instance_name=inst.name,
                                         aspects=aspects)
        return rtnval

    def _runner_aspects(self, *, aspects: Any) -> Any:
        """
            Resolve the AspectsRunner passed to interop client calls.

            :param aspects: ProvisioningAspects.

            :returns: An AspectsRunner instance.
        """
        candidate = self._aspect_attr(aspects=aspects, name="runner_aspects",
                                      default=None)
        if candidate is not None:
            rtnval = candidate
            return rtnval
        rtnval = DEFAULT_HYPERV_ASPECTS
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
        rtnval = "hyperv-{}".format(self._venue.name)
        return rtnval
