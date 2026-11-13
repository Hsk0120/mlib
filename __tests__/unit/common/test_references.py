"""``mlib.common.references`` のテスト。

- mlib.nodes.reference の Reference と mlib.common.references.listReferences を検証するMaya内テスト。
- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import math
import os
import sys
import tempfile
from unittest import mock
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import (
    CurveFit,
    Deferred,
    DrivenKey,
    LOADED,
    MISSING,
    Namespace,
    Plugin,
    PluginPackage,
    references,
    ScriptJob,
    ScriptJobs,
    Selection,
    SKIPPED,
    undo,
    units,
    Version,
)
from mlib.common.references import createReference, listReferences
from mlib.components import Vertex
from mlib.nodes import Node
from mlib.nodes.reference import Reference
from mlib.plugs import Plug


class CreateReferenceTest(unittest.TestCase):
    """mlib.common.references.createReference による参照の新規作成を検証する。"""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.ref_path = os.path.join(self.tmp_dir, "mlibCreateReferenceTarget.ma")
        helper = cmds.createNode("transform", name="mlibCreateReferenceHelper")
        cmds.select(helper, replace=True)
        cmds.file(self.ref_path, exportSelected=True, type="mayaAscii", force=True)
        cmds.delete(helper)
        cmds.select(clear=True)
        self.created = None

    def tearDown(self):
        if self.created is not None and cmds.objExists(self.created.getName()):
            cmds.file(removeReference=True, referenceNode=self.created.getName())
        if os.path.exists(self.ref_path):
            os.remove(self.ref_path)
        if os.path.isdir(self.tmp_dir):
            os.rmdir(self.tmp_dir)

    def test_creates_reference_under_requested_namespace(self):
        self.created = createReference(self.ref_path, namespace="mlibCreateReferenceNs")
        self.assertIsInstance(self.created, Reference)
        self.assertTrue(self.created.isLoaded())
        self.assertTrue(cmds.objExists("mlibCreateReferenceNs:mlibCreateReferenceHelper"))
        self.assertEqual(self.created.getAssociatedNamespace(), Namespace("mlibCreateReferenceNs"))

    def test_created_reference_is_included_in_list_references(self):
        self.created = createReference(self.ref_path, namespace="mlibCreateReferenceNs2")
        self.assertIn(self.created.getName(), [reference.getName() for reference in listReferences()])

    def test_invalid_path_raises_value_error(self):
        with self.assertRaises(ValueError):
            createReference("")


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class ReferencesSpecTest(unittest.TestCase):
    """references の入力検証と一覧の型を固定する。"""

    def test_list_references_excludes_shared_node(self):
        """listReferencesはsharedReferenceNodeを含めず、Referenceのlistを返す。"""
        from mlib.nodes import Reference

        result = references.listReferences()
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(item, Reference) for item in result))
        self.assertNotIn("sharedReferenceNode", [item.getName() for item in result])
        top = references.listReferences(topLevelOnly=True)
        self.assertTrue(all(item.getParentReference() is None for item in top))

    def test_create_reference_rejects_invalid_path_before_maya(self):
        """空・str/Path以外のpathはMayaへ渡す前にValueError。"""
        with mock.patch.object(cmds, "file", side_effect=AssertionError("file")):
            for path in ("", None, 5):
                with self.assertRaises(ValueError):
                    references.createReference(path)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
