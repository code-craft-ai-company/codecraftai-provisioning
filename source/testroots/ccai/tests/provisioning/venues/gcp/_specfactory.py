"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building GcpSpec instances for tests.

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
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
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
from ccai.provisioning.venues.google.gcpspec import GcpSpec


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "e2-standard-2",
               accelerators: Optional[List[CloudAcceleratorSpec]] = None,
               interconnect: Optional[CloudInterconnect] = None,
               preemption: PreemptionPolicy = PreemptionPolicy.FAIL
               ) -> GcpSpec:
    """
        Build a baseline GcpSpec with one VPC + subnet + firewall +
        instance + disk + bucket.

        :param with_vpn: When True, attach a VPNJoinSpec to the instance.
        :param instance_size: Machine type / size hint.
        :param accelerators: Optional accelerator specs.
        :param interconnect: Optional interconnect.
        :param preemption: Preemption policy for the instance.

        :returns: A GcpSpec instance.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16",
                           region="us-central1")
    subnet = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                         zone="us-central1-a", public=True)
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    sg = CloudSecurityGroup(name="sg-a", network="vpc-a",
                            ingress_rules=[rule])
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-cred",
            hostname_template="gcp-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="inst-a", profile_ref="default", image=image,
        size=instance_size, subnet="sub-a", security_groups=["sg-a"],
        vpn_join=vpn_join, accelerators=accelerators,
        interconnect=interconnect, preemption_policy=preemption,
    )

    volume = CloudStorageVolume(name="vol-a", size_gb=10, storage_class="standard",
                                attached_to="inst-a", mount="/dev/sdb")

    bucket = CloudObjectBucket(name="bkt-a", region="us-central1")

    rtnval = GcpSpec(
        networks=[network], subnets=[subnet], security_groups=[sg],
        instances=[instance], volumes=[volume], buckets=[bucket],
    )
    return rtnval


def gpu_compact_spec(*, member_count: int = 2) -> GcpSpec:
    """
        Build a GcpSpec with N A3 GPU instances sharing a compact group.

        :param member_count: Number of compact-grouped instances.

        :returns: A GcpSpec instance.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16",
                           region="us-central1")
    subnet = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                         zone="us-central1-a")
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="ETHERNET", bandwidth_gbps=400,
                                     topology="RAIL_OPTIMIZED")

    instances: List[CloudInstance] = []
    for index in range(member_count):
        instance = CloudInstance(
            name="train-{}".format(index), profile_ref="default",
            image=image, size="a3-highgpu-8g", subnet="sub-a",
            accelerators=[accel], interconnect=interconnect,
            placement_group="train-cluster",
        )
        instances.append(instance)

    rtnval = GcpSpec(networks=[network], subnets=[subnet],
                     instances=instances)
    return rtnval


def tpu_spec() -> GcpSpec:
    """
        Build a GcpSpec with a single TPU node instance.

        :returns: A GcpSpec instance.
    """
    network = CloudNetwork(name="vpc-a", cidr="10.0.0.0/16",
                           region="us-central1")
    subnet = CloudSubnet(name="sub-a", network="vpc-a", cidr="10.0.1.0/24",
                         zone="us-central1-a")
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")
    accel = CloudAcceleratorSpec(kind="TPU", model="TPU_V5P", count=8,
                                 interconnect="NONE", memory_gb=95)
    instance = CloudInstance(
        name="tpu-a", profile_ref="default", image=image,
        size="tpu-v5p", subnet="sub-a", accelerators=[accel],
    )
    rtnval = GcpSpec(networks=[network], subnets=[subnet],
                     instances=[instance])
    return rtnval
