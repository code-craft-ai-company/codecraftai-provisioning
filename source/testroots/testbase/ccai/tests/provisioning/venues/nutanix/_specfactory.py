"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building NutanixSpec instances for tests.

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
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec

from ccai.provisioning.venues.nutanix.nutanixspec import NutanixSpec
from ccai.provisioning.venues.nutanix.nutanixvenueconfig import (
    NutanixVenueConfig
)


_PUBLIC_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILABTESTKEY00000000000000000 "
    "test@nutanix"
)


def make_config(*, objects_configured: bool = False) -> NutanixVenueConfig:
    """
        Build a NutanixVenueConfig pinned to a known cluster.

        :param objects_configured: Whether Nutanix Objects is configured.

        :returns: A NutanixVenueConfig instance.
    """
    rtnval = NutanixVenueConfig(cluster_name="homelab-cluster",
                                storage_container_uuid="sc-0001",
                                objects_configured=objects_configured)
    return rtnval


def make_image() -> CloudImage:
    """
        Build a CloudImage resolvable by the default Nutanix catalog.

        :returns: A CloudImage instance.
    """
    rtnval = CloudImage(family="ubuntu", version="24.04",
                        architecture="x86_64")
    return rtnval


def make_keypair() -> CloudKeyPair:
    """
        Build a CloudKeyPair for the Nutanix venue.

        :returns: A CloudKeyPair instance.
    """
    rtnval = CloudKeyPair(name="lab-key", public_key_material=_PUBLIC_KEY)
    return rtnval


def make_network(*, name: str = "vpcnet") -> CloudNetwork:
    """
        Build a CloudNetwork for the Nutanix venue.

        :param name: The network name.

        :returns: A CloudNetwork instance.
    """
    rtnval = CloudNetwork(name=name, cidr="10.20.0.0/16", region="homelab")
    return rtnval


def make_subnet(*, name: str = "appsubnet",
                network: str = "vpcnet") -> CloudSubnet:
    """
        Build a CloudSubnet for the Nutanix venue.

        :param name: The subnet name.
        :param network: The enclosing network name.

        :returns: A CloudSubnet instance.
    """
    rtnval = CloudSubnet(name=name, network=network, cidr="10.20.0.0/24",
                         zone="homelab-a")
    return rtnval


def make_instance(*, name: str = "node", size: str = "medium",
                  with_vpn: bool = False,
                  tags: Optional[List[Dict[str, str]]] = None
                  ) -> CloudInstance:
    """
        Build a CloudInstance for the Nutanix venue.

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
                           image=make_image(), size=size,
                           subnet="appsubnet", keypair="lab-key",
                           vpn_join=vpn_join, tags=tags)
    return rtnval


def basic_spec(*, with_vpn: bool = False,
               tags: Optional[List[Dict[str, str]]] = None) -> NutanixSpec:
    """
        Build a baseline NutanixSpec: one network, subnet, keypair, VM.

        :param with_vpn: Whether the instance carries a VPNJoinSpec.
        :param tags: Optional neutral tag list on the instance.

        :returns: A NutanixSpec instance.
    """
    rtnval = NutanixSpec(networks=[make_network()],
                         subnets=[make_subnet()],
                         keypairs=[make_keypair()],
                         instances=[make_instance(with_vpn=with_vpn,
                                                  tags=tags)])
    return rtnval


def resized_spec(*, size: str = "large") -> NutanixSpec:
    """
        Build a NutanixSpec whose single VM carries a different size
        token — used to provoke vCPU / memory drift against an
        already-applied baseline_spec.

        :param size: The neutral size token for the VM.

        :returns: A NutanixSpec instance.
    """
    rtnval = NutanixSpec(networks=[make_network()],
                         subnets=[make_subnet()],
                         keypairs=[make_keypair()],
                         instances=[make_instance(size=size)])
    return rtnval


def volume_spec() -> NutanixSpec:
    """
        Build a NutanixSpec carrying a data volume.

        :returns: A NutanixSpec instance.
    """
    volume = CloudStorageVolume(name="data", size_gb=10, storage_class="standard")
    rtnval = NutanixSpec(networks=[make_network()],
                         subnets=[make_subnet()],
                         keypairs=[make_keypair()],
                         instances=[make_instance()],
                         volumes=[volume])
    return rtnval


def bucket_lb_dns_spec() -> NutanixSpec:
    """
        Build a NutanixSpec containing every resource Nutanix rejects.

        :returns: A NutanixSpec instance.
    """
    bucket = CloudObjectBucket(name="data-bucket", region="homelab")
    lb = CloudLoadBalancer(name="api-lb", scheme="internet-facing")
    record = CloudDnsRecord(zone="example.com", name="api",
                            record_type="A", values=["203.0.113.1"],
                            ttl_seconds=300)
    rtnval = NutanixSpec(networks=[make_network()],
                         subnets=[make_subnet()],
                         keypairs=[make_keypair()],
                         instances=[make_instance()],
                         buckets=[bucket], load_balancers=[lb],
                         dns_records=[record])
    return rtnval
