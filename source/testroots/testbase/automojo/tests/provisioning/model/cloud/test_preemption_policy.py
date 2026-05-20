"""
    .. module:: test_preemption_policy
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: PreemptionPolicy enum + CloudInstance carrying-field tests.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import unittest

from automojo.provisioning.model.exceptions import SchemaValidationError
from automojo.provisioning.model.cloud.preemptionpolicy import PreemptionPolicy
from automojo.provisioning.model.cloud.cloudinstance import CloudInstance
from automojo.provisioning.model.cloud.cloudimage import CloudImage


def _image() -> CloudImage:
    rtnval = CloudImage(family="ubuntu", version="24.04", architecture="x86_64")
    return rtnval


class PreemptionPolicyTests(unittest.TestCase):

    def test_default_is_fail(self) -> None:
        inst = CloudInstance(name="h", profile_ref="p", image=_image(),
                             size="m5.large", subnet="s")
        self.assertEqual(inst.preemption_policy, PreemptionPolicy.FAIL.value)
        return

    def test_accepts_enum(self) -> None:
        inst = CloudInstance(name="h", profile_ref="p", image=_image(),
                             size="m5.large", subnet="s",
                             preemption_policy=PreemptionPolicy.REACQUIRE)
        self.assertEqual(inst.preemption_policy,
                         PreemptionPolicy.REACQUIRE.value)
        return

    def test_accepts_string(self) -> None:
        inst = CloudInstance(name="h", profile_ref="p", image=_image(),
                             size="m5.large", subnet="s",
                             preemption_policy="BEST_EFFORT")
        self.assertEqual(inst.preemption_policy,
                         PreemptionPolicy.BEST_EFFORT.value)
        return

    def test_rejects_unknown(self) -> None:
        with self.assertRaises(SchemaValidationError):
            CloudInstance(name="h", profile_ref="p", image=_image(),
                          size="m5.large", subnet="s",
                          preemption_policy="WHATEVER")
        return

    def test_roundtrip_serialises_policy(self) -> None:
        inst = CloudInstance(name="h", profile_ref="p", image=_image(),
                             size="m5.large", subnet="s",
                             preemption_policy=PreemptionPolicy.REACQUIRE)
        d = inst.to_dict()
        self.assertEqual(d["preemption_policy"], "REACQUIRE")
        rebuilt = CloudInstance.from_dict(d)
        self.assertEqual(rebuilt.preemption_policy,
                         PreemptionPolicy.REACQUIRE.value)
        return


if __name__ == "__main__":
    unittest.main()
