"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building ProxmoxSpec instances for tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List, Optional

from automojo.credentials.proxmoxapitokencredential import (
    ProxmoxApiTokenCredential
)
from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
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

from automojo.provisioning.venues.proxmox.proxmoxspec import ProxmoxSpec
from automojo.provisioning.venues.proxmox.pveresolver import PveResolver


_PUBLIC_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILABTESTKEY00000000000000000 "
    "test@proxmox"
)

# The catalog key the default test image resolves to.
_IMAGE_KEY = "ubuntu/24.04/x86_64"

# The Proxmox template VMID the test catalog maps the image to.
TEMPLATE_VMID = 8000

# The node the test resolver places every VM on.
DEFAULT_NODE = "pve-node-1"


def make_credential() -> ProxmoxApiTokenCredential:
    """
        Build a ProxmoxApiTokenCredential acceptable to the provisioner.

        :returns: A ProxmoxApiTokenCredential instance.
    """
    rtnval = ProxmoxApiTokenCredential(
        identifier="pve-test", categories=["vm-venue"],
        token_id="automojo@pve!testtoken", secret="00000000-test-secret",
    )
    return rtnval


def make_resolver() -> PveResolver:
    """
        Build a PveResolver whose catalog resolves the test image.

        :returns: A PveResolver instance with a default node.
    """
    rtnval = PveResolver(template_catalog={_IMAGE_KEY: TEMPLATE_VMID},
                         default_node=DEFAULT_NODE,
                         default_storage="local-lvm")
    return rtnval


def make_image() -> CloudImage:
    """
        Build a CloudImage resolvable by the test resolver catalog.

        :returns: A CloudImage instance.
    """
    rtnval = CloudImage(family="ubuntu", version="24.04",
                        architecture="x86_64")
    return rtnval


def make_keypair() -> CloudKeyPair:
    """
        Build a CloudKeyPair for the Proxmox venue.

        :returns: A CloudKeyPair instance.
    """
    rtnval = CloudKeyPair(name="lab-key", public_key_material=_PUBLIC_KEY)
    return rtnval


def make_network(*, name: str = "vmbr-test") -> CloudNetwork:
    """
        Build a CloudNetwork for the Proxmox venue.

        :param name: The network (bridge) name.

        :returns: A CloudNetwork instance.
    """
    rtnval = CloudNetwork(name=name, cidr="10.30.0.0/24", region="local")
    return rtnval


def make_instance(*, name: str = "node", size: str = "medium",
                  with_vpn: bool = False,
                  tags: Optional[List[Dict[str, str]]] = None
                  ) -> CloudInstance:
    """
        Build a CloudInstance for the Proxmox venue.

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
                           subnet="vmbr-test", keypair="lab-key",
                           vpn_join=vpn_join, tags=tags,
                           placement_group=DEFAULT_NODE)
    return rtnval


def basic_spec(*, with_vpn: bool = False,
               tags: Optional[List[Dict[str, str]]] = None) -> ProxmoxSpec:
    """
        Build a baseline ProxmoxSpec: one network, keypair, instance.

        :param with_vpn: Whether the instance carries a VPNJoinSpec.
        :param tags: Optional neutral tag list on the instance.

        :returns: A ProxmoxSpec instance.
    """
    rtnval = ProxmoxSpec(networks=[make_network()],
                         keypairs=[make_keypair()],
                         instances=[make_instance(with_vpn=with_vpn,
                                                  tags=tags)])
    return rtnval


def volume_spec() -> ProxmoxSpec:
    """
        Build a ProxmoxSpec carrying a data volume bound to the instance.

        :returns: A ProxmoxSpec instance.
    """
    volume = CloudStorageVolume(name="data", size_gb=10, type="ssd",
                                attached_to="node")
    rtnval = ProxmoxSpec(networks=[make_network()],
                         keypairs=[make_keypair()],
                         instances=[make_instance()],
                         volumes=[volume])
    return rtnval


def bucket_lb_dns_spec() -> ProxmoxSpec:
    """
        Build a ProxmoxSpec containing every resource Proxmox rejects.

        :returns: A ProxmoxSpec instance.
    """
    bucket = CloudObjectBucket(name="data-bucket", region="local")
    lb = CloudLoadBalancer(name="api-lb", scheme="internet-facing")
    record = CloudDnsRecord(zone="example.com", name="api",
                            record_type="A", values=["203.0.113.1"],
                            ttl_seconds=300)
    rtnval = ProxmoxSpec(networks=[make_network()],
                         keypairs=[make_keypair()],
                         instances=[make_instance()],
                         buckets=[bucket], load_balancers=[lb],
                         dns_records=[record])
    return rtnval
