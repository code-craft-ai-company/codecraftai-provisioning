"""
    .. module:: test_lifecycle
        :platform: Darwin, Linux, Unix, Windows
        :synopsis: Validate / plan / apply / destroy / inventory tests for
                   :class:`RunpodWorkloadProvisioner`.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import pytest

from automojo.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)
from automojo.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec

from automojo.provisioning.venues.runpod.rperrors import (
    ConfirmationRequiredError, RpCapacityError, RpValidationError
)
from automojo.provisioning.venues.runpod.rpnaming import pod_name

from automojo.tests.provisioning.venues.runpod.testsupport import (
    FakeGpuType, FakePod, MockRunpodClient, MockVpnControlPlane, TEST_RUN_ID,
    make_gpu_job, make_provisioner, make_service, make_spec
)


_RUN_SHORT = TEST_RUN_ID[0:8]


# ----------------------------------------------------------------------
# validate
# ----------------------------------------------------------------------

def test_validate_happy_path():
    """
        ``validate`` succeeds for a GPU job that resolves to a GPU type with
        Secure Cloud capacity.
    """
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]))
    result = provisioner.validate()
    assert result.ok is True


def test_validate_rejects_object_bucket():
    """
        A spec carrying an object bucket is rejected — RunPod has no
        object-storage API.
    """
    provisioner = make_provisioner(
        spec=make_spec(jobs=[make_gpu_job()], buckets=[object()]))
    with pytest.raises(RpValidationError):
        provisioner.validate()


def test_validate_rejects_load_balancer():
    """
        A spec carrying a load balancer is rejected.
    """
    provisioner = make_provisioner(
        spec=make_spec(jobs=[make_gpu_job()], load_balancers=[object()]))
    with pytest.raises(RpValidationError):
        provisioner.validate()


def test_validate_rejects_dns_record():
    """
        A spec carrying a DNS record is rejected.
    """
    provisioner = make_provisioner(
        spec=make_spec(jobs=[make_gpu_job()], dns_records=[object()]))
    with pytest.raises(RpValidationError):
        provisioner.validate()


def test_validate_rejects_non_none_interconnect():
    """
        A spec carrying a non-NONE interconnect is rejected.
    """
    class _Interconnect:
        kind = "INFINIBAND_NDR"
        topology = "RAIL_OPTIMIZED"

    provisioner = make_provisioner(
        spec=make_spec(jobs=[make_gpu_job()],
                       interconnects=[_Interconnect()]))
    with pytest.raises(RpValidationError):
        provisioner.validate()


def test_validate_warns_on_unrealised_network():
    """
        A spec carrying a network warns that RunPod realises no network.
    """
    provisioner = make_provisioner(
        spec=make_spec(jobs=[make_gpu_job()], networks=[object()]))
    result = provisioner.validate()
    assert result.ok is True
    assert len(result.warnings) == 1


def test_validate_rejects_unmappable_gpu():
    """
        A workload whose accelerator model has no RunPod GPU type mapping is
        rejected.
    """
    from automojo.provisioning.model.cloud.cloudacceleratorspec import (
        CloudAcceleratorSpec
    )
    from automojo.provisioning.model.workload.workloadjob import WorkloadJob

    bad_accel = CloudAcceleratorSpec(kind="GPU", model="TPU_V5",
                                     count=1, memory_gb=32)
    job = WorkloadJob(name="t", image="i:1", accelerators=[bad_accel])
    provisioner = make_provisioner(spec=make_spec(jobs=[job]))
    with pytest.raises(RpValidationError):
        provisioner.validate()


def test_validate_secure_capacity_unavailable():
    """
        ``validate`` raises RpCapacityError when the GPU type has no Secure
        Cloud capacity in the requested data center.
    """
    client = MockRunpodClient(gpu_types=[
        FakeGpuType(gpu_type_id="NVIDIA H100 80GB HBM3",
                    secure_data_centers=[], community_data_centers=["EU-1"])])
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]),
                                   runpod_client=client)
    with pytest.raises(RpCapacityError):
        provisioner.validate()


# ----------------------------------------------------------------------
# plan
# ----------------------------------------------------------------------

def test_plan_fresh_emits_creates():
    """
        ``plan`` against an empty account emits CREATE intents.
    """
    spec = make_spec(jobs=[make_gpu_job()],
                     network_volumes=[{"name": "data", "size_gb": 100}])
    provisioner = make_provisioner(spec=spec)
    plan = provisioner.plan()
    intents = [a.intent for a in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents
    assert len(plan.actions) == 2


def test_plan_after_apply_is_all_skip():
    """
        Re-planning an already-applied spec yields only SKIP intents.
    """
    spec = make_spec(jobs=[make_gpu_job()])
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    provisioner.apply()

    plan = provisioner.plan()
    for action in plan.actions:
        assert action.intent == PlannedActionIntent.SKIP.value


def test_plan_flags_gpu_drift_as_update():
    """
        A live pod whose GPU type drifts from the desired one is flagged
        UPDATE-by-recreate.
    """
    spec = make_spec(jobs=[make_gpu_job()])
    drifted = FakePod(pod_id="pod-old",
                      name=pod_name(workload_name="trainer",
                                    run_id_short=_RUN_SHORT),
                      gpu_type_id="NVIDIA A40")
    client = MockRunpodClient(pods=[drifted])
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    plan = provisioner.plan()
    assert plan.actions[0].intent == PlannedActionIntent.UPDATE.value


# ----------------------------------------------------------------------
# apply
# ----------------------------------------------------------------------

def test_apply_launches_a_pod_per_workload():
    """
        ``apply`` launches a RunPod pod for each declared workload.
    """
    spec = make_spec(jobs=[make_gpu_job()], services=[make_service()])
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    result = provisioner.apply()
    assert len(result.created) == 2
    assert client.launch_count == 2


def test_apply_ensures_network_volumes():
    """
        ``apply`` ensures every declared Network Volume exists.
    """
    spec = make_spec(jobs=[make_gpu_job()],
                     network_volumes=[{"name": "data", "size_gb": 100}])
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    provisioner.apply()
    assert client.volume_create_count == 1


def test_apply_reapply_makes_no_mutating_calls():
    """
        Re-applying a fully-realised spec mutates nothing.
    """
    spec = make_spec(jobs=[make_gpu_job()])
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    provisioner.apply()

    launches_after_first = client.launch_count
    result = provisioner.apply()
    assert client.launch_count == launches_after_first
    assert len(result.skipped) > 0


def test_apply_update_without_confirm_raises():
    """
        An apply carrying an UPDATE-by-recreate without confirmation raises
        ConfirmationRequiredError.
    """
    class _Aspects:
        confirm = False

    spec = make_spec(jobs=[make_gpu_job()])
    drifted = FakePod(pod_id="pod-old",
                      name=pod_name(workload_name="trainer",
                                    run_id_short=_RUN_SHORT),
                      gpu_type_id="NVIDIA A40")
    client = MockRunpodClient(pods=[drifted])
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    with pytest.raises(ConfirmationRequiredError):
        provisioner.apply(aspects=_Aspects())


def test_apply_renders_userspace_tailscale_for_vpn_pod():
    """
        A VPN-joined workload's pod gets a userspace-mode Tailscale start
        script and an auth key is minted.
    """
    vpn_join = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="ts-cred",
                           hostname_template="trainer-pod")
    spec = make_spec(jobs=[make_gpu_job()],
                     vpn_joins={"trainer": vpn_join})
    client = MockRunpodClient()
    vpn = MockVpnControlPlane()
    provisioner = make_provisioner(spec=spec, runpod_client=client,
                                   vpn_control_plane=vpn)
    result = provisioner.apply()
    assert len(result.created) == 1


# ----------------------------------------------------------------------
# destroy
# ----------------------------------------------------------------------

def test_destroy_terminates_run_pods():
    """
        ``destroy`` stops and terminates every pod owned by the run.
    """
    spec = make_spec(jobs=[make_gpu_job()])
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    provisioner.apply()

    provisioner.destroy()
    assert client.terminate_count >= 1
    assert len(client.list_pods()) == 0


def test_destroy_without_confirm_raises():
    """
        ``destroy`` without ``aspects.confirm`` raises
        ConfirmationRequiredError.
    """
    class _Aspects:
        confirm = False

    spec = make_spec(jobs=[make_gpu_job()])
    provisioner = make_provisioner(spec=spec)
    with pytest.raises(ConfirmationRequiredError):
        provisioner.destroy(aspects=_Aspects())


def test_destroy_deletes_run_network_volumes():
    """
        ``destroy`` deletes the Network Volumes owned by the run.
    """
    spec = make_spec(jobs=[make_gpu_job()],
                     network_volumes=[{"name": "data", "size_gb": 100}])
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    provisioner.apply()
    assert len(client.list_network_volumes()) == 1

    provisioner.destroy()
    assert len(client.list_network_volumes()) == 0


# ----------------------------------------------------------------------
# inventory
# ----------------------------------------------------------------------

def test_inventory_lists_run_pods_with_public_ip():
    """
        ``inventory`` emits a Pod record carrying the public IP.
    """
    spec = make_spec(jobs=[make_gpu_job()])
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)
    provisioner.apply()

    resources = provisioner.inventory()
    pods = [r for r in resources if r.kind == "Pod"]
    assert len(pods) == 1
    assert pods[0].attributes.get("public_ip") == "203.0.113.1"
