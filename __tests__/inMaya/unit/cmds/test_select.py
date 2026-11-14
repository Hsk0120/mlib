"""``mlib.cmds.select`` のテスト。

- mlib.cmds の7入口(getNode・getPlug・createNode・ls・delete・duplicate・select)の仕様テスト(担当D)。
- 名前空間・選択・matchTransform の通常経路と、om2 へ置き換えた読み取りを cmds と突き合わせる。
"""

import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.common.selection import Selection
from mlib.components import Vertices


class _CmdsCase(unittest.TestCase):
    """一時名前空間・選択・Undo設定の保存と復元を共通にする。"""

    def setUp(self):
        """一時名前空間を作り、選択とUndo設定を保存する。"""
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.selection = cmds.ls(selection=True, long=True)
        self.ns = "mlibSpecDCmds_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)

    def tearDown(self):
        """一時名前空間を中身ごと削除し、選択とUndo設定を戻す。"""
        cmds.select(clear=True)
        if cmds.namespace(exists=self.ns):
            for node in cmds.ls(self.ns + ":*", long=True) or []:
                if cmds.objExists(node) and cmds.lockNode(node, query=True, lock=True)[0]:
                    cmds.lockNode(node, lock=False)
            cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        existing = [name for name in self.selection if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)
        cmds.undoInfo(state=self.undo_state)

    def name(self, leaf):
        """一時名前空間内の名前を返す。"""
        return self.ns + ":" + leaf

    def transforms(self):
        """一時名前空間内のtransformの数を返す。"""
        return len(cmds.ls(self.ns + ":*", type="transform") or [])


class SelectSpecTest(_CmdsCase):
    """selectのフラグ・cmds.selectとの一致・Undoを固定する。"""

    def setUp(self):
        """選択対象を作る。"""
        super().setUp()
        self.a = cmds.createNode("transform", name=self.name("a"))
        self.b = cmds.createNode("transform", name=self.name("b"))
        self.cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]

    def selected(self):
        """現在の選択を平坦化した名前で返す。"""
        return cmds.ls(selection=True, flatten=True)

    def test_matches_cmds_select(self):
        """同じ対象・フラグでcmds.selectと同じ選択結果になり、Noneを返す。"""
        cases = [
            ((self.a,), {}),
            (([self.a, self.b],), dict(add=True)),
            ((self.a,), dict(d=True)),
            ((self.a,), dict(tgl=True)),
            ((), dict(cl=True)),
            (([],), {}),
            ((self.cube + ".vtx[0:3]",), dict(r=True)),
        ]
        for args, kwargs in cases:
            cmds.select(self.b, replace=True)
            cmds.select(*args, **kwargs)
            expected = self.selected()
            cmds.select(self.b, replace=True)
            self.assertIsNone(mlib.select(*args, **kwargs))
            self.assertEqual(self.selected(), expected, msg=repr((args, kwargs)))

    def test_wrappers_and_collections(self):
        """Node・Plug・Componentsを名前へ変換して選択する。"""
        shape = mlib.getNode(cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0])
        mlib.select([mlib.getNode(self.a), Vertices(shape, [0, 1, 2])])
        self.assertEqual(len(self.selected()), 4)
        mlib.select(clear=True)
        self.assertEqual(self.selected(), [])

    def test_conflicts_and_undo(self):
        """長短名の同時指定はTypeErrorで選択を変えず、通常の選択は1回のUndoで戻る。"""
        cmds.select(self.a, replace=True)
        for kwargs in (
            dict(clear=True, cl=True),
            dict(replace=True, r=True),
            dict(deselect=True, d=True),
            dict(toggle=True, tgl=True),
            dict(hierarchy=True, hi=True),
            dict(noExpand=True, ne=True),
        ):
            with self.assertRaises(TypeError, msg=repr(kwargs)):
                mlib.select(self.b, **kwargs)
        self.assertEqual(self.selected(), [self.a])
        mlib.select(self.b)
        self.assertEqual(self.selected(), [self.b])
        cmds.undo()
        self.assertEqual(self.selected(), [self.a])
        with self.assertRaises(ValueError):
            mlib.select([""])
        with self.assertRaises(TypeError):
            mlib.select([5])


