"""
    .. module:: nutanixspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NutanixSpec — venue-scoped bundle of neutral resources for
               the Nutanix AHV / Prism Central venue.

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
from automojo.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from automojo.provisioning.model.cloud.cloudsubnet import CloudSubnet


class NutanixSpec:
    """
        Nutanix-venue-scoped spec bundle.

        Nutanix realises networks (Flow VPCs), subnets (VLAN or VPC
        overlay), security groups (Flow security policies), VMs (cloned
        from a registered Prism image with cloud-init guest customisation),
        storage volumes (volume groups) and SSH keys (injected into the
        cloud-init user_data).  Nutanix exposes no public object storage
        in Prism, no load balancer, and no HPC interconnect — those lists
        are accepted purely so ``validate`` can be honest: buckets
        without Objects configured, load balancers, DNS records and
        non-NONE interconnects produce errors.
    """

    def __init__(self, *,
                 networks: Optional[List[CloudNetwork]] = None,
                 subnets: Optional[List[CloudSubnet]] = None,
                 security_groups: Optional[List[CloudSecurityGroup]] = None,
                 keypairs: Optional[List[CloudKeyPair]] = None,
                 instances: Optional[List[CloudInstance]] = None,
                 volumes: Optional[List[CloudStorageVolume]] = None,
                 shared_filesystems: Optional[
                     List[CloudSharedFilesystem]] = None,
                 buckets: Optional[List[CloudObjectBucket]] = None,
                 dns_records: Optional[List[CloudDnsRecord]] = None,
                 load_balancers: Optional[List[CloudLoadBalancer]] = None
                 ) -> None:
        """
            Construct a NutanixSpec.

            :param networks: List of CloudNetwork (realised as Flow VPCs).
            :param subnets: List of CloudSubnet (realised as Prism
                subnets, VLAN or VPC overlay).
            :param security_groups: List of CloudSecurityGroup (realised
                as Flow security policies).
            :param keypairs: List of CloudKeyPair (injected as cloud-init
                ssh keys).
            :param instances: List of CloudInstance (realised as VMs).
            :param volumes: List of CloudStorageVolume (realised as
                volume groups attached to VMs).
            :param shared_filesystems: List of CloudSharedFilesystem
                (attach-only — must carry ``existing_id``).
            :param buckets: List of CloudObjectBucket (validate-error
                unless Nutanix Objects is configured).
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
        self.volumes: List[CloudStorageVolume] = (
            list(volumes) if volumes is not None else []
        )
        self.shared_filesystems: List[CloudSharedFilesystem] = (
            list(shared_filesystems)
            if shared_filesystems is not None else []
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
