"""
    .. module:: linodetagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Round-trip translation between neutral tag dicts and Linode's
               string-list tag shape.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Dict, List, Optional

from ccai.provisioning.venues.linode.linodeerrors import (
    LinodeValidationError
)


OWNER_TAG_KEY = "ccai:owned-by"
OWNER_TAG_VALUE = "codecraftai-provisioning"
RUN_ID_TAG_KEY = "ccai:owner"
RESOURCE_NAME_TAG_KEY = "ccai:resource-name"
RESOURCE_KIND_TAG_KEY = "ccai:resource-kind"

LINODE_TAG_MAX = 50


class LinodeTagTranslator:
    """
        Translator that encodes neutral single-entry tag dicts as Linode
        ``key=value`` string tags and recovers them losslessly.

        Linode resources carry a flat list of string tags.  Each neutral
        ``{key: value}`` pair is encoded as the single string ``"key=value"``
        so that ``from_linode(to_linode(x))`` is the identity.
    """

    def to_linode(self, *, neutral_tags: Optional[Dict[str, str]]
                  ) -> List[str]:
        """
            Convert a neutral flat tag dict to Linode string tags.

            :param neutral_tags: Flat ``{key: value}`` dict of tag pairs.

            :returns: A key-sorted list of ``"key=value"`` strings.
            :raises: LinodeValidationError
        """
        if neutral_tags is None:
            rtnval: List[str] = []
            return rtnval

        pairs: List[str] = []
        for key, value in neutral_tags.items():
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

            encoded = "{}={}".format(key, value)
            if len(encoded) > LINODE_TAG_MAX:
                err_msg_lines = [
                    "Encoded Linode tag exceeds the 50-char limit."
                ]
                err_msg_lines.append("TAG: {!r}".format(encoded))
                err_msg = os.linesep.join(err_msg_lines)
                raise LinodeValidationError(err_msg)

            pairs.append(encoded)

        pairs.sort()
        rtnval = pairs
        return rtnval

    def from_linode(self, *, strings: Optional[List[str]]
                    ) -> Dict[str, str]:
        """
            Convert a Linode string tag list back to a neutral flat tag dict.

            Strings that do not contain an ``=`` are ignored so foreign tags
            placed on a resource by hand do not break the round-trip.

            :param strings: List of ``"key=value"`` strings.

            :returns: A neutral flat ``{key: value}`` dict.
        """
        out: Dict[str, str] = {}
        if strings is None:
            rtnval = out
            return rtnval

        for entry in sorted(strings):
            if "=" not in entry:
                continue
            split_at = entry.index("=")
            key = entry[:split_at]
            value = entry[split_at + 1:]
            out[key] = value

        rtnval = out
        return rtnval

    def owner_tags(self, *, run_id: str, resource_name: str,
                   resource_kind: str,
                   extra: Optional[Dict[str, str]] = None,
                   defaults: Optional[Dict[str, str]] = None
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
        rtnval: Optional[str] = neutral.get(RESOURCE_NAME_TAG_KEY, None)
        return rtnval
