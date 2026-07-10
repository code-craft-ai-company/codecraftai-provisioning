"""
    .. module:: diskmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP Persistent Disk manager for the Google venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.storageclass import StorageClass
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.google.gcpoperations import (
    labels_of, resource_or_none, wait_for_operation
)
from ccai.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_COMPUTE
)
from ccai.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from ccai.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, RESOURCE_NAME_LABEL_KEY
)


# Neutral StorageClass → GCP Persistent Disk type.
_DISK_TYPE_TABLE: Dict[StorageClass, str] = {
    StorageClass.STANDARD: "pd-ssd",
    StorageClass.BALANCED: "pd-balanced",
    StorageClass.PERFORMANCE: "pd-ssd",
    StorageClass.ARCHIVE: "pd-standard",
}


def resolve_disk_type(*, storage_class: StorageClass) -> str:
    """
        Resolve a neutral StorageClass to a GCP Persistent Disk type.

        :param storage_class: Neutral StorageClass member.

        :returns: A GCP Persistent Disk type string.
    """
    rtnval = _DISK_TYPE_TABLE.get(storage_class, "pd-balanced")
    return rtnval


class DiskManager:
    """
        Manager for GCP Persistent Disks (``compute.disks``).

        Disks are zone-scoped resources.  ``type`` is mapped from the neutral
        hint via :func:`resolve_disk_type`.
    """

    KIND: str = "volume"

    def __init__(self, *, session_factory: GcpSessionFactory) -> None:
        """
            Construct a DiskManager.

            :param session_factory: GcpSessionFactory.
        """
        self._session_factory: GcpSessionFactory = session_factory
        return

    def _client(self) -> Any:
        """
            Return the compute ``disks`` sub-client.

            :returns: The disks sub-client.
        """
        compute = self._session_factory.client(service_name=SERVICE_COMPUTE)
        rtnval = compute["disks"]
        return rtnval

    def _gcp_name(self, *, run_id: str, name: str) -> str:
        """
            Build the GCP-side disk name.

            :param run_id: Run identifier.
            :param name: Neutral volume name.

            :returns: A GCP-conformant disk name.
        """
        rtnval = "codecraftai-{}-{}".format(run_id, name).lower()
        return rtnval

    def find(self, *, run_id: str, name: str,
             zone: str) -> Optional[Any]:
        """
            Find an existing owned Persistent Disk by run+name labels.

            :param run_id: Run identifier.
            :param name: Neutral volume name.
            :param zone: Zone the disk lives in.

            :returns: The disk resource, or None.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=name)
        existing = resource_or_none(fetch=client.get, project=project,
                                    zone=zone, disk=gcp_name)
        if existing is None:
            rtnval: Optional[Any] = None
            return rtnval

        if not belongs_to_run(labels=labels_of(resource=existing),
                              run_id=run_id):
            rtnval = None
            return rtnval

        rtnval = existing
        return rtnval

    def ensure(self, *, desired: CloudStorageVolume, run_id: str, zone: str,
               default_tags: List[Dict[str, str]],
               aspects: Any) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Persistent Disk.

            :param desired: Desired CloudStorageVolume.
            :param run_id: Run identifier.
            :param zone: Zone to create the disk in.
            :param default_tags: Venue default tags.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the disk.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=desired.name)

        existing = self.find(run_id=run_id, name=desired.name, zone=zone)
        if existing is None:
            labels = base_resource_labels(
                run_id=run_id, resource_name=desired.name,
                resource_kind=self.KIND, extra=dict(desired.tags),
                defaults=default_tags,
            )
            disk_type = resolve_disk_type(storage_class=desired.storage_class)
            body: Dict[str, Any] = {
                "name": gcp_name,
                "size_gb": desired.size_gb,
                "type": "zones/{}/diskTypes/{}".format(zone, disk_type),
                "labels": labels,
            }
            operation = client.insert(project=project, zone=zone,
                                      disk_resource=body)
            wait_for_operation(operation=operation)
            existing = client.get(project=project, zone=zone, disk=gcp_name)

        disk_id = str(existing.id) if existing.id != 0 else gcp_name
        size_gb = existing.size_gb if existing.size_gb != 0 else desired.size_gb

        attributes: Dict[str, Any] = {}
        attributes["disk_id"] = disk_id
        attributes["gcp_name"] = gcp_name
        attributes["zone"] = zone
        attributes["size_gb"] = size_gb
        attributes["disk_type"] = resolve_disk_type(
            storage_class=desired.storage_class
        )

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcp_name,
            attributes=attributes,
            tags=from_labels(labels=labels_of(resource=existing)),
        )
        return rtnval

    def destroy(self, *, run_id: str, zone: str,
                aspects: Any) -> List[str]:
        """
            Destroy every owned Persistent Disk in the zone for the run.

            :param run_id: Run identifier.
            :param zone: Zone to scan.
            :param aspects: Aspects.

            :returns: List of destroyed disk names.
        """
        client = self._client()
        project = self._session_factory.project
        deleted: List[str] = []
        for entry in self.list_raw(run_id=run_id, zone=zone):
            gcp_name = entry.name
            if len(gcp_name) == 0:
                continue
            try:
                client.delete(project=project, zone=zone, disk=gcp_name)
                deleted.append(gcp_name)
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_raw(self, *, run_id: str,
                 zone: str) -> List[Any]:
        """
            Return raw owned Persistent Disk resources for the run.

            :param run_id: Run identifier.
            :param zone: Zone to scan.

            :returns: List of disk resources.
        """
        client = self._client()
        project = self._session_factory.project
        out: List[Any] = []
        for entry in client.list(project=project, zone=zone):
            if belongs_to_run(labels=labels_of(resource=entry),
                              run_id=run_id):
                out.append(entry)
        rtnval = out
        return rtnval

    def list_owned(self, *, run_id: str,
                   zone: str) -> List[ProvisionedResource]:
        """
            Return all owned disks for the run as ProvisionedResources.

            :param run_id: Run identifier.
            :param zone: Zone to scan.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for entry in self.list_raw(run_id=run_id, zone=zone):
            labels = labels_of(resource=entry)
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            entry_id = str(entry.id) if entry.id != 0 else entry.name
            attributes: Dict[str, Any] = {}
            attributes["disk_id"] = entry_id
            attributes["gcp_name"] = entry.name
            attributes["size_gb"] = entry.size_gb
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.name,
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
