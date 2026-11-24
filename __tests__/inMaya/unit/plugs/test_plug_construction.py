"""``Plug(node, mplug)`` の構築と、名前からPlugを求めるときの誤りのテスト。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib
from mlib.plugs.plug import MissingAttributeError


class PlugConstructionTest(NamespaceCase):
    """Plug(node, mplug)。"""

    PREFIX = "mlibPlugConstruction_"

    def test_subclass_constructor(self):
        """具体的なPlugのクラスを直接呼んでも、同じアトリビュートを指すPlugになる。"""
        node = mlib.getNode(self.make("transform", "node#"))
        cmds.addAttr(node.getName(full=True), longName="extraValue", attributeType="double")
        for name in ("tx", "extraValue"):
            with self.subTest(name=name):
                plug = node.getPlug(name)
                built = type(plug)(node, plug.mplug())
                self.assertIs(type(built), type(plug))
                self.assertEqual(built, plug)
                self.assertEqual(built.getName(full=True), cmds.ls(plug.getName(full=True))[0])
                built.set(2.5)
                self.assertEqual(cmds.getAttr(plug.getName(full=True)), 2.5)

    def test_deleted_node_and_attribute(self):
        """削除したノード・アトリビュートのMPlugからはPlugを作らずRuntimeError。"""
        name = self.make("transform", "node#")
        node = mlib.getNode(name)
        cmds.addAttr(name, longName="extraValue", attributeType="double")
        dynamic = node.getPlug("extraValue").mplug()
        cmds.deleteAttr(name + ".extraValue")
        with self.assertRaises(RuntimeError):
            mlib.Plug(node, dynamic)
        static = node.getPlug("tx").mplug()
        cmds.delete(name)
        with self.assertRaises(RuntimeError):
            mlib.Plug(node, static)


class PlugResolveNameTest(NamespaceCase):
    """名前からPlugを求めるときの誤り。"""

    PREFIX = "mlibPlugResolve_"

    def test_component_name(self):
        """頂点の名前はアトリビュートでないのでTypeError。transformの名前のpntsはシェイプのアトリビュートになる。"""
        cube = cmds.polyCube(name=self.name("cube"))[0]
        shape = cmds.listRelatives(cube, shapes=True, fullPath=True)[0]
        with self.assertRaises(TypeError):
            mlib.getPlug(cube + ".vtx[0]")
        with self.assertRaises(TypeError):
            mlib.getPlug(shape + ".pnts[0][1]")
        with self.assertRaises(MissingAttributeError):
            mlib.getPlug(cube + ".pnts[0].notAttribute")
        child = mlib.getPlug(cube + ".pnts[0].px")
        self.assertEqual(child.getName(full=True), cmds.ls(shape + ".pnts[0].pntx")[0])
        self.assertEqual(child.getNode().getName(full=True), shape)

    def test_not_unique(self):
        """同じ名前のノードが2つあれば、アトリビュートの名前は一意でなくRuntimeError。無いアトリビュートはMissingAttributeError。"""
        groups = [self.make("transform", "group#") for _ in range(2)]
        for group in groups:
            cmds.createNode("transform", name=self.ns + ":sameName", parent=group)
        name = self.ns + ":sameName"
        self.assertEqual(len(cmds.ls(name + ".tx")), 2)
        with self.assertRaises(RuntimeError) as context:
            mlib.getPlug(name + ".tx")
        self.assertNotIsInstance(context.exception, MissingAttributeError)
        with self.assertRaises(MissingAttributeError):
            mlib.getPlug(name + ".notAttribute")
        path = cmds.ls(name, long=True)[0]
        self.assertEqual(cmds.ls(mlib.getPlug(path + ".tx").getName(full=True), long=True), [path + ".translateX"])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
