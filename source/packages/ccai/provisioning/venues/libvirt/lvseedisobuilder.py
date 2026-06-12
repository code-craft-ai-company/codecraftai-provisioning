"""
    .. module:: lvseedisobuilder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LvSeedIsoBuilder — builds a cloud-init NoCloud (cidata)
               seed payload for a libvirt domain.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import hashlib
import os

from typing import Any, Dict, List, Optional

import yaml

from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


class LvSeedIsoPayload:
    """
        The materials of a cloud-init NoCloud datasource.

        Carries the three NoCloud files (``user-data``, ``meta-data``,
        ``network-config``) plus a deterministic content hash and the
        on-host ISO path the domain CD-ROM device points at.
    """

    def __init__(self, *, user_data: str, meta_data: str,
                 network_config: str, content_hash: str,
                 iso_path: str) -> None:
        """
            Construct an LvSeedIsoPayload.

            :param user_data: The ``user-data`` document text.
            :param meta_data: The ``meta-data`` document text.
            :param network_config: The ``network-config`` document text.
            :param content_hash: A deterministic SHA-256 of the payload.
            :param iso_path: The on-host path of the seed ISO volume.
        """
        self.user_data: str = user_data
        self.meta_data: str = meta_data
        self.network_config: str = network_config
        self.content_hash: str = content_hash
        self.iso_path: str = iso_path
        return


class LvSeedIsoBuilder:
    """
        Builds the cloud-init NoCloud (``cidata``) seed payload for a
        libvirt domain.

        The NoCloud datasource is a small ISO carrying ``user-data`` and
        ``meta-data``.  This builder renders those documents
        deterministically: identical inputs always yield byte-identical
        documents and therefore an identical content hash.  The optional
        command runner is used to materialise the physical ISO; when it
        is ``None`` the builder stages the document text only (the
        physical ISO build is left to the live integration path).
    """

    def __init__(self, *, command_runner: Optional[Any] = None,
                 staging_root: str = ".output") -> None:
        """
            Construct an LvSeedIsoBuilder.

            :param command_runner: Optional ``ICommandRunner`` used to
                invoke ``genisoimage`` / ``xorriso``.  When ``None`` the
                builder stages document text only.
            :param staging_root: Directory under which seed documents
                are staged.
        """
        self._command_runner: Optional[Any] = command_runner
        self._staging_root: str = staging_root
        return

    def render_user_data(self, *, instance: CloudInstance,
                         keypairs: List[Any], authkey: str,
                         rendered_hostname: str) -> str:
        """
            Render the ``user-data`` document for an instance.

            SSH public keys from the spec's keypairs are injected as
            ``ssh_authorized_keys``; a ``vpn_join`` spec is rendered with
            the M6 cloud-init renderer and merged into the document.

            :param instance: The neutral :class:`CloudInstance`.
            :param keypairs: The :class:`CloudKeyPair` objects whose
                public key material should be authorised.
            :param authkey: The minted VPN auth key (or connector
                token); ignored when the instance has no ``vpn_join``.
            :param rendered_hostname: The per-domain hostname.

            :returns: The ``user-data`` document text (``#cloud-config``).
        """
        document: Dict[str, Any] = {}

        document["hostname"] = rendered_hostname

        authorized_keys: List[str] = []
        for keypair in keypairs:
            material = keypair.public_key_material
            if material is not None and len(material) > 0:
                authorized_keys.append(material)
        if len(authorized_keys) > 0:
            document["ssh_authorized_keys"] = authorized_keys

        if instance.vpn_join is not None:
            cloud_init_doc = render_cloud_init(
                spec=instance.vpn_join, authkey=authkey,
                rendered_hostname=rendered_hostname,
                image_family=instance.image.family,
            )
            document["write_files"] = cloud_init_doc["write_files"]
            document["runcmd"] = cloud_init_doc["runcmd"]

        body = yaml.safe_dump(document, default_flow_style=False,
                              sort_keys=True)
        rtnval = "#cloud-config\n" + body
        return rtnval

    def render_meta_data(self, *, instance_id: str,
                         rendered_hostname: str) -> str:
        """
            Render the ``meta-data`` document for an instance.

            :param instance_id: The NoCloud ``instance-id`` value.
            :param rendered_hostname: The per-domain hostname.

            :returns: The ``meta-data`` document text.
        """
        document: Dict[str, Any] = {
            "instance-id": instance_id,
            "local-hostname": rendered_hostname,
        }
        rtnval = yaml.safe_dump(document, default_flow_style=False,
                                sort_keys=True)
        return rtnval

    def build(self, *, user_data: str, meta_data: str,
              network_config: str, iso_path: str) -> LvSeedIsoPayload:
        """
            Build the seed payload from the three NoCloud documents.

            The content hash is a SHA-256 over the three documents joined
            in a fixed order; identical inputs always produce the same
            hash.  When a command runner is configured the physical ISO
            is produced; otherwise only the document text is staged.

            :param user_data: The ``user-data`` document text.
            :param meta_data: The ``meta-data`` document text.
            :param network_config: The ``network-config`` document text.
            :param iso_path: The on-host path of the seed ISO volume.

            :returns: An :class:`LvSeedIsoPayload`.
        """
        hasher = hashlib.sha256()
        hasher.update(b"user-data\0")
        hasher.update(user_data.encode("utf-8"))
        hasher.update(b"\0meta-data\0")
        hasher.update(meta_data.encode("utf-8"))
        hasher.update(b"\0network-config\0")
        hasher.update(network_config.encode("utf-8"))
        content_hash = hasher.hexdigest()

        self._stage_documents(user_data=user_data, meta_data=meta_data,
                              network_config=network_config,
                              content_hash=content_hash)

        if self._command_runner is not None:
            self._materialise_iso(iso_path=iso_path,
                                  content_hash=content_hash)

        rtnval = LvSeedIsoPayload(user_data=user_data, meta_data=meta_data,
                                  network_config=network_config,
                                  content_hash=content_hash,
                                  iso_path=iso_path)
        return rtnval

    def _stage_documents(self, *, user_data: str, meta_data: str,
                         network_config: str, content_hash: str) -> str:
        """
            Stage the three NoCloud documents to the staging root.

            :param user_data: The ``user-data`` document text.
            :param meta_data: The ``meta-data`` document text.
            :param network_config: The ``network-config`` document text.
            :param content_hash: The deterministic content hash used as
                the staging directory name.

            :returns: The staging directory path.
        """
        directory = os.path.join(self._staging_root, "cidata", content_hash)
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        # The cidata user-data can embed a minted VPN/Tailscale authkey, so the
        # staging dir and its files must not be world-readable on multi-user hosts.
        os.chmod(directory, 0o700)

        documents = {
            "user-data": user_data,
            "meta-data": meta_data,
            "network-config": network_config,
        }
        for filename, text in documents.items():
            path = os.path.join(directory, filename)
            # Create with 0600 atomically (no world-readable window) since
            # user-data may contain a secret.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(text)

        rtnval = directory
        return rtnval

    def _materialise_iso(self, *, iso_path: str,
                         content_hash: str) -> None:
        """
            Invoke the command runner to produce the physical seed ISO.

            :param iso_path: The on-host ISO output path.
            :param content_hash: The staging directory name.

            :returns: ``None``.
        """
        directory = os.path.join(self._staging_root, "cidata", content_hash)
        command = [
            "genisoimage", "-output", iso_path, "-volid", "cidata",
            "-joliet", "-rock", directory,
        ]
        self._command_runner.run(command=command)
        return
