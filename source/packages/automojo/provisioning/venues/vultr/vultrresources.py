"""
    .. module:: vultrresources
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Owner-tagged read-before-create helpers over the Vultr API.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.provisioning.venues.vultr.vultrclient import VultrClient
from automojo.provisioning.venues.vultr.vultrtagtranslator import (
    VultrTagTranslator, RESOURCE_NAME_TAG_KEY, RUN_ID_TAG_KEY, OWNER_TAG_KEY,
    OWNER_TAG_VALUE
)


def _tag_strings_of(*, entry: Dict[str, Any]) -> List[str]:
    """
        Return the Vultr string tag list of an API resource entry.

        Vultr resources may carry either a ``tags`` string list or a single
        legacy ``tag`` string; this helper normalises both.

        :param entry: A Vultr API resource dict.

        :returns: A list of tag strings.
    """
    out: List[str] = []
    tags = entry.get("tags", None)
    if tags is not None and isinstance(tags, list):
        for value in tags:
            out.append(str(value))
    single = entry.get("tag", None)
    if single is not None and isinstance(single, str) and len(single) > 0:
        out.append(single)

    # Resources without a native tag list (firewall groups, SSH keys, block
    # storage, object storage) carry the owner tags embedded in their
    # description / name / label field; recover them here.
    for field in ("description", "label", "name"):
        text = entry.get(field, None)
        if text is None or not isinstance(text, str):
            continue
        for piece in _embedded_tag_pieces(text=text):
            if piece not in out:
                out.append(piece)

    rtnval = out
    return rtnval


def _embedded_tag_pieces(*, text: str) -> List[str]:
    """
        Recover ``key=value`` tag pieces embedded in a name/label/description.

        Owner tags are embedded after a ``|`` or inside ``[...]`` brackets.

        :param text: The field text to scan.

        :returns: A list of recovered tag piece strings.
    """
    out: List[str] = []
    candidates: List[str] = []
    if "|" in text:
        candidates.append(text.split("|", 1)[1])
    start = text.find("[")
    end = text.find("]")
    if start >= 0 and end > start:
        candidates.append(text[start + 1:end])
    for candidate in candidates:
        for piece in candidate.split("|"):
            for sub in piece.split(","):
                if "=" in sub:
                    out.append(sub)
    rtnval = out
    return rtnval


def is_owned(*, entry: Dict[str, Any], run_id: str) -> bool:
    """
        Return whether a Vultr API entry is owned by this provisioning run.

        :param entry: A Vultr API resource dict.
        :param run_id: The provisioning run identifier.

        :returns: True when the owner + run-id tags are present.
    """
    tag_strings = _tag_strings_of(entry=entry)
    owner_marker = "{}={}".format(OWNER_TAG_KEY, OWNER_TAG_VALUE)
    run_marker = "{}={}".format(RUN_ID_TAG_KEY, run_id)
    rtnval = owner_marker in tag_strings and run_marker in tag_strings
    return rtnval


def find_named(*, client: VultrClient, path: str, collection_key: str,
               run_id: str, name: str) -> Optional[Dict[str, Any]]:
    """
        Find an owned resource by run-id + resource-name tags.

        :param client: A VultrClient.
        :param path: The list endpoint path.
        :param collection_key: The list collection key.
        :param run_id: The provisioning run identifier.
        :param name: The neutral resource name.

        :returns: The matching API entry, or None.
    """
    entries = list_owned_raw(client=client, path=path,
                             collection_key=collection_key, run_id=run_id)
    name_marker = "{}={}".format(RESOURCE_NAME_TAG_KEY, name)
    found: Optional[Dict[str, Any]] = None
    for entry in entries:
        tag_strings = _tag_strings_of(entry=entry)
        if name_marker in tag_strings:
            found = entry
    rtnval = found
    return rtnval


def list_owned_raw(*, client: VultrClient, path: str, collection_key: str,
                   run_id: str) -> List[Dict[str, Any]]:
    """
        List every owned resource entry for the run at a list endpoint.

        :param client: A VultrClient.
        :param path: The list endpoint path.
        :param collection_key: The list collection key.
        :param run_id: The provisioning run identifier.

        :returns: A list of owned API entries.
    """
    owner_marker = "{}={}".format(OWNER_TAG_KEY, OWNER_TAG_VALUE)
    params = {"tag": owner_marker}
    entries = client.list_all(path=path, collection_key=collection_key,
                              params=params)
    out: List[Dict[str, Any]] = []
    for entry in entries:
        if is_owned(entry=entry, run_id=run_id):
            out.append(entry)
    rtnval = out
    return rtnval


def neutral_tags_of(*, entry: Dict[str, Any]) -> Dict[str, str]:
    """
        Reconstruct the neutral tag dict from a Vultr API entry.

        :param entry: A Vultr API resource dict.

        :returns: A flat ``{key: value}`` dict of neutral tag pairs.
    """
    rtnval = VultrTagTranslator.from_vultr(strings=_tag_strings_of(entry=entry))
    return rtnval
