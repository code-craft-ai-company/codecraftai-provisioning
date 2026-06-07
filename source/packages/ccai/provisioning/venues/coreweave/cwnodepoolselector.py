"""
    .. module:: cwnodepoolselector
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CwNodePoolSelector — resolves a neutral accelerator /
        interconnect request onto a CoreWeave node pool and the Kubernetes
        ``nodeSelector`` / resource fragment it implies.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import os

from typing import Any, Dict, List, Optional

from ccai.provisioning.venues.coreweave.cwerrors import CwValidationError


# CoreWeave node-pool label keys (the documented label surface).
NODE_POOL_LABEL = "node.coreweave.cloud/pool"
GPU_MODEL_LABEL = "gpu.nvidia.com/model"
IB_FABRIC_LABEL = "ib.coreweave.cloud/fabric"

# Interconnect kinds that map onto an InfiniBand fabric affinity.
_INFINIBAND_KINDS = frozenset({"INFINIBAND_HDR", "INFINIBAND_NDR",
                               "INFINIBAND_XDR"})


class CwNodePoolSelector:
    """
        Resolves a neutral :class:`CloudAcceleratorSpec` (and optional
        :class:`CloudInterconnect`) onto a concrete CoreWeave node pool.

        The selector is constructed with the node-pool catalog returned by
        ``CoreweaveClient.node_pools.list`` (a list of
        :class:`CoreweaveNodePool`). :meth:`match` returns the pool whose
        ``gpu_model`` satisfies the request; :meth:`node_selector_for` and
        :meth:`gpu_resources_for` translate the request into the Kubernetes
        Pod fragments.
    """

    def __init__(self, *, node_pools: List[Any]) -> None:
        """
            Initialise the selector with a CoreWeave node-pool catalog.

            :param node_pools: A list of :class:`CoreweaveNodePool` records.

            :returns: ``None``.
        """
        self._node_pools = node_pools if node_pools is not None else []
        return

    def match(self, *, accel_spec: Optional[Any],
              interconnect: Optional[Any] = None) -> Optional[Any]:
        """
            Resolve a node pool for an accelerator request.

            :param accel_spec: A :class:`CloudAcceleratorSpec`, or ``None``
                for a CPU-only workload.
            :param interconnect: An optional :class:`CloudInterconnect`.

            :returns: The matching :class:`CoreweaveNodePool`, or ``None``
                when ``accel_spec`` is ``None`` (CPU-only — any pool).

            :raises: :class:`CwValidationError` when no pool offers the
                requested GPU model or InfiniBand fabric.
        """
        if accel_spec is None:
            rtnval = None
            return rtnval

        requested_model = accel_spec.model

        candidates = []
        for pool in self._node_pools:
            if pool.gpu_model == requested_model:
                candidates.append(pool)

        if len(candidates) == 0:
            err_msg_lines = ["No CoreWeave node pool offers the requested "
                             "accelerator model."]
            err_msg_lines.append("REQUESTED MODEL: {}".format(requested_model))
            err_msg_lines.append("AVAILABLE POOLS: ({})".format(
                len(self._node_pools)))
            for pool in self._node_pools:
                err_msg_lines.append("    {} -> {}".format(pool.name,
                                                           pool.gpu_model))
            err_msg = os.linesep.join(err_msg_lines)
            raise CwValidationError(err_msg)

        if interconnect is not None and interconnect.kind in _INFINIBAND_KINDS:
            ib_candidates = []
            for pool in candidates:
                if pool.interconnect in _INFINIBAND_KINDS:
                    ib_candidates.append(pool)

            if len(ib_candidates) == 0:
                err_msg_lines = ["No CoreWeave node pool with the requested "
                                 "GPU model offers an InfiniBand fabric."]
                err_msg_lines.append("REQUESTED MODEL: {}".format(
                    requested_model))
                err_msg_lines.append("REQUESTED FABRIC: {}".format(
                    interconnect.kind))
                err_msg = os.linesep.join(err_msg_lines)
                raise CwValidationError(err_msg)

            candidates = ib_candidates

        rtnval = candidates[0]
        return rtnval

    def node_selector_for(self, *, accel_spec: Optional[Any],
                          interconnect: Optional[Any] = None) -> Dict[str, str]:
        """
            Build the Kubernetes ``nodeSelector`` label map for a request.

            :param accel_spec: A :class:`CloudAcceleratorSpec`, or ``None``.
            :param interconnect: An optional :class:`CloudInterconnect`.

            :returns: A node-selector label dict (empty for CPU-only).

            :raises: :class:`CwValidationError` when the request cannot be
                satisfied.
        """
        pool = self.match(accel_spec=accel_spec, interconnect=interconnect)

        rtnval: Dict[str, str] = {}
        if pool is None:
            return rtnval

        rtnval[NODE_POOL_LABEL] = pool.name
        rtnval[GPU_MODEL_LABEL] = pool.gpu_model

        if interconnect is not None and interconnect.kind in _INFINIBAND_KINDS:
            rtnval[IB_FABRIC_LABEL] = pool.interconnect

        return rtnval

    def gpu_resources_for(self, *, accel_spec: Optional[Any],
                          interconnect: Optional[Any] = None) -> Dict[str, Dict[str, str]]:
        """
            Build the container ``resources`` fragment for an accelerator
            request.

            :param accel_spec: A :class:`CloudAcceleratorSpec`, or ``None``.
            :param interconnect: An optional :class:`CloudInterconnect`.

            :returns: A ``{"limits": {...}}`` resources fragment, or an empty
                dict for a CPU-only request.
        """
        rtnval: Dict[str, Dict[str, str]] = {}
        if accel_spec is None:
            return rtnval

        limits: Dict[str, str] = {
            "nvidia.com/gpu": str(accel_spec.count),
        }

        if interconnect is not None and interconnect.kind in _INFINIBAND_KINDS:
            # CoreWeave exposes RDMA host devices through the documented
            # ``nvidia.com/hostdev`` resource for IB-attached pods.
            limits["nvidia.com/hostdev"] = str(accel_spec.count)

        rtnval["limits"] = limits
        return rtnval


__all__ = ["CwNodePoolSelector", "NODE_POOL_LABEL", "GPU_MODEL_LABEL",
           "IB_FABRIC_LABEL"]
