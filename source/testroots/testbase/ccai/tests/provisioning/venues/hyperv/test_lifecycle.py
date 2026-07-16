"""
    .. module:: test_lifecycle
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Plan / apply / destroy / inventory tests for the Hyper-V
        venue provisioner.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import pytest

from ccai.provisioning.model.exceptions import SchemaSemanticError

from ccai.provisioning.venues.hyperv.hypervcloudprovisioner import (
    HypervCloudProvisioner
)
from ccai.provisioning.venues.hyperv.hverrors import (
    ConfirmationRequiredError
)

from . import _specfactory


def _provisioner(*, venue, client, host_config, spec, vpn_control_plane=None):
    """
        Build a HypervCloudProvisioner for a lifecycle test.

        :param venue: The CloudVenue.
        :param client: The MockHypervClient.
        :param host_config: The HvHostConfig.
        :param spec: The HypervSpec.
        :param vpn_control_plane: Optional VPN control-plane.

        :returns: A HypervCloudProvisioner.
    """
    rtnval = HypervCloudProvisioner(venue=venue, client=client,
                                    host_config=host_config, spec=spec,
                                    vpn_control_plane=vpn_control_plane)
    return rtnval


def test_plan_all_create_on_empty_host(venue, client, host_config, aspects):
    """
        Against an empty host every planned action is CREATE.
    """
    spec = _specfactory.make_basic_spec(with_volume=True)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    plan = provisioner.plan(aspects=aspects)

    intents = [action.intent for action in plan.actions]
    assert len(intents) == 3
    for intent in intents:
        assert intent == "create"
    return


def test_plan_re_plan_after_apply_is_all_skip(venue, client, host_config,
                                              aspects):
    """
        Re-planning after apply yields only SKIP actions.
    """
    spec = _specfactory.make_basic_spec(with_volume=True)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    provisioner.apply(aspects=aspects)
    plan = provisioner.plan(aspects=aspects)

    intents = [action.intent for action in plan.actions]
    assert len(intents) == 3
    for intent in intents:
        assert intent == "skip"
    return


def test_plan_detects_hardware_drift(venue, client, host_config, aspects):
    """
        A VM whose processor count drifts yields an UPDATE action.
    """
    spec = _specfactory.make_basic_spec()
    client.seed_vm(name="vm-app", processor_count=99,
                   memory_startup_bytes=8589934592)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    plan = provisioner.plan(aspects=aspects)

    instance_actions = [a for a in plan.actions
                        if a.resource_kind == "instance"]
    assert len(instance_actions) == 1
    assert instance_actions[0].intent == "update"
    return


def test_apply_creates_switch_vm_and_starts(venue, client, host_config,
                                            aspects):
    """
        apply ensures the switch, creates the VM and starts it.
    """
    spec = _specfactory.make_basic_spec()
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    result = provisioner.apply(aspects=aspects)

    assert len(result.created) == 2
    assert client.calls["new_switch"] == 1
    assert client.calls["new_vm"] == 1
    assert client.calls["start_vm"] == 1
    assert client.calls["set_vm_processor"] == 1
    assert client.calls["set_vm_memory"] == 1
    return


def test_apply_realises_hardware_drift_in_place(venue, client, host_config,
                                                confirm_aspects):
    """
        apply over a host carrying a processor/memory-drifted VM realises
        the resize in place via Set-VMProcessor / Set-VMMemory; the
        result carries the VM in ``updated``.
    """
    spec = _specfactory.make_basic_spec()
    client.seed_vm(name="vm-app", processor_count=99,
                   memory_startup_bytes=2147483648)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    result = provisioner.apply(aspects=confirm_aspects)

    assert client.calls["set_vm_processor"] == 1
    assert client.calls["set_vm_memory"] == 1
    assert client.calls["new_vm"] == 0
    updated_names = [r.name for r in result.updated]
    assert updated_names == ["vm-app"]
    assert result.updated[0].attributes["processor_count"] == 4

    live = client.vms_state["vm-app"]
    assert live.processor_count == 4
    assert live.memory_startup_bytes == 8589934592
    return


def test_replan_after_resize_emits_skip(venue, client, host_config,
                                        confirm_aspects):
    """
        A second apply after an in-place resize emits SKIP for the VM —
        idempotence is preserved.
    """
    spec = _specfactory.make_basic_spec()
    client.seed_vm(name="vm-app", processor_count=99,
                   memory_startup_bytes=2147483648)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    provisioner.apply(aspects=confirm_aspects)

    plan = provisioner.plan(aspects=confirm_aspects)
    instance_actions = [a for a in plan.actions
                        if a.resource_kind == "instance"]
    assert len(instance_actions) == 1
    assert instance_actions[0].intent == "skip"

    second = provisioner.apply(aspects=confirm_aspects)
    assert "vm-app" in second.skipped
    assert len(second.updated) == 0
    return


def test_unconfirmed_resize_requires_confirm(venue, client, host_config,
                                             aspects):
    """
        An in-place VM resize without aspects.confirm raises
        ConfirmationRequiredError — Set-VMProcessor / Set-VMMemory need
        the VM stopped, so the resize is disruptive.
    """
    spec = _specfactory.make_basic_spec()
    client.seed_vm(name="vm-app", processor_count=99,
                   memory_startup_bytes=2147483648)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    with pytest.raises(ConfirmationRequiredError):
        provisioner.apply(aspects=aspects)

    assert client.calls["set_vm_processor"] == 0
    return


def test_apply_encodes_run_id_into_notes(venue, client, host_config,
                                         aspects):
    """
        apply writes the ccai run-id envelope into VM.Notes.
    """
    spec = _specfactory.make_basic_spec()
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    provisioner.apply(aspects=aspects)

    vm_record = client.vms_state["vm-app"]
    assert "hvrun01" in vm_record.notes
    assert "ccai" in vm_record.notes
    return


def test_apply_with_volume_attaches_disk(venue, client, host_config,
                                         aspects):
    """
        apply creates a data VHDX and attaches it to its instance.
    """
    spec = _specfactory.make_basic_spec(with_volume=True)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    provisioner.apply(aspects=aspects)

    assert client.calls["add_vm_hard_disk"] == 1
    return


def test_apply_with_vpn_join_mounts_iso(venue, client, host_config,
                                        aspects, vpn_control_plane):
    """
        A VPN-joined instance gets a config-drive ISO mounted.
    """
    spec = _specfactory.make_basic_spec(with_vpn=True)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec,
                               vpn_control_plane=vpn_control_plane)

    provisioner.apply(aspects=aspects)

    assert client.calls["add_vm_dvd_drive"] == 1
    assert len(provisioner.last_vpn_records) == 1
    return


def test_inventory_lists_run_owned_vms(venue, client, host_config, aspects):
    """
        inventory enumerates run-id-owned VMs after apply.
    """
    spec = _specfactory.make_basic_spec()
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    provisioner.apply(aspects=aspects)
    items = provisioner.inventory(aspects=aspects)

    assert len(items) == 1
    assert items[0].name == "vm-app"
    assert items[0].kind == "instance"
    return


def test_inventory_ignores_foreign_vms(venue, client, host_config, aspects):
    """
        inventory does not report VMs that are not run-owned.
    """
    spec = _specfactory.make_basic_spec()
    client.seed_vm(name="foreign-vm", notes="not-ccai")
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)

    provisioner.apply(aspects=aspects)
    items = provisioner.inventory(aspects=aspects)

    names = [item.name for item in items]
    assert "foreign-vm" not in names
    assert "vm-app" in names
    return


def test_destroy_requires_confirm(venue, client, host_config, aspects):
    """
        destroy without confirm raises before any teardown.
    """
    spec = _specfactory.make_basic_spec()
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)
    provisioner.apply(aspects=aspects)

    with pytest.raises(SchemaSemanticError):
        provisioner.destroy(aspects=aspects)

    assert "vm-app" in client.vms_state
    return


def test_destroy_removes_run_owned_resources(venue, client, host_config,
                                             aspects, confirm_aspects):
    """
        destroy with confirm removes the VM, its VHDX and the switch.
    """
    spec = _specfactory.make_basic_spec()
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)
    provisioner.apply(aspects=aspects)

    provisioner.destroy(aspects=confirm_aspects)

    assert "vm-app" not in client.vms_state
    assert len(client.switches_state) == 0
    assert client.calls["stop_vm"] >= 1
    assert client.calls["remove_vm"] == 1
    return


def test_destroy_invokes_vpn_cleanup(venue, client, host_config, aspects,
                                     confirm_aspects, vpn_control_plane):
    """
        destroy de-registers VPN devices recorded during apply.
    """
    spec = _specfactory.make_basic_spec(with_vpn=True)
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec,
                               vpn_control_plane=vpn_control_plane)
    provisioner.apply(aspects=aspects)

    # The VPN-joined instance joins the tailnet under its vpn_join hostname;
    # register the matching control-plane device so destroy resolves it
    # durably (device ids are no longer threaded through apply-process state).
    vpn_instances = [inst for inst in spec.instances
                     if inst.vpn_join is not None]
    assert len(vpn_instances) > 0
    hostname = vpn_instances[0].vpn_join.hostname_template
    vpn_control_plane.register_device(device_id="dev-vm-app",
                                      hostname=hostname)

    provisioner.destroy(aspects=confirm_aspects)

    assert "dev-vm-app" in vpn_control_plane.deleted_devices
    return


def test_persist_inventory_writes_json(tmp_path, venue, client,
                                       host_config, aspects):
    """
        persist_inventory writes the hyperv-inventory.json file.
    """
    spec = _specfactory.make_basic_spec()
    provisioner = _provisioner(venue=venue, client=client,
                               host_config=host_config, spec=spec)
    provisioner.apply(aspects=aspects)

    out_path = provisioner.persist_inventory(aspects=aspects,
                                             output_root=str(tmp_path))

    assert out_path.endswith("hyperv-inventory.json")
    return
