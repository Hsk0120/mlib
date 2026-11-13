"""全8型と重み付き加算の登録・編集・Undoを検証する。

あわせて次も確かめる。

- DAG・Transform・アニメーションカーブ・DG の照会と編集の契約を固定する。
- デフォーマー・AnimCurve・ObjectSet のメソッドと作成関数を確かめる。
"""

import sys
import unittest
from unittest.mock import patch
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.cmds.bakeResults import bakeResults
from mlib.maths import Matrix
from mlib.nodes import AnimCurve
from support.namespaceCase import NamespaceCase


class AnimationNodesTest(unittest.TestCase):
    def setUp(self):
        self.ns = "mlibAnim_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)

    def tearDown(self):
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def create(self, kind):
        return mlib.createNode(kind, name=self.ns + ":" + kind)

    def test_all_types(self):
        for suffix in ("TA", "TL", "TT", "TU", "UA", "UL", "UT", "UU"):
            with self.subTest(suffix=suffix):
                curve = self.create("animCurve" + suffix)
                self.assertIsInstance(curve, getattr(mlib.nodes, "AnimCurve" + suffix))
                self.assertIsInstance(curve, mlib.AnimCurve)
                for obsolete in ("getDriverPlug", "getOutputPlug", "shiftKeys", "scaleKeys"):
                    self.assertFalse(hasattr(type(curve), obsolete), obsolete)
                curve.setKey(0, 0, "linear", "linear").setKey(10, 20, "linear", "linear")
                self.assertEqual(curve.getKeyInputs(), [0, 10])
                self.assertAlmostEqual(curve.getKeyValues()[1], 20)
                self.assertAlmostEqual(curve.evaluate(5), 10)
                self.assertEqual(curve.getKeyCount(), 2)
                cmds.undo()
                self.assertEqual(curve.getKeyCount(), 1)
                cmds.redo()
                self.assertEqual(curve.getKeyCount(), 2)
                curve.removeKey(1)
                self.assertEqual(curve.getKeyCount(), 1)
                cmds.undo()
                self.assertEqual(curve.getKeyCount(), 2)

    def test_tangents_infinity_and_invalid_input(self):
        curve = self.create("animCurveUU").setKey(0, 0, "linear", "linear").setKey(1, 1, "linear", "linear")
        curve.setTangent(0, outTangentType="flat")
        self.assertEqual(curve.getTangent(0)["outTangentType"], "flat")
        cmds.undo()
        self.assertEqual(curve.getTangent(0)["outTangentType"], "linear")
        curve.setInfinity(pre="cycle", post="linear")
        self.assertEqual(curve.getInfinity(), {"pre": "cycle", "post": "linear"})
        cmds.undo()
        self.assertEqual(curve.getInfinity()["pre"], "constant")
        with self.assertRaises(ValueError):
            curve.setKey(float("nan"), 1)
        with self.assertRaises(IndexError):
            curve.removeKey(5)

    def test_infinity_api_reads_and_fast_updates_all_types(self):
        """全8型で照会・fast更新がcmds非依存で、通常更新と同じ外挿になる。"""
        for suffix in ("TA", "TL", "TT", "TU", "UA", "UL", "UT", "UU"):
            curve = self.create("animCurve" + suffix).setKey(0, 0).setKey(1, 2)
            for mode in ("constant", "linear", "cycle", "cycleRelative", "oscillate"):
                curve.setInfinity(pre=mode, post=mode)
                expected = [curve.evaluate(t) for t in (-.5, 1.5)]
                cmds.undo()
                before = cmds.undoInfo(query=True, undoName=True)
                with patch.object(cmds, "getAttr", side_effect=AssertionError("getAttr")), \
                        patch.object(cmds, "setAttr", side_effect=AssertionError("setAttr")), \
                        patch.object(cmds, "undoInfo", side_effect=AssertionError("undoInfo")):
                    self.assertIs(curve.setInfinity(pre=mode, post=mode, fast=True), curve)
                    self.assertEqual(curve.getInfinity(), dict(pre=mode, post=mode))
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), before)
                for actual, value in zip([curve.evaluate(t) for t in (-.5, 1.5)], expected):
                    self.assertAlmostEqual(actual, value)

    def test_infinity_fast_preflight_and_partial_flags(self):
        """両側を事前検証し、片側省略・不正値・ロック・接続を扱う。"""
        curve = self.create("animCurveUU")
        original = curve.getInfinity()
        cmds.setAttr(curve.getFullName() + ".postInfinity", lock=True)
        with self.assertRaises(RuntimeError):
            curve.setInfinity(pre="cycle", post="linear", fast=True)
        self.assertEqual(curve.getInfinity(), original)
        curve.setInfinity(pre="oscillate", fast=True)
        self.assertEqual(curve.getInfinity(), dict(pre="oscillate", post="constant"))
        cmds.setAttr(curve.getFullName() + ".postInfinity", lock=False)
        source = self.create("animCurveUU")
        cmds.connectAttr(source.getFullName() + ".preInfinity", curve.getFullName() + ".postInfinity")
        with self.assertRaises(RuntimeError):
            curve.setInfinity(pre="linear", post="linear", fast=True)
        self.assertEqual(curve.getInfinity()["pre"], "oscillate")
        with self.assertRaises(ValueError):
            curve.setInfinity(pre="linear", post="invalid", fast=True)
        with self.assertRaises(TypeError):
            curve.setInfinity(pre="linear", fast=1)
        self.assertEqual(curve.getInfinity()["pre"], "oscillate")
        self.assertIs(curve.setInfinity(fast=True), curve)


    def test_standard_plug_queries_keep_direct_conversion_connections(self):
        """入出力の直接接続照会は変換ノードを飛ばさず、Undo履歴を変えない。"""
        curve = self.create("animCurveUU").setKey(0, 0).setKey(1, 1)
        driver = self.create("network").addAttr("driver", defaultValue=0.5)
        driven = self.create("network").addAttr("driven")
        incoming = self.create("unitConversion")
        outgoing = self.create("unitConversion")
        driver.connectTo(incoming.getPlug("input"))
        incoming.getPlug("output").connectTo(curve.getPlug("input"))
        curve.getPlug("output").connectTo(outgoing.getPlug("input"))
        outgoing.getPlug("output").connectTo(driven)
        before = cmds.undoInfo(query=True, undoName=True)

        source = curve.getPlug("input").getSource()
        destinations = curve.getPlug("output").getDestinations()

        self.assertEqual(source, incoming.getPlug("output"))
        self.assertEqual(destinations, [outgoing.getPlug("input")])
        self.assertNotEqual(source, driver)
        self.assertNotIn(driven, destinations)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), before)

    def test_mirror_and_shift_ignore_other_selected_keys(self):
        for kind in ("animCurveTL", "animCurveUU"):
            curve = self.create(kind).setKey(-2, 3).setKey(4, 9)
            other = self.create("animCurveTU").setKey(1, 10)
            cmds.selectKey(other.getFullName(), index=(0, 0))
            curve.mirror(input=True, value=True)
            self.assertEqual(curve.getKeyInputs(), [-4, 2])
            self.assertAlmostEqual(curve.evaluate(-1), -6)
            self.assertEqual(other.getKeyValues(), [10])
            cmds.undo()
            self.assertEqual(curve.getKeyInputs(), [-2, 4])
            cmds.redo()
            self.assertEqual(curve.getKeyInputs(), [-4, 2])
            curve.moveKey(timeOffset=1, valueOffset=2)
            self.assertEqual(curve.getKeyInputs(), [-3, 3])
            self.assertAlmostEqual(curve.evaluate(0), -4)
            cmds.selectKey(clear=True)


