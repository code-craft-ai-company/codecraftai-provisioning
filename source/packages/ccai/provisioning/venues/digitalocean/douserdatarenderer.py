"""
    .. module:: douserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DoUserDataRenderer — builds Droplet ``user_data`` cloud-init
               payloads, including VPN-join bootstrap.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Optional

import yaml

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_user_data
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


class DoUserDataRenderer:
    """
        Renders the cloud-init ``user_data`` string passed to a DigitalOcean
        Droplet at create time.

        When the owning :class:`CloudInstance` carries a ``vpn_join`` spec the
        renderer delegates to the shared M6 :func:`render_instance_user_data` so the
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
        rendered_hostname: Optional[str] = None
        if instance.vpn_join is not None:
            rendered_hostname = instance.vpn_join.hostname_template.replace(
                "{instance_name}", instance.name
            )

        # The shared composer folds VPN join, Python environments and the
        # raw user_data_script (as a trailing runcmd entry) into one
        # document; a raw script alone passes through verbatim.
        document = render_instance_user_data(
            instance=instance, authkey=authkey,
            rendered_hostname=rendered_hostname,
        )
        rtnval = document if document is not None else ""
        return rtnval
