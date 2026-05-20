"""
    .. module:: _mockgcp
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory fake google-cloud-* clients for GCP venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional


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
        rtnval = self._items.get(self._store_key(name=name, scope=scope),
                                 None)
        return rtnval

    def insert(self, **kwargs: Any) -> None:
        """
            Store a resource dict.

            :param kwargs: Call arguments; one ends in ``_resource``.
        """
        self.insert_calls += 1
        body: Dict[str, Any] = {}
        for key, value in kwargs.items():
            if key.endswith("_resource"):
                body = value
        scope = kwargs.get("zone", kwargs.get("region", "global"))
        name = body.get("name", "")
        self._items[self._store_key(name=name, scope=scope)] = body
        return

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
        rtnval = list(self._items.values())
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
        rtnval = self._nodes.get(name, None)
        return rtnval

    def create_node(self, *, parent: str, node_id: str,
                    node: Dict[str, Any]) -> None:
        """
            Store a TPU node dict.

            :param parent: TPU API parent path.
            :param node_id: Node id.
            :param node: The node body.
        """
        self.create_calls += 1
        full_name = "{}/nodes/{}".format(parent, node_id)
        stored = dict(node)
        stored["name"] = full_name
        stored["state"] = "READY"
        stored["network_endpoints"] = [{"ip_address": "10.128.0.50"}]
        self._nodes[full_name] = stored
        return

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
                out.append(node)
        rtnval = out
        return rtnval


class FakeStorageClient:
    """
        In-memory fake of ``storage.Client``.
    """

    def __init__(self) -> None:
        """
            Construct a FakeStorageClient.
        """
        self._buckets: Dict[str, Dict[str, Any]] = {}
        self.create_calls: int = 0
        return

    def get_bucket(self, *, bucket_name: str) -> Optional[Dict[str, Any]]:
        """
            Return a stored bucket dict by name, or None.

            :param bucket_name: GCS bucket name.

            :returns: The bucket dict or None.
        """
        rtnval = self._buckets.get(bucket_name, None)
        return rtnval

    def create_bucket(self, *, bucket_resource: Dict[str, Any]) -> None:
        """
            Store a bucket dict.

            :param bucket_resource: The bucket body.
        """
        self.create_calls += 1
        name = bucket_resource.get("name", "")
        self._buckets[name] = dict(bucket_resource)
        return

    def delete_bucket(self, *, bucket_name: str) -> None:
        """
            Remove a stored bucket dict.

            :param bucket_name: GCS bucket name.
        """
        self._buckets.pop(bucket_name, None)
        return

    def list_buckets(self) -> List[Dict[str, Any]]:
        """
            Return every stored bucket dict.

            :returns: A list of bucket dicts.
        """
        rtnval = list(self._buckets.values())
        return rtnval


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
