"""
    .. module:: test_state_persistence
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for ProvisioningStateStore and helper modules.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import tempfile
import threading
import unittest

from pathlib import Path

from ccai.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from ccai.provisioning.model.cloud.provisioningresult import (
    ProvisioningResult
)
from ccai.provisioning.state.atomicwrite import write_tmp_then_rename
from ccai.provisioning.state.crossplatformlock import (
    cross_platform_lock
)
from ccai.provisioning.state.provisioninglocktimeouterror import (
    ProvisioningLockTimeoutError
)
from ccai.provisioning.state.provisioningstatestore import (
    ProvisioningStateStore
)
from ccai.provisioning.state.redactforpersistence import (
    redact_for_persistence, REDACTED_PLACEHOLDER,
)
from ccai.provisioning.state.runstate import RunState
from ccai.provisioning.state.runstatus import RunStatus


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

    def test_redacts_authkey_write_files_content(self) -> None:
        """
            C7 regression: a cloud-init write_files entry whose path names an
            auth-key file has its (innocuously-named) ``content`` redacted.
        """
        before = {"write_files": [
            {"path": "/etc/tailscale/authkey",
             "content": "tskey-leaked-via-content"},
            {"path": "/etc/motd", "content": "welcome"},
        ]}
        after = redact_for_persistence(value=before)
        self.assertEqual(after["write_files"][0]["content"],
                         REDACTED_PLACEHOLDER)
        # A non-secret file path keeps its content.
        self.assertEqual(after["write_files"][1]["content"], "welcome")
        return

    def test_redacts_twingate_connector_content(self) -> None:
        """
            C7 regression: a Twingate connector file write_files entry has
            its ``content`` redacted by value-context.
        """
        before = {"path": "/etc/twingate/connector.conf",
                  "content": "twingate-token-leaked"}
        after = redact_for_persistence(value=before)
        self.assertEqual(after["content"], REDACTED_PLACEHOLDER)
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

    def test_concurrent_create_run_does_not_lose_index_entries(self) -> None:
        """
            C5 regression: many concurrent create_run calls must all land
            in index.yaml -- the read-modify-write is serialised by the
            cross-platform advisory lock, so no entry is lost.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            run_count = 24
            errors: list = []

            def _create(index: int) -> None:
                try:
                    store.create_run(runid="run-{:03d}".format(index),
                                     venues=[])
                except Exception as xcpt:  # noqa: BLE001
                    errors.append(xcpt)
                return

            workers = []
            for index in range(run_count):
                worker = threading.Thread(target=_create, args=(index,))
                workers.append(worker)
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()

            self.assertEqual(len(errors), 0)
            entries = store.list_runs()
            self.assertEqual(len(entries), run_count)
            recorded = sorted(entry.runid for entry in entries)
            expected = sorted("run-{:03d}".format(i)
                              for i in range(run_count))
            self.assertEqual(recorded, expected)
        return

    def test_concurrent_index_status_updates_preserve_all_entries(self
                                                                  ) -> None:
        """
            C5 regression: concurrent mark_finished updates against a shared
            index.yaml must not clobber sibling entries.
        """
        with tempfile.TemporaryDirectory() as tmp:
            store = ProvisioningStateStore(root=Path(tmp))
            run_count = 16
            for index in range(run_count):
                store.create_run(runid="run-{:03d}".format(index),
                                 venues=[])

            def _finish(index: int) -> None:
                store.mark_finished(runid="run-{:03d}".format(index),
                                    status=RunStatus.APPLIED)
                return

            workers = []
            for index in range(run_count):
                worker = threading.Thread(target=_finish, args=(index,))
                workers.append(worker)
            for worker in workers:
                worker.start()
            for worker in workers:
                worker.join()

            entries = store.list_runs()
            self.assertEqual(len(entries), run_count)
            for entry in entries:
                self.assertEqual(entry.status, RunStatus.APPLIED.value)
        return


if __name__ == "__main__":
    unittest.main()
