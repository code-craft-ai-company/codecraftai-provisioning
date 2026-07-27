"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building OciSpec instances for the Oracle tests.

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
from ccai.provisioning.venues.oracle.ocispec import OciSpec


_SSH_PUBLIC_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
    "2Tvpmdw6KmeqR2a9oJPvufL1YbpX/vRydyqt2NzbwlXhMeNMb29a22kdNRCK"
    "Zfza5VYaRkIFmKrfWu8b2akrytVsgGyPSUzlv0yo3RjKbYDCQuWuusyCYhWf"
    "KMPNRdWXfyRwOg39PdYUQJrLav7n+4X+0bcYLvpS0M06s/T1BEstcyUFeeJ"
    "w/+/xdb1GbPzIjJvIK4ljQoZIdJEAYInA68Wh+Myv6MaIALP85N9GaN3gxi"
    "o1OFEa/IgvKNGI/oRNJRR6eJQikb5fjayB+/R8m7VdHA4A/WViD2HWc2Zm3"
    "q/wZvIH9QV6py7yz1gDzF test@host"
)


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "VM.Standard.E4.Flex",
               accelerators: Optional[List[CloudAcceleratorSpec]] = None,
               interconnect: Optional[CloudInterconnect] = None,
               preemption: PreemptionPolicy = PreemptionPolicy.FAIL
               ) -> OciSpec:
    """
        Build a baseline OciSpec with one VCN + subnet + security list +
        keypair + instance + volume + bucket.

        :param with_vpn: When True, the instance carries a Tailscale VPNJoinSpec.
        :param instance_size: The neutral instance size.
        :param accelerators: Optional accelerator list.
        :param interconnect: Optional CloudInterconnect.
        :param preemption: PreemptionPolicy for the instance.

        :returns: An OciSpec.
    """
    network = CloudNetwork(name="vcn-a", cidr="10.0.0.0/16",
                           region="us-ashburn-1")
    subnet = CloudSubnet(name="sub-a", network="vcn-a", cidr="10.0.1.0/24",
                         zone="Uocm:US-ASHBURN-AD-1", public=True)
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    sg = CloudSecurityGroup(name="sl-a", network="vcn-a",
                            ingress_rules=[rule])
    keypair = CloudKeyPair(name="kp-a",
                           public_key_material=_SSH_PUBLIC_KEY)
    image = CloudImage(family="ubuntu", version="22.04",
                       architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-cred",
            hostname_template="oci-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="inst-a", profile_ref="default", image=image,
        size=instance_size, subnet="sub-a", security_groups=["sl-a"],
        keypair="kp-a", vpn_join=vpn_join, accelerators=accelerators,
        interconnect=interconnect, preemption_policy=preemption,
    )

    volume = CloudStorageVolume(name="vol-a", size_gb=50, storage_class="standard",
                                attached_to="inst-a", mount="/mnt/data")

    bucket = CloudObjectBucket(name="bkt-a", region="us-ashburn-1")

    rtnval = OciSpec(
        networks=[network], subnets=[subnet], security_groups=[sg],
        keypairs=[keypair], instances=[instance], volumes=[volume],
        buckets=[bucket],
    )
    return rtnval


def rdma_spec(*, member_count: int = 3) -> OciSpec:
    """
        Build an OciSpec with N RDMA-grouped BM.GPU instances.

        Every instance shares the ``rail-pod`` placement group with
        ``CloudInterconnect(kind=OCI_RDMA)``.

        :param member_count: Number of instances in the cluster network.

        :returns: An OciSpec.
    """
    network = CloudNetwork(name="vcn-r", cidr="10.1.0.0/16",
                           region="us-ashburn-1")
    subnet = CloudSubnet(name="sub-r", network="vcn-r", cidr="10.1.1.0/24",
                         zone="Uocm:US-ASHBURN-AD-1", public=True)
    image = CloudImage(family="ubuntu", version="22.04",
                       architecture="x86_64")
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="OCI_RDMA", bandwidth_gbps=3200,
                                     topology="RAIL_OPTIMIZED")

    instances: List[CloudInstance] = []
    for index in range(member_count):
        instances.append(CloudInstance(
            name="gpu-{}".format(index), profile_ref="default",
            image=image, size="BM.GPU.H100.8", subnet="sub-r",
            accelerators=[accel], interconnect=interconnect,
            placement_group="rail-pod",
        ))

    rtnval = OciSpec(networks=[network], subnets=[subnet],
                     instances=instances)
    return rtnval
