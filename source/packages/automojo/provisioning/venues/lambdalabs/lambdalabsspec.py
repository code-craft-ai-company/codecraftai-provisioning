"""
    .. module:: lambdalabsspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LambdalabsSpec — venue-scoped bundle of neutral resources
               for the Lambda Labs venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import List, Optional

from automojo.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from automojo.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
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
from automojo.provisioning.model.cloud.cloudsubnet import CloudSubnet


class LambdalabsSpec:
    """
        Lambda-Labs-venue-scoped spec bundle.

        Lambda Labs realises only a small slice of the neutral resource
        model — instances, SSH keys, and (attach-only) file systems.  The
        remaining lists are still accepted so the provisioner's ``validate``
        can be honest about what Lambda cannot do: networks / subnets /
        security groups produce warnings, while buckets / load balancers /
        DNS records produce errors.
    """

    def __init__(self, *,
                 networks: Optional[List[CloudNetwork]] = None,
                 subnets: Optional[List[CloudSubnet]] = None,
                 security_groups: Optional[List[CloudSecurityGroup]] = None,
                 keypairs: Optional[List[CloudKeyPair]] = None,
                 instances: Optional[List[CloudInstance]] = None,
                 shared_filesystems: Optional[List[CloudSharedFilesystem]] = None,
                 buckets: Optional[List[CloudObjectBucket]] = None,
                 dns_records: Optional[List[CloudDnsRecord]] = None,
                 load_balancers: Optional[List[CloudLoadBalancer]] = None
                 ) -> None:
        """
            Construct a LambdalabsSpec.

            :param networks: List of CloudNetwork (warned + ignored).
            :param subnets: List of CloudSubnet (warned + ignored).
            :param security_groups: List of CloudSecurityGroup (warned +
                ignored).
            :param keypairs: List of CloudKeyPair (realised as SSH keys).
            :param instances: List of CloudInstance (realised as instances
                or 1-click clusters).
            :param shared_filesystems: List of CloudSharedFilesystem
                (attach-only).
            :param buckets: List of CloudObjectBucket (validate-error).
            :param dns_records: List of CloudDnsRecord (validate-error).
            :param load_balancers: List of CloudLoadBalancer
                (validate-error).
        """
        self.networks: List[CloudNetwork] = (
            list(networks) if networks is not None else []
        )
        self.subnets: List[CloudSubnet] = (
            list(subnets) if subnets is not None else []
        )
        self.security_groups: List[CloudSecurityGroup] = (
            list(security_groups) if security_groups is not None else []
        )
        self.keypairs: List[CloudKeyPair] = (
            list(keypairs) if keypairs is not None else []
        )
        self.instances: List[CloudInstance] = (
            list(instances) if instances is not None else []
        )
        self.shared_filesystems: List[CloudSharedFilesystem] = (
            list(shared_filesystems) if shared_filesystems is not None else []
        )
        self.buckets: List[CloudObjectBucket] = (
            list(buckets) if buckets is not None else []
        )
        self.dns_records: List[CloudDnsRecord] = (
            list(dns_records) if dns_records is not None else []
        )
        self.load_balancers: List[CloudLoadBalancer] = (
            list(load_balancers) if load_balancers is not None else []
        )
        return
