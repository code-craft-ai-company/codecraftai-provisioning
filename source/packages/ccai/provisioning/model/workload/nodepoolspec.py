"""
    .. module:: nodepoolspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Node-pool descriptor used by WorkloadCluster.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, List, Optional

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.interfaces.schemavalidators import (
    validate_name, validate_positive_int
)
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudinterconnect import CloudInterconnect


class NodePoolSpec(SchemaObject):
    """
        Declarative node pool for a WorkloadCluster.

        Mirrors the accelerator / interconnect optional slots on CloudInstance
        so an accelerator pool's node shape is venue-neutral.
    """

    name = Field(str, required=True)
    count = Field(int, required=True)
    size = Field(str, required=True)
    accelerators = Field(list, required=False, default=None)
    interconnect = Field(CloudInterconnect, required=False, default=None)
    taints = Field(list, required=False, default=None)
    labels = Field(dict, required=False, default=None)

    def __init__(self, *, name: str, count: int, size: str,
                 accelerators: Optional[List[CloudAcceleratorSpec]] = None,
                 interconnect: Optional[CloudInterconnect] = None,
                 taints: Optional[List[Dict[str, str]]] = None,
                 labels: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a NodePoolSpec.

            :param name: Pool name.
            :param count: Number of nodes; must be > 0.
            :param size: Venue-neutral size identifier.
            :param accelerators: Optional accelerator specs.
            :param interconnect: Optional interconnect spec.
            :param taints: Optional list of taint dicts.
            :param labels: Optional label map.

            :raises: SchemaValidationError
        """
        validate_name(value=name)
        validate_positive_int(value=count, field_name="count")

        if size is None or len(size) == 0:
            raise SchemaValidationError("size must not be empty.")

        effective_taints = taints if taints is not None else []
        effective_labels = labels if labels is not None else {}

        super().__init__(name=name, count=count, size=size,
                         accelerators=accelerators, interconnect=interconnect,
                         taints=effective_taints, labels=effective_labels)
        return
