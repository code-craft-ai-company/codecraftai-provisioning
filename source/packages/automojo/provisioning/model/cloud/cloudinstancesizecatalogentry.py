"""
    .. module:: cloudinstancesizecatalogentry
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: One entry in the venue-neutral instance-size catalog.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.validators import validate_positive_int


_SUPPORTED_FAMILIES = ("general", "compute", "memory")

_SUPPORTED_SIZES = ("small", "medium", "large", "xlarge", "2xlarge")


class CloudInstanceSizeCatalogEntry(SchemaObject):
    """
        One catalog row: neutral size token + shape metadata + venue-SKU map.
    """

    token = Field(str, required=True)
    vcpu = Field(int, required=True)
    memory_gb = Field(int, required=True)
    venue_skus = Field(dict, required=True)

    def __init__(self, *, token: str, vcpu: int, memory_gb: int,
                 venue_skus: Dict[str, str]) -> None:
        """
            Construct a catalog entry.

            :param token: Catalog-unique neutral size token of the form
                          ``<family>.<size>``.
            :param vcpu: Neutral vCPU count for the shape; must be > 0.
            :param memory_gb: Neutral RAM in GB for the shape; must be > 0.
            :param venue_skus: Mapping of venue name -> native SKU string.

            :raises: SchemaValidationError
        """
        if token is None or len(token) == 0:
            raise SchemaValidationError("token must not be empty.")

        parts = token.split(".")
        if len(parts) != 2:
            raise SchemaValidationError(
                "token must be of the form '<family>.<size>', got {!r}".format(
                    token
                )
            )

        family, size = parts
        if family not in _SUPPORTED_FAMILIES:
            raise SchemaValidationError(
                "token family must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_FAMILIES), family
                )
            )

        if size not in _SUPPORTED_SIZES:
            raise SchemaValidationError(
                "token size must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_SIZES), size
                )
            )

        validate_positive_int(value=vcpu, field_name="vcpu")
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

        super().__init__(token=token, vcpu=vcpu, memory_gb=memory_gb,
                         venue_skus=dict(venue_skus))
        return
