"""
    .. module:: azuretagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and the Azure
               flat ``tags`` dict shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, Optional

from ccai.provisioning.venues.azure.azureerrors import AzureValidationError


OWNER_TAG_KEY = "ccai:owned-by"
OWNER_TAG_VALUE = "codecraftai-provisioning"
RUN_ID_TAG_KEY = "ccai:owner"
RESOURCE_NAME_TAG_KEY = "ccai:resource-name"
RESOURCE_KIND_TAG_KEY = "ccai:resource-kind"

# Azure tag limits.
AZURE_TAG_KEY_MAX = 512
AZURE_TAG_VALUE_MAX = 256


def to_azure(*, neutral_tags: Optional[Dict[str, str]]
             ) -> Dict[str, str]:
    """
        Convert a neutral flat tag dict into an Azure tags dict.

        Azure represents resource tags as a flat ``Dict[str, str]``, which
        matches the neutral tag shape directly.

        :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

        :returns: A flat ``Dict[str, str]``.
        :raises: AzureValidationError
    """
    if neutral_tags is None:
        rtnval: Dict[str, str] = {}
        return rtnval

    out: Dict[str, str] = {}
    for key, value in neutral_tags.items():
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

        out[key] = value

    rtnval = out
    return rtnval


def from_azure(*, azure_tags: Optional[Dict[str, str]]
               ) -> Dict[str, str]:
    """
        Convert a flat Azure tags dict back to a neutral flat tag dict.

        :param azure_tags: A flat ``Dict[str, str]`` or None.

        :returns: A neutral flat ``{key: value}`` dict.
    """
    out: Dict[str, str] = {}
    if azure_tags is None:
        rtnval = out
        return rtnval

    for key in sorted(azure_tags.keys()):
        out[key] = azure_tags[key]

    rtnval = out
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[Dict[str, str]] = None,
                       defaults: Optional[Dict[str, str]] = None
                       ) -> Dict[str, str]:
    """
        Build the full neutral tag dict for a created Azure resource.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: Combined neutral flat tag dict.
    """
    combined: Dict[str, str] = {}
    combined[OWNER_TAG_KEY] = OWNER_TAG_VALUE
    combined[RUN_ID_TAG_KEY] = run_id
    combined[RESOURCE_NAME_TAG_KEY] = resource_name
    combined[RESOURCE_KIND_TAG_KEY] = resource_kind

    if defaults is not None:
        for key, value in defaults.items():
            combined[key] = value

    if extra is not None:
        for key, value in extra.items():
            combined[key] = value

    rtnval = combined
    return rtnval


def azure_tags_for(*, run_id: str, resource_name: str, resource_kind: str,
                   extra: Optional[Dict[str, str]] = None,
                   defaults: Optional[Dict[str, str]] = None
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
