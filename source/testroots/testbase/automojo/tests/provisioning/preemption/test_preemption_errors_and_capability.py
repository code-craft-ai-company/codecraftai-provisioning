"""
    .. module:: test_preemption_errors_and_capability
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for ProvisioningPreemptionError and the per-venue
               supports_preemption capability.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Automation Mojo LLC"
__credits__ = []


import unittest

from automojo.provisioning.model.cloud._fake.fakecloudprovisioner import (
    FakeCloudProvisioner
)
from automojo.provisioning.preemption.preemptionerrors import (
    ProvisioningPreemptionError
)


class ProvisioningPreemptionErrorTests(unittest.TestCase):

    def test_is_runtime_error_subclass(self) -> None:
        self.assertTrue(issubclass(ProvisioningPreemptionError, RuntimeError))
        return

    def test_can_be_raised_and_caught(self) -> None:
        with self.assertRaises(ProvisioningPreemptionError):
            raise ProvisioningPreemptionError("preempted")
        return

    def test_carries_message(self) -> None:
        error = ProvisioningPreemptionError("instance i-0 preempted")
        self.assertIn("i-0", str(error))
        return


class SupportsPreemptionTests(unittest.TestCase):

    def test_supports_preemption_default_false(self) -> None:
        self.assertFalse(FakeCloudProvisioner.supports_preemption())
        return

    def test_aws_supports_preemption(self) -> None:
        from automojo.provisioning.venues.aws.awscloudprovisioner import (
            AwsCloudProvisioner
        )
        self.assertTrue(AwsCloudProvisioner.supports_preemption())
        return

    def test_azure_supports_preemption(self) -> None:
        from automojo.provisioning.venues.azure.azurecloudprovisioner import (
            AzureCloudProvisioner
        )
        self.assertTrue(AzureCloudProvisioner.supports_preemption())
        return

    def test_gcp_supports_preemption(self) -> None:
        from automojo.provisioning.venues.google.googlecloudprovisioner import (
            GoogleCloudProvisioner
        )
        self.assertTrue(GoogleCloudProvisioner.supports_preemption())
        return

    def test_oracle_supports_preemption(self) -> None:
        from automojo.provisioning.venues.oracle.oraclecloudprovisioner import (
            OracleCloudProvisioner
        )
        self.assertTrue(OracleCloudProvisioner.supports_preemption())
        return

    def test_lambdalabs_supports_preemption(self) -> None:
        from automojo.provisioning.venues.lambdalabs.lambdalabscloudprovisioner \
            import LambdalabsCloudProvisioner
        self.assertTrue(LambdalabsCloudProvisioner.supports_preemption())
        return


if __name__ == "__main__":
    unittest.main()
