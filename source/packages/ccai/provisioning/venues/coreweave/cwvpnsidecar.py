"""
    .. module:: cwvpnsidecar
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CwVpnSidecar — renders a userspace-mode Tailscale sidecar
        container into a Pod template, or the alternative subnet-router
        DaemonSet, when a workload carries a VPNJoinSpec.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List


# A pinned, minimal Tailscale image. Userspace mode needs no privileged
# container and no /dev/net/tun device, which is the §7.6-aligned default
# for a workload pod inside CoreWeave CKS.
TAILSCALE_IMAGE = "tailscale/tailscale:stable"

_AUTHKEY_ENV = "TS_AUTHKEY"


class CwVpnSidecar:
    """
        Renders the Tailscale connectivity surface for a CoreWeave workload.

        Two shapes are supported:

        - :meth:`render` — injects a **userspace-mode** ``tailscale`` sidecar
          container into a Pod template. Userspace mode (``--tun=userspace-
          networking``) needs no ``NET_ADMIN`` capability and no host TUN
          device, which is the safe default inside a multi-tenant CKS pod.
        - :meth:`render_subnet_router_daemonset` — emits a subnet-router
          DaemonSet manifest for the case where the workload must advertise
          routes to the rest of the tailnet.
    """

    def _sidecar_container(self, *, vpn_join: Any, authkey: str,
                           hostname: str) -> Dict[str, Any]:
        """
            Build the userspace-mode Tailscale sidecar container fragment.

            :param vpn_join: The :class:`VPNJoinSpec` for the workload.
            :param authkey: A freshly minted, ephemeral auth key.
            :param hostname: The rendered Tailscale hostname.

            :returns: The container dict.
        """
        env_list = [
            {"name": _AUTHKEY_ENV, "value": authkey},
            {"name": "TS_HOSTNAME", "value": hostname},
            {"name": "TS_USERSPACE", "value": "true"},
            {"name": "TS_STATE_DIR", "value": "mem:"},
        ]

        advertise_tags = getattr(vpn_join, "advertise_tags", None)
        if advertise_tags is not None and len(advertise_tags) > 0:
            env_list.append({"name": "TS_EXTRA_ARGS",
                             "value": "--advertise-tags={}".format(
                                 ",".join(advertise_tags))})

        container: Dict[str, Any] = {
            "name": "tailscale",
            "image": TAILSCALE_IMAGE,
            "env": env_list,
        }
        return container

    def render(self, *, vpn_join: Any, pod_template: Dict[str, Any],
               authkey: str, hostname: str) -> Dict[str, Any]:
        """
            Inject a userspace-mode Tailscale sidecar into a Pod template.

            :param vpn_join: The :class:`VPNJoinSpec` for the workload.
            :param pod_template: The Pod template dict to mutate. The dict is
                copied; the original is left untouched.
            :param authkey: A freshly minted ephemeral auth key. It is placed
                in the sidecar environment and never persisted elsewhere.
            :param hostname: The rendered Tailscale hostname for the pod.

            :returns: A new Pod template dict carrying the sidecar.
        """
        import copy

        rendered = copy.deepcopy(pod_template)

        spec_section = rendered.get("spec", None)
        if spec_section is None:
            spec_section = {}
            rendered["spec"] = spec_section

        containers = spec_section.get("containers", None)
        if containers is None:
            containers = []
            spec_section["containers"] = containers

        sidecar = self._sidecar_container(vpn_join=vpn_join, authkey=authkey,
                                          hostname=hostname)
        containers.append(sidecar)

        rtnval = rendered
        return rtnval

    def render_subnet_router_daemonset(self, *, vpn_join: Any, authkey: str,
                                       namespace: str, run_id: str,
                                       routes: List[str]) -> Dict[str, Any]:
        """
            Render a subnet-router DaemonSet manifest.

            :param vpn_join: The :class:`VPNJoinSpec` for the workload.
            :param authkey: A freshly minted ephemeral auth key.
            :param namespace: The target Kubernetes namespace.
            :param run_id: The ccai run identifier (label value).
            :param routes: The CIDR routes the router advertises.

            :returns: A DaemonSet manifest dict.
        """
        labels = {
            "codecraftai-run-id": run_id,
            "app": "coreweave-tailscale-subnet-router",
        }

        env_list = [
            {"name": _AUTHKEY_ENV, "value": authkey},
            {"name": "TS_USERSPACE", "value": "true"},
            {"name": "TS_STATE_DIR", "value": "mem:"},
            {"name": "TS_ROUTES", "value": ",".join(routes)},
        ]

        container = {
            "name": "tailscale-subnet-router",
            "image": TAILSCALE_IMAGE,
            "env": env_list,
        }

        manifest: Dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "DaemonSet",
            "metadata": {
                "name": "coreweave-tailscale-subnet-router",
                "namespace": namespace,
                "labels": labels,
            },
            "spec": {
                "selector": {"matchLabels": labels},
                "template": {
                    "metadata": {"labels": labels},
                    "spec": {"containers": [container]},
                },
            },
        }

        rtnval = manifest
        return rtnval


__all__ = ["CwVpnSidecar", "TAILSCALE_IMAGE"]
