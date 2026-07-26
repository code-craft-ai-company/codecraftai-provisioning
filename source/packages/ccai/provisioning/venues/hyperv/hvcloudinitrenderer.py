"""
    .. module:: hvcloudinitrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: HvCloudInitRenderer — builds NoCloud config-drive ISO payloads
        (Linux) and SetupComplete.cmd unattend scripts (Windows) for Hyper-V
        guests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import hashlib

from typing import Any, Dict, List, Optional

import yaml

from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_azure_cse, render_cloud_init
)
from ccai.interfaces.vpnjoinspec import VPNJoinSpec


class HvCloudInitPayload:
    """
        Rendered cloud-init delivery payload for a single Hyper-V guest.

        Carries the NoCloud ISO file contents (meta-data, user-data,
        network-config) for Linux guests, or a SetupComplete.cmd body for
        Windows guests, plus a content hash for determinism assertions.
    """

    def __init__(self, *, is_windows: bool,
                 iso_files: Optional[Dict[str, str]] = None,
                 setup_complete: Optional[str] = None,
                 content_hash: str = "") -> None:
        """
            Construct an HvCloudInitPayload.

            :param is_windows: Whether this payload targets a Windows guest.
            :param iso_files: Map of NoCloud ISO member file -> contents.
            :param setup_complete: The SetupComplete.cmd body for Windows.
            :param content_hash: A stable hash of the payload contents.
        """
        self.is_windows: bool = is_windows
        self.iso_files: Dict[str, str] = (
            dict(iso_files) if iso_files is not None else {}
        )
        self.setup_complete: Optional[str] = setup_complete
        self.content_hash: str = content_hash
        return


class HvCloudInitRenderer:
    """
        Renderer producing Hyper-V cloud-init delivery payloads.

        Linux guests receive a NoCloud config-drive ISO; the renderer
        produces the ISO member files (``meta-data``, ``user-data``,
        ``network-config``).  Windows guests receive a ``SetupComplete.cmd``
        unattend script.  Both paths fold a :class:`VPNJoinSpec` in via the
        shared M6 ``vpncloudinitrenderer``.
    """

    def build_iso(self, *, instance_name: str, image_family: str,
                  ssh_keys: List[str],
                  user_data: Optional[str] = None,
                  network_config: Optional[Dict[str, Any]] = None,
                  vpn_join: Optional[VPNJoinSpec] = None,
                  vpn_authkey: str = "",
                  rendered_hostname: str = "") -> HvCloudInitPayload:
        """
            Build a NoCloud config-drive ISO payload for a Linux guest.

            :param instance_name: The neutral instance name.
            :param image_family: The image family (ubuntu, debian, rhel...).
            :param ssh_keys: Public-key material seeded into the default
                user via cloud-init.
            :param user_data: Optional raw user-data script appended as a
                ``runcmd`` shell entry.
            :param network_config: Optional NoCloud network-config dict.
            :param vpn_join: Optional VPNJoinSpec folded into user-data.
            :param vpn_authkey: Minted VPN auth key / connector token.
            :param rendered_hostname: Hostname rendered for the guest.

            :returns: An HvCloudInitPayload carrying the ISO member files.
        """
        host_name = rendered_hostname
        if host_name is None or len(host_name) == 0:
            host_name = instance_name

        cloud_config: Dict[str, Any] = {}

        effective_keys = ssh_keys if ssh_keys is not None else []
        if len(effective_keys) > 0:
            cloud_config["ssh_authorized_keys"] = list(effective_keys)

        write_files: List[Dict[str, Any]] = []
        runcmd: List[Any] = []

        if vpn_join is not None:
            vpn_fragment = render_cloud_init(spec=vpn_join,
                                             authkey=vpn_authkey,
                                             rendered_hostname=host_name,
                                             image_family=image_family)
            write_files.extend(vpn_fragment.get("write_files", []))
            runcmd.extend(vpn_fragment.get("runcmd", []))

        if user_data is not None and len(user_data) > 0:
            runcmd.append(["sh", "-c", user_data])

        if len(write_files) > 0:
            cloud_config["write_files"] = write_files
        if len(runcmd) > 0:
            cloud_config["runcmd"] = runcmd

        user_data_doc = "#cloud-config\n" + yaml.safe_dump(
            cloud_config, sort_keys=True, default_flow_style=False)

        meta_data_doc = yaml.safe_dump(
            {"instance-id": instance_name, "local-hostname": host_name},
            sort_keys=True, default_flow_style=False)

        iso_files: Dict[str, str] = {
            "meta-data": meta_data_doc,
            "user-data": user_data_doc,
        }

        if network_config is not None:
            iso_files["network-config"] = yaml.safe_dump(
                network_config, sort_keys=True, default_flow_style=False)

        content_hash = self._hash_files(iso_files=iso_files)

        rtnval = HvCloudInitPayload(is_windows=False, iso_files=iso_files,
                                    setup_complete=None,
                                    content_hash=content_hash)
        return rtnval

    def build_setupcomplete(self, *, instance_name: str, image_family: str,
                            vpn_join: Optional[VPNJoinSpec] = None,
                            vpn_authkey: str = "",
                            rendered_hostname: str = "") -> HvCloudInitPayload:
        """
            Build a SetupComplete.cmd unattend payload for a Windows guest.

            :param instance_name: The neutral instance name.
            :param image_family: The Windows image family.
            :param vpn_join: Optional VPNJoinSpec folded into the script.
            :param vpn_authkey: Minted VPN auth key.
            :param rendered_hostname: Hostname rendered for the guest.

            :returns: An HvCloudInitPayload carrying the SetupComplete body.
        """
        host_name = rendered_hostname
        if host_name is None or len(host_name) == 0:
            host_name = instance_name

        lines: List[str] = ["@echo off"]

        if vpn_join is not None:
            cse = render_azure_cse(spec=vpn_join, authkey=vpn_authkey,
                                   rendered_hostname=host_name,
                                   image_family=image_family)
            command = cse["settings"]["commandToExecute"]
            lines.append(command)

        setup_complete = "\r\n".join(lines) + "\r\n"
        content_hash = self._hash_files(
            iso_files={"SetupComplete.cmd": setup_complete})

        rtnval = HvCloudInitPayload(is_windows=True, iso_files={},
                                    setup_complete=setup_complete,
                                    content_hash=content_hash)
        return rtnval

    @staticmethod
    def _hash_files(*, iso_files: Dict[str, str]) -> str:
        """
            Compute a stable content hash over a member-file map.

            :param iso_files: Map of member file name -> contents.

            :returns: A hex SHA-256 digest string.
        """
        hasher = hashlib.sha256()
        for name in sorted(iso_files.keys()):
            hasher.update(name.encode("utf-8"))
            hasher.update(b"\x00")
            hasher.update(iso_files[name].encode("utf-8"))
            hasher.update(b"\x00")
        rtnval = hasher.hexdigest()
        return rtnval
