"""
    .. module:: _ocifakes
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: In-memory fake ``oci`` SDK clients for the Oracle venue tests.

    There is no moto equivalent for OCI, so the venue tests drive the
    provisioner against hand-written in-memory fakes that mimic the subset of
    the ``oci`` SDK call surface the venue uses.  Each fake returns objects
    carrying a ``.data`` attribute, exactly like the real SDK.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import itertools

from types import SimpleNamespace
from typing import Any, Dict, List

from ccai.restclient.oracle.ocierror import ServiceError


_OCID_COUNTER = itertools.count(1)


def _ocid(*, kind: str) -> str:
    """
        Mint a deterministic-but-unique fake OCID.

        :param kind: A short resource-kind tag embedded in the OCID.

        :returns: A fake OCID string.
    """
    rtnval = "ocid1.{}.oc1..{:08d}".format(kind, next(_OCID_COUNTER))
    return rtnval


class _Response:
    """
        Minimal stand-in for an ``oci`` SDK response.

        Carries ``next_page`` as well as ``data`` because the venue lists
        through the REAL ``oci.pagination.list_call_get_all_results``, handing
        it these fakes as the list function.  That paginator reads
        ``next_page`` to decide whether to keep going, so a response without
        it fails there rather than in any code this repo owns.

        ``None`` means "this is the last page", which is what a single-page
        fake should say.
    """

    def __init__(self, *, data: Any, next_page: Any = None,
                 status: int = 200) -> None:
        """
            Construct a fake response.

            The attribute set matches ``oci.response.Response`` exactly —
            status, headers, data, request, next_page, request_id, with
            has_next_page as a property — because the real paginator reads
            several of them and adding one at a time as each blew up would
            just be guessing at the contract.

            :param data: The payload exposed as ``.data``.
            :param next_page: The opaque next-page token, or None when the
                listing is complete.
            :param status: The HTTP status.
        """
        self.status = status
        self.headers: Dict[str, Any] = {}
        self.data = data
        self.request: Any = None
        self.next_page = next_page
        self.request_id = ""
        return

    @property
    def has_next_page(self) -> bool:
        """
            Report whether another page follows.

            :returns: True when a next-page token is present.
        """
        rtnval = self.next_page is not None
        return rtnval


class FakeVirtualNetworkClient:
    """
        In-memory fake of ``oci.core.VirtualNetworkClient``.
    """

    def __init__(self) -> None:
        """
            Construct an empty fake VirtualNetworkClient.
        """
        self.vcns: List[Any] = []
        self.subnets: List[Any] = []
        self.security_lists: List[Any] = []
        self.internet_gateways: List[Any] = []
        self.route_tables: List[Any] = []
        return

    def list_vcns(self, *, compartment_id: str, **kwargs: Any) -> _Response:
        """List VCNs in the compartment."""
        rtnval = _Response(data=list(self.vcns))
        return rtnval

    def create_vcn(self, *, create_vcn_details: Any) -> _Response:
        """Create a VCN."""
        vcn = SimpleNamespace(
            id=_ocid(kind="vcn"),
            cidr_block=create_vcn_details.cidr_block,
            display_name=create_vcn_details.display_name,
            freeform_tags=dict(create_vcn_details.freeform_tags or {}),
        )
        self.vcns.append(vcn)
        rtnval = _Response(data=vcn)
        return rtnval

    def delete_vcn(self, *, vcn_id: str) -> _Response:
        """Delete a VCN."""
        self.vcns = [v for v in self.vcns if v.id != vcn_id]
        rtnval = _Response(data=None)
        return rtnval

    def list_subnets(self, *, compartment_id: str, **kwargs: Any
                     ) -> _Response:
        """List subnets in the compartment."""
        rtnval = _Response(data=list(self.subnets))
        return rtnval

    def create_subnet(self, *, create_subnet_details: Any) -> _Response:
        """Create a subnet."""
        details = create_subnet_details
        subnet = SimpleNamespace(
            id=_ocid(kind="subnet"),
            vcn_id=details.vcn_id,
            cidr_block=details.cidr_block,
            availability_domain=getattr(details, "availability_domain",
                                        None),
            display_name=details.display_name,
            freeform_tags=dict(details.freeform_tags or {}),
        )
        self.subnets.append(subnet)
        rtnval = _Response(data=subnet)
        return rtnval

    def delete_subnet(self, *, subnet_id: str) -> _Response:
        """Delete a subnet."""
        self.subnets = [s for s in self.subnets if s.id != subnet_id]
        rtnval = _Response(data=None)
        return rtnval

    def list_security_lists(self, *, compartment_id: str, **kwargs: Any
                            ) -> _Response:
        """List security lists in the compartment."""
        rtnval = _Response(data=list(self.security_lists))
        return rtnval

    def create_security_list(self, *, create_security_list_details: Any
                             ) -> _Response:
        """Create a security list."""
        details = create_security_list_details
        seclist = SimpleNamespace(
            id=_ocid(kind="securitylist"),
            vcn_id=details.vcn_id,
            ingress_security_rules=list(details.ingress_security_rules),
            egress_security_rules=list(details.egress_security_rules),
            display_name=details.display_name,
            freeform_tags=dict(details.freeform_tags or {}),
        )
        self.security_lists.append(seclist)
        rtnval = _Response(data=seclist)
        return rtnval

    def delete_security_list(self, *, security_list_id: str) -> _Response:
        """Delete a security list."""
        self.security_lists = [s for s in self.security_lists
                               if s.id != security_list_id]
        rtnval = _Response(data=None)
        return rtnval

    def list_internet_gateways(self, *, compartment_id: str, **kwargs: Any
                               ) -> _Response:
        """List internet gateways in the compartment."""
        vcn_id = kwargs.get("vcn_id", None)
        if vcn_id is not None:
            data = [g for g in self.internet_gateways if g.vcn_id == vcn_id]
        else:
            data = list(self.internet_gateways)
        rtnval = _Response(data=data)
        return rtnval

    def create_internet_gateway(self, *, create_internet_gateway_details: Any
                                ) -> _Response:
        """Create an internet gateway."""
        details = create_internet_gateway_details
        igw = SimpleNamespace(
            id=_ocid(kind="internetgateway"),
            vcn_id=details.vcn_id,
            display_name=details.display_name,
            freeform_tags=dict(details.freeform_tags or {}),
        )
        self.internet_gateways.append(igw)
        rtnval = _Response(data=igw)
        return rtnval

    def delete_internet_gateway(self, *, ig_id: str) -> _Response:
        """Delete an internet gateway."""
        self.internet_gateways = [g for g in self.internet_gateways
                                  if g.id != ig_id]
        rtnval = _Response(data=None)
        return rtnval

    def list_route_tables(self, *, compartment_id: str, **kwargs: Any
                          ) -> _Response:
        """List route tables in the compartment."""
        vcn_id = kwargs.get("vcn_id", None)
        if vcn_id is not None:
            data = [t for t in self.route_tables if t.vcn_id == vcn_id]
        else:
            data = list(self.route_tables)
        rtnval = _Response(data=data)
        return rtnval

    def create_route_table(self, *, create_route_table_details: Any
                           ) -> _Response:
        """Create a route table."""
        details = create_route_table_details
        table = SimpleNamespace(
            id=_ocid(kind="routetable"),
            vcn_id=details.vcn_id,
            display_name=details.display_name,
            freeform_tags=dict(details.freeform_tags or {}),
        )
        self.route_tables.append(table)
        rtnval = _Response(data=table)
        return rtnval

    def delete_route_table(self, *, rt_id: str) -> _Response:
        """Delete a route table."""
        self.route_tables = [t for t in self.route_tables if t.id != rt_id]
        rtnval = _Response(data=None)
        return rtnval


class FakeComputeClient:
    """
        In-memory fake of ``oci.core.ComputeClient``.
    """

    def __init__(self, *, images: List[Any] = None) -> None:
        """
            Construct a fake ComputeClient.

            :param images: Optional pre-seeded image list.
        """
        self.instances: List[Any] = []
        self.volume_attachments: List[Any] = []
        if images is not None:
            self.images: List[Any] = list(images)
        else:
            self.images = [SimpleNamespace(
                id=_ocid(kind="image"),
                display_name="Canonical-Ubuntu-22.04",
            )]
        return

    def list_images(self, *, compartment_id: str, **kwargs: Any
                    ) -> _Response:
        """List images in the compartment."""
        rtnval = _Response(data=list(self.images))
        return rtnval

    def list_instances(self, *, compartment_id: str, **kwargs: Any
                       ) -> _Response:
        """List compute instances in the compartment."""
        rtnval = _Response(data=list(self.instances))
        return rtnval

    def launch_instance(self, *, launch_instance_details: Any) -> _Response:
        """Launch a compute instance."""
        details = launch_instance_details
        instance = SimpleNamespace(
            id=_ocid(kind="instance"),
            shape=details.shape,
            lifecycle_state="RUNNING",
            availability_domain=details.availability_domain,
            display_name=details.display_name,
            metadata=dict(getattr(details, "metadata", None) or {}),
            freeform_tags=dict(details.freeform_tags or {}),
            compute_cluster_id=getattr(details, "compute_cluster_id", None),
            preemptible_instance_config=getattr(
                details, "preemptible_instance_config", None
            ),
        )
        self.instances.append(instance)
        rtnval = _Response(data=instance)
        return rtnval

    def terminate_instance(self, *, instance_id: str) -> _Response:
        """Terminate a compute instance."""
        for instance in self.instances:
            if instance.id == instance_id:
                instance.lifecycle_state = "TERMINATED"
        rtnval = _Response(data=None)
        return rtnval

    def attach_volume(self, *, attach_volume_details: Any) -> _Response:
        """
            Attach a block volume to an instance.

            Answers the way OCI does for a volume that already has a live
            attachment: HTTP 409, whichever instance holds it.
        """
        volume_id = attach_volume_details.volume_id
        for attachment in self.volume_attachments:
            if attachment.volume_id != volume_id:
                continue
            if attachment.lifecycle_state in ("ATTACHING", "ATTACHED"):
                raise ServiceError(
                    "The OCI request failed. STATUS: 409 CODE: Conflict",
                    status=409, code="Conflict",
                    message="Volume {} is already attached.".format(
                        volume_id))

        attachment = SimpleNamespace(
            id=_ocid(kind="volumeattachment"),
            instance_id=attach_volume_details.instance_id,
            volume_id=volume_id,
            lifecycle_state="ATTACHED",
        )
        self.volume_attachments.append(attachment)
        rtnval = _Response(data=attachment)
        return rtnval

    def list_volume_attachments(self, *, compartment_id: str,
                                **kwargs: Any) -> _Response:
        """List volume attachments, narrowed by instance_id / volume_id."""
        instance_id = kwargs.get("instance_id", None)
        volume_id = kwargs.get("volume_id", None)
        data: List[Any] = []
        for attachment in self.volume_attachments:
            if instance_id is not None and attachment.instance_id != instance_id:
                continue
            if volume_id is not None and attachment.volume_id != volume_id:
                continue
            data.append(attachment)
        rtnval = _Response(data=data)
        return rtnval


class FakeBlockstorageClient:
    """
        In-memory fake of ``oci.core.BlockstorageClient``.
    """

    def __init__(self) -> None:
        """
            Construct an empty fake BlockstorageClient.
        """
        self.volumes: List[Any] = []
        return

    def list_volumes(self, *, compartment_id: str, **kwargs: Any
                     ) -> _Response:
        """List block volumes in the compartment."""
        rtnval = _Response(data=list(self.volumes))
        return rtnval

    def create_volume(self, *, create_volume_details: Any) -> _Response:
        """Create a block volume."""
        details = create_volume_details
        volume = SimpleNamespace(
            id=_ocid(kind="volume"),
            size_in_gbs=details.size_in_gbs,
            availability_domain=details.availability_domain,
            display_name=details.display_name,
            freeform_tags=dict(details.freeform_tags or {}),
        )
        self.volumes.append(volume)
        rtnval = _Response(data=volume)
        return rtnval

    def delete_volume(self, *, volume_id: str) -> _Response:
        """Delete a block volume."""
        self.volumes = [v for v in self.volumes if v.id != volume_id]
        rtnval = _Response(data=None)
        return rtnval


class FakeObjectStorageClient:
    """
        In-memory fake of ``oci.object_storage.ObjectStorageClient``.
    """

    def __init__(self) -> None:
        """
            Construct an empty fake ObjectStorageClient.
        """
        self.buckets: Dict[str, Any] = {}
        return

    def get_namespace(self) -> _Response:
        """Return the tenancy namespace."""
        rtnval = _Response(data="ccainamespace")
        return rtnval

    def get_bucket(self, *, namespace_name: str, bucket_name: str
                   ) -> _Response:
        """Get a bucket by name (raises when absent)."""
        if bucket_name not in self.buckets:
            raise KeyError("bucket not found: {}".format(bucket_name))
        rtnval = _Response(data=self.buckets[bucket_name])
        return rtnval

    def create_bucket(self, *, namespace_name: str,
                      create_bucket_details: Any) -> _Response:
        """Create a bucket."""
        details = create_bucket_details
        bucket = SimpleNamespace(
            name=details.name,
            compartment_id=details.compartment_id,
            freeform_tags=dict(details.freeform_tags or {}),
        )
        self.buckets[details.name] = bucket
        rtnval = _Response(data=bucket)
        return rtnval

    def list_buckets(self, *, namespace_name: str, compartment_id: str,
                     **kwargs: Any) -> _Response:
        """List buckets in the compartment."""
        rtnval = _Response(data=list(self.buckets.values()))
        return rtnval

    def delete_bucket(self, *, namespace_name: str, bucket_name: str
                      ) -> _Response:
        """Delete a bucket."""
        self.buckets.pop(bucket_name, None)
        rtnval = _Response(data=None)
        return rtnval


class FakeDnsClient:
    """
        In-memory fake of ``oci.dns.DnsClient``.
    """

    def __init__(self, *, zones: List[str] = None) -> None:
        """
            Construct a fake DnsClient.

            :param zones: Optional pre-seeded zone names.
        """
        zone_names = zones if zones is not None else ["example.com"]
        self.zones: List[Any] = [
            SimpleNamespace(name=n) for n in zone_names
        ]
        self.rrsets: Dict[str, Any] = {}
        return

    def list_zones(self, *, compartment_id: str, **kwargs: Any
                   ) -> _Response:
        """List DNS zones in the compartment."""
        rtnval = _Response(data=list(self.zones))
        return rtnval

    def update_rr_set(self, *, zone_name_or_id: str, domain: str,
                      rtype: str, update_rr_set_details: Any) -> _Response:
        """Upsert a DNS RRSet."""
        key = "{}#{}#{}".format(zone_name_or_id, domain, rtype)
        self.rrsets[key] = update_rr_set_details
        rtnval = _Response(data=update_rr_set_details)
        return rtnval

    def delete_rr_set(self, *, zone_name_or_id: str, domain: str,
                      rtype: str) -> _Response:
        """Delete a DNS RRSet."""
        key = "{}#{}#{}".format(zone_name_or_id, domain, rtype)
        self.rrsets.pop(key, None)
        rtnval = _Response(data=None)
        return rtnval


class FakeComputeManagementClient:
    """
        In-memory fake of ``oci.core.ComputeManagementClient``.
    """

    def __init__(self) -> None:
        """
            Construct an empty fake ComputeManagementClient.
        """
        self.cluster_networks: List[Any] = []
        self.instance_configurations: List[Any] = []
        return

    def list_cluster_networks(self, *, compartment_id: str, **kwargs: Any
                              ) -> _Response:
        """List cluster networks in the compartment."""
        rtnval = _Response(data=list(self.cluster_networks))
        return rtnval

    def create_instance_configuration(self, *,
                                      create_instance_configuration: Any
                                      ) -> _Response:
        """Create an instance configuration."""
        config = SimpleNamespace(
            id=_ocid(kind="instanceconfiguration"),
            display_name=create_instance_configuration.display_name,
            freeform_tags=dict(
                getattr(create_instance_configuration, "freeform_tags",
                        None) or {}
            ),
        )
        self.instance_configurations.append(config)
        rtnval = _Response(data=config)
        return rtnval

    def create_cluster_network(self, *, create_cluster_network_details: Any
                               ) -> _Response:
        """Create a cluster network."""
        details = create_cluster_network_details
        cluster = SimpleNamespace(
            id=_ocid(kind="clusternetwork"),
            display_name=details.display_name,
            freeform_tags=dict(details.freeform_tags or {}),
            instance_pools=list(details.instance_pools),
        )
        self.cluster_networks.append(cluster)
        rtnval = _Response(data=cluster)
        return rtnval

    def terminate_cluster_network(self, *, cluster_network_id: str
                                  ) -> _Response:
        """Terminate a cluster network."""
        self.cluster_networks = [c for c in self.cluster_networks
                                 if c.id != cluster_network_id]
        rtnval = _Response(data=None)
        return rtnval


class FakeFileStorageClient:
    """
        In-memory fake of ``oci.file_storage.FileStorageClient``.
    """

    def __init__(self) -> None:
        """
            Construct an empty fake FileStorageClient.
        """
        self.file_systems: Dict[str, Any] = {}
        return

    def get_file_system(self, *, file_system_id: str) -> _Response:
        """Get a file system by OCID."""
        if file_system_id not in self.file_systems:
            data = SimpleNamespace(id=file_system_id,
                                   display_name="managed-lustre")
        else:
            data = self.file_systems[file_system_id]
        rtnval = _Response(data=data)
        return rtnval


def install_fakes(*, provisioner: Any) -> Dict[str, Any]:
    """
        Register a complete set of fake ``oci`` clients on a provisioner.

        :param provisioner: An OracleCloudProvisioner instance.

        :returns: A dict mapping service name to the installed fake client.
    """
    factory = provisioner._session_factory
    fakes: Dict[str, Any] = {}
    fakes["virtual_network"] = FakeVirtualNetworkClient()
    fakes["compute"] = FakeComputeClient()
    fakes["compute_management"] = FakeComputeManagementClient()
    fakes["blockstorage"] = FakeBlockstorageClient()
    fakes["object_storage"] = FakeObjectStorageClient()
    fakes["dns"] = FakeDnsClient()
    fakes["file_storage"] = FakeFileStorageClient()
    for service_name, client in fakes.items():
        factory.register_client(service_name=service_name, client=client)
    rtnval = fakes
    return rtnval
