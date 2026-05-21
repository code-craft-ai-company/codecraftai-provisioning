"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Helpers building VultrSpec instances for tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import List, Optional

from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
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
from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from automojo.provisioning.venues.vultr.vultrspec import VultrSpec


_PUBLIC_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
    "2Tvpmdw6KmeqR2a9oJPvufL1YbpX test@host"
)


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "vc2-2c-4gb",
               accelerators: Optional[List[CloudAcceleratorSpec]] = None,
               interconnect: Optional[CloudInterconnect] = None,
               shared_filesystems: Optional[List[CloudSharedFilesystem]] = None
               ) -> VultrSpec:
    """
        Build a baseline VultrSpec with one VPC + SG + keypair + instance +
        block volume + bucket + DNS record.

        :param with_vpn: When True, attach a tailscale VPNJoinSpec.
        :param instance_size: The instance plan hint.
        :param accelerators: Optional accelerator list.
        :param interconnect: Optional interconnect (for rejection tests).
        :param shared_filesystems: Optional shared FS list (for rejection).

        :returns: A VultrSpec.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16", region="ewr")
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
            hostname_template="vultr-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="inst-a", profile_ref="default", image=image,
        size=instance_size, subnet="vpc-a", security_groups=["sg-a"],
        keypair="kp-a", vpn_join=vpn_join, accelerators=accelerators,
        interconnect=interconnect,
    )

    volume = CloudStorageVolume(name="vol-a", size_gb=40, storage_class="standard",
                                attached_to="inst-a")
    bucket = CloudObjectBucket(name="bkt-a", region="ewr")
    dns = CloudDnsRecord(zone="example.com", name="host", record_type="A",
                         values=["192.0.2.10"], ttl_seconds=300)

    rtnval = VultrSpec(
        networks=[network], security_groups=[sg], keypairs=[keypair],
        instances=[instance], volumes=[volume], buckets=[bucket],
        dns_records=[dns], shared_filesystems=shared_filesystems,
    )
    return rtnval
