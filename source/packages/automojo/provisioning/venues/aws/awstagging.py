"""
    .. module:: awstagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and AWS Tags shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.aws.awserrors import AwsValidationError


OWNER_TAG_KEY = "automojo:owned-by"
OWNER_TAG_VALUE = "automojo-provisioning"
RUN_ID_TAG_KEY = "automojo:owner"
RESOURCE_NAME_TAG_KEY = "automojo:resource-name"
RESOURCE_KIND_TAG_KEY = "automojo:resource-kind"

AWS_TAG_VALUE_MAX = 256
AWS_TAG_KEY_MAX = 128


def to_aws(*, neutral_tags: Optional[List[Dict[str, str]]]
           ) -> List[Dict[str, str]]:
    """
        Convert neutral single-entry tag dicts to the AWS Tags wire shape.

        :param neutral_tags: List of single-entry ``{key: value}`` dicts.

        :returns: A list of ``{"Key": k, "Value": v}`` dicts, key-sorted.
        :raises: AwsValidationError
    """
    if neutral_tags is None:
        rtnval: List[Dict[str, str]] = []
        return rtnval

    pairs: List[Dict[str, str]] = []
    seen_keys: Dict[str, str] = {}
    for entry in neutral_tags:
        if not isinstance(entry, dict):
            err_msg_lines = ["Neutral tag entry is not a dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise AwsValidationError(err_msg)
        if len(entry) != 1:
            err_msg_lines = ["Neutral tag entry must be a single-key dict."]
            err_msg_lines.append("ENTRY: {!r}".format(entry))
            err_msg = os.linesep.join(err_msg_lines)
            raise AwsValidationError(err_msg)

        for key, value in entry.items():
            if not isinstance(key, str) or not isinstance(value, str):
                err_msg_lines = ["Tag key and value must be strings."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg_lines.append("VALUE: {!r}".format(value))
                err_msg = os.linesep.join(err_msg_lines)
                raise AwsValidationError(err_msg)

            if len(key) > AWS_TAG_KEY_MAX:
                err_msg_lines = ["Tag key exceeds AWS 128-char limit."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise AwsValidationError(err_msg)

            if len(value) > AWS_TAG_VALUE_MAX:
                err_msg_lines = ["Tag value exceeds AWS 256-char limit."]
                err_msg_lines.append("KEY: {}".format(key))
                err_msg_lines.append("LENGTH: {}".format(len(value)))
                err_msg = os.linesep.join(err_msg_lines)
                raise AwsValidationError(err_msg)

            if key in seen_keys:
                err_msg_lines = ["Duplicate tag key in neutral tag set."]
                err_msg_lines.append("KEY: {}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise AwsValidationError(err_msg)

            seen_keys[key] = value
            pairs.append({"Key": key, "Value": value})

    pairs.sort(key=lambda d: d["Key"])
    rtnval = pairs
    return rtnval


def from_aws(*, aws_tags: Optional[List[Dict[str, str]]]
             ) -> List[Dict[str, str]]:
    """
        Convert an AWS Tags list back to neutral single-entry dicts.

        :param aws_tags: List of ``{"Key": k, "Value": v}`` dicts.

        :returns: A key-sorted list of single-entry neutral dicts.
    """
    if aws_tags is None:
        rtnval: List[Dict[str, str]] = []
        return rtnval

    sorted_tags = sorted(aws_tags, key=lambda d: d.get("Key", ""))
    out: List[Dict[str, str]] = []
    for entry in sorted_tags:
        key = entry.get("Key", "")
        value = entry.get("Value", "")
        out.append({key: value})

    rtnval = out
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[List[Dict[str, str]]] = None,
                       defaults: Optional[List[Dict[str, str]]] = None
                       ) -> List[Dict[str, str]]:
    """
        Build the full neutral tag list for a created AWS resource.

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


def tag_specifications(*, resource_type: str,
                       neutral_tags: List[Dict[str, str]]
                       ) -> List[Dict[str, Any]]:
    """
        Build the ``TagSpecifications`` argument for an EC2 create call.

        :param resource_type: AWS resource type (e.g. ``vpc``, ``subnet``).
        :param neutral_tags: Neutral tag list to translate.

        :returns: A single-element TagSpecifications list.
    """
    aws_tags = to_aws(neutral_tags=neutral_tags)
    rtnval = [{"ResourceType": resource_type, "Tags": aws_tags}]
    return rtnval
