"""
    .. module:: linodetagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Round-trip translation between neutral tag dicts and Linode's
               string-list tag shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from automojo.provisioning.venues.linode.linodeerrors import (
    LinodeValidationError
)


OWNER_TAG_KEY = "automojo:owned-by"
OWNER_TAG_VALUE = "automojo-provisioning"
RUN_ID_TAG_KEY = "automojo:owner"
RESOURCE_NAME_TAG_KEY = "automojo:resource-name"
RESOURCE_KIND_TAG_KEY = "automojo:resource-kind"

LINODE_TAG_MAX = 50


class LinodeTagTranslator:
    """
        Translator that encodes neutral single-entry tag dicts as Linode
        ``key=value`` string tags and recovers them losslessly.

        Linode resources carry a flat list of string tags.  Each neutral
        ``{key: value}`` pair is encoded as the single string ``"key=value"``
        so that ``from_linode(to_linode(x))`` is the identity.
    """

    def to_linode(self, *, neutral_tags: Optional[List[Dict[str, str]]]
                  ) -> List[str]:
        """
            Convert neutral single-entry tag dicts to Linode string tags.

            :param neutral_tags: List of single-entry ``{key: value}`` dicts.

            :returns: A key-sorted list of ``"key=value"`` strings.
            :raises: LinodeValidationError
        """
        if neutral_tags is None:
            rtnval: List[str] = []
            return rtnval

        pairs: List[str] = []
        seen_keys: Dict[str, str] = {}
        for entry in neutral_tags:
            if not isinstance(entry, dict):
                err_msg_lines = ["Neutral tag entry is not a dict."]
                err_msg_lines.append("ENTRY: {!r}".format(entry))
                err_msg = os.linesep.join(err_msg_lines)
                raise LinodeValidationError(err_msg)

            if len(entry) != 1:
                err_msg_lines = [
                    "Neutral tag entry must be a single-key dict."
                ]
                err_msg_lines.append("ENTRY: {!r}".format(entry))
                err_msg = os.linesep.join(err_msg_lines)
                raise LinodeValidationError(err_msg)

            for key, value in entry.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    err_msg_lines = ["Tag key and value must be strings."]
                    err_msg_lines.append("KEY: {!r}".format(key))
                    err_msg_lines.append("VALUE: {!r}".format(value))
                    err_msg = os.linesep.join(err_msg_lines)
                    raise LinodeValidationError(err_msg)

                if "=" in key:
                    err_msg_lines = [
                        "Tag key must not contain an '=' character."
                    ]
                    err_msg_lines.append("KEY: {!r}".format(key))
                    err_msg = os.linesep.join(err_msg_lines)
                    raise LinodeValidationError(err_msg)

                if key in seen_keys:
                    err_msg_lines = ["Duplicate tag key in neutral tag set."]
                    err_msg_lines.append("KEY: {}".format(key))
                    err_msg = os.linesep.join(err_msg_lines)
                    raise LinodeValidationError(err_msg)

                encoded = "{}={}".format(key, value)
                if len(encoded) > LINODE_TAG_MAX:
                    err_msg_lines = [
                        "Encoded Linode tag exceeds the 50-char limit."
                    ]
                    err_msg_lines.append("TAG: {!r}".format(encoded))
                    err_msg = os.linesep.join(err_msg_lines)
                    raise LinodeValidationError(err_msg)

                seen_keys[key] = value
                pairs.append(encoded)

        pairs.sort()
        rtnval = pairs
        return rtnval

    def from_linode(self, *, strings: Optional[List[str]]
                    ) -> List[Dict[str, str]]:
        """
            Convert a Linode string tag list back to neutral tag dicts.

            Strings that do not contain an ``=`` are ignored so foreign tags
            placed on a resource by hand do not break the round-trip.

            :param strings: List of ``"key=value"`` strings.

            :returns: A key-sorted list of single-entry neutral dicts.
        """
        if strings is None:
            rtnval: List[Dict[str, str]] = []
            return rtnval

        out: List[Dict[str, str]] = []
        for entry in sorted(strings):
            if "=" not in entry:
                continue
            split_at = entry.index("=")
            key = entry[:split_at]
            value = entry[split_at + 1:]
            out.append({key: value})

        rtnval = out
        return rtnval

    def owner_tags(self, *, run_id: str, resource_name: str,
                   resource_kind: str,
                   extra: Optional[List[Dict[str, str]]] = None,
                   defaults: Optional[List[Dict[str, str]]] = None
                   ) -> List[str]:
        """
            Build the full Linode string tag list for a created resource.

            :param run_id: The provisioning run identifier.
            :param resource_name: Neutral resource name.
            :param resource_kind: Neutral resource kind string.
            :param extra: Optional user-declared tags.
            :param defaults: Optional venue default tags.

            :returns: A list of ``"key=value"`` string tags.
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

        rtnval = self.to_linode(neutral_tags=combined)
        return rtnval

    def is_owned_by_run(self, *, strings: Optional[List[str]],
                        run_id: str) -> bool:
        """
            Test whether a Linode resource's tags mark it owned by a run.

            :param strings: The resource's Linode string tag list.
            :param run_id: The run identifier to match.

            :returns: True when both owner and run-id tags are present.
        """
        if strings is None:
            rtnval = False
            return rtnval

        owner_tag = "{}={}".format(OWNER_TAG_KEY, OWNER_TAG_VALUE)
        run_tag = "{}={}".format(RUN_ID_TAG_KEY, run_id)
        has_owner = owner_tag in strings
        has_run = run_tag in strings
        rtnval = has_owner and has_run
        return rtnval

    def resource_name_of(self, *, strings: Optional[List[str]]
                         ) -> Optional[str]:
        """
            Extract the neutral resource name from a Linode tag list.

            :param strings: The resource's Linode string tag list.

            :returns: The resource name, or None when absent.
        """
        neutral = self.from_linode(strings=strings)
        for entry in neutral:
            for key, value in entry.items():
                if key == RESOURCE_NAME_TAG_KEY:
                    rtnval: Optional[str] = value
                    return rtnval
        rtnval = None
        return rtnval
