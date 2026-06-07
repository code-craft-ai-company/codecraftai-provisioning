"""
    .. module:: xencloudinitrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: XenCloudInitRenderer — renders the cloud-init payload delivered
        to an XCP-ng VM through the xenstore ``vm-data/cloud-init`` keys.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import base64

from typing import Dict, Optional

import yaml

from ccai.provisioning.cloudinit.vpncloudinitrenderer import (
    render_cloud_init
)
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


# The xenstore key the XCP-ng cloud-init datasource reads the base64
# user-data from.  XCP-ng's NoCloud datasource consumes ``vm-data/...``
# keys handed to the VM through ``VM.xenstore_data``.
XENSTORE_USERDATA_KEY = "vm-data/cloud-init/user-data"
XENSTORE_ENCODING_KEY = "vm-data/cloud-init/encoding"


class XenCloudInitRenderer:
    """
        Renders the XCP-ng cloud-init xenstore payload for a VM.

        When a :class:`CloudInstance` carries a ``vpn_join`` spec the renderer
        delegates to the M6 :func:`render_cloud_init` to produce the
        cloud-init document, serialises it to a ``#cloud-config`` YAML
        string, and base64-encodes it for delivery through the VM's
        ``xenstore_data`` map.  When the instance carries only a raw
        ``user_data_script`` that script is encoded verbatim.  When the
        instance needs no bootstrap metadata the renderer returns an empty
        map and the apply stage pushes nothing.
    """

    def render(self, *, spec_vm: CloudInstance, vpn_join: Optional[object],
               authkey: str, rendered_hostname: str) -> Dict[str, str]:
        """
            Render the xenstore ``vm-data/cloud-init`` key map for a VM.

            :param spec_vm: The neutral :class:`CloudInstance`.
            :param vpn_join: The instance's ``VPNJoinSpec``, or None.
            :param authkey: The minted VPN auth key (or connector token);
                            ignored when ``vpn_join`` is None.
            :param rendered_hostname: The per-VM hostname.

            :returns: A dict of xenstore keys to push through
                      ``VM.add_to_xenstore_data``; empty when the VM needs
                      no bootstrap metadata.
        """
        user_data = self._user_data_body(
            spec_vm=spec_vm, vpn_join=vpn_join, authkey=authkey,
            rendered_hostname=rendered_hostname)
        if user_data is None:
            rtnval: Dict[str, str] = {}
            return rtnval

        encoded = base64.b64encode(user_data.encode("utf-8")).decode("ascii")
        rtnval = {
            XENSTORE_USERDATA_KEY: encoded,
            XENSTORE_ENCODING_KEY: "base64",
        }
        return rtnval

    def _user_data_body(self, *, spec_vm: CloudInstance,
                        vpn_join: Optional[object], authkey: str,
                        rendered_hostname: str) -> Optional[str]:
        """
            Build the raw cloud-init user-data body for a VM.

            :param spec_vm: The neutral :class:`CloudInstance`.
            :param vpn_join: The instance's ``VPNJoinSpec``, or None.
            :param authkey: The minted VPN auth key.
            :param rendered_hostname: The per-VM hostname.

            :returns: The user-data string, or None when none is needed.
        """
        if vpn_join is not None:
            image_family = spec_vm.image.family
            cloud_init_doc = render_cloud_init(
                spec=vpn_join, authkey=authkey,
                rendered_hostname=rendered_hostname,
                image_family=image_family)
            body = yaml.safe_dump(cloud_init_doc,
                                  default_flow_style=False, sort_keys=True)
            rtnval = "#cloud-config\n" + body
            return rtnval

        script = spec_vm.user_data_script
        if script is not None and len(script) > 0:
            rtnval = script
            return rtnval

        rtnval = None
        return rtnval
