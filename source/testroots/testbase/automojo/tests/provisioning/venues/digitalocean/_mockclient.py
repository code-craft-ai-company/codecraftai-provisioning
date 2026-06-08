"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: An in-memory mock of the ``pydo`` SDK client surface used to
               exercise the DigitalOcean venue without any network access.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


def _tag_matches(*, tags: List[str], tag_name: Optional[str]) -> bool:
    """
        Return True when the tag list carries the requested tag.

        :param tags: The resource tag string-list.
        :param tag_name: The requested ``tag_name`` filter or None.

        :returns: True when the resource should be included.
    """
    if tag_name is None:
        rtnval = True
        return rtnval
    rtnval = tag_name in tags
    return rtnval


class _VpcsCollection:
    """
        In-memory mock of the ``pydo`` vpcs resource collection.
    """

    def __init__(self, *, store: Dict[str, Any]) -> None:
        """
            Construct the collection.

            :param store: Shared backing store.
        """
        self._store: Dict[str, Any] = store
        return

    def list(self, **kwargs: Any) -> Dict[str, Any]:
        """
            List every VPC.

            :returns: A ``{"vpcs": [...]}`` dict.
        """
        rtnval = {"vpcs": list(self._store["vpcs"].values())}
        return rtnval

    def create(self, *, body: Dict[str, Any]) -> Dict[str, Any]:
        """
            Create a VPC.

            :param body: The create body.

            :returns: A ``{"vpc": {...}}`` dict.
        """
        new_id = "vpc-{}".format(len(self._store["vpcs"]) + 1)
        record = dict(body)
        record["id"] = new_id
        self._store["vpcs"][new_id] = record
        rtnval = {"vpc": record}
        return rtnval

    def delete(self, *, vpc_id: str) -> None:
        """
            Delete a VPC.

            :param vpc_id: The VPC id.
        """
        self._store["vpcs"].pop(vpc_id, None)
        return


class _FirewallsCollection:
    """
        In-memory mock of the ``pydo`` firewalls resource collection.
    """

    def __init__(self, *, store: Dict[str, Any]) -> None:
        """
            Construct the collection.

            :param store: Shared backing store.
        """
        self._store: Dict[str, Any] = store
        return

    def list(self, **kwargs: Any) -> Dict[str, Any]:
        """
            List every firewall.

            :returns: A ``{"firewalls": [...]}`` dict.
        """
        rtnval = {"firewalls": list(self._store["firewalls"].values())}
        return rtnval

    def create(self, *, body: Dict[str, Any]) -> Dict[str, Any]:
        """
            Create a firewall.

            :param body: The create body.

            :returns: A ``{"firewall": {...}}`` dict.
        """
        new_id = "fw-{}".format(len(self._store["firewalls"]) + 1)
        record = dict(body)
        record["id"] = new_id
        self._store["firewalls"][new_id] = record
        rtnval = {"firewall": record}
        return rtnval

    def update(self, *, firewall_id: str,
               body: Dict[str, Any]) -> Dict[str, Any]:
        """
            Update a firewall.

            :param firewall_id: The firewall id.
            :param body: The update body.

            :returns: A ``{"firewall": {...}}`` dict.
        """
        record = dict(body)
        record["id"] = firewall_id
        self._store["firewalls"][firewall_id] = record
        rtnval = {"firewall": record}
        return rtnval

    def delete(self, *, firewall_id: str) -> None:
        """
            Delete a firewall.

            :param firewall_id: The firewall id.
        """
        self._store["firewalls"].pop(firewall_id, None)
        return


class _SshKeysCollection:
    """
        In-memory mock of the ``pydo`` ssh_keys resource collection.
    """

    def __init__(self, *, store: Dict[str, Any]) -> None:
        """
            Construct the collection.

            :param store: Shared backing store.
        """
        self._store: Dict[str, Any] = store
        return

    def list(self, **kwargs: Any) -> Dict[str, Any]:
        """
            List every SSH key.

            :returns: A ``{"ssh_keys": [...]}`` dict.
        """
        rtnval = {"ssh_keys": list(self._store["ssh_keys"].values())}
        return rtnval

    def create(self, *, body: Dict[str, Any]) -> Dict[str, Any]:
        """
            Create an SSH key.

            :param body: The create body.

            :returns: A ``{"ssh_key": {...}}`` dict.
        """
        new_id = len(self._store["ssh_keys"]) + 1
        record = dict(body)
        record["id"] = new_id
        record["fingerprint"] = "fp-{}".format(record.get("name", new_id))
        self._store["ssh_keys"][new_id] = record
        rtnval = {"ssh_key": record}
        return rtnval

    def delete(self, *, ssh_key_id: Any) -> None:
        """
            Delete an SSH key.

            :param ssh_key_id: The SSH key id.
        """
        self._store["ssh_keys"].pop(ssh_key_id, None)
        return


