"""
    .. module:: provisioningstatestore
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: On-disk store for per-run provisioning state.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import datetime
import os

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from automojo.provisioning.model.exceptions import SchemaSemanticError
from automojo.provisioning.state.atomicwrite import write_tmp_then_rename
from automojo.provisioning.state.crossplatformlock import cross_platform_lock
from automojo.provisioning.state.redactforpersistence import (
    redact_for_persistence
)
from automojo.provisioning.state.runindexentry import RunIndexEntry
from automojo.provisioning.state.runstate import RunState
from automojo.provisioning.state.runstatus import RunStatus


class ProvisioningStateStore:
    """
        File-backed store rooted at ``.output/provisioning/``.

        Layout:

            <root>/
                index.yaml
                <runid>/
                    spec.yaml
                    plan.yaml
                    result.yaml
                    inventory.yaml
                    landscape.yaml
                    stages.log
                <runid>.destroyed/
                    ... (renamed after clean destroy) ...

        All YAML writes are atomic via ``write_tmp_then_rename``; the
        ``stages.log`` file is append-only.
    """

    def __init__(self, *, root: Path) -> None:
        """
            Construct a ProvisioningStateStore.

            :param root: Root directory; created on first use.
        """
        self._root: Path = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        return

    @property
    def root(self) -> Path:
        """
            Return the root directory.

            :returns: The root Path.
        """
        rtnval = self._root
        return rtnval

    def run_dir(self, *, runid: str) -> Path:
        """
            Return the run directory Path (does not create it).

            :param runid: Run identifier.

            :returns: The run directory Path.
        """
        rtnval = self._root / runid
        return rtnval

    def create_run(self, *, runid: str,
                   spec_path: Optional[Union[str, Path]] = None,
                   venues: Optional[List[str]] = None) -> Path:
        """
            Create the run directory and append an index entry.

            :param runid: Run identifier.
            :param spec_path: Source spec path string.
            :param venues: Venue names.

            :returns: The created run directory Path.
        """
        rdir = self.run_dir(runid=runid)
        rdir.mkdir(parents=True, exist_ok=True)

        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        spec_path_str = str(spec_path) if spec_path is not None else None
        entry = RunIndexEntry(runid=runid, started=started,
                              status=RunStatus.STARTED,
                              spec_path=spec_path_str,
                              venues=venues if venues is not None else [])
        self._append_index_entry(entry=entry)
        rtnval = rdir
        return rtnval

    def write_state(self, *, runid: str, state: RunState) -> None:
        """
            Persist the run state to disk (atomic per file).

            :param runid: Run identifier.
            :param state: RunState.
        """
        rdir = self.run_dir(runid=runid)
        rdir.mkdir(parents=True, exist_ok=True)

        spec_redacted = redact_for_persistence(value=state.spec)
        plan_redacted = redact_for_persistence(value=state.plan)
        results_redacted = redact_for_persistence(
            value=self._results_to_plain(results=state.results)
        )
        inventory_redacted = redact_for_persistence(
            value=self._inventory_to_plain(inventory=state.inventory)
        )

        write_tmp_then_rename(
            path=rdir / "spec.yaml",
            content=yaml.safe_dump(spec_redacted, sort_keys=True),
        )
        write_tmp_then_rename(
            path=rdir / "plan.yaml",
            content=yaml.safe_dump(plan_redacted, sort_keys=True),
        )
        write_tmp_then_rename(
            path=rdir / "result.yaml",
            content=yaml.safe_dump(results_redacted, sort_keys=True),
        )
        write_tmp_then_rename(
            path=rdir / "inventory.yaml",
            content=yaml.safe_dump(inventory_redacted, sort_keys=True),
        )
        return

    def load_run(self, *, runid: str) -> RunState:
        """
            Load a previously-persisted RunState.

            :param runid: Run identifier.

            :returns: A RunState reconstructed from disk.
            :raises: SchemaSemanticError
        """
        rdir = self.run_dir(runid=runid)
        if not rdir.exists():
            err_msg = "No run directory for runid={!r} under {}".format(
                runid, self._root
            )
            raise SchemaSemanticError(err_msg)

        def _load_yaml(name: str) -> Any:
            path = rdir / name
            if not path.exists():
                rtnval: Any = None
                return rtnval
            with open(str(path), "r") as fh:
                rtnval = yaml.safe_load(fh)
            return rtnval

        spec_data = _load_yaml("spec.yaml") or {}
        plan_data = _load_yaml("plan.yaml") or {}
        results_data = _load_yaml("result.yaml") or {}
        inv_data = _load_yaml("inventory.yaml") or {}

        rtnval = RunState(runid=runid, spec=spec_data, plan=plan_data,
                          results=results_data, inventory=inv_data)
        return rtnval

    def append_log(self, *, runid: str, line: str) -> None:
        """
            Append a line to ``stages.log``.

            :param runid: Run identifier.
            :param line: Single log line (newline appended automatically).
        """
        rdir = self.run_dir(runid=runid)
        rdir.mkdir(parents=True, exist_ok=True)
        path = rdir / "stages.log"
        with open(str(path), "a") as fh:
            fh.write(line.rstrip("\n") + "\n")
        return

    def write_landscape(self, *, runid: str,
                        landscape: Dict[str, Any]) -> None:
        """
            Write the landscape YAML block.

            :param runid: Run identifier.
            :param landscape: Landscape dict.
        """
        rdir = self.run_dir(runid=runid)
        rdir.mkdir(parents=True, exist_ok=True)
        write_tmp_then_rename(
            path=rdir / "landscape.yaml",
            content=yaml.safe_dump(landscape, sort_keys=True),
        )
        return

    def list_runs(self) -> List[RunIndexEntry]:
        """
            Return all index entries.

            :returns: List of RunIndexEntry.
        """
        index_path = self._root / "index.yaml"
        if not index_path.exists():
            rtnval: List[RunIndexEntry] = []
            return rtnval
        with open(str(index_path), "r") as fh:
            data = yaml.safe_load(fh) or []

        rtnval = []
        for entry in data:
            rtnval.append(RunIndexEntry.from_dict(entry))
        return rtnval

    def latest_run(self) -> Optional[RunIndexEntry]:
        """
            Return the most recently appended index entry.

            :returns: The latest RunIndexEntry or None.
        """
        all_runs = self.list_runs()
        if len(all_runs) == 0:
            rtnval: Optional[RunIndexEntry] = None
            return rtnval
        rtnval = all_runs[-1]
        return rtnval

    def mark_destroyed(self, *, runid: str) -> None:
        """
            Rename ``<runid>/`` to ``<runid>.destroyed/`` after clean destroy.

            :param runid: Run identifier.
        """
        rdir = self.run_dir(runid=runid)
        if not rdir.exists():
            return
        target = self._root / "{}.destroyed".format(runid)
        os.replace(str(rdir), str(target))

        self._update_index_status(runid=runid, status=RunStatus.DESTROYED)
        return

    def mark_finished(self, *, runid: str, status: RunStatus) -> None:
        """
            Mark a run finished in the index.

            :param runid: Run identifier.
            :param status: Terminal RunStatus.
        """
        self._update_index_status(runid=runid, status=status)
        return

    def _index_lock_path(self) -> Path:
        """
            Return the advisory lock-file Path guarding ``index.yaml``.

            :returns: The lock-file Path.
        """
        rtnval = self._root / "index.yaml.lock"
        return rtnval

    def _append_index_entry(self, *, entry: RunIndexEntry) -> None:
        """
            Append an index entry under an advisory cross-platform lock.

            The read-modify-write of ``index.yaml`` is serialised through
            :func:`cross_platform_lock` so concurrent provisioning runs do
            not lose each other's index entries.

            :param entry: The RunIndexEntry.

            :raises: ProvisioningLockTimeoutError
        """
        index_path = self._root / "index.yaml"
        with cross_platform_lock(path=self._index_lock_path()):
            if index_path.exists():
                with open(str(index_path), "r") as fh:
                    data = yaml.safe_load(fh) or []
            else:
                data = []
            data.append(entry.to_dict())
            write_tmp_then_rename(
                path=index_path,
                content=yaml.safe_dump(data, sort_keys=False),
            )
        return

    def _update_index_status(self, *, runid: str,
                             status: RunStatus) -> None:
        """
            Update the index entry's status + finished timestamp under an
            advisory cross-platform lock.

            The read-modify-write of ``index.yaml`` is serialised through
            :func:`cross_platform_lock` so concurrent provisioning runs do
            not clobber each other's status updates.

            :param runid: Run identifier.
            :param status: New status.

            :raises: ProvisioningLockTimeoutError
        """
        index_path = self._root / "index.yaml"
        with cross_platform_lock(path=self._index_lock_path()):
            if not index_path.exists():
                return
            with open(str(index_path), "r") as fh:
                data = yaml.safe_load(fh) or []
            finished = datetime.datetime.now(
                datetime.timezone.utc).isoformat()
            for entry in data:
                if entry.get("runid") == runid:
                    entry["status"] = status.value
                    entry["finished"] = finished
            write_tmp_then_rename(
                path=index_path,
                content=yaml.safe_dump(data, sort_keys=False),
            )
        return

    @staticmethod
    def _results_to_plain(*, results: Dict[str, Any]) -> Dict[str, Any]:
        """
            Convert ProvisioningResult instances to plain dicts.

            :param results: Per-venue map.

            :returns: Plain dict map.
        """
        rtnval: Dict[str, Any] = {}
        for venue, value in results.items():
            if hasattr(value, "to_dict"):
                rtnval[venue] = value.to_dict()
            else:
                rtnval[venue] = value
        return rtnval

    @staticmethod
    def _inventory_to_plain(*, inventory: Dict[str, Any]) -> Dict[str, Any]:
        """
            Convert ProvisionedResource lists to plain dicts.

            :param inventory: Per-venue map.

            :returns: Plain dict map.
        """
        rtnval: Dict[str, Any] = {}
        for venue, value in inventory.items():
            converted: List[Any] = []
            for item in value:
                if hasattr(item, "to_dict"):
                    converted.append(item.to_dict())
                else:
                    converted.append(item)
            rtnval[venue] = converted
        return rtnval
