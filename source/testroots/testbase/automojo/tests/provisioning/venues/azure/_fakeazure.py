"""
    .. module:: _fakeazure
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory fake of the azure-mgmt-* management clients.

    There is no moto equivalent for Azure; this module provides a small
    deterministic in-memory model of the azure-mgmt SDK call shapes the
    Azure venue uses (``get`` / ``begin_create_or_update`` /
    ``create_or_update`` / ``begin_delete`` / ``list`` / ``delete``).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from azure.core.exceptions import ResourceNotFoundError


class FakeResource:
    """
        A generic attribute-bag resource object.

        Mirrors the duck-typed ``azure-mgmt`` model objects: every
        constructor keyword becomes an attribute, and nested dicts are
        recursively promoted so attribute access works for sub-objects.
    """

    # Keys whose dict values are kept as plain dicts (azure-mgmt models
    # them as ``Dict[str, str]`` rather than nested objects).
    _FLAT_DICT_KEYS = frozenset({"tags"})

    def __init__(self, **kwargs: Any) -> None:
        """
            Construct a FakeResource from arbitrary keyword fields.

            :param kwargs: Field name → value pairs.
        """
        for key, value in kwargs.items():
            if isinstance(value, dict) and key not in self._FLAT_DICT_KEYS:
                setattr(self, key, FakeResource(**value))
            else:
                setattr(self, key, value)
        return


class _Poller:
    """
        Minimal stand-in for ``azure.core.polling.LROPoller``.
    """

    def __init__(self, *, value: Any) -> None:
        """
            Construct a _Poller wrapping an already-resolved value.

            :param value: The resolved resource.
        """
        self._value: Any = value
        return

    def result(self, timeout: Optional[float] = None) -> Any:
        """
            Return the wrapped resolved value.

            :param timeout: Ignored; accepted for SDK signature parity.

            :returns: The resolved resource.
        """
        rtnval = self._value
        return rtnval


def _to_resource(*, params: Any, name: str, location: str,
                 extra: Optional[Dict[str, Any]] = None) -> FakeResource:
    """
        Promote a create-parameters dict to a stored FakeResource.

        :param params: The create parameters (dict or FakeResource).
        :param name: The resource name.
        :param location: The Azure location.
        :param extra: Optional extra fields to merge.

        :returns: A FakeResource representing the stored resource.
    """
    if isinstance(params, FakeResource):
        fields: Dict[str, Any] = dict(params.__dict__)
    elif isinstance(params, dict):
        fields = dict(params)
    else:
        fields = {}

    fields["name"] = name
    if "location" not in fields:
        fields["location"] = location
    fields["id"] = "/fake/{}/{}".format(location, name)
    if extra is not None:
        fields.update(extra)

    rtnval = FakeResource(**fields)
    return rtnval


class _ResourceGroupsOps:
    """
        Fake of ``ResourceManagementClient.resource_groups``.
    """

    def __init__(self, *, store: Dict[str, FakeResource]) -> None:
        """
            Construct.

            :param store: Backing dict keyed by resource-group name.
        """
        self._store: Dict[str, FakeResource] = store
        return

    def get(self, *, resource_group_name: str) -> FakeResource:
        """
            Return a resource group, or raise when absent.

            :param resource_group_name: Resource group name.

            :returns: The FakeResource.
            :raises: ResourceNotFoundError
        """
        entry = self._store.get(resource_group_name, None)
        if entry is None:
            raise ResourceNotFoundError("resource group not found")
        rtnval = entry
        return rtnval

    def create_or_update(self, *, resource_group_name: str,
                         parameters: Any) -> FakeResource:
        """
            Create or update a resource group.

            :param resource_group_name: Resource group name.
            :param parameters: Create parameters.

            :returns: The stored FakeResource.
        """
        location = ""
        if isinstance(parameters, dict):
            location = parameters.get("location", "")
        resource = _to_resource(params=parameters,
                                name=resource_group_name, location=location)
        self._store[resource_group_name] = resource
        rtnval = resource
        return rtnval

    def begin_delete(self, *, resource_group_name: str) -> _Poller:
        """
            Delete a resource group.

            :param resource_group_name: Resource group name.

            :returns: A resolved _Poller.
        """
        self._store.pop(resource_group_name, None)
        rtnval = _Poller(value=None)
        return rtnval


class _ResourcesOps:
    """
        Fake of ``ResourceManagementClient.resources``.
    """

    def __init__(self, *, world: "FakeAzureWorld") -> None:
        """
            Construct.

            :param world: The shared FakeAzureWorld.
        """
        self._world: "FakeAzureWorld" = world
        return

    def list_by_resource_group(self, *, resource_group_name: str
                               ) -> List[FakeResource]:
        """
            Return every non-group resource in a resource group.

            :param resource_group_name: Resource group name.

            :returns: A list of FakeResource entries.
        """
        rtnval = self._world.all_contained_resources(
            resource_group=resource_group_name
        )
        return rtnval


class _ChildScopedOps:
    """
        Generic fake for an azure-mgmt collection scoped under a resource
        group, with optional second-level scoping.

        Supports get / begin_create_or_update / create_or_update /
        begin_delete / delete / list / list_by_resource_group.
    """

    def __init__(self, *, store: Dict[str, FakeResource],
                 name_kw: str, location: str,
                 second_kw: Optional[str] = None) -> None:
        """
            Construct.

            :param store: Backing dict keyed by the composite resource key.
            :param name_kw: Keyword used to pass the resource name.
            :param location: Default Azure location.
            :param second_kw: Optional second-level scoping keyword.
        """
        self._store: Dict[str, FakeResource] = store
        self._name_kw: str = name_kw
        self._location: str = location
        self._second_kw: Optional[str] = second_kw
        return

    def _key(self, *, kwargs: Dict[str, Any]) -> str:
        """
            Build the composite store key from the call kwargs.

            :param kwargs: The call keyword arguments.

            :returns: The composite key string.
        """
        rg = kwargs.get("resource_group_name", "")
        name = kwargs.get(self._name_kw, "")
        if self._second_kw is not None:
            second = kwargs.get(self._second_kw, "")
            rtnval = "{}/{}/{}".format(rg, second, name)
            return rtnval
        rtnval = "{}/{}".format(rg, name)
        return rtnval

    def get(self, **kwargs: Any) -> FakeResource:
        """
            Return a stored resource, or raise when absent.

            :param kwargs: The scoping + name keywords.

            :returns: The FakeResource.
            :raises: ResourceNotFoundError
        """
        key = self._key(kwargs=kwargs)
        entry = self._store.get(key, None)
        if entry is None:
            raise ResourceNotFoundError("resource not found: {}".format(key))
        rtnval = entry
        return rtnval

    def _store_create(self, **kwargs: Any) -> FakeResource:
        """
            Store a create-or-update payload and return the resource.

            :param kwargs: The scoping + name + parameters keywords.

            :returns: The stored FakeResource.
        """
        key = self._key(kwargs=kwargs)
        name = kwargs.get(self._name_kw, "")
        params = (kwargs.get("parameters", None)
                  or kwargs.get("subnet_parameters", None)
                  or kwargs.get("extension_parameters", None)
                  or kwargs.get("disk", None)
                  or kwargs.get("blob_container", None)
                  or {})
        location = self._location
        if isinstance(params, dict) and "location" in params:
            location = params["location"]
        resource = _to_resource(params=params, name=name, location=location)
        self._store[key] = resource
        rtnval = resource
        return rtnval

    def begin_create_or_update(self, **kwargs: Any) -> _Poller:
        """
            Create or update a resource and return a resolved poller.

            :param kwargs: The scoping + name + parameters keywords.

            :returns: A resolved _Poller.
        """
        resource = self._store_create(**kwargs)
        rtnval = _Poller(value=resource)
        return rtnval

    def create_or_update(self, **kwargs: Any) -> FakeResource:
        """
            Create or update a resource synchronously.

            :param kwargs: The scoping + name + parameters keywords.

            :returns: The stored FakeResource.
        """
        rtnval = self._store_create(**kwargs)
        return rtnval

    def create(self, **kwargs: Any) -> Any:
        """
            Create a resource synchronously (storage / blob shape).

            Container creates carry no ``location``; they are treated as a
            no-op record so the venue's ``blob_containers.create`` succeeds.

            :param kwargs: The scoping + name + parameters keywords.

            :returns: A resolved _Poller or the FakeResource.
        """
        if "blob_container" in kwargs:
            rtnval: Any = FakeResource(name=kwargs.get(self._name_kw, ""))
            return rtnval
        resource = self._store_create(**kwargs)
        rtnval = _Poller(value=resource)
        return rtnval

    def begin_create(self, **kwargs: Any) -> _Poller:
        """
            Create a resource and return a resolved poller.

            :param kwargs: The scoping + name + parameters keywords.

            :returns: A resolved _Poller.
        """
        resource = self._store_create(**kwargs)
        rtnval = _Poller(value=resource)
        return rtnval

    def begin_delete(self, **kwargs: Any) -> _Poller:
        """
            Delete a resource and return a resolved poller.

            :param kwargs: The scoping + name keywords.

            :returns: A resolved _Poller.
        """
        key = self._key(kwargs=kwargs)
        self._store.pop(key, None)
        rtnval = _Poller(value=None)
        return rtnval

    def delete(self, **kwargs: Any) -> Any:
        """
            Delete a resource synchronously.

            :param kwargs: The scoping + name keywords.

            :returns: None.
        """
        key = self._key(kwargs=kwargs)
        self._store.pop(key, None)
        return None

    def list(self, *, resource_group_name: str,
             **kwargs: Any) -> List[FakeResource]:
        """
            List every stored resource within a resource group.

            :param resource_group_name: Resource group name.
            :param kwargs: Optional extra scoping (e.g. virtual_network_name).

            :returns: A list of FakeResource entries.
        """
        prefix = "{}/".format(resource_group_name)
        out: List[FakeResource] = []
        for key, value in self._store.items():
            if key.startswith(prefix):
                out.append(value)
        rtnval = out
        return rtnval

    def list_by_resource_group(self, *, resource_group_name: str
                               ) -> List[FakeResource]:
        """
            List every stored resource within a resource group.

            :param resource_group_name: Resource group name.

            :returns: A list of FakeResource entries.
        """
        rtnval = self.list(resource_group_name=resource_group_name)
        return rtnval


class FakeResourceClient:
    """
        Fake ``ResourceManagementClient``.
    """

    def __init__(self, *, world: "FakeAzureWorld") -> None:
        """
            Construct.

            :param world: The shared FakeAzureWorld.
        """
        self.resource_groups: _ResourceGroupsOps = _ResourceGroupsOps(
            store=world.resource_groups
        )
        self.resources: _ResourcesOps = _ResourcesOps(world=world)
        return


class FakeNetworkClient:
    """
        Fake ``NetworkManagementClient``.
    """

    def __init__(self, *, world: "FakeAzureWorld") -> None:
        """
            Construct.

            :param world: The shared FakeAzureWorld.
        """
        loc = world.location
        self.virtual_networks: _ChildScopedOps = _ChildScopedOps(
            store=world.vnets, name_kw="virtual_network_name", location=loc
        )
        self.subnets: _ChildScopedOps = _ChildScopedOps(
            store=world.subnets, name_kw="subnet_name", location=loc,
            second_kw="virtual_network_name",
        )
        self.network_security_groups: _ChildScopedOps = _ChildScopedOps(
            store=world.nsgs, name_kw="network_security_group_name",
            location=loc,
        )
        self.network_interfaces: _ChildScopedOps = _ChildScopedOps(
            store=world.nics, name_kw="network_interface_name", location=loc
        )
        self.public_ip_addresses: _ChildScopedOps = _ChildScopedOps(
            store=world.public_ips, name_kw="public_ip_address_name",
            location=loc,
        )
        return


class FakeComputeClient:
    """
        Fake ``ComputeManagementClient``.
    """

    def __init__(self, *, world: "FakeAzureWorld") -> None:
        """
            Construct.

            :param world: The shared FakeAzureWorld.
        """
        loc = world.location
        self.virtual_machines: _ChildScopedOps = _ChildScopedOps(
            store=world.vms, name_kw="vm_name", location=loc
        )
        self.virtual_machine_extensions: _ChildScopedOps = _ChildScopedOps(
            store=world.vm_extensions, name_kw="vm_extension_name",
            location=loc, second_kw="vm_name",
        )
        self.disks: _ChildScopedOps = _ChildScopedOps(
            store=world.disks, name_kw="disk_name", location=loc
        )
        self.proximity_placement_groups: _ChildScopedOps = _ChildScopedOps(
            store=world.ppgs, name_kw="proximity_placement_group_name",
            location=loc,
        )
        return


class FakeStorageClient:
    """
        Fake ``StorageManagementClient``.
    """

    def __init__(self, *, world: "FakeAzureWorld") -> None:
        """
            Construct.

            :param world: The shared FakeAzureWorld.
        """
        loc = world.location
        self.storage_accounts: _ChildScopedOps = _ChildScopedOps(
            store=world.storage_accounts, name_kw="account_name",
            location=loc,
        )
        # ``get_properties`` aliases ``get`` on the storage accounts ops.
        self.storage_accounts.get_properties = self.storage_accounts.get
        self.blob_containers: _ChildScopedOps = _ChildScopedOps(
            store=world.blob_containers, name_kw="container_name",
            location=loc, second_kw="account_name",
        )
        return


class _RecordSetsOps:
    """
        Fake of ``DnsManagementClient.record_sets``.
    """

    def __init__(self, *, store: Dict[str, FakeResource]) -> None:
        """
            Construct.

            :param store: Backing dict keyed by the record-set key.
        """
        self._store: Dict[str, FakeResource] = store
        return

    def create_or_update(self, *, resource_group_name: str, zone_name: str,
                          relative_record_set_name: str, record_type: str,
                          parameters: Any) -> FakeResource:
        """
            Upsert a DNS record set.

            :param resource_group_name: Resource group name.
            :param zone_name: DNS zone name.
            :param relative_record_set_name: Record set name.
            :param record_type: Record type.
            :param parameters: Record-set payload.

            :returns: The stored FakeResource.
        """
        key = "{}/{}/{}/{}".format(resource_group_name, zone_name,
                                   relative_record_set_name, record_type)
        resource = FakeResource(name=relative_record_set_name,
                                record_type=record_type)
        self._store[key] = resource
        rtnval = resource
        return rtnval

    def delete(self, *, resource_group_name: str, zone_name: str,
               relative_record_set_name: str,
               record_type: str) -> None:
        """
            Delete a DNS record set.

            :param resource_group_name: Resource group name.
            :param zone_name: DNS zone name.
            :param relative_record_set_name: Record set name.
            :param record_type: Record type.

            :returns: None.
        """
        key = "{}/{}/{}/{}".format(resource_group_name, zone_name,
                                   relative_record_set_name, record_type)
        self._store.pop(key, None)
        return None


class FakeDnsClient:
    """
        Fake ``DnsManagementClient``.
    """

    def __init__(self, *, world: "FakeAzureWorld") -> None:
        """
            Construct.

            :param world: The shared FakeAzureWorld.
        """
        self.record_sets: _RecordSetsOps = _RecordSetsOps(
            store=world.dns_records
        )
        return


class FakeAzureWorld:
    """
        Shared in-memory state backing the fake azure-mgmt clients.

        One world instance is created per test; all five fake clients read
        and write the same backing dicts so cross-client effects (a VM
        referencing a NIC, a destroy emptying a resource group) behave
        consistently.
    """

    def __init__(self, *, location: str = "eastus") -> None:
        """
            Construct an empty FakeAzureWorld.

            :param location: The Azure location for stored resources.
        """
        self.location: str = location
        self.resource_groups: Dict[str, FakeResource] = {}
        self.vnets: Dict[str, FakeResource] = {}
        self.subnets: Dict[str, FakeResource] = {}
        self.nsgs: Dict[str, FakeResource] = {}
        self.nics: Dict[str, FakeResource] = {}
        self.public_ips: Dict[str, FakeResource] = {}
        self.vms: Dict[str, FakeResource] = {}
        self.vm_extensions: Dict[str, FakeResource] = {}
        self.disks: Dict[str, FakeResource] = {}
        self.ppgs: Dict[str, FakeResource] = {}
        self.storage_accounts: Dict[str, FakeResource] = {}
        self.blob_containers: Dict[str, FakeResource] = {}
        self.dns_records: Dict[str, FakeResource] = {}
        return

    def all_contained_resources(self, *, resource_group: str
                                ) -> List[FakeResource]:
        """
            Return every non-group resource stored in a resource group.

            :param resource_group: Resource group name.

            :returns: A list of FakeResource entries.
        """
        prefix = "{}/".format(resource_group)
        out: List[FakeResource] = []
        for store in (self.vnets, self.subnets, self.nsgs, self.nics,
                      self.public_ips, self.vms, self.vm_extensions,
                      self.disks, self.ppgs, self.storage_accounts):
            for key, value in store.items():
                if key.startswith(prefix):
                    out.append(value)
        rtnval = out
        return rtnval

    def resource_client(self) -> FakeResourceClient:
        """
            Return a fake ResourceManagementClient bound to this world.

            :returns: A FakeResourceClient.
        """
        rtnval = FakeResourceClient(world=self)
        return rtnval

    def network_client(self) -> FakeNetworkClient:
        """
            Return a fake NetworkManagementClient bound to this world.

            :returns: A FakeNetworkClient.
        """
        rtnval = FakeNetworkClient(world=self)
        return rtnval

    def compute_client(self) -> FakeComputeClient:
        """
            Return a fake ComputeManagementClient bound to this world.

            :returns: A FakeComputeClient.
        """
        rtnval = FakeComputeClient(world=self)
        return rtnval

    def storage_client(self) -> FakeStorageClient:
        """
            Return a fake StorageManagementClient bound to this world.

            :returns: A FakeStorageClient.
        """
        rtnval = FakeStorageClient(world=self)
        return rtnval

    def dns_client(self) -> FakeDnsClient:
        """
            Return a fake DnsManagementClient bound to this world.

            :returns: A FakeDnsClient.
        """
        rtnval = FakeDnsClient(world=self)
        return rtnval
