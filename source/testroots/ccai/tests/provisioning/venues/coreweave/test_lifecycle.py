"""
    .. module:: test_lifecycle
        :platform: Darwin, Linux, Unix, Windows
        :synopsis: Validate / plan / apply / destroy / inventory tests for
                   :class:`CoreweaveWorkloadProvisioner`.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


from ccai import testbase


from ccai.provisioning.model.cloud.plannedactionintent import (
    PlannedActionIntent
)

from ccai.provisioning.venues.coreweave.cwerrors import (
    ConfirmationRequiredError, CwValidationError
)

from ccai.interfaces.vpnjoinspec import VPNJoinSpec

from ccai.tests.provisioning.venues.coreweave.testsupport import (
    FakeNodePool, MockCoreweaveClient, MockKubernetesClient,
    MockVpnControlPlane, make_gpu_job, make_provisioner, make_service,
    make_slurm_venue, make_spec
)


# ----------------------------------------------------------------------
# validate
# ----------------------------------------------------------------------

def test_validate_happy_path():
    """
        ``validate`` succeeds for a GPU job that resolves to a node pool.
    """
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]))
    result = provisioner.validate()
    assert result.ok is True
    return


def test_validate_rejects_unresolvable_accelerator():
    """
        ``validate`` rejects a job whose GPU model has no node pool.
    """
    cw = MockCoreweaveClient(pools=[FakeNodePool(name="a100-pool",
                                                 gpu_model="A100_SXM")])
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]),
                                   coreweave_client=cw)
    with testbase.raises(CwValidationError):
        provisioner.validate()
    return


def test_validate_rejects_slurm_without_sunk():
    """
        A SLURM venue without ``sub_mode='sunk'`` is rejected loudly.
    """
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]),
                                   venue=make_slurm_venue())
    with testbase.raises(CwValidationError):
        provisioner.validate()
    return


def test_validate_accepts_slurm_with_sunk():
    """
        A SLURM venue with ``sub_mode='sunk'`` is accepted.
    """
    spec = make_spec(jobs=[make_gpu_job()], sub_mode="sunk")
    provisioner = make_provisioner(spec=spec, venue=make_slurm_venue())
    result = provisioner.validate()
    assert result.ok is True
    return


# ----------------------------------------------------------------------
# plan
# ----------------------------------------------------------------------

def test_plan_fresh_emits_creates():
    """
        ``plan`` against an empty cluster emits CREATE intents.
    """
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]))
    plan = provisioner.plan()

    intents = [action.intent for action in plan.actions]
    assert PlannedActionIntent.CREATE.value in intents
    return


def test_plan_after_apply_emits_only_skips():
    """
        Re-planning an already-applied spec emits only SKIP actions.
    """
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]))
    provisioner.apply()
    plan = provisioner.plan()

    for action in plan.actions:
        assert action.intent == PlannedActionIntent.SKIP.value
    return


# ----------------------------------------------------------------------
# apply
# ----------------------------------------------------------------------

def test_apply_workload_job_creates_k8s_job():
    """
        Applying a :class:`WorkloadJob` realises a Kubernetes Job.
    """
    kube = MockKubernetesClient()
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]),
                                   kubernetes_client=kube)
    result = provisioner.apply()

    kinds = [resource.kind for resource in result.created]
    assert "Job" in kinds
    assert "Namespace" in kinds
    job_record = kube.jobs.get(name="trainer")
    assert job_record.name == "trainer"
    return


def test_apply_workload_service_creates_deployment_and_service():
    """
        Applying a :class:`WorkloadService` realises a Deployment + Service.
    """
    provisioner = make_provisioner(
        spec=make_spec(services=[make_service()]))
    result = provisioner.apply()

    kinds = [resource.kind for resource in result.created]
    assert "Deployment" in kinds
    assert "Service" in kinds
    return


def test_apply_is_idempotent():
    """
        Applying the same spec twice yields the same realised resource set.
    """
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]))
    first = provisioner.apply()
    second = provisioner.apply()

    first_names = sorted(r.name for r in first.created)
    second_names = sorted(r.name for r in second.created)
    assert first_names == second_names
    return


def test_apply_sunk_sub_mode_renders_bundle():
    """
        ``sub_mode='sunk'`` apply realises the Sunk manifest bundle.
    """
    spec = make_spec(jobs=[make_gpu_job()], sub_mode="sunk")
    provisioner = make_provisioner(spec=spec, venue=make_slurm_venue())
    result = provisioner.apply()

    names = [r.name for r in result.created]
    assert "sunk-slurmctld" in names
    assert "sunk-slurmd" in names
    assert "sunk-mysql" in names
    return


# ----------------------------------------------------------------------
# destroy
# ----------------------------------------------------------------------

class _Confirm:
    """
        A minimal aspects stand-in carrying ``confirm=True``.
    """
    confirm = True


def test_destroy_removes_workloads():
    """
        ``destroy`` removes the realised Job from the cluster.
    """
    kube = MockKubernetesClient()
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]),
                                   kubernetes_client=kube)
    provisioner.apply()
    provisioner.destroy(aspects=_Confirm())

    with testbase.raises(KeyError):
        kube.jobs.get(name="trainer")
    return


def test_destroy_without_confirm_raises():
    """
        ``destroy`` with ``aspects.confirm=False`` raises.
    """
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]))
    provisioner.apply()

    class _NoConfirm:
        confirm = False

    with testbase.raises(ConfirmationRequiredError):
        provisioner.destroy(aspects=_NoConfirm())
    return


def test_destroy_defaults_to_confirm_false():
    """
        ``destroy`` with no aspects defaults to ``confirm=False`` and
        refuses to tear down — destruction is opt-in.
    """
    provisioner = make_provisioner(spec=make_spec(jobs=[make_gpu_job()]))
    provisioner.apply()

    with testbase.raises(ConfirmationRequiredError):
        provisioner.destroy()
    return


def test_destroy_deregisters_recorded_vpn_devices():
    """
        Regression for PV-H5: ``apply`` records every VPN-joined workload's
        device id and ``destroy`` de-registers each recorded id — the
        cleanup path is no longer dead code.
    """
    vpn_join = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="ts-cred",
                           hostname_template="trainer")
    spec = make_spec(jobs=[make_gpu_job()],
                     vpn_joins={"trainer": vpn_join})
    vpn = MockVpnControlPlane()
    provisioner = make_provisioner(spec=spec, vpn_control_plane=vpn)
    provisioner.apply()

    recorded = provisioner.registered_vpn_devices
    assert len(recorded) == 1

    # The workload joined the tailnet under its workload-name hostname;
    # register the matching control-plane device so destroy resolves the real
    # device id durably rather than from apply-process state.
    vpn.register_device(device_id="dev-real-1", hostname=recorded[0])

    provisioner.destroy(aspects=_Confirm())
    assert vpn.deleted_devices == ["dev-real-1"]
    return


class _SpecStub:
    """
        A minimal typed-spec stand-in carrying ``name`` and ``labels``.
    """

    def __init__(self, *, name: str) -> None:
        self.name = name
        self.labels = {}
        return


def test_destroy_sunk_tears_down_the_bundle():
    """
        Regression for PV-H6: a ``sub_mode='sunk'`` destroy tears down every
        manifest in the rendered Sunk bundle through the Kubernetes
        primitives, leaving the cluster clean.
    """
    kube = MockKubernetesClient()
    spec = make_spec(jobs=[make_gpu_job()], sub_mode="sunk")
    provisioner = make_provisioner(spec=spec, venue=make_slurm_venue(),
                                   kubernetes_client=kube)
    provisioner.apply()

    # Re-render the bundle and seed the cluster store so destroy has
    # something concrete to tear down.
    from ccai.provisioning.venues.coreweave.cwsunkrenderer import (
        CwSunkRenderer
    )
    bundle = CwSunkRenderer().render(namespace="default",
                                     run_id=spec.run_id,
                                     workload_names=["trainer"])
    seeded = []
    for manifest in bundle:
        kind = manifest["kind"]
        name = manifest["metadata"]["name"]
        primitive = {"StatefulSet": kube.statefulsets,
                     "Deployment": kube.deployments}.get(kind, None)
        if primitive is not None:
            primitive.apply(spec=_SpecStub(name=name), namespace="default")
            seeded.append((primitive, name))
    assert len(seeded) > 0

    provisioner.destroy(aspects=_Confirm())

    for primitive, name in seeded:
        with testbase.raises(KeyError):
            primitive.get(name=name, namespace="default")
    return


# ----------------------------------------------------------------------
# inventory
# ----------------------------------------------------------------------

def test_inventory_lists_run_labelled_resources():
    """
        ``inventory`` enumerates resources carrying the run-id label.
    """
    provisioner = make_provisioner(
        spec=make_spec(jobs=[make_gpu_job()], services=[make_service()]))
    provisioner.apply()
    inventory = provisioner.inventory()

    kinds = sorted(set(r.kind for r in inventory))
    assert "Job" in kinds
    assert "Deployment" in kinds
    assert "Service" in kinds
    return
