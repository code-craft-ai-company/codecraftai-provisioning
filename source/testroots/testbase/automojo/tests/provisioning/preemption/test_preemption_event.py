"""
    .. module:: test_preemption_event
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the PreemptionEvent SchemaObject.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import unittest

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.preemption.preemptionevent import PreemptionEvent


class PreemptionEventTests(unittest.TestCase):

    def test_minimal_construction(self) -> None:
        event = PreemptionEvent(instance_name="trainer-0",
                                venue_id="i-0abc",
                                detected_at_stage="apply",
                                policy=PreemptionPolicy.FAIL)
        self.assertEqual(event.instance_name, "trainer-0")
        self.assertEqual(event.venue_id, "i-0abc")
        self.assertEqual(event.detected_at_stage, "apply")
        self.assertEqual(event.policy, "FAIL")
        self.assertIsNone(event.original_venue_id)
        self.assertIsNone(event.replacement_venue_id)
        self.assertIsNone(event.reason)
        return

    def test_accepts_string_policy(self) -> None:
        event = PreemptionEvent(instance_name="h", venue_id="v",
                                detected_at_stage="verify",
                                policy="REACQUIRE")
        self.assertEqual(event.policy, "REACQUIRE")
        return

    def test_rejects_invalid_stage(self) -> None:
        with self.assertRaises(SchemaValidationError):
            PreemptionEvent(instance_name="h", venue_id="v",
                            detected_at_stage="provision",
                            policy=PreemptionPolicy.FAIL)
        return

    def test_rejects_invalid_policy(self) -> None:
        with self.assertRaises(SchemaValidationError):
            PreemptionEvent(instance_name="h", venue_id="v",
                            detected_at_stage="apply",
                            policy="WHATEVER")
        return

    def test_rejects_empty_instance_name(self) -> None:
        with self.assertRaises(SchemaValidationError):
            PreemptionEvent(instance_name="", venue_id="v",
                            detected_at_stage="apply",
                            policy=PreemptionPolicy.FAIL)
        return

    def test_rejects_empty_venue_id(self) -> None:
        with self.assertRaises(SchemaValidationError):
            PreemptionEvent(instance_name="h", venue_id="",
                            detected_at_stage="apply",
                            policy=PreemptionPolicy.FAIL)
        return

    def test_roundtrip_through_dict(self) -> None:
        event = PreemptionEvent(instance_name="trainer-0",
                                venue_id="i-new",
                                detected_at_stage="verify",
                                policy=PreemptionPolicy.REACQUIRE,
                                original_venue_id="i-old",
                                replacement_venue_id="i-new",
                                reason="spot-capacity-reclaim")
        payload = event.to_dict()
        self.assertEqual(payload["instance_name"], "trainer-0")
        self.assertEqual(payload["policy"], "REACQUIRE")
        self.assertEqual(payload["original_venue_id"], "i-old")
        self.assertEqual(payload["replacement_venue_id"], "i-new")
        self.assertEqual(payload["reason"], "spot-capacity-reclaim")

        rebuilt = PreemptionEvent.from_dict(payload)
        self.assertEqual(rebuilt, event)
        return


if __name__ == "__main__":
    unittest.main()