class _DropletsCollection:
    """
        In-memory mock of the ``pydo`` droplets resource collection.
    """

    def __init__(self, *, store: Dict[str, Any]) -> None:
        """
            Construct the collection.

            :param store: Shared backing store.
        """
        self._store: Dict[str, Any] = store
        return

    def list(self, *, tag_name: Optional[str] = None,
             **kwargs: Any) -> Dict[str, Any]:
        """
            List Droplets, optionally filtered by ``tag_name``.

            :param tag_name: Optional tag filter.

            :returns: A ``{"droplets": [...]}`` dict.
        """
        out: List[Dict[str, Any]] = []
        for record in self._store["droplets"].values():
            if _tag_matches(tags=record.get("tags", []), tag_name=tag_name):
                out.append(record)
        rtnval = {"droplets": out}
        return rtnval

    def create(self, *, body: Dict[str, Any]) -> Dict[str, Any]:
        """
            Create a Droplet.

            :param body: The create body.

            :returns: A ``{"droplet": {...}}`` dict.
        """
        new_id = len(self._store["droplets"]) + 1
        record = dict(body)
        record["id"] = new_id
        record["size_slug"] = body.get("size", "")
        record["networks"] = {
            "v4": [
                {"type": "public", "ip_address": "203.0.113.{}".format(new_id)},
                {"type": "private", "ip_address": "10.0.0.{}".format(new_id)},
            ]
        }
        self._store["droplets"][new_id] = record
        rtnval = {"droplet": record}
        return rtnval

    def destroy(self, *, droplet_id: Any) -> None:
        """
            Destroy a Droplet.

            :param droplet_id: The Droplet id.
        """
        self._store["droplets"].pop(droplet_id, None)
        return


class _VolumesCollection:
    """
        In-memory mock of the ``pydo`` volumes resource collection.
    """

    def __init__(self, *, store: Dict[str, Any]) -> None:
        """
            Construct the collection.

            :param store: Shared backing store.
        """
        self._store: Dict[str, Any] = store
        return

    def list(self, **kwargs: Any) -> Dict[str, Any]:
        """
            List every volume.

            :returns: A ``{"volumes": [...]}`` dict.
        """
        rtnval = {"volumes": list(self._store["volumes"].values())}
        return rtnval

    def create(self, *, body: Dict[str, Any]) -> Dict[str, Any]:
        """
            Create a volume.

            :param body: The create body.

            :returns: A ``{"volume": {...}}`` dict.
        """
        new_id = "vol-{}".format(len(self._store["volumes"]) + 1)
        record = dict(body)
        record["id"] = new_id
        record["droplet_ids"] = []
        self._store["volumes"][new_id] = record
        rtnval = {"volume": record}
        return rtnval

    def delete(self, *, volume_id: str) -> None:
        """
            Delete a volume.

            :param volume_id: The volume id.
        """
        self._store["volumes"].pop(volume_id, None)
        return


class _VolumeActionsCollection:
    """
        In-memory mock of the ``pydo`` volume_actions resource collection.
    """

    def __init__(self, *, store: Dict[str, Any]) -> None:
        """
            Construct the collection.

            :param store: Shared backing store.
        """
        self._store: Dict[str, Any] = store
        return

    def post_by_id(self, *, volume_id: str,
                   body: Dict[str, Any]) -> Dict[str, Any]:
        """
            Apply a volume action (attach / detach).

            :param volume_id: The volume id.
            :param body: The action body.

            :returns: A ``{"action": {...}}`` dict.
        """
        volume = self._store["volumes"].get(volume_id, None)
        if volume is not None:
            if body.get("type", "") == "attach":
                volume.setdefault("droplet_ids", []).append(
                    body.get("droplet_id")
                )
            elif body.get("type", "") == "detach":
                droplets = volume.get("droplet_ids", [])
                if body.get("droplet_id") in droplets:
                    droplets.remove(body.get("droplet_id"))
        rtnval = {"action": {"id": 1, "status": "completed"}}
        return rtnval


