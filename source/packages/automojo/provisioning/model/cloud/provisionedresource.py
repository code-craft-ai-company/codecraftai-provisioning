"""
    .. module:: provisionedresource
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: ProvisionedResource record describing one realised resource.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError


class ProvisionedResource(SchemaObject):
    """
        One resource that exists in a venue after a successful apply.

        Carries the venue-neutral kind, the resource name, the venue-side
        identifier, an attributes bag (provider-specific facts: ip
        addresses, ids, az, image-id, etc.), and the tag set the provisioner
        used to identify ownership.
    """

    kind = Field(str, required=True)
    name = Field(str, required=True)
    venue_id = Field(str, required=True)
    attributes = Field(dict, required=False, default=None)
    tags = Field(list, required=False, default=None)

    def __init__(self, *, kind: str, name: str, venue_id: str,
                 attributes: Optional[Dict[str, Any]] = None,
                 tags: Optional[List[Dict[str, str]]] = None) -> None:
        """
            Construct a ProvisionedResource.

            :param kind: Venue-neutral resource kind string.
            :param name: Logical resource name (matches the spec).
            :param venue_id: Venue-side identifier returned by the API.
            :param attributes: Provider-specific facts.
            :param tags: Ownership/tag-set list.

            :raises: SchemaValidationError
        """
        if kind is None or len(kind) == 0:
            raise SchemaValidationError("kind must not be empty.")
        if name is None or len(name) == 0:
            raise SchemaValidationError("name must not be empty.")
        if venue_id is None or len(venue_id) == 0:
            raise SchemaValidationError("venue_id must not be empty.")

        effective_attrs = attributes if attributes is not None else {}
        effective_tags = tags if tags is not None else []

        super().__init__(kind=kind, name=name, venue_id=venue_id,
                         attributes=effective_attrs, tags=effective_tags)
        return
