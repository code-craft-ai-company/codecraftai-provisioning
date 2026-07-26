"""
    .. module:: vspherespec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: VSphereSpec — venue-scoped bundle of neutral resources for
        the VSphere venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List, Optional

from ccai.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from ccai.provisioning.model.cloud.cloudloadbalancer import (
    CloudLoadBalancer
)
from ccai.provisioning.model.cloud.cloudnetwork import CloudNetwork
from ccai.provisioning.model.cloud.cloudobjectbucket import (
    CloudObjectBucket
)
from ccai.provisioning.model.cloud.cloudsecuritygroup import (
    CloudSecurityGroup
)
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.model.cloud.cloudstoragevolume import (
    CloudStorageVolume
)
from ccai.provisioning.model.cloud.cloudsubnet import CloudSubnet


class VSphereSpec:
    """
        VSphere-venue-scoped spec bundle.

        Holds lists of neutral resource objects in natural dependency order.
        The :class:`VSphereCloudProvisioner` walks this bundle in
        ``validate / plan / apply / destroy``.  Neutral resources with no
        faithful vSphere realisation (object buckets, NSX-less load
        balancers, HPC interconnects) are accepted here but rejected at
        ``validate`` time per the venue spec.
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
            Construct a VSphereSpec.

            :param networks: List of CloudNetwork (-> Distributed Virtual Switch).
            :param subnets: List of CloudSubnet (-> Distributed Port Group).
            :param security_groups: List of CloudSecurityGroup.
            :param keypairs: List of CloudKeyPair.
            :param instances: List of CloudInstance (-> VM).
            :param volumes: List of CloudStorageVolume (-> VMDK).
            :param buckets: List of CloudObjectBucket (validate-error).
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
