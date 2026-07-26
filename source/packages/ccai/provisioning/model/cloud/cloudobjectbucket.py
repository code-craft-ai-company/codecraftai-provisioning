"""
    .. module:: cloudobjectbucket
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral object storage bucket descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, Optional

from ccai.interfaces.schemaobject import SchemaObject
from ccai.interfaces.schemafield import Field

from ccai.interfaces.schemavalidators import validate_name


class CloudObjectBucket(SchemaObject):
    """
        Venue-neutral object storage bucket descriptor.
    """

    name = Field(str, required=True)
    region = Field(str, required=True)
    versioning = Field(bool, required=False, default=False)
    public = Field(bool, required=False, default=False)
    tags = Field(dict, required=False, default=None)

    def __init__(self, *, name: str, region: str,
                 versioning: bool = False, public: bool = False,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a CloudObjectBucket.

            :param name: Bucket name.
            :param region: Region identifier.
            :param versioning: Whether object versioning is enabled.
            :param public: Whether the bucket is publicly accessible.
            :param tags: Optional flat dict of tag key/value pairs.

            :raises: SchemaValidationError
        """
        validate_name(value=name)
        validate_name(value=region)

        effective_tags = tags if tags is not None else {}

        super().__init__(name=name, region=region, versioning=versioning,
                         public=public, tags=effective_tags)
        return
