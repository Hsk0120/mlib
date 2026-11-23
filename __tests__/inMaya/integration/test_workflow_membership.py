"""ノードの検索条件とセットの所属を組み合わせて確認する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class MembershipTest(NamespaceCase):
    def test_leaf_name_uniqueness(self):
        left = self.make(text="left")
        right = self.make(text="right")
        a = mlib.Node(self.make(text="ctrl", parent=left))
        self.assertTrue(a.hasUniqueName())
        b = mlib.Node(self.make(text="ctrl", parent=right))
        self.assertFalse(a.hasUniqueName())
        self.assertFalse(b.hasUniqueName())
        cmds.delete(str(b))
        self.assertTrue(a.hasUniqueName())

    def test_animatable_matches_maya_and_retains_selection(self):
        node = mlib.Node(self.make())
        node.tx.setLocked()
        cmds.select(str(node))
        expected = cmds.listAnimatable(str(node)) or []
        selection = cmds.ls(selection=True, long=True)
        actual = node.getPlugs(animatable=True)
        self.assertIsInstance(actual, mlib.Plugs)
        self.assertEqual([mlib.getPlug(name) for name in expected], list(actual))
        self.assertEqual(cmds.ls(selection=True, long=True), selection)
        # animatable=True は、ほかの引数と同時に指定できない(TypeError)。animatable は bool だけ。
        for args, flags in (
            ((True,), {"animatable": True}),
            ((), {"animatable": True, "userDefined": True}),
            ((), {"animatable": True, "includeChildren": False}),
            ((), {"animatable": True, "writable": True}),
            ((), {"animatable": True, "keyable": True}),
            ((), {"animatable": 1}),
            ((False, True, True), {}),
        ):
            with self.subTest(args=args, flags=flags), self.assertRaises(TypeError):
                node.getPlugs(*args, **flags)
        # animatable=False(既定)は今までどおりの一覧で、writable=True はロックしたものを除く。
        self.assertEqual(list(node.getPlugs(animatable=False)), list(node.getPlugs()))
        writable = [plug.getAttributeName() for plug in node.getPlugs(writable=True)]
        self.assertNotIn("translateX", writable)
        self.assertIn("translateY", writable)
        cmds.delete(str(node))
        with self.assertRaises(RuntimeError):
            node.getPlugs(animatable=True)

    def test_nested_set_flatten(self):
        cube = cmds.polyCube(name=self.name("cube"))[0]
        child = mlib.Node(cmds.sets(cube + ".vtx[0:3]", name=self.name("child")))
        parent = mlib.Node(cmds.sets(empty=True, name=self.name("parent")))
        parent.addMembers(child)
        self.assertEqual(parent.getMembers(), [child])
        members = parent.getMembers(flatten=True)
        self.assertEqual(len(members), 1)
        self.assertEqual(tuple(members[0].indices), (0, 1, 2, 3))
        self.assertEqual(parent.getMembers(), [child])

    def test_path_set_components(self):
        cube = cmds.polyCube(name=self.name("cube"))[0]
        shape = mlib.Node(cube).getShape()
        group = mlib.Node(cmds.sets(cube + ".f[1:2]", name=self.name("faces")))
        pairs = shape.getSetsAndMembers()
        match = [members for node, members in pairs if node == group]
        self.assertEqual(len(match), 1)
        self.assertEqual(tuple(match[0][0].indices), (1, 2))
        for node, _members in shape.getSetsAndMembers(renderableOnly=True):
            self.assertTrue(node.isType("shadingEngine"))

    def test_instanced_shape_keeps_each_path_membership(self):
        cube = cmds.polyCube(name=self.name("original"))[0]
        instance = cmds.instance(cube, name=self.name("instance"))[0]
        first = mlib.Node(cube).getShape()
        second = mlib.Node(instance).getShape()
        group = mlib.Node(cmds.sets(empty=True, renderable=True, noSurfaceShader=True, name=self.name("material")))
        cmds.sets(instance + ".f[2:3]", edit=True, forceElement=str(group))
        self.flushUndo()
        self.assertNotIn(group, [node for node, _members in first.getSetsAndMembers(renderableOnly=True)])
        matches = [members for node, members in second.getSetsAndMembers(renderableOnly=True) if node == group]
        self.assertEqual(len(matches), 1)
        self.assertEqual(tuple(matches[0][0].indices), (2, 3))
        self.assertIn(instance, str(matches[0][0]))
        self.assertUndoEmpty()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
