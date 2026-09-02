"""
    .. module:: test_cloudinstance_python_environments
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the python_environments slot on CloudInstance.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from ccai.interfaces.pythonenvspec import PythonEnvironmentSpec
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.interfaces.schemavalidationerror import SchemaValidationError

from ccai.provisioning.model.cloud.cloudimage import CloudImage
from ccai.provisioning.model.cloud.cloudinstance import CloudInstance


def _instance(**overrides) -> CloudInstance:
    kwargs = {
        "name": "agent-01", "profile_ref": "profile",
        "image": CloudImage(family="ubuntu", version="24.04", architecture="x86_64"),
        "size": "general.small", "subnet": "subnet",
    }
    kwargs.update(overrides)
    rtnval = CloudInstance(**kwargs)
    return rtnval


class CloudInstancePythonEnvironmentsTests(unittest.TestCase):

    def test_default_is_none(self) -> None:
        self.assertIsNone(_instance().python_environments)
        return

    def test_accepts_spec_list(self) -> None:
        spec = PythonEnvironmentSpec(path="/opt/venvs/app")
        inst = _instance(python_environments=[spec])
        self.assertEqual(inst.python_environments, [spec])
        return

    def test_rejects_non_spec_entries(self) -> None:
        with self.assertRaises(SchemaValidationError):
            _instance(python_environments=[{"path": "/opt/venvs/app"}])
        return

    def test_rejects_duplicate_paths(self) -> None:
        with self.assertRaises(SchemaSemanticError):
            _instance(python_environments=[
                PythonEnvironmentSpec(path="/opt/venvs/app", name="a"),
                PythonEnvironmentSpec(path="/opt/venvs/app", name="b"),
            ])
        return

    def test_from_dict_promotes_nested_specs(self) -> None:
        inst = _instance(python_environments=[
            PythonEnvironmentSpec(path="/opt/venvs/app", packages=["rich"]),
        ])
        restored = CloudInstance.from_dict(inst.to_dict())
        self.assertEqual(restored.python_environments, inst.python_environments)
        self.assertIsInstance(restored.python_environments[0], PythonEnvironmentSpec)
        return

    def test_from_dict_without_slot_leaves_none(self) -> None:
        restored = CloudInstance.from_dict(_instance().to_dict())
        self.assertIsNone(restored.python_environments)
        return


if __name__ == "__main__":
    unittest.main()
