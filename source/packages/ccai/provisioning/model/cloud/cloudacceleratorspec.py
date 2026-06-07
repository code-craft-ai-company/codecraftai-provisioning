"""
    .. module:: cloudacceleratorspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral accelerator descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.exceptions import SchemaValidationError
from ccai.provisioning.model.cloud.validators import validate_positive_int


_SUPPORTED_KINDS = ("GPU", "TPU", "IPU", "ASIC")

_SUPPORTED_INTERCONNECTS = (
    "NONE", "PCIE", "NVLINK", "NVSWITCH", "INFINITY_FABRIC"
)


class CloudAcceleratorSpec(SchemaObject):
    """
        Venue-neutral accelerator specification.

        The model field carries a neutral catalog name (e.g. H100_SXM) that is
        resolved to a venue SKU by the accelerator catalog.
    """

    kind = Field(str, required=True)
    model = Field(str, required=True)
    count = Field(int, required=True)
    interconnect = Field(str, required=False, default="NONE")
    memory_gb = Field(int, required=True)

    def __init__(self, *, kind: str, model: str, count: int,
                 interconnect: str = "NONE", memory_gb: int) -> None:
        """
            Construct a CloudAcceleratorSpec.

            :param kind: One of GPU, TPU, IPU, ASIC.
            :param model: Neutral catalog name (resolved via catalog).
            :param count: Number of accelerators per host; must be > 0.
            :param interconnect: NONE | PCIE | NVLINK | NVSWITCH | INFINITY_FABRIC.
            :param memory_gb: Per-accelerator memory in GB; must be > 0.

            :raises: SchemaValidationError
        """
        if kind not in _SUPPORTED_KINDS:
            raise SchemaValidationError(
                "kind must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_KINDS), kind
                )
            )

        if model is None or len(model) == 0:
            raise SchemaValidationError("model must not be empty.")

        if interconnect not in _SUPPORTED_INTERCONNECTS:
            raise SchemaValidationError(
                "interconnect must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_INTERCONNECTS), interconnect
                )
            )

        validate_positive_int(value=count, field_name="count")
        validate_positive_int(value=memory_gb, field_name="memory_gb")

        super().__init__(kind=kind, model=model, count=count,
                         interconnect=interconnect, memory_gb=memory_gb)
        return
