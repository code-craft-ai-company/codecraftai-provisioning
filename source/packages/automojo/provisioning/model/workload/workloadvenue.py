"""
    .. module:: workloadvenue
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Workload venue descriptor parallel to CloudVenue.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, Optional, Union

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.validators import validate_name
from automojo.provisioning.model.workload.workloadvenuekind import WorkloadVenueKind


class WorkloadVenue(SchemaObject):
    """
        Declarative descriptor for a workload venue (K8s cluster, Slurm head node,
        etc.) parallel to CloudVenue.
    """

    name = Field(str, required=True)
    kind = Field(str, required=True)
    credential_ref = Field(str, required=True)
    endpoint = Field(str, required=False, default=None)
    tags = Field(dict, required=False, default=None)

    def __init__(self, *, name: str,
                 kind: Union[WorkloadVenueKind, str],
                 credential_ref: str,
                 endpoint: Optional[str] = None,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a WorkloadVenue.

            :param name: Venue name.
            :param kind: WorkloadVenueKind value.
            :param credential_ref: Credential vault reference name.
            :param endpoint: Optional API endpoint URL.
            :param tags: Optional flat dict of tag key/value pairs.

            :raises: SchemaValidationError
        """
        validate_name(value=name)
        validate_name(value=credential_ref)

        if isinstance(kind, WorkloadVenueKind):
            kind_value = kind.value
        elif isinstance(kind, str):
            try:
                kind_value = WorkloadVenueKind(kind).value
            except ValueError:
                supported = ", ".join(k.value for k in WorkloadVenueKind)
                raise SchemaValidationError(
                    "kind must be one of {}, got {!r}".format(supported, kind)
                ) from None
        else:
            raise SchemaValidationError(
                "kind must be a WorkloadVenueKind or string."
            )

        effective_tags = tags if tags is not None else {}

        super().__init__(name=name, kind=kind_value,
                         credential_ref=credential_ref,
                         endpoint=endpoint, tags=effective_tags)
        return
