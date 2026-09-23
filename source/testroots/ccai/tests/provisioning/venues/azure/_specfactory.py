"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building AzureSpec instances for tests.

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
from ccai.provisioning.venues.azure.azurespec import AzureSpec


_SSH_KEY = (
    "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCucuwhORgLvigCS6X6MaGJgX"
    "2Tvpmdw6KmeqR2a9oJPvufL1YbpX/vRydyqt2NzbwlXhMeNMb29a22kdNRCK"
    "Zfza5VYaRkIFmKrfWu8b2akrytVsgGyPSUzlv0yo3RjKbYDCQuWuusyCYhWf"
    "KMPNRdWXfyRwOg39PdYUQJrLav7n+4X+0bcYLvpS0M06s/T1BEstcyUFeeJ"
    "w/+/xdb1GbPzIjJvIK4ljQoZIdJEAYInA68Wh+Myv6MaIALP85N9GaN3gxi"
    "o1OFEa/IgvKNGI/oRNJRR6eJQikb5fjayB+/R8m7VdHA4A/WViD2HWc2Zm3"
    "q/wZvIH9QV6py7yz1gDzF test@host"
)


def basic_spec(*, with_vpn: bool = False,
               instance_size: str = "Standard_D2s_v5",
               accelerators: Optional[List[CloudAcceleratorSpec]] = None,
               interconnect: Optional[CloudInterconnect] = None,
               placement_group: Optional[str] = None,
               preemption: PreemptionPolicy = PreemptionPolicy.FAIL,
               image: Optional[CloudImage] = None
               ) -> AzureSpec:
    """
        Build a baseline AzureSpec with one VNet + subnet + NSG + keypair +
        instance + volume + bucket.

        :param with_vpn: When True, attach a Tailscale VPNJoinSpec.
        :param instance_size: Azure VM size for the instance.
        :param accelerators: Optional accelerator list.
        :param interconnect: Optional CloudInterconnect.
        :param placement_group: Optional placement group / interconnect group.
        :param preemption: PreemptionPolicy for the instance.
        :param image: The instance image; None means Ubuntu 22.04.

        :returns: A populated AzureSpec.
    """
    network = CloudNetwork(name="vnet-a", cidr="10.0.0.0/16",
                           region="eastus")
    subnet = CloudSubnet(name="sub-a", network="vnet-a", cidr="10.0.1.0/24",
                         zone="eastus-1", public=True)
    rule = CloudIngressRule(protocol="tcp", from_port=22, to_port=22,
                            source_cidrs=["0.0.0.0/0"])
    sg = CloudSecurityGroup(name="nsg-a", network="vnet-a",
                            ingress_rules=[rule])
    keypair = CloudKeyPair(name="kp-a", public_key_material=_SSH_KEY)
    if image is None:
        image = CloudImage(family="ubuntu", version="22.04",
                           architecture="x86_64")

    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(
            provider="tailscale",
            control_plane_credential="ts-cred",
            hostname_template="azure-{instance_name}",
            advertise_tags=["tag:ci"],
        )

    instance = CloudInstance(
        name="inst-a", profile_ref="default", image=image,
        size=instance_size, subnet="sub-a", security_groups=["nsg-a"],
        keypair="kp-a", vpn_join=vpn_join, accelerators=accelerators,
        interconnect=interconnect, placement_group=placement_group,
        preemption_policy=preemption,
    )

    volume = CloudStorageVolume(name="vol-a", size_gb=64, storage_class="standard",
                                attached_to="inst-a", mount="/dev/sdc")

    bucket = CloudObjectBucket(name="bkta", region="eastus")

    rtnval = AzureSpec(
        networks=[network], subnets=[subnet], security_groups=[sg],
        keypairs=[keypair], instances=[instance], volumes=[volume],
        buckets=[bucket],
    )
    return rtnval


def ib_instance(*, name: str, interconnect_group: str) -> CloudInstance:
    """
        Build an InfiniBand-requesting GPU CloudInstance.

        :param name: Instance name.
        :param interconnect_group: Shared interconnect / placement group.

        :returns: A CloudInstance configured for InfiniBand.
    """
    image = CloudImage(family="ubuntu", version="22.04",
                       architecture="x86_64")
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400,
                                     topology="FAT_TREE")
    rtnval = CloudInstance(
        name=name, profile_ref="default", image=image,
        size="Standard_ND96isr_H100_v5", subnet="sub-a",
        security_groups=["nsg-a"], keypair="kp-a",
        accelerators=[accel], interconnect=interconnect,
        placement_group=interconnect_group,
    )
    return rtnval
