"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers building NebiusSpec instances for venue tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List, Optional

from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudingressrule import (
    CloudIngressRule
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.interfaces.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.venues.nebius.nebiusspec import NebiusSpec


_PUBLIC_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
    "2Tvpmdw6KmeqR2a9oJPvufL1YbpX/vRydyqt2NzbwlXhMeNMb29a22kdNRCK"
    "Zfza5VYaRkIFmKrfWu8b2akrytVsgGyPSUzlv0yo3RjKbYDCQuWuusyCYhWf "
    "test@host"
)


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "cpu-4vcpu-16gb",
               accelerators: Optional[List[CloudAcceleratorSpec]] = None,
               interconnect: Optional[CloudInterconnect] = None,
               placement_group: Optional[str] = None) -> NebiusSpec:
    """
        Build a baseline NebiusSpec with one VPC + subnet + SG + keypair +
        instance + volume.

        :param with_vpn: When True, attach a VPNJoinSpec to the instance.
        :param instance_size: The neutral size hint.
        :param accelerators: Optional accelerator list.
        :param interconnect: Optional CloudInterconnect.
        :param placement_group: Optional placement-group / interconnect
            group name.

        :returns: A NebiusSpec.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16",
                           region="eu-north1")
    subnet = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                         zone="eu-north1-a", public=True)
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    sg = CloudSecurityGroup(name="sg-a", network="vpc-a",
                            ingress_rules=[rule])
    keypair = CloudKeyPair(name="kp-a", public_key_material=_PUBLIC_KEY)
    image = CloudImage(family="ubuntu", version="22.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale", control_plane_credential="ts-cred",
            hostname_template="nebius-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="inst-a", profile_ref="default", image=image,
        size=instance_size, subnet="sub-a", security_groups=["sg-a"],
        keypair="kp-a", vpn_join=vpn_join, accelerators=accelerators,
        interconnect=interconnect, placement_group=placement_group,
    )

    volume = CloudStorageVolume(name="vol-a", size_gb=100, storage_class="standard",
                                attached_to="inst-a", mount="/dev/sdb")

    rtnval = NebiusSpec(
        parent_id="proj-test", region_id="eu-north1",
        networks=[network], subnets=[subnet], security_groups=[sg],
        keypairs=[keypair], instances=[instance], volumes=[volume],
    )
    return rtnval


def gpu_cluster_spec() -> NebiusSpec:
    """
        Build a NebiusSpec with two GPU instances sharing an IB interconnect
        group plus a shared filesystem.

        :returns: A NebiusSpec.
    """
    network = CloudNetwork(name="vpc-g", cidr="10.10.0.0/16",
                           region="eu-north1")
    subnet = CloudSubnet(name="sub-g", network="vpc-g",
                         cidr="10.10.1.0/24", zone="eu-north1-a")
    keypair = CloudKeyPair(name="kp-g", public_key_material=_PUBLIC_KEY)
    image = CloudImage(family="ubuntu", version="22.04",
                       architecture="x86_64")
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    ic = CloudInterconnect(kind="INFINIBAND_NDR", bandwidth_gbps=400)

    instances = []
    for index in range(2):
        instances.append(CloudInstance(
            name="gpu-{}".format(index), profile_ref="default", image=image,
            size="gpu", subnet="sub-g", keypair="kp-g",
            accelerators=[accel], interconnect=ic,
            placement_group="train-cluster",
        ))

    from ccai.interfaces.cloudsharedfilesystem import (
        CloudSharedFilesystem
    )
    sfs = CloudSharedFilesystem(name="shared-a", kind="VENUE_NATIVE",
                                existing_id="fs-pre-existing")

    rtnval = NebiusSpec(
        parent_id="proj-test", region_id="eu-north1",
        networks=[network], subnets=[subnet], keypairs=[keypair],
        instances=instances, shared_filesystems=[sfs],
    )
    return rtnval
