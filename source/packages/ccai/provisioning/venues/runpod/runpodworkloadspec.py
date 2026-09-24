"""
    .. module:: runpodworkloadspec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RunpodWorkloadSpec — the resource bundle the RunPod workload
        provisioner operates on.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from ccai.provisioning.venues.runpod.rperrors import RpValidationError


# RunPod capacity tiers, mapped onto the interop RunpodCloudType.
RUNPOD_TIER_SECURE = "secure"
RUNPOD_TIER_COMMUNITY = "community"

_SUPPORTED_TIERS = (RUNPOD_TIER_SECURE, RUNPOD_TIER_COMMUNITY)


def require_supported_tier(*, tier: Any) -> None:
    """
        Refuse a capacity tier RunPod does not offer.

        Called by ``validate`` and again wherever the tier is acted on,
        because ``apply`` can be driven without a prior ``validate`` and an
        unknown tier must never fall through to a Secure Cloud launch.

        :param tier: The spec's capacity tier.

        :returns: ``None``.

        :raises: :class:`RpValidationError` when the tier is not one of the
            supported tiers.
    """
    if tier not in _SUPPORTED_TIERS:
        err_msg_lines = ["The RunPod capacity tier is not supported."]
        err_msg_lines.append("TIER: {!r}".format(tier))
        err_msg_lines.append("SUPPORTED TIERS: {}".format(
            ", ".join(_SUPPORTED_TIERS)))
        err_msg = os.linesep.join(err_msg_lines)
        raise RpValidationError(err_msg)

    return


class RunpodWorkloadSpec:
    """
        The declared resource bundle a :class:`RunpodWorkloadProvisioner`
        realises onto RunPod.

        RunPod is container-shaped, so every :class:`WorkloadJob` /
        :class:`WorkloadService` becomes a RunPod pod. The spec carries the
        run identifier, the data center, the capacity tier, the workload
        lists, optional network-volume requests, per-workload
        :class:`VPNJoinSpec` instances keyed by workload name, optional
        unsupported / unrealised resources (used by ``validate`` to report
        honest-fit failures), and the neutral tag list.
    """

    def __init__(self, *, run_id: str, data_center_id: str,
                 tier: Optional[str] = None,
                 jobs: Optional[List[Any]] = None,
                 services: Optional[List[Any]] = None,
                 network_volumes: Optional[List[Dict[str, Any]]] = None,
                 vpn_joins: Optional[Dict[str, Any]] = None,
                 buckets: Optional[List[Any]] = None,
                 load_balancers: Optional[List[Any]] = None,
                 dns_records: Optional[List[Any]] = None,
                 interconnects: Optional[List[Any]] = None,
                 networks: Optional[List[Any]] = None,
                 subnets: Optional[List[Any]] = None,
                 security_groups: Optional[List[Any]] = None,
                 key_pairs: Optional[List[Any]] = None,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """
            Construct a :class:`RunpodWorkloadSpec`.

            :param run_id: The ccai run identifier.
            :param data_center_id: The RunPod data center pods are launched
                in.
            :param tier: ``secure`` or ``community``; ``None`` defaults to
                ``secure``.
            :param jobs: The :class:`WorkloadJob` resources to realise.
            :param services: The :class:`WorkloadService` resources to
                realise.
            :param network_volumes: Optional network-volume requests, each a
                dict with ``name`` and ``size_gb`` (and optional
                ``existing_id``).
            :param vpn_joins: Optional ``workload-name -> VPNJoinSpec`` map.
            :param buckets: Object-storage requests — unsupported by RunPod.
            :param load_balancers: Load-balancer requests — unsupported.
            :param dns_records: DNS-record requests — unsupported.
            :param interconnects: Inter-pod interconnect requests —
                unsupported when the kind is not NONE.
            :param networks: Network requests — not realised (warn).
            :param subnets: Subnet requests — not realised (warn).
            :param security_groups: Security-group requests — not realised
                (warn).
            :param key_pairs: Key-pair requests — not realised (warn).
            :param tags: The neutral tag list.

            :returns: ``None``.
        """
        self.run_id = run_id
        self.data_center_id = data_center_id
        self.tier = tier if tier is not None else RUNPOD_TIER_SECURE
        self.jobs = jobs if jobs is not None else []
        self.services = services if services is not None else []
        self.network_volumes = network_volumes if network_volumes is not None else []
        self.vpn_joins = vpn_joins if vpn_joins is not None else {}
        self.buckets = buckets if buckets is not None else []
        self.load_balancers = load_balancers if load_balancers is not None else []
        self.dns_records = dns_records if dns_records is not None else []
        self.interconnects = interconnects if interconnects is not None else []
        self.networks = networks if networks is not None else []
        self.subnets = subnets if subnets is not None else []
        self.security_groups = security_groups if security_groups is not None else []
        self.key_pairs = key_pairs if key_pairs is not None else []
        self.tags = tags if tags is not None else {}
        return

    @property
    def run_id_short(self) -> str:
        """
            The short run-id prefix used to name and discover resources.

            :returns: The first eight characters of the run identifier.
        """
        rtnval = self.run_id[0:8]
        return rtnval


__all__ = ["RunpodWorkloadSpec", "RUNPOD_TIER_SECURE", "RUNPOD_TIER_COMMUNITY",
           "require_supported_tier"]
