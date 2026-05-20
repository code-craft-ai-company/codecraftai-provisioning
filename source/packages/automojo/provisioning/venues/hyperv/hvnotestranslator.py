"""
    .. module:: hvnotestranslator
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvNotesTranslator — encodes / decodes the automojo JSON
        envelope carried in a Hyper-V VM ``Notes`` field.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import json

from typing import Any, Dict, List, Optional


_ENVELOPE_KEY = "automojo"


class HvNotesEnvelope:
    """
        Decoded representation of the automojo envelope in a VM's Notes.

        Carries the provisioning run identifier and the recovered neutral
        tag list.
    """

    def __init__(self, *, run_id: Optional[str],
                 tags: List[Dict[str, str]]) -> None:
        """
            Construct an HvNotesEnvelope.

            :param run_id: The provisioning run identifier, or ``None`` when
                the VM carries no automojo envelope.
            :param tags: The recovered neutral tag list.
        """
        self.run_id: Optional[str] = run_id
        self.tags: List[Dict[str, str]] = tags
        return


class HvNotesTranslator:
    """
        Translator for the automojo JSON envelope stored in ``VM.Notes``.

        Hyper-V has no first-class tagging system, so the provisioner
        stores ownership and neutral tags as a JSON object under the
        ``automojo`` key inside the VM ``Notes`` string.  ``encode`` and
        ``decode`` are exact inverses on the neutral tag list.
    """

    def encode(self, *, neutral_tags: Optional[List[Dict[str, str]]],
               run_id: str) -> str:
        """
            Encode neutral tags and a run-id into a Notes string.

            :param neutral_tags: The neutral tag list (single-entry dicts),
                or ``None``.
            :param run_id: The provisioning run identifier.

            :returns: A JSON string suitable for ``Set-VM -Notes``.
        """
        effective_tags = neutral_tags if neutral_tags is not None else []

        normalized: List[Dict[str, str]] = []
        for entry in effective_tags:
            normalized.append(dict(entry))

        envelope: Dict[str, Any] = {
            _ENVELOPE_KEY: {
                "run_id": run_id,
                "tags": normalized,
            }
        }
        rtnval = json.dumps(envelope, sort_keys=True, separators=(",", ":"))
        return rtnval

    def decode(self, *, notes_str: Optional[str]) -> HvNotesEnvelope:
        """
            Decode a VM Notes string into an :class:`HvNotesEnvelope`.

            A Notes string that does not parse as JSON, or that carries no
            ``automojo`` envelope, yields an envelope with ``run_id=None``
            and an empty tag list.

            :param notes_str: The raw VM ``Notes`` string, or ``None``.

            :returns: An HvNotesEnvelope.
        """
        if notes_str is None or len(notes_str) == 0:
            rtnval = HvNotesEnvelope(run_id=None, tags=[])
            return rtnval

        try:
            parsed = json.loads(notes_str)
        except (ValueError, TypeError):
            rtnval = HvNotesEnvelope(run_id=None, tags=[])
            return rtnval

        if not isinstance(parsed, dict):
            rtnval = HvNotesEnvelope(run_id=None, tags=[])
            return rtnval

        envelope = parsed.get(_ENVELOPE_KEY, None)
        if not isinstance(envelope, dict):
            rtnval = HvNotesEnvelope(run_id=None, tags=[])
            return rtnval

        raw_run_id = envelope.get("run_id", None)
        run_id: Optional[str] = None
        if raw_run_id is not None:
            run_id = str(raw_run_id)

        raw_tags = envelope.get("tags", None)
        tags: List[Dict[str, str]] = []
        if isinstance(raw_tags, list):
            for entry in raw_tags:
                if isinstance(entry, dict):
                    normalized: Dict[str, str] = {}
                    for key in entry:
                        normalized[str(key)] = str(entry[key])
                    tags.append(normalized)

        rtnval = HvNotesEnvelope(run_id=run_id, tags=tags)
        return rtnval

    def owned_by(self, *, notes_str: Optional[str], run_id: str) -> bool:
        """
            Report whether a VM's Notes mark it as owned by a run.

            :param notes_str: The raw VM ``Notes`` string.
            :param run_id: The provisioning run identifier.

            :returns: ``True`` when the envelope run-id matches.
        """
        envelope = self.decode(notes_str=notes_str)
        rtnval = envelope.run_id == run_id
        return rtnval
