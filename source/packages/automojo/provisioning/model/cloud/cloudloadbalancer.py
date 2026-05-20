"""
    .. module:: cloudloadbalancer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Venue-neutral load balancer descriptor (flagged stub for v1).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.restclient.base.schemaobject import SchemaObject
from automojo.restclient.base.schemafield import Field

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.validators import validate_name


_SUPPORTED_SCHEMES = ("internet-facing", "internal")


class CloudLoadBalancer(SchemaObject):
    """
        Venue-neutral load balancer descriptor.

        The lifecycle layer treats this as a flagged stub in v1; the model class
        ships the shape so spec authors can declare load balancers today.
    """

    name = Field(str, required=True)
    scheme = Field(str, required=True)
    listeners = Field(list, required=False, default=None)
    target_instance_names = Field(list, required=False, default=None)
    tags = Field(list, required=False, default=None)

    def __init__(self, *, name: str, scheme: str,
                 listeners: Optional[List[Dict[str, Any]]] = None,
                 target_instance_names: Optional[List[str]] = None,
                 tags: Optional[List[Dict[str, str]]] = None) -> None:
        """
            Construct a CloudLoadBalancer.

            :param name: Load balancer name.
            :param scheme: One of internet-facing or internal.
            :param listeners: Optional list of listener dicts.
            :param target_instance_names: Optional list of target instance names.
            :param tags: Optional list of single-entry tag dicts.

            :raises: SchemaValidationError
        """
        validate_name(value=name)

        if scheme not in _SUPPORTED_SCHEMES:
            raise SchemaValidationError(
                "scheme must be one of {}, got {!r}".format(
                    ", ".join(_SUPPORTED_SCHEMES), scheme
                )
            )

        effective_listeners = listeners if listeners is not None else []
        effective_targets = target_instance_names if target_instance_names is not None else []
        effective_tags = tags if tags is not None else []

        super().__init__(name=name, scheme=scheme, listeners=effective_listeners,
                         target_instance_names=effective_targets, tags=effective_tags)
        return
