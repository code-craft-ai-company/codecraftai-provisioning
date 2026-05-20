"""
    .. module:: test_preemption_handler
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for handle_preemption — each PreemptionPolicy branch.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import logging
import unittest

from typing import Any, List

from automojo.provisioning.model.cloud.cloudvenue import CloudVenue
from automojo.provisioning.model.cloud.cloudimage import CloudImage
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.model.cloud.provisionedresource import (
    ProvisionedResource
)
from automojo.provisioning.model.cloud._fake.fakecloudprovisioner import (
    FakeCloudProvisioner
)
from automojo.provisioning.preemption.preemptionerrors import (
    ProvisioningPreemptionError
)
from automojo.provisioning.preemption.preemptionhandler import (
    handle_preemption
)


def _make_venue() -> CloudVenue:
    rtnval = CloudVenue(name="lab", provider="fake",
                        management_url="https://fake",
                        subscription="sub", region="r1",
                        credential="cred")
    return rtnval


def _make_instance(*, policy: Any = PreemptionPolicy.FAIL) -> CloudInstance:
    image = CloudImage(family="ubuntu", version="24.04",
                       architecture="x86_64")
    rtnval = CloudInstance(name="trainer-0", profile_ref="p", image=image,
                           size="m5.large", subnet="s",
                           preemption_policy=policy)
    return rtnval


class ReacquireFakeProvisioner(FakeCloudProvisioner):
    """
        FakeCloudProvisioner extended with a reacquire_instance hook that
        records each recreation and mints a fresh venue id.
    """

    def __init__(self, *, venue: CloudVenue) -> None:
        super().__init__(venue=venue, spec=None)
        self._reacquire_log: List[str] = []
        self._next_id: int = 1
        return

    @property
    def reacquire_log(self) -> List[str]:
        rtnval = self._reacquire_log
        return rtnval

    def reacquire_instance(self, *, spec: CloudInstance,
                           aspects: Any) -> ProvisionedResource:
        new_id = "i-replacement-{}".format(self._next_id)
        self._next_id = self._next_id + 1
        self._reacquire_log.append(spec.name)
        owner_tag = {self.OWNER_TAG_KEY: self.OWNER_TAG_VALUE}
        resource = ProvisionedResource(kind="instance", name=spec.name,
                                       venue_id=new_id,
                                       attributes={"recreated": True},
                                       tags=[owner_tag])
        self._state[("instance", spec.name)] = resource
        rtnval = resource
        return rtnval


class HandlePreemptionFailTests(unittest.TestCase):

    def test_fail_branch_raises_preemption_error(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.FAIL)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        with self.assertRaises(ProvisioningPreemptionError) as captured:
            handle_preemption(spec=instance, policy=PreemptionPolicy.FAIL,
                              provisioner=provisioner, stage="apply",
                              aspects=None, venue_id="i-old",
                              reason="spot-reclaim")
        message = str(captured.exception)
        self.assertIn("trainer-0", message)
        self.assertIn("i-old", message)
        self.assertIn("FAIL", message)
        self.assertIn("spot-reclaim", message)
        return

    def test_fail_branch_raises_in_verify_stage(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.FAIL)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        with self.assertRaises(ProvisioningPreemptionError):
            handle_preemption(spec=instance, policy=PreemptionPolicy.FAIL,
                              provisioner=provisioner, stage="verify",
                              aspects=None, venue_id="i-old")
        return


class HandlePreemptionReacquireTests(unittest.TestCase):

    def test_reacquire_branch_creates_replacement(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.REACQUIRE)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        replacement = handle_preemption(
            spec=instance, policy=PreemptionPolicy.REACQUIRE,
            provisioner=provisioner, stage="apply", aspects=None,
            venue_id="i-old")
        self.assertIsInstance(replacement, ProvisionedResource)
        self.assertEqual(replacement.name, "trainer-0")
        self.assertNotEqual(replacement.venue_id, "i-old")
        self.assertEqual(provisioner.reacquire_log, ["trainer-0"])
        return

    def test_reacquire_logs_warning_with_old_and_new_id(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.REACQUIRE)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        with self.assertLogs(
                "automojo.provisioning.preemption.preemptionhandler",
                level=logging.WARNING) as captured:
            replacement = handle_preemption(
                spec=instance, policy=PreemptionPolicy.REACQUIRE,
                provisioner=provisioner, stage="apply", aspects=None,
                venue_id="i-old")
        joined = "\n".join(captured.output)
        self.assertIn("i-old", joined)
        self.assertIn(replacement.venue_id, joined)
        return

    def test_reacquire_without_hook_raises(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.REACQUIRE)
        provisioner = FakeCloudProvisioner(venue=_make_venue(), spec=None)
        with self.assertRaises(ProvisioningPreemptionError):
            handle_preemption(spec=instance,
                              policy=PreemptionPolicy.REACQUIRE,
                              provisioner=provisioner, stage="apply",
                              aspects=None, venue_id="i-old")
        return


class HandlePreemptionBestEffortTests(unittest.TestCase):

    def test_best_effort_branch_returns_none(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.BEST_EFFORT)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        result = handle_preemption(
            spec=instance, policy=PreemptionPolicy.BEST_EFFORT,
            provisioner=provisioner, stage="apply", aspects=None,
            venue_id="i-old")
        self.assertIsNone(result)
        return

    def test_best_effort_drops_from_inventory(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.BEST_EFFORT)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        handle_preemption(spec=instance,
                          policy=PreemptionPolicy.BEST_EFFORT,
                          provisioner=provisioner, stage="apply",
                          aspects=None, venue_id="i-old")
        inventory = provisioner.inventory(aspects=None)
        names = [r.name for r in inventory]
        self.assertNotIn("trainer-0", names)
        return

    def test_best_effort_logs_info(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.BEST_EFFORT)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        with self.assertLogs(
                "automojo.provisioning.preemption.preemptionhandler",
                level=logging.INFO) as captured:
            handle_preemption(spec=instance,
                              policy=PreemptionPolicy.BEST_EFFORT,
                              provisioner=provisioner, stage="apply",
                              aspects=None, venue_id="i-old")
        joined = "\n".join(captured.output)
        self.assertIn("trainer-0", joined)
        self.assertIn("BEST_EFFORT", joined)
        return


class HandlePreemptionDispatchTests(unittest.TestCase):

    def test_accepts_string_policy(self) -> None:
        instance = _make_instance(policy="BEST_EFFORT")
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        result = handle_preemption(spec=instance, policy="BEST_EFFORT",
                                   provisioner=provisioner, stage="apply",
                                   aspects=None, venue_id="i-old")
        self.assertIsNone(result)
        return

    def test_rejects_invalid_stage(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.FAIL)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        with self.assertRaises(ProvisioningPreemptionError):
            handle_preemption(spec=instance, policy=PreemptionPolicy.FAIL,
                              provisioner=provisioner, stage="destroy",
                              aspects=None, venue_id="i-old")
        return

    def test_rejects_invalid_policy(self) -> None:
        instance = _make_instance(policy=PreemptionPolicy.FAIL)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        with self.assertRaises(ProvisioningPreemptionError):
            handle_preemption(spec=instance, policy="WHATEVER",
                              provisioner=provisioner, stage="apply",
                              aspects=None, venue_id="i-old")
        return

    def test_destroy_during_reacquire_does_not_recreate(self) -> None:
        # The handler only accepts apply/verify stages; a destroy-stage
        # invocation must refuse rather than reacquire, so no replacement is
        # ever created during teardown.
        instance = _make_instance(policy=PreemptionPolicy.REACQUIRE)
        provisioner = ReacquireFakeProvisioner(venue=_make_venue())
        with self.assertRaises(ProvisioningPreemptionError):
            handle_preemption(spec=instance,
                              policy=PreemptionPolicy.REACQUIRE,
                              provisioner=provisioner, stage="destroy",
                              aspects=None, venue_id="i-old")
        self.assertEqual(provisioner.reacquire_log, [])
        return


if __name__ == "__main__":
    unittest.main()
