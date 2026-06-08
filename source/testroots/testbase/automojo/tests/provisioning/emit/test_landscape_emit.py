"""
    .. module:: test_landscape_emit
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for LandscapeEmitter and DeviceAddressBlock.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.aspects.provisioningaspects import (
    ProvisioningAspects
)
from ccai.provisioning.landscape.deviceaddressblock import (
    DeviceAddressBlock
)
from ccai.provisioning.landscape.landscapeemitter import LandscapeEmitter


class _FakeControlPlane:
    def __init__(self, *, devices) -> None:
        self._devices = devices
        self.call_count = 0
        return

    def list_devices(self, *, aspects):
        self.call_count = self.call_count + 1
        rtnval = self._devices
        return rtnval


class _FailingControlPlane:
    def list_devices(self, *, aspects):
        raise RuntimeError("control plane offline")


class DeviceAddressBlockTests(unittest.TestCase):

    def test_omits_public_when_absent(self) -> None:
        block = DeviceAddressBlock(private="10.0.0.5")
        emitted = block.to_emitted_dict()
        self.assertNotIn("public", emitted)
        self.assertIn("private", emitted)
        return

    def test_includes_overlay_when_present(self) -> None:
        block = DeviceAddressBlock(public="1.2.3.4", private="10.0.0.5",
                                   overlay={"provider": "tailscale",
                                            "address": "100.64.0.1",
                                            "magic_dns": "h.ts.net"})
        emitted = block.to_emitted_dict()
        self.assertEqual(emitted["overlay"]["provider"], "tailscale")
        return


class LandscapeEmitterTests(unittest.TestCase):

    def _spec(self):
        rtnval = {
            "apod": {"name": "lab"},
            "venues": [{"name": "aws-east", "kind": "aws"}],
            "instances": [{"name": "web-01"}],
            "groups": [{"name": "web", "members": ["web-01"]}],
        }
        return rtnval

    def test_emit_simple_instance(self) -> None:
        spec = self._spec()
        inventory = {"aws-east": [
            ProvisionedResource(kind="instance", name="web-01",
                                venue_id="i-1",
                                attributes={"public_ip": "1.2.3.4",
                                            "private_ip": "10.0.0.5"},
                                tags={"role": "web"})
        ]}
        emitter = LandscapeEmitter(spec=spec, inventory=inventory)
        doc = emitter.emit(aspects=ProvisioningAspects())
        self.assertEqual(doc["apod"]["name"], "lab")
        device = doc["apod"]["devices"][0]
        self.assertEqual(device["addresses"]["public"], "1.2.3.4")
        self.assertEqual(device["group"], "web")
        return

    def test_emit_omits_public_when_no_public_ip(self) -> None:
        spec = self._spec()
        inventory = {"aws-east": [
            ProvisionedResource(kind="instance", name="web-01",
                                venue_id="i-1",
                                attributes={"private_ip": "10.0.0.5"})
        ]}
        emitter = LandscapeEmitter(spec=spec, inventory=inventory)
        doc = emitter.emit(aspects=ProvisioningAspects())
        device = doc["apod"]["devices"][0]
        self.assertNotIn("public", device["addresses"])
        return

    def test_emit_empty_inventory_produces_valid_file(self) -> None:
        spec = {"apod": {"name": "empty"}, "venues": []}
        emitter = LandscapeEmitter(spec=spec, inventory={})
        doc = emitter.emit(aspects=ProvisioningAspects())
        self.assertEqual(doc["apod"]["devices"], [])
        return

    def test_emit_includes_overlay_for_vpn_join(self) -> None:
        spec = {
            "apod": {"name": "lab"},
            "venues": [],
            "instances": [{"name": "web-01",
                           "vpn_join": {"provider": "tailscale"}}],
            "vpn_providers": [{"name": "lab-tailnet", "kind": "tailscale"}],
        }
        inventory = {"aws-east": [
            ProvisionedResource(kind="instance", name="web-01",
                                venue_id="i-1",
                                attributes={"public_ip": "1.2.3.4"})
        ]}
        cp = _FakeControlPlane(devices=[
            {"hostname": "web-01", "address": "100.64.0.7",
             "magic_dns": "web-01.ts.net"},
        ])
        emitter = LandscapeEmitter(spec=spec, inventory=inventory,
                                   control_planes={"tailscale": cp})
        doc = emitter.emit(aspects=ProvisioningAspects())
        device = doc["apod"]["devices"][0]
        self.assertEqual(device["addresses"]["overlay"]["address"],
                         "100.64.0.7")
        self.assertIn("vpn", doc)
        return

    def test_emit_handles_overlay_query_failure(self) -> None:
        spec = {
            "apod": {"name": "lab"},
            "venues": [],
            "instances": [{"name": "web-01",
                           "vpn_join": {"provider": "tailscale"}}],
        }
        inventory = {"aws-east": [
            ProvisionedResource(kind="instance", name="web-01",
                                venue_id="i-1",
                                attributes={"public_ip": "1.2.3.4"})
        ]}
        emitter = LandscapeEmitter(spec=spec, inventory=inventory,
                                   control_planes={"tailscale":
                                                   _FailingControlPlane()})
        doc = emitter.emit(aspects=ProvisioningAspects())
        # Device entry still emitted; overlay key absent.
        device = doc["apod"]["devices"][0]
        self.assertNotIn("overlay", device["addresses"])
        return

    def test_landscape_emit_includes_policy(self) -> None:
        spec = {
            "apod": {"name": "lab"},
            "venues": [],
            "instances": [
                {"name": "spot-01", "preemption_policy": "REACQUIRE"},
                {"name": "fixed-01"},
            ],
        }
        inventory = {"aws-east": [
            ProvisionedResource(kind="instance", name="spot-01",
                                venue_id="i-1",
                                attributes={"public_ip": "1.2.3.4"},
                                preemption_policy="REACQUIRE"),
            ProvisionedResource(kind="instance", name="fixed-01",
                                venue_id="i-2",
                                attributes={"public_ip": "1.2.3.5"}),
        ]}
        emitter = LandscapeEmitter(spec=spec, inventory=inventory)
        doc = emitter.emit(aspects=ProvisioningAspects())
        by_name = {d["name"]: d for d in doc["apod"]["devices"]}
        # Every emitted device entry carries a preemption_policy.
        self.assertIn("preemption_policy", by_name["spot-01"])
        self.assertIn("preemption_policy", by_name["fixed-01"])
        # The policy threaded from the ProvisionedResource is honoured.
        self.assertEqual(by_name["spot-01"]["preemption_policy"], "REACQUIRE")
        # An instance without an explicit policy falls back to fail-loud.
        self.assertEqual(by_name["fixed-01"]["preemption_policy"], "FAIL")
        return

    def test_emit_caches_list_devices_per_provider(self) -> None:
        spec = {
            "apod": {"name": "lab"},
            "venues": [],
            "instances": [
                {"name": "web-01",
                 "vpn_join": {"provider": "tailscale"}},
                {"name": "web-02",
                 "vpn_join": {"provider": "tailscale"}},
            ],
        }
        inventory = {"aws-east": [
            ProvisionedResource(kind="instance", name="web-01",
                                venue_id="i-1", attributes={}),
            ProvisionedResource(kind="instance", name="web-02",
                                venue_id="i-2", attributes={}),
        ]}
        cp = _FakeControlPlane(devices=[
            {"hostname": "web-01", "address": "100.64.0.7",
             "magic_dns": "web-01.ts.net"},
            {"hostname": "web-02", "address": "100.64.0.8",
             "magic_dns": "web-02.ts.net"},
        ])
        emitter = LandscapeEmitter(spec=spec, inventory=inventory,
                                   control_planes={"tailscale": cp})
        emitter.emit(aspects=ProvisioningAspects())
        self.assertEqual(cp.call_count, 1)
        return


if __name__ == "__main__":
    unittest.main()
