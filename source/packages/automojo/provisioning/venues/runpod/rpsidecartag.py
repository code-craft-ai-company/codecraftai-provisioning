"""
    .. module:: rpsidecartag
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpSidecarTag — JSON sidecar tag store for the RunPod venue,
               since the RunPod API has no native pod tag field.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import json
import os

from typing import Any, Dict, List


_SIDECAR_FILENAME = "runpod-tags.json"


class RpSidecarTag:
    """
        JSON-backed sidecar tag store for the RunPod venue.

        RunPod pods have no native tag / label field, so the provisioner
        records the neutral tag list keyed by pod id in a sidecar JSON file
        under ``.output/provisioning/<runid>/``. Reads and writes round-trip
        the neutral tag list as the identity.
    """

    def __init__(self, *, runid: str,
                 output_root: str = ".output") -> None:
        """
            Construct an :class:`RpSidecarTag` store.

            :param runid: The provisioning run identifier.
            :param output_root: The output root directory.

            :returns: ``None``.
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

            :returns: The sidecar file path.
        """
        rtnval = self._path
        return rtnval

    def _load(self) -> Dict[str, Any]:
        """
            Load the sidecar document, degrading to an empty mapping.

            :returns: The decoded sidecar mapping keyed by pod id.
        """
        if not os.path.exists(self._path):
            rtnval: Dict[str, Any] = {}
            return rtnval

        with open(self._path, "r", encoding="utf-8") as file_handle:
            try:
                document = json.load(file_handle)
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

        with open(self._path, "w", encoding="utf-8") as file_handle:
            json.dump(document, file_handle, indent=2, sort_keys=True)
        return

    def write(self, *, neutral_tags: Dict[str, str],
              pod_id: str) -> None:
        """
            Record the neutral tag dict for a pod id.

            :param neutral_tags: The neutral flat tag dict.
            :param pod_id: The RunPod pod id key.

            :returns: ``None``.
        """
        document = self._load()
        if neutral_tags is not None:
            document[pod_id] = dict(neutral_tags)
        else:
            document[pod_id] = {}
        self._store(document=document)
        return

    def read(self, *, pod_id: str) -> Dict[str, str]:
        """
            Recover the neutral tag dict for a pod id.

            :param pod_id: The RunPod pod id key.

            :returns: The neutral flat tag dict, or an empty dict when the id
                is not recorded.
        """
        document = self._load()
        entry = document.get(pod_id, None)
        if entry is None:
            rtnval: Dict[str, str] = {}
            return rtnval

        rtnval = dict(entry)
        return rtnval

    def all_pod_ids(self) -> List[str]:
        """
            Return every pod id recorded in the sidecar.

            :returns: A sorted list of recorded pod ids.
        """
        document = self._load()
        rtnval = sorted(document.keys())
        return rtnval


__all__ = ["RpSidecarTag"]
