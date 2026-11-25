"""``mlib.cmds.findCycles`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class FindCyclesTest(NamespaceCase):
    """cycleCheckの経路を、経路ごとのPlugsで返す。"""

    PREFIX = "mlibFindCycles_"

    def setUp(self):
        super().setUp()
        self.a = cmds.createNode("transform", name=f"{self.ns}:a")
        self.b = cmds.createNode("transform", name=f"{self.ns}:b")
        self.c = cmds.createNode("transform", name=f"{self.ns}:c")
        cmds.connectAttr(f"{self.a}.tx", f"{self.b}.tx")
        cmds.connectAttr(f"{self.b}.tx", f"{self.a}.tx")

    def names(self, path):
        return {plug.getName(full=True) for plug in path}

    def test_targets_match_cycle_check(self):
        paths = mlib.findCycles(self.a)
        self.assertEqual(len(paths), 1)
        self.assertIsInstance(paths[0], mlib.Plugs)
        expected = cmds.cycleCheck(self.a, list=True, secondary=True)
        self.assertEqual(self.names(paths[0]), {mlib.getPlug(name).getName(full=True) for name in expected})
        self.assertEqual(mlib.findCycles([mlib.getNode(self.a)]), paths)

    def test_whole_scene_contains_cycle(self):
        paths = mlib.findCycles(timeLimit=10.0)
        own = {mlib.getPlug(f"{self.a}.tx").getName(full=True), mlib.getPlug(f"{self.b}.tx").getName(full=True)}
        self.assertTrue(any(own <= self.names(path) for path in paths))

    def test_several_paths_are_separated(self):
        d = cmds.createNode("transform", name=f"{self.ns}:d")
        cmds.connectAttr(f"{self.c}.ty", f"{d}.ty")
        cmds.connectAttr(f"{d}.ty", f"{self.c}.ty")
        paths = mlib.findCycles([self.a, self.c])
        self.assertEqual(len(paths), 2)
        self.assertTrue(all(len(path) == 2 for path in paths))

    def test_no_cycle(self):
        self.assertEqual(mlib.findCycles(self.c), [])
        self.assertEqual(mlib.findCycles(mlib.getPlug(f"{self.c}.tx"), dag=True, firstOnly=True), [])

    def test_scene_is_not_changed(self):
        before = cmds.ls(f"{self.ns}:*")
        cmds.flushUndo()
        mlib.findCycles(self.a, dag=True)
        self.assertEqual(cmds.ls(f"{self.ns}:*"), before)
        self.assertFalse(cmds.undoInfo(query=True, undoName=True))

    def test_invalid(self):
        for args, kwargs, error in (
            (([],), {}, ValueError),
            (([1],), {}, TypeError),
            ((self.a,), {"dag": 1}, TypeError),
            ((self.a,), {"firstOnly": None}, TypeError),
            ((self.a,), {"timeLimit": "10"}, TypeError),
            ((self.a,), {"timeLimit": True}, TypeError),
            ((self.a,), {"timeLimit": 0}, ValueError),
            ((self.a,), {"timeLimit": float("inf")}, ValueError),
        ):
            with self.subTest(args=args, kwargs=kwargs), self.assertRaises(error):
                mlib.findCycles(*args, **kwargs)

    def test_missing_name_raises_runtime_error(self):
        with self.assertRaisesRegex(RuntimeError, "ノードが見つかりません"):
            mlib.findCycles([self.name("noSuchNode")])

    def test_deleted_node_is_refused(self):
        node = mlib.getNode(self.c)
        cmds.delete(self.c)
        with self.assertRaises(ValueError):
            mlib.findCycles([node])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
