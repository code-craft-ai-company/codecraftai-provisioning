"""
    .. module:: volumemanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOcean Block Storage volume manager.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)
from ccai.provisioning.venues.digitalocean.doidempotency import (
    matches_name, belongs_to_run
)
from ccai.provisioning.venues.digitalocean.dotagtranslator import (
    base_resource_tags, from_do, to_do, to_flat, RESOURCE_NAME_TAG_KEY
)



from ccai.provisioning.venues.digitalocean.dopagination import (
    collect_all_pages
)

class VolumeManager:
    """
        Manager for DigitalOcean Block Storage volumes.

        Volumes carry the venue owner / run / name tags natively.  When the
        owning resource declares ``attached_to`` the volume is attached to
        the target Droplet after creation.
    """

    KIND: str = "volume"

    def __init__(self, *, client: DigitalOceanClient) -> None:
        """
            Construct a VolumeManager.

            :param client: DigitalOceanClient.
        """
        self._client: DigitalOceanClient = client
        return

    def _all_volumes(self) -> List[Dict[str, Any]]:
        """
            List every Block Storage volume on the account.

            :returns: A list of volume dicts.
        """
        rtnval = collect_all_pages(
            list_fn=self._client.volumes.list, data_key="volumes",
        )
        return rtnval

    def find(self, *, run_id: str, name: str) -> Optional[Dict[str, Any]]:
        """
            Find an existing owned volume by run+name tags.

            :param run_id: Run identifier.
            :param name: Neutral volume name.

            :returns: The volume dict, or None.
        """
        for volume in self._all_volumes():
            do_tags = volume.get("tags", [])
            if matches_name(do_tags=do_tags, run_id=run_id,
                            resource_name=name):
                rtnval: Optional[Dict[str, Any]] = volume
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, desired: CloudStorageVolume, run_id: str,
               region: str, default_tags: List[Dict[str, str]],
               attach_droplet_id: Optional[Any] = None,
               aspects: Any = None) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for a Block Storage volume.

            :param desired: Desired CloudStorageVolume.
            :param run_id: Run identifier.
            :param region: DigitalOcean region slug.
            :param default_tags: Venue default tags.
            :param attach_droplet_id: Optional droplet id to attach to.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the volume.
        """
        existing = self.find(run_id=run_id, name=desired.name)
        neutral_tags = base_resource_tags(
            run_id=run_id, resource_name=desired.name,
            resource_kind=self.KIND, extra=dict(desired.tags),
            defaults=default_tags,
        )
        do_tags = to_do(neutral_tags=neutral_tags)

        if existing is None:
            body: Dict[str, Any] = {
                "name": "codecraftai-{}".format(desired.name),
                "region": region,
                "size_gigabytes": desired.size_gb,
                "tags": do_tags,
            }
            created = self._client.volumes.create(body=body)
            existing = created.get("volume", {})

            if attach_droplet_id is not None:
                attach_body = {
                    "type": "attach",
                    "droplet_id": attach_droplet_id,
                    "region": region,
                }
                try:
                    self._client.volume_actions.post_by_id(
                        volume_id=existing.get("id", ""), body=attach_body
                    )
                except Exception:
                    pass

        attributes: Dict[str, Any] = {}
        attributes["volume_id"] = existing.get("id", "")
        attributes["size_gb"] = existing.get("size_gigabytes",
                                             desired.size_gb)

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=str(existing.get("id", "")),
            attributes=attributes, tags=neutral_tags,
        )
        return rtnval

    def destroy(self, *, run_id: str, aspects: Any) -> List[str]:
        """
            Destroy every owned volume for the run.

            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: List of destroyed volume ids.
        """
        deleted: List[str] = []
        for volume in self._all_volumes():
            do_tags = volume.get("tags", [])
            if not belongs_to_run(do_tags=do_tags, run_id=run_id):
                continue
            volume_id = volume.get("id", "")
            for droplet_id in volume.get("droplet_ids", []) or []:
                detach_body = {"type": "detach", "droplet_id": droplet_id}
                try:
                    self._client.volume_actions.post_by_id(
                        volume_id=volume_id, body=detach_body
                    )
                except Exception:
                    pass
            try:
                self._client.volumes.delete(volume_id=volume_id)
                deleted.append(str(volume_id))
            except Exception:
                pass
        rtnval = deleted
        return rtnval

    def list_owned(self, *, run_id: str) -> List[ProvisionedResource]:
        """
            Return all owned volumes for the run as ProvisionedResources.

            :param run_id: Run identifier.

            :returns: List of ProvisionedResource entries.
        """
        out: List[ProvisionedResource] = []
        for volume in self._all_volumes():
            do_tags = volume.get("tags", [])
            if not belongs_to_run(do_tags=do_tags, run_id=run_id):
                continue
            flat = to_flat(do_tags=do_tags)
            name = flat.get(RESOURCE_NAME_TAG_KEY, "")
            if len(name) == 0:
                continue
            attributes: Dict[str, Any] = {}
            attributes["volume_id"] = volume.get("id", "")
            attributes["size_gb"] = volume.get("size_gigabytes", 0)
            entry = ProvisionedResource(
                kind=self.KIND, name=name,
                venue_id=str(volume.get("id", "")),
                attributes=attributes, tags=from_do(do_tags=do_tags),
            )
            out.append(entry)
        rtnval = out
        return rtnval
