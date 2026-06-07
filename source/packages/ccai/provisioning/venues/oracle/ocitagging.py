"""
    .. module:: ocitagging
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and the OCI
               freeform-tags shape (a flat ``Dict[str, str]``).

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, Optional

from ccai.provisioning.venues.oracle.ocierrors import OciValidationError


OWNER_TAG_KEY = "ccai_owned-by"
OWNER_TAG_VALUE = "codecraftai-provisioning"
RUN_ID_TAG_KEY = "ccai_run-id"
RESOURCE_NAME_TAG_KEY = "ccai_resource-name"
RESOURCE_KIND_TAG_KEY = "ccai_resource-kind"

# OCI freeform-tag limits.
OCI_TAG_KEY_MAX = 100
OCI_TAG_VALUE_MAX = 256


def to_freeform(*, neutral_tags: Optional[Dict[str, str]]
                ) -> Dict[str, str]:
    """
        Convert a neutral flat tag dict to the OCI freeform-tags shape.

        OCI freeform tags are a flat ``Dict[str, str]``, which matches the
        neutral tag shape directly.

        :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

        :returns: A flat ``{key: value}`` dict.
        :raises: OciValidationError
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
            raise OciValidationError(err_msg)

        if len(key) > OCI_TAG_KEY_MAX:
            err_msg_lines = ["Tag key exceeds OCI 100-char limit."]
            err_msg_lines.append("KEY: {!r}".format(key))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg)

        if len(value) > OCI_TAG_VALUE_MAX:
            err_msg_lines = ["Tag value exceeds OCI 256-char limit."]
            err_msg_lines.append("KEY: {}".format(key))
            err_msg_lines.append("LENGTH: {}".format(len(value)))
            err_msg = os.linesep.join(err_msg_lines)
            raise OciValidationError(err_msg)

        out[key] = value

    rtnval = out
    return rtnval


def from_freeform(*, freeform_tags: Optional[Dict[str, str]]
                  ) -> Dict[str, str]:
    """
        Convert an OCI freeform-tags dict back to a neutral flat tag dict.

        :param freeform_tags: A flat ``{key: value}`` dict.

        :returns: A neutral flat ``{key: value}`` dict.
    """
    out: Dict[str, str] = {}
    if freeform_tags is None:
        rtnval = out
        return rtnval

    for key in sorted(freeform_tags.keys()):
        out[key] = freeform_tags[key]

    rtnval = out
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[Dict[str, str]] = None,
                       defaults: Optional[Dict[str, str]] = None
                       ) -> Dict[str, str]:
    """
        Build the full neutral tag dict for a created OCI resource.

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


def freeform_for_resource(*, run_id: str, resource_name: str,
                          resource_kind: str,
                          extra: Optional[Dict[str, str]] = None,
                          defaults: Optional[Dict[str, str]] = None
                          ) -> Dict[str, str]:
    """
        Build the OCI freeform-tags dict for a created resource directly.

        :param run_id: The provisioning run identifier.
        :param resource_name: Neutral resource name.
        :param resource_kind: Neutral resource kind string.
        :param extra: Optional user-declared tags.
        :param defaults: Optional venue default tags.

        :returns: An OCI freeform-tags dict.
    """
    neutral = base_resource_tags(run_id=run_id, resource_name=resource_name,
                                 resource_kind=resource_kind, extra=extra,
                                 defaults=defaults)
    rtnval = to_freeform(neutral_tags=neutral)
    return rtnval
