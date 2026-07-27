"""
    .. module:: _mockgcp
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory fake google-cloud-* clients for GCP venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


class _FakeOperation:
    """
        Stand-in for a Compute ``ExtendedOperation`` / TPU ``Operation``.

        Mutating GCP calls return immediately with an operation rather than
        the finished resource, and the venue blocks on ``result()`` before
        reading the resource back — otherwise the follow-up ``get`` races the
        create and 404s.  A mock that returned ``None`` from a mutation left
        that wait completely untested, and every caller of it crashed with
        ``'NoneType' object has no attribute 'result'``.
    """

    def __init__(self, *, value: Any = None) -> None:
        """
            Construct a _FakeOperation.

            :param value: The value ``result()`` should return.
        """
        self._value: Any = value
        self.result_calls: int = 0
        return

    def result(self, *args: Any, **kwargs: Any) -> Any:
        """
            Return the finished operation's value.

            :returns: The value the operation resolved to.
        """
        self.result_calls = self.result_calls + 1
        rtnval = self._value
        return rtnval


# Fields the Compute API models as integers.  Everything else the venue reads
# is a string or a message.  The distinction matters because protobuf returns
# TYPED zero values for unset fields, and the venue relies on that:
# `existing.id != 0` picks the fallback name, and `len(existing.self_link) > 0`
# picks the fallback link.  Handing back None instead would make str(None) the
# resource id and crash len().
_INT_FIELDS = ("id", "size_gb", "disk_size_gb")


class _ProtoLike:
    """
        Attribute-addressable view over a stored resource dict, with
        protobuf's zero-value semantics for unset fields.

        The real google-cloud clients return protobuf messages, not dicts, so
        a mock that handed back dicts left every attribute read in the venue
        untested — and the venue reads them everywhere.
    """

    def __init__(self, *, body: Dict[str, Any]) -> None:
        """
            Construct a _ProtoLike.

            :param body: The stored resource dict.
        """
        object.__setattr__(self, "_body", body)
        return

    def __getattr__(self, name: str) -> Any:
        """
            Resolve a field, defaulting to the protobuf zero value.

            :param name: The field name.

            :returns: The field value, or its typed zero value when unset.
        """
        if name.startswith("_") is True:
            raise AttributeError(name)

        body = object.__getattribute__(self, "_body")
        if name in body:
            value = body[name]
            if isinstance(value, dict) is True:
                # Map fields (labels) behave as plain dicts in protobuf and
                # are iterated as such; wrapping them would break that.
                rtnval = value
                return rtnval
            if isinstance(value, list) is True:
                rtnval = [
                    _ProtoLike(body=item) if isinstance(item, dict) else item
                    for item in value
                ]
                return rtnval
            rtnval = value
            return rtnval

        if name in _INT_FIELDS:
            rtnval = 0
            return rtnval

        rtnval = ""
        return rtnval

    def __setattr__(self, name: str, value: Any) -> None:
        """
            Set a field.

            :param name: The field name.
            :param value: The value to store.
        """
        body = object.__getattribute__(self, "_body")
        body[name] = value
        return

    def as_dict(self) -> Dict[str, Any]:
        """
            Return the underlying dict.

            :returns: The stored resource dict.
        """
        rtnval = object.__getattribute__(self, "_body")
        return rtnval


class _ResourceStore:
    """
        Generic keyed store backing one fake compute sub-client.

        Records call counts so tests can assert TPU/Compute branch isolation.
    """

    def __init__(self, *, key_param: str) -> None:
        """
            Construct a _ResourceStore.

            :param key_param: The name of the keyword argument carrying the
                              resource name in get/insert/delete calls.
        """
        self._key_param: str = key_param
        self._items: Dict[str, Dict[str, Any]] = {}
        self.insert_calls: int = 0
        self.delete_calls: int = 0
        return

    def _store_key(self, *, name: str, scope: str) -> str:
        """
            Build the internal store key (scope-qualified).

            :param name: Resource name.
            :param scope: Scope qualifier (zone/region or "global").

            :returns: A composite store key.
        """
        rtnval = "{}::{}".format(scope, name)
        return rtnval

    def get(self, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """
            Return a stored resource dict by name, or None.

            :param kwargs: Call arguments including the key param.

            :returns: The resource dict or None.
        """
        name = kwargs.get(self._key_param, "")
        scope = kwargs.get("zone", kwargs.get("region", "global"))
        found = self._items.get(self._store_key(name=name, scope=scope),
                                None)
        if found is None:
            rtnval: Optional[Any] = None
            return rtnval
        rtnval = _ProtoLike(body=found)
        return rtnval

    def insert(self, **kwargs: Any) -> Any:
        """
            Store a resource dict and return an operation handle.

            Compute mutations answer with an operation, not the resource; the
            venue waits on it before reading the resource back.

            :param kwargs: Call arguments; one ends in ``_resource``.

            :returns: A :class:`_FakeOperation`.
        """
        self.insert_calls += 1
        body: Dict[str, Any] = {}
        for key, value in kwargs.items():
            if key.endswith("_resource"):
                body = value
        scope = kwargs.get("zone", kwargs.get("region", "global"))
        name = body.get("name", "")
        self._items[self._store_key(name=name, scope=scope)] = body
        rtnval = _FakeOperation()
        return rtnval

    def delete(self, **kwargs: Any) -> None:
        """
            Remove a stored resource dict.

            :param kwargs: Call arguments including the key param.
        """
        self.delete_calls += 1
        name = kwargs.get(self._key_param, "")
        scope = kwargs.get("zone", kwargs.get("region", "global"))
        self._items.pop(self._store_key(name=name, scope=scope), None)
        return

    def list(self, **kwargs: Any) -> List[Dict[str, Any]]:
        """
            Return every stored resource dict.

            :param kwargs: Ignored scope arguments.

            :returns: A list of resource dicts.
        """
        rtnval = [_ProtoLike(body=body) for body in self._items.values()]
        return rtnval


def build_fake_compute() -> Dict[str, _ResourceStore]:
    """
        Build a fake compute client (dict of sub-clients).

        :returns: A dict matching the GcpSessionFactory compute shape.
    """
    rtnval = {
        "networks": _ResourceStore(key_param="network"),
        "subnetworks": _ResourceStore(key_param="subnetwork"),
        "firewalls": _ResourceStore(key_param="firewall"),
        "instances": _ResourceStore(key_param="instance"),
        "disks": _ResourceStore(key_param="disk"),
        "resource_policies": _ResourceStore(key_param="resource_policy"),
        "images": _ResourceStore(key_param="image"),
    }
    return rtnval


class FakeTpuClient:
    """
        In-memory fake of ``tpu_v2.TpuClient``.
    """

    def __init__(self) -> None:
        """
            Construct a FakeTpuClient.
        """
        self._nodes: Dict[str, Dict[str, Any]] = {}
        self.create_calls: int = 0
        self.delete_calls: int = 0
        return

    def get_node(self, *, name: str) -> Optional[Dict[str, Any]]:
        """
            Return a stored TPU node dict by full name, or None.

            :param name: Full TPU node path.

            :returns: The node dict or None.
        """
        found = self._nodes.get(name, None)
        if found is None:
            rtnval: Optional[Any] = None
            return rtnval
        rtnval = _ProtoLike(body=found)
        return rtnval

    def create_node(self, *, parent: str, node_id: str,
                    node: Dict[str, Any]) -> Any:
        """
            Store a TPU node dict and return an operation handle.

            Like Compute mutations, TPU node creation answers with an
            operation the venue waits on before reading the node back.

            :param parent: TPU API parent path.
            :param node_id: Node id.
            :param node: The node body.

            :returns: A :class:`_FakeOperation`.
        """
        self.create_calls += 1
        full_name = "{}/nodes/{}".format(parent, node_id)
        stored = dict(node)
        stored["name"] = full_name
        stored["state"] = "READY"
        stored["network_endpoints"] = [{"ip_address": "10.128.0.50"}]
        self._nodes[full_name] = stored
        rtnval = _FakeOperation()
        return rtnval

    def delete_node(self, *, name: str) -> None:
        """
            Remove a stored TPU node dict.

            :param name: Full TPU node path.
        """
        self.delete_calls += 1
        self._nodes.pop(name, None)
        return

    def list_nodes(self, *, parent: str) -> List[Dict[str, Any]]:
        """
            Return every stored TPU node under a parent.

            :param parent: TPU API parent path.

            :returns: A list of node dicts.
        """
        out: List[Dict[str, Any]] = []
        for full_name, node in self._nodes.items():
            if full_name.startswith(parent + "/"):
                out.append(_ProtoLike(body=node))
        rtnval = out
        return rtnval


class _FakeBucket:
    """
        Stand-in for a ``storage.Bucket``.

        The venue reads ``name`` / ``labels`` / ``location`` off buckets and
        deletes them via ``bucket.delete(force=True)`` — buckets are active
        record in the storage SDK, unlike the compute resources.
    """

    def __init__(self, *, name: str, client: Any,
                 labels: Optional[Dict[str, str]] = None,
                 location: str = "",
                 versioning_enabled: bool = False) -> None:
        """
            Construct a _FakeBucket.

            :param name: The bucket name.
            :param client: The owning fake client.
            :param labels: The bucket labels.
            :param location: The bucket location.
            :param versioning_enabled: Whether versioning is on.
        """
        self.name: str = name
        self.labels: Dict[str, str] = dict(labels or {})
        self.location: str = location
        self.versioning_enabled: bool = versioning_enabled
        self._client = client
        return

    def delete(self, force: bool = False) -> None:
        """
            Delete this bucket.

            :param force: Whether to delete a non-empty bucket.
        """
        self._client.remove(name=self.name)
        return


class FakeStorageClient:
    """
        In-memory fake of ``storage.Client``.

        Mirrors the surface the venue uses: ``lookup_bucket`` answers None for
        an absent bucket rather than raising, ``create_bucket`` takes the
        bucket OBJECT positionally with a keyword location, and
        ``list_buckets`` filters by prefix.  The previous fake modelled a
        different, dict-based API entirely, so none of these paths were
        exercised.
    """

    def __init__(self) -> None:
        """
            Construct a FakeStorageClient.
        """
        self._buckets: Dict[str, _FakeBucket] = {}
        self.create_calls: int = 0
        return

    def lookup_bucket(self, bucket_name: str) -> Optional[_FakeBucket]:
        """
            Return a bucket by name, or None when it does not exist.

            :param bucket_name: The bucket name.

            :returns: The bucket, or None.
        """
        rtnval = self._buckets.get(bucket_name, None)
        return rtnval

    def get_bucket(self, bucket_name: str) -> Optional[_FakeBucket]:
        """
            Return a bucket by name.

            :param bucket_name: The bucket name.

            :returns: The bucket, or None.
        """
        rtnval = self._buckets.get(bucket_name, None)
        return rtnval

    def create_bucket(self, bucket: Any,
                      location: str = "") -> _FakeBucket:
        """
            Create a bucket from a bucket object.

            :param bucket: The bucket to create, carrying name and labels.
            :param location: The bucket location.

            :returns: The created bucket.
        """
        self.create_calls += 1
        name = getattr(bucket, "name", "")
        built = _FakeBucket(
            name=name, client=self,
            labels=dict(getattr(bucket, "labels", None) or {}),
            location=location,
            versioning_enabled=bool(
                getattr(bucket, "versioning_enabled", False)))
        self._buckets[name] = built
        rtnval = built
        return rtnval

    def list_buckets(self, prefix: str = "") -> List[_FakeBucket]:
        """
            List buckets, optionally filtered by name prefix.

            :param prefix: The name prefix to match.

            :returns: The matching buckets.
        """
        out: List[_FakeBucket] = []
        for name, bucket in self._buckets.items():
            if len(prefix) == 0 or name.startswith(prefix):
                out.append(bucket)
        rtnval = out
        return rtnval

    def remove(self, *, name: str) -> None:
        """
            Drop a bucket from the store.

            :param name: The bucket name.
        """
        self._buckets.pop(name, None)
        return


class FakeDnsClient:
    """
        In-memory fake of ``dns.Client``.
    """

    def __init__(self) -> None:
        """
            Construct a FakeDnsClient.
        """
        self.upserts: List[Dict[str, Any]] = []
        self.deletes: List[Dict[str, Any]] = []
        return

    def upsert_record_set(self, *, zone_name: str,
                          record_set: Dict[str, Any]) -> None:
        """
            Record an upsert call.

            :param zone_name: DNS managed zone name.
            :param record_set: The record-set body.
        """
        self.upserts.append({"zone": zone_name, "record": record_set})
        return

    def delete_record_set(self, *, zone_name: str,
                          record_set: Dict[str, Any]) -> None:
        """
            Record a delete call.

            :param zone_name: DNS managed zone name.
            :param record_set: The record-set body.
        """
        self.deletes.append({"zone": zone_name, "record": record_set})
        return
