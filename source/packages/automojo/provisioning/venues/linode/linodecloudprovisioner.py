"""
    .. module:: linodecloudprovisioner
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LinodeCloudProvisioner — concrete CloudProvisioner for the
               Linode (Akamai Connected Cloud) venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.credentials.linodeapitokencredential import (
    LinodeApiTokenCredential
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
from automojo.provisioning.venues.linode.linodeapplystages import (
    LinodeApplyStages, LinodeApplyResult
)
from automojo.provisioning.venues.linode.linodeclientfactory import (
    LinodeClientFactory
)
from automojo.provisioning.venues.linode.linodedestroystages import (
    LinodeDestroyStages
)
from automojo.provisioning.venues.linode.linodeerrors import (
    LinodeValidationError
)
from automojo.provisioning.venues.linode.linodeinventory import LinodeInventory
from automojo.provisioning.venues.linode.linodeplanbuilder import (
    LinodePlanBuilder
)
from automojo.provisioning.venues.linode.linodereader import LinodeReader
from automojo.provisioning.venues.linode.linoderegionconfig import (
    LinodeRegionConfig
)
from automojo.provisioning.venues.linode.linoderesolver import LinodeResolver
from automojo.provisioning.venues.linode.linodespec import LinodeSpec
from automojo.provisioning.venues.linode.linodetagtranslator import (
    LinodeTagTranslator
)
from automojo.provisioning.venues.linode.linodeuserdatarenderer import (
    LinodeUserDataRenderer
)


# HPC interconnect kinds Linode does not offer.  Only NONE is accepted.
_REJECTED_INTERCONNECTS = frozenset({
    "INFINIBAND", "INFINIBAND_HDR", "INFINIBAND_NDR", "INFINIBAND_XDR",
    "EFA", "OCI_RDMA", "NVSWITCH", "NVLINK",
})

# Shared-FS kinds with no Linode-native equivalent.
_REJECTED_FS_KINDS = frozenset({
    "LUSTRE", "WEKA", "VAST", "GPFS", "EFS", "FILESTORE", "BEEGFS",
})


class LinodeCloudProvisioner(CloudProvisioner):
    """
        Linode-venue concrete :class:`CloudProvisioner` implementation.

        Realises the neutral resource model on Linode via the ``linode_api4``
        SDK used directly by this venue (no separate interop package).  The
        five-verb lifecycle composes the resolver, tag translator, reader,
        plan builder, apply / destroy stages, and inventory enumerator.
    """

    VENUE_NAME: str = "linode"

    def __init__(self, *, venue: CloudVenue,
                 credential: LinodeApiTokenCredential,
                 region_config: LinodeRegionConfig,
                 spec: Optional[LinodeSpec] = None,
                 vpn_control_plane: Optional[Any] = None,
                 client: Optional[Any] = None) -> None:
        """
            Construct a LinodeCloudProvisioner.

            :param venue: The CloudVenue.
            :param credential: A LinodeApiTokenCredential.
            :param region_config: A LinodeRegionConfig.
            :param spec: Optional LinodeSpec.
            :param vpn_control_plane: Optional IVPNControlPlane impl; destroy
                                      uses this to de-register VPN devices.
            :param client: Optional pre-built (or mock) ``linode_api4``
                           client; injected for tests.
        """
        super().__init__(venue=venue, spec=spec)
        self._credential: LinodeApiTokenCredential = credential
        self._region_config: LinodeRegionConfig = region_config
        self._vpn_control_plane: Optional[Any] = vpn_control_plane

        self._client_factory: LinodeClientFactory = LinodeClientFactory(
            credential=credential
        )
        if client is not None:
            self._client_factory.set_client(client=client)

        self._resolver: LinodeResolver = LinodeResolver()
        self._translator: LinodeTagTranslator = LinodeTagTranslator()
        self._user_data_renderer: LinodeUserDataRenderer = (
            LinodeUserDataRenderer()
        )

        self._last_run_id: Optional[str] = None
        self._last_vpn_records: List[Dict[str, Any]] = []
        return

    # ------------------------------------------------------------------
    # Lifecycle: validate
    # ------------------------------------------------------------------

    def validate(self, *, aspects: Any) -> ValidationResult:
        """
            Validate the LinodeSpec without any SDK calls.

            :param aspects: Aspects.

            :returns: A ValidationResult with ok=True on success.
            :raises: LinodeValidationError
        """
        if not isinstance(self._credential, LinodeApiTokenCredential):
            err_msg_lines = [
                "LinodeCloudProvisioner requires a LinodeApiTokenCredential."
            ]
            err_msg_lines.append("ACTUAL: {}".format(
                type(self._credential).__name__
            ))
            err_msg = os.linesep.join(err_msg_lines)
            raise LinodeValidationError(err_msg)

        spec = self._spec
        if spec is None:
            rtnval = ValidationResult(ok=True)
            return rtnval

        errors: List[Dict[str, Any]] = []

        for net in spec.networks:
            if not self._resolver.is_known_region(region=net.region):
                errors.append({
                    "resource": net.name,
                    "error": ("Network region {!r} does not resolve to a "
                              "Linode region slug.").format(net.region),
                })

        for sfs in spec.shared_filesystems:
            if sfs.kind in _REJECTED_FS_KINDS:
                errors.append({
                    "resource": sfs.name,
                    "error": ("Linode has no shared-FS service of the "
                              "WEKA/Lustre class; kind={} is "
                              "unsupported.").format(sfs.kind),
                })

        for instance in spec.instances:
            if instance.interconnect is not None:
                if instance.interconnect.kind in _REJECTED_INTERCONNECTS:
                    errors.append({
                        "resource": instance.name,
                        "error": ("Linode offers no HPC interconnect; "
                                  "interconnect kind {} is "
                                  "unsupported.").format(
                                      instance.interconnect.kind
                                  ),
                    })

            try:
                self._resolver.image_to_id(
                    family=instance.image.family,
                    version=instance.image.version,
                    architecture=instance.image.architecture,
                )
            except LinodeValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": "Image not resolvable: {}".format(xcpt),
                })

            accelerator_models = self._accelerator_models(instance=instance)
            try:
                self._resolver.size_to_type(
                    size_hint=instance.size,
                    accelerators=accelerator_models,
                )
            except LinodeValidationError as xcpt:
                errors.append({
                    "resource": instance.name,
                    "error": "Size/accelerator not resolvable: {}".format(
                        xcpt
                    ),
                })

        # Tag validity (drives the round-trip / 50-char checks).
        for collection in (spec.networks, spec.security_groups,
                           spec.instances, spec.volumes):
            for entry in collection:
                tags = getattr(entry, "tags", None)
                if tags is None:
                    continue
                try:
                    self._translator.to_linode(neutral_tags=tags)
                except LinodeValidationError as xcpt:
                    errors.append({
                        "resource": getattr(entry, "name", "<tags>"),
                        "error": "Invalid tags: {}".format(xcpt),
                    })

        if len(errors) > 0:
            err_msg_lines = ["LinodeCloudProvisioner.validate found errors."]
            for entry in errors:
                err_msg_lines.append("    {}: {}".format(
                    entry["resource"], entry["error"]
                ))
            err_msg = os.linesep.join(err_msg_lines)
            raise LinodeValidationError(err_msg)

        rtnval = ValidationResult(ok=True)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: plan
    # ------------------------------------------------------------------

    def plan(self, *, aspects: Any) -> ProvisioningPlan:
        """
            Compute a CREATE/SKIP/UPDATE plan via tag-filtered reads.

            :param aspects: Aspects.

            :returns: A ProvisioningPlan.
        """
        run_id = self._run_id(aspects=aspects)
        reader = self._reader(run_id=run_id)
        builder = LinodePlanBuilder(reader=reader, resolver=self._resolver)
        rtnval = builder.plan(spec=self._spec, run_id=run_id)
        return rtnval

    # ------------------------------------------------------------------
    # Lifecycle: apply
    # ------------------------------------------------------------------

    def apply(self, *, aspects: Any) -> ProvisioningResult:
        """
            Apply the spec idempotently.

            Stages: VPC → Firewall → SSH key → Instance → Volume → Object
            Storage → DNS.

            :param aspects: Aspects.

            :returns: A ProvisioningResult.
        """
        if self._spec is None:
            rtnval = ProvisioningResult()
            return rtnval

        run_id = self._run_id(aspects=aspects)
        self._last_run_id = run_id

        client = self._client_factory.client()
        reader = LinodeReader(client=client, run_id=run_id,
                              translator=self._translator)
        stages = LinodeApplyStages(
            client=client, reader=reader, resolver=self._resolver,
            translator=self._translator,
            region_config=self._region_config,
            user_data_renderer=self._user_data_renderer,
            vpn_control_plane=self._vpn_control_plane,
        )

        result = LinodeApplyResult()
        state = stages.apply_network_and_firewall(
            spec=self._spec, run_id=run_id, result=result, aspects=aspects,
        )
        stages.apply_instances_and_volumes(
            spec=self._spec, run_id=run_id, state=state, result=result,
            aspects=aspects,
        )
        stages.apply_object_storage_and_dns(
            spec=self._spec, run_id=run_id, result=result, aspects=aspects,
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
            Destroy every owned resource in reverse dependency order.

            :param aspects: Aspects.
        """
        run_id = self._run_id(aspects=aspects)
        client = self._client_factory.client()
        reader = LinodeReader(client=client, run_id=run_id,
                              translator=self._translator)
        stages = LinodeDestroyStages(
            client=client, reader=reader,
            vpn_control_plane=self._vpn_control_plane,
        )
        stages.destroy(spec=self._spec, run_id=run_id,
                       vpn_records=self._last_vpn_records, aspects=aspects)
        return

    # ------------------------------------------------------------------
    # Lifecycle: inventory
    # ------------------------------------------------------------------

    def inventory(self, *, aspects: Any) -> List[ProvisionedResource]:
        """
            Enumerate run-id-tagged resources.

            :param aspects: Aspects.

            :returns: A list of ProvisionedResource entries.
        """
        run_id = self._run_id(aspects=aspects)
        client = self._client_factory.client()
        reader = LinodeReader(client=client, run_id=run_id,
                              translator=self._translator)
        enumerator = LinodeInventory(client=client, reader=reader,
                                     translator=self._translator)
        rtnval = enumerator.list_run(aspects=aspects)
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

    def _reader(self, *, run_id: str) -> LinodeReader:
        """
            Build a LinodeReader bound to the client and run id.

            :param run_id: The run identifier.

            :returns: A LinodeReader.
        """
        client = self._client_factory.client()
        rtnval = LinodeReader(client=client, run_id=run_id,
                              translator=self._translator)
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
        rtnval = "linode-{}".format(self._venue.name)
        return rtnval

    @staticmethod
    def _accelerator_models(*, instance: Any) -> List[str]:
        """
            Extract neutral accelerator model strings from an instance.

            :param instance: A CloudInstance.

            :returns: A list of model strings (possibly empty).
        """
        accelerators = instance.accelerators if instance.accelerators is not None else []
        out: List[str] = []
        for entry in accelerators:
            out.append(entry.model)
        rtnval = out
        return rtnval
