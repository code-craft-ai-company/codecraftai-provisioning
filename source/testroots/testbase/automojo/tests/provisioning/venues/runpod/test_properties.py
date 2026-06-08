"""
    .. module:: test_properties
        :platform: Darwin, Linux, Unix, Windows
        :synopsis: Property-based tests (hypothesis) for the RunPod workload
                   provisioner — apply idempotence, destroy as the inverse of
                   apply, sidecar-tag round-trip identity, deterministic
                   userspace-Tailscale start-script hashing, and the secure
                   vs community tier branch.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import tempfile

from hypothesis import given, settings
from hypothesis import strategies as st

from ccai.restclient.runpod.enums.runpodcloudtype import RunpodCloudType
from ccai.provisioning.model.vpn.vpnjoinspec import VPNJoinSpec

from ccai.provisioning.venues.runpod.rpapplystages import RpApplyStages
from ccai.provisioning.venues.runpod.rpcontainerstartrenderer import (
    RpContainerStartRenderer
)
from ccai.provisioning.venues.runpod.rpsidecartag import RpSidecarTag

from ccai.tests.provisioning.venues.runpod.testsupport import (
    MockRunpodClient, make_gpu_job, make_provisioner, make_service, make_spec
)


# ----------------------------------------------------------------------
# apply idempotence
# ----------------------------------------------------------------------

@settings(max_examples=30, deadline=None)
@given(job_count=st.integers(min_value=1, max_value=4),
       service_count=st.integers(min_value=0, max_value=3))
def test_apply_idempotent(job_count, service_count):
    """
        ``apply`` ∘ ``apply`` launches no extra pods — the second apply is a
        no-op SKIP.
    """
    jobs = [make_gpu_job(name="job-{}".format(i)) for i in range(job_count)]
    services = [make_service(name="svc-{}".format(i))
                for i in range(service_count)]
    spec = make_spec(jobs=jobs, services=services)
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)

    provisioner.apply()
    launches_after_first = client.launch_count
    provisioner.apply()
    assert client.launch_count == launches_after_first
    assert launches_after_first == job_count + service_count


# ----------------------------------------------------------------------
# destroy is the inverse of apply
# ----------------------------------------------------------------------

@settings(max_examples=30, deadline=None)
@given(job_count=st.integers(min_value=1, max_value=4),
       volume_count=st.integers(min_value=0, max_value=3))
def test_destroy_is_inverse_of_apply(job_count, volume_count):
    """
        After ``apply`` then ``destroy`` the account holds none of the run's
        pods or volumes.
    """
    jobs = [make_gpu_job(name="job-{}".format(i)) for i in range(job_count)]
    volumes = [{"name": "vol-{}".format(i), "size_gb": 50}
               for i in range(volume_count)]
    spec = make_spec(jobs=jobs, network_volumes=volumes)
    client = MockRunpodClient()
    provisioner = make_provisioner(spec=spec, runpod_client=client)

    class _Confirm:
        confirm = True

    provisioner.apply()
    provisioner.destroy(aspects=_Confirm())

    assert len(client.list_pods()) == 0
    assert len(client.list_network_volumes()) == 0


# ----------------------------------------------------------------------
# sidecar-tag round-trip identity
# ----------------------------------------------------------------------

@settings(max_examples=40, deadline=None)
@given(tags=st.dictionaries(keys=st.text(min_size=1, max_size=8),
                            values=st.text(min_size=0, max_size=12),
                            min_size=0, max_size=6))
def test_sidecar_tag_round_trip_identity(tags):
    """
        Writing a neutral tag dict and reading it back recovers the identity.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        sidecar = RpSidecarTag(runid="run-xyz", output_root=tmp_dir)
        sidecar.write(neutral_tags=tags, pod_id="pod-1")
        recovered = sidecar.read(pod_id="pod-1")
    assert recovered == tags


# ----------------------------------------------------------------------
# userspace-Tailscale start-script hash determinism
# ----------------------------------------------------------------------

@settings(max_examples=30, deadline=None)
@given(hostname=st.text(alphabet="abcdefghijklmnop-", min_size=1,
                        max_size=16))
def test_userspace_tailscale_start_script_hash_deterministic(hostname):
    """
        For the same inputs the rendered userspace-Tailscale start script is
        byte-for-byte deterministic.
    """
    renderer = RpContainerStartRenderer()
    vpn_join = VPNJoinSpec(provider="tailscale",
                           control_plane_credential="ts-cred",
                           hostname_template="tmpl")
    job = make_gpu_job()

    first = renderer.render(workload=job, vpn_join=vpn_join,
                            authkey="tskey-1", hostname=hostname)
    second = renderer.render(workload=job, vpn_join=vpn_join,
                             authkey="tskey-1", hostname=hostname)
    assert first == second
    assert renderer.content_hash(script=first) == \
        renderer.content_hash(script=second)
    assert "--tun=userspace-networking" in first


# ----------------------------------------------------------------------
# secure vs community tier branch
# ----------------------------------------------------------------------

@settings(max_examples=20, deadline=None)
@given(tier=st.sampled_from(("secure", "community", None)))
def test_secure_vs_community_branch(tier):
    """
        The apply stage maps the spec tier onto the matching RunPod cloud
        type; an unset tier defaults to Secure.
    """
    spec = make_spec(jobs=[make_gpu_job()], tier=tier)
    stages = RpApplyStages()
    cloud_type = stages._cloud_type(spec=spec)
    if tier == "community":
        assert cloud_type == RunpodCloudType.COMMUNITY
    else:
        assert cloud_type == RunpodCloudType.SECURE
