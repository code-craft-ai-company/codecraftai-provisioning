"""
    .. module:: test_exceptions
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Tests for the provisioning model exception hierarchy.

    .. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2026, Code Craft AI LLC"
__credits__ = []


import unittest

from ccai.errors.exceptions import SemanticError
from ccai.interfaces.schemasemanticerror import SchemaSemanticError
from ccai.interfaces.schemavalidationerror import SchemaValidationError


class SchemaSemanticErrorHierarchyTests(unittest.TestCase):
    """
        PC-H7 / Cross-cutting #2 regression: SchemaSemanticError must derive
        from the rooted SemanticError so an ordinary broad ``except`` cannot
        silently swallow it.
    """

    def test_schema_semantic_error_is_a_semantic_error(self) -> None:
        """
            SchemaSemanticError derives from ccai SemanticError.
        """
        self.assertTrue(issubclass(SchemaSemanticError, SemanticError))
        return

    def test_schema_semantic_error_is_not_an_exception(self) -> None:
        """
            SchemaSemanticError is NOT an Exception subclass, so a bare
            ``except Exception`` cannot catch it.
        """
        self.assertFalse(issubclass(SchemaSemanticError, Exception))
        self.assertFalse(issubclass(SchemaSemanticError, RuntimeError))
        return

    def test_except_exception_does_not_swallow_it(self) -> None:
        """
            A bare ``except Exception`` lets SchemaSemanticError bubble.
        """
        caught_by_exception = False
        bubbled = False
        try:
            try:
                raise SchemaSemanticError("semantic failure")
            except Exception:  # noqa: BLE001
                caught_by_exception = True
        except SchemaSemanticError:
            bubbled = True

        self.assertFalse(caught_by_exception)
        self.assertTrue(bubbled)
        return

    def test_except_runtimeerror_does_not_swallow_it(self) -> None:
        """
            A bare ``except RuntimeError`` lets SchemaSemanticError bubble.
        """
        caught_by_runtimeerror = False
        bubbled = False
        try:
            try:
                raise SchemaSemanticError("semantic failure")
            except RuntimeError:
                caught_by_runtimeerror = True
        except SchemaSemanticError:
            bubbled = True

        self.assertFalse(caught_by_runtimeerror)
        self.assertTrue(bubbled)
        return

    def test_schema_validation_error_is_still_a_value_error(self) -> None:
        """
            SchemaValidationError remains a catchable shape-validation error.
        """
        self.assertTrue(issubclass(SchemaValidationError, ValueError))
        self.assertTrue(issubclass(SchemaValidationError, Exception))
        return


if __name__ == "__main__":
    unittest.main()
