"""
    .. module:: cloudinterconnect
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral host-fabric interconnect descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.exceptions import SchemaValidationError
from ccai.provisioning.model.cloud.validators import validate_positive_int


_SUPPORTED_KINDS = (
    "ETHERNET",
    "ROCE",
    "INFINIBAND_HDR",
    "INFINIBAND_NDR",
    "INFINIBAND_XDR",
    "EFA",
    "OCI_RDMA",
)

_SUPPORTED_TOPOLOGIES = ("NONE", "RAIL_OPTIMIZED", "FAT_TREE", "DRAGONFLY")


class CloudInterconnect(SchemaObject):
    """
        Venue-neutral inter-host fabric descriptor.

        Carries every value the framework knows about on day one; venue support
        is checked at validate-time, not at construction time.
    """

    kind = Field(str, required=True)
    bandwidth_gbps = Field(int, required=True)
    topology = Field(str, required=False, default="NONE")

    def __init__(self, *, kind: str, bandwidth_gbps: int,
                 topology: str = "NONE") -> None:
        """
            Construct a CloudInterconnect.

            :param kind: Interconnect fabric kind.
            :param bandwidth_gbps: Bandwidth in gigabits per second; must be > 0.
            :param topology: NONE | RAIL_OPTIMIZED | FAT_TREE | DRAGONFLY.

            :raises: SchemaValidationError
        """
        if kind not in _SUPPORTED_KINDS:
            raise SchemaValidationError(
                "kind must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_KINDS), kind
                )
            )

        if topology not in _SUPPORTED_TOPOLOGIES:
            raise SchemaValidationError(
                "topology must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_TOPOLOGIES), topology
                )
            )

        validate_positive_int(value=bandwidth_gbps, field_name="bandwidth_gbps")

        super().__init__(kind=kind, bandwidth_gbps=bandwidth_gbps,
                         topology=topology)
        return
