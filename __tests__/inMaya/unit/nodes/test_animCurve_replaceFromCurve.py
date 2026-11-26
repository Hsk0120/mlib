"""``AnimCurve.replaceKeys`` にカーブを渡したときのテスト(copyKey/pasteKey と同じ結果)。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


def _state(name):
    """カーブのキーと接線の状態を、比べられる形で返す。"""

    def rounded(values):
        return [round(value, 6) for value in values or []]

    return (
        rounded(cmds.keyframe(name, query=True, timeChange=True)),
        rounded(cmds.keyframe(name, query=True, valueChange=True)),
        rounded(cmds.keyTangent(name, query=True, inAngle=True)),
        rounded(cmds.keyTangent(name, query=True, outAngle=True)),
        rounded(cmds.keyTangent(name, query=True, inWeight=True)),
        rounded(cmds.keyTangent(name, query=True, outWeight=True)),
        cmds.keyTangent(name, query=True, inTangentType=True),
        cmds.keyTangent(name, query=True, outTangentType=True),
        cmds.keyTangent(name, query=True, lock=True),
        cmds.keyTangent(name, query=True, weightLock=True),
        cmds.keyframe(name, query=True, breakdown=True),
        cmds.keyTangent(name, query=True, weightedTangents=True),
    )


class ReplaceKeysFromCurveTest(NamespaceCase):
    """接線・ウェイト・ロック・ブレイクダウンまで写す。"""

    PREFIX = "mlibReplaceFromCurve_"

    def source(self, weighted):
        """いろいろな接線を持つカーブを作る。"""
        curve = mlib.createNode("animCurveTA", name=self.name("source"), skipSelect=True)
        for time, value in ((1, 0), (5, 30), (9, -10), (14, 45)):
            curve.addKey(time, value)
        name = curve.getName(full=True)
        if weighted:
            cmds.keyTangent(name, edit=True, weightedTangents=True)
        cmds.keyTangent(name, edit=True, index=(0, 0), outAngle=25, lock=False)
        if weighted:
            cmds.keyTangent(name, edit=True, index=(0, 0), outWeight=4, weightLock=False)
        cmds.keyTangent(name, edit=True, index=(1, 1), inTangentType="linear", outTangentType="step")
        cmds.keyTangent(name, edit=True, index=(3, 3), inTangentType="flat", outTangentType="clamped")
        cmds.keyframe(name, edit=True, index=(2, 2), breakdown=True)
        return curve

    def test_matches_paste_key(self):
        """ウェイト付き・なしの両方で、cmds.pasteKey(option="replaceCompletely") と同じ状態になり、Undo 1回で戻る。"""
        for weighted in (False, True):
            with self.subTest(weighted=weighted):
                source = self.source(weighted)
                target = mlib.createNode("animCurveTA", name=self.name("target"), skipSelect=True)
                target.addKey(3, 7)
                reference = mlib.createNode("animCurveTA", name=self.name("reference"), skipSelect=True)
                cmds.copyKey(source.getName(full=True))
                cmds.pasteKey(reference.getName(full=True), option="replaceCompletely")
                before = _state(target.getName(full=True))
                self.flushUndo()
                target.replaceKeys(source)
                expected = _state(reference.getName(full=True))
                self.assertUndoesInOneStep(
                    lambda: self.assertEqual(_state(target.getName(full=True)), before), lambda: self.assertEqual(_state(target.getName(full=True)), expected)
                )

    def test_errors(self):
        """型の違うカーブと自分自身を拒否し、カーブを変えない。"""
        source = self.source(False)
        other = mlib.createNode("animCurveTL", name=self.name("linear"), skipSelect=True)
        other.addKey(1, 1)
        with self.assertRaises(TypeError):
            other.replaceKeys(source)
        with self.assertRaises(ValueError):
            source.replaceKeys(source)
        self.assertEqual(other.getKeyCount(), 1)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
