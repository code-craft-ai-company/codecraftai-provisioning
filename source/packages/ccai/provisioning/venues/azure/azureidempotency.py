"""
    .. module:: azureidempotency
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Read-by-tag helpers for idempotent Azure resource lookup.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, Optional

from ccai.provisioning.venues.azure.azuretagging import (
    OWNER_TAG_KEY, OWNER_TAG_VALUE, RESOURCE_NAME_TAG_KEY, RUN_ID_TAG_KEY
)


def tag_dict_from_azure(*, azure_tags: Optional[Dict[str, str]]
                        ) -> Dict[str, str]:
    """
        Return a defensive copy of an Azure tags dict.

        :param azure_tags: The Azure ``tags`` dict or None.

        :returns: A flat dict (empty when input is None).
    """
    if azure_tags is None:
        rtnval: Dict[str, str] = {}
        return rtnval
    rtnval = dict(azure_tags)
    return rtnval


def is_owned(*, azure_tags: Optional[Dict[str, str]]) -> bool:
    """
        Check whether a tags dict carries the owner-tag pair.

        :param azure_tags: The Azure ``tags`` dict.

        :returns: True when owned by codecraftai-provisioning.
    """
    flat = tag_dict_from_azure(azure_tags=azure_tags)
    rtnval = flat.get(OWNER_TAG_KEY, None) == OWNER_TAG_VALUE
    return rtnval


def belongs_to_run(*, azure_tags: Optional[Dict[str, str]],
                   run_id: str) -> bool:
    """
        Check whether a tags dict carries the (owner, run-id) pair.

        :param azure_tags: The Azure ``tags`` dict.
        :param run_id: Expected run-id value.

        :returns: True when owned by ccai and matching the run id.
    """
    flat = tag_dict_from_azure(azure_tags=azure_tags)
    if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
        rtnval = False
        return rtnval
    rtnval = flat.get(RUN_ID_TAG_KEY, None) == run_id
    return rtnval


def matches_run_and_name(*, azure_tags: Optional[Dict[str, str]],
                         run_id: str, resource_name: str) -> bool:
    """
        Check whether a tags dict matches the (owner, run-id, name) triple.

        :param azure_tags: The Azure ``tags`` dict.
        :param run_id: Expected run-id value.
        :param resource_name: Expected neutral resource name.

        :returns: True when all three tags match.
    """
    flat = tag_dict_from_azure(azure_tags=azure_tags)
    if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
        rtnval = False
        return rtnval
    if flat.get(RUN_ID_TAG_KEY, None) != run_id:
        rtnval = False
        return rtnval
    rtnval = flat.get(RESOURCE_NAME_TAG_KEY, None) == resource_name
    return rtnval


def get_or_none(*, getter: Any, **kwargs: Any) -> Optional[Any]:
    """
        Invoke an Azure ``.get(...)`` style call and translate the
        ``ResourceNotFoundError`` absence signal into ``None``.

        :param getter: A zero-or-more-arg callable performing the lookup.
        :param kwargs: Keyword arguments forwarded to ``getter``.

        :returns: The looked-up object, or None when absent.
    """
    from azure.core.exceptions import ResourceNotFoundError

    try:
        result = getter(**kwargs)
    except ResourceNotFoundError:
        rtnval: Optional[Any] = None
        return rtnval

    rtnval = result
    return rtnval
