"""
    .. module:: sshkeymanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DigitalOcean account-scoped SSH key manager.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import base64
import hashlib

from typing import Any, Dict, List, Optional

from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair
from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.venues.digitalocean.doclient import (
    DigitalOceanClient
)


def _fingerprint(*, public_key_material: str) -> str:
    """
        Compute the MD5 fingerprint of an OpenSSH public key.

        :param public_key_material: The ``ssh-rsa AAAA... comment`` string.

        :returns: The colon-separated MD5 fingerprint, or empty on failure.
    """
    parts = public_key_material.split()
    if len(parts) < 2:
        rtnval = ""
        return rtnval
    try:
        raw = base64.b64decode(parts[1])
    except Exception:
        rtnval = ""
        return rtnval
    digest = hashlib.md5(raw).hexdigest()
    pairs = [digest[i:i + 2] for i in range(0, len(digest), 2)]
    rtnval = ":".join(pairs)
    return rtnval


class SshKeyManager:
    """
        Manager for DigitalOcean account-scoped SSH keys.

        SSH keys are not taggable on DigitalOcean; they are deduped by
        fingerprint.  An existing key with a matching fingerprint is reused.
    """

    KIND: str = "keypair"

    def __init__(self, *, client: DigitalOceanClient) -> None:
        """
            Construct an SshKeyManager.

            :param client: DigitalOceanClient.
        """
        self._client: DigitalOceanClient = client
        return

    def _all_keys(self) -> List[Dict[str, Any]]:
        """
            List every SSH key on the account.

            :returns: A list of SSH key dicts.
        """
        response = self._client.ssh_keys.list()
        rtnval = list(response.get("ssh_keys", []))
        return rtnval

    def find(self, *, run_id: str, name: str,
             desired: Optional[CloudKeyPair] = None
             ) -> Optional[Dict[str, Any]]:
        """
            Find an existing SSH key by fingerprint, then by name.

            :param run_id: Run identifier (unused; keys are account-scoped).
            :param name: Neutral keypair name.
            :param desired: Optional CloudKeyPair providing the public key.

            :returns: The SSH key dict, or None.
        """
        fingerprint = ""
        if desired is not None:
            fingerprint = _fingerprint(
                public_key_material=desired.public_key_material
            )
        for key in self._all_keys():
            if len(fingerprint) > 0 and key.get("fingerprint", "") == fingerprint:
                rtnval: Optional[Dict[str, Any]] = key
                return rtnval
            if key.get("name", "") == "codecraftai-{}".format(name):
                rtnval = key
                return rtnval
        rtnval = None
        return rtnval

    def ensure(self, *, desired: CloudKeyPair, run_id: str,
               aspects: Any = None) -> ProvisionedResource:
        """
            Match-then-act create-or-reuse for an SSH key.

            :param desired: Desired CloudKeyPair.
            :param run_id: Run identifier.
            :param aspects: Aspects.

            :returns: A ProvisionedResource describing the SSH key.
        """
        existing = self.find(run_id=run_id, name=desired.name,
                             desired=desired)
        if existing is None:
            body: Dict[str, Any] = {
                "name": "codecraftai-{}".format(desired.name),
                "public_key": desired.public_key_material,
            }
            created = self._client.ssh_keys.create(body=body)
            existing = created.get("ssh_key", {})

        attributes: Dict[str, Any] = {}
        attributes["ssh_key_id"] = existing.get("id", "")
        attributes["fingerprint"] = existing.get("fingerprint", "")
        attributes["do_key_name"] = existing.get("name", "")

        rtnval = ProvisionedResource(
            kind=self.KIND, name=desired.name,
            venue_id=str(existing.get("id", "")),
            attributes=attributes, tags={},
        )
        return rtnval

    def destroy(self, *, run_id: str, names: List[str],
                aspects: Any) -> List[str]:
        """
            Destroy SSH keys created for the run.

            SSH keys are account-scoped and not run-tagged; only keys whose
            name matches the ``codecraftai-<name>`` convention for the run's
            spec names are removed.

            :param run_id: Run identifier.
            :param names: Neutral keypair names from the run's spec.
            :param aspects: Aspects.

            :returns: List of destroyed SSH key ids.
        """
        wanted = set("codecraftai-{}".format(name) for name in names)
        deleted: List[str] = []
        for key in self._all_keys():
            if key.get("name", "") not in wanted:
                continue
            ssh_key_id = key.get("id", "")
            try:
                self._client.ssh_keys.delete(ssh_key_id=ssh_key_id)
                deleted.append(str(ssh_key_id))
            except Exception:
                pass
        rtnval = deleted
        return rtnval
