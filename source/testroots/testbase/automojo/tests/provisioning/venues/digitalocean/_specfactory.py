"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building DoSpec instances for DigitalOcean tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, List, Optional

from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudingressrule import (
    CloudIngressRule
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from automojo.provisioning.model.cloud.cloudnetwork import CloudNetwork
from automojo.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from automojo.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from automojo.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from automojo.provisioning.venues.digitalocean.dospec import DoSpec


_PUBLIC_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
    "2Tvpmdw6KmeqR2a9oJPvufL1YbpX/vRydyqt2NzbwlXhMeNMb29a22kdNRCK"
    "Zfza5VYaRkIFmKrfWu8b2akrytVsgGyPSUzlv0yo3RjKbYDCQuWuusyCYhWf"
    "KMPNRdWXfyRwOg39PdYUQJrLav7n+4X+0bcYLvpS0M06s/T1BEstcyUFeeJ"
    "w/+/xdb1GbPzIjJvIK4ljQoZIdJEAYInA68Wh+Myv6MaIALP85N9GaN3gxi"
    "o1OFEa/IgvKNGI/oRNJRR6eJQikb5fjayB+/R8m7VdHA4A/WViD2HWc2Zm3"
    "q/wZvIH9QV6py7yz1gDzF test@host"
)


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "s-2vcpu-4gb",
               accelerators: Optional[List[Any]] = None,
               with_dns: bool = False) -> DoSpec:
    """
        Build a baseline DoSpec with one VPC + firewall + keypair + Droplet +
        volume + Spaces bucket.

        :param with_vpn: When True the Droplet carries a Tailscale vpn_join.
        :param instance_size: Droplet size hint.
        :param accelerators: Optional accelerator list.
        :param with_dns: When True a DNS record is added.

        :returns: A DoSpec.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16", region="nyc3")
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    firewall = CloudSecurityGroup(name="fw-a", network="vpc-a",
                                  ingress_rules=[rule])
    keypair = CloudKeyPair(name="kp-a", public_key_material=_PUBLIC_KEY)
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale", control_plane_credential="ts-cred",
            hostname_template="do-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="droplet-a", profile_ref="default", image=image,
        size=instance_size, subnet="vpc-a", security_groups=["fw-a"],
        keypair="kp-a", vpn_join=vpn_join, accelerators=accelerators,
    )

    volume = CloudStorageVolume(name="vol-a", size_gb=10, type="ssd",
                                attached_to="droplet-a", mount="/mnt/data")
    bucket = CloudObjectBucket(name="bkt-a", region="nyc3")

    dns_records: List[CloudDnsRecord] = []
    if with_dns is True:
        dns_records.append(CloudDnsRecord(
            zone="example.com", name="api", record_type="A",
            values=["203.0.113.10"], ttl_seconds=300,
        ))

    rtnval = DoSpec(
        networks=[network], security_groups=[firewall], keypairs=[keypair],
        instances=[instance], volumes=[volume], buckets=[bucket],
        dns_records=dns_records,
    )
    return rtnval
