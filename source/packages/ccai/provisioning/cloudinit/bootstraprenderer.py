"""
    .. module:: bootstraprenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Composes every first-boot fragment a CloudInstance declares
               into one cloud-init document.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>

    Venue renderers historically checked ``instance.vpn_join`` and called
    :func:`render_cloud_init` directly.  As more bootstrap concerns arrive
    (Python environments today), that per-venue branching would have to be
    repeated in every venue.  This module is the single place that knows
    which instance slots produce cloud-init fragments and in what order;
    venues call :func:`render_instance_cloud_init` and only decide how to
    ship the resulting document (base64, verbatim, seed ISO, ...).
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

import yaml

from ccai.provisioning.cloudinit.cloudinitmerge import merge_cloud_init_fragments
from ccai.provisioning.cloudinit.pythonenvcloudinitrenderer import (
    render_python_env_cloud_init
)
from ccai.provisioning.cloudinit.vpncloudinitrenderer import render_cloud_init
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


CLOUD_CONFIG_HEADER = "#cloud-config"


def render_instance_cloud_init(*, instance: CloudInstance,
                               authkey: Optional[str] = None,
                               rendered_hostname: Optional[str] = None
                               ) -> Optional[Dict[str, Any]]:
    """
        Render and merge every cloud-init fragment the instance declares.

        Order: VPN join first (so the overlay is up before anything that
        might need a private index), then Python environments.  A raw
        ``user_data_script`` is appended as a final ``runcmd`` entry so it
        runs after the managed bootstrap.

        :param instance: The neutral CloudInstance.
        :param authkey: Minted VPN auth-key; required when ``vpn_join`` is
                        set (an empty string is substituted otherwise).
        :param rendered_hostname: Hostname rendered from the join spec
                                  template; defaults to the instance name.

        :returns: The merged fragment, or ``None`` when the instance
                  declares no bootstrap content at all.
    """
    fragments: List[Optional[Dict[str, Any]]] = []

    if instance.vpn_join is not None:
        effective_hostname = rendered_hostname
        if effective_hostname is None or len(effective_hostname) == 0:
            effective_hostname = instance.name
        effective_authkey = authkey if authkey is not None else ""
        fragments.append(render_cloud_init(
            spec=instance.vpn_join,
            authkey=effective_authkey,
            rendered_hostname=effective_hostname,
            image_family=instance.image.family,
        ))

    python_environments = instance.python_environments
    if python_environments is not None and len(python_environments) > 0:
        fragments.append(render_python_env_cloud_init(
            specs=python_environments,
            image_family=instance.image.family,
        ))

    raw_script = instance.user_data_script
    if len(fragments) == 0:
        rtnval: Optional[Dict[str, Any]] = None
        return rtnval

    merged = merge_cloud_init_fragments(*fragments)
    if raw_script is not None and len(raw_script) > 0:
        runcmd: List[Any] = list(merged.get("runcmd", []))
        runcmd.append(["sh", "-c", raw_script])
        merged["runcmd"] = runcmd

    rtnval = merged
    return rtnval


def render_instance_user_data(*, instance: CloudInstance,
                              authkey: Optional[str] = None,
                              rendered_hostname: Optional[str] = None
                              ) -> Optional[str]:
    """
        Render the complete ``#cloud-config`` document for an instance.

        :param instance: The neutral CloudInstance.
        :param authkey: Minted VPN auth-key when ``vpn_join`` is set.
        :param rendered_hostname: Hostname for the join spec.

        :returns: The YAML document with the ``#cloud-config`` header; the
                  raw ``user_data_script`` verbatim when that is the only
                  bootstrap content; ``None`` when there is none.
    """
    fragment = render_instance_cloud_init(
        instance=instance, authkey=authkey, rendered_hostname=rendered_hostname,
    )
    if fragment is None:
        raw_script = instance.user_data_script
        if raw_script is None or len(raw_script) == 0:
            rtnval: Optional[str] = None
            return rtnval
        rtnval = raw_script
        return rtnval

    body = yaml.safe_dump(fragment, default_flow_style=False, sort_keys=False)
    rtnval = "{}\n{}".format(CLOUD_CONFIG_HEADER, body)
    return rtnval


__all__ = [
    "CLOUD_CONFIG_HEADER",
    "render_instance_cloud_init",
    "render_instance_user_data",
]
