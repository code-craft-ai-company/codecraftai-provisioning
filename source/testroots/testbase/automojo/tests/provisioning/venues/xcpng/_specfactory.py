"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building XcpngSpec instances for tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List, Optional

from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from automojo.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from automojo.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from automojo.provisioning.venues.xcpng.xcpngspec import XcpngSpec


def make_image() -> CloudImage:
    """
        Build a CloudImage that resolves to the seeded Ubuntu Template.

        :returns: A CloudImage instance.
    """
    rtnval = CloudImage(family="ubuntu", version="22.04",
                        architecture="x86_64")
    return rtnval


def make_instance(*, name: str = "worker", network: str = "lab-net",
                  size: str = "medium", with_vpn: bool = False,
                  interconnect: Optional[CloudInterconnect] = None,
                  tags: Optional[List[Dict[str, str]]] = None
                  ) -> CloudInstance:
    """
        Build a CloudInstance for the XCP-ng venue.

        The XCP-ng venue treats the instance ``subnet`` field as the target
        network name_label.

        :param name: The instance name.
        :param network: The XAPI network name_label (carried in ``subnet``).
        :param size: The neutral size slug.
        :param with_vpn: Whether to attach a Tailscale VPNJoinSpec.
        :param interconnect: Optional interconnect (a non-NONE kind is a
                             validate-error).
        :param tags: Optional neutral tag list.

        :returns: A CloudInstance instance.
    """
    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(provider="tailscale",
                               control_plane_credential="ts-cred",
                               hostname_template="{name}",
                               advertise_tags=["tag:lab"])

    rtnval = CloudInstance(name=name, profile_ref="xcpng-profile",
                           image=make_image(), size=size, subnet=network,
                           vpn_join=vpn_join, interconnect=interconnect,
                           tags=tags)
    return rtnval


def make_network(*, name: str = "lab-net") -> CloudNetwork:
    """
        Build a CloudNetwork for the XCP-ng venue.

        :param name: The network name.

        :returns: A CloudNetwork instance.
    """
    rtnval = CloudNetwork(name=name, cidr="10.20.0.0/16", region="homelab")
    return rtnval


def make_volume(*, name: str = "data", size_gb: int = 50,
                attached_to: str = "worker") -> CloudStorageVolume:
    """
        Build a CloudStorageVolume for the XCP-ng venue.

        :param name: The volume name.
        :param size_gb: The volume size in gigabytes.
        :param attached_to: The instance the volume attaches to.

        :returns: A CloudStorageVolume instance.
    """
    rtnval = CloudStorageVolume(name=name, size_gb=size_gb, storage_class="standard",
                                attached_to=attached_to)
    return rtnval


def basic_spec(*, with_vpn: bool = False, with_volume: bool = False,
               tags: Optional[List[Dict[str, str]]] = None) -> XcpngSpec:
    """
        Build a baseline XcpngSpec with one network and one instance.

        :param with_vpn: Whether the instance carries a VPNJoinSpec.
        :param with_volume: Whether to attach one CloudStorageVolume.
        :param tags: Optional neutral tag list on the instance.

        :returns: An XcpngSpec instance.
    """
    volumes: List[CloudStorageVolume] = []
    if with_volume is True:
        volumes = [make_volume()]

    rtnval = XcpngSpec(
        networks=[make_network()],
        instances=[make_instance(with_vpn=with_vpn, tags=tags)],
        volumes=volumes)
    return rtnval


def resized_spec(*, size: str = "large") -> XcpngSpec:
    """
        Build an XcpngSpec whose single VM carries a different size slug
        — used to provoke vCPU / memory drift against an already-applied
        basic_spec.

        :param size: The neutral size slug for the VM.

        :returns: An XcpngSpec instance.
    """
    rtnval = XcpngSpec(networks=[make_network()],
                       instances=[make_instance(size=size)])
    return rtnval


def bucket_lb_spec() -> XcpngSpec:
    """
        Build an XcpngSpec containing an object bucket and a load balancer
        — the resource kinds XCP-ng rejects at validate.

        :returns: An XcpngSpec instance.
    """
    bucket = CloudObjectBucket(name="data-bucket", region="homelab")
    lb = CloudLoadBalancer(name="api-lb", scheme="internet-facing")
    rtnval = XcpngSpec(instances=[make_instance()],
                       networks=[make_network()],
                       buckets=[bucket], load_balancers=[lb])
    return rtnval


def dns_record_spec() -> XcpngSpec:
    """
        Build an XcpngSpec containing a DNS record — a validate-warning.

        :returns: An XcpngSpec instance.
    """
    record = CloudDnsRecord(zone="example.com", name="api", record_type="A",
                            values=["203.0.113.1"], ttl_seconds=300)
    rtnval = XcpngSpec(instances=[make_instance()],
                       networks=[make_network()], dns_records=[record])
    return rtnval


def interconnect_spec(*, kind: str = "INFINIBAND_NDR") -> XcpngSpec:
    """
        Build an XcpngSpec whose instance requests an HPC interconnect —
        a validate-error on XCP-ng.

        :param kind: The CloudInterconnect kind to request.

        :returns: An XcpngSpec instance.
    """
    interconnect = CloudInterconnect(kind=kind,
                                     bandwidth_gbps=400,
                                     topology="RAIL_OPTIMIZED")
    instance = make_instance(name="hpc-node", interconnect=interconnect)
    rtnval = XcpngSpec(instances=[instance], networks=[make_network()])
    return rtnval
