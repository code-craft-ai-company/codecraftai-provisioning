"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building LibvirtSpec instances for tests.

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

from ccai.provisioning.venues.libvirt.libvirtspec import LibvirtSpec
from ccai.provisioning.venues.libvirt.libvirtvenueconfig import (
    LibvirtVenueConfig
)


_PUBLIC_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILABTESTKEY00000000000000000 "
    "test@libvirt"
)

BASE_IMAGE_VOLUME = "ubuntu-24.04-server-cloudimg-amd64.img"


def make_config() -> LibvirtVenueConfig:
    """
        Build a LibvirtVenueConfig pointing at a test session URI.

        :returns: A LibvirtVenueConfig instance.
    """
    rtnval = LibvirtVenueConfig(connection_uri="test:///default",
                                base_image_pool="images",
                                boot_disk_pool="vmstore",
                                cloudinit_pool="cidata")
    return rtnval


def make_image() -> CloudImage:
    """
        Build a CloudImage resolvable by the default libvirt catalog.

        :returns: A CloudImage instance.
    """
    rtnval = CloudImage(family="ubuntu", version="24.04",
                        architecture="x86_64")
    return rtnval


def make_keypair() -> CloudKeyPair:
    """
        Build a CloudKeyPair for the libvirt venue.

        :returns: A CloudKeyPair instance.
    """
    rtnval = CloudKeyPair(name="lab-key", public_key_material=_PUBLIC_KEY)
    return rtnval


def make_network(*, name: str = "vmnet") -> CloudNetwork:
    """
        Build a CloudNetwork for the libvirt venue.

        :param name: The network name.

        :returns: A CloudNetwork instance.
    """
    rtnval = CloudNetwork(name=name, cidr="10.20.0.0/24", region="local")
    return rtnval


def make_instance(*, name: str = "node", size: str = "medium",
                  with_vpn: bool = False,
                  tags: Optional[List[Dict[str, str]]] = None
                  ) -> CloudInstance:
    """
        Build a CloudInstance for the libvirt venue.

        :param name: The instance name.
        :param size: The neutral size token.
        :param with_vpn: Whether to attach a Tailscale VPNJoinSpec.
        :param tags: Optional neutral tag list.

        :returns: A CloudInstance instance.
    """
    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(provider="tailscale",
                               control_plane_credential="ts-cred",
                               hostname_template="{name}",
                               advertise_tags=["tag:lab"])

    rtnval = CloudInstance(name=name, profile_ref="vm-profile",
                           image=make_image(), size=size, subnet="vmnet",
                           keypair="lab-key", vpn_join=vpn_join, tags=tags)
    return rtnval


def basic_spec(*, with_vpn: bool = False,
               tags: Optional[List[Dict[str, str]]] = None) -> LibvirtSpec:
    """
        Build a baseline LibvirtSpec: one network, keypair, instance.

        :param with_vpn: Whether the instance carries a VPNJoinSpec.
        :param tags: Optional neutral tag list on the instance.

        :returns: A LibvirtSpec instance.
    """
    rtnval = LibvirtSpec(networks=[make_network()],
                         keypairs=[make_keypair()],
                         instances=[make_instance(with_vpn=with_vpn,
                                                  tags=tags)])
    return rtnval


def resized_spec(*, size: str = "large") -> LibvirtSpec:
    """
        Build a LibvirtSpec whose single domain carries a different size
        token — used to provoke vCPU / memory drift against an
        already-applied basic_spec.

        :param size: The neutral size token for the domain.

        :returns: A LibvirtSpec instance.
    """
    rtnval = LibvirtSpec(networks=[make_network()],
                         keypairs=[make_keypair()],
                         instances=[make_instance(size=size)])
    return rtnval


def volume_spec() -> LibvirtSpec:
    """
        Build a LibvirtSpec carrying a data volume.

        :returns: A LibvirtSpec instance.
    """
    volume = CloudStorageVolume(name="data", size_gb=10, storage_class="standard")
    rtnval = LibvirtSpec(networks=[make_network()],
                         keypairs=[make_keypair()],
                         instances=[make_instance()],
                         volumes=[volume])
    return rtnval


def bucket_lb_dns_spec() -> LibvirtSpec:
    """
        Build a LibvirtSpec containing every resource libvirt rejects.

        :returns: A LibvirtSpec instance.
    """
    bucket = CloudObjectBucket(name="data-bucket", region="local")
    lb = CloudLoadBalancer(name="api-lb", scheme="internet-facing")
    record = CloudDnsRecord(zone="example.com", name="api",
                            record_type="A", values=["203.0.113.1"],
                            ttl_seconds=300)
    rtnval = LibvirtSpec(networks=[make_network()],
                         keypairs=[make_keypair()],
                         instances=[make_instance()],
                         buckets=[bucket], load_balancers=[lb],
                         dns_records=[record])
    return rtnval
