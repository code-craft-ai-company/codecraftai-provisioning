"""
    .. module:: ntxcloudinitrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: NtxCloudInitRenderer — builds the base64 cloud-init user_data
               placed in a Prism VM's ``guest_customization`` field.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from base64 import b64encode
from typing import Any, List, Optional

import yaml

from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)


class NtxCloudInitRenderer:
    """
        Builds the cloud-init ``user_data`` document for a Prism VM.

        The renderer merges three optional sources: the SSH public keys
        from the run's :class:`CloudKeyPair` list, the raw
        ``user_data_script`` on the instance, and — when the instance
        carries a :class:`VPNJoinSpec` — the VPN-join cloud-init fragment
        produced by the M6 :func:`render_cloud_init` renderer.  The merged
        ``#cloud-config`` document is base64-encoded for placement under
        ``guest_customization.cloud_init.user_data``.
    """

    def render(self, *, instance: CloudInstance, keypairs: List[Any],
               authkey: str, rendered_hostname: str) -> Optional[str]:
        """
            Render the base64-encoded cloud-init user_data for a VM.

            :param instance: The neutral :class:`CloudInstance`.
            :param keypairs: The run's :class:`CloudKeyPair` list.
            :param authkey: The minted VPN auth key (empty when no VPN).
            :param rendered_hostname: The venue-side VM hostname.

            :returns: The base64-encoded user_data string, or ``None``
                when the VM needs no guest customisation.
        """
        document = self._build_document(instance=instance,
                                        keypairs=keypairs,
                                        authkey=authkey,
                                        rendered_hostname=rendered_hostname)
        if document is None:
            rtnval: Optional[str] = None
            return rtnval

        body_lines = ["#cloud-config"]
        body_lines.append(yaml.safe_dump(document, default_flow_style=False,
                                         sort_keys=True))
        body = "\n".join(body_lines)

        encoded = b64encode(body.encode("utf-8")).decode("utf-8")
        rtnval = encoded
        return rtnval

    def _build_document(self, *, instance: CloudInstance,
                        keypairs: List[Any], authkey: str,
                        rendered_hostname: str) -> Optional[dict]:
        """
            Build the merged cloud-init document dict.

            :param instance: The neutral :class:`CloudInstance`.
            :param keypairs: The run's :class:`CloudKeyPair` list.
            :param authkey: The minted VPN auth key.
            :param rendered_hostname: The venue-side VM hostname.

            :returns: The cloud-init document dict, or ``None`` when there
                is nothing to customise.
        """
        document: dict = {}

        ssh_keys: List[str] = []
        effective_keypairs = keypairs if keypairs is not None else []
        for keypair in effective_keypairs:
            material = getattr(keypair, "public_key_material", None)
            if material is not None and len(material) > 0:
                ssh_keys.append(material)
        if len(ssh_keys) > 0:
            document["ssh_authorized_keys"] = ssh_keys

        document["hostname"] = rendered_hostname

        if instance.vpn_join is not None:
            fragment = render_cloud_init(
                spec=instance.vpn_join, authkey=authkey,
                rendered_hostname=rendered_hostname,
                image_family=instance.image.family,
            )
            for key, value in fragment.items():
                document[key] = value

        if (instance.user_data_script is not None
                and len(instance.user_data_script) > 0):
            existing = document.get("runcmd", None)
            if existing is None:
                existing = []
            existing.append(["sh", "-c", instance.user_data_script])
            document["runcmd"] = existing

        # A document carrying only the hostname is still meaningful for a
        # deterministic cloud-init, so any non-empty document is rendered.
        if len(document) == 0:
            rtnval: Optional[dict] = None
            return rtnval

        rtnval = document
        return rtnval
