"""``mlib.nodes.animCurve`` の AnimCurve の、空の番号・空のカーブ・不正な引数・無効なノードでの動きを確かめる。"""

import sys
import unittest
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _CurveCase(NamespaceCase):
    """専用の名前空間に、キーを2つ持つ animCurveTL と、キーの無い animCurveTL を作る。"""

    PREFIX = "mlibSpecAnimCurveEdge_"

    def setUp(self):
        super().setUp()
        self.curve = mlib.createNode("animCurveTL", name=self.name("keyed"))
        self.curve.replaceKeys([(1, 0.0, "linear", "linear"), (5, 2.0, "linear", "linear")])
        self.empty = mlib.createNode("animCurveTL", name=self.name("empty"))

    def times(self, curve):
        return cmds.keyframe(curve.getName(full=True), query=True, timeChange=True) or []

    def values(self, curve):
        return cmds.keyframe(curve.getName(full=True), query=True, valueChange=True) or []


class AnimCurveEmptyInputTest(_CurveCase):
    """番号が空・カーブが空のときは、キーを変えない。"""

    def test_set_breakdown_with_no_index(self):
        """setBreakdown([]) は何もしない。ブレイクダウンのキーは増えない。"""
        self.curve.setBreakdown([])
        self.assertEqual(cmds.keyframe(self.curve.getName(full=True), query=True, breakdown=True), None)

    def test_scale_key_with_no_index(self):
        """scaleKey(index=[]) は何もしない。キーの時刻と値は変わらない。"""
        self.curve.scaleKey(index=[], inputScale=2, valueScale=3)
        self.assertEqual(self.times(self.curve), [1.0, 5.0])
        self.assertEqual(self.values(self.curve), [0.0, 2.0])

    def test_set_key_values_with_no_index(self):
        """内部の _set_key_values は番号が空なら何も書かずに自身を返す。"""
        self.assertIs(self.curve._set_key_values([], 9.0), self.curve)
        self.assertEqual(self.values(self.curve), [0.0, 2.0])

    def test_replace_keys_on_empty_curve(self):
        """キーの無いカーブへの replaceKeys(並び) はキーを打つだけ。Undo 1回で空に戻る。"""
        self.empty.replaceKeys([(2, 1.0), (4, 3.0)])
        self.assertEqual(self.times(self.empty), [2.0, 4.0])
        self.assertEqual(self.values(self.empty), [1.0, 3.0])
        cmds.undo()
        self.assertEqual(self.times(self.empty), [])

    def test_replace_keys_from_empty_curve(self):
        """キーの無いカーブを写すと、キーがすべて無くなる。Undo 1回で戻る。"""
        self.curve.replaceKeys(self.empty)
        self.assertEqual(self.times(self.curve), [])
        cmds.undo()
        self.assertEqual(self.times(self.curve), [1.0, 5.0])

    def test_replace_keys_from_curve_into_empty_curve(self):
        """キーの無いカーブへ、別のカーブを写す。fixed の接線は角度を写し、型は fixed のまま。"""
        cmds.keyTangent(self.curve.getName(full=True), edit=True, inTangentType="fixed", outTangentType="fixed")
        self.empty.replaceKeys(self.curve)
        self.assertEqual(self.times(self.empty), [1.0, 5.0])
        self.assertEqual(self.values(self.empty), [0.0, 2.0])
        self.assertEqual(cmds.keyTangent(self.empty.getName(full=True), query=True, inTangentType=True, outTangentType=True), ["fixed"] * 4)


class AnimCurveErrorTest(_CurveCase):
    """docstringの Raises に書いた例外が出る。"""

    def test_key_inputs_rejects_non_string_time_unit(self):
        """getKeyInputs の timeUnit が文字列・None以外なら TypeError。"""
        with self.assertRaises(TypeError):
            self.curve.getKeyInputs(timeUnit=3)

    def test_set_tangent_errors(self):
        """setTangent は範囲外の番号で IndexError、文字列でない unit で TypeError。接線は変わらない。"""
        name = self.curve.getName(full=True)
        before = cmds.keyTangent(name, query=True, inAngle=True, outAngle=True)
        with self.assertRaises(IndexError):
            self.curve.setTangent(9, inAngle=10)
        with self.assertRaises(TypeError):
            self.curve.setTangent(0, unit=3, inAngle=10)
        self.assertEqual(cmds.keyTangent(name, query=True, inAngle=True, outAngle=True), before)

    def test_set_breakdown_on_deleted_curve(self):
        """削除済みのカーブへの setBreakdown は RuntimeError。"""
        cmds.delete(self.curve.getName(full=True))
        with self.assertRaises(RuntimeError):
            self.curve.setBreakdown(0)

    def test_unit_value_on_deleted_curve(self):
        """内部の _unit_value は、無効なノードではアトリビュートを取り直そうとして RuntimeError。"""
        cmds.delete(self.curve.getName(full=True))
        with self.assertRaises(RuntimeError):
            self.curve._unit_value(1.0)

    def test_unit_value_without_plug_falls_back(self):
        """findPlug が失敗しても、getPlug の結果で同じ値に変換する(UIの単位がcmのときはそのまま)。"""
        cmds.currentUnit(linear="cm")
        expected = self.curve._unit_value(2.5, output=True)
        fn = mock.Mock()
        fn.findPlug.side_effect = RuntimeError("not found")
        with mock.patch.object(type(self.curve), "_dependency_fn", return_value=fn):
            self.assertEqual(self.curve._unit_value(2.5, output=True), expected)
        self.assertTrue(fn.findPlug.called)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
