"""
    .. module:: llsidecartag
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LlSidecarTag — JSON sidecar tag store for the Lambda Labs
               venue, since the Lambda Labs API has no native tag field.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, List


_SIDECAR_FILENAME = "lambdalabs-tags.json"


class LlSidecarTag:
    """
        JSON-backed sidecar tag store for the Lambda Labs venue.

        Lambda Labs instances have no native tag/label field, so the
        provisioner records the neutral tag list keyed by instance id in a
        sidecar JSON file under ``.output/provisioning/<runid>/``.  Reads
        and writes round-trip the neutral tag list as the identity.
    """

    def __init__(self, *, runid: str,
                 output_root: str = ".output") -> None:
        """
            Construct an LlSidecarTag store.

            :param runid: The provisioning run identifier.
            :param output_root: The output root directory.
        """
        self._runid = runid
        self._output_root = output_root
        self._directory = os.path.join(output_root, "provisioning", runid)
        self._path = os.path.join(self._directory, _SIDECAR_FILENAME)
        return

    @property
    def path(self) -> str:
        """
            The sidecar file path.

            :returns: The absolute-or-relative sidecar file path.
        """
        return self._path

    def _load(self) -> Dict[str, Any]:
        """
            Load the sidecar document, degrading to an empty mapping.

            :returns: The decoded sidecar mapping keyed by instance id.
        """
        if not os.path.exists(self._path):
            rtnval: Dict[str, Any] = {}
            return rtnval

        with open(self._path, "r", encoding="utf-8") as fh:
            try:
                document = json.load(fh)
            except ValueError:
                document = {}

        if not isinstance(document, dict):
            rtnval = {}
            return rtnval

        rtnval = document
        return rtnval

    def _store(self, *, document: Dict[str, Any]) -> None:
        """
            Persist the sidecar document, creating the directory tree.

            :param document: The sidecar mapping to persist.

            :returns: ``None``.
        """
        if not os.path.exists(self._directory):
            os.makedirs(self._directory, exist_ok=True)

        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(document, fh, indent=2, sort_keys=True)
        return

    def write(self, *, neutral_tags: Dict[str, str],
              instance_id: str) -> None:
        """
            Record the neutral tag dict for an instance id.

            :param neutral_tags: The neutral flat tag dict.
            :param instance_id: The Lambda Labs instance id key.

            :returns: ``None``.
        """
        document = self._load()
        if neutral_tags is not None:
            document[instance_id] = dict(neutral_tags)
        else:
            document[instance_id] = {}
        self._store(document=document)
        return

    def read(self, *, instance_id: str) -> Dict[str, str]:
        """
            Recover the neutral tag dict for an instance id.

            :param instance_id: The Lambda Labs instance id key.

            :returns: The neutral flat tag dict, or an empty dict when the id
                is not recorded.
        """
        document = self._load()
        entry = document.get(instance_id, None)
        if entry is None:
            rtnval: Dict[str, str] = {}
            return rtnval

        rtnval = dict(entry)
        return rtnval

    def all_instance_ids(self) -> List[str]:
        """
            Return every instance id recorded in the sidecar.

            :returns: A sorted list of recorded instance ids.
        """
        document = self._load()
        rtnval = sorted(document.keys())
        return rtnval
