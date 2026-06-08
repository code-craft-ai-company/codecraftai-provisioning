"""
    .. module:: cloudsharedfilesystem
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral shared filesystem descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.restclient.base.schemaobject import SchemaObject
from ccai.restclient.base.schemafield import Field

from ccai.provisioning.model.exceptions import SchemaValidationError
from ccai.provisioning.model.cloud.validators import (
    validate_name, validate_positive_int
)
from ccai.provisioning.model.cloud.sharedfsmountspec import SharedFsMountSpec


_SUPPORTED_KINDS = (
    "WEKA", "LUSTRE", "VAST", "GPFS", "EFS",
    "FILESTORE", "AZUREFILES", "BEEGFS", "VENUE_NATIVE",
)


class CloudSharedFilesystem(SchemaObject):
    """
        Venue-neutral shared filesystem descriptor.

        v1 supports attach-only (existing_id set) on most venues; v1.5 will add
        provision-and-attach paths.  Either size_tb or existing_id must be set.
    """

    name = Field(str, required=True)
    kind = Field(str, required=True)
    size_tb = Field(int, required=False, default=None)
    throughput_gbps = Field(int, required=False, default=None)
    mount_targets = Field(list, required=False, default=None)
    existing_id = Field(str, required=False, default=None)
    tags = Field(dict, required=False, default=None)

    def __init__(self, *, name: str, kind: str,
                 size_tb: Optional[int] = None,
                 throughput_gbps: Optional[int] = None,
                 mount_targets: Optional[List[SharedFsMountSpec]] = None,
                 existing_id: Optional[str] = None,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a CloudSharedFilesystem.

            :param name: Filesystem name.
            :param kind: One of the supported filesystem kinds.
            :param size_tb: Size in terabytes (None when existing_id is set).
            :param throughput_gbps: Optional throughput hint.
            :param mount_targets: Optional list of SharedFsMountSpec entries.
            :param existing_id: When set, attach-only mode against an existing FS.
            :param tags: Optional flat dict of tag key/value pairs.

            :raises: SchemaValidationError
        """
        validate_name(value=name)

        if kind not in _SUPPORTED_KINDS:
            raise SchemaValidationError(
                "kind must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_KINDS), kind
                )
            )

        if size_tb is None and existing_id is None:
            raise SchemaValidationError(
                "Either size_tb or existing_id must be set."
            )

        if size_tb is not None:
            validate_positive_int(value=size_tb, field_name="size_tb")

        if throughput_gbps is not None:
            validate_positive_int(value=throughput_gbps,
                                  field_name="throughput_gbps")

        effective_mount_targets = mount_targets if mount_targets is not None else []
        effective_tags = tags if tags is not None else {}

        super().__init__(name=name, kind=kind, size_tb=size_tb,
                         throughput_gbps=throughput_gbps,
                         mount_targets=effective_mount_targets,
                         existing_id=existing_id, tags=effective_tags)
        return

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CloudSharedFilesystem":
        """
            Construct from a serialised payload (promotes nested mount targets).

            :param data: Serialised payload.

            :returns: A CloudSharedFilesystem instance.
        """
        if not isinstance(data, dict):
            return data  # type: ignore

        targets_payload = data.get("mount_targets", None)
        promoted_targets: List[SharedFsMountSpec] = []
        if targets_payload is not None:
            for entry in targets_payload:
                if isinstance(entry, SharedFsMountSpec):
                    promoted_targets.append(entry)
                else:
                    promoted_targets.append(SharedFsMountSpec.from_dict(entry))

        rtnval = cls(name=data["name"], kind=data["kind"],
                     size_tb=data.get("size_tb", None),
                     throughput_gbps=data.get("throughput_gbps", None),
                     mount_targets=promoted_targets,
                     existing_id=data.get("existing_id", None),
                     tags=data.get("tags", None))
        return rtnval
