"""
    .. module:: test_state_persistence
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for ProvisioningStateStore and helper modules.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import tempfile
import unittest

from pathlib import Path

import yaml

from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from automojo.provisioning.state.atomicwrite import write_tmp_then_rename
from automojo.provisioning.state.crossplatformlock import (
    cross_platform_lock
)
from automojo.provisioning.state.provisioninglocktimeouterror import (
    ProvisioningLockTimeoutError
)
from automojo.provisioning.state.provisioningstatestore import (
    ProvisioningStateStore
)
from automojo.provisioning.state.redactforpersistence import (
    redact_for_persistence, REDACTED_PLACEHOLDER,
)
from automojo.provisioning.state.runstate import RunState
from automojo.provisioning.state.runstatus import RunStatus


class AtomicWriteTests(unittest.TestCase):

    def test_atomic_write_creates_final_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "data.yaml"
            write_tmp_then_rename(path=target, content="hello: world\n")
            self.assertEqual(target.read_text(), "hello: world\n")
            self.assertFalse((Path(tmp) / "data.yaml.tmp").exists())
        return


class CrossPlatformLockTests(unittest.TestCase):

    def test_lock_timeout_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = Path(tmp) / "lock"
            with cross_platform_lock(path=lockfile,
                                     timeout_seconds=1.0,
                                     poll_interval_seconds=0.05):
                with self.assertRaises(ProvisioningLockTimeoutError):
                    with cross_platform_lock(path=lockfile,
                                             timeout_seconds=0.2,
                                             poll_interval_seconds=0.05):
                        pass
        return

    def test_lock_released_on_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lockfile = Path(tmp) / "lock"
            with cross_platform_lock(path=lockfile, timeout_seconds=1.0):
                pass
            # Second acquisition must succeed immediately.
            with cross_platform_lock(path=lockfile, timeout_seconds=0.1):
                pass
        return


class RedactionTests(unittest.TestCase):

    def test_redacts_authkey_keys(self) -> None:
        before = {"name": "x",
                  "credential": {"authkey": "tskey-secret",
                                 "client_secret": "cs-secret"}}
        after = redact_for_persistence(value=before)
        self.assertEqual(after["credential"]["authkey"], REDACTED_PLACEHOLDER)
        self.assertEqual(after["credential"]["client_secret"],
                         REDACTED_PLACEHOLDER)
        self.assertEqual(after["name"], "x")
        return

    def test_redacts_nested_lists(self) -> None:
        before = [{"token": "abc"}, "plain"]
        after = redact_for_persistence(value=before)
        self.assertEqual(after[0]["token"], REDACTED_PLACEHOLDER)
        self.assertEqual(after[1], "plain")
        return


class StoreLayoutTests(unittest.TestCase):

    def test_create_run_creates_dir_and_index_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            store.create_run(runid="run-1", spec_path="spec.yaml",
                             venues=["aws-east"])
            self.assertTrue((Path(tmp) / "run-1").is_dir())
            self.assertTrue((Path(tmp) / "index.yaml").exists())
            entries = store.list_runs()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].runid, "run-1")
        return

    def test_write_and_load_state_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            store.create_run(runid="run-1", venues=["aws-east"])

            res = ProvisionedResource(kind="instance", name="web-01",
                                      venue_id="i-1")
            result = ProvisioningResult(created=[res])

            state = RunState(runid="run-1",
                             spec={"apod": {"name": "lab"}},
                             results={"aws-east": result},
                             inventory={"aws-east": [res]})
            store.write_state(runid="run-1", state=state)

            loaded = store.load_run(runid="run-1")
            self.assertIn("aws-east", loaded.inventory)
            self.assertEqual(loaded.inventory["aws-east"][0]["name"], "web-01")
        return

    def test_mark_destroyed_renames_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            store.create_run(runid="run-1", venues=[])
            store.mark_destroyed(runid="run-1")
            self.assertFalse((Path(tmp) / "run-1").exists())
            self.assertTrue((Path(tmp) / "run-1.destroyed").exists())
        return

    def test_secret_scrubbed_from_persisted_spec(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            store.create_run(runid="run-1", venues=[])
            spec = {"providers": [{"authkey": "tskey-leaked-secret"}]}
            state = RunState(runid="run-1", spec=spec)
            store.write_state(runid="run-1", state=state)
            text = (Path(tmp) / "run-1" / "spec.yaml").read_text()
            self.assertNotIn("tskey-leaked-secret", text)
            self.assertIn(REDACTED_PLACEHOLDER, text)
        return

    def test_mark_finished_updates_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            store.create_run(runid="run-1", venues=[])
            store.mark_finished(runid="run-1", status=RunStatus.APPLIED)
            entries = store.list_runs()
            self.assertEqual(entries[0].status, RunStatus.APPLIED.value)
            self.assertIsNotNone(entries[0].finished)
        return

    def test_append_log_writes_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            store.create_run(runid="run-1", venues=[])
            store.append_log(runid="run-1", line="hello")
            store.append_log(runid="run-1", line="world")
            log_path = Path(tmp) / "run-1" / "stages.log"
            self.assertEqual(log_path.read_text(), "hello\nworld\n")
        return


if __name__ == "__main__":
    unittest.main()
