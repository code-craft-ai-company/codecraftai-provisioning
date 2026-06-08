"""
    .. module:: awsidempotency
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Read-by-tag helpers for idempotent AWS resource lookup.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.venues.aws.awstagging import (
    OWNER_TAG_KEY, OWNER_TAG_VALUE, RESOURCE_NAME_TAG_KEY, RUN_ID_TAG_KEY
)


def owner_filters(*, run_id: str, resource_name: Optional[str] = None
                  ) -> List[Dict[str, Any]]:
    """
        Build EC2 describe-style filter dicts that select owner+run+name.

        :param run_id: The provisioning run identifier.
        :param resource_name: Optional neutral resource name.

        :returns: List of filter dicts in the AWS ``Filters`` shape.
    """
    filters: List[Dict[str, Any]] = []
    filters.append({"Name": "tag:{}".format(OWNER_TAG_KEY),
                    "Values": [OWNER_TAG_VALUE]})
    filters.append({"Name": "tag:{}".format(RUN_ID_TAG_KEY),
                    "Values": [run_id]})
    if resource_name is not None:
        filters.append({"Name": "tag:{}".format(RESOURCE_NAME_TAG_KEY),
                        "Values": [resource_name]})
    rtnval = filters
    return rtnval


def tag_dict_from_aws(*, aws_tags: Optional[List[Dict[str, str]]]
                      ) -> Dict[str, str]:
    """
        Build a flat ``{key: value}`` dict from an AWS Tags list.

        :param aws_tags: AWS Tags list or None.

        :returns: A flat dict (empty when input is None).
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


def is_owned(*, aws_tags: Optional[List[Dict[str, str]]]) -> bool:
    """
        Check whether a tag list carries the owner-tag pair.

        :param aws_tags: AWS Tags list.

        :returns: True when owned by codecraftai-provisioning.
    """
    flat = tag_dict_from_aws(aws_tags=aws_tags)
    rtnval = flat.get(OWNER_TAG_KEY, None) == OWNER_TAG_VALUE
    return rtnval


def belongs_to_run(*, aws_tags: Optional[List[Dict[str, str]]],
                   run_id: str) -> bool:
    """
        Check whether a tag list carries the (owner, run-id) pair.

        :param aws_tags: AWS Tags list.
        :param run_id: Expected run-id value.

        :returns: True when owned by ccai and matching the run id.
    """
    flat = tag_dict_from_aws(aws_tags=aws_tags)
    if flat.get(OWNER_TAG_KEY, None) != OWNER_TAG_VALUE:
        rtnval = False
        return rtnval
    rtnval = flat.get(RUN_ID_TAG_KEY, None) == run_id
    return rtnval
