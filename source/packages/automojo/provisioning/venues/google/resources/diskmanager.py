"""
    .. module:: diskmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: GCP Persistent Disk manager for the Google venue.

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
from automojo.provisioning.venues.google.gcpsessionfactory import (
    GcpSessionFactory, SERVICE_COMPUTE
)
from automojo.provisioning.venues.google.gcpidempotency import (
    belongs_to_run
)
from automojo.provisioning.venues.google.gcptagging import (
    base_resource_labels, from_labels, RESOURCE_NAME_LABEL_KEY
)


# Neutral volume type hint → GCP Persistent Disk type.
_DISK_TYPE_TABLE: Dict[str, str] = {
    "ssd": "pd-ssd",
    "nvme": "pd-ssd",
    "hdd": "pd-standard",
    "balanced": "pd-balanced",
}


def resolve_disk_type(*, neutral_type: str) -> str:
    """
        Resolve a neutral volume type hint to a GCP Persistent Disk type.

        :param neutral_type: Neutral type hint (ssd, hdd, nvme, balanced).

        :returns: A GCP Persistent Disk type string.
    """
    rtnval = _DISK_TYPE_TABLE.get(neutral_type.lower(), "pd-balanced")
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
        rtnval = "automojo-{}-{}".format(run_id, name).lower()
        return rtnval

    def find(self, *, run_id: str, name: str,
             zone: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned Persistent Disk by run+name labels.

            :param run_id: Run identifier.
            :param name: Neutral volume name.
            :param zone: Zone the disk lives in.

            :returns: The disk resource dict, or None.
        """
        client = self._client()
        project = self._session_factory.project
        gcp_name = self._gcp_name(run_id=run_id, name=name)
        existing = client.get(project=project, zone=zone, disk=gcp_name)
        if existing is None:
            rtnval: Optional[Dict[str, Any]] = None
            return rtnval
        if not belongs_to_run(labels=existing.get("labels", {}),
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
                resource_kind=self.KIND, extra=list(desired.tags),
                defaults=default_tags,
            )
            disk_type = resolve_disk_type(neutral_type=desired.type)
            body: Dict[str, Any] = {
                "name": gcp_name,
                "size_gb": desired.size_gb,
                "type": "zones/{}/diskTypes/{}".format(zone, disk_type),
                "labels": labels,
            }
            client.insert(project=project, zone=zone, disk_resource=body)
            existing = client.get(project=project, zone=zone, disk=gcp_name)

        attributes: Dict[str, Any] = {}
        attributes["disk_id"] = str(existing.get("id", gcp_name))
        attributes["gcp_name"] = gcp_name
        attributes["zone"] = zone
        attributes["size_gb"] = existing.get("size_gb", desired.size_gb)
        attributes["disk_type"] = resolve_disk_type(neutral_type=desired.type)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name, venue_id=gcp_name,
            attributes=attributes,
            tags=from_labels(labels=existing.get("labels", {})),
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
            gcp_name = entry.get("name", "")
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
                 zone: str) -> List[Dict[str, Any]]:
        """
            Return raw owned Persistent Disk resource dicts for the run.

            :param run_id: Run identifier.
            :param zone: Zone to scan.

            :returns: List of disk resource dicts.
        """
        client = self._client()
        project = self._session_factory.project
        out: List[Dict[str, Any]] = []
        for entry in client.list(project=project, zone=zone):
            if belongs_to_run(labels=entry.get("labels", {}),
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
            labels = entry.get("labels", {})
            name = labels.get(RESOURCE_NAME_LABEL_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["disk_id"] = str(entry.get("id", entry.get("name")))
            attributes["gcp_name"] = entry.get("name", "")
            attributes["size_gb"] = entry.get("size_gb", 0)
            resource = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=entry.get("name", ""),
                attributes=attributes,
                tags=from_labels(labels=labels),
            )
            out.append(resource)
        rtnval = out
        return rtnval
