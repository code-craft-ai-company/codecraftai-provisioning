"""
    .. module:: metaltagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and the Equinix
               Metal string-list tag shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from ccai.provisioning.venues.equinix_metal.metalerrors import (
    MetalValidationError
)


OWNER_TAG_KEY = "ccai:owned-by"
OWNER_TAG_VALUE = "codecraftai-provisioning"
RUN_ID_TAG_KEY = "ccai:run-id"
RESOURCE_NAME_TAG_KEY = "ccai:resource-name"
RESOURCE_KIND_TAG_KEY = "ccai:resource-kind"
VPN_PROVIDER_TAG_KEY = "ccai:vpn-provider"
VPN_DEVICE_ID_TAG_KEY = "ccai:vpn-device-id"


class MetalTagTranslator:
    """
        Translates between neutral single-entry tag dicts and the Equinix
        Metal device-tag wire shape, which is a flat list of ``"key=value"``
        strings.

        The translation is the identity round-trip: ``from_metal(to_metal(x))``
        returns ``x`` (key-sorted).
    """

    @staticmethod
    def to_metal(*, neutral_tags: Optional[Dict[str, str]]
                 ) -> List[str]:
        """
            Convert a neutral flat tag dict to the Metal string list.

            :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

            :returns: A key-sorted list of ``"key=value"`` strings.
            :raises: MetalValidationError
        """
        if neutral_tags is None:
            rtnval: List[str] = []
            return rtnval

        seen_keys: Dict[str, str] = {}
        for key, value in neutral_tags.items():
            if not isinstance(key, str) or not isinstance(value, str):
                err_msg_lines = ["Tag key and value must be strings."]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg_lines.append("VALUE: {!r}".format(value))
                err_msg = os.linesep.join(err_msg_lines)
                raise MetalValidationError(err_msg)

            if "=" in key:
                err_msg_lines = [
                    "Tag key must not contain '=' on Equinix Metal."
                ]
                err_msg_lines.append("KEY: {!r}".format(key))
                err_msg = os.linesep.join(err_msg_lines)
                raise MetalValidationError(err_msg)

            seen_keys[key] = value

        out: List[str] = []
        for key in sorted(seen_keys.keys()):
            out.append("{}={}".format(key, seen_keys[key]))

        rtnval = out
        return rtnval

    @staticmethod
    def from_metal(*, strings: Optional[List[str]]
                   ) -> Dict[str, str]:
        """
            Convert a Metal ``"key=value"`` string list back to a neutral
            flat tag dict.

            :param strings: List of ``"key=value"`` strings.

            :returns: A neutral flat ``{key: value}`` dict.
        """
        pairs: Dict[str, str] = {}
        if strings is None:
            rtnval = pairs
            return rtnval

        for entry in strings:
            if entry is None or len(entry) == 0:
                continue
            if "=" not in entry:
                continue
            key, value = entry.split("=", 1)
            pairs[key] = value

        out: Dict[str, str] = {}
        for key in sorted(pairs.keys()):
            out[key] = pairs[key]

        rtnval = out
        return rtnval

    @staticmethod
    def flat_dict(*, strings: Optional[List[str]]) -> Dict[str, str]:
        """
            Return a flat ``{key: value}`` dict from a Metal tag string list.

            :param strings: List of ``"key=value"`` strings.

            :returns: A flat dict of tag pairs.
        """
        out: Dict[str, str] = {}
        if strings is None:
            rtnval = out
            return rtnval
        for entry in strings:
            if entry is None or "=" not in entry:
                continue
            key, value = entry.split("=", 1)
            out[key] = value
        rtnval = out
        return rtnval


def base_resource_tags(*, run_id: str, resource_name: str,
                       resource_kind: str,
                       extra: Optional[Dict[str, str]] = None,
                       defaults: Optional[Dict[str, str]] = None
                       ) -> Dict[str, str]:
    """
        Build the full neutral tag dict for a created Equinix Metal resource.

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
