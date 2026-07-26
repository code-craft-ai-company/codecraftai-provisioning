"""
    .. module:: workloadcluster
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Declarative WorkloadCluster resource.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.interfaces.schemavalidators import validate_name
from ccai.provisioning.model.workload.nodepoolspec import NodePoolSpec
from ccai.provisioning.model.workload.autoscalingspec import AutoscalingSpec


class WorkloadCluster(SchemaObject):
    """
        Declarative cluster resource for a WorkloadVenue.

        Carries node pool descriptors, optional accelerator pools, optional
        autoscaling, networking dict, and tags.
    """

    name = Field(str, required=True)
    node_pools = Field(list, required=False, default=None)
    accelerator_pools = Field(list, required=False, default=None)
    autoscaling = Field(AutoscalingSpec, required=False, default=None)
    networking = Field(dict, required=False, default=None)
    tags = Field(dict, required=False, default=None)

    def __init__(self, *, name: str,
                 node_pools: Optional[List[NodePoolSpec]] = None,
                 accelerator_pools: Optional[List[NodePoolSpec]] = None,
                 autoscaling: Optional[AutoscalingSpec] = None,
                 networking: Optional[Dict[str, Any]] = None,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a WorkloadCluster.

            :param name: Cluster name.
            :param node_pools: Optional list of CPU/general node pools.
            :param accelerator_pools: Optional list of accelerator node pools.
            :param autoscaling: Optional autoscaling spec.
            :param networking: Optional venue-neutral networking dict.
            :param tags: Optional flat dict of tag key/value pairs.

            :raises: SchemaValidationError
        """
        validate_name(value=name)

        effective_node_pools = node_pools if node_pools is not None else []
        effective_accel_pools = accelerator_pools if accelerator_pools is not None else []
        effective_networking = networking if networking is not None else {}
        effective_tags = tags if tags is not None else {}

        super().__init__(name=name, node_pools=effective_node_pools,
                         accelerator_pools=effective_accel_pools,
                         autoscaling=autoscaling,
                         networking=effective_networking,
                         tags=effective_tags)
        return
