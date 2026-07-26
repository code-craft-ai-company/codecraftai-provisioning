"""
    .. module:: test_accelerator_and_interconnect
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit tests for accelerator, interconnect, and shared-fs classes.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest
import warnings

from ccai.interfaces.schemavalidationerror import SchemaValidationError
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.interfaces.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from ccai.provisioning.model.cloud.cloudinterconnect import CloudInterconnect
from ccai.interfaces.sharedfsmountspec import SharedFsMountSpec
from ccai.interfaces.cloudsharedfilesystem import (
    CloudSharedFilesystem
)
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.interfaces.schemavalidators import resolve_mount_targets
from ccai.provisioning.model.cloud.venuecapability import (
    VenueCapability, venue_capability
)
from ccai.interfaces.vpnjoinspec import VPNJoinSpec


def _basic_image() -> CloudImage:
    rtnval = CloudImage(family="ubuntu", version="24.04", architecture="x86_64")
    return rtnval


class AcceleratorSpecTests(unittest.TestCase):

    def test_roundtrip(self) -> None:
        spec = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                    interconnect="NVSWITCH", memory_gb=80)
        rebuilt = CloudAcceleratorSpec.from_dict(spec.to_dict())
        self.assertEqual(spec, rebuilt)
        return

    def test_rejects_bad_kind(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudAcceleratorSpec(kind="FPGA", model="x", count=1,
                                 interconnect="NONE", memory_gb=1)
        return

    def test_rejects_zero_count(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=0,
                                 interconnect="NVSWITCH", memory_gb=80)
        return


class InterconnectTests(unittest.TestCase):

    def test_roundtrip(self) -> None:
        ic = CloudInterconnect(kind="INFINIBAND_NDR", bandwidth_gbps=400,
                               topology="FAT_TREE")
        rebuilt = CloudInterconnect.from_dict(ic.to_dict())
        self.assertEqual(ic, rebuilt)
        return

    def test_rejects_bad_topology(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudInterconnect(kind="ETHERNET", bandwidth_gbps=100,
                              topology="MESH")
        return


class SharedFsTests(unittest.TestCase):

    def test_mount_spec_rejects_relative_path(self) -> None:
        with self.assertRaises(SchemaValidationError):
            SharedFsMountSpec(filesystem_name="fs",
                              target_instance="inst",
                              mount_path="relative/path")
        return

    def test_filesystem_requires_size_or_existing_id(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudSharedFilesystem(name="fs", kind="LUSTRE")
        return

    def test_filesystem_attach_only_roundtrip(self) -> None:
        fs = CloudSharedFilesystem(name="fs", kind="EFS",
                                   existing_id="fs-abc123")
        rebuilt = CloudSharedFilesystem.from_dict(fs.to_dict())
        self.assertEqual(fs, rebuilt)
        return


class VenueCapabilityTests(unittest.TestCase):

    def test_stub_capability_rejects_every_interconnect(self) -> None:
        cap = venue_capability(venue="stub-venue")
        self.assertIsInstance(cap, VenueCapability)
        self.assertFalse(cap.supports_interconnect(kind="INFINIBAND_NDR"))
        self.assertFalse(cap.supports_interconnect(kind="EFA"))
        return

    def test_published_capability_reports_support(self) -> None:
        cap = VenueCapability(venue="azure",
                              interconnect_kinds=["INFINIBAND_NDR"],
                              shared_fs_attach_kinds=["LUSTRE"])
        self.assertTrue(cap.supports_interconnect(kind="INFINIBAND_NDR"))
        self.assertFalse(cap.supports_interconnect(kind="EFA"))
        self.assertEqual(cap.shared_fs_attach_kinds, ["LUSTRE"])
        return


class CloudInstanceAcceleratorTests(unittest.TestCase):

    def test_cloudinstance_with_accelerators_roundtrip(self) -> None:
        accel = CloudAcceleratorSpec(kind="GPU", model="H100_SXM", count=8,
                                     interconnect="NVSWITCH", memory_gb=80)
        ic = CloudInterconnect(kind="INFINIBAND_NDR", bandwidth_gbps=400,
                               topology="FAT_TREE")
        mount = SharedFsMountSpec(filesystem_name="weka-fs",
                                  target_instance="gpu-node",
                                  mount_path="/mnt/weka")
        instance = CloudInstance(name="gpu-node", profile_ref="gpu-profile",
                                 image=_basic_image(), size="8xh100",
                                 subnet="gpu-subnet",
                                 accelerators=[accel], interconnect=ic,
                                 placement_group="cluster-a",
                                 shared_fs_mounts=[mount])
        rebuilt = CloudInstance.from_dict(instance.to_dict())
        self.assertEqual(instance, rebuilt)
        return

    def test_interconnect_without_placement_group_warns(self) -> None:
        ic = CloudInterconnect(kind="ETHERNET", bandwidth_gbps=100)
        with self.assertWarns(UserWarning):
            CloudInstance(name="node-a", profile_ref="prof",
                          image=_basic_image(), size="m", subnet="sub",
                          interconnect=ic)
        return


class MountTargetResolutionTests(unittest.TestCase):

    def test_mount_target_resolution_during_validate(self) -> None:
        mount = SharedFsMountSpec(filesystem_name="weka-fs",
                                  target_instance="gpu-node",
                                  mount_path="/mnt/weka")
        # Resolves cleanly when the target instance + filesystem are declared.
        resolve_mount_targets(mount_specs=[mount],
                              instance_names=["gpu-node", "cpu-node"],
                              filesystem_names=["weka-fs"])

        # Unresolved target_instance raises a semantic error during validate.
        with self.assertRaises(SchemaSemanticError):
            resolve_mount_targets(mount_specs=[mount],
                                  instance_names=["cpu-node"],
                                  filesystem_names=["weka-fs"])

        # Unresolved filesystem_name raises a semantic error during validate.
        with self.assertRaises(SchemaSemanticError):
            resolve_mount_targets(mount_specs=[mount],
                                  instance_names=["gpu-node"],
                                  filesystem_names=["other-fs"])
        return


class ConnectivityBoundaryTests(unittest.TestCase):

    def test_vpn_join_plus_training_fabric_warns(self) -> None:
        vpn = VPNJoinSpec(provider="tailscale",
                          control_plane_credential="ts-oauth",
                          hostname_template="node-{index}")
        ic = CloudInterconnect(kind="EFA", bandwidth_gbps=400,
                               topology="RAIL_OPTIMIZED")
        # The configuration is accepted but emits the documented warning.
        with self.assertWarns(UserWarning):
            instance = CloudInstance(name="gpu-node", profile_ref="prof",
                                     image=_basic_image(), size="8xh100",
                                     subnet="sub", vpn_join=vpn,
                                     interconnect=ic,
                                     placement_group="cluster-a")
        self.assertIsNotNone(instance.vpn_join)
        self.assertEqual(instance.interconnect.kind, "EFA")
        return

    def test_vpn_join_plus_ethernet_does_not_training_warn(self) -> None:
        vpn = VPNJoinSpec(provider="tailscale",
                          control_plane_credential="ts-oauth",
                          hostname_template="node-{index}")
        ic = CloudInterconnect(kind="ETHERNET", bandwidth_gbps=100)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            CloudInstance(name="node-a", profile_ref="prof",
                          image=_basic_image(), size="m", subnet="sub",
                          vpn_join=vpn, interconnect=ic,
                          placement_group="cluster-a")
        training_warnings = [
            w for w in captured
            if "training-fabric interconnect" in str(w.message)
        ]
        self.assertEqual(len(training_warnings), 0)
        return


if __name__ == "__main__":
    unittest.main()
