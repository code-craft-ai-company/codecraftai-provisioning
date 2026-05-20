"""
    .. module:: azurespec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AzureSpec — venue-scoped bundle of neutral resources for Azure.

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


class AzureSpec:
    """
        Azure-venue-scoped spec bundle.

        Holds lists of neutral resource objects in the natural dependency
        order.  The :class:`AzureCloudProvisioner` walks this in
        ``validate / plan / apply``.  The Azure ResourceGroup is the apex
        container; it is resolved from the :class:`AzureRegionConfig` rather
        than declared as a neutral resource.
    """

    def __init__(self, *,
                 networks: Optional[List[CloudNetwork]] = None,
                 subnets: Optional[List[CloudSubnet]] = None,
                 security_groups: Optional[List[CloudSecurityGroup]] = None,
                 keypairs: Optional[List[CloudKeyPair]] = None,
                 instances: Optional[List[CloudInstance]] = None,
                 volumes: Optional[List[CloudStorageVolume]] = None,
                 buckets: Optional[List[CloudObjectBucket]] = None,
                 dns_records: Optional[List[CloudDnsRecord]] = None,
                 shared_filesystems: Optional[List[CloudSharedFilesystem]] = None,
                 load_balancers: Optional[List[CloudLoadBalancer]] = None
                 ) -> None:
        """
            Construct an AzureSpec.

            :param networks: List of CloudNetwork (each maps to a VNet).
            :param subnets: List of CloudSubnet.
            :param security_groups: List of CloudSecurityGroup (each maps to
                                    a Network Security Group).
            :param keypairs: List of CloudKeyPair (injected into VM admin
                             SSH config).
            :param instances: List of CloudInstance (each maps to a VM+NIC).
            :param volumes: List of CloudStorageVolume (each maps to a
                            Managed Disk).
            :param buckets: List of CloudObjectBucket (Blob container).
            :param dns_records: List of CloudDnsRecord.
            :param shared_filesystems: List of CloudSharedFilesystem.
            :param load_balancers: List of CloudLoadBalancer.
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
        self.buckets: List[CloudObjectBucket] = (
            list(buckets) if buckets is not None else []
        )
        self.dns_records: List[CloudDnsRecord] = (
            list(dns_records) if dns_records is not None else []
        )
        self.shared_filesystems: List[CloudSharedFilesystem] = (
            list(shared_filesystems) if shared_filesystems is not None else []
        )
        self.load_balancers: List[CloudLoadBalancer] = (
            list(load_balancers) if load_balancers is not None else []
        )
        return
