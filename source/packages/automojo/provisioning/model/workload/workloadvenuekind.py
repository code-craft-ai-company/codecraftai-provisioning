"""
    .. module:: workloadvenuekind
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Locked-set enum of workload venue kinds.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from enum import Enum


class WorkloadVenueKind(str, Enum):
    """
        Locked set of workload venue kinds.

        Only KUBERNETES is implementable in v1.  The other values are reserved
        public-surface entries so future implementations are purely additive.
    """
    KUBERNETES = "kubernetes"
    SLURM = "slurm"
    RAY = "ray"
    NOMAD = "nomad"
