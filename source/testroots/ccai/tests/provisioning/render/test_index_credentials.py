"""
    .. module:: test_index_credentials
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the credentialed private-index path: secrets
               container, credential resolver, pip.conf embedding, and the
               composer's ambient fallback.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

import yaml

from ccai.credentials.apitokencredential import ApiTokenCredential
from ccai.credentials.basiccredential import BasicCredential
from ccai.credentials.personalapitokencredential import PersonalApiTokenCredential
from ccai.credentials.secrettokencredential import SecretTokenCredential
from ccai.credentials.sshcredential import SshCredential
from ccai.interfaces.pythonenvspec import PythonEnvironmentSpec
from ccai.interfaces.schemasemanticerror import SchemaSemanticError

from ccai.provisioning.cloudinit.bootstraprenderer import render_instance_user_data
from ccai.provisioning.cloudinit.bootstrapsecrets import (
    BootstrapSecrets, IndexCredential, bind_bootstrap_secrets,
    current_bootstrap_secrets,
)
from ccai.provisioning.cloudinit.cloudinitrenderererror import CloudInitRendererError
from ccai.provisioning.cloudinit.pythonenvcloudinitrenderer import (
    embed_index_credential, render_bootstrap_script, render_pip_config,
    render_python_env_cloud_init,
)
from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance
from ccai.provisioning.model.pythonenv.indexcredentialresolver import (
    TOKEN_USERNAME, collect_bootstrap_secrets, resolve_index_credential,
)


def _spec(**overrides) -> PythonEnvironmentSpec:
    kwargs = {"path": "/opt/venvs/app", "packages": ["rich"],
              "index_url": "https://pypi.internal/simple",
              "index_credential": "pypi:internal"}
    kwargs.update(overrides)
    rtnval = PythonEnvironmentSpec(**kwargs)
    return rtnval


def _instance(**overrides) -> CloudInstance:
    kwargs = {
        "name": "agent-01", "profile_ref": "profile",
        "image": CloudImage(family="ubuntu", version="24.04", architecture="x86_64"),
        "size": "general.small", "subnet": "subnet",
    }
    kwargs.update(overrides)
    rtnval = CloudInstance(**kwargs)
    return rtnval


def _secrets(username: str = "svc", secret: str = "s3cret") -> BootstrapSecrets:
    rtnval = BootstrapSecrets(index_credentials={
        "pypi:internal": IndexCredential(username=username, secret=secret),
    })
    return rtnval


class BootstrapSecretsTests(unittest.TestCase):

    def test_repr_never_shows_secret(self) -> None:
        secrets = _secrets()
        self.assertNotIn("s3cret", repr(secrets))
        self.assertNotIn("s3cret", repr(secrets.index_credentials["pypi:internal"]))
        return

    def test_credential_for_spec(self) -> None:
        secrets = _secrets()
        self.assertEqual(secrets.credential_for(spec=_spec()).username, "svc")
        self.assertIsNone(secrets.credential_for(spec=_spec(index_credential=None)))
        self.assertIsNone(secrets.credential_for(spec=_spec(index_credential="other")))
        return

    def test_bind_and_restore(self) -> None:
        self.assertIsNone(current_bootstrap_secrets())
        secrets = _secrets()
        with bind_bootstrap_secrets(secrets):
            self.assertIs(current_bootstrap_secrets(), secrets)
            with bind_bootstrap_secrets(None):
                self.assertIsNone(current_bootstrap_secrets())
            self.assertIs(current_bootstrap_secrets(), secrets)
        self.assertIsNone(current_bootstrap_secrets())
        return


class ResolverTests(unittest.TestCase):

    def _lookup(self, credential):
        def lookup(reference: str):
            self.assertEqual(reference, "pypi:internal")
            return credential
        return lookup

    def test_basic_credential(self) -> None:
        cred = BasicCredential(identifier="pypi:internal", categories=["basic"],
                               username="svc", password="pw")
        resolved = resolve_index_credential(spec=_spec(), credential_lookup=self._lookup(cred))
        self.assertEqual(resolved, IndexCredential(username="svc", secret="pw"))
        return

    def test_personal_api_token_credential(self) -> None:
        cred = PersonalApiTokenCredential(identifier="pypi:internal", categories=["personal-api-token"],
                                          username="svc", token="tok")
        resolved = resolve_index_credential(spec=_spec(), credential_lookup=self._lookup(cred))
        self.assertEqual(resolved, IndexCredential(username="svc", secret="tok"))
        return

    def test_api_and_secret_token_credentials_use_token_username(self) -> None:
        api = ApiTokenCredential(identifier="pypi:internal", categories=["api-token"], token="tok-a")
        secret = SecretTokenCredential(identifier="pypi:internal", categories=["secret-token"],
                                       endpoint="https://pypi.internal", token="tok-s")
        self.assertEqual(
            resolve_index_credential(spec=_spec(), credential_lookup=self._lookup(api)),
            IndexCredential(username=TOKEN_USERNAME, secret="tok-a"))
        self.assertEqual(
            resolve_index_credential(spec=_spec(), credential_lookup=self._lookup(secret)),
            IndexCredential(username=TOKEN_USERNAME, secret="tok-s"))
        return

    def test_wrong_class_rejected(self) -> None:
        cred = SshCredential(identifier="pypi:internal", categories=["ssh"],
                             username="svc", password="pw")
        with self.assertRaises(SchemaSemanticError) as caught:
            resolve_index_credential(spec=_spec(), credential_lookup=self._lookup(cred))
        self.assertIn("SshCredential", str(caught.exception))
        return

    def test_unresolved_reference_rejected(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            resolve_index_credential(spec=_spec(), credential_lookup=lambda ref: None)
        with self.assertRaises(SchemaSemanticError):
            resolve_index_credential(spec=_spec(),
                                     credential_lookup=lambda ref: (_ for _ in ()).throw(KeyError(ref)))
        return

    def test_spec_without_credential_rejected(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            resolve_index_credential(spec=_spec(index_credential=None),
                                     credential_lookup=lambda ref: None)
        return

    def test_collect_resolves_each_reference_once(self) -> None:
        calls = []

        def lookup(reference: str):
            calls.append(reference)
            return BasicCredential(identifier=reference, categories=["basic"],
                                   username="svc", password="pw")

        instances = [
            _instance(python_environments=[_spec(path="/a", name="a"), _spec(path="/b", name="b")]),
            _instance(name="agent-02", python_environments=[_spec(path="/c", name="c", index_credential=None)]),
            _instance(name="agent-03"),
        ]
        secrets = collect_bootstrap_secrets(instances=instances, credential_lookup=lookup)
        self.assertEqual(calls, ["pypi:internal"])
        self.assertEqual(set(secrets.index_credentials), {"pypi:internal"})
        return


class EmbeddingTests(unittest.TestCase):

    def test_embed_percent_encodes_and_keeps_port_and_path(self) -> None:
        url = embed_index_credential(
            url="https://pypi.internal:8443/simple/?x=1",
            credential=IndexCredential(username="svc@corp", secret="p@ss:w/rd"))
        self.assertEqual(url, "https://svc%40corp:p%40ss%3Aw%2Frd@pypi.internal:8443/simple/?x=1")
        return

    def test_pip_config_embeds_credential_on_index_host_only(self) -> None:
        spec = _spec(extra_index_urls=["https://pypi.internal/extra/simple",
                                       "https://other.example/simple"])
        text = render_pip_config(spec=spec, credential=IndexCredential("svc", "pw"))
        self.assertEqual(
            text,
            "[global]\n"
            "index-url = https://svc:pw@pypi.internal/simple\n"
            "extra-index-url =\n"
            "    https://svc:pw@pypi.internal/extra/simple\n"
            "    https://other.example/simple\n",
        )
        return

    def test_pip_config_without_credential_is_unchanged(self) -> None:
        text = render_pip_config(spec=_spec())
        self.assertEqual(text, "[global]\nindex-url = https://pypi.internal/simple\n")
        return


class RendererSecretFlowTests(unittest.TestCase):

    def test_secret_lands_only_in_the_0400_pip_conf(self) -> None:
        doc = render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu",
                                           secrets=_secrets(secret="s3cret"))
        dumped = yaml.safe_dump(doc)
        self.assertEqual(dumped.count("s3cret"), 1)
        conf = [w for w in doc["write_files"] if w["path"].endswith(".pip.conf")][0]
        self.assertIn("https://svc:s3cret@pypi.internal/simple", conf["content"])
        self.assertEqual(conf["permissions"], "0400")
        self.assertNotIn("s3cret", render_bootstrap_script(spec=_spec()))
        self.assertNotIn("s3cret", str(doc["runcmd"]))
        return

    def test_missing_secret_raises_instead_of_rendering_unauthenticated(self) -> None:
        with self.assertRaises(CloudInitRendererError) as caught:
            render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu")
        self.assertIn("credential_lookup", str(caught.exception))
        with self.assertRaises(CloudInitRendererError):
            render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu",
                                         secrets=BootstrapSecrets())
        return

    def test_ambient_secrets_are_used_when_none_passed(self) -> None:
        with bind_bootstrap_secrets(_secrets(secret="ambient")):
            doc = render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu")
        self.assertIn("ambient", doc["write_files"][0]["content"])
        return

    def test_explicit_secrets_win_over_ambient(self) -> None:
        with bind_bootstrap_secrets(_secrets(secret="ambient")):
            doc = render_python_env_cloud_init(specs=[_spec()], image_family="ubuntu",
                                               secrets=_secrets(secret="explicit"))
        self.assertIn("explicit", doc["write_files"][0]["content"])
        self.assertNotIn("ambient", doc["write_files"][0]["content"])
        return

    def test_spec_without_credential_needs_no_secrets(self) -> None:
        doc = render_python_env_cloud_init(specs=[_spec(index_credential=None)],
                                           image_family="ubuntu")
        self.assertIn("index-url = https://pypi.internal/simple", doc["write_files"][0]["content"])
        return


class ComposerSecretFlowTests(unittest.TestCase):

    def test_composer_passes_explicit_and_ambient_secrets(self) -> None:
        instance = _instance(python_environments=[_spec()])
        explicit = render_instance_user_data(instance=instance, secrets=_secrets(secret="explicit"))
        self.assertIn("explicit", explicit)
        with bind_bootstrap_secrets(_secrets(secret="ambient")):
            ambient = render_instance_user_data(instance=instance)
        self.assertIn("ambient", ambient)
        return

    def test_composer_raises_without_secrets_for_credentialed_index(self) -> None:
        with self.assertRaises(CloudInitRendererError):
            render_instance_user_data(instance=_instance(python_environments=[_spec()]))
        return


if __name__ == "__main__":
    unittest.main()
