"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building AwsSpec instances for tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, List, Optional

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
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet
from ccai.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from ccai.interfaces.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.venues.aws.awsspec import AwsSpec


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "t3.micro",
               accelerators: Optional[List[CloudAcceleratorSpec]] = None,
               interconnect: Optional[CloudInterconnect] = None,
               preemption: PreemptionPolicy = PreemptionPolicy.FAIL
               ) -> AwsSpec:
    """
        Build a baseline AwsSpec with one VPC + subnet + SG + keypair +
        instance + volume.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16",
                           region="us-east-1")
    subnet = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                         zone="us-east-1a", public=True)
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    sg = CloudSecurityGroup(name="sg-a", network="vpc-a",
                            ingress_rules=[rule])
    keypair = CloudKeyPair(
        name="kp-a",
        public_key_material=(
            "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
            "2Tvpmdw6KmeqR2a9oJPvufL1YbpX/vRydyqt2NzbwlXhMeNMb29a22kdNRCK"
            "Zfza5VYaRkIFmKrfWu8b2akrytVsgGyPSUzlv0yo3RjKbYDCQuWuusyCYhWf"
            "KMPNRdWXfyRwOg39PdYUQJrLav7n+4X+0bcYLvpS0M06s/T1BEstcyUFeeJ"
            "w/+/xdb1GbPzIjJvIK4ljQoZIdJEAYInA68Wh+Myv6MaIALP85N9GaN3gxi"
            "o1OFEa/IgvKNGI/oRNJRR6eJQikb5fjayB+/R8m7VdHA4A/WViD2HWc2Zm3"
            "q/wZvIH9QV6py7yz1gDzF test@host"
        ),
    )
    image = CloudImage(family="ubuntu", version="22.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-cred",
            hostname_template="aws-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="inst-a", profile_ref="default", image=image,
        size=instance_size, subnet="sub-a", security_groups=["sg-a"],
        keypair="kp-a", vpn_join=vpn_join, accelerators=accelerators,
        interconnect=interconnect, preemption_policy=preemption,
    )

    volume = CloudStorageVolume(name="vol-a", size_gb=10, storage_class="standard",
                                attached_to="inst-a", mount="/dev/sdf")

    bucket = CloudObjectBucket(name="bkt-a", region="us-east-1")

    rtnval = AwsSpec(
        networks=[network], subnets=[subnet], security_groups=[sg],
        keypairs=[keypair], instances=[instance], volumes=[volume],
        buckets=[bucket],
    )
    return rtnval
