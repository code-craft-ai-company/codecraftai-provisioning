"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers building HetznerSpec instances for tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List, Optional

from ccai.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudingressrule import (
    CloudIngressRule
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.venues.hetzner.hetznerspec import HetznerSpec


_PUBLIC_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
    "2Tvpmdw6KmeqR2a9oJPvufL1YbpX/vRydyqt2NzbwlXhMeNMb29a22kdNRCK"
    "Zfza5VYaRkIFmKrfWu8b2akrytVsgGyPSUzlv0yo3RjKbYDCQuWuusyCYhWf test@host"
)


def basic_spec(*, with_vpn: bool = False,
               with_dns: bool = False,
               with_volume: bool = True,
               instance_size: str = "cx22",
               tags: Optional[List] = None) -> HetznerSpec:
    """
        Build a baseline HetznerSpec with one Network + Subnet + Firewall +
        SSH key + Server (+ optional Volume / DNS / VPN).

        :param with_vpn: Attach a tailscale VPNJoinSpec to the server.
        :param with_dns: Add a CloudDnsRecord.
        :param with_volume: Add a CloudStorageVolume attached to the server.
        :param instance_size: The neutral size hint for the server.
        :param tags: Optional list of single-entry tag dicts on the network.

        :returns: A HetznerSpec.
    """
    network = CloudNetwork(name="net-a", cidr="10.0.0.0/16",
                           region="nbg1", tags=tags)
    subnet = CloudSubnet(name="sub-a", network="net-a",
                         cidr="10.0.1.0/24", zone="nbg1", public=True)
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    firewall = CloudSecurityGroup(name="fw-a", network="net-a",
                                  ingress_rules=[rule])
    keypair = CloudKeyPair(name="kp-a", public_key_material=_PUBLIC_KEY)
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-cred",
            hostname_template="{name}.example",
            advertise_tags=["tag:ci"])

    instance = CloudInstance(
        name="srv-a", profile_ref="profile-a", image=image,
        size=instance_size, subnet="sub-a",
        security_groups=["fw-a"], keypair="kp-a", public_ip=True,
        vpn_join=vpn_join)

    volumes: List[CloudStorageVolume] = []
    if with_volume is True:
        volumes.append(CloudStorageVolume(
            name="vol-a", size_gb=20, storage_class="standard", attached_to="srv-a",
            mount="/data"))

    dns_records: List[CloudDnsRecord] = []
    if with_dns is True:
        dns_records.append(CloudDnsRecord(
            zone="example.com", name="srv-a", record_type="A",
            values=["203.0.113.10"], ttl_seconds=300))

    rtnval = HetznerSpec(networks=[network], subnets=[subnet],
                         security_groups=[firewall], keypairs=[keypair],
                         instances=[instance], volumes=volumes,
                         dns_records=dns_records)
    return rtnval
