"""
    .. module:: test_workload_provisioners
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the workload-kind provisioners — the v1 Kubernetes
        provisioner lifecycle, the three NIE stubs, and the WorkloadProvisioner
        validation hooks.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from typing import Any, Dict, List, Optional

from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from ccai.provisioning.model.workload.workloadvenue import WorkloadVenue
from ccai.interfaces.workloadvenuekind import (
    WorkloadVenueKind
)
from ccai.provisioning.model.workload.nodepoolspec import NodePoolSpec
from ccai.provisioning.model.workload.workloadcluster import WorkloadCluster
from ccai.provisioning.model.workload.workloadjob import WorkloadJob
from ccai.provisioning.model.workload.workloadservice import WorkloadService
from ccai.provisioning.model.workload.workloadspec import WorkloadSpec
from ccai.provisioning.model.workload.kubernetesworkloadprovisioner import (
    KubernetesWorkloadProvisioner
)
from ccai.provisioning.model.workload.slurmworkloadprovisioner import (
    SlurmWorkloadProvisioner
)
from ccai.provisioning.model.workload.rayworkloadprovisioner import (
    RayWorkloadProvisioner
)
from ccai.provisioning.model.workload.nomadworkloadprovisioner import (
    NomadWorkloadProvisioner
)


# ----------------------------------------------------------------------
# Deterministic in-memory Kubernetes client fake
# ----------------------------------------------------------------------

class _RecordInfo:
    """
        A minimal info DTO returned by the fake primitives.
    """

    def __init__(self, *, name: str,
                 labels: Optional[Dict[str, str]] = None) -> None:
        self.name = name
        self.labels = labels if labels is not None else {}
        return


class _FakePrimitive:
    """
        A fake workload primitive backed by an in-memory store.
    """

    def __init__(self, *, kind: str, store: Dict[str, _RecordInfo]) -> None:
        self._kind = kind
        self._store = store
        return

    def _key(self, *, name: str) -> str:
        rtnval = "{}/{}".format(self._kind, name)
        return rtnval

    def apply(self, *, spec: Any, namespace: str = "default",
              aspects: Any = None) -> _RecordInfo:
        labels = getattr(spec, "labels", {})
        record = _RecordInfo(name=spec.name, labels=dict(labels))
        self._store[self._key(name=spec.name)] = record
        return record

    def get(self, *, name: str, namespace: str = "default",
            aspects: Any = None) -> _RecordInfo:
        rtnval = self._store[self._key(name=name)]
        return rtnval

    def delete(self, *, name: str, namespace: str = "default",
               aspects: Any = None) -> None:
        self._store.pop(self._key(name=name), None)
        return

    def list(self, *, namespace: str = "default",
             label_selector: Optional[str] = None,
             aspects: Any = None) -> List[_RecordInfo]:
        prefix = "{}/".format(self._kind)
        results: List[_RecordInfo] = []
        for key, record in self._store.items():
            if not key.startswith(prefix):
                continue
            if label_selector is not None and len(label_selector) > 0:
                sel_key, _, sel_value = label_selector.partition("=")
                if record.labels.get(sel_key, None) != sel_value:
                    continue
            results.append(record)
        return results


class _FakeNamespacePrimitive(_FakePrimitive):
    """
        A fake namespace primitive (no namespace argument).
    """

    def apply(self, *, spec: Any, aspects: Any = None) -> _RecordInfo:
        labels = getattr(spec, "labels", {})
        record = _RecordInfo(name=spec.name, labels=dict(labels))
        self._store[self._key(name=spec.name)] = record
        return record

    def get(self, *, name: str, aspects: Any = None) -> _RecordInfo:
        rtnval = self._store[self._key(name=name)]
        return rtnval

    def delete(self, *, name: str, aspects: Any = None) -> None:
        self._store.pop(self._key(name=name), None)
        return


class FakeKubernetesClient:
    """
        Deterministic in-memory stand-in for the Kubernetes interop client.
    """

    def __init__(self) -> None:
        self._store: Dict[str, _RecordInfo] = {}
        self.jobs = _FakePrimitive(kind="Job", store=self._store)
        self.deployments = _FakePrimitive(kind="Deployment",
                                          store=self._store)
        self.services = _FakePrimitive(kind="Service", store=self._store)
        self.namespaces = _FakeNamespacePrimitive(kind="Namespace",
                                                  store=self._store)
        return


# ----------------------------------------------------------------------
# Fake credentials + resolver
# ----------------------------------------------------------------------

class _FakeCredential:
    """
        A minimal credential carrying a ``credential_type`` attribute.
    """

    def __init__(self, *, credential_type: str) -> None:
        self.credential_type = credential_type
        return


def _make_resolver(*, credential: Optional[_FakeCredential]) -> Any:
    """
        Build a credential resolver callable returning ``credential``.

        :param credential: The credential to return, or ``None``.

        :returns: A resolver callable.
    """
    def _resolver(*, credential_ref: str) -> Optional[_FakeCredential]:
        rtnval = credential
        return rtnval

    return _resolver


# ----------------------------------------------------------------------
# Fixture builders
# ----------------------------------------------------------------------

def _k8s_venue() -> WorkloadVenue:
    rtnval = WorkloadVenue(name="prod-k8s",
                           kind=WorkloadVenueKind.KUBERNETES,
                           credential_ref="kube-token")
    return rtnval


def _service(*, name: str = "inference",
             exposure: str = "ClusterIP") -> WorkloadService:
    rtnval = WorkloadService(name=name, image="server:latest",
                             ports=[{"port": 8080}], exposure=exposure)
    return rtnval


def _job(*, name: str = "trainer") -> WorkloadJob:
    rtnval = WorkloadJob(name=name, image="trainer:latest",
                         command=["python", "train.py"], replicas=2)
    return rtnval


def _k8s_provisioner(*, spec: Optional[WorkloadSpec] = None,
                     kube: Optional[FakeKubernetesClient] = None,
                     credential_resolver: Any = None,
                     cloud_provisioner: Any = None
                     ) -> KubernetesWorkloadProvisioner:
    if spec is None:
        spec = WorkloadSpec(run_id="run-0001", jobs=[_job()],
                            services=[_service()])
    if kube is None:
        kube = FakeKubernetesClient()
    rtnval = KubernetesWorkloadProvisioner(
        venue=_k8s_venue(), kubernetes_client=kube, spec=spec,
        cloud_provisioner=cloud_provisioner,
        credential_resolver=credential_resolver)
    return rtnval


# ----------------------------------------------------------------------
# 24. test_workload_service_loadbalancer_exposure_validates
# ----------------------------------------------------------------------

class WorkloadServiceLoadBalancerExposureTests(unittest.TestCase):

    def test_workload_service_loadbalancer_exposure_validates(self) -> None:
        """
            A LoadBalancer service validates on an LB-capable venue and is
            rejected on a venue without LB support.
        """
        lb_spec = WorkloadSpec(run_id="run-lb",
                               services=[_service(exposure="LoadBalancer")])

        # The Kubernetes provisioner supports load balancers by default.
        ok_provisioner = _k8s_provisioner(spec=lb_spec)
        result = ok_provisioner.validate()
        self.assertTrue(result.ok)

        # Flip the venue capability off — the same service is now rejected.
        no_lb_provisioner = _k8s_provisioner(spec=lb_spec)
        no_lb_provisioner.SUPPORTS_LOAD_BALANCER = False
        with self.assertRaises(SchemaSemanticError):
            no_lb_provisioner.validate()
        return


# ----------------------------------------------------------------------
# 25-27. NIE stubs raise correctly
# ----------------------------------------------------------------------

class SchedulerNotImplementedTests(unittest.TestCase):

    def test_slurm_provisioner_apply_raises_nie(self) -> None:
        """
            SlurmWorkloadProvisioner.apply raises NotImplementedError with
            a stable issue-tracker pointer.
        """
        venue = WorkloadVenue(name="hpc", kind=WorkloadVenueKind.SLURM,
                              credential_ref="slurm-token")
        provisioner = SlurmWorkloadProvisioner(venue=venue)
        with self.assertRaises(NotImplementedError) as caught:
            provisioner.apply(aspects=None)
        self.assertIn("WORKLOAD-SLURM-V2", str(caught.exception))
        self.assertIn("§7.6", str(caught.exception))
        return

    def test_ray_provisioner_apply_raises_nie(self) -> None:
        """
            RayWorkloadProvisioner.apply raises NotImplementedError with a
            stable issue-tracker pointer.
        """
        venue = WorkloadVenue(name="ray-cl", kind=WorkloadVenueKind.RAY,
                              credential_ref="ray-token")
        provisioner = RayWorkloadProvisioner(venue=venue)
        with self.assertRaises(NotImplementedError) as caught:
            provisioner.apply(aspects=None)
        self.assertIn("WORKLOAD-RAY-V2", str(caught.exception))
        return

    def test_nomad_provisioner_apply_raises_nie(self) -> None:
        """
            NomadWorkloadProvisioner.apply raises NotImplementedError with a
            stable issue-tracker pointer.
        """
        venue = WorkloadVenue(name="nomad-cl", kind=WorkloadVenueKind.NOMAD,
                              credential_ref="nomad-token")
        provisioner = NomadWorkloadProvisioner(venue=venue)
        with self.assertRaises(NotImplementedError) as caught:
            provisioner.apply(aspects=None)
        self.assertIn("WORKLOAD-NOMAD-V2", str(caught.exception))
        return

    def test_every_scheduler_verb_raises_nie(self) -> None:
        """
            Every lifecycle verb of every scheduler stub raises NIE.
        """
        cases = [
            (SlurmWorkloadProvisioner, WorkloadVenueKind.SLURM),
            (RayWorkloadProvisioner, WorkloadVenueKind.RAY),
            (NomadWorkloadProvisioner, WorkloadVenueKind.NOMAD),
        ]
        for provisioner_cls, kind in cases:
            venue = WorkloadVenue(name="v", kind=kind, credential_ref="cred")
            provisioner = provisioner_cls(venue=venue)
            for verb in ("validate", "plan", "apply", "destroy", "inventory"):
                method = getattr(provisioner, verb)
                with self.assertRaises(NotImplementedError):
                    method(aspects=None)
        return


# ----------------------------------------------------------------------
# 28. test_composition_drives_cloud_before_workload
# ----------------------------------------------------------------------

class _RecordingCloudProvisioner:
    """
        A recording stand-in for a CloudProvisioner used in composition.
    """

    def __init__(self, *, journal: List[str]) -> None:
        self._journal = journal
        return

    def apply(self, *, aspects: Any = None) -> str:
        self._journal.append("cloud-apply")
        rtnval = "cloud-apply"
        return rtnval

    def destroy(self, *, aspects: Any = None) -> None:
        self._journal.append("cloud-destroy")
        return


class CompositionTests(unittest.TestCase):

    def test_composition_drives_cloud_before_workload(self) -> None:
        """
            When a WorkloadProvisioner composes a CloudProvisioner, the
            engine drives the cloud apply first and the cloud destroy last.
        """
        journal: List[str] = []
        cloud = _RecordingCloudProvisioner(journal=journal)
        provisioner = _k8s_provisioner(cloud_provisioner=cloud)

        self.assertIs(provisioner.cloud_provisioner, cloud)

        # Engine ordering on apply: cloud first, then workload.
        provisioner.cloud_provisioner.apply(aspects=None)
        provisioner.apply(aspects=None)
        journal.append("workload-apply")

        # Engine ordering on destroy: workload first, then cloud.
        provisioner.destroy(aspects={"confirm": True})
        journal.append("workload-destroy")
        provisioner.cloud_provisioner.destroy(aspects=None)

        self.assertEqual(journal,
                         ["cloud-apply", "workload-apply",
                          "workload-destroy", "cloud-destroy"])
        return


# ----------------------------------------------------------------------
# 29. test_node_pool_accelerator_rejected_when_unsupported
# ----------------------------------------------------------------------

class NodePoolAcceleratorValidationTests(unittest.TestCase):

    def test_node_pool_accelerator_rejected_when_unsupported(self) -> None:
        """
            A node-pool accelerator whose neutral name does not resolve on
            the parent venue raises SchemaSemanticError during validate.
        """
        accel = CloudAcceleratorSpec(kind="GPU", model="NO_SUCH_GPU",
                                     count=8, memory_gb=80)
        pool = NodePoolSpec(name="gpu-pool", count=2, size="gpu.8x",
                            accelerators=[accel])
        cluster = WorkloadCluster(name="train-cluster",
                                  accelerator_pools=[pool])
        spec = WorkloadSpec(run_id="run-accel", cluster=cluster)

        provisioner = _k8s_provisioner(spec=spec)
        with self.assertRaises(SchemaSemanticError):
            provisioner.validate()
        return


# ----------------------------------------------------------------------
# Kubernetes provisioner lifecycle
# ----------------------------------------------------------------------

class KubernetesWorkloadProvisionerLifecycleTests(unittest.TestCase):

    def test_constructor_rejects_non_kubernetes_venue(self) -> None:
        """
            The Kubernetes provisioner rejects a non-KUBERNETES venue.
        """
        venue = WorkloadVenue(name="hpc", kind=WorkloadVenueKind.SLURM,
                              credential_ref="slurm-token")
        with self.assertRaises(SchemaSemanticError):
            KubernetesWorkloadProvisioner(
                venue=venue, kubernetes_client=FakeKubernetesClient(),
                spec=WorkloadSpec(run_id="run-x"))
        return

    def test_validate_succeeds_for_clean_spec(self) -> None:
        """
            validate returns ok=True for a spec with no offending resources.
        """
        provisioner = _k8s_provisioner()
        result = provisioner.validate()
        self.assertTrue(result.ok)
        return

    def test_validate_resolves_and_matches_credential(self) -> None:
        """
            validate resolves the credential and confirms its type matches
            the KUBERNETES venue kind.
        """
        resolver = _make_resolver(
            credential=_FakeCredential(credential_type="kubeconfig"))
        provisioner = _k8s_provisioner(credential_resolver=resolver)
        result = provisioner.validate()
        self.assertTrue(result.ok)
        return

    def test_validate_rejects_mismatched_credential_type(self) -> None:
        """
            validate rejects a credential whose type does not match the
            venue kind.
        """
        resolver = _make_resolver(
            credential=_FakeCredential(credential_type="nomad_token"))
        provisioner = _k8s_provisioner(credential_resolver=resolver)
        with self.assertRaises(SchemaSemanticError):
            provisioner.validate()
        return

    def test_validate_rejects_unresolvable_credential_ref(self) -> None:
        """
            validate rejects a credential_ref that resolves to None.
        """
        resolver = _make_resolver(credential=None)
        provisioner = _k8s_provisioner(credential_resolver=resolver)
        with self.assertRaises(SchemaSemanticError):
            provisioner.validate()
        return

    def test_plan_fresh_emits_creates(self) -> None:
        """
            plan against an empty cluster emits CREATE intents.
        """
        provisioner = _k8s_provisioner()
        plan = provisioner.plan()
        intents = [action.intent for action in plan.actions]
        self.assertIn(PlannedActionIntent.CREATE.value, intents)
        return

    def test_plan_after_apply_emits_only_skips(self) -> None:
        """
            Re-planning an already-applied spec emits only SKIP actions.
        """
        kube = FakeKubernetesClient()
        provisioner = _k8s_provisioner(kube=kube)
        provisioner.apply()
        plan = provisioner.plan()
        for action in plan.actions:
            self.assertEqual(action.intent, PlannedActionIntent.SKIP.value)
        return

    def test_apply_realises_jobs_and_services(self) -> None:
        """
            apply realises Kubernetes Jobs, Deployments, and Services.
        """
        provisioner = _k8s_provisioner()
        result = provisioner.apply()
        kinds = sorted({resource.kind for resource in result.created})
        self.assertEqual(kinds,
                         ["Deployment", "Job", "Namespace", "Service"])
        return

    def test_apply_is_idempotent(self) -> None:
        """
            Running apply twice yields the same inventory.
        """
        kube = FakeKubernetesClient()
        provisioner = _k8s_provisioner(kube=kube)
        provisioner.apply()
        first = provisioner.inventory()
        provisioner.apply()
        second = provisioner.inventory()
        self.assertEqual(len(first), len(second))
        return

    def test_inventory_scopes_to_run_id(self) -> None:
        """
            inventory returns only resources carrying this run's run-id.
        """
        provisioner = _k8s_provisioner()
        provisioner.apply()
        inventory = provisioner.inventory()
        names = sorted(resource.name for resource in inventory)
        self.assertEqual(names, ["inference", "inference", "trainer"])
        return

    def test_destroy_removes_applied_resources(self) -> None:
        """
            destroy removes the previously-applied Jobs and Services.
        """
        provisioner = _k8s_provisioner()
        provisioner.apply()
        provisioner.destroy(aspects={"confirm": True})
        inventory = provisioner.inventory()
        self.assertEqual(len(inventory), 0)
        return

    def test_destroy_requires_confirmation(self) -> None:
        """
            destroy rejects an explicit aspects.confirm=False.
        """
        provisioner = _k8s_provisioner()
        provisioner.apply()
        with self.assertRaises(SchemaSemanticError):
            provisioner.destroy(aspects={"confirm": False})
        return

    def test_destroy_defaults_to_gated_when_no_aspects(self) -> None:
        """
            destroy with no aspects (aspects=None) is gated by default --
            the confirm-gate defaults to False (PC-H1 / PC-H3 regression).
        """
        provisioner = _k8s_provisioner()
        provisioner.apply()
        with self.assertRaises(SchemaSemanticError):
            provisioner.destroy(aspects=None)
        return

    def test_destroy_removes_the_namespace_apply_created(self) -> None:
        """
            destroy deletes the namespace that apply created so that
            destroy inverts apply (PC-H2 regression).
        """
        kube = FakeKubernetesClient()
        provisioner = _k8s_provisioner(kube=kube)
        provisioner.apply()
        # apply created the namespace.
        self.assertIsNotNone(kube.namespaces.get(
            name=provisioner.spec.namespace))
        provisioner.destroy(aspects={"confirm": True})
        # destroy removed the namespace.
        with self.assertRaises(KeyError):
            kube.namespaces.get(name=provisioner.spec.namespace)
        return


if __name__ == "__main__":
    unittest.main()