class _DomainsCollection:
    """
        In-memory mock of the ``pydo`` domains resource collection.
    """

    def __init__(self, *, store: Dict[str, Any]) -> None:
        """
            Construct the collection.

            :param store: Shared backing store.
        """
        self._store: Dict[str, Any] = store
        return

    def list_records(self, *, domain_name: str,
                     **kwargs: Any) -> Dict[str, Any]:
        """
            List records within a domain.

            :param domain_name: The domain name.

            :returns: A ``{"domain_records": [...]}`` dict.
        """
        records = self._store["dns"].get(domain_name, {})
        rtnval = {"domain_records": list(records.values())}
        return rtnval

    def create_record(self, *, domain_name: str,
                      body: Dict[str, Any]) -> Dict[str, Any]:
        """
            Create a record within a domain.

            :param domain_name: The domain name.
            :param body: The record body.

            :returns: A ``{"domain_record": {...}}`` dict.
        """
        domain = self._store["dns"].setdefault(domain_name, {})
        new_id = len(domain) + 1
        record = dict(body)
        record["id"] = new_id
        domain[new_id] = record
        rtnval = {"domain_record": record}
        return rtnval

    def delete_record(self, *, domain_name: str,
                     domain_record_id: Any) -> None:
        """
            Delete a record within a domain.

            :param domain_name: The domain name.
            :param domain_record_id: The record id.
        """
        domain = self._store["dns"].get(domain_name, {})
        domain.pop(domain_record_id, None)
        return


class _SpacesCollection:
    """
        In-memory mock of the Spaces (S3-compatible) bucket surface.
    """

    def __init__(self, *, store: Dict[str, Any]) -> None:
        """
            Construct the collection.

            :param store: Shared backing store.
        """
        self._store: Dict[str, Any] = store
        return

    def head_bucket(self, *, bucket: str, region: str) -> bool:
        """
            Report whether a bucket exists.

            :param bucket: The bucket name.
            :param region: The Spaces region.

            :returns: True when the bucket exists.
        """
        rtnval = bucket in self._store["spaces"]
        return rtnval

    def create_bucket(self, *, bucket: str, region: str) -> None:
        """
            Create a bucket.

            :param bucket: The bucket name.
            :param region: The Spaces region.
        """
        self._store["spaces"][bucket] = {"region": region}
        return

    def delete_bucket(self, *, bucket: str, region: str) -> None:
        """
            Delete a bucket.

            :param bucket: The bucket name.
            :param region: The Spaces region.
        """
        self._store["spaces"].pop(bucket, None)
        return


class MockDigitalOceanRawClient:
    """
        A deterministic in-memory mock of the ``pydo`` SDK client surface.

        Construct one of these and pass it to :class:`DigitalOceanClient`
        via its ``raw_client`` argument so the venue exercises every code
        path without touching the DigitalOcean API.
    """

    def __init__(self) -> None:
        """
            Construct a MockDigitalOceanRawClient.
        """
        self._store: Dict[str, Any] = {
            "vpcs": {},
            "firewalls": {},
            "ssh_keys": {},
            "droplets": {},
            "volumes": {},
            "dns": {},
            "spaces": {},
        }
        self.vpcs: _VpcsCollection = _VpcsCollection(store=self._store)
        self.firewalls: _FirewallsCollection = _FirewallsCollection(
            store=self._store
        )
        self.ssh_keys: _SshKeysCollection = _SshKeysCollection(
            store=self._store
        )
        self.droplets: _DropletsCollection = _DropletsCollection(
            store=self._store
        )
        self.volumes: _VolumesCollection = _VolumesCollection(
            store=self._store
        )
        self.volume_actions: _VolumeActionsCollection = (
            _VolumeActionsCollection(store=self._store)
        )
        self.domains: _DomainsCollection = _DomainsCollection(
            store=self._store
        )
        self.spaces: _SpacesCollection = _SpacesCollection(store=self._store)
        return

    @property
    def store(self) -> Dict[str, Any]:
        """
            Return the backing store for assertions.

            :returns: The raw backing-store dict.
        """
        rtnval = self._store
        return rtnval