def _world(name):
    """cmds で読むワールドマトリクス。"""
    return cmds.xform(name, query=True, worldSpace=True, matrix=True)


class EulerFilterTest(NamespaceCase):

    def keyed(self):
        node = self.make(text="rot")
        for frame, values in ((1, (0, 0, 0)), (2, (350, 10, -340)), (3, (20, 380, 0))):
            for axis, value in zip("XYZ", values):
                cmds.setKeyframe(node, attribute="rotate" + axis, time=frame, value=value)
        return node

    def values(self, node):
        return [cmds.keyframe(node + ".rotate" + axis, query=True, valueChange=True) for axis in "XYZ"]

    def test_transform_matches_filter_curve(self):
        """Transform.eulerFilter は3本を filterCurve に渡したのと同じ結果で、Undo 1回で戻る。"""
        node, reference = self.keyed(), self.keyed()
        before = self.values(node)
        cmds.filterCurve([cmds.listConnections(reference + ".rotate" + axis)[0] for axis in "XYZ"], filter="euler")
        self.flushUndo()
        transform = mlib.getNode(node)
        self.assertIs(transform.eulerFilter(), transform)
        self.assertNotEqual(self.values(node), before)
        for actual, expected in zip(self.values(node), self.values(reference)):
            self.assertSequenceAlmostEqual(actual, expected)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.values(node), before), lambda: None)

    def test_transform_without_keys(self):
        """キーが無ければ何もしないで自身を返す。"""
        transform = mlib.getNode(self.make())
        self.flushUndo()
        self.assertIs(transform.eulerFilter(), transform)
        self.assertUndoEmpty()

    def test_anim_curve(self):
        """AnimCurve.eulerFilter は animCurveTA だけを受け、Undo 1回で戻る。"""
        node = self.keyed()
        curve = mlib.getNode(cmds.listConnections(node + ".rotateX")[0])
        before = self.values(node)[0]
        self.flushUndo()
        self.assertIs(curve.eulerFilter(), curve)
        self.assertNotEqual(self.values(node)[0], before)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.values(node)[0], before), lambda: None)
        cmds.setKeyframe(node, attribute="translateX", time=1, value=1)
        linear = mlib.getNode(cmds.listConnections(node + ".translateX")[0])
        self.assertRaises(TypeError, linear.eulerFilter)


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibDeformAdd_"

    def cube(self, subdivisionsY=1):
        """1辺2cm の polyCube を作り、(transform 名, shape 名) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, subdivisionsY=subdivisionsY,
                                  constructionHistory=False)[0]
        transform = cmds.ls(transform, long=True)[0]
        return transform, cmds.listRelatives(transform, shapes=True, fullPath=True)[0]

    def skinned(self):
        """2段の cube を2本の joint へバインドし、(skin, mesh 名, joints, 未登録 joint) を返す。"""
        mesh, _ = self.cube(subdivisionsY=2)
        cmds.select(clear=True)
        j0 = cmds.joint(name=self.name("j0"), position=(0, -1, 0))
        j1 = cmds.joint(name=self.name("j1"), position=(0, 1, 0))
        cmds.select(clear=True)
        stranger = cmds.joint(name=self.name("stranger"))
        cmds.select(clear=True)
        name = cmds.skinCluster(j0, j1, mesh, toSelectedBones=True, name=self.name("skin"))[0]
        cmds.select(clear=True)
        return mlib.getNode(name), mesh, (j0, j1), stranger

    def keyed(self):
        """translateX の frame 1 に 0、frame 10 に 5 のキーを打ったカーブを返す。"""
        node = self.make("transform", "keyed#")
        cmds.setKeyframe(node, attribute="translateX", time=1, value=0.0)
        cmds.setKeyframe(node, attribute="translateX", time=10, value=5.0)
        return mlib.getNode(cmds.listConnections(node + ".tx", type="animCurve")[0])


class AnimCurveTest(_Case):
    """AnimCurve と Keyframe の追加メソッド。"""

    def test_insert_key_keeps_shape(self):
        """insertKey は評価値を変えずにキーを足し、Undo 1回で戻る。"""
        curve = self.keyed()
        value = curve.evaluate(4)
        self.flushUndo()
        self.assertIs(curve.insertKey(4), curve)
        self.assertUndoesInOneStep(lambda: self.assertEqual(curve.getKeyInputs(), [1.0, 10.0]),
                                   lambda: self.assertEqual(curve.getKeyInputs(), [1.0, 4.0, 10.0]))
        cmds.redo()
        self.assertAlmostEqual(curve.getKeyValues()[1], value)
        self.assertAlmostEqual(curve.evaluate(4), value)

    def test_insert_key_seconds_and_invalid(self):
        """timeUnit="sec" の入力と、不正な入力・空のカーブ。"""
        curve = self.keyed()
        fps = {"film": 24.0, "ntsc": 30.0, "pal": 25.0}[cmds.currentUnit(query=True, time=True)]
        curve.insertKey(7.0 / fps, timeUnit="sec")
        self.assertEqual([round(value, 6) for value in curve.getKeyInputs()], [1.0, 7.0, 10.0])
        for args, kwargs, error in (((float("inf"),), {}, ValueError), (("a",), {}, ValueError),
                                    ((None,), {}, TypeError), ((5,), {"timeUnit": "week"}, ValueError)):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    curve.insertKey(*args, **kwargs)
        empty = mlib.getNode(self.make("animCurveTL", "empty#"))
        with self.assertRaises(RuntimeError):
            empty.insertKey(3)

    def test_find_closest_index(self):
        """findClosestIndex は最も近いキーの番号。"""
        curve = self.keyed()
        for value, expected in ((-5, 0), (3, 0), (8, 1), (100, 1)):
            with self.subTest(value=value):
                self.assertEqual(curve.findClosestIndex(value), expected)
        empty = mlib.getNode(self.make("animCurveTL", "empty#"))
        with self.assertRaises(RuntimeError):
            empty.findClosestIndex(1)
        with self.assertRaises(ValueError):
            curve.findClosestIndex(float("nan"))

    def test_breakdown(self):
        """setBreakdown は keyframe -q -breakdown と一致し、Undo 1回で戻る。Keyframe からも使える。"""
        curve = self.keyed()
        curve.insertKey(5)
        name = curve.getFullName()

        def queried():
            return cmds.keyframe(name, query=True, breakdown=True) or []
        self.assertEqual([curve.isBreakdown(i) for i in range(3)], [False, False, False])
        self.flushUndo()
        self.assertIs(curve.setBreakdown(1), curve)
        self.assertUndoesInOneStep(lambda: self.assertEqual(queried(), []),
                                   lambda: self.assertEqual(queried(), [5.0]))
        key = curve.getKeyframe(1)
        self.assertIs(key.setBreakdown(), key)
        self.assertTrue(key.isBreakdown())
        self.assertEqual([curve.isBreakdown(i) for i in range(3)], [False, True, False])
        key.setBreakdown(False)
        self.assertFalse(key.isBreakdown())
        curve.setBreakdown([0, 2])
        self.assertEqual(queried(), [1.0, 10.0])
        for args, error in (((5,), IndexError), ((1, "yes"), TypeError), ((None,), TypeError)):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    curve.setBreakdown(*args)
        with self.assertRaises(IndexError):
            curve.isBreakdown(3)
        cmds.delete(name)
        with self.assertRaises(RuntimeError):
            curve.isBreakdown(0)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
