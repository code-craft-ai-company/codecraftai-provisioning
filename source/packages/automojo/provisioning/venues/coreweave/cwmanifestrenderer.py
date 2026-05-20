"""
    .. module:: cwmanifestrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CwManifestRenderer — translates neutral WorkloadJob /
        WorkloadService resources into the typed Kubernetes workload specs
        consumed by ``automojo-interop-kubernetes``.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


from typing import Any, Dict, List, Optional

from automojo.interop.kubernetes.specs.workloadspecs import (
    DeploymentSpec, JobSpec, PvcSpec, ServiceSpec
)

from automojo.provisioning.venues.coreweave.cwlabeltranslator import (
    CwLabelTranslator
)
from automojo.provisioning.venues.coreweave.cwnodepoolselector import (
    CwNodePoolSelector
)


RUN_ID_LABEL = "automojo-run-id"


def _first_accelerator(workload: Any) -> Optional[Any]:
    """
        Return the first accelerator spec carried by a workload, or ``None``.

        :param workload: A :class:`WorkloadJob` or :class:`WorkloadService`.

        :returns: The first :class:`CloudAcceleratorSpec`, or ``None``.
    """
    accelerators = getattr(workload, "accelerators", None)
    if accelerators is None:
        rtnval = None
        return rtnval

    if len(accelerators) == 0:
        rtnval = None
        return rtnval

    rtnval = accelerators[0]
    return rtnval


class CwManifestRenderer:
    """
        Translates the neutral workload model onto the typed Kubernetes
        workload specs.

        - A :class:`WorkloadJob` renders to a :class:`JobSpec`.
        - A :class:`WorkloadService` renders to a :class:`DeploymentSpec`
          plus a :class:`ServiceSpec`.
        - A shared-filesystem mount renders to a :class:`PvcSpec`.

        GPU placement (``nodeSelector`` / ``resources.limits``) is resolved
        through a :class:`CwNodePoolSelector`. Neutral tags become
        Kubernetes labels via :class:`CwLabelTranslator`; every resource
        also carries the ``automojo-run-id`` label.
    """

    def __init__(self, *, selector: CwNodePoolSelector,
                 label_translator: Optional[CwLabelTranslator] = None) -> None:
        """
            Initialise the renderer.

            :param selector: The :class:`CwNodePoolSelector` used to resolve
                accelerator placement.
            :param label_translator: Optional :class:`CwLabelTranslator`.

            :returns: ``None``.
        """
        self._selector = selector
        if label_translator is not None:
            self._labels = label_translator
        else:
            self._labels = CwLabelTranslator()
        return

    def _run_labels(self, *, run_id: str,
                    tags: Optional[List[Dict[str, str]]]) -> Dict[str, str]:
        """
            Build the label map for a resource — neutral tags plus the
            run-id label.

            :param run_id: The automojo run identifier.
            :param tags: Optional neutral tag list.

            :returns: A Kubernetes label dict.
        """
        labels = self._labels.to_k8s(neutral_tags=tags if tags is not None else [])
        labels[RUN_ID_LABEL] = run_id
        return labels

    def render_job(self, *, workload: Any, run_id: str) -> JobSpec:
        """
            Render a :class:`WorkloadJob` into a :class:`JobSpec`.

            :param workload: The neutral :class:`WorkloadJob`.
            :param run_id: The automojo run identifier.

            :returns: A typed :class:`JobSpec`.
        """
        accel = _first_accelerator(workload)
        node_selector = self._selector.node_selector_for(accel_spec=accel)
        gpu_resources = self._selector.gpu_resources_for(accel_spec=accel)

        labels = self._run_labels(run_id=run_id, tags=None)

        rtnval = JobSpec(name=workload.name, image=workload.image,
                         command=list(workload.command),
                         env=dict(workload.env),
                         resources=gpu_resources,
                         restart_policy=workload.restart_policy,
                         completions=workload.replicas,
                         parallelism=workload.replicas,
                         node_selector=node_selector,
                         labels=labels)
        return rtnval

    def render_service_deployment(self, *, workload: Any,
                                  run_id: str) -> DeploymentSpec:
        """
            Render a :class:`WorkloadService` into a :class:`DeploymentSpec`.

            :param workload: The neutral :class:`WorkloadService`.
            :param run_id: The automojo run identifier.

            :returns: A typed :class:`DeploymentSpec`.
        """
        accel = _first_accelerator(workload)
        node_selector = self._selector.node_selector_for(accel_spec=accel)
        gpu_resources = self._selector.gpu_resources_for(accel_spec=accel)

        labels = self._run_labels(run_id=run_id, tags=None)

        container_port = None
        if len(workload.ports) > 0:
            first_port = workload.ports[0]
            container_port = first_port.get("port", None)

        rtnval = DeploymentSpec(name=workload.name, image=workload.image,
                                replicas=workload.replicas,
                                container_port=container_port,
                                env=dict(workload.env),
                                resources=gpu_resources,
                                labels=labels,
                                node_selector=node_selector)
        return rtnval

    def render_service_service(self, *, workload: Any,
                               run_id: str) -> ServiceSpec:
        """
            Render the Kubernetes Service for a :class:`WorkloadService`.

            :param workload: The neutral :class:`WorkloadService`.
            :param run_id: The automojo run identifier.

            :returns: A typed :class:`ServiceSpec`.
        """
        labels = self._run_labels(run_id=run_id, tags=None)

        port_numbers: List[int] = []
        for entry in workload.ports:
            port_value = entry.get("port", None)
            if port_value is not None:
                port_numbers.append(port_value)

        if len(port_numbers) == 0:
            port_numbers = [80]

        selector = {RUN_ID_LABEL: run_id, "app": workload.name}

        rtnval = ServiceSpec(name=workload.name, ports=port_numbers,
                             selector=selector,
                             service_type=workload.exposure,
                             labels=labels)
        return rtnval

    def render_shared_fs_pvc(self, *, mount: Any, run_id: str,
                             storage_class: str,
                             storage_request: str = "100Gi") -> PvcSpec:
        """
            Render a :class:`PvcSpec` binding a shared-filesystem mount onto
            a CoreWeave CSI StorageClass.

            :param mount: A :class:`SharedFsMountSpec`.
            :param run_id: The automojo run identifier.
            :param storage_class: The CoreWeave CSI StorageClass name.
            :param storage_request: The requested storage size.

            :returns: A typed :class:`PvcSpec`.
        """
        labels = self._run_labels(run_id=run_id, tags=None)

        rtnval = PvcSpec(name=mount.filesystem_name,
                         storage_request=storage_request,
                         access_modes=["ReadWriteMany"],
                         storage_class=storage_class,
                         labels=labels)
        return rtnval


__all__ = ["CwManifestRenderer", "RUN_ID_LABEL"]
