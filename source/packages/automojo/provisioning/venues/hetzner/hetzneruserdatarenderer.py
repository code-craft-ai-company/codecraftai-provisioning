"""
    .. module:: hetzneruserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Renderer producing Hetzner Server ``user_data`` payloads,
               including VPN-join cloud-init bootstrap.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

import yaml

from automojo.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance


class HetznerUserDataRenderer:
    """
        Renderer producing the ``user_data`` string handed to
        ``client.servers.create``.

        When a CloudInstance carries a ``vpn_join`` spec, the renderer uses
        the shared :func:`render_cloud_init` helper to build the cloud-init
        ``write_files`` / ``runcmd`` fragment and merges it with any raw
        ``user_data_script`` declared on the instance.
    """

    @classmethod
    def render(cls, *, instance: CloudInstance,
               authkey: Optional[str] = None,
               rendered_hostname: Optional[str] = None
               ) -> Optional[str]:
        """
            Render the ``user_data`` payload for a Hetzner Server.

            :param instance: The neutral CloudInstance.
            :param authkey: Minted VPN auth-key (required when vpn_join set).
            :param rendered_hostname: Hostname rendered from the join spec
                                      template (defaults to instance name).

            :returns: A cloud-config ``user_data`` string, or None when the
                      instance declares no bootstrap content.
        """
        has_vpn = instance.vpn_join is not None
        raw_script = instance.user_data_script

        if has_vpn is False:
            if raw_script is None or len(raw_script) == 0:
                rtnval: Optional[str] = None
                return rtnval
            rtnval = raw_script
            return rtnval

        effective_hostname = rendered_hostname
        if effective_hostname is None or len(effective_hostname) == 0:
            effective_hostname = instance.name

        effective_authkey = authkey if authkey is not None else ""

        fragment = render_cloud_init(
            spec=instance.vpn_join,
            authkey=effective_authkey,
            rendered_hostname=effective_hostname,
            image_family=instance.image.family,
        )

        cloud_config: Dict[str, Any] = {}
        write_files: List[Any] = list(fragment.get("write_files", []))
        runcmd: List[Any] = list(fragment.get("runcmd", []))

        if raw_script is not None and len(raw_script) > 0:
            runcmd.append(["sh", "-c", raw_script])

        cloud_config["write_files"] = write_files
        cloud_config["runcmd"] = runcmd

        body = yaml.safe_dump(cloud_config, default_flow_style=False,
                              sort_keys=True)
        rtnval = "#cloud-config\n{}".format(body)
        return rtnval
