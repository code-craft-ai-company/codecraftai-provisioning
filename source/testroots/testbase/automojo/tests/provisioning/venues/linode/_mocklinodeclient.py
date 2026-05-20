"""
    .. module:: _mocklinodeclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: MockLinodeClient — deterministic in-memory stand-in for the
               ``linode_api4`` client surface used by the Linode venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import itertools

from typing import Any, Dict, List, Optional


_ID_COUNTER = itertools.count(1000)


def _next_id() -> int:
    """
        Return the next deterministic synthetic resource id.

        :returns: An integer id.
    """
    rtnval = next(_ID_COUNTER)
    return rtnval


class MockResource:
    """
        Generic mock Linode SDK object with id/label/tags and a delete hook.
    """

    def __init__(self, *, store: List[Any], **fields: Any) -> None:
        """
            Construct a MockResource.

            :param store: The collection list this resource belongs to.
            :param fields: Arbitrary attribute key/values.
        """
        self._store: List[Any] = store
        self.id: int = _next_id()
        for key, value in fields.items():
            setattr(self, key, value)
        if not hasattr(self, "tags"):
            self.tags: List[str] = []
        return

    def delete(self) -> None:
        """
            Remove this resource from its backing collection.
        """
        if self in self._store:
            self._store.remove(self)
        return


class MockVPC(MockResource):
    """
        Mock VPC carrying a list of subnets.
    """

    def __init__(self, *, store: List[Any], **fields: Any) -> None:
        """
            Construct a MockVPC.

            :param store: Backing collection.
            :param fields: Attribute key/values.
        """
        super().__init__(store=store, **fields)
        if not hasattr(self, "subnets"):
            self.subnets: List[Any] = []
        return


class MockVolume(MockResource):
    """
        Mock Block Storage volume with detach support.
    """

    def detach(self) -> None:
        """
            Detach the volume from any attached instance.
        """
        self.linode_id = None
        return


class MockDomain(MockResource):
    """
        Mock DNS domain that can create child records.
    """

    def __init__(self, *, store: List[Any], **fields: Any) -> None:
        """
            Construct a MockDomain.

            :param store: Backing collection.
            :param fields: Attribute key/values.
        """
        super().__init__(store=store, **fields)
        if not hasattr(self, "records"):
            self.records: List[Any] = []
        return

    def record_create(self, *, record_type: str, name: str, target: str,
                      ttl_sec: int) -> "MockResource":
        """
            Create a DNS record under this domain.

            :param record_type: The DNS record type.
            :param name: The record name.
            :param target: The record target value.
            :param ttl_sec: The record TTL in seconds.

            :returns: A MockResource record.
        """
        record = MockResource(store=self.records, record_type=record_type,
                              name=name, target=target, ttl_sec=ttl_sec)
        self.records.append(record)
        rtnval = record
        return rtnval


class _ProfileNamespace:
    """
        Mock ``client.profile`` namespace exposing SSH-key operations.
    """

    def __init__(self, *, ssh_key_store: List[Any]) -> None:
        """
            Construct the profile namespace.

            :param ssh_key_store: The SSH key backing collection.
        """
        self._ssh_key_store: List[Any] = ssh_key_store
        return

    def ssh_keys(self) -> List[Any]:
        """
            Return all account SSH keys.

            :returns: The SSH key list.
        """
        rtnval = list(self._ssh_key_store)
        return rtnval

    def ssh_key_upload(self, *, key: str, label: str) -> MockResource:
        """
            Upload an SSH key to the account.

            :param key: The public key material.
            :param label: The key label.

            :returns: A MockResource SSH key.
        """
        resource = MockResource(store=self._ssh_key_store, ssh_key=key,
                                label=label)
        self._ssh_key_store.append(resource)
        rtnval = resource
        return rtnval


class _NetworkingNamespace:
    """
        Mock ``client.networking`` namespace exposing firewall listing.
    """

    def __init__(self, *, firewall_store: List[Any]) -> None:
        """
            Construct the networking namespace.

            :param firewall_store: The firewall backing collection.
        """
        self._firewall_store: List[Any] = firewall_store
        return

    def firewalls(self) -> List[Any]:
        """
            Return all Cloud Firewalls.

            :returns: The firewall list.
        """
        rtnval = list(self._firewall_store)
        return rtnval


class _LinodeNamespace:
    """
        Mock ``client.linode`` namespace exposing instance listing.
    """

    def __init__(self, *, instance_store: List[Any]) -> None:
        """
            Construct the linode namespace.

            :param instance_store: The instance backing collection.
        """
        self._instance_store: List[Any] = instance_store
        return

    def instances(self) -> List[Any]:
        """
            Return all Linode instances.

            :returns: The instance list.
        """
        rtnval = list(self._instance_store)
        return rtnval


class _ObjectStorageNamespace:
    """
        Mock ``client.object_storage`` namespace exposing bucket operations.
    """

    def __init__(self, *, bucket_store: List[Any]) -> None:
        """
            Construct the object-storage namespace.

            :param bucket_store: The bucket backing collection.
        """
        self._bucket_store: List[Any] = bucket_store
        return

    def buckets(self) -> List[Any]:
        """
            Return all Object Storage buckets.

            :returns: The bucket list.
        """
        rtnval = list(self._bucket_store)
        return rtnval

    def bucket_create(self, *, cluster: str, label: str) -> MockResource:
        """
            Create an Object Storage bucket.

            :param cluster: The object-storage cluster.
            :param label: The bucket label.

            :returns: A MockResource bucket.
        """
        resource = MockResource(store=self._bucket_store, cluster=cluster,
                                label=label)
        self._bucket_store.append(resource)
        rtnval = resource
        return rtnval


class MockLinodeClient:
    """
        Deterministic in-memory mock of the ``linode_api4.LinodeClient``.

        Mirrors only the surface the Linode venue uses: VPC, VPC subnet,
        firewall, SSH key, instance, volume, object-storage, and domain
        create / list calls.  No network I/O is performed.
    """

    def __init__(self) -> None:
        """
            Construct an empty MockLinodeClient.
        """
        self._vpcs: List[Any] = []
        self._firewalls: List[Any] = []
        self._instances: List[Any] = []
        self._volumes: List[Any] = []
        self._buckets: List[Any] = []
        self._domains: List[Any] = []
        self._ssh_keys: List[Any] = []

        self.profile: _ProfileNamespace = _ProfileNamespace(
            ssh_key_store=self._ssh_keys
        )
        self.networking: _NetworkingNamespace = _NetworkingNamespace(
            firewall_store=self._firewalls
        )
        self.linode: _LinodeNamespace = _LinodeNamespace(
            instance_store=self._instances
        )
        self.object_storage: _ObjectStorageNamespace = (
            _ObjectStorageNamespace(bucket_store=self._buckets)
        )
        return

    def vpcs(self) -> List[Any]:
        """
            Return all VPCs.

            :returns: The VPC list.
        """
        rtnval = list(self._vpcs)
        return rtnval

    def vpc_create(self, *, label: str, region: str,
                   tags: List[str]) -> MockVPC:
        """
            Create a VPC.

            :param label: The VPC label.
            :param region: The Linode region.
            :param tags: The VPC string tags.

            :returns: A MockVPC.
        """
        resource = MockVPC(store=self._vpcs, label=label, region=region,
                           tags=list(tags))
        self._vpcs.append(resource)
        rtnval = resource
        return rtnval

    def vpc_subnet_create(self, *, vpc: Any, label: str,
                          ipv4: str) -> MockResource:
        """
            Create a subnet within a VPC.

            :param vpc: The parent MockVPC.
            :param label: The subnet label.
            :param ipv4: The subnet CIDR.

            :returns: A MockResource subnet.
        """
        resource = MockResource(store=vpc.subnets, label=label, ipv4=ipv4)
        vpc.subnets.append(resource)
        rtnval = resource
        return rtnval

    def firewall_create(self, *, label: str, rules: Dict[str, Any],
                        tags: List[str]) -> MockResource:
        """
            Create a Cloud Firewall.

            :param label: The firewall label.
            :param rules: The firewall rules dict.
            :param tags: The firewall string tags.

            :returns: A MockResource firewall.
        """
        resource = MockResource(store=self._firewalls, label=label,
                                rules=rules, tags=list(tags))
        self._firewalls.append(resource)
        rtnval = resource
        return rtnval

    def instance_create(self, *, ltype: str, region: str, image: str,
                        label: str, tags: List[str],
                        authorized_keys: List[str],
                        metadata: Dict[str, Any],
                        firewall: Optional[int],
                        private_ip: bool) -> MockResource:
        """
            Create a Linode instance.

            :param ltype: The Linode type slug.
            :param region: The Linode region.
            :param image: The image id.
            :param label: The instance label.
            :param tags: The instance string tags.
            :param authorized_keys: SSH keys injected into the instance.
            :param metadata: The instance metadata dict (user_data).
            :param firewall: Optional firewall id.
            :param private_ip: Whether a private IP is attached.

            :returns: A MockResource instance.
        """
        resource = MockResource(
            store=self._instances, type=ltype, region=region, image=image,
            label=label, tags=list(tags),
            authorized_keys=list(authorized_keys),
            metadata=dict(metadata), firewall=firewall,
            private_ip=private_ip,
        )
        self._instances.append(resource)
        rtnval = resource
        return rtnval

    def volumes(self) -> List[Any]:
        """
            Return all Block Storage volumes.

            :returns: The volume list.
        """
        rtnval = list(self._volumes)
        return rtnval

    def volume_create(self, *, label: str, region: str, size: int,
                      tags: List[str],
                      linode: Optional[Any]) -> MockVolume:
        """
            Create a Block Storage volume.

            :param label: The volume label.
            :param region: The Linode region.
            :param size: The volume size in GB.
            :param tags: The volume string tags.
            :param linode: Optional instance to attach the volume to.

            :returns: A MockVolume.
        """
        attach_id = getattr(linode, "id", None) if linode is not None else None
        resource = MockVolume(store=self._volumes, label=label,
                              region=region, size=size, tags=list(tags),
                              linode_id=attach_id)
        self._volumes.append(resource)
        rtnval = resource
        return rtnval

    def domains(self) -> List[Any]:
        """
            Return all DNS domains.

            :returns: The domain list.
        """
        rtnval = list(self._domains)
        return rtnval

    def domain_create(self, *, domain: str, soa_email: str) -> MockDomain:
        """
            Create a DNS domain.

            :param domain: The zone name.
            :param soa_email: The SOA contact email.

            :returns: A MockDomain.
        """
        resource = MockDomain(store=self._domains, domain=domain,
                              soa_email=soa_email)
        self._domains.append(resource)
        rtnval = resource
        return rtnval
