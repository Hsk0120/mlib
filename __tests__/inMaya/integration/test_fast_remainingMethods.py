"""これまで ``fast=True`` の結果を通常と突き合わせていなかった書き込みメソッドを、表でまとめて確かめる。

対象は ``Keyframe.remove``・``Keyframes.remove``・``VertexFace.removeColor``・``Joint.connectInverseScale``・
``Joint.setPreferredAngle``・``Nodes.setColors(outliner=True)``・``SkinCluster.transferWeights``・``Transform.addShape``。
表の各行について、次を確かめる。

- ``fast=True`` と ``fast=False`` で、同じ結果(値・接続・親子)になる。
- ``fast=True`` は Undo キューに何も載せず、``cmds.undo()`` をしても値が戻らない。
- ``fast=False`` は Undo 1 回で呼ぶ前の状態へ戻る。

``place2dTexture.connectTexture`` は ``inMaya/integration/test_fast_utilityNodes.py`` が同じ内容を確かめているので対象にしない。
"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib

mlib.reload()

from mlib.nodes import Nodes


def _rounded(value):
    """比べるために、小数を丸めた入れ子のtupleへ変える。

    Args:
        value (object): getAttr等で読んだ値。

    Returns:
        object: 丸めた値。
    """
    if isinstance(value, float):
        return round(value, 5) + 0.0
    if isinstance(value, (list, tuple)):
        return tuple(_rounded(item) for item in value)
    return value


class _FastCase(NamespaceCase):
    """専用の名前空間をカレントにして、表の各行の準備を持つ。

    各行の準備関数は ``(call, state)`` を返す。``call(fast=...)`` が対象メソッドを呼び、
    ``state()`` がノードの名前に依らない比較用の状態を返す。
    """

    PREFIX = "mlibSpecFastRemaining_"

    def setUp(self):
        super().setUp()
        cmds.namespace(setNamespace=":" + self.ns)

    def tearDown(self):
        cmds.namespace(setNamespace=":")
        super().tearDown()

    # ---- 準備 -----------------------------------------------------------------

    def keyed(self):
        """translateX に 3 つのキーを打ち、その animCurve を返す。"""
        node = cmds.createNode("transform", name="xf#", skipSelect=True)
        for time, value in ((1, 0.0), (5, 2.0), (10, 5.0)):
            cmds.setKeyframe(node, attribute="translateX", time=time, value=value, inTangentType="linear", outTangentType="linear")
        curve = mlib.getNode(cmds.listConnections(node + ".tx", type="animCurve")[0])

        def state():
            name = curve.getName(full=True)
            return _rounded((cmds.keyframe(name, query=True, timeChange=True), cmds.keyframe(name, query=True, valueChange=True)))

        return curve, state

    def r_Keyframe_remove(self):
        curve, state = self.keyed()
        return (lambda **kw: curve.getKeyframes(1).remove(**kw)), state

    def r_Keyframes_remove(self):
        curve, state = self.keyed()
        return (lambda **kw: curve.getKeyframes([0, 2]).remove(**kw)), state

    def r_VertexFace_removeColor(self):
        transform = cmds.polyCube(name="cube#", constructionHistory=False)[0]
        shape = mlib.getNode(transform).getShape()
        cmds.polyColorSet(shape.getName(full=True), create=True, colorSet="colors")
        shape.setVertexColors([(0.2, 0.3, 0.4, 0.5)] * 24, perFace=True, colorSet="colors")

        def state():
            return _rounded([face.getColor(colorSet="colors") for face in shape.getVertexFaces([0, 1, 2])])

        return (lambda **kw: shape.getVertexFaces([0])[0].removeColor(colorSet="colors", **kw)), state

    def r_Joint_connectInverseScale(self):
        parent = cmds.createNode("joint", name="jp#", skipSelect=True)
        child = cmds.createNode("joint", name="jc#", parent=parent, skipSelect=True)
        cmds.setAttr(parent + ".s", 2.0, 3.0, 4.0)
        joint = mlib.getNode(child)

        def state():
            sources = cmds.listConnections(child + ".inverseScale", source=True, destination=False, plugs=True) or []
            return tuple(source.split(":")[-1].split("|")[-1].split(".")[-1] for source in sources), _rounded(cmds.getAttr(child + ".inverseScale"))

        return (lambda **kw: joint.connectInverseScale(**kw)), state

    def r_Joint_setPreferredAngle_current(self):
        name = cmds.createNode("joint", name="jnt#", skipSelect=True)
        cmds.setAttr(name + ".r", 10.0, 20.0, 30.0)
        joint = mlib.getNode(name)
        return (lambda **kw: joint.setPreferredAngle(**kw)), (lambda: _rounded(cmds.getAttr(name + ".preferredAngle")))

    def r_Joint_setPreferredAngle_value(self):
        name = cmds.createNode("joint", name="jnt#", skipSelect=True)
        joint = mlib.getNode(name)
        return (lambda **kw: joint.setPreferredAngle((5.0, -15.0, 25.0), **kw)), (lambda: _rounded(cmds.getAttr(name + ".preferredAngle")))

    def r_Nodes_setOutlinerColors(self):
        names = [cmds.createNode("transform", name="xf#", skipSelect=True) for _ in range(2)]
        nodes = Nodes(names)

        def state():
            return tuple(_rounded((cmds.getAttr(name + ".useOutlinerColor"), cmds.getAttr(name + ".outlinerColor"))) for name in names)

        return (lambda **kw: nodes.setColors([(1.0, 0.5, 0.0), (0.0, 1.0, 0.0)], **kw, outliner=True)), state

    def r_SkinCluster_transferWeights(self):
        mesh = cmds.ls(cmds.polyCube(name="skinMesh#", subdivisionsY=2, constructionHistory=False)[0], long=True)[0]
        cmds.select(clear=True)
        j0 = cmds.joint(name="sj#", position=(0, -0.5, 0))
        j1 = cmds.joint(name="sj#", position=(0, 0.5, 0))
        cmds.select(clear=True)
        name = cmds.skinCluster(j0, j1, mesh, toSelectedBones=True, name="skin#")[0]
        skin = mlib.getNode(name)
        count = cmds.polyEvaluate(mesh, vertex=True)

        def state():
            return tuple(_rounded(cmds.skinPercent(name, f"{mesh}.vtx[{index}]", query=True, value=True)) for index in range(count))

        return (lambda **kw: skin.transferWeights([(mlib.getNode(j1), mlib.getNode(j0))], **kw)), state

    def r_Transform_addShape(self):
        receiver = cmds.ls(cmds.curve(name="crv#", degree=1, point=[(0, 0, 0), (1, 0, 0), (1, 1, 0)]), long=True)[0]
        source = cmds.ls(cmds.curve(name="src#", degree=1, point=[(0, 0, 0), (0, 2, 0)]), long=True)[0]
        cmds.setAttr(source + ".tx", 2.0)
        moved = mlib.getNode(source).getShape()
        node = mlib.getNode(receiver)

        def state():
            shapes = [len(cmds.listRelatives(parent, shapes=True) or []) for parent in (receiver, source)]
            parent = cmds.listRelatives(moved.getName(full=True), parent=True, fullPath=True)[0]
            return tuple(shapes), parent == receiver, _rounded(cmds.xform(moved.getName(full=True) + ".cv[*]", query=True, translation=True, worldSpace=True))

        return (lambda **kw: node.addShape(moved, **kw)), state

    def rows(self):
        """表の全行を (ラベル, 準備関数) で返す。"""
        return [(name[len("r_") :], getattr(self, name)) for name in sorted(dir(self)) if name.startswith("r_")]


class FastRemainingTest(_FastCase):
    """表の各行で、fast と通常の結果・Undo を確かめる。"""

    def run_normal(self, build):
        """通常の経路で呼び、呼ぶ前・後の状態を返す。Undo 1 回で戻ることも確かめる。"""
        call, state = build()
        self.flushUndo()
        before = state()
        call(fast=False)
        after = state()
        self.assertNotEqual(after, before, "呼んでも何も変わっていない(表を見直す)")
        cmds.undo()
        self.assertEqual(state(), before, "通常の経路が Undo 1 回で戻らない")
        return before, after

    def test_fast_matches_normal(self):
        """fast=True は通常と同じ結果になる。"""
        for label, build in self.rows():
            with self.subTest(label):
                _before, expected = self.run_normal(build)
                call, state = build()
                call(fast=True)
                self.assertEqual(state(), expected)

    def test_fast_records_no_undo(self):
        """fast=True は Undo キューに何も載せず、cmds.undo() でも戻らない。

        空のキューへの cmds.undo() は例外になるので、先に別の操作(transform の作成)を1つ載せておき、
        cmds.undo() がその操作だけを戻すことを確かめる。
        """
        for label, build in self.rows():
            with self.subTest(label):
                call, state = build()
                self.flushUndo()
                marker = cmds.createNode("transform", name="undoMarker#", skipSelect=True)
                marker_name = cmds.undoInfo(query=True, undoName=True)
                before = state()
                call(fast=True)
                after = state()
                self.assertNotEqual(after, before)
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), marker_name)
                cmds.undo()
                self.assertFalse(cmds.objExists(marker))
                self.assertEqual(state(), after)

    def test_normal_undoes_in_one_step(self):
        """fast=False は Undo 1 回で呼ぶ前の状態へ戻る。"""
        for label, build in self.rows():
            with self.subTest(label):
                self.run_normal(build)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
