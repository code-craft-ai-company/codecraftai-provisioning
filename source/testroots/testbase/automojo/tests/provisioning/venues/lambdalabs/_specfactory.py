"""
    .. module:: _specfactory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Small helpers building LambdalabsSpec instances for tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, List, Optional

from ccai.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudinterconnect import (
    CloudInterconnect
)
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from ccai.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec
from ccai.provisioning.venues.lambdalabs.lambdalabsspec import (
    LambdalabsSpec
)


_PUBLIC_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILABTESTKEY00000000000000000 "
    "test@lambdalabs"
)


def make_image() -> CloudImage:
    """
        Build a CloudImage suitable for the Lambda Labs venue.

        :returns: A CloudImage instance.
    """
    rtnval = CloudImage(family="ubuntu", version="22.04",
                        architecture="x86_64")
    return rtnval


def make_keypair() -> CloudKeyPair:
    """
        Build a CloudKeyPair suitable for the Lambda Labs venue.

        :returns: A CloudKeyPair instance.
    """
    rtnval = CloudKeyPair(name="lab-key", public_key_material=_PUBLIC_KEY)
    return rtnval


def make_instance(*, name: str = "trainer", region: str = "us-east-1",
                  size: str = "gpu_1x_h100_pcie",
                  with_vpn: bool = False,
                  accelerators: Optional[List[CloudAcceleratorSpec]] = None,
                  interconnect: Optional[CloudInterconnect] = None,
                  tags: Optional[List[Dict[str, str]]] = None
                  ) -> CloudInstance:
    """
        Build a CloudInstance for the Lambda Labs venue.

        The Lambda Labs venue treats the instance ``subnet`` field as the
        region name, since Lambda has no subnet model.

        :param name: The instance name.
        :param region: The Lambda Labs region (carried in ``subnet``).
        :param size: The Lambda Labs instance-type slug.
        :param with_vpn: Whether to attach a Tailscale VPNJoinSpec.
        :param accelerators: Optional accelerator list.
        :param interconnect: Optional interconnect.
        :param tags: Optional neutral tag list.

        :returns: A CloudInstance instance.
    """
    vpn_join: Optional[VPNJoinSpec] = None
    if with_vpn is True:
        vpn_join = VPNJoinSpec(provider="tailscale",
                               control_plane_credential="ts-cred",
                               hostname_template="{name}",
                               advertise_tags=["tag:lab"])

    rtnval = CloudInstance(name=name, profile_ref="gpu-profile",
                           image=make_image(), size=size, subnet=region,
                           keypair="lab-key", vpn_join=vpn_join,
                           accelerators=accelerators,
                           interconnect=interconnect, tags=tags)
    return rtnval


def basic_spec(*, with_vpn: bool = False,
               tags: Optional[List[Dict[str, str]]] = None) -> LambdalabsSpec:
    """
        Build a baseline LambdalabsSpec with one keypair + one instance.

        :param with_vpn: Whether the instance carries a VPNJoinSpec.
        :param tags: Optional neutral tag list on the instance.

        :returns: A LambdalabsSpec instance.
    """
    rtnval = LambdalabsSpec(keypairs=[make_keypair()],
                            instances=[make_instance(with_vpn=with_vpn,
                                                     tags=tags)])
    return rtnval


def cluster_spec() -> LambdalabsSpec:
    """
        Build a LambdalabsSpec whose instance resolves to a 1-click cluster.

        :returns: A LambdalabsSpec instance.
    """
    accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                 interconnect="NVSWITCH", memory_gb=80)
    interconnect = CloudInterconnect(kind="INFINIBAND_NDR",
                                     bandwidth_gbps=400,
                                     topology="RAIL_OPTIMIZED")
    instance = make_instance(name="cluster-node",
                             accelerators=[accel, accel],
                             interconnect=interconnect)
    rtnval = LambdalabsSpec(keypairs=[make_keypair()], instances=[instance])
    return rtnval


def bucket_lb_dns_spec() -> LambdalabsSpec:
    """
        Build a LambdalabsSpec containing an object bucket, a load
        balancer, and a DNS record — every resource Lambda Labs rejects.

        :returns: A LambdalabsSpec instance.
    """
    bucket = CloudObjectBucket(name="data-bucket", region="us-east-1")
    lb = CloudLoadBalancer(name="api-lb", scheme="internet-facing")
    record = CloudDnsRecord(zone="example.com", name="api",
                            record_type="A", values=["203.0.113.1"],
                            ttl_seconds=300)
    rtnval = LambdalabsSpec(instances=[make_instance()],
                            keypairs=[make_keypair()],
                            buckets=[bucket], load_balancers=[lb],
                            dns_records=[record])
    return rtnval
