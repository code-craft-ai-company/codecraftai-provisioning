"""
    .. module:: workloadspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: WorkloadSpec — the venue-neutral resource bundle a
        WorkloadProvisioner realises onto a workload venue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import List, Optional

from automojo.provisioning.model.workload.workloadcluster import WorkloadCluster
from automojo.provisioning.model.workload.workloadjob import WorkloadJob
from automojo.provisioning.model.workload.workloadservice import WorkloadService


class WorkloadSpec:
    """
        The venue-neutral declared resource bundle a
        :class:`WorkloadProvisioner` realises onto a workload venue.

        Unlike the CoreWeave-specific ``CoreweaveWorkloadSpec`` this bundle
        carries no venue-native identifiers; the venue connection is supplied
        separately to the provisioner constructor so the bundle stays
        portable across the four workload-venue kinds.
    """

    def __init__(self, *, run_id: str,
                 namespace: str = "default",
                 cluster: Optional[WorkloadCluster] = None,
                 jobs: Optional[List[WorkloadJob]] = None,
                 services: Optional[List[WorkloadService]] = None) -> None:
        """
            Construct a :class:`WorkloadSpec`.

            :param run_id: The automojo run identifier. Every realised
                resource is labelled with it.
            :param namespace: The target namespace (Kubernetes) or logical
                partition (other venue kinds).
            :param cluster: Optional :class:`WorkloadCluster` node-pool
                descriptor.
            :param jobs: The :class:`WorkloadJob` resources to realise.
            :param services: The :class:`WorkloadService` resources to
                realise.

            :returns: None
        """
        self.run_id: str = run_id
        self.namespace: str = namespace
        self.cluster: Optional[WorkloadCluster] = cluster
        self.jobs: List[WorkloadJob] = jobs if jobs is not None else []
        self.services: List[WorkloadService] = services if services is not None else []
        return


__all__ = ["WorkloadSpec"]
