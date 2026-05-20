"""
    .. module:: crusoeuserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CrusoeUserDataRenderer — builds instance user-data, folding in
        the VPN-join cloud-init snippet from the M6 renderer.

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


class CrusoeUserDataRenderer:
    """
        Builds the ``user_data`` payload supplied on a Crusoe instance launch.

        When the instance carries a ``vpn_join`` spec the renderer folds the
        M6 cloud-init snippet (``render_cloud_init``) into a ``#cloud-config``
        document; otherwise it passes through any raw ``user_data_script``.
    """

    def render(self, *, instance: CloudInstance,
               authkey: Optional[str]) -> Optional[str]:
        """
            Render the user-data payload for an instance.

            :param instance: The neutral CloudInstance.
            :param authkey: The minted VPN auth key, when a VPN join is
                requested.

            :returns: The user-data string, or ``None`` when neither a VPN
                join nor a raw user-data script is present.
        """
        if instance.vpn_join is not None:
            effective_authkey = authkey if authkey is not None else ""
            image_family = instance.image.family
            rendered_hostname = self._rendered_hostname(instance=instance)

            cloud_init = render_cloud_init(spec=instance.vpn_join,
                                           authkey=effective_authkey,
                                           rendered_hostname=rendered_hostname,
                                           image_family=image_family)
            document = "#cloud-config\n" + yaml.safe_dump(
                cloud_init, default_flow_style=False, sort_keys=True)
            rtnval: Optional[str] = document
            return rtnval

        if instance.user_data_script is not None:
            rtnval = instance.user_data_script
            return rtnval

        rtnval = None
        return rtnval

    def _rendered_hostname(self, *, instance: CloudInstance) -> str:
        """
            Compute the hostname for the VPN-join cloud-init snippet.

            :param instance: The neutral CloudInstance.

            :returns: The rendered hostname string.
        """
        template = instance.vpn_join.hostname_template
        rtnval = template.replace("{name}", instance.name)
        return rtnval
