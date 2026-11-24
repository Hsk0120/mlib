"""``mlib.cmds.createNode`` のシェーディングノードの分類の指定(asShaderなど)のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class CreateNodeShadingTest(NamespaceCase):
    """mlib.createNode の asShader などの指定。"""

    PREFIX = "mlibCreateNodeShading_"

    def test_registers_like_shading_node(self):
        """cmds.shadingNode と同じ既定のリストへつなぎ、型に合ったクラスで返す。"""
        for flag, node_type, listing in (
            ("asShader", "blinn", "defaultShaderList1"),
            ("asTexture", "checker", "defaultTextureList1"),
            ("asUtility", "multiplyDivide", "defaultRenderUtilityList1"),
        ):
            with self.subTest(flag=flag):
                node = mlib.createNode(node_type, name=self.name(node_type), **{flag: True})
                self.assertEqual(node.getType(), node_type)
                self.assertIn(listing, cmds.listConnections(node.getName(full=True), source=False, destination=True) or [])
        plain = mlib.createNode("blinn", name=self.name("plain"))
        self.assertNotIn("defaultShaderList1", cmds.listConnections(plain.getName(full=True), source=False, destination=True) or [])

    def test_undo_once(self):
        """作成はUndo 1回で戻る。"""
        self.flushUndo()
        node = mlib.createNode("lambert", name=self.name("undoMat"), asShader=True)
        name = node.getName(full=True)
        self.assertUndoesInOneStep(lambda: self.assertFalse(cmds.objExists(name)), lambda: self.assertTrue(cmds.objExists(name)))

    def test_errors(self):
        """2つ以上の分類・bool以外・fast・知らない型を、作る前に拒否する。"""
        before = len(cmds.ls())
        cases = [({"asShader": True, "asTexture": True}, TypeError), ({"asShader": 1}, TypeError), ({"asShader": True, "fast": True}, NotImplementedError)]
        for kwargs, error in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                mlib.createNode("blinn", **kwargs)
        with self.assertRaises(RuntimeError):
            mlib.createNode("mlibNoSuchShadingType", asShader=True)
        self.assertEqual(len(cmds.ls()), before)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
