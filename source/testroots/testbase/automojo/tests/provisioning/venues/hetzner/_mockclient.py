"""
    .. module:: _mockclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory MockHetznerClient mimicking the hcloud SDK surface.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


class _FakeObject:
    """
        Lightweight attribute bag standing in for an hcloud SDK object.
    """

    def __init__(self, **kwargs: Any) -> None:
        """
            Construct a _FakeObject from keyword attributes.

            :param kwargs: Attribute name / value pairs.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        return


def _selector_matches(*, labels: Dict[str, str], selector: str) -> bool:
    """
        Test whether a labels dict satisfies a comma-joined label selector.

        :param labels: The object's labels dict.
        :param selector: A ``key=value,key=value`` selector string.

        :returns: True when every selector clause matches.
    """
    if selector is None or len(selector) == 0:
        rtnval = True
        return rtnval
    for clause in selector.split(","):
        if "=" not in clause:
            continue
        key, value = clause.split("=", 1)
        if labels.get(key, None) != value:
            rtnval = False
            return rtnval
    rtnval = True
    return rtnval


class _MockCollection:
    """
        In-memory stand-in for an hcloud resource collection.

        Records every create / delete call so tests can assert on
        idempotence (no mutating calls on re-apply).
    """

    def __init__(self, *, kind: str, owner: "MockHetznerClient") -> None:
        """
            Construct a _MockCollection.

            :param kind: Resource kind label (e.g. ``server``).
            :param owner: Owning MockHetznerClient (for call counters).
        """
        self._kind: str = kind
        self._owner: "MockHetznerClient" = owner
        self._objects: Dict[str, _FakeObject] = {}
        self._next_id: int = 1
        return

    def get_by_name(self, *, name: str) -> Optional[_FakeObject]:
        """
            Look up an object by name.

            :param name: The object name.

            :returns: The object, or None when absent.
        """
        rtnval = self._objects.get(name, None)
        return rtnval

    def get_all(self, *, label_selector: Optional[str] = None
                ) -> List[_FakeObject]:
        """
            Return every object matching an optional label selector.

            :param label_selector: Optional selector string.

            :returns: A list of matching objects.
        """
        out: List[_FakeObject] = []
        effective_selector = label_selector if label_selector is not None else ""
        for obj in self._objects.values():
            labels = getattr(obj, "labels", {})
            if _selector_matches(labels=labels, selector=effective_selector):
                out.append(obj)
        rtnval = out
        return rtnval

    def create(self, *, name: str, labels: Optional[Dict[str, str]] = None,
               **kwargs: Any) -> _FakeObject:
        """
            Create and store a fake object.

            :param name: The object name.
            :param labels: Optional labels dict.
            :param kwargs: Additional attributes to record.

            :returns: The created object (or a create-response wrapper).
        """
        self._owner.create_calls += 1
        effective_labels = labels if labels is not None else {}
        attributes: Dict[str, Any] = {"id": self._next_id, "name": name,
                                      "labels": effective_labels}
        self._next_id += 1

        server_type_name = kwargs.pop("server_type", None)
        if server_type_name is not None:
            attributes["server_type"] = _FakeObject(name=server_type_name)
        for key, value in kwargs.items():
            attributes[key] = value

        obj = _FakeObject(**attributes)
        self._objects[name] = obj

        if self._kind == "server":
            rtnval: Any = _FakeObject(server=obj)
            return rtnval
        if self._kind == "volume":
            rtnval = _FakeObject(volume=obj)
            return rtnval
        rtnval = obj
        return rtnval

    def delete(self, **kwargs: Any) -> None:
        """
            Delete a previously-created object.

            :param kwargs: Carries the object under its kind keyword.
        """
        self._owner.delete_calls += 1
        target = None
        for value in kwargs.values():
            target = value
        if target is None:
            return
        name = getattr(target, "name", None)
        if name is not None and name in self._objects:
            del self._objects[name]
        return

    def resize(self, *, volume: Any, size: int) -> None:
        """
            Grow a volume in place to a new (larger) size.

            Mirrors the hcloud ``VolumesClient.resize`` surface; Hetzner
            volumes only support a grow.

            :param volume: The volume object.
            :param size: The new size in GiB.
        """
        self._owner.resize_calls += 1
        setattr(volume, "size", size)
        return

    def attach(self, *, volume: Any, server_id: Any) -> None:
        """
            Record a volume attachment.

            :param volume: The volume object.
            :param server_id: The server id to attach to.
        """
        self._owner.attach_calls += 1
        setattr(volume, "attached_server_id", server_id)
        return

    def detach(self, *, volume: Any) -> None:
        """
            Record a volume detachment.

            :param volume: The volume object.
        """
        self._owner.detach_calls += 1
        setattr(volume, "attached_server_id", None)
        return


