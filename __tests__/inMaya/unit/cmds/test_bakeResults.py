"""``mlib.cmds.bakeResults`` のテスト。

- DAG・Transform・アニメーションカーブ・DG の照会と編集の契約を固定する。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.cmds.bakeResults import bakeResults
from mlib.nodes import AnimCurve


def _world(name):
    """cmds で読むワールドマトリクス。"""
    return cmds.xform(name, query=True, worldSpace=True, matrix=True)


class BakeResultsTest(NamespaceCase):
    def setUp(self):
        super().setUp()
        self.range = cmds.playbackOptions(query=True, minTime=True), cmds.playbackOptions(query=True, maxTime=True)
        self.time = cmds.currentTime(query=True)
        cmds.playbackOptions(minTime=1, maxTime=5)
        self.driver = self.make(text="driver")
        self.target = self.make(text="target")
        cmds.setKeyframe(self.driver, attribute="translateX", time=1, value=0)
        cmds.setKeyframe(self.driver, attribute="translateX", time=10, value=10)
        cmds.parentConstraint(self.driver, self.target, name=self.name("pc"))

    def tearDown(self):
        cmds.playbackOptions(minTime=self.range[0], maxTime=self.range[1])
        cmds.currentTime(self.time)
        super().tearDown()

    def test_bake_returns_curves_and_restores_time(self):
        """既定は再生範囲、焼き込んだカーブを AnimCurve で返し、現在時刻を戻す。"""
        cmds.currentTime(3)
        self.flushUndo()
        curves = bakeResults(self.target, simulation=True)
        self.assertTrue(curves)
        self.assertTrue(all(isinstance(curve, AnimCurve) for curve in curves))
        self.assertEqual(cmds.currentTime(query=True), 3)
        tx = cmds.listConnections(self.target + ".translateX", source=True, destination=False, type="animCurve")
        self.assertIn(mlib.getNode(tx[0]), curves)
        self.assertEqual(cmds.keyframe(self.target + ".translateX", query=True, timeChange=True), [1.0, 2.0, 3.0, 4.0, 5.0])
        cmds.undo()
        self.assertFalse(cmds.listConnections(self.target + ".translateX", source=True, destination=False, type="animCurve"))
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_attributes_time_and_sample(self):
        """attributes・time・sampleBy を cmds.bakeResults へ渡し、指定したアトリビュートのカーブだけを返す。"""
        curves = bakeResults([self.target], attributes=["tx", "rotate"], time=(2, 6), sampleBy=2, simulation=True)
        driven = {plug.getLongName() for curve in curves for plug in curve.getDrivenPlugs()}
        self.assertEqual(driven, {"translateX", "rotateX", "rotateY", "rotateZ"})
        self.assertEqual(cmds.keyframe(self.target + ".translateX", query=True, timeChange=True), [2.0, 4.0, 6.0])
        self.assertFalse(cmds.listConnections(self.target + ".translateY", source=True, destination=False, type="animCurve"))

    def test_errors(self):
        """引数で受けるフラグ・query・不正な time/sampleBy/attributes/nodes は例外。"""
        for kwargs, error in (
            ({"time": (1, 2), "t": (1, 2)}, TypeError),
            ({"attributes": "tx", "at": "tx"}, TypeError),
            ({"attribute": "tx"}, TypeError),
            ({"query": True}, TypeError),
            ({"time": (5, 1)}, ValueError),
            ({"time": (1,)}, ValueError),
            ({"time": "1:5"}, TypeError),
            ({"sampleBy": 0}, ValueError),
            ({"sampleBy": "1"}, TypeError),
            ({"attributes": 1}, TypeError),
            ({"attributes": []}, ValueError),
        ):
            with self.subTest(kwargs=kwargs):
                self.assertRaises(error, bakeResults, self.target, **kwargs)
        self.assertRaises(ValueError, bakeResults, [])
        self.assertRaises(RuntimeError, bakeResults, self.name("missing"))


if __name__ == "__main__":
    unittest.main()
