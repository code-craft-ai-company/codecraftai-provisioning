"""
    .. module:: cloudobjectbucket
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral object storage bucket descriptor.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.cloud.validators import validate_name


class CloudObjectBucket(SchemaObject):
    """
        Venue-neutral object storage bucket descriptor.
    """

    name = Field(str, required=True)
    region = Field(str, required=True)
    versioning = Field(bool, required=False, default=False)
    public = Field(bool, required=False, default=False)
    tags = Field(list, required=False, default=None)

    def __init__(self, *, name: str, region: str,
                 versioning: bool = False, public: bool = False,
                 tags: Optional[List[Dict[str, str]]] = None) -> None:
        """
            Construct a CloudObjectBucket.

            :param name: Bucket name.
            :param region: Region identifier.
            :param versioning: Whether object versioning is enabled.
            :param public: Whether the bucket is publicly accessible.
            :param tags: Optional list of single-entry tag dicts.

            :raises: SchemaValidationError
        """
        validate_name(value=name)
        validate_name(value=region)

        effective_tags = tags if tags is not None else []

        super().__init__(name=name, region=region, versioning=versioning,
                         public=public, tags=effective_tags)
        return
