"""
    .. module:: pvecloudinitrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PveCloudInitRenderer — renders a VM's cloud-init user-data
               snippet and uploads it to a Proxmox snippet storage with
               SHA256 content-addressed deduplication.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import hashlib

from typing import Any, List, Optional

import yaml

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_cloud_init
)
from ccai.provisioning.cloudinit.cloudinitmerge import merge_cloud_init_fragments
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.cloud.cloudkeypair import CloudKeyPair


class PveCloudInitSnippet:
    """
        A rendered, uploaded cloud-init snippet.

        Carries the ``cicustom`` config value the venue references on the
        VM config (``user=<storage>:snippets/<filename>``) and the SHA256
        digest used for content-addressed dedup.
    """

    def __init__(self, *, cicustom_value: str, digest: str,
                 filename: str, body: str) -> None:
        """
            Construct a PveCloudInitSnippet.

            :param cicustom_value: The ``cicustom`` config value.
            :param digest: The SHA256 hex digest of the rendered body.
            :param filename: The snippet filename on the storage.
            :param body: The rendered ``#cloud-config`` body.
        """
        self.cicustom_value: str = cicustom_value
        self.digest: str = digest
        self.filename: str = filename
        self.body: str = body
        return


class PveCloudInitRenderer:
    """
        Renders the per-VM cloud-init user-data snippet and uploads it to a
        Proxmox snippet storage.

        When the instance carries a ``vpn_join`` spec the body is produced
        by the M6 :func:`render_cloud_init`; SSH keypairs are merged into
        ``ssh_authorized_keys`` either way.  Uploads are content-addressed
        by SHA256 — re-uploading an identical snippet is skipped, so the
        whole apply path stays idempotent (the spec's snippet-dedup
        requirement).
    """

    def __init__(self, *, client: Any,
                 snippet_storage: str = "local") -> None:
        """
            Construct a PveCloudInitRenderer.

            :param client: The Proxmox interop client.
            :param snippet_storage: The Proxmox storage that holds
                cloud-init snippets (``content`` must include ``snippets``).
        """
        self._client = client
        self._snippet_storage: str = snippet_storage
        return

    def render_and_upload(self, *, node_name: str, instance: CloudInstance,
                          keypairs: List[CloudKeyPair],
                          rendered_hostname: str, authkey: str,
                          aspects: Any) -> Optional[PveCloudInitSnippet]:
        """
            Render the VM cloud-init snippet and upload it (deduped).

            :param node_name: The node the snippet storage lives on.
            :param instance: The neutral :class:`CloudInstance`.
            :param keypairs: The spec keypairs to inject as authorized
                SSH keys.
            :param rendered_hostname: The per-VM hostname.
            :param authkey: The minted VPN auth key (or connector token).
            :param aspects: Behaviour control for the interop client.

            :returns: A :class:`PveCloudInitSnippet`, or ``None`` when the
                instance needs no cloud-init snippet.
        """
        body = self.render_body(instance=instance, keypairs=keypairs,
                                rendered_hostname=rendered_hostname,
                                authkey=authkey)
        if body is None:
            rtnval: Optional[PveCloudInitSnippet] = None
            return rtnval

        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        filename = "codecraftai-{}.yaml".format(digest[:16])

        already = self._client.storage.has_snippet(
            node_name=node_name, storage=self._snippet_storage,
            filename=filename, aspects=aspects,
        )
        if already is not True:
            self._client.storage.upload_snippet(
                node_name=node_name, storage=self._snippet_storage,
                filename=filename, content=body, aspects=aspects,
            )

        cicustom_value = "user={}:snippets/{}".format(
            self._snippet_storage, filename
        )
        rtnval = PveCloudInitSnippet(cicustom_value=cicustom_value,
                                     digest=digest, filename=filename,
                                     body=body)
        return rtnval

    @staticmethod
    def render_body(*, instance: CloudInstance,
                    keypairs: List[CloudKeyPair],
                    rendered_hostname: str,
                    authkey: str) -> Optional[str]:
        """
            Render the ``#cloud-config`` body for an instance.

            :param instance: The neutral :class:`CloudInstance`.
            :param keypairs: The spec keypairs to inject.
            :param rendered_hostname: The per-VM hostname.
            :param authkey: The minted VPN auth key (or connector token).

            :returns: The rendered ``#cloud-config`` string, or ``None``
                when the instance needs no cloud-init snippet.
        """
        ssh_keys: List[str] = []
        for keypair in keypairs:
            if keypair.name == instance.keypair:
                ssh_keys.append(keypair.public_key_material)

        document: dict = {}
        if len(ssh_keys) > 0:
            document["ssh_authorized_keys"] = ssh_keys
        document["hostname"] = rendered_hostname

        # The shared composer folds VPN join, Python environments and the
        # raw user_data_script (as a trailing ``sh -c`` runcmd entry) into
        # one fragment.  It returns None when only a raw script is
        # declared, in which case the script is appended here as before.
        fragment = render_instance_cloud_init(
            instance=instance, authkey=authkey,
            rendered_hostname=rendered_hostname,
        )
        if fragment is not None:
            document = merge_cloud_init_fragments(document, fragment)

        has_user_payload = False
        if len(ssh_keys) > 0:
            has_user_payload = True
        if fragment is not None:
            has_user_payload = True
        if instance.user_data_script is not None:
            if len(instance.user_data_script) > 0:
                has_user_payload = True

        if has_user_payload is not True:
            rtnval: Optional[str] = None
            return rtnval

        if fragment is None and instance.user_data_script is not None:
            if len(instance.user_data_script) > 0:
                document["runcmd"] = document.get("runcmd", [])
                document["runcmd"].append(
                    ["bash", "-c", instance.user_data_script]
                )

        body = yaml.safe_dump(document, default_flow_style=False,
                              sort_keys=True)
        rtnval = "#cloud-config\n" + body
        return rtnval
