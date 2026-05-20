"""
    .. module:: blockvolumemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI Block Volume manager for the Oracle Cloud venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.venues.oracle.ocisessionfactory import (
    OciSessionFactory
)
from automojo.provisioning.venues.oracle.ociidempotency import (
    belongs_to_run, matches_resource, resource_name_of
)
from automojo.provisioning.venues.oracle.ocitagging import (
    base_resource_tags, from_freeform, to_freeform
)


# OCI Block Volume minimum size is 50 GB.
_MIN_VOLUME_GB = 50


class BlockVolumeManager:
    """
        Manager for OCI Block Volumes.

        Block volumes are created in an availability domain and attached to a
        compute instance after creation.  Idempotent ``ensure`` is done by
        freeform-tag lookup.
    """

    KIND: str = "volume"

    def __init__(self, *, session_factory: OciSessionFactory) -> None:
        """
            Construct a BlockVolumeManager.

            :param session_factory: OciSessionFactory.
        """
        self._session_factory: OciSessionFactory = session_factory
        return

    def _block(self) -> Any:
        """
            Return the OCI BlockstorageClient.

            :returns: An ``oci`` BlockstorageClient.
        """
        rtnval = self._session_factory.client(service_name="blockstorage")
        return rtnval

    def _compute(self) -> Any:
        """
            Return the OCI ComputeClient (used for volume attachment).

            :returns: An ``oci`` ComputeClient.
        """
        rtnval = self._session_factory.client(service_name="compute")
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Any]:
        """
            Find an existing owned volume by run+name freeform tags.

            :param run_id: Run identifier.
            :param name: Neutral volume name.

            :returns: An OCI Volume model object or None.
        """
        client = self._block()
        compartment_id = self._session_factory.region_config.compartment_id
        response = client.list_volumes(compartment_id=compartment_id)
        for volume in response.data:
            if matches_resource(entity=volume, run_id=run_id,
                                resource_name=name):
                rtnval: Optional[Any] = volume
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, desired: CloudStorageVolume, run_id: str,
               default_tags: List[Dict[str, str]],
               attach_instance_id: Optional[str],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Block Volume.

            :param desired: Desired CloudStorageVolume.
            :param run_id: Run identifier.
            :param default_tags: Venue default tags.
            :param attach_instance_id: OCI instance OCID to attach to or None.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the volume.
        """
        import oci

        client = self._block()
        compartment_id = self._session_factory.region_config.compartment_id
        availability_domain = (
            self._session_factory.region_config.availability_domain
        )
        existing = self.find(run_id=run_id, name=desired.name)

        if existing is None:
            neutral_tags = base_resource_tags(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=list(desired.tags),
                defaults=default_tags,
            )
            size_gb = desired.size_gb
            if size_gb < _MIN_VOLUME_GB:
                size_gb = _MIN_VOLUME_GB
            details = oci.core.models.CreateVolumeDetails(
                compartment_id=compartment_id,
                availability_domain=availability_domain,
                size_in_gbs=size_gb,
                display_name="automojo-{}-{}".format(run_id, desired.name),
                freeform_tags=to_freeform(neutral_tags=neutral_tags),
            )
            created = client.create_volume(create_volume_details=details)
            existing = created.data

        volume_id = getattr(existing, "id", "")

        if attach_instance_id is not None and len(attach_instance_id) > 0:
            attach_details = oci.core.models.AttachParavirtualizedVolumeDetails(
                type="paravirtualized",
                instance_id=attach_instance_id,
                volume_id=volume_id,
            )
            try:
                self._compute().attach_volume(
                    attach_volume_details=attach_details
                )
            except Exception:
                pass

        attributes: Dict[str, Any] = {}
        attributes["volume_id"] = volume_id
        attributes["size_gb"] = getattr(existing, "size_in_gbs",
                                        desired.size_gb)
        attributes["availability_domain"] = getattr(
            existing, "availability_domain", availability_domain
        )

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=volume_id,
            attributes=attributes,
            tags=from_freeform(
                freeform_tags=getattr(existing, "freeform_tags", None)
            ),
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned Block Volume for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed volume OCIDs.
        """
        client = self._block()
        compartment_id = self._session_factory.region_config.compartment_id
        deleted: List[str] = []
        response = client.list_volumes(compartment_id=compartment_id)
        for volume in response.data:
            if not belongs_to_run(entity=volume, run_id=run_id):
                continue
            volume_id = getattr(volume, "id", "")
            try:
                client.delete_volume(volume_id=volume_id)
                deleted.append(volume_id)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return every owned Block Volume for the run.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        client = self._block()
        compartment_id = self._session_factory.region_config.compartment_id
        out: List[ProvisionedResource] = []
        response = client.list_volumes(compartment_id=compartment_id)
        for volume in response.data:
            if not belongs_to_run(entity=volume, run_id=run_id):
                continue
            name = resource_name_of(entity=volume)
            if name is None:
                continue
            attributes: Dict[str, Any] = {}
            attributes["volume_id"] = getattr(volume, "id", "")
            attributes["size_gb"] = getattr(volume, "size_in_gbs", 0)
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=getattr(volume, "id", ""),
                attributes=attributes,
                tags=from_freeform(
                    freeform_tags=getattr(volume, "freeform_tags", None)
                ),
            )
            out.append(entry)
        rtnval = out
        return rtnval
