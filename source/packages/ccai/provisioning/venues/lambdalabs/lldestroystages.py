"""
    .. module:: lldestroystages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: LlDestroyStages — terminates instances and de-registers VPN
               devices for the Lambda Labs venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from ccai.provisioning.venues.vpncleanup import delete_vpn_device

from ccai.provisioning.venues.lambdalabs.llnaming import instance_name_for
from ccai.provisioning.venues.lambdalabs.lambdalabsspec import (
    LambdalabsSpec
)


class LlDestroyStages:
    """
        The Lambda Labs destroy stages.

        Destroy terminates every instance whose venue-side name matches
        the run, deletes 1-click clusters, and — for any VPN-joined
        instance — invokes ``IVPNControlPlane.delete_device`` so the VPN
        control plane does not accumulate stale device registrations.
        Lambda Labs manages file-system lifecycle outside this provisioner,
        so file systems are detached (left in place), never deleted.
    """

    def __init__(self, *, client: Any) -> None:
        """
            Construct an LlDestroyStages.

            :param client: The Lambda Labs interop client.
        """
        self._client = client
        return

    def destroy(self, *, spec: Optional[LambdalabsSpec], run_id: str,
                vpn_records: List[Dict[str, Any]],
                vpn_control_plane: Optional[Any], aspects: Any) -> None:
        """
            Terminate run-owned instances and clean up VPN devices.

            :param spec: The :class:`LambdalabsSpec`, or ``None`` when
                destroying from a persisted run id.
            :param run_id: The provisioning run id.
            :param vpn_records: The VPN-device records captured at apply.
            :param vpn_control_plane: Optional ``IVPNControlPlane`` impl.
            :param aspects: Behaviour control for the interop client.

            :returns: ``None``.
        """
        owned_names: List[str] = []
        if spec is not None:
            for inst in spec.instances:
                owned_names.append(
                    instance_name_for(spec_name=inst.name, run_id=run_id)
                )

        live_instances = self._client.list_instances(aspects=aspects)
        terminate_ids: List[str] = []
        for instance in live_instances:
            if spec is None:
                if instance.name.endswith("-" + _short(run_id=run_id)):
                    terminate_ids.append(instance.identifier)
            elif instance.name in owned_names:
                terminate_ids.append(instance.identifier)

        if len(terminate_ids) > 0:
            self._client.terminate_instances(instance_ids=terminate_ids,
                                             aspects=aspects)

        # Tear down any 1-click clusters owned by the run.
        live_clusters = self._client.list_clusters(aspects=aspects)
        for cluster in live_clusters:
            if spec is None:
                if cluster.name.endswith("-" + _short(run_id=run_id)):
                    self._client.delete_cluster(cluster_id=cluster.identifier,
                                                aspects=aspects)
            elif cluster.name in owned_names:
                self._client.delete_cluster(cluster_id=cluster.identifier,
                                            aspects=aspects)

        # VPN control-plane device cleanup for VPN-joined instances.
        if vpn_control_plane is not None:
            for record in vpn_records:
                device_id = record.get("vpn_device_id", None)
                if device_id is None or len(str(device_id)) == 0:
                    continue
                delete_vpn_device(vpn_control_plane=vpn_control_plane,
                                  device_id=device_id, aspects=aspects)
        return


def _short(*, run_id: str) -> str:
    """
        Return the short form of a run id used for prefix matching.

        :param run_id: The full provisioning run id.

        :returns: The first eight characters of the run id.
    """
    if run_id is None:
        rtnval = "run"
        return rtnval
    if len(run_id) <= 8:
        rtnval = run_id
        return rtnval
    rtnval = run_id[:8]
    return rtnval
