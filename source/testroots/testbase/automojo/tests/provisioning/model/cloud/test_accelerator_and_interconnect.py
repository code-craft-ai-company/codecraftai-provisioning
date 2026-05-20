"""
    .. module:: test_accelerator_and_interconnect
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Unit tests for accelerator, interconnect, and shared-fs classes.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import unittest

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.cloudacceleratorspec import (
    CloudAcceleratorSpec
)
from automojo.provisioning.model.cloud.cloudinterconnect import CloudInterconnect
from automojo.provisioning.model.cloud.sharedfsmountspec import SharedFsMountSpec
from automojo.provisioning.model.cloud.cloudsharedfilesystem import (
    CloudSharedFilesystem
)


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


if __name__ == "__main__":
    unittest.main()
