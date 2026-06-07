"""
    .. module:: cwsunkrenderer
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: CwSunkRenderer — renders the Sunk (Slurm-on-Kubernetes)
        manifest bundle for the optional CoreWeave Slurm sub-mode.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import hashlib
import json

from typing import Any, Dict, List


RUN_ID_LABEL = "codecraftai-run-id"


class CwSunkRenderer:
    """
        Renders the Sunk Slurm-on-Kubernetes manifest bundle.

        Sunk is CoreWeave's documented optional sub-mode that runs Slurm on
        top of CKS: a Slurm controller Deployment, a ``slurmd`` DaemonSet
        pinned to the GPU node pools, and a MySQL StatefulSet for
        accounting. The bundle this renderer emits is a deterministic
        function of ``(workload_names, run_id, namespace)`` — re-rendering
        the same inputs yields a byte-identical bundle, which is the
        property the idempotent plan/apply pipeline relies on.

        Each rendered manifest is a plain dict ready to hand to the
        Kubernetes interop's manifest-apply surface; this venue never speaks
        the Kubernetes API itself.
    """

    SLURM_CONTROLLER_IMAGE = "ghcr.io/coreweave/sunk-slurmctld:stable"
    SLURMD_IMAGE = "ghcr.io/coreweave/sunk-slurmd:stable"
    MYSQL_IMAGE = "mysql:8.0"

    def render(self, *, namespace: str, run_id: str,
               workload_names: List[str]) -> List[Dict[str, Any]]:
        """
            Render the full Sunk manifest bundle.

            :param namespace: The target Kubernetes namespace.
            :param run_id: The ccai run identifier (label value).
            :param workload_names: The names of the Slurm workloads being
                placed (recorded as a controller annotation so the bundle
                is content-distinct per declared workload set).

            :returns: An ordered list of manifest dicts —
                ``[mysql StatefulSet, slurm controller Deployment,
                slurmd DaemonSet]``.
        """
        base_labels = {RUN_ID_LABEL: run_id}

        ordered_names = sorted(workload_names)

        mysql = self._render_mysql(namespace=namespace, labels=base_labels)
        controller = self._render_controller(namespace=namespace,
                                             labels=base_labels,
                                             workload_names=ordered_names)
        slurmd = self._render_slurmd(namespace=namespace, labels=base_labels)

        rtnval = [mysql, controller, slurmd]
        return rtnval

    def bundle_hash(self, *, namespace: str, run_id: str,
                    workload_names: List[str]) -> str:
        """
            Return a deterministic content hash of the rendered bundle.

            :param namespace: The target Kubernetes namespace.
            :param run_id: The ccai run identifier.
            :param workload_names: The Slurm workload names.

            :returns: A hex SHA-256 digest of the canonicalised bundle.
        """
        bundle = self.render(namespace=namespace, run_id=run_id,
                             workload_names=workload_names)
        canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"))

        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        rtnval = digest
        return rtnval

    def _render_mysql(self, *, namespace: str,
                      labels: Dict[str, str]) -> Dict[str, Any]:
        """
            Render the Sunk accounting MySQL StatefulSet.

            :param namespace: The target namespace.
            :param labels: The base label map.

            :returns: A StatefulSet manifest dict.
        """
        component_labels = dict(labels)
        component_labels["app"] = "sunk-mysql"

        manifest: Dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": "sunk-mysql", "namespace": namespace,
                         "labels": component_labels},
            "spec": {
                "serviceName": "sunk-mysql",
                "replicas": 1,
                "selector": {"matchLabels": component_labels},
                "template": {
                    "metadata": {"labels": component_labels},
                    "spec": {"containers": [
                        {"name": "mysql", "image": self.MYSQL_IMAGE}]},
                },
            },
        }
        return manifest

    def _render_controller(self, *, namespace: str, labels: Dict[str, str],
                           workload_names: List[str]) -> Dict[str, Any]:
        """
            Render the Sunk Slurm controller Deployment.

            :param namespace: The target namespace.
            :param labels: The base label map.
            :param workload_names: The Slurm workload names (annotation).

            :returns: A Deployment manifest dict.
        """
        component_labels = dict(labels)
        component_labels["app"] = "sunk-slurmctld"

        manifest: Dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": "sunk-slurmctld",
                "namespace": namespace,
                "labels": component_labels,
                "annotations": {
                    "codecraftai-sunk-workloads": ",".join(workload_names),
                },
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": component_labels},
                "template": {
                    "metadata": {"labels": component_labels},
                    "spec": {"containers": [
                        {"name": "slurmctld",
                         "image": self.SLURM_CONTROLLER_IMAGE}]},
                },
            },
        }
        return manifest

    def _render_slurmd(self, *, namespace: str,
                       labels: Dict[str, str]) -> Dict[str, Any]:
        """
            Render the Sunk ``slurmd`` DaemonSet.

            :param namespace: The target namespace.
            :param labels: The base label map.

            :returns: A DaemonSet manifest dict.
        """
        component_labels = dict(labels)
        component_labels["app"] = "sunk-slurmd"

        manifest: Dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "DaemonSet",
            "metadata": {"name": "sunk-slurmd", "namespace": namespace,
                         "labels": component_labels},
            "spec": {
                "selector": {"matchLabels": component_labels},
                "template": {
                    "metadata": {"labels": component_labels},
                    "spec": {"containers": [
                        {"name": "slurmd", "image": self.SLURMD_IMAGE}]},
                },
            },
        }
        return manifest


__all__ = ["CwSunkRenderer"]
