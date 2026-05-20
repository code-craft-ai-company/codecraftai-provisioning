"""
    .. module:: ociidempotency
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Read-by-freeform-tag helpers for idempotent OCI resource lookup.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, Optional

from automojo.provisioning.venues.oracle.ocitagging import (
    OWNER_TAG_KEY, OWNER_TAG_VALUE, RESOURCE_NAME_TAG_KEY, RUN_ID_TAG_KEY
)


def _freeform_of(*, entity: Any) -> Dict[str, str]:
    """
        Read the ``freeform_tags`` attribute from an OCI SDK model object.

        :param entity: An OCI SDK model object (or dict-shaped stand-in).

        :returns: A flat ``{key: value}`` dict (empty when absent).
    """
    if entity is None:
        rtnval: Dict[str, str] = {}
        return rtnval
    if isinstance(entity, dict):
        tags = entity.get("freeform_tags", None)
    else:
        tags = getattr(entity, "freeform_tags", None)
    if tags is None:
        rtnval = {}
        return rtnval
    rtnval = dict(tags)
    return rtnval


def is_owned(*, entity: Any) -> bool:
    """
        Check whether an OCI entity carries the owner-tag pair.

        :param entity: An OCI SDK model object.

        :returns: True when owned by automojo-provisioning.
    """
    flat = _freeform_of(entity=entity)
    rtnval = flat.get(OWNER_TAG_KEY, None) == OWNER_TAG_VALUE
    return rtnval


def belongs_to_run(*, entity: Any, run_id: str) -> bool:
    """
        Check whether an OCI entity carries the (owner, run-id) pair.

        :param entity: An OCI SDK model object.
        :param run_id: Expected run-id value.

        :returns: True when owned by automojo and matching the run id.
    """
    flat = _freeform_of(entity=entity)
    if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
        rtnval = False
        return rtnval
    rtnval = flat.get(RUN_ID_TAG_KEY, None) == run_id
    return rtnval


def matches_resource(*, entity: Any, run_id: str,
                     resource_name: str) -> bool:
    """
        Check whether an OCI entity matches a specific (run, name) pair.

        :param entity: An OCI SDK model object.
        :param run_id: Expected run-id value.
        :param resource_name: Expected neutral resource name.

        :returns: True when the entity is the owned resource named.
    """
    if not belongs_to_run(entity=entity, run_id=run_id):
        rtnval = False
        return rtnval
    flat = _freeform_of(entity=entity)
    rtnval = flat.get(RESOURCE_NAME_TAG_KEY, None) == resource_name
    return rtnval


def resource_name_of(*, entity: Any) -> Optional[str]:
    """
        Return the recorded neutral resource-name tag, if any.

        :param entity: An OCI SDK model object.

        :returns: The resource name or None.
    """
    flat = _freeform_of(entity=entity)
    value = flat.get(RESOURCE_NAME_TAG_KEY, None)
    if value is None or len(value) == 0:
        rtnval: Optional[str] = None
        return rtnval
    rtnval = value
    return rtnval
