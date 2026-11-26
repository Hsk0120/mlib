"""全8型と重み付き加算の登録・編集・Undoを検証する。

あわせて次も確かめる。

- DAG・Transform・アニメーションカーブ・DG の照会と編集の契約を固定する。
- デフォーマー・AnimCurve・ObjectSet のメソッドと作成関数を確かめる。
"""

import sys
import unittest
import uuid
from unittest.mock import patch

import maya.cmds as cmds

import mlib

mlib.reload()

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
                curve.addKey(0, 0, "linear", "linear")
                curve.addKey(10, 20, "linear", "linear")
                self.assertEqual(curve.getKeyInputs(), [0, 10])
                self.assertAlmostEqual(curve.getKeyValues()[1], 20)
                self.assertAlmostEqual(curve.evaluate(5), 10)
                self.assertEqual(curve.getKeyCount(), 2)
                cmds.undo()
                self.assertEqual(curve.getKeyCount(), 1)
                cmds.redo()
                self.assertEqual(curve.getKeyCount(), 2)
                curve.getKeyframes(1).delete()
                self.assertEqual(curve.getKeyCount(), 1)
                cmds.undo()
                self.assertEqual(curve.getKeyCount(), 2)

    def test_tangents_infinity_and_invalid_input(self):
        curve = self.create("animCurveUU")
        curve.addKey(0, 0, "linear", "linear")
        curve.addKey(1, 1, "linear", "linear")
        curve.getKeyframes(0).setTangent(outTangentType="flat")
        self.assertEqual(curve.getKeyframes(0).getTangent()["outTangentType"], "flat")
        cmds.undo()
        self.assertEqual(curve.getKeyframes(0).getTangent()["outTangentType"], "linear")
        curve.setInfinity(pre="cycle", post="linear")
        self.assertEqual(curve.getInfinity(), {"pre": "cycle", "post": "linear"})
        cmds.undo()
        self.assertEqual(curve.getInfinity()["pre"], "constant")
        with self.assertRaises(ValueError):
            curve.addKey(float("nan"), 1)
        with self.assertRaises(IndexError):
            curve.getKeyframes(5).delete()

    def test_infinity_api_reads_and_fast_updates_all_types(self):
        """全8型で照会・fast更新がcmds非依存で、通常更新と同じ外挿になる。"""
        for suffix in ("TA", "TL", "TT", "TU", "UA", "UL", "UT", "UU"):
            curve = self.create("animCurve" + suffix)
            curve.addKey(0, 0)
            curve.addKey(1, 2)
            for mode in ("constant", "linear", "cycle", "cycleRelative", "oscillate"):
                curve.setInfinity(pre=mode, post=mode)
                expected = [curve.evaluate(t) for t in (-0.5, 1.5)]
                cmds.undo()
                before = cmds.undoInfo(query=True, undoName=True)
                with patch.object(cmds, "getAttr", side_effect=AssertionError("getAttr")), patch.object(
                    cmds, "setAttr", side_effect=AssertionError("setAttr")
                ), patch.object(cmds, "undoInfo", side_effect=AssertionError("undoInfo")):
                    self.assertIsNone(curve.setInfinity(pre=mode, post=mode, fast=True))
                    self.assertEqual(curve.getInfinity(), dict(pre=mode, post=mode))
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), before)
                for actual, value in zip([curve.evaluate(t) for t in (-0.5, 1.5)], expected):
                    self.assertAlmostEqual(actual, value)

    def test_infinity_fast_preflight_and_partial_flags(self):
        """両側を事前検証し、片側省略・不正値・ロック・接続を扱う。"""
        curve = self.create("animCurveUU")
        original = curve.getInfinity()
        cmds.setAttr(curve.getName(full=True) + ".postInfinity", lock=True)
        with self.assertRaises(RuntimeError):
            curve.setInfinity(pre="cycle", post="linear", fast=True, check=True)
        self.assertEqual(curve.getInfinity(), original)
        curve.setInfinity(pre="oscillate", fast=True)
        self.assertEqual(curve.getInfinity(), dict(pre="oscillate", post="constant"))
        cmds.setAttr(curve.getName(full=True) + ".postInfinity", lock=False)
        source = self.create("animCurveUU")
        cmds.connectAttr(source.getName(full=True) + ".preInfinity", curve.getName(full=True) + ".postInfinity")
        with self.assertRaises(RuntimeError):
            curve.setInfinity(pre="linear", post="linear", fast=True, check=True)
        self.assertEqual(curve.getInfinity()["pre"], "oscillate")
        with self.assertRaises(ValueError):
            curve.setInfinity(pre="linear", post="invalid", fast=True)
        with self.assertRaises(TypeError):
            curve.setInfinity(pre="linear", fast=1)
        self.assertEqual(curve.getInfinity()["pre"], "oscillate")
        self.assertIsNone(curve.setInfinity(fast=True))

    def test_standard_plug_queries_keep_direct_conversion_connections(self):
        """入出力の直接接続照会は変換ノードを飛ばさず、Undo履歴を変えない。"""
        curve = self.create("animCurveUU")
        curve.addKey(0, 0)
        curve.addKey(1, 1)
        driver = self.create("network").addAttr("driver", defaultValue=0.5)
        driven = self.create("network").addAttr("driven")
        incoming = self.create("unitConversion")
        outgoing = self.create("unitConversion")
        driver.connectTo(incoming.getPlug("input"))
        incoming.getPlug("output").connectTo(curve.getPlug("input"))
        curve.getPlug("output").connectTo(outgoing.getPlug("input"))
        outgoing.getPlug("output").connectTo(driven)
        before = cmds.undoInfo(query=True, undoName=True)

        source = curve.getPlug("input").getConnections(input=True)
        destinations = curve.getPlug("output").getConnections(output=True)

        self.assertEqual(source, incoming.getPlug("output"))
        self.assertEqual(destinations, [outgoing.getPlug("input")])
        self.assertNotEqual(source, driver)
        self.assertNotIn(driven, destinations)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), before)

    def test_mirror_and_shift_ignore_other_selected_keys(self):
        for kind in ("animCurveTL", "animCurveUU"):
            curve = self.create(kind)
            curve.addKey(-2, 3)
            curve.addKey(4, 9)
            other = self.create("animCurveTU")
            other.addKey(1, 10)
            cmds.selectKey(other.getName(full=True), index=(0, 0))
            curve.scaleKey(-1, -1)
            self.assertEqual(curve.getKeyInputs(), [-4, 2])
            self.assertAlmostEqual(curve.evaluate(-1), -6)
            self.assertEqual(other.getKeyValues(), [10])
            cmds.undo()
            self.assertEqual(curve.getKeyInputs(), [-2, 4])
            cmds.redo()
            self.assertEqual(curve.getKeyInputs(), [-4, 2])
            curve.getKeyframes().move(timeOffset=1, valueOffset=2)
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
        self.assertIsNone(transform.eulerFilter())
        self.assertNotEqual(self.values(node), before)
        for actual, expected in zip(self.values(node), self.values(reference)):
            self.assertSequenceAlmostEqual(actual, expected)
        self.assertUndoesInOneStep(lambda: self.assertEqual(self.values(node), before), lambda: None)

    def test_transform_without_keys(self):
        """キーが無ければ何もしないで自身を返す。"""
        transform = mlib.getNode(self.make())
        self.flushUndo()
        self.assertIsNone(transform.eulerFilter())
        self.assertUndoEmpty()

    def test_anim_curve(self):
        """AnimCurve.eulerFilter は animCurveTA だけを受け、Undo 1回で戻る。"""
        node = self.keyed()
        curve = mlib.getNode(cmds.listConnections(node + ".rotateX")[0])
        before = self.values(node)[0]
        self.flushUndo()
        self.assertIsNone(curve.eulerFilter())
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
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, subdivisionsY=subdivisionsY, constructionHistory=False)[0]
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
        """addKey(input)(value を省いた挿入)は評価値を変えずにキーを足し、Undo 1回で戻る。"""
        curve = self.keyed()
        value = curve.evaluate(4)
        self.flushUndo()
        self.assertIsNone(curve.addKey(4))
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "mlibAnimCurveInsertKey")
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(curve.getKeyInputs(), [1.0, 10.0]), lambda: self.assertEqual(curve.getKeyInputs(), [1.0, 4.0, 10.0])
        )
        cmds.redo()
        self.assertAlmostEqual(curve.getKeyValues()[1], value)
        self.assertAlmostEqual(curve.evaluate(4), value)
        # value=None を明示しても挿入。すでにキーのある位置では何も変えない。
        curve.addKey(7, None)
        self.assertEqual(curve.getKeyInputs(), [1.0, 4.0, 7.0, 10.0])
        values = curve.getKeyValues()
        curve.addKey(4)
        self.assertEqual(curve.getKeyInputs(), [1.0, 4.0, 7.0, 10.0])
        self.assertEqual(curve.getKeyValues(), values)
        # value を渡すと今までどおりの書き込み(挿入と区別される)。
        curve.addKey(4, 9.0)
        self.assertEqual(cmds.undoInfo(query=True, undoName=True), "mlibAnimCurveSetKey")
        self.assertAlmostEqual(curve.getKeyValues()[1], 9.0)

    def test_insert_key_seconds_and_invalid(self):
        """timeUnit="sec" の入力と、不正な入力・空のカーブ。"""
        curve = self.keyed()
        fps = {"film": 24.0, "ntsc": 30.0, "pal": 25.0}[cmds.currentUnit(query=True, time=True)]
        curve.addKey(7.0 / fps, timeUnit="sec")
        self.assertEqual([round(value, 6) for value in curve.getKeyInputs()], [1.0, 7.0, 10.0])
        for args, kwargs, error in (
            ((float("inf"),), {}, ValueError),
            (("a",), {}, TypeError),
            ((None,), {}, TypeError),
            ((5,), {"timeUnit": "week"}, ValueError),
        ):
            with self.subTest(args=args, kwargs=kwargs):
                with self.assertRaises(error):
                    curve.addKey(*args, **kwargs)
        # 挿入(value を省く)では、接線の型・fast・check を指定できない(unit は使わない)。
        before = (curve.getKeyInputs(), curve.getKeyValues())
        for label, args, kwargs in (
            ("inTangentType", (5, None, "linear"), {}),
            ("outTangentType", (5,), {"outTangentType": "linear"}),
            ("fast", (5,), {"fast": True}),
            ("check", (5,), {"check": True}),
            ("fast+check", (5,), {"fast": True, "check": True}),
        ):
            with self.subTest(label=label):
                with self.assertRaises(TypeError):
                    curve.addKey(*args, **kwargs)
                self.assertEqual((curve.getKeyInputs(), curve.getKeyValues()), before)
        empty = mlib.getNode(self.make("animCurveTL", "empty#"))
        with self.assertRaisesRegex(RuntimeError, "空のカーブへはキーを挿入できません"):
            empty.addKey(3)
        self.assertEqual(empty.getKeyCount(), 0)

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
        """getKeyframes が返す Keyframe の setBreakdown は keyframe -q -breakdown と一致し、Undo 1回で戻る。"""
        curve = self.keyed()
        curve.addKey(5)
        name = curve.getName(full=True)

        def queried():
            return cmds.keyframe(name, query=True, breakdown=True) or []

        self.assertEqual([curve.getKeyframes(i).isBreakdown() for i in range(3)], [False, False, False])
        self.flushUndo()
        self.assertIsNone(curve.getKeyframes(1).setBreakdown())
        self.assertUndoesInOneStep(lambda: self.assertEqual(queried(), []), lambda: self.assertEqual(queried(), [5.0]))
        key = curve.getKeyframes(1)
        self.assertIsNone(key.setBreakdown())
        self.assertTrue(key.isBreakdown())
        self.assertEqual([curve.getKeyframes(i).isBreakdown() for i in range(3)], [False, True, False])
        key.setBreakdown(False)
        self.assertFalse(key.isBreakdown())
        for index in (0, 2):
            curve.getKeyframes(index).setBreakdown()
        self.assertEqual(queried(), [1.0, 10.0])
        with self.assertRaises(IndexError):
            curve.getKeyframes(5)
        with self.assertRaises(TypeError):
            curve.getKeyframes(1).setBreakdown("yes")
        with self.assertRaises(AttributeError):
            # 番号を渡す setBreakdown・isBreakdown は AnimCurve に置かない(Keyframe で行う)。
            curve.setBreakdown(1)
        with self.assertRaises(IndexError):
            curve.getKeyframes(3).isBreakdown()
        cmds.delete(name)
        with self.assertRaises(RuntimeError):
            curve.getKeyframes(0).isBreakdown()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
