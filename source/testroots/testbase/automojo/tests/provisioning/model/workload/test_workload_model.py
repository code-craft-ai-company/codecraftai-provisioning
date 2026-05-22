"""
    .. module:: test_workload_model
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for WorkloadVenue + WorkloadCluster + WorkloadJob/Service.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import unittest

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.workload.workloadvenue import WorkloadVenue
from automojo.provisioning.model.workload.workloadvenuekind import (
    WorkloadVenueKind
)
from automojo.provisioning.model.workload.nodepoolspec import NodePoolSpec
from automojo.provisioning.model.workload.autoscalingspec import AutoscalingSpec
from automojo.provisioning.model.workload.workloadcluster import WorkloadCluster
from automojo.provisioning.model.workload.workloadjob import WorkloadJob
from automojo.provisioning.model.workload.workloadservice import WorkloadService
from automojo.provisioning.model.workload.workloadprovisioner import (
    WorkloadProvisioner
)


class WorkloadVenueTests(unittest.TestCase):

    def test_roundtrip(self) -> None:
        v = WorkloadVenue(name="prod-k8s", kind=WorkloadVenueKind.KUBERNETES,
                          credential_ref="kc", endpoint="https://k8s.example")
        rebuilt = WorkloadVenue.from_dict(v.to_dict())
        self.assertEqual(v, rebuilt)
        return

    def test_rejects_unknown_kind(self) -> None:
        with self.assertRaises(SchemaValidationError):
            WorkloadVenue(name="x", kind="messos", credential_ref="kc")
        return

    def test_accepts_container_kind(self) -> None:
        venue_from_enum = WorkloadVenue(name="runpod-venue",
                                        kind=WorkloadVenueKind.CONTAINER,
                                        credential_ref="kc")
        self.assertEqual(venue_from_enum.kind, "container")

        venue_from_str = WorkloadVenue(name="runpod-venue", kind="container",
                                       credential_ref="kc")
        self.assertEqual(venue_from_str.kind, "container")
        return


class WorkloadClusterTests(unittest.TestCase):

    def test_roundtrip(self) -> None:
        pool = NodePoolSpec(name="default", count=3, size="m5.large")
        auto = AutoscalingSpec(min_nodes=1, max_nodes=10,
                               target_utilisation=0.75)
        cluster = WorkloadCluster(name="cluster-a",
                                  node_pools=[pool],
                                  autoscaling=auto,
                                  networking={"cni": "cilium"})
        rebuilt = WorkloadCluster.from_dict(cluster.to_dict())
        self.assertEqual(cluster.name, rebuilt.name)
        return


class WorkloadJobServiceTests(unittest.TestCase):

    def test_job_rejects_bad_restart_policy(self) -> None:
        with self.assertRaises(SchemaValidationError):
            WorkloadJob(name="j", image="busybox", restart_policy="Always")
        return

    def test_service_rejects_bad_exposure(self) -> None:
        with self.assertRaises(SchemaValidationError):
            WorkloadService(name="s", image="nginx", exposure="Hostnet")
        return

    def test_job_roundtrip(self) -> None:
        job = WorkloadJob(name="j", image="busybox",
                          command=["echo", "hi"], replicas=2,
                          restart_policy="OnFailure")
        rebuilt = WorkloadJob.from_dict(job.to_dict())
        self.assertEqual(job, rebuilt)
        return


class WorkloadProvisionerTests(unittest.TestCase):

    def test_provisioner_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            WorkloadProvisioner(venue=WorkloadVenue(
                name="x", kind=WorkloadVenueKind.KUBERNETES,
                credential_ref="kc"
            ))
        return

    def test_subclass_nie_signature(self) -> None:

        class StubProvisioner(WorkloadProvisioner):
            def validate(self, *, aspects):
                raise NotImplementedError("stub validate")

            def plan(self, *, aspects):
                raise NotImplementedError("stub plan")

            def apply(self, *, aspects):
                raise NotImplementedError("stub apply")

            def destroy(self, *, aspects):
                raise NotImplementedError("stub destroy")

            def inventory(self, *, aspects):
                raise NotImplementedError("stub inventory")

        venue = WorkloadVenue(name="x",
                              kind=WorkloadVenueKind.KUBERNETES,
                              credential_ref="kc")
        prov = StubProvisioner(venue=venue)
        with self.assertRaises(NotImplementedError):
            prov.apply(aspects=None)
        self.assertIs(prov.venue, venue)
        return


if __name__ == "__main__":
    unittest.main()
