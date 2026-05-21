"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers building CrusoeSpec instances for the venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import List, Optional

from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudingressrule import CloudIngressRule
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from automojo.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from automojo.provisioning.model.cloud.cloudsubnet import CloudSubnet
from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec

from automojo.provisioning.venues.crusoe.crusoespec import CrusoeSpec


def basic_spec(*, with_vpn: bool = False,
               accelerators: Optional[List[CloudAcceleratorSpec]] = None,
               interconnect: Optional[CloudInterconnect] = None,
               instance_size: str = "c1.small") -> CrusoeSpec:
    """
        Build a baseline CrusoeSpec with one VPC + subnet + SG + keypair +
        instance + volume.

        :param with_vpn: When True the instance carries a Tailscale VPN join.
        :param accelerators: Optional accelerator list for the instance.
        :param interconnect: Optional interconnect for the instance.
        :param instance_size: The instance size hint.

        :returns: A CrusoeSpec.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16",
                           region="us-east1")
    subnet = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                         zone="us-east1-a", public=True)
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    sg = CloudSecurityGroup(name="sg-a", network="vpc-a",
                            ingress_rules=[rule])
    keypair = CloudKeyPair(name="kp-a",
                           public_key_material="ssh-ed25519 AAAA test")
    image = CloudImage(family="ubuntu", version="22.04", architecture="x86_64")

    vpn_join = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(provider="tailscale",
                               control_plane_credential="ts-cred",
                               hostname_template="{name}",
                               advertise_tags=["tag:test"])

    instance = CloudInstance(name="node-0", profile_ref="gpu",
                             image=image, size=instance_size, subnet="sub-a",
                             security_groups=["sg-a"], keypair="kp-a",
                             accelerators=accelerators,
                             interconnect=interconnect,
                             vpn_join=vpn_join)

    volume = CloudStorageVolume(name="vol-0", size_gb=100, storage_class="standard",
                                attached_to="node-0")

    rtnval = CrusoeSpec(networks=[network], subnets=[subnet],
                        security_groups=[sg], keypairs=[keypair],
                        instances=[instance], volumes=[volume])
    return rtnval
