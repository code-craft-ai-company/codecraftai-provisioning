"""
    .. module:: cloudacceleratorcatalogentry
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: One entry in the venue-neutral accelerator catalog.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.interfaces.schemavalidators import validate_positive_int


_SUPPORTED_KINDS = ("GPU", "TPU", "IPU", "ASIC")

_SUPPORTED_INTERCONNECTS = (
    "NONE", "PCIE", "NVLINK", "NVSWITCH", "INFINITY_FABRIC"
)


class CloudAcceleratorCatalogEntry(SchemaObject):
    """
        One catalog row: neutral name + properties + venue-SKU map.
    """

    neutral_name = Field(str, required=True)
    kind = Field(str, required=True)
    memory_gb = Field(int, required=True)
    interconnect = Field(str, required=True)
    venue_skus = Field(dict, required=True)
    default = Field(bool, required=False, default=False)

    def __init__(self, *, neutral_name: str, kind: str, memory_gb: int,
                 interconnect: str, venue_skus: Dict[str, str],
                 default: bool = False) -> None:
        """
            Construct a catalog entry.

            :param neutral_name: Catalog-unique neutral name.
            :param kind: GPU | TPU | IPU | ASIC.
            :param memory_gb: Per-accelerator memory in GB; must be > 0.
            :param interconnect: NONE | PCIE | NVLINK | NVSWITCH |
                                  INFINITY_FABRIC.
            :param venue_skus: Mapping of venue name → SKU string.
            :param default: Whether this entry is the default for its kind.

            :raises: SchemaValidationError
        """
        if neutral_name is None or len(neutral_name) == 0:
            raise SchemaValidationError("neutral_name must not be empty.")

        if kind not in _SUPPORTED_KINDS:
            raise SchemaValidationError(
                "kind must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_KINDS), kind
                )
            )

        if interconnect not in _SUPPORTED_INTERCONNECTS:
            raise SchemaValidationError(
                "interconnect must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_INTERCONNECTS), interconnect
                )
            )

        validate_positive_int(value=memory_gb, field_name="memory_gb")

        if venue_skus is None or not isinstance(venue_skus, dict):
            raise SchemaValidationError("venue_skus must be a dict.")

        if len(venue_skus) == 0:
            raise SchemaValidationError(
                "venue_skus must contain at least one venue mapping."
            )

        for venue, sku in venue_skus.items():
            if not isinstance(venue, str) or len(venue) == 0:
                raise SchemaValidationError(
                    "venue_skus keys must be non-empty strings."
                )
            if not isinstance(sku, str) or len(sku) == 0:
                raise SchemaValidationError(
                    "venue_skus values must be non-empty strings."
                )

        super().__init__(neutral_name=neutral_name, kind=kind,
                         memory_gb=memory_gb, interconnect=interconnect,
                         venue_skus=dict(venue_skus), default=default)
        return
