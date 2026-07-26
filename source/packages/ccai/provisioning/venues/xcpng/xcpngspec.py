"""
    .. module:: xcpngspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XcpngSpec — venue-scoped bundle of neutral resources for the
        XCP-ng / XenServer venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import List, Optional

from ccai.provisioning.model.cloud.clouddnsrecord import CloudDnsRecord
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
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


class XcpngSpec:
    """
        XCP-ng-venue-scoped spec bundle.

        XCP-ng realises Networks (XAPI ``network``), Instances (VMs cloned
        from a Template), and Storage Volumes (VDIs on a chosen SR).  The
        remaining lists are still accepted so the provisioner's ``validate``
        can be honest about every gap: security groups produce warnings (the
        intent is recorded in VM tags), DNS records produce warnings, while
        object buckets and load balancers produce errors — XCP-ng has no
        native object-storage or load-balancing service.
    """

    def __init__(self, *,
                 networks: Optional[List[CloudNetwork]] = None,
                 subnets: Optional[List[CloudSubnet]] = None,
                 security_groups: Optional[List[CloudSecurityGroup]] = None,
                 instances: Optional[List[CloudInstance]] = None,
                 volumes: Optional[List[CloudStorageVolume]] = None,
                 shared_filesystems: Optional[
                     List[CloudSharedFilesystem]] = None,
                 buckets: Optional[List[CloudObjectBucket]] = None,
                 dns_records: Optional[List[CloudDnsRecord]] = None,
                 load_balancers: Optional[List[CloudLoadBalancer]] = None
                 ) -> None:
        """
            Construct an XcpngSpec.

            :param networks: List of CloudNetwork (realised as XAPI
                             networks, reused by name_label).
            :param subnets: List of CloudSubnet (folded into cloud-init).
            :param security_groups: List of CloudSecurityGroup (warned;
                                    intent recorded in VM tags).
            :param instances: List of CloudInstance (realised as VM clones).
            :param volumes: List of CloudStorageVolume (realised as VDIs).
            :param shared_filesystems: List of CloudSharedFilesystem
                                       (attach-only).
            :param buckets: List of CloudObjectBucket (validate-error).
            :param dns_records: List of CloudDnsRecord (validate-warning).
            :param load_balancers: List of CloudLoadBalancer
                                   (validate-error).
        """
        self.networks: List[CloudNetwork] = (
            list(networks) if networks is not None else [])
        self.subnets: List[CloudSubnet] = (
            list(subnets) if subnets is not None else [])
        self.security_groups: List[CloudSecurityGroup] = (
            list(security_groups) if security_groups is not None else [])
        self.instances: List[CloudInstance] = (
            list(instances) if instances is not None else [])
        self.volumes: List[CloudStorageVolume] = (
            list(volumes) if volumes is not None else [])
        self.shared_filesystems: List[CloudSharedFilesystem] = (
            list(shared_filesystems)
            if shared_filesystems is not None else [])
        self.buckets: List[CloudObjectBucket] = (
            list(buckets) if buckets is not None else [])
        self.dns_records: List[CloudDnsRecord] = (
            list(dns_records) if dns_records is not None else [])
        self.load_balancers: List[CloudLoadBalancer] = (
            list(load_balancers) if load_balancers is not None else [])
        return