class _CommonCase(NamespaceCase):
    PREFIX = "mlibSpecCommonEdits_"

    def setUp(self):
        super().setUp()
        self.current = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        self.relative = cmds.namespace(query=True, relativeNames=True)
        self.selection = cmds.ls(selection=True, long=True)
        cmds.select(clear=True)

    def tearDown(self):
        cmds.namespace(relativeNames=self.relative)
        cmds.namespace(set=self.current if cmds.namespace(exists=self.current) else ":")
        if self.selection:
            cmds.select(self.selection, replace=True)
        else:
            cmds.select(clear=True)
        super().tearDown()

    def namespaces(self, root):
        """root 配下の名前空間を root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyNamespaces=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root) :] for name in names)

    def nodes(self, root):
        """root 配下のノードを root からの相対名で返す。"""
        names = cmds.namespaceInfo(root, listOnlyDependencyNodes=True, recurse=True, absoluteName=True) or []
        return sorted(name[len(root) :] for name in names)


class SelectTest(_CommonCase):
    def setUp(self):
        super().setUp()
        self.cube = cmds.polyCube(name=self.name("cube"))[0]
        self.sphere = cmds.polySphere(name=self.name("sphere"))[0]
        self.curve = cmds.curve(name=self.name("curve"), degree=1, point=[(0, 0, 0), (1, 0, 0), (2, 0, 0)])
        self.set = cmds.sets(self.cube, self.sphere, name=self.name("set"))
        cmds.select(clear=True)

    def state(self):
        return cmds.ls(selection=True), cmds.ls(orderedSelection=True)

    def n(self, text):
        return self.ns + ":" + text

    def test_errors_match(self):
        """存在しない名前は ValueError で、選択を変えない。"""
        cmds.select(self.sphere)
        with self.assertRaises(ValueError):
            mlib.select([self.cube, self.n("missing")])
        self.assertEqual(cmds.ls(selection=True), [self.sphere])

    def test_normal_undo_once(self):
        """Undo 1 回で元の選択に戻る。"""
        cmds.select(self.sphere)
        mlib.select([self.cube + ".vtx[1]", self.curve])
        cmds.undo()
        self.assertEqual(cmds.ls(selection=True), [self.sphere])

    def test_selection_select(self):
        """Selection.select の各 mode は、cmds.select(noExpand=True) と同じ選択になる。"""
        names = [self.cube + ".vtx[3]", self.sphere, self.cube + ".vtx[1]", self.cube + ".vtx[2]", self.set]
        selection = Selection(names)
        base = [self.curve, self.cube + ".vtx[2]"]
        for mode, flag in (("replace", "replace"), ("add", "add"), ("remove", "deselect")):
            with self.subTest(mode=mode):
                cmds.select(base)
                cmds.select([item.getFullName() for item in selection], noExpand=True, **{flag: True})
                expected = self.state()
                cmds.select(base)
                self.assertIs(selection.select(mode), selection)
                self.assertEqual(self.state(), expected)
        cmds.select(self.curve)
        Selection().select()
        self.assertEqual(cmds.ls(selection=True), [])

    def test_exists_matches_obj_exists(self):
        """選択の存在確認(core.object._exists)は cmds.objExists と同じ結果になる。"""
        from mlib.core.object import _exists

        shape = cmds.listRelatives(self.cube, shapes=True, fullPath=True)[0]
        curve_shape = cmds.listRelatives(self.curve, shapes=True, fullPath=True)[0]
        node = cmds.ls(self.make(), long=True)[0]
        cmds.addAttr(node, longName="arr", multi=True)
        cmds.setAttr(node + ".arr[2]", 1)
        names = [
            shape + ".vtx[7]",
            shape + ".vtx[100]",
            shape + ".e[11]",
            shape + ".f[6]",
            shape + ".map[400]",
            curve_shape + ".cv[2]",
            curve_shape + ".cv[50]",
            node + ".tx",
            node + ".nope",
            node + ".arr[2]",
            node + ".arr[5]",
            node + ".worldMatrix[3]",
            node,
            node + "|nope",
            "|" + self.ns + ":missing",
        ]
        for name in names:
            with self.subTest(name=name):
                self.assertEqual(_exists(name), cmds.objExists(name))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
