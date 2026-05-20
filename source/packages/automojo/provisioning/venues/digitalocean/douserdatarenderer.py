"""
    .. module:: douserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DoUserDataRenderer — builds Droplet ``user_data`` cloud-init
               payloads, including VPN-join bootstrap.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Optional

import yaml

from automojo.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance


class DoUserDataRenderer:
    """
        Renders the cloud-init ``user_data`` string passed to a DigitalOcean
        Droplet at create time.

        When the owning :class:`CloudInstance` carries a ``vpn_join`` spec the
        renderer delegates to the shared M6 :func:`render_cloud_init` so the
        Tailscale / Twingate bootstrap is identical to every other venue.
    """

    def __init__(self) -> None:
        """
            Construct a DoUserDataRenderer.
        """
        return

    def render(self, *, instance: CloudInstance,
               authkey: Optional[str] = None) -> str:
        """
            Render the ``user_data`` body for a Droplet.

            :param instance: The neutral CloudInstance.
            :param authkey: Optional minted VPN auth key / connector token.

            :returns: The cloud-init ``user_data`` string (empty when there
                      is neither a raw script nor a vpn_join spec).
        """
        if instance.vpn_join is None:
            base_script = instance.user_data_script
            if base_script is None:
                rtnval = ""
                return rtnval
            rtnval = base_script
            return rtnval

        effective_authkey = authkey if authkey is not None else ""
        rendered_hostname = instance.vpn_join.hostname_template.replace(
            "{instance_name}", instance.name
        )
        cloud_init = render_cloud_init(
            spec=instance.vpn_join,
            authkey=effective_authkey,
            rendered_hostname=rendered_hostname,
            image_family=instance.image.family,
        )

        body_lines = ["#cloud-config"]
        body_lines.append(yaml.safe_dump(cloud_init, sort_keys=False))

        raw_script = instance.user_data_script
        if raw_script is not None and len(raw_script) > 0:
            body_lines.append("# --- user_data_script ---")
            body_lines.append(raw_script)

        rtnval = "\n".join(body_lines)
        return rtnval
