"""
    .. module:: rpresolver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpResolver — maps neutral accelerator / image specs onto
        RunPod GPU types and container image references.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import os

from typing import Any, List, Optional

from automojo.provisioning.venues.runpod.rperrors import RpValidationError


# Neutral accelerator catalog name -> RunPod gpuTypeId.  RunPod identifies
# GPU types by a descriptive id string; this map covers the catalog names
# the framework emits.
_GPU_TYPE_MAP = {
    "H100_SXM": "NVIDIA H100 80GB HBM3",
    "H100_PCIE": "NVIDIA H100 PCIe",
    "A100_SXM": "NVIDIA A100-SXM4-80GB",
    "A100_PCIE": "NVIDIA A100 80GB PCIe",
    "A40": "NVIDIA A40",
    "L40S": "NVIDIA L40S",
    "L4": "NVIDIA L4",
    "RTX_4090": "NVIDIA GeForce RTX 4090",
    "RTX_A6000": "NVIDIA RTX A6000",
}


class RpResolver:
    """
        Resolves neutral accelerator and image specifications onto RunPod
        primitives.

        RunPod identifies GPUs by a ``gpuTypeId`` string and containers by an
        image reference. The resolver maps the framework's neutral catalog
        names onto those, and resolves a neutral image triple onto a
        container image URL when no explicit RunPod pod template is supplied.
    """

    def accelerator_to_gpu_type(self, *, accel_spec: Any) -> str:
        """
            Map a neutral :class:`CloudAcceleratorSpec` onto a RunPod
            ``gpuTypeId``.

            :param accel_spec: The neutral accelerator spec.

            :returns: The RunPod GPU type identifier.

            :raises: :class:`RpValidationError` when the accelerator is not a
                GPU or its model has no RunPod GPU type mapping.
        """
        kind = getattr(accel_spec, "kind", None)
        if kind != "GPU":
            err_msg_lines = ["RunPod only provisions GPU accelerators."]
            err_msg_lines.append("KIND: {}".format(kind))
            err_msg = os.linesep.join(err_msg_lines)
            raise RpValidationError(err_msg)

        model = getattr(accel_spec, "model", None)
        gpu_type_id = _GPU_TYPE_MAP.get(model)
        if gpu_type_id is None:
            supported = ", ".join(sorted(_GPU_TYPE_MAP.keys()))
            err_msg_lines = ["No RunPod GPU type maps to the requested "
                             "accelerator model."]
            err_msg_lines.append("MODEL: {}".format(model))
            err_msg_lines.append("SUPPORTED: {}".format(supported))
            err_msg = os.linesep.join(err_msg_lines)
            raise RpValidationError(err_msg)

        rtnval = gpu_type_id
        return rtnval

    def image_to_template_or_url(self, *, family: str, version: str,
                                 architecture: str = "x86_64") -> str:
        """
            Resolve a neutral image triple onto a container image reference.

            RunPod containers run an OCI image directly; there is no separate
            machine-image catalog. A ``family`` that already looks like a
            registry reference (contains ``/`` or ``:``) is returned
            verbatim; otherwise a Docker Hub reference ``family:version`` is
            composed.

            :param family: The image family or a registry reference.
            :param version: The image version / tag.
            :param architecture: The CPU architecture (informational).

            :returns: A container image reference string.

            :raises: :class:`RpValidationError` when ``family`` is empty.
        """
        if family is None or len(family) == 0:
            raise RpValidationError("An image family must not be empty.")

        if "/" in family or ":" in family:
            rtnval = family
            return rtnval

        effective_version = version
        if effective_version is None or len(effective_version) == 0:
            effective_version = "latest"

        rtnval = "{}:{}".format(family, effective_version)
        return rtnval

    def supported_gpu_models(self) -> List[str]:
        """
            Return the neutral accelerator models RunPod can realise.

            :returns: A sorted list of supported neutral GPU model names.
        """
        rtnval = sorted(_GPU_TYPE_MAP.keys())
        return rtnval

    def gpu_type_for_workload(self, *, workload: Any) -> Optional[str]:
        """
            Resolve the RunPod GPU type for the first accelerator a workload
            carries.

            :param workload: A :class:`WorkloadJob` / :class:`WorkloadService`.

            :returns: The RunPod GPU type identifier, or ``None`` when the
                workload carries no accelerator.
        """
        accelerators = getattr(workload, "accelerators", None)
        if accelerators is None:
            rtnval: Optional[str] = None
            return rtnval
        if len(accelerators) == 0:
            rtnval = None
            return rtnval

        rtnval = self.accelerator_to_gpu_type(accel_spec=accelerators[0])
        return rtnval


__all__ = ["RpResolver"]
