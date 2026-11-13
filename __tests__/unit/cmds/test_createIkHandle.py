"""``mlib.cmds.createIkHandle`` のテスト。

- リグ構築の補助APIの約束を固定する。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.nodes import BlendShape, IkHandle, Joint, Joints, Node
from mlib.plugs import Plug
from support.namespaceCase import NamespaceCase


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecRigBuilders_"
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        # Maya が現在の名前空間へ作るノード(エフェクター・自動カーブ・名前空間を外した鏡映)も片付ける。
        self.existing = set(cmds.ls(long=True))

    def tearDown(self):
        for name in cmds.ls(long=True):
            if (name not in self.existing and cmds.objExists(name) and not cmds.lockNode(name, query=True)[0]
                    and not cmds.objectType(name, isAType="ikSolver")):
                cmds.delete(name)
        super().tearDown()

    def chain(self, *items):
        """(名前, 位置) の並びで、選択を使わずに親子の joint を作る。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(text), position=position) for text, position in items]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def sphere(self, text):
        """構築履歴の無い polySphere の transform を作る。"""
        return cmds.polySphere(name=self.name(text), constructionHistory=False)[0]

    def aliases(self, blend):
        """aliasAttr の照会から、weight のエイリアスを論理番号順に返す。"""
        items = cmds.aliasAttr(str(blend), query=True) or []
        pairs = [(int(target[target.index("[") + 1:-1]), alias)
                 for alias, target in zip(items[::2], items[1::2]) if target.startswith("weight[")]
        return [alias for _index, alias in sorted(pairs)]

    def leaf(self, name):
        """完全パス・名前空間を除いた名前を返す。"""
        return name.split("|")[-1].split(":")[-1]


