"""
    .. module:: keypairmanager
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: OCI SSH key resolution for the Oracle Cloud venue.

    OCI has no first-class key-pair resource: public keys are injected into
    each Compute Instance's ``metadata["ssh_authorized_keys"]``.  This
    manager simply tracks the declared CloudKeyPair objects so the compute
    manager can resolve a name reference to public-key material.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Dict, List, Optional

from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair


class KeyPairManager:
    """
        Resolver for OCI SSH key material.

        OCI exposes no key-pair API; key material is placed on instances via
        instance metadata.  This manager is a pure in-memory index from
        neutral key-pair name to public-key material.  It performs no SDK
        calls and creates no venue-side resource.
    """

    KIND: str = "keypair"

    def __init__(self) -> None:
        """
            Construct a KeyPairManager.
        """
        self._by_name: Dict[str, str] = {}
        return

    def register(self, *, keypairs: List[CloudKeyPair]) -> None:
        """
            Register the declared key pairs from a spec.

            :param keypairs: List of CloudKeyPair objects.
        """
        for keypair in keypairs:
            self._by_name[keypair.name] = keypair.public_key_material
        return

    def authorized_keys_for(self, *, name: Optional[str]
                            ) -> Optional[str]:
        """
            Return the SSH public-key material for a key-pair name.

            :param name: Neutral key-pair name (or None).

            :returns: The public-key material string, or None.
        """
        if name is None or len(name) == 0:
            rtnval: Optional[str] = None
            return rtnval
        rtnval = self._by_name.get(name, None)
        return rtnval
