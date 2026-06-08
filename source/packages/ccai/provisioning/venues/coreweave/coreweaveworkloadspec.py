"""
    .. module:: coreweaveworkloadspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CoreweaveWorkloadSpec — the resource bundle the CoreWeave
        workload provisioner operates on.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.model.workload.workloadcluster import WorkloadCluster
from ccai.provisioning.model.workload.workloadjob import WorkloadJob
from ccai.provisioning.model.workload.workloadservice import WorkloadService


class CoreweaveWorkloadSpec:
    """
        The declared resource bundle a :class:`CoreweaveWorkloadProvisioner`
        realises onto a CoreWeave CKS cluster.

        It carries the target cluster identifier, the optional
        :class:`WorkloadCluster` node-pool descriptor, the list of
        :class:`WorkloadJob` and :class:`WorkloadService` resources, and the
        optional Sunk (Slurm-on-K8s) sub-mode flag. Per-workload
        :class:`VPNJoinSpec` instances are supplied through ``vpn_joins``
        keyed by workload name.
    """

    def __init__(self, *, run_id: str, cluster_id: str,
                 namespace: str = "default",
                 cluster: Optional[WorkloadCluster] = None,
                 jobs: Optional[List[WorkloadJob]] = None,
                 services: Optional[List[WorkloadService]] = None,
                 sub_mode: Optional[str] = None,
                 vpn_joins: Optional[Dict[str, Any]] = None,
                 csi_bindings: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a :class:`CoreweaveWorkloadSpec`.

            :param run_id: The ccai run identifier. Every realised
                Kubernetes resource is labelled with it.
            :param cluster_id: The CoreWeave CKS cluster identifier the
                kubeconfig is minted for.
            :param namespace: The target Kubernetes namespace.
            :param cluster: Optional :class:`WorkloadCluster` carrying the
                node-pool / accelerator-pool descriptors.
            :param jobs: The :class:`WorkloadJob` resources to realise.
            :param services: The :class:`WorkloadService` resources to
                realise.
            :param sub_mode: Optional sub-mode flag. ``"sunk"`` selects the
                Slurm-on-Kubernetes rendering path.
            :param vpn_joins: Optional ``workload-name -> VPNJoinSpec`` map.
            :param csi_bindings: Optional ``shared-fs-id -> StorageClass``
                map used to bind shared-filesystem PVCs.

            :returns: ``None``.
        """
        self.run_id = run_id
        self.cluster_id = cluster_id
        self.namespace = namespace
        self.cluster = cluster
        self.jobs = jobs if jobs is not None else []
        self.services = services if services is not None else []
        self.sub_mode = sub_mode
        self.vpn_joins = vpn_joins if vpn_joins is not None else {}
        self.csi_bindings = csi_bindings if csi_bindings is not None else {}
        return


__all__ = ["CoreweaveWorkloadSpec"]
