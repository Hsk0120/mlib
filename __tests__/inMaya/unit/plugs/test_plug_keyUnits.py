"""``Plug.setKey``・``Plug.removeKey`` の、秒の指定と時刻の検査のテスト。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


def _frames(seconds):
    """秒を、現在のUIの時間単位でのフレームへ換算する。"""
    return om2.MTime(seconds, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())


class _KeyCase(NamespaceCase):
    """キーを打つtransformを作る。"""

    PREFIX = "mlibPlugKeyUnits_"


class SetKeySecondsTest(_KeyCase):
    """Plug.setKey(timeUnit="sec")。"""

    def test_time_attribute_value_in_seconds(self):
        """時間のアトリビュートでは、timeとvalueの両方を秒で受け、cmdsではフレームで読める。Undo 1回で消える。"""
        node = self.make("transform", "node#")
        cmds.addAttr(node, longName="timeValue", attributeType="time", keyable=True)
        plug = mlib.getPlug(node + ".timeValue")
        name = plug.getName(full=True)
        self.flushUndo()
        plug.setKey(time=1.0, value=2.0, timeUnit="sec")
        self.assertAlmostEqual(cmds.keyframe(name, query=True, timeChange=True)[0], _frames(1.0))
        self.assertAlmostEqual(cmds.keyframe(name, query=True, valueChange=True)[0], _frames(2.0))
        cmds.undo()
        self.assertIsNone(cmds.keyframe(name, query=True, timeChange=True))

    def test_time_attribute_value_in_frames(self):
        """既定(フレーム)では、時間のアトリビュートのvalueをそのままフレームとして打つ。"""
        node = self.make("transform", "node#")
        cmds.addAttr(node, longName="timeValue", attributeType="time", keyable=True)
        plug = mlib.getPlug(node + ".timeValue")
        plug.setKey(time=3, value=12)
        name = plug.getName(full=True)
        self.assertEqual(cmds.keyframe(name, query=True, timeChange=True), [3.0])
        self.assertAlmostEqual(cmds.keyframe(name, query=True, valueChange=True)[0], 12.0)


class RemoveKeySecondsTest(_KeyCase):
    """Plug.removeKey の時刻の単位と検査。"""

    def keyed(self):
        """1秒・2秒にキーを持つtranslateXのPlugを返す。"""
        node = self.make("transform", "node#")
        for seconds in (1.0, 2.0):
            cmds.setKeyframe(node + ".tx", time=_frames(seconds), value=seconds)
        return mlib.getPlug(node + ".tx")

    def test_range_in_seconds(self):
        """秒の範囲は、cmdsでフレームに換算した範囲と同じキーを消す。Undo 1回で戻る。"""
        plug = self.keyed()
        name = plug.getName(full=True)
        self.flushUndo()
        plug.removeKey(time=(0.5, 1.5), timeUnit="sec")
        self.assertEqual(cmds.keyframe(name, query=True, timeChange=True), [_frames(2.0)])
        cmds.undo()
        self.assertEqual(cmds.keyframe(name, query=True, timeChange=True), [_frames(1.0), _frames(2.0)])
        plug.removeKey(time=2.0, timeUnit="sec")
        self.assertEqual(cmds.keyframe(name, query=True, timeChange=True), [_frames(1.0)])

    def test_invalid_time(self):
        """有限でない時刻はValueError、秒で範囲の文字列はTypeErrorで、キーを消さない。"""
        plug = self.keyed()
        name = plug.getName(full=True)
        cases = [
            ({"time": float("inf")}, ValueError),
            ({"time": (0, float("nan"))}, ValueError),
            ({"time": "1:10", "timeUnit": "sec"}, TypeError),
            ({"time": (1, 2, 3)}, TypeError),
            ({"time": True}, TypeError),
        ]
        for kwargs, error in cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(error):
                    plug.removeKey(**kwargs)
                self.assertEqual(len(cmds.keyframe(name, query=True, timeChange=True)), 2)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
