"""
    .. module:: azuretagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and the Azure
               flat ``tags`` dict shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from automojo.provisioning.venues.azure.azureerrors import AzureValidationError


OWNER_TAG_KEY = "automojo:owned-by"
OWNER_TAG_VALUE = "automojo-provisioning"
RUN_ID_TAG_KEY = "automojo:owner"
RESOURCE_NAME_TAG_KEY = "automojo:resource-name"
RESOURCE_KIND_TAG_KEY = "automojo:resource-kind"

# Azure tag limits.
AZURE_TAG_KEY_MAX = 512
AZURE_TAG_VALUE_MAX = 256


def to_azure(*, neutral_tags: Optional[List[Dict[str, str]]]
             ) -> Dict[str, str]:
    """
        Flatten neutral single-entry tag dicts into a single Azure tags dict.

        Azure represents resource tags as a flat ``Dict[str, str]``; the
        neutral model carries a ``List[Dict[str, str]]`` of single-entry
        dicts.  Any key collision is rejected.

        :param neutral_tags: List of single-entry ``{key: value}`` dicts.

        :returns: A flat ``Dict[str, str]``.
        :raises: AzureValidationError
    """
    if neutral_tags is None:
        rtnval: Dict[str, str] = {}
        return rtnval

    out: Dict[str, str] = {}
    for entry in neutral_tags:
        if not isinstance(entry, dict):
            err_msg_lines = ["Neutral tag entry is not a dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise AzureValidationError(err_msg)

        if len(entry) != 1:
            err_msg_lines = ["Neutral tag entry must be a single-key dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise AzureValidationError(err_msg)

        for key, value in entry.items():
            if not isinstance(key, str) or not isinstance(value, str):
                err_msg_lines = ["Tag key and value must be strings."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg_lines.append("VALUE: {!r}".format(value))
                err_msg = os.linesep.join(err_msg_lines)
                raise AzureValidationError(err_msg)

            if len(key) > AZURE_TAG_KEY_MAX:
                err_msg_lines = ["Tag key exceeds Azure 512-char limit."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise AzureValidationError(err_msg)

            if len(value) > AZURE_TAG_VALUE_MAX:
                err_msg_lines = ["Tag value exceeds Azure 256-char limit."]
                err_msg_lines.append("KEY: {}".format(key))
                err_msg_lines.append("LENGTH: {}".format(len(value)))
                err_msg = os.linesep.join(err_msg_lines)
                raise AzureValidationError(err_msg)

            if key in out:
                err_msg_lines = ["Duplicate tag key in neutral tag set."]
                err_msg_lines.append("KEY: {}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise AzureValidationError(err_msg)

            out[key] = value

    rtnval = out
    return rtnval


def from_azure(*, azure_tags: Optional[Dict[str, str]]
               ) -> List[Dict[str, str]]:
    """
        Convert a flat Azure tags dict back to neutral single-entry dicts.

        :param azure_tags: A flat ``Dict[str, str]`` or None.

        :returns: A key-sorted list of single-entry neutral dicts.
    """
    if azure_tags is None:
        rtnval: List[Dict[str, str]] = []
        return rtnval

    out: List[Dict[str, str]] = []
    for key in sorted(azure_tags.keys()):
        out.append({key: azure_tags[key]})

    rtnval = out
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[List[Dict[str, str]]] = None,
                       defaults: Optional[List[Dict[str, str]]] = None
                       ) -> List[Dict[str, str]]:
    """
        Build the full neutral tag list for a created Azure resource.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: Combined neutral tag list.
    """
    combined: List[Dict[str, str]] = []
    combined.append({OWNER_TAG_KEY: OWNER_TAG_VALUE})
    combined.append({RUN_ID_TAG_KEY: run_id})
    combined.append({RESOURCE_NAME_TAG_KEY: resource_name})
    combined.append({RESOURCE_KIND_TAG_KEY: resource_kind})

    if defaults is not None:
        for entry in defaults:
            combined.append(dict(entry))

    if extra is not None:
        for entry in extra:
            combined.append(dict(entry))

    rtnval = combined
    return rtnval


def azure_tags_for(*, run_id: str, resource_name: str, resource_kind: str,
                   extra: Optional[List[Dict[str, str]]] = None,
                   defaults: Optional[List[Dict[str, str]]] = None
                   ) -> Dict[str, str]:
    """
        Build the flat Azure tags dict for a created resource.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: A flat ``Dict[str, str]``.
        :raises: AzureValidationError
    """
    neutral = base_resource_tags(run_id=run_id, resource_name=resource_name,
                                 resource_kind=resource_kind, extra=extra,
                                 defaults=defaults)
    rtnval = to_azure(neutral_tags=neutral)
    return rtnval
