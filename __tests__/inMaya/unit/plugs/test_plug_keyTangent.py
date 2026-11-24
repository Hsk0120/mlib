"""``Plug.setKeyTangent``・``Node.setKeyTangent`` と ``Plug.getAnimCurve(indirect=True)`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _KeyCase(NamespaceCase):
    """キーのあるtransformを作る。"""

    PREFIX = "mlibKeyTangent_"

    def keyed(self):
        """rotateX・translateXに1・5・10のキーを持つtransformを返す。"""
        node = self.make("transform", "keyed#")
        for attribute in ("rotateX", "translateX"):
            for time, value in ((1, 0), (5, 3), (10, 1)):
                cmds.setKeyframe(node, attribute=attribute, time=time, value=value, inTangentType="spline", outTangentType="spline")
        return mlib.getNode(node)


class PlugSetKeyTangentTest(_KeyCase):
    """Plug.setKeyTangent。"""

    def test_range_and_undo(self):
        """範囲のキーの接線の型だけを変え、Undo 1回で戻る。"""
        node = self.keyed()
        plug = node.getPlug("rotateX")
        self.flushUndo()
        plug.setKeyTangent(inTangentType="linear", outTangentType="step", time=(1, 5))
        name = plug.getName(full=True)
        self.assertUndoesInOneStep(
            lambda: self.assertEqual(cmds.keyTangent(name, query=True, outTangentType=True), ["spline"] * 3),
            lambda: self.assertEqual(cmds.keyTangent(name, query=True, outTangentType=True), ["step", "step", "spline"]),
        )
        plug.setKeyTangent(inTangentType="AUTO")
        self.assertEqual(cmds.keyTangent(name, query=True, inTangentType=True), ["auto"] * 3)
        self.assertEqual(cmds.keyTangent(node.getPlug("translateX").getName(full=True), query=True, inTangentType=True), ["spline"] * 3)

    def test_errors(self):
        """接線の型の誤り・範囲の誤りを変更前に拒否する。キーの無い範囲は何もしない。"""
        plug = self.keyed().getPlug("rotateX")
        cases = [
            ({}, ValueError),
            ({"inTangentType": "fixed"}, ValueError),
            ({"inTangentType": "bogus"}, ValueError),
            ({"inTangentType": "auto", "time": (5, 1)}, ValueError),
            ({"inTangentType": "auto", "time": "1"}, TypeError),
            ({"inTangentType": "auto", "timeUnit": "deg"}, ValueError),
        ]
        for kwargs, error in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(error):
                plug.setKeyTangent(**kwargs)
        plug.setKeyTangent(inTangentType="auto", time=(20, 30))
        self.assertEqual(cmds.keyTangent(plug.getName(full=True), query=True, inTangentType=True), ["spline"] * 3)


class NodeSetKeyTangentTest(_KeyCase):
    """Node.setKeyTangent。"""

    def test_attributes_and_forwarding(self):
        """指定したアトリビュートだけを変え、Noneなら全部を変える。複数形からも呼べる。"""
        node = self.keyed()
        node.setKeyTangent(["rotateX"], outTangentType="linear")
        self.assertEqual(cmds.keyTangent(node.getPlug("rotateX").getName(full=True), query=True, outTangentType=True), ["linear"] * 3)
        self.assertEqual(cmds.keyTangent(node.getPlug("translateX").getName(full=True), query=True, outTangentType=True), ["spline"] * 3)
        other = self.keyed()
        mlib.Nodes([node, other]).setKeyTangent(inTangentType="flat", time=(10, 10))
        for target in (node, other):
            self.assertEqual(cmds.keyTangent(target.getPlug("translateX").getName(full=True), query=True, inTangentType=True), ["spline", "spline", "flat"])
        with self.assertRaises(ValueError):
            node.setKeyTangent([], inTangentType="auto")


class GetAnimCurveIndirectTest(NamespaceCase):
    """Plug.getAnimCurve(indirect=True)。"""

    PREFIX = "mlibAnimCurveIndirect_"

    def test_layer_and_pair_blend(self):
        """直接のカーブ、レイヤー、pairBlend の先で、cmds.keyframe(q=True, name=True) の先頭と同じカーブを返す。"""
        direct = self.make("transform", "direct#")
        cmds.setKeyframe(direct, attribute="translateX", time=1, value=1)
        plug = mlib.getNode(direct).getPlug("translateX")
        self.assertEqual(plug.getAnimCurve(indirect=True), plug.getAnimCurve())
        self.assertIsNone(mlib.getNode(direct).getPlug("translateY").getAnimCurve(indirect=True))

        layered = self.make("transform", "layered#")
        cmds.setKeyframe(layered, attribute="translateX", time=1, value=1)
        layer = cmds.animLayer(self.name("layer"))
        cmds.animLayer(layer, edit=True, attribute=layered + ".translateX")
        cmds.animLayer(layer, edit=True, selected=True, preferred=True)
        cmds.setKeyframe(layered, attribute="translateX", time=1, value=2, animLayer=layer)
        plug = mlib.getNode(layered).getPlug("translateX")
        self.assertIsNone(plug.getAnimCurve())
        self.assertEqual(plug.getAnimCurve(indirect=True).getName(), cmds.keyframe(plug.getName(full=True), query=True, name=True)[0])

        blended = self.make("transform", "blended#")
        cmds.setKeyframe(blended, attribute="translateX", time=1, value=1)
        cmds.pointConstraint(self.make("transform", "target#"), blended)
        cmds.setKeyframe(blended, attribute="translateX", time=2, value=1)
        plug = mlib.getNode(blended).getPlug("translateX")
        names = cmds.keyframe(plug.getName(full=True), query=True, name=True) or []
        result = plug.getAnimCurve(indirect=True)
        self.assertEqual(None if result is None else result.getName(), names[0] if names else None)

    def test_errors(self):
        """layerとindirectの同時指定、bool以外のindirectを拒否する。"""
        plug = mlib.getNode(self.make("transform", "node#")).getPlug("translateX")
        with self.assertRaises(TypeError):
            plug.getAnimCurve(indirect=1)
        with self.assertRaises(ValueError):
            plug.getAnimCurve(cmds.animLayer(query=True, root=True) or "BaseAnimation", indirect=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
