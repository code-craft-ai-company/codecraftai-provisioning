"""
    .. module:: pvetagtranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PveTagTranslator — converts neutral tag dicts to and from
               the Proxmox semicolon-delimited tag string list.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Dict, List


class PveTagTranslator:
    """
        Translates between the neutral tag representation — a list of
        single-entry ``{key: value}`` dicts — and the Proxmox tag
        representation — a flat list of ``key=value`` strings (Proxmox
        joins tags with a semicolon into a single config string).

        Round-tripping ``from_pve(to_pve(tags))`` recovers the neutral list
        for every well-formed input (the identity contract from
        Requirement 6).
    """

    @staticmethod
    def to_pve(*, neutral_tags: List[Dict[str, str]]) -> List[str]:
        """
            Encode a neutral tag list into a Proxmox tag-string list.

            :param neutral_tags: A list of single-entry ``{key: value}``
                dicts.

            :returns: A list of ``key=value`` strings, one per neutral tag.
        """
        rtnval: List[str] = []
        if neutral_tags is None:
            return rtnval

        for entry in neutral_tags:
            if entry is None:
                continue
            for key, value in entry.items():
                rtnval.append("{}={}".format(key, value))

        return rtnval

    @staticmethod
    def from_pve(*, pve_tags: List[str]) -> List[Dict[str, str]]:
        """
            Decode a Proxmox tag-string list back into a neutral tag list.

            :param pve_tags: A list of ``key=value`` strings.

            :returns: A list of single-entry ``{key: value}`` dicts.
        """
        rtnval: List[Dict[str, str]] = []
        if pve_tags is None:
            return rtnval

        for token in pve_tags:
            if token is None or len(token) == 0:
                continue
            if "=" not in token:
                continue
            key, _, value = token.partition("=")
            rtnval.append({key: value})

        return rtnval
