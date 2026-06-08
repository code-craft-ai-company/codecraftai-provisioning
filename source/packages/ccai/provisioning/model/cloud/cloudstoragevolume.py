"""
    .. module:: cloudstoragevolume
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral block storage volume descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, Optional, Union

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.exceptions import SchemaSemanticError
from ccai.provisioning.model.cloud.storageclass import StorageClass
from ccai.provisioning.model.cloud.validators import (
    validate_name, validate_positive_int
)


def _coerce_storage_class(*, value: Union[StorageClass, str]) -> StorageClass:
    """
        Coerce an enum-or-string value into a StorageClass member.

        :param value: A StorageClass member or its string value.

        :returns: The resolved StorageClass member.
        :raises: SchemaSemanticError
    """
    if isinstance(value, StorageClass):
        rtnval = value
        return rtnval

    if isinstance(value, str):
        normalized = value.strip().lower()
        for member in StorageClass:
            if member.value == normalized:
                rtnval = member
                return rtnval

    supported = [member.value for member in StorageClass]
    err_msg_lines = ["Unknown storage class."]
    err_msg_lines.append("VALUE: {!r}".format(value))
    err_msg_lines.append("SUPPORTED: {}".format(", ".join(supported)))
    err_msg = os.linesep.join(err_msg_lines)
    raise SchemaSemanticError(err_msg)


class CloudStorageVolume(SchemaObject):
    """
        Venue-neutral block storage volume descriptor.

        size_gb must be > 0; storage_class is a venue-mapped neutral hint.
    """

    name = Field(str, required=True)
    size_gb = Field(int, required=True)
    storage_class = Field(str, required=True)
    attached_to = Field(str, required=False, default=None)
    mount = Field(str, required=False, default=None)
    tags = Field(dict, required=False, default=None)

    def __init__(self, *, name: str, size_gb: int,
                 storage_class: Union[StorageClass, str] = StorageClass.STANDARD,
                 attached_to: Optional[str] = None,
                 mount: Optional[str] = None,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a CloudStorageVolume.

            :param name: Volume name.
            :param size_gb: Size in gigabytes; must be > 0.
            :param storage_class: Neutral storage class; either a StorageClass
                                  member or its lowercase string value.
            :param attached_to: Optional name of attaching CloudInstance.
            :param mount: Optional mount path within the attached instance.
            :param tags: Optional flat dict of tag key/value pairs.

            :raises: SchemaValidationError, SchemaSemanticError
        """
        validate_name(value=name)
        validate_positive_int(value=size_gb, field_name="size_gb")

        effective_class = _coerce_storage_class(value=storage_class)

        effective_tags = tags if tags is not None else {}

        super().__init__(name=name, size_gb=size_gb,
                         storage_class=effective_class,
                         attached_to=attached_to, mount=mount,
                         tags=effective_tags)
        return
