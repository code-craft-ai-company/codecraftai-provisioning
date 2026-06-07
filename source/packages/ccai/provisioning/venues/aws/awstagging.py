"""
    .. module:: awstagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and AWS Tags shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from ccai.provisioning.venues.aws.awserrors import AwsValidationError


OWNER_TAG_KEY = "ccai:owned-by"
OWNER_TAG_VALUE = "codecraftai-provisioning"
RUN_ID_TAG_KEY = "ccai:owner"
RESOURCE_NAME_TAG_KEY = "ccai:resource-name"
RESOURCE_KIND_TAG_KEY = "ccai:resource-kind"

AWS_TAG_VALUE_MAX = 256
AWS_TAG_KEY_MAX = 128


def to_aws(*, neutral_tags: Optional[Dict[str, str]]
           ) -> List[Dict[str, str]]:
    """
        Convert a neutral flat tag dict to the AWS Tags wire shape.

        :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

        :returns: A list of ``{"Key": k, "Value": v}`` dicts, key-sorted.
        :raises: AwsValidationError
    """
    if neutral_tags is None:
        rtnval: List[Dict[str, str]] = []
        return rtnval

    pairs: List[Dict[str, str]] = []
    for key, value in neutral_tags.items():
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

        pairs.append({"Key": key, "Value": value})

    pairs.sort(key=lambda d: d["Key"])
    rtnval = pairs
    return rtnval


def from_aws(*, aws_tags: Optional[List[Dict[str, str]]]
             ) -> Dict[str, str]:
    """
        Convert an AWS Tags list back to a neutral flat tag dict.

        :param aws_tags: List of ``{"Key": k, "Value": v}`` dicts.

        :returns: A neutral flat ``{key: value}`` dict.
    """
    out: Dict[str, str] = {}
    if aws_tags is None:
        rtnval = out
        return rtnval

    for entry in aws_tags:
        key = entry.get("Key", "")
        value = entry.get("Value", "")
        out[key] = value

    rtnval = out
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[Dict[str, str]] = None,
                       defaults: Optional[Dict[str, str]] = None
                       ) -> Dict[str, str]:
    """
        Build the full neutral tag dict for a created AWS resource.

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


def tag_specifications(*, resource_type: str,
                       neutral_tags: Dict[str, str]
                       ) -> List[Dict[str, Any]]:
    """
        Build the ``TagSpecifications`` argument for an EC2 create call.

        :param resource_type: AWS resource type (e.g. ``vpc``, ``subnet``).
        :param neutral_tags: Neutral flat tag dict to translate.

        :returns: A single-element TagSpecifications list.
    """
    aws_tags = to_aws(neutral_tags=neutral_tags)
    rtnval = [{"ResourceType": resource_type, "Tags": aws_tags}]
    return rtnval
