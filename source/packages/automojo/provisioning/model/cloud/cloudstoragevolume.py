"""
    .. module:: cloudstoragevolume
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral block storage volume descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.cloud.validators import (
    validate_name, validate_positive_int
)


class CloudStorageVolume(SchemaObject):
    """
        Venue-neutral block storage volume descriptor.

        size_gb must be > 0; type is a venue-mapped neutral hint.
    """

    name = Field(str, required=True)
    size_gb = Field(int, required=True)
    type = Field(str, required=True)
    attached_to = Field(str, required=False, default=None)
    mount = Field(str, required=False, default=None)
    tags = Field(list, required=False, default=None)

    def __init__(self, *, name: str, size_gb: int, type: str,
                 attached_to: Optional[str] = None,
                 mount: Optional[str] = None,
                 tags: Optional[List[Dict[str, str]]] = None) -> None:
        """
            Construct a CloudStorageVolume.

            :param name: Volume name.
            :param size_gb: Size in gigabytes; must be > 0.
            :param type: Neutral volume type hint (ssd, hdd, nvme, ...).
            :param attached_to: Optional name of attaching CloudInstance.
            :param mount: Optional mount path within the attached instance.
            :param tags: Optional list of single-entry tag dicts.

            :raises: SchemaValidationError
        """
        validate_name(value=name)
        validate_positive_int(value=size_gb, field_name="size_gb")

        if type is None or len(type) == 0:
            from automojo.provisioning.model.exceptions import SchemaValidationError
            raise SchemaValidationError("type must not be empty.")

        effective_tags = tags if tags is not None else []

        super().__init__(name=name, size_gb=size_gb, type=type,
                         attached_to=attached_to, mount=mount, tags=effective_tags)
        return
