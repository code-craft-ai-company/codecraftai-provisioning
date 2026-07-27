"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers building HypervSpec instances for the venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, List, Optional

from ccai.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from ccai.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.interfaces.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.venues.hyperv.hypervspec import HypervSpec


_PUBLIC_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHYPERVTESTKEY0000000000000 "
    "test@hyperv"
)


def make_image(*, family: str = "ubuntu",
               version: str = "22.04") -> CloudImage:
    """
        Build a CloudImage for the Hyper-V venue tests.

        :param family: The image family.
        :param version: The image version.

        :returns: A CloudImage instance.
    """
    rtnval = CloudImage(family=family, version=version,
                        architecture="x86_64")
    return rtnval


def make_keypair() -> CloudKeyPair:
    """
        Build a CloudKeyPair for the Hyper-V venue tests.

        :returns: A CloudKeyPair instance.
    """
    rtnval = CloudKeyPair(name="hv-key", public_key_material=_PUBLIC_KEY)
    return rtnval


def make_vpn_join() -> VPNJoinSpec:
    """
        Build a Tailscale VPNJoinSpec for the Hyper-V venue tests.

        :returns: A VPNJoinSpec instance.
    """
    rtnval = VPNJoinSpec(provider="tailscale",
                         control_plane_credential="ts-cred",
                         hostname_template="hv-{name}",
                         advertise_tags=["tag:lab"])
    return rtnval


def make_instance(*, name: str = "vm-app", size: str = "medium",
                   subnet: str = "lab-net",
                   vpn_join: Optional[VPNJoinSpec] = None,
                   image_family: str = "ubuntu",
                   tags: Optional[List[Dict[str, str]]] = None
                   ) -> CloudInstance:
    """
        Build a CloudInstance for the Hyper-V venue tests.

        :param name: The instance name.
        :param size: The neutral size hint.
        :param subnet: The parent subnet / network name.
        :param vpn_join: Optional VPNJoinSpec.
        :param image_family: The image family.
        :param tags: Optional neutral tag list.

        :returns: A CloudInstance instance.
    """
    rtnval = CloudInstance(name=name, profile_ref="lab-profile",
                           image=make_image(family=image_family),
                           size=size, subnet=subnet, keypair="hv-key",
                           vpn_join=vpn_join, tags=tags)
    return rtnval


def make_network(*, name: str = "lab-net") -> CloudNetwork:
    """
        Build a CloudNetwork for the Hyper-V venue tests.

        :param name: The network name.

        :returns: A CloudNetwork instance.
    """
    rtnval = CloudNetwork(name=name, cidr="10.0.0.0/24", region="lab")
    return rtnval


def make_volume(*, name: str = "data-vol", size_gb: int = 50,
                attached_to: Optional[str] = None) -> CloudStorageVolume:
    """
        Build a CloudStorageVolume for the Hyper-V venue tests.

        :param name: The volume name.
        :param size_gb: The volume size in gigabytes.
        :param attached_to: Optional attaching instance name.

        :returns: A CloudStorageVolume instance.
    """
    rtnval = CloudStorageVolume(name=name, size_gb=size_gb, storage_class="standard",
                                attached_to=attached_to)
    return rtnval


def make_basic_spec(*, with_vpn: bool = False,
                     with_volume: bool = False) -> HypervSpec:
    """
        Build a small valid HypervSpec for happy-path tests.

        :param with_vpn: Whether the instance carries a VPNJoinSpec.
        :param with_volume: Whether a data volume is included.

        :returns: A HypervSpec instance.
    """
    vpn = make_vpn_join() if with_vpn is True else None
    instance = make_instance(vpn_join=vpn)

    volumes: List[CloudStorageVolume] = []
    if with_volume is True:
        volumes.append(make_volume(attached_to="vm-app"))

    rtnval = HypervSpec(networks=[make_network()],
                        keypairs=[make_keypair()],
                        instances=[instance], volumes=volumes)
    return rtnval


def make_bucket() -> CloudObjectBucket:
    """
        Build a CloudObjectBucket (an unsupported Hyper-V kind).

        :returns: A CloudObjectBucket instance.
    """
    rtnval = CloudObjectBucket(name="lab-bucket", region="lab")
    return rtnval


def make_load_balancer() -> CloudLoadBalancer:
    """
        Build a CloudLoadBalancer (an unsupported Hyper-V kind).

        :returns: A CloudLoadBalancer instance.
    """
    rtnval = CloudLoadBalancer(name="lab-lb", scheme="internal")
    return rtnval


def make_dns_record() -> CloudDnsRecord:
    """
        Build a CloudDnsRecord (a warn-only Hyper-V kind).

        :returns: A CloudDnsRecord instance.
    """
    rtnval = CloudDnsRecord(zone="lab.example.com", name="app",
                            record_type="A", values=["10.0.0.10"],
                            ttl_seconds=300)
    return rtnval
