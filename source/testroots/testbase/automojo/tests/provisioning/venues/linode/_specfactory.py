"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers building LinodeSpec instances for tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import List, Optional

from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudingressrule import (
    CloudIngressRule
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from automojo.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from automojo.provisioning.model.cloud.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from automojo.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from automojo.provisioning.model.cloud.cloudsubnet import CloudSubnet
from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from automojo.provisioning.venues.linode.linodespec import LinodeSpec


_PUBLIC_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
    "2Tvpmdw6KmeqR2a9oJPvufL1YbpX/vRydyqt2NzbwlXhMeNMb29a22kdNRCK"
    "Zfza5VYaRkIFmKrfWu8b2akrytVsgGyPSUzlv0yo3RjKbYDCQuWuusyCYhWf"
    "test@host"
)


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "medium",
               region: str = "us-east",
               interconnect: Optional[CloudInterconnect] = None,
               shared_filesystems: Optional[List[CloudSharedFilesystem]] = None
               ) -> LinodeSpec:
    """
        Build a baseline LinodeSpec with one VPC + subnet + firewall +
        SSH key + instance + volume + bucket + DNS record.

        :param with_vpn: Whether the instance carries a VPNJoinSpec.
        :param instance_size: Neutral instance size hint.
        :param region: Linode region slug.
        :param interconnect: Optional CloudInterconnect.
        :param shared_filesystems: Optional shared filesystems.

        :returns: A LinodeSpec.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16", region=region)
    subnet = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                         zone=region, public=True)
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    sg = CloudSecurityGroup(name="sg-a", network="vpc-a",
                            ingress_rules=[rule])
    keypair = CloudKeyPair(name="kp-a", public_key_material=_PUBLIC_KEY)
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-cred",
            hostname_template="linode-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="inst-a", profile_ref="default", image=image,
        size=instance_size, subnet="sub-a", security_groups=["sg-a"],
        keypair="kp-a", vpn_join=vpn_join, interconnect=interconnect,
    )

    volume = CloudStorageVolume(name="vol-a", size_gb=20, type="ssd",
                                attached_to="inst-a", mount="/mnt/data")
    bucket = CloudObjectBucket(name="bkt-a", region="us-east-1")
    dns_record = CloudDnsRecord(zone="example.com", name="host",
                                record_type="A", values=["203.0.113.10"],
                                ttl_seconds=300)

    effective_sfs = shared_filesystems if shared_filesystems is not None else []

    rtnval = LinodeSpec(
        networks=[network], subnets=[subnet], security_groups=[sg],
        keypairs=[keypair], instances=[instance], volumes=[volume],
        buckets=[bucket], dns_records=[dns_record],
        shared_filesystems=effective_sfs,
    )
    return rtnval
