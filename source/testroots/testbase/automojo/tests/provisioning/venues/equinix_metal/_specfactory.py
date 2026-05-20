"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers building MetalSpec instances for Equinix Metal tests.

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
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.cloudsubnet import CloudSubnet
from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from automojo.provisioning.venues.equinix_metal.metalspec import MetalSpec


_PUBLIC_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
    "2Tvpmdw6KmeqR2a9oJPvufL1YbpX/vRydyqt2NzbwlXhMeNMb29a22kdNRCK"
    "Zfza5VYaRkIFmKrfWu8b2akrytVsgGyPSUzlv0yo3RjKbYDCQuWuusyCYhWf"
    "test@host"
)


def basic_spec(*, with_vpn: bool = False,
               size: str = "c3.medium.x86",
               accelerators: Optional[List[CloudAcceleratorSpec]] = None,
               interconnect: Optional[CloudInterconnect] = None
               ) -> MetalSpec:
    """
        Build a baseline MetalSpec with one network + subnet + keypair +
        instance.

        :param with_vpn: When True the instance carries a VPNJoinSpec.
        :param size: Neutral size hint or Metal plan slug.
        :param accelerators: Optional accelerator list.
        :param interconnect: Optional CloudInterconnect.

        :returns: A MetalSpec.
    """
    network = CloudNetwork(name="net-a", cidr="10.0.0.0/16", region="sv")
    subnet = CloudSubnet(name="sub-a", network="net-a", cidr="10.0.1.0/24",
                         zone="sv", public=True)
    keypair = CloudKeyPair(name="kp-a", public_key_material=_PUBLIC_KEY)
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale", control_plane_credential="ts-cred",
            hostname_template="metal-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="dev-a", profile_ref="default", image=image, size=size,
        subnet="sub-a", keypair="kp-a", vpn_join=vpn_join,
        accelerators=accelerators, interconnect=interconnect,
        tags=[{"automojo:purpose": "test"}],
    )

    rtnval = MetalSpec(networks=[network], subnets=[subnet],
                       keypairs=[keypair], instances=[instance])
    return rtnval
