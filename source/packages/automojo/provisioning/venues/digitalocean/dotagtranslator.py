"""
    .. module:: dotagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral tag dicts and the
               DigitalOcean string-list tag shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from automojo.provisioning.venues.digitalocean.doerrors import (
    DoValidationError
)


OWNER_TAG_KEY = "automojo:owned-by"
OWNER_TAG_VALUE = "automojo-provisioning"
RUN_ID_TAG_KEY = "automojo:owner"
RESOURCE_NAME_TAG_KEY = "automojo:resource-name"
RESOURCE_KIND_TAG_KEY = "automojo:resource-kind"

# DigitalOcean caps a tag string at 255 characters.
DO_TAG_MAX = 255


def _escape(*, value: str) -> str:
    """
        Escape a string so it can be embedded in a single ``k=v`` tag.

        ``\\`` becomes ``\\\\`` and ``=`` becomes ``\\e`` so that the first
        unescaped ``=`` separates key from value unambiguously.

        :param value: Raw string fragment.

        :returns: The escaped fragment.
    """
    escaped = value.replace("\\", "\\\\").replace("=", "\\e")
    rtnval = escaped
    return rtnval


def _unescape(*, value: str) -> str:
    """
        Reverse :func:`_escape`.

        :param value: Escaped string fragment.

        :returns: The original string fragment.
    """
    out_chars: List[str] = []
    index = 0
    length = len(value)
    while index < length:
        char = value[index]
        if char == "\\" and index + 1 < length:
            nextc = value[index + 1]
            if nextc == "\\":
                out_chars.append("\\")
                index = index + 2
                continue
            if nextc == "e":
                out_chars.append("=")
                index = index + 2
                continue
        out_chars.append(char)
        index = index + 1
    rtnval = "".join(out_chars)
    return rtnval


def to_do(*, neutral_tags: Optional[Dict[str, str]]) -> List[str]:
    """
        Convert a neutral flat tag dict to the DigitalOcean tag
        string-list wire shape.

        Each ``{key: value}`` pair becomes a single ``key=value`` string with
        ``\\`` and ``=`` escaped so round-tripping is the identity.

        :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

        :returns: A sorted list of ``key=value`` tag strings.
        :raises: DoValidationError
    """
    if neutral_tags is None:
        rtnval: List[str] = []
        return rtnval

    encoded: List[str] = []
    for key, value in neutral_tags.items():
        if not isinstance(key, str) or not isinstance(value, str):
            err_msg_lines = ["Tag key and value must be strings."]
            err_msg_lines.append("KEY: {!r}".format(key))
            err_msg_lines.append("VALUE: {!r}".format(value))
            err_msg = os.linesep.join(err_msg_lines)
            raise DoValidationError(err_msg)

        tag_string = "{}={}".format(_escape(value=key),
                                    _escape(value=value))
        if len(tag_string) > DO_TAG_MAX:
            err_msg_lines = ["Encoded tag exceeds DigitalOcean 255 limit."]
            err_msg_lines.append("KEY: {}".format(key))
            err_msg_lines.append("LENGTH: {}".format(len(tag_string)))
            err_msg = os.linesep.join(err_msg_lines)
            raise DoValidationError(err_msg)

        encoded.append(tag_string)

    encoded.sort()
    rtnval = encoded
    return rtnval


def from_do(*, do_tags: Optional[List[str]]) -> Dict[str, str]:
    """
        Convert a DigitalOcean tag string-list back to a neutral flat tag
        dict.

        :param do_tags: List of ``key=value`` tag strings.

        :returns: A neutral flat ``{key: value}`` dict.
    """
    out: Dict[str, str] = {}
    if do_tags is None:
        rtnval = out
        return rtnval

    for tag_string in do_tags:
        # Split on the first unescaped '='.
        split_index = -1
        index = 0
        length = len(tag_string)
        while index < length:
            char = tag_string[index]
            if char == "\\":
                index = index + 2
                continue
            if char == "=":
                split_index = index
                break
            index = index + 1

        if split_index < 0:
            # Not a key=value tag; ignore.
            continue

        raw_key = tag_string[:split_index]
        raw_value = tag_string[split_index + 1:]
        key = _unescape(value=raw_key)
        value = _unescape(value=raw_value)
        out[key] = value

    rtnval = out
    return rtnval


def to_flat(*, do_tags: Optional[List[str]]) -> Dict[str, str]:
    """
        Build a flat ``{key: value}`` dict from a DigitalOcean tag list.

        :param do_tags: DigitalOcean tag string-list or None.

        :returns: A flat dict (empty when input is None).
    """
    rtnval = from_do(do_tags=do_tags)
    return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[Dict[str, str]] = None,
                       defaults: Optional[Dict[str, str]] = None
                       ) -> Dict[str, str]:
    """
        Build the full neutral tag dict for a created DigitalOcean resource.

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
