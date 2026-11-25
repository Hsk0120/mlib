"""ドリブンキーの接続解決・単位変換・複数入力・Undoを検証する。

あわせて次も確かめる。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
"""

import math
import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import DrivenKey


class DrivenKeyTest(unittest.TestCase):
    def setUp(self):
        self.ns = "mlibSDK_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)
        self.a = cmds.createNode("transform", name=self.ns + ":a")
        self.b = cmds.createNode("transform", name=self.ns + ":b")
        self.c = cmds.createNode("transform", name=self.ns + ":c")

    def tearDown(self):
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_creation_units_undo_and_rename(self):
        relation = mlib.DrivenKey(self.a + ".ry", mlib.getNode(self.b).getPlug("rz"))
        before = cmds.ls(type="animCurve") or []
        self.assertFalse(relation.exists())
        self.assertEqual(cmds.ls(type="animCurve") or [], before)
        relation.setKey(0, 0)
        cmds.undo()
        self.assertFalse(relation.exists())
        cmds.redo()
        self.assertTrue(relation.exists())
        relation.setKey(90, 45)
        self.assertEqual(len(relation.getCurves()), 1)
        cmds.setAttr(self.a + ".ry", 45)
        self.assertAlmostEqual(cmds.getAttr(self.b + ".rz"), 22.5, places=4)
        relation.setKey(90, 60)
        self.assertAlmostEqual(cmds.getAttr(self.a + ".ry"), 45)
        self.assertAlmostEqual(cmds.getAttr(self.b + ".rz"), 30, places=4)
        cmds.undo()
        self.assertAlmostEqual(cmds.getAttr(self.b + ".rz"), 22.5, places=4)
        self.a = cmds.rename(self.a, self.ns + ":renamed")
        self.assertIn("renamed", relation.getDriverPlug().getName(full=True))
        self.assertEqual(len(relation.getCurves()), 1)

    def test_multiple_drivers_and_find(self):
        one = mlib.DrivenKey(self.a + ".tx", self.b + ".ty")
        two = mlib.DrivenKey(self.c + ".tx", self.b + ".ty")
        one.setKey(0, 0)
        one.setKey(10, 10)
        two.setKey(0, 0)
        two.setKey(10, 20)
        self.assertEqual(len(one.getCurves()), 1)
        self.assertEqual(len(two.getCurves()), 1)
        self.assertNotEqual(one.getCurves()[0].getName(full=True), two.getCurves()[0].getName(full=True))
        found = mlib.DrivenKey.find(self.b + ".ty")
        self.assertEqual(len(found), 2)
        cmds.setAttr(self.a + ".tx", 5)
        cmds.setAttr(self.c + ".tx", 5)
        self.assertAlmostEqual(cmds.getAttr(self.b + ".ty"), 15)
        self.assertIsInstance(found, list)
        from mlib.decorator import undoChunk

        with undoChunk("testDrivenKeys"):
            for relation in found:
                relation.setKey(10, 30)
        self.assertAlmostEqual(cmds.getAttr(self.b + ".ty"), 30)
        cmds.undo()
        self.assertAlmostEqual(cmds.getAttr(self.b + ".ty"), 15)
        cmds.redo()
        self.assertAlmostEqual(cmds.getAttr(self.b + ".ty"), 30)
        self.assertEqual(len(found[:1]), 1)
        self.assertEqual(len([relation.getDriverPlug() for relation in found]), 2)

    def test_existing_maya_keys_and_weight_branch(self):
        cmds.setDrivenKeyframe(self.b + ".ty", currentDriver=self.a + ".tx", driverValue=0, value=0)
        cmds.setDrivenKeyframe(self.b + ".ty", currentDriver=self.c + ".tx", driverValue=0, value=0)
        blend = cmds.listConnections(self.b + ".ty", source=True, destination=False, type="blendWeighted", skipConversionNodes=True)[0]
        cmds.setDrivenKeyframe(blend + ".weight[0]", currentDriver=self.a + ".tz", driverValue=0, value=1)
        found = mlib.DrivenKey.find(self.b + ".ty")
        self.assertEqual(len(found), 2)
        self.assertEqual(
            {p.getName(full=True) for p in [relation.getDriverPlug() for relation in found]},
            {mlib.getNode(self.a).getPlug("tx").getName(full=True), mlib.getNode(self.c).getPlug("tx").getName(full=True)},
        )
        relation = mlib.DrivenKey(self.a + ".tx", self.b + ".ty")
        self.assertEqual(len(relation.getCurves()), 1)
        relation.setKey(10, 10)
        self.assertEqual(relation.getCurves()[0].getKeyCount(), 2)

    def test_repr_shows_full_plug_names(self):
        """reprはドライバーと駆動先の完全名を含む。"""
        relation = mlib.DrivenKey(self.a + ".tx", self.b + ".ty")
        driver = mlib.getPlug(self.a + ".tx")._full_name()
        driven = mlib.getPlug(self.b + ".ty")._full_name()
        self.assertEqual(repr(relation), f"DrivenKey({driver!r}, {driven!r})")

    def _driver_curve(self, name, slope):
        """ドライバー a.tx から入力を受ける animCurveUL を作る。"""
        curve = cmds.createNode("animCurveUL", name=self.ns + ":" + name)
        cmds.setKeyframe(curve, float=0.0, value=0.0)
        cmds.setKeyframe(curve, float=10.0, value=10.0 * slope)
        cmds.connectAttr(self.a + ".tx", curve + ".input")
        return curve

    def test_same_curve_through_two_blend_paths_is_counted_once(self):
        """同じカーブが2つのblendWeightedを通る2つの経路でつながっていても、カーブは1回だけ数える。"""
        curve = self._driver_curve("shared", 1.0)
        left = cmds.createNode("blendWeighted", name=self.ns + ":left")
        right = cmds.createNode("blendWeighted", name=self.ns + ":right")
        blend = cmds.createNode("blendWeighted", name=self.ns + ":blend")
        cmds.connectAttr(curve + ".output", left + ".input[0]")
        cmds.connectAttr(curve + ".output", right + ".input[0]")
        cmds.connectAttr(left + ".output", blend + ".input[0]")
        cmds.connectAttr(right + ".output", blend + ".input[1]")
        cmds.connectAttr(blend + ".output", self.b + ".ty")
        relation = mlib.DrivenKey(self.a + ".tx", self.b + ".ty")
        curves = relation.getCurves()
        self.assertEqual(len(curves), 1)
        self.assertEqual(curves[0].getName(full=True), cmds.ls(curve, long=True)[0])

    def test_find_merges_two_curves_of_one_driver(self):
        """同じドライバーの2つのカーブがblendWeightedで1つの駆動先へつながっていても、findは1件にまとめる。"""
        first = self._driver_curve("firstCurve", 1.0)
        second = self._driver_curve("secondCurve", 2.0)
        blend = cmds.createNode("blendWeighted", name=self.ns + ":merge")
        cmds.connectAttr(first + ".output", blend + ".input[0]")
        cmds.connectAttr(second + ".output", blend + ".input[1]")
        cmds.connectAttr(blend + ".output", self.b + ".ty")
        found = mlib.DrivenKey.find(self.b + ".ty")
        self.assertEqual(len(found), 1)
        self.assertTrue(found[0].getDriverPlug().mplug() == mlib.getNode(self.a).getPlug("tx").mplug())
        # 2つのカーブは cmds でもどちらも a.tx から入力を受けている。
        self.assertEqual(cmds.listConnections(first + ".input", plugs=True), cmds.listConnections(second + ".input", plugs=True))

    def test_find_missing_attribute_raises_attribute_error(self):
        """存在しないアトリビュートの駆動先は AttributeError(MissingAttributeError)。"""
        with self.assertRaises(AttributeError):
            mlib.DrivenKey.find(self.b + ".mlibNoSuchAttribute")

    def test_set_key_rejects_two_curves_for_one_pair(self):
        """同じドライバーと駆動先の組にカーブが2つあると、setKeyはRuntimeErrorで何も変えない。"""
        first = self._driver_curve("first", 1.0)
        second = self._driver_curve("second", 2.0)
        blend = cmds.createNode("blendWeighted", name=self.ns + ":blend")
        cmds.connectAttr(first + ".output", blend + ".input[0]")
        cmds.connectAttr(second + ".output", blend + ".input[1]")
        cmds.connectAttr(blend + ".output", self.b + ".ty")
        relation = mlib.DrivenKey(self.a + ".tx", self.b + ".ty")
        self.assertEqual(len(relation.getCurves()), 2)
        for fast in (False, True):
            with self.subTest(fast=fast), self.assertRaises(RuntimeError):
                relation.setKey(5, 1, fast=fast)
        self.assertEqual(cmds.keyframe(first, query=True, keyframeCount=True), 2)
        self.assertEqual(cmds.keyframe(second, query=True, keyframeCount=True), 2)

    def test_time_animation_is_not_replaced(self):
        cmds.setKeyframe(self.b + ".tx", time=1, value=2)
        before = cmds.listConnections(self.b + ".tx", source=True, destination=False, plugs=True)
        relation = mlib.DrivenKey(self.a + ".tx", self.b + ".tx")
        with self.assertRaises(RuntimeError):
            relation.setKey(0, 0)
        self.assertEqual(cmds.listConnections(self.b + ".tx", source=True, destination=False, plugs=True), before)

    def test_validation_and_unsupported_connections(self):
        with self.assertRaises(ValueError):
            mlib.DrivenKey(self.a + ".translate", self.b + ".ty")
        with self.assertRaises(ValueError):
            mlib.DrivenKey(self.a + ".tx", self.a + ".translateX")
        relation = mlib.DrivenKey(self.a + ".tx", self.b + ".ty")
        with self.assertRaises(ValueError):
            relation.setKey(float("nan"), 0)
        cmds.connectAttr(self.c + ".ty", self.b + ".ty")
        with self.assertRaises(RuntimeError):
            relation.setKey(0, 0)
        self.assertTrue(cmds.isConnected(self.c + ".ty", self.b + ".ty"))
        self.assertFalse(relation.exists())
        self.assertEqual(len(mlib.DrivenKey.find(self.b + ".ty")), 0)
        cmds.delete(self.a)
        with self.assertRaises(RuntimeError):
            relation.setKey(0, 0)

    def test_instanced_shape_driver_is_matched_by_plug_identity(self):
        # インスタンス化されたシェイプのアトリビュートは、どのインスタンスのパスから指定しても同じプラグ。
        # 2つ目のインスタンスのパスで指定したドライバーも、作成したカーブと照合できること。
        box = cmds.polyCube(name=self.ns + ":box", constructionHistory=False)[0]
        first_group = cmds.group(box, name=self.ns + ":ga")
        second_group = cmds.createNode("transform", name=self.ns + ":gb")
        instance = cmds.instance(cmds.listRelatives(first_group, children=True, fullPath=True)[0], name=self.ns + ":box1")[0]
        instance = cmds.parent(instance, second_group)[0]
        first_shape = cmds.listRelatives(cmds.ls(first_group, long=True)[0], allDescendents=True, type="mesh", fullPath=True)[0]
        second_shape = cmds.listRelatives(cmds.ls(instance, long=True)[0], shapes=True, fullPath=True)[0]
        self.assertNotEqual(first_shape, second_shape)
        cmds.addAttr(first_shape, longName="drv", attributeType="double", keyable=True)
        driver = mlib.getNode(second_shape).getPlug("drv")
        relation = mlib.DrivenKey(driver, self.c + ".tx")
        relation.setKey(0, 0)
        relation.setKey(1, 10)
        self.assertEqual(len(relation.getCurves()), 1)
        self.assertTrue(relation.exists())
        # 1つ目のインスタンスのパスで指定しても同じ関係として見つかる。
        same = mlib.DrivenKey(mlib.getNode(first_shape).getPlug("drv"), self.c + ".tx")
        self.assertEqual([curve.getName(full=True) for curve in same.getCurves()], [curve.getName(full=True) for curve in relation.getCurves()])
        found = mlib.DrivenKey.find(self.c + ".tx")
        self.assertEqual(len(found), 1)
        cmds.setAttr(first_shape + ".drv", 1)
        self.assertAlmostEqual(cmds.getAttr(self.c + ".tx"), 10.0)
        with self.assertRaises(ValueError):
            mlib.DrivenKey(mlib.getNode(first_shape).getPlug("drv"), mlib.getNode(second_shape).getPlug("drv"))

    def test_find_skips_non_numeric_drivers(self):
        # 値によって型が変わる generic アトリビュート(choice.output)のドライバーは対象外として除外し、
        # 例外にしない。同じ駆動先の数値ドライバーは見つかる。
        relation = mlib.DrivenKey(self.a + ".tx", self.b + ".ty")
        relation.setKey(0, 0)
        relation.setKey(10, 10)
        choice = cmds.createNode("choice", name=self.ns + ":choice")
        cmds.connectAttr(self.c + ".tx", choice + ".input[0]")
        curve = cmds.createNode("animCurveUU", name=self.ns + ":genericCurve")
        cmds.setKeyframe(curve, float=0.0, value=0.0)
        cmds.setKeyframe(curve, float=1.0, value=1.0)
        cmds.connectAttr(choice + ".output", curve + ".input")
        cmds.connectAttr(curve + ".output", self.b + ".tz")
        self.assertEqual(len(mlib.DrivenKey.find(self.b + ".tz")), 0)
        self.assertEqual(len(mlib.DrivenKey.find(self.b + ".ty")), 1)
        self.assertEqual(len(mlib.DrivenKey.find(mlib.getNode(self.b).getPlug("ty").mplug())), 1)


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class DrivenKeySpecTest(unittest.TestCase):
    """DrivenKeyの内部単位・検証・Undoを固定する。"""

    def setUp(self):
        """一時名前空間にドライバーと駆動先を作り、UI単位を保存する。"""
        self.linear = cmds.currentUnit(query=True, linear=True)
        self.angle = cmds.currentUnit(query=True, angle=True)
        self.undo_state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=True)
        self.ns = "mlibSpecDDriven_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)
        self.driver = cmds.createNode("transform", name=self.ns + ":driver")
        self.driven = cmds.createNode("transform", name=self.ns + ":driven")

    def tearDown(self):
        """一時名前空間を削除し、UI単位とUndo設定を戻す。"""
        cmds.currentUnit(linear=self.linear, angle=self.angle)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        cmds.undoInfo(state=self.undo_state)

    def test_set_key_uses_internal_units(self):
        """setKeyの値はrad・cmの内部単位で、UI単位がdeg・mmでも同じ関係になる。"""
        cmds.currentUnit(linear="mm", angle="deg")
        key = DrivenKey(self.driver + ".rx", self.driven + ".tx")
        self.assertFalse(key.exists())
        self.assertIsNone(key.setKey(0.0, 0.0))
        key.setKey(math.pi / 2, 1.0)
        self.assertTrue(key.exists())
        cmds.setAttr(self.driver + ".rx", 90.0)
        node = om2.MFnDependencyNode(om2.MSelectionList().add(self.driven).getDependNode(0))
        self.assertAlmostEqual(node.findPlug("translateX", False).asDouble(), 1.0, places=6)
        self.assertAlmostEqual(cmds.getAttr(self.driven + ".tx"), 10.0, places=4)
        found = DrivenKey.find(self.driven + ".tx")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].getDriverPlug().getName(full=True), key.getDriverPlug().getName(full=True))
        self.assertEqual(found[0].getDrivenPlug().getName(full=True), key.getDrivenPlug().getName(full=True))
        self.assertEqual(len(key.getCurves()), 1)

    def test_one_undo_per_key(self):
        """setKeyは1回のUndoで戻る。"""
        key = DrivenKey(self.driver + ".tx", self.driven + ".ty")
        key.setKey(0.0, 0.0)
        cmds.undo()
        self.assertFalse(key.exists())

    def test_second_driver_is_undone_in_one_step(self):
        """2つ目のドライバーのsetKeyも、blendWeighted・カーブ・接続ごと1回のUndoで戻る。角度の駆動先でも同じ値になる。"""
        types = ["animCurve", "blendWeighted", "unitConversion"]
        for attribute in ("tz", "rz"):
            with self.subTest(attribute=attribute):
                driven = self.driven + "." + attribute
                first = DrivenKey(self.driver + ".rx", driven)
                first.setKey(0.0, 0.0)
                first.setKey(10.0, 1.0)
                before = (cmds.listConnections(driven, source=True, destination=False), set(cmds.ls(type=types) or []))
                second = DrivenKey(self.driver + ".ry", driven)
                second.setKey(10.0, 2.0)
                self.assertEqual(cmds.nodeType(cmds.listConnections(driven, source=True, destination=False, skipConversionNodes=True)[0]), "blendWeighted")
                self.assertEqual(len(second.getCurves()), 1)
                self.assertEqual(len(DrivenKey.find(driven)), 2)
                cmds.setAttr(self.driver + ".rx", 10.0)
                cmds.setAttr(self.driver + ".ry", 10.0)
                self.assertAlmostEqual(cmds.getAttr(driven), 3.0, places=4)
                cmds.undo()
                cmds.undo()
                cmds.undo()
                self.assertEqual((cmds.listConnections(driven, source=True, destination=False), set(cmds.ls(type=types) or [])), before)
                self.assertFalse(second.exists())
                cmds.setAttr(self.driver + ".rx", 0.0)

    def test_multi_and_compound_plugs_are_refused(self):
        """要素の型が数値でも、マルチアトリビュート全体(コンパウンドでない)とコンパウンドアトリビュートはValueError。"""
        average = cmds.createNode("plusMinusAverage", name=self.ns + ":average")
        self.assertTrue(cmds.attributeQuery("input1D", node=average, multi=True))
        for driver, driven in (
            (average + ".input1D", self.driven + ".tx"),
            (self.driver + ".tx", average + ".input1D"),
            (self.driver + ".translate", self.driven + ".tx"),
        ):
            with self.subTest(driver=driver, driven=driven), self.assertRaisesRegex(ValueError, "マルチアトリビュートやコンパウンドアトリビュート"):
                DrivenKey(driver, driven)
        self.assertIsNotNone(DrivenKey(self.driver + ".tx", average + ".input1D[0]"))

    def test_validation(self):
        """同じアトリビュート・非数値はValueError、型不正はTypeError、存在しないはAttributeError。"""
        with self.assertRaises(ValueError):
            DrivenKey(self.driver + ".tx", self.driver + ".translateX")
        with self.assertRaises(ValueError):
            DrivenKey(self.driver + ".translate", self.driven + ".tx")
        with self.assertRaises(TypeError):
            DrivenKey(5, self.driven + ".tx")
        with self.assertRaises(AttributeError):
            DrivenKey(self.driver + ".noSuchAttribute", self.driven + ".tx")
        key = DrivenKey(self.driver + ".tx", self.driven + ".tx")
        for value in (float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                key.setKey(value, 0.0)
        with self.assertRaises(ValueError):
            key.setKey("abc", 0.0)
        with self.assertRaises(TypeError):
            key.setKey(None, 0.0)
        self.assertFalse(key.exists())
        cmds.delete(self.driver)
        with self.assertRaises(RuntimeError):
            key.getDriverPlug()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
