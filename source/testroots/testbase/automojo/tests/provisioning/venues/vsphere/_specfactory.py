"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers building VSphereSpec instances for venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Optional

from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.venues.vsphere.vspherespec import VSphereSpec


_PUBLIC_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITESTKEYMATERIALabcdef ccai"
)


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "small",
               image_family: str = "ubuntu",
               with_volume: bool = True) -> VSphereSpec:
    """
        Build a baseline VSphereSpec: one network + subnet + keypair +
        instance, plus an optional attached volume.

        :param with_vpn: When True the instance carries a VPNJoinSpec.
        :param instance_size: The neutral size hint for the instance.
        :param image_family: The image family for the instance.
        :param with_volume: When True an attached CloudStorageVolume is added.

        :returns: A VSphereSpec.
    """
    network = CloudNetwork(name="dvs-a", cidr="10.20.0.0/16",
                           region="homelab")
    subnet = CloudSubnet(name="pg-a", network="dvs-a", cidr="10.20.1.0/24",
                         zone="homelab-a")
    keypair = CloudKeyPair(name="kp-a", public_key_material=_PUBLIC_KEY)
    image = CloudImage(family=image_family, version="22.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn:
        vpn_join = VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-oauth",
            hostname_template="vm-{instance_name}",
            advertise_tags=["tag:lab"],
        )

    instance = CloudInstance(
        name="inst-a", profile_ref="prof-a", image=image,
        size=instance_size, subnet="pg-a", keypair="kp-a",
        vpn_join=vpn_join,
    )

    volumes = []
    if with_volume:
        volumes.append(CloudStorageVolume(
            name="vol-a", size_gb=64, storage_class="standard", attached_to="inst-a",
        ))

    rtnval = VSphereSpec(
        networks=[network], subnets=[subnet], keypairs=[keypair],
        instances=[instance], volumes=volumes,
    )
    return rtnval
