"""
    .. module:: rpinventory
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpInventory — enumerates the RunPod pods and volumes belonging
        to a run and emits ProvisionedResource records.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)

from ccai.provisioning.venues.runpod.rpnaming import belongs_to_run
from ccai.provisioning.venues.runpod.rpsidecartag import RpSidecarTag


class RpInventory:
    """
        Enumerates the RunPod resources that belong to a run.

        :meth:`list_run` discovers Pods and Network Volumes by the
        ``-<run-id-short>`` name suffix and emits :class:`ProvisionedResource`
        records. A Pod record carries the public IP when one is allocated and
        the overlay (VPN) IP when it is recorded. Sidecar tags are recovered
        and attached to each Pod record.
    """

    def list_run(self, *, spec: Any, client: Any,
                 overlay_ips: Dict[str, str] = None) -> List[ProvisionedResource]:
        """
            Enumerate the run's Pods and Network Volumes.

            :param spec: The :class:`RunpodWorkloadSpec`.
            :param client: The RunPod interop client.
            :param overlay_ips: Optional ``pod-id -> overlay-IP`` map.

            :returns: A list of :class:`ProvisionedResource` records.
        """
        effective_overlay: Dict[str, str] = {}
        if overlay_ips is not None:
            effective_overlay = overlay_ips

        run_short = spec.run_id_short
        sidecar = RpSidecarTag(runid=spec.run_id)

        rtnval: List[ProvisionedResource] = []

        for pod in client.list_pods():
            if not belongs_to_run(resource_name=pod.name,
                                  run_id_short=run_short):
                continue

            attributes: Dict[str, Any] = {
                "desired_status": getattr(pod, "desired_status", ""),
            }
            public_ip = getattr(pod, "public_ip", None)
            if public_ip is not None:
                attributes["public_ip"] = public_ip

            overlay_ip = effective_overlay.get(pod.pod_id)
            if overlay_ip is not None:
                attributes["overlay_ip"] = overlay_ip

            tags = sidecar.read(pod_id=pod.pod_id)

            rtnval.append(ProvisionedResource(kind="Pod", name=pod.name,
                                              venue_id=pod.pod_id,
                                              attributes=attributes,
                                              tags=tags))

        for volume in client.list_network_volumes():
            if not belongs_to_run(resource_name=volume.name,
                                  run_id_short=run_short):
                continue

            volume_attributes: Dict[str, Any] = {
                "size_gb": getattr(volume, "size_gb", 0),
                "data_center_id": getattr(volume, "data_center_id", ""),
            }
            rtnval.append(ProvisionedResource(kind="NetworkVolume",
                                              name=volume.name,
                                              venue_id=volume.volume_id,
                                              attributes=volume_attributes))

        return rtnval


__all__ = ["RpInventory"]
