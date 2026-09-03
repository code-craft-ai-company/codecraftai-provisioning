"""
    .. module:: test_bootstrap_secrets_binding
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Proves the engine resolves index credentials once at
               LOAD_VALIDATE and binds them for every apply stage.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from typing import Any, Dict, List, Optional

from ccai.credentials.basiccredential import BasicCredential
from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.provisioning.aspects.provisioningaspects import ProvisioningAspects
from ccai.provisioning.cloudinit.bootstrapsecrets import (
    BootstrapSecrets, current_bootstrap_secrets,
)
from ccai.provisioning.cloudprovisionerregistry import CloudProvisionerRegistry
from ccai.provisioning.model.cloud.provisioningresult import ProvisioningResult
from ccai.provisioning.provisioningengine import ProvisioningEngine

from ccai.tests.provisioning.engine.test_engine_pipeline import (
    MockCloudProvisioner, _venue,
)


class _RecordingProvisioner(MockCloudProvisioner):
    """
        Records the bootstrap secrets visible during each apply_subset call.
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.seen: List[Optional[BootstrapSecrets]] = []
        return

    def apply_subset(self, *, kinds: List[str], aspects: Any) -> ProvisioningResult:
        self.seen.append(current_bootstrap_secrets())
        rtnval = super().apply_subset(kinds=kinds, aspects=aspects)
        return rtnval


def _spec(with_credential: bool = True) -> Dict[str, Any]:
    env: Dict[str, Any] = {"path": "/opt/venvs/app", "packages": ["rich"],
                           "index_url": "https://pypi.internal/simple"}
    if with_credential:
        env["index_credential"] = "pypi:internal"
    rtnval = {
        "networks": [{"name": "vpc-east"}],
        "subnets": [{"name": "sub-east", "network": "vpc-east"}],
        "instances": [
            {"name": "web-01", "subnet": "sub-east", "python_environments": [env]},
            {"name": "web-02", "subnet": "sub-east"},
        ],
    }
    return rtnval


def _lookup(reference: str) -> BasicCredential:
    assert reference == "pypi:internal", reference
    rtnval = BasicCredential(identifier=reference, categories=["basic"],
                             username="svc", password="pw")
    return rtnval


def _engine(spec: Dict[str, Any], lookup=None):
    registry = CloudProvisionerRegistry()
    provisioner = _RecordingProvisioner(
        venue=_venue("mock-east"),
        venue_spec={"instances": [{"name": "web-01"}, {"name": "web-02"}],
                    "networks": [{"name": "vpc-east"}]})
    registry.register(name="mock-east", provisioner=provisioner)
    engine = ProvisioningEngine(spec=spec, registry=registry, credential_lookup=lookup)
    return engine, provisioner


class EngineBootstrapSecretsTests(unittest.TestCase):

    def test_validate_resolves_named_credentials_once(self) -> None:
        calls: List[str] = []

        def lookup(reference: str):
            calls.append(reference)
            return _lookup(reference)

        engine, _ = _engine(_spec(), lookup)
        engine.validate(aspects=ProvisioningAspects(dry_run=True))
        engine.validate(aspects=ProvisioningAspects(dry_run=True))
        self.assertEqual(calls, ["pypi:internal"])
        return

    def test_validate_fails_fast_without_a_lookup(self) -> None:
        engine, _ = _engine(_spec(), None)
        with self.assertRaises(SchemaSemanticError) as caught:
            engine.validate(aspects=ProvisioningAspects(dry_run=True))
        self.assertIn("credential_lookup", str(caught.exception))
        return

    def test_no_credentials_named_needs_no_lookup(self) -> None:
        engine, _ = _engine(_spec(with_credential=False), None)
        engine.validate(aspects=ProvisioningAspects(dry_run=True))
        return

    def test_apply_binds_secrets_for_every_stage_and_clears_after(self) -> None:
        engine, provisioner = _engine(_spec(), _lookup)
        engine.apply(aspects=ProvisioningAspects())
        self.assertGreaterEqual(len(provisioner.seen), 3)
        for seen in provisioner.seen:
            self.assertIsNotNone(seen)
            self.assertEqual(seen.index_credentials["pypi:internal"].username, "svc")
        self.assertIsNone(current_bootstrap_secrets())
        return

    def test_dry_run_apply_never_binds(self) -> None:
        engine, provisioner = _engine(_spec(), _lookup)
        engine.apply(aspects=ProvisioningAspects(dry_run=True))
        self.assertEqual(provisioner.seen, [])
        return


if __name__ == "__main__":
    unittest.main()
