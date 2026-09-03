"""
    .. module:: hetzneruserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Renderer producing Hetzner Server ``user_data`` payloads,
               including VPN-join cloud-init bootstrap.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

import yaml

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_user_data
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


class HetznerUserDataRenderer:
    """
        Renderer producing the ``user_data`` string handed to
        ``client.servers.create``.

        When a CloudInstance carries a ``vpn_join`` spec, the renderer uses
        the shared :func:`render_instance_user_data` helper to build the cloud-init
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
        # The shared composer folds VPN join, Python environments and the
        # raw user_data_script (as a trailing runcmd entry) into one
        # document; a raw script alone passes through verbatim.
        rtnval = render_instance_user_data(
            instance=instance, authkey=authkey,
            rendered_hostname=rendered_hostname,
        )
        return rtnval
