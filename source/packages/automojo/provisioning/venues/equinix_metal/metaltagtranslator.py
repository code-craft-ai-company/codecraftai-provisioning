"""
    .. module:: metaltagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tag round-trip helpers between neutral dicts and the Equinix
               Metal string-list tag shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from automojo.provisioning.venues.equinix_metal.metalerrors import (
    MetalValidationError
)


OWNER_TAG_KEY = "automojo:owned-by"
OWNER_TAG_VALUE = "automojo-provisioning"
RUN_ID_TAG_KEY = "automojo:run-id"
RESOURCE_NAME_TAG_KEY = "automojo:resource-name"
RESOURCE_KIND_TAG_KEY = "automojo:resource-kind"
VPN_PROVIDER_TAG_KEY = "automojo:vpn-provider"
VPN_DEVICE_ID_TAG_KEY = "automojo:vpn-device-id"


class MetalTagTranslator:
    """
        Translates between neutral single-entry tag dicts and the Equinix
        Metal device-tag wire shape, which is a flat list of ``"key=value"``
        strings.

        The translation is the identity round-trip: ``from_metal(to_metal(x))``
        returns ``x`` (key-sorted).
    """

    @staticmethod
    def to_metal(*, neutral_tags: Optional[List[Dict[str, str]]]
                 ) -> List[str]:
        """
            Convert neutral single-entry tag dicts to the Metal string list.

            :param neutral_tags: List of single-entry ``{key: value}`` dicts.

            :returns: A key-sorted list of ``"key=value"`` strings.
            :raises: MetalValidationError
        """
        if neutral_tags is None:
            rtnval: List[str] = []
            return rtnval

        seen_keys: Dict[str, str] = {}
        for entry in neutral_tags:
            if not isinstance(entry, dict):
                err_msg_lines = ["Neutral tag entry is not a dict."]
                err_msg_lines.append("ENTRY: {!r}".format(entry))
                err_msg = os.linesep.join(err_msg_lines)
                raise MetalValidationError(err_msg)

            if len(entry) != 1:
                err_msg_lines = [
                    "Neutral tag entry must be a single-key dict."
                ]
                err_msg_lines.append("ENTRY: {!r}".format(entry))
                err_msg = os.linesep.join(err_msg_lines)
                raise MetalValidationError(err_msg)

            for key, value in entry.items():
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

                if key in seen_keys:
                    err_msg_lines = [
                        "Duplicate tag key in neutral tag set."
                    ]
                    err_msg_lines.append("KEY: {}".format(key))
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
                   ) -> List[Dict[str, str]]:
        """
            Convert a Metal ``"key=value"`` string list back to neutral
            single-entry dicts.

            :param strings: List of ``"key=value"`` strings.

            :returns: A key-sorted list of single-entry neutral dicts.
        """
        if strings is None:
            rtnval: List[Dict[str, str]] = []
            return rtnval

        pairs: Dict[str, str] = {}
        for entry in strings:
            if entry is None or len(entry) == 0:
                continue
            if "=" not in entry:
                continue
            key, value = entry.split("=", 1)
            pairs[key] = value

        out: List[Dict[str, str]] = []
        for key in sorted(pairs.keys()):
            out.append({key: pairs[key]})

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
                       extra: Optional[List[Dict[str, str]]] = None,
                       defaults: Optional[List[Dict[str, str]]] = None
                       ) -> List[Dict[str, str]]:
    """
        Build the full neutral tag list for a created Equinix Metal resource.

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
