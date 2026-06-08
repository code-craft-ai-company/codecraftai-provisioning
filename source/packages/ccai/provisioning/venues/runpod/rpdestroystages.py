"""
    .. module:: rpdestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpDestroyStages — reverses an apply: stop + terminate the
        run's pods, de-register VPN devices, then delete the run's network
        volumes.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, List, Optional

from ccai.provisioning.venues.runpod.rpnaming import belongs_to_run


class RpDestroyStages:
    """
        The destroy-lifecycle stages of the RunPod workload provisioner.

        :meth:`destroy` reverses an apply. Pods owned by the run (matched by
        the ``-<run-id-short>`` name suffix) are stopped and terminated; for
        a VPN-joined pod the matching Tailscale device is de-registered via
        the ``IVPNControlPlane``; finally the run's Network Volumes are
        deleted. Termination and volume deletion are idempotent at the
        interop layer, so a destroy on a partially-destroyed run completes
        cleanly.
    """

    def destroy(self, *, spec: Any, client: Any,
                vpn_control_plane: Optional[Any] = None,
                vpn_device_ids: Optional[List[str]] = None,
                aspects: Optional[Any] = None) -> List[str]:
        """
            Stop and terminate the run's pods, de-register VPN devices, then
            delete the run's network volumes.

            :param spec: The :class:`RunpodWorkloadSpec`.
            :param client: The RunPod interop client.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` used to
                de-register VPN devices.
            :param vpn_device_ids: Optional list of Tailscale device ids the
                apply registered for this run.
            :param aspects: Behaviour control propagated into the VPN
                de-register call.

            :returns: The list of terminated pod ids.
        """
        run_short = spec.run_id_short

        terminated: List[str] = []
        for pod in client.list_pods():
            if not belongs_to_run(resource_name=pod.name,
                                  run_id_short=run_short):
                continue

            client.stop_pod(pod_id=pod.pod_id)
            client.terminate_pod(pod_id=pod.pod_id)
            terminated.append(pod.pod_id)

        if vpn_control_plane is not None and vpn_device_ids is not None:
            for device_id in vpn_device_ids:
                vpn_control_plane.delete_device(device_id=device_id,
                                                aspects=aspects)

        for volume in client.list_network_volumes():
            if belongs_to_run(resource_name=volume.name,
                              run_id_short=run_short):
                client.delete_network_volume(volume_id=volume.volume_id)

        rtnval = terminated
        return rtnval


__all__ = ["RpDestroyStages"]