class IkHandleCreateTest(_SpecCase):
    """IkHandle.create は cmds.ikHandle と同じハンドル・エフェクターを作る。"""

    def setUp(self):
        super().setUp()
        self.j1, self.j2, self.j3 = self.chain(("a", (0, 0, 0)), ("b", (2, 0, -1)), ("c", (4, 0, 0)))

    def test_rp_solver(self):
        """既定は ikRPsolver。エフェクターは end joint の1つ上の子で、getJoints が cmds と一致する。"""
        handle = mlib.createIkHandle(self.j1, self.j3, name=self.name("hdl"))
        self.assertIs(type(handle), IkHandle)
        self.assertEqual(handle.getName(), self.name("hdl"))
        self.assertEqual(cmds.ikHandle(handle.getFullName(), query=True, solver=True), "ikRPsolver")
        effector = handle.getEffector()
        self.assertTrue(effector.isType("ikEffector"))
        self.assertEqual(effector.getParent().getFullName(), self.j2)
        self.assertEqual(effector.getFullName(),
                         cmds.ls(cmds.ikHandle(handle.getFullName(), query=True, endEffector=True), long=True)[0])
        self.assertEqual([j.getFullName() for j in handle.getJoints()],
                         cmds.ls(cmds.ikHandle(handle.getFullName(), query=True, jointList=True), long=True))
        self.assertEqual(handle.getEndJoint(), Joint(self.j3))
        self.assertIsNone(handle.getCurve())

    def test_sc_and_extra_flags(self):
        """ikSCsolver と、Maya の他のフラグ(priority)をそのまま渡せる。"""
        handle = mlib.createIkHandle(self.j1, self.j3, solver="ikSCsolver", priority=3)
        self.assertEqual(cmds.ikHandle(handle.getFullName(), query=True, solver=True), "ikSCsolver")
        self.assertEqual(cmds.ikHandle(handle.getFullName(), query=True, priority=True), 3)

    def test_spline_auto_curve(self):
        """ikSplineSolver で curve を省略すると Maya がカーブを作り、getCurve で取得できる。"""
        handle = mlib.createIkHandle(self.j1, self.j3, solver="ikSplineSolver")
        curve = handle.getCurve()
        self.assertIsNotNone(curve)
        self.assertTrue(curve.getShape().isType("nurbsCurve"))
        self.assertEqual(cmds.ikHandle(handle.getFullName(), query=True, curve=True).split("|")[-1],
                         curve.getShape().getName().split("|")[-1])

    def test_spline_existing_curve(self):
        """既存カーブを指定すると、そのカーブを使い新しいカーブは作らない。"""
        curve = cmds.curve(name=self.name("crv"), degree=3,
                           point=[(0, 0, 0), (1, 0, 0), (3, 0, 0), (4, 0, 0)])
        before = set(cmds.ls(type="nurbsCurve", long=True))
        handle = mlib.createIkHandle(self.j1, self.j3, solver="ikSplineSolver", curve=curve)
        self.assertEqual(set(cmds.ls(type="nurbsCurve", long=True)), before)
        self.assertEqual(handle.getCurve(), Node(curve))

    def test_undo_once(self):
        """作成(ハンドル・エフェクター・Maya が設定する preferredAngle)は Undo 1回で戻る。"""
        # シーンで最初の IK ハンドルが作るソルバーは Undo で消えない(cmds.ikHandle と同じ)ので先に作る。
        warm = self.chain(("w0", (0, 0, 5)), ("w1", (1, 0, 5)))
        mlib.createIkHandle(warm[0], warm[1], solver="ikSCsolver")
        cmds.delete(warm[0])
        # まっすぐな連鎖では Maya が中間 joint の preferredAngle を設定する。
        straight = self.chain(("s0", (0, 0, 0)), ("s1", (0, 1, 0)), ("s2", (0, 2, 0)))
        self.flushUndo()
        before = cmds.getAttr(straight[1] + ".preferredAngle")[0]
        mlib.createIkHandle(straight[0], straight[2], name=self.name("hdl"))

        def unchanged():
            self.assertEqual(cmds.ls(type=("ikHandle", "ikEffector")), [])
            self.assertEqual(cmds.getAttr(straight[1] + ".preferredAngle")[0], before)

        def changed():
            self.assertEqual(len(cmds.ls(type=("ikHandle", "ikEffector"))), 2)
            self.assertNotEqual(cmds.getAttr(straight[1] + ".preferredAngle")[0], before)

        self.assertUndoesInOneStep(unchanged, changed)

    def test_errors(self):
        """不正な引数は作成前に型付きの例外になり、ノードを残さない。"""
        other, = self.chain(("other", (0, 5, 0)))
        cases = [
            (ValueError, dict(startJoint=self.j1, endJoint=self.j3, solver="badSolver")),
            (ValueError, dict(startJoint=self.j1, endJoint=self.j3, curve=self.j1)),
            (ValueError, dict(startJoint=self.j3, endJoint=self.j1)),
            (ValueError, dict(startJoint=self.j1, endJoint=other)),
            (ValueError, dict(startJoint=self.j1, endJoint=self.j3, name="")),
            (TypeError, dict(startJoint=self.j1, endJoint=self.j3, name=1)),
            (TypeError, dict(startJoint=self.j1, endJoint=self.j3, solver="ikSCsolver", sol="ikSCsolver")),
            (TypeError, dict(startJoint=self.j1, endJoint=self.j3, endEffector=self.j3)),
            (TypeError, dict(endJoint=self.j3)),
            (RuntimeError, dict(startJoint=self.name("missing"), endJoint=self.j3)),
        ]
        transform = cmds.createNode("transform", name=self.name("xform"), parent=self.j2, skipSelect=True)
        cases.append((ValueError, dict(startJoint=self.j1, endJoint=transform)))
        for error, flags in cases:
            with self.subTest(flags=flags):
                with self.assertRaises(error):
                    mlib.createIkHandle(**flags)
        self.assertEqual(cmds.ls(type=("ikHandle", "ikEffector")), [])

    def test_get_effector_on_unconnected_handle(self):
        """createNode で作った未接続のハンドルの getEffector は None。"""
        handle = mlib.createNode("ikHandle", name=self.name("bare"))
        self.assertIsNone(handle.getEffector())
        self.assertIsNone(handle.getCurve())


if __name__ == "__main__":
    unittest.main()
