"""
    .. module:: workloadvenuekind
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Locked-set enum of workload venue kinds.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from enum import Enum


class WorkloadVenueKind(str, Enum):
    """
        Locked set of workload venue kinds.

        KUBERNETES and CONTAINER are implementable; CONTAINER describes a
        container-shaped GPU venue (e.g. RunPod) whose unit of work is a
        container/pod rather than a cluster-scheduler job.  SLURM, RAY and
        NOMAD are reserved public-surface entries so future implementations
        are purely additive.
    """
    KUBERNETES = "kubernetes"
    CONTAINER = "container"
    SLURM = "slurm"
    RAY = "ray"
    NOMAD = "nomad"
