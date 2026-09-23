"""
    .. module:: crusoeuserdatarenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CrusoeUserDataRenderer — builds instance user-data, folding in
        the VPN-join cloud-init snippet from the M6 renderer.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Optional

from ccai.provisioning.cloudinit.bootstraprenderer import (
    render_instance_user_data
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


class CrusoeUserDataRenderer:
    """
        Builds the ``user_data`` payload supplied on a Crusoe instance launch.

        When the instance carries a ``vpn_join`` spec the renderer folds the
        M6 cloud-init snippet (``render_instance_user_data``) into a ``#cloud-config``
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
        rendered_hostname: Optional[str] = None
        if instance.vpn_join is not None:
            rendered_hostname = self._rendered_hostname(instance=instance)

        # The shared composer folds every bootstrap slot the instance
        # declares (VPN join, Python environments, raw user_data_script)
        # into one document, or passes the raw script through verbatim.
        rtnval = render_instance_user_data(
            instance=instance, authkey=authkey,
            rendered_hostname=rendered_hostname,
        )
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