class MockHetznerClient:
    """
        In-memory MockHetznerClient mimicking the ``hcloud.Client`` surface.

        Exposes ``networks``, ``firewalls``, ``ssh_keys``, ``servers``, and
        ``volumes`` collections plus call counters so tests can assert that
        a re-apply performs no mutating calls.
    """

    def __init__(self) -> None:
        """
            Construct a MockHetznerClient with empty collections.
        """
        self.create_calls: int = 0
        self.delete_calls: int = 0
        self.attach_calls: int = 0
        self.detach_calls: int = 0
        self.resize_calls: int = 0

        self.networks: _MockCollection = _MockCollection(
            kind="network", owner=self)
        self.firewalls: _MockCollection = _MockCollection(
            kind="firewall", owner=self)
        self.ssh_keys: _MockCollection = _MockCollection(
            kind="ssh_key", owner=self)
        self.servers: _MockCollection = _MockCollection(
            kind="server", owner=self)
        self.volumes: _MockCollection = _MockCollection(
            kind="volume", owner=self)
        return


class MockDnsClient:
    """
        In-memory stand-in for the Hetzner DNS API client.
    """

    def __init__(self) -> None:
        """
            Construct a MockDnsClient.
        """
        self.records: List[Dict[str, Any]] = []
        self.delete_calls: int = 0
        self._next_id: int = 1
        return

    def get_zone_id(self, *, zone_name: str) -> str:
        """
            Resolve a deterministic zone id for a zone name.

            :param zone_name: The DNS zone name.

            :returns: A deterministic zone id string.
        """
        rtnval = "zone-{}".format(zone_name)
        return rtnval

    def create_record(self, *, zone_id: str, name: str,
                       record_type: str, value: str, ttl: int
                       ) -> _FakeObject:
        """
            Create a DNS record.

            :param zone_id: The zone id.
            :param name: The record name.
            :param record_type: The record type.
            :param value: The record value.
            :param ttl: The record TTL.

            :returns: The created record object.
        """
        record_id = "rec-{}".format(self._next_id)
        self._next_id += 1
        entry = {"id": record_id, "zone_id": zone_id, "name": name,
                 "type": record_type, "value": value, "ttl": ttl}
        self.records.append(entry)
        rtnval = _FakeObject(id=record_id)
        return rtnval

    def delete_records(self, *, zone_name: str, name: str) -> None:
        """
            Delete every record matching a zone + name.

            :param zone_name: The DNS zone name.
            :param name: The record name.
        """
        self.delete_calls += 1
        zone_id = self.get_zone_id(zone_name=zone_name)
        kept: List[Dict[str, Any]] = []
        for entry in self.records:
            if entry["zone_id"] == zone_id and entry["name"] == name:
                continue
            kept.append(entry)
        self.records = kept
        return


class MockVpnControlPlane:
    """
        In-memory stand-in for an IVPNControlPlane implementation.
    """

    def __init__(self, *, minted_authkey: str = "tskey-mock-0001") -> None:
        """
            Construct a MockVpnControlPlane.

            :param minted_authkey: The auth-key returned to callers.
        """
        self.minted_authkey: str = minted_authkey
        self.deleted_devices: List[str] = []
        return

    def delete_device(self, *, device_id: str, aspects: Any) -> None:
        """
            Record a device de-registration.

            :param device_id: The device id to delete.
            :param aspects: ProvisioningAspects.
        """
        self.deleted_devices.append(device_id)
        return
