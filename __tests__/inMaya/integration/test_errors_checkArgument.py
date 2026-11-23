"""書き込むメソッドの ``check=True`` の約束を、表でまとめて確かめる。

``check=True`` は、書き込む前に「値が有限か・書き込めるか(ロック・入力の接続)」を確かめ、
だめなら型付きの例外を出して何も書かない。既定の ``check=False`` はその検査をしない。
表の各行(メソッド)について、通常と ``fast=True`` の両方で次を確かめる。

- 無限大・NaN を渡すと、docstring の Raises の型(ValueError)の例外になり、シーンが変わらない。
- 書き込む先の一部をロックすると RuntimeError になり、ロックしていない成分・要素も書き換えない。
- 正しい値なら、``check=True`` でも ``check=False`` と同じ結果になる。

ロックは、後ろに書く成分・要素(または書き込む先の一部)へ付けて、途中まで書いてから止まらないことを確かめる。

ほかのテストで ``check=True`` を確かめているメソッド(``Plug.set``・``setPivot``・``setColor`` など)は対象にしない。
"""

import math
import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib

mlib.reload()

from mlib.common.drivenKey import DrivenKey
from mlib.nodes import Joints, Nodes

#: 有限でない値(NaN)。
NAN = float("nan")
#: 有限でない値(無限大)。
INF = float("inf")


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
    if isinstance(value, dict):
        return tuple(sorted((key, _rounded(item)) for key, item in value.items()))
    return value


def _attrs(node, *names):
    """ノードのアトリビュートの値を、丸めたtupleで返す。"""
    return tuple(_rounded(cmds.getAttr(node + "." + name)) for name in names)


class Case:
    """表の1行。

    Attributes:
        call (callable): ``call(value, **kwargs)`` で対象メソッドを呼ぶ。kwargs は check・fast。
        good (object): 正しい値。
        bad (object | None): 有限でない値。None なら有限か確かめる項目を省く。
        lock (callable | None): 書き込む先の一部をロックする。None ならロックの項目を省く。
        state (callable): 比べる状態を返す。
        modes (tuple[bool, ...]): 確かめる fast の値。
    """

    def __init__(self, call, good, state, bad=None, lock=None, modes=(False, True)):
        self.call = call
        self.good = good
        self.state = state
        self.bad = bad
        self.lock = lock
        self.modes = modes


class _CheckCase(NamespaceCase):
    """専用の名前空間をカレントにして、表の各行の準備を持つ。"""

    PREFIX = "mlibSpecCheckArg_"

    @staticmethod
    def points(component):
        """コンポーネントのオブジェクト空間の位置を、丸めたtupleで返す。"""
        return _rounded(cmds.xform(component, query=True, translation=True, objectSpace=True))

    @staticmethod
    def curve_state(curve):
        """animCurve のキーの入力・値・接線の型を返す。"""
        name = curve.getFullName()
        return _rounded(
            (
                cmds.keyframe(name, query=True, floatChange=True) or cmds.keyframe(name, query=True, timeChange=True),
                cmds.keyframe(name, query=True, valueChange=True),
                cmds.keyTangent(name, query=True, inTangentType=True),
                cmds.keyTangent(name, query=True, outTangentType=True),
                cmds.keyTangent(name, query=True, outAngle=True),
            )
        )

    @staticmethod
    def lock_keys(curve):
        """キーを格納する keyTimeValue をロックする。"""
        cmds.setAttr(curve.getFullName() + ".keyTimeValue", lock=True)

    @staticmethod
    def item(blend):
        """ターゲット 0 の本体の項目のアトリビュート名を返す。"""
        return blend.getFullName() + ".inputTarget[0].inputTargetGroup[0].inputTargetItem[6000]"

    @staticmethod
    def vertex_weights(skin, mesh, indices=(0, 1, 2)):
        """頂点ごとのウェイトを返す。"""
        return tuple(_rounded(cmds.skinPercent(skin.getFullName(), f"{mesh}.vtx[{index}]", query=True, value=True)) for index in indices)

    def setUp(self):
        super().setUp()
        cmds.namespace(setNamespace=":" + self.ns)

    def tearDown(self):
        cmds.namespace(setNamespace=":")
        super().tearDown()

    # ---- 共通の準備 -----------------------------------------------------------
    def xf(self):
        """t=(1,2,3)・r=(10,20,30) の transform を作る。"""
        name = cmds.ls(cmds.createNode("transform", name="xf#", skipSelect=True), long=True)[0]
        cmds.setAttr(name + ".t", 1.0, 2.0, 3.0)
        cmds.setAttr(name + ".r", 10.0, 20.0, 30.0)
        return name

    def xf_state(self, name):
        """transform のチャンネル・ピボット・offsetParentMatrix を返す。"""
        return _attrs(name, "t", "r", "s", "sh", "ro", "rp", "sp", "rpt", "spt", "ra", "offsetParentMatrix")

    def cube(self):
        """履歴なしの polyCube の (transform, shape) を返す。"""
        transform = cmds.ls(cmds.polyCube(name="cube#", constructionHistory=False)[0], long=True)[0]
        return transform, cmds.listRelatives(transform, shapes=True, fullPath=True)[0]

    def curve(self):
        """CV 3 個の 1 次 nurbsCurve の (transform, shape) を返す。"""
        transform = cmds.ls(cmds.curve(name="crv#", degree=1, point=[(0, 0, 0), (1, 0, 0), (1, 1, 0)]), long=True)[0]
        return transform, cmds.listRelatives(transform, shapes=True, fullPath=True)[0]

    def joint(self, text="jnt#"):
        """親の無い joint を作る。"""
        return cmds.ls(cmds.createNode("joint", name=text, skipSelect=True), long=True)[0]

    def keyed(self):
        """translateX にキーを 3 つ打った transform と、その animCurve を返す。"""
        node = self.xf()
        for time, value in ((1, 0.0), (5, 2.0), (10, 5.0)):
            cmds.setKeyframe(node, attribute="translateX", time=time, value=value)
        return node, mlib.getNode(cmds.listConnections(node + ".tx", type="animCurve")[0])

    def blend(self, baked=False):
        """ターゲット 1 つの blendShape を作る。baked なら形状の接続を外してデルタを書く。"""
        base, target = (cmds.ls(cmds.polyCube(name=text, constructionHistory=False)[0], long=True)[0] for text in ("base#", "target#"))
        cmds.setAttr(target + ".vtx[0]", 0.0, 1.0, 0.0)
        blend = mlib.getNode(cmds.blendShape(target, base, name="blend#", frontOfChain=True)[0])
        if baked:
            plug = blend.getFullName() + ".inputTarget[0].inputTargetGroup[0].inputTargetItem[6000].inputGeomTarget"
            cmds.disconnectAttr(cmds.listConnections(plug, source=True, plugs=True)[0], plug)
            blend.setTargetDeltas(0, {0: (0.0, 1.0, 0.0), 1: (0.0, 0.1, 0.0), 2: (0.0, 0.0, 2.0)})
        return blend

    def item_state(self, blend):
        """項目のデルタと頂点の一覧を返す。"""
        item = self.item(blend)
        return _rounded((cmds.getAttr(item + ".inputPointsTarget"), cmds.getAttr(item + ".inputComponentsTarget")))

    def skin(self, uneven=False):
        """2 段の cube を 2 つの joint へバインドした (skinCluster, mesh, joints) を返す。"""
        mesh = cmds.ls(cmds.polyCube(name="skinMesh#", subdivisionsY=2, constructionHistory=False)[0], long=True)[0]
        cmds.select(clear=True)
        j0 = cmds.ls(cmds.joint(name="sj#", position=(0, -0.5, 0)), long=True)[0]
        j1 = cmds.ls(cmds.joint(name="sj#", position=(0, 0.5, 0)), long=True)[0]
        cmds.select(clear=True)
        name = cmds.skinCluster(j0, j1, mesh, toSelectedBones=True, name="skin#")[0]
        if uneven:
            cmds.setAttr(name + ".weightList[0].weights[0]", 0.9)
            cmds.setAttr(name + ".weightList[0].weights[1]", 0.1)
        cmds.select(clear=True)
        return mlib.getNode(name), mesh, (mlib.getNode(j0), mlib.getNode(j1))

    # ---- 表 -------------------------------------------------------------------
    def cases(self):
        """表の全行を (ラベル, 準備関数) で返す。準備関数は Case を返す。"""
        return [(name[len("c_") :], getattr(self, name)) for name in sorted(dir(self)) if name.startswith("c_")]

    def c_Transform_setTranslation(self):
        return self._xf_case("setTranslation", (4.0, 5.0, 6.0), (NAN, 0.0, 0.0), "tz")

    def c_Transform_setRotate(self):
        return self._xf_case("setRotate", (15.0, 25.0, 35.0), (0.0, INF, 0.0), "rz")

    def c_Transform_setScale(self):
        return self._xf_case("setScale", (2.0, 3.0, 4.0), (INF, 1.0, 1.0), "sz")

    def c_Transform_setShear(self):
        return self._xf_case("setShear", (0.1, 0.2, 0.3), (0.1, NAN, 0.3), "shearYZ")

    def c_Transform_setMatrix(self):
        good = [2.0, 0, 0, 0, 0, 2.0, 0, 0, 0, 0, 2.0, 0, 4.0, 5.0, 6.0, 1.0]
        bad = list(good)
        bad[12] = NAN
        return self._xf_case("setMatrix", good, bad, "tz")

    def c_Transform_setQuaternion(self):
        half = math.sqrt(0.5)
        return self._xf_case("setQuaternion", (0.0, half, 0.0, half), (NAN, 0.0, 0.0, 1.0), "rz")

    def c_Transform_setOffsetParentMatrix(self):
        good = [1.0, 0, 0, 0, 0, 1.0, 0, 0, 0, 0, 1.0, 0, 4.0, 5.0, 6.0, 1.0]
        bad = list(good)
        bad[13] = INF
        return self._xf_case("setOffsetParentMatrix", good, bad, "offsetParentMatrix")

    def c_Transform_mirrorTransform(self):
        node = self.xf()
        target = mlib.getNode(node)
        return Case(
            call=lambda value, **kw: target.mirrorTransform("x", pivot=value, **kw),
            good=(0.5, 0.0, 0.0),
            bad=(NAN, 0.0, 0.0),
            lock=lambda: cmds.setAttr(node + ".rz", lock=True),
            state=lambda: self.xf_state(node),
        )

    def c_Transform_setPivot_translation(self):
        case = self._xf_case("setPivot", (1.0, 2.0, 3.0), (1.0, 2.0, NAN), "rotatePivotTranslateZ", translation=True)
        case.modes = (False,)
        return case

    def c_Transform_setTransformation(self):
        node = self.xf()
        target = mlib.getNode(node)
        value = mlib.Transformation(rotateOrder=2, translate=(4.0, 5.0, 6.0), rotate=(0.1, 0.2, 0.3), scale=(2.0, 3.0, 4.0), rotatePivot=(0.5, 0.0, 1.0))
        return Case(
            call=lambda value, **kw: target.setTransformation(value, **kw),
            good=value,
            lock=lambda: cmds.setAttr(node + ".tz", lock=True),
            state=lambda: self.xf_state(node),
        )

    def c_DagNode_setVisibility(self):
        return self._display_case("setVisibility", False, "visibility", ("visibility",))

    def c_DagNode_setDisplayType(self):
        return self._display_case("setDisplayType", "template", "overrideDisplayType", ("overrideEnabled", "overrideDisplayType"))

    def c_DagNode_setShadingOverride(self):
        return self._display_case("setShadingOverride", True, "overrideShading", ("overrideEnabled", "overrideShading"))

    def c_Nodes_setVisibility(self):
        return self._pair_case("setVisibility", False, "visibility", ("visibility",))

    def c_Nodes_setColors(self):
        return self._pair_case("setColors", [13, 17], "overrideColor", ("overrideEnabled", "overrideRGBColors", "overrideColor"))

    def c_Nodes_setColors_outliner(self):
        return self._pair_case(
            "setColors",
            [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            "outlinerColor",
            ("useOutlinerColor", "outlinerColor"),
            bad=[(1.0, 0.0, 0.0), (NAN, 1.0, 0.0)],
            outliner=True,
        )

    def c_Nodes_resetAttrs(self):
        return self._pair_case("resetAttrs", ["tx", "ty"], "ty", ("tx", "ty"))

    def c_Joint_setSegmentScaleCompensate(self):
        return self._joint_case("setSegmentScaleCompensate", False, "segmentScaleCompensate", ("segmentScaleCompensate",))

    def c_Joint_setRadius(self):
        return self._joint_case("setRadius", 2.5, "radius", ("radius",), bad=NAN)

    def c_Joint_setPreferredAngle(self):
        return self._joint_case("setPreferredAngle", (5.0, 15.0, 25.0), "preferredAngleZ", ("preferredAngle",), bad=(0.0, NAN, 0.0))

    def c_Joint_resetAttrs(self):
        return self._joint_case("resetAttrs", ["rx", "ry"], "ry", ("rx", "ry"))

    def c_Node_resetAttrs(self):
        node = self.xf()
        target = mlib.getNode(node)
        return Case(
            call=lambda value, **kw: target.resetAttrs(value, **kw),
            good=["tx", "ty"],
            lock=lambda: cmds.setAttr(node + ".ty", lock=True),
            state=lambda: _attrs(node, "tx", "ty"),
        )

    def c_Joints_setRadius(self):
        return self._joints_case("setRadius", 2.5, "radius", ("radius",), bad=INF)

    def c_Joints_setSegmentScaleCompensate(self):
        return self._joints_case("setSegmentScaleCompensate", False, "segmentScaleCompensate", ("segmentScaleCompensate",))

    # そのほかのノード・Plug。
    def c_Locator_setPosition(self):
        transform = cmds.ls(cmds.spaceLocator(name="loc#")[0], long=True)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        locator = mlib.getNode(shape)
        return Case(
            call=lambda value, **kw: locator.setPosition(value, **kw),
            good=(1.0, 2.0, 3.0),
            bad=(1.0, NAN, 3.0),
            lock=lambda: cmds.setAttr(shape + ".localPositionZ", lock=True),
            state=lambda: _attrs(shape, "localPosition"),
        )

    def c_Plug_setIfChanged(self):
        node = self.xf()
        plug = mlib.getPlug(node + ".tx")
        return Case(
            call=lambda value, **kw: plug.setIfChanged(value, **kw),
            good=4.0,
            bad=NAN,
            lock=lambda: cmds.setAttr(node + ".tx", lock=True),
            state=lambda: _attrs(node, "tx"),
        )

    def c_Plug_reset(self):
        node = self.xf()
        plug = mlib.getPlug(node + ".translate")
        return Case(
            call=lambda _value, **kw: plug.reset(**kw), good=None, lock=lambda: cmds.setAttr(node + ".tz", lock=True), state=lambda: _attrs(node, "translate")
        )

    def c_Constraint_setWeight(self):
        a, b, c = self.xf(), self.xf(), self.xf()
        name = cmds.parentConstraint(a, b, c, name="pcon#")[0]
        aliases = cmds.parentConstraint(name, query=True, weightAliasList=True)
        node = mlib.getNode(name)
        return Case(
            call=lambda value, **kw: node.setWeight(value, **kw),
            good=0.5,
            bad=NAN,
            lock=lambda: cmds.setAttr(name + "." + aliases[1], lock=True),
            state=lambda: _attrs(name, *aliases),
        )

    def c_PointComponent_setPosition(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertex(0).setPosition(value, **kw), (1.0, 2.0, 3.0), (1.0, 2.0, NAN))

    def c_PointComponent_setPosition_axisX(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertex(0).setPosition(value, axis="x", **kw), 2.0, NAN)

    def c_PointComponent_setPosition_axisY(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertex(0).setPosition(value, axis="y", **kw), 2.0, INF)

    def c_PointComponent_setPosition_axisZ(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertex(0).setPosition(value, axis="z", **kw), 2.0, NAN)

    def c_PointComponent_setPosition_relative(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertex(0).setPosition(value, relative=True, **kw), (1.0, 0.0, 0.0), (NAN, 0.0, 0.0))

    def c_PointComponents_setPosition_axisX(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertices([1, 0]).setPosition(value, axis="x", **kw), 2.0, NAN)

    def c_PointComponents_setPosition_axisY_each(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertices([1, 0]).setPosition(value, axis="y", each=True, **kw), [2.0, 3.0], [2.0, NAN])

    def c_PointComponents_setPosition_axisZ(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertices([1, 0]).setPosition(value, axis="z", **kw), 2.0, INF)

    def c_PointComponents_setPosition(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertices([1, 0]).setPosition(value, **kw), (1.0, 2.0, 3.0), (NAN, 2.0, 3.0))

    def c_PointComponents_setPosition_each(self):
        return self._vertex_case(
            lambda mesh, value, **kw: mesh.getVertices([1, 0]).setPosition(value, each=True, **kw),
            [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            [(1.0, 0.0, 0.0), (0.0, NAN, 0.0)],
        )

    def c_PointComponents_mirror(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertices([1, 0]).mirror("x", pivot=value, **kw), (0.25, 0.0, 0.0), (NAN, 0.0, 0.0))

    def c_PointComponents_setPosition_relative(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.getVertices([1, 0]).setPosition(value, relative=True, **kw), (0.0, 1.0, 0.0), (0.0, INF, 0.0))

    def c_Mesh_setPoints(self):
        good = [(x * 2.0, y * 2.0, z * 2.0) for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5)]
        bad = list(good)
        bad[0] = (NAN, 0.0, 0.0)
        return self._vertex_case(lambda mesh, value, **kw: mesh.setPoints(value, **kw), good, bad)

    def c_Mesh_mirror(self):
        return self._vertex_case(lambda mesh, value, **kw: mesh.mirror("x", pivot=value, **kw), (0.25, 0.0, 0.0), (NAN, 0.0, 0.0))

    def c_Transform_mirrorGeometry(self):
        transform, shape = self.cube()
        node = mlib.getNode(transform)
        return Case(
            call=lambda value, **kw: node.mirrorGeometry("x", pivot=value, **kw),
            good=(0.25, 0.0, 0.0),
            bad=(NAN, 0.0, 0.0),
            lock=lambda: cmds.setAttr(shape + ".pnts[0].pntx", lock=True),
            state=lambda: self.points(shape + ".vtx[*]"),
        )

    def c_NurbsCurve_setCvPositions(self):
        return self._curve_case(
            lambda curve, value, **kw: curve.setCvPositions(value, **kw),
            [(0.0, 1.0, 0.0), (1.0, 1.0, 0.0), (2.0, 2.0, 0.0)],
            [(0.0, 1.0, 0.0), (1.0, NAN, 0.0), (2.0, 2.0, 0.0)],
        )

    def c_NurbsCurve_mirror(self):
        return self._curve_case(lambda curve, value, **kw: curve.mirror("y", pivot=value, **kw), (0.0, 1.0, 0.0), (0.0, INF, 0.0))

    def c_NurbsSurface_setCvPositions(self):
        transform = cmds.ls(cmds.nurbsPlane(name="srf#", constructionHistory=False)[0], long=True)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        surface = mlib.getNode(shape)
        good = [(x + 0.5, 1.0, z) for x, _y, z in surface.getCvPositions()]
        bad = list(good)
        bad[3] = (NAN, 1.0, 0.0)
        return Case(
            call=lambda value, **kw: surface.setCvPositions(value, **kw),
            good=good,
            bad=bad,
            lock=lambda: cmds.setAttr(shape + ".controlPoints[0].xValue", lock=True),
            state=lambda: self.points(shape + ".cv[*][*]"),
        )

    def c_VertexFace_setNormal(self):
        _transform, shape = self.cube()
        mesh = mlib.getNode(shape)
        return Case(
            call=lambda value, **kw: mesh.getVertexFaces([0])[0].setNormal(value, **kw),
            good=(1.0, 2.0, 3.0),
            bad=(NAN, 0.0, 1.0),
            state=lambda: _rounded(cmds.polyNormalPerVertex(shape + ".vtxFace[0][0]", query=True, xyz=True)),
        )

    def c_AnimCurve_setKey(self):
        return self._key_case(lambda curve, value, **kw: curve.setKey(5, value, **kw), 3.0, NAN)

    def c_AnimCurve_addKeys(self):
        return self._key_case(lambda curve, value, **kw: curve.addKeys([{"input": 7, "value": value}], **kw), 3.0, NAN, modes=(False,))

    def c_AnimCurve_removeKey(self):
        return self._key_case(lambda curve, value, **kw: curve.removeKey(time=value, **kw), 5, NAN)

    def c_AnimCurve_setTangent(self):
        return self._key_case(lambda curve, value, **kw: curve.setTangent(1, **value, **kw), {"inTangentType": "flat", "outTangentType": "flat"})

    def c_Keyframe_setValue(self):
        return self._key_case(lambda curve, value, **kw: curve.getKeyframe(1).setValue(value, **kw), 3.0, NAN)

    def c_Keyframe_setTangent(self):
        return self._key_case(lambda curve, value, **kw: curve.getKeyframe(1).setTangent(**value, **kw), {"inTangentType": "flat", "outTangentType": "flat"})

    def c_Keyframes_setValue(self):
        return self._key_case(lambda curve, value, **kw: curve.getKeyframes([0, 1]).setValue(value, **kw), 3.0, INF)

    def c_Keyframes_setTangent(self):
        return self._key_case(
            lambda curve, value, **kw: curve.getKeyframes([0, 1]).setTangent(**value, **kw), {"inTangentType": "flat", "outTangentType": "flat"}
        )

    def c_DrivenKey_setKey(self):
        driver, driven = self.xf(), self.xf()
        key = DrivenKey(mlib.getPlug(driver + ".tx"), mlib.getPlug(driven + ".ty"))

        def state():
            curves = cmds.listConnections(driven + ".ty", source=True, destination=False) or []
            keys = [_rounded(cmds.keyframe(curve, query=True, floatChange=True, valueChange=True)) for curve in curves]
            return _attrs(driven, "ty"), tuple(keys)

        return Case(call=lambda value, **kw: key.setKey(1.0, value, **kw), good=2.0, bad=NAN, lock=lambda: cmds.setAttr(driven + ".ty", lock=True), state=state)

    # デフォーマーのウェイトとデルタ。
    def c_BlendShape_setTargetWeights(self):
        blend = self.blend()
        group = blend.getFullName() + ".inputTarget[0].inputTargetGroup[0].targetWeights"

        def lock():
            cmds.setAttr(group + "[2]", 1.0)
            cmds.setAttr(group + "[2]", lock=True)

        return Case(
            call=lambda value, **kw: blend.setTargetWeights(0, value, **kw),
            good={1: 0.5, 2: 0.25},
            bad={1: 0.5, 2: NAN},
            lock=lock,
            state=lambda: tuple(_rounded(cmds.getAttr(f"{group}[{index}]")) for index in (1, 2)),
        )

    def c_BlendShape_setTargetDeltas(self):
        return self._delta_case(
            lambda blend, value, **kw: blend.setTargetDeltas(0, value, **kw), {0: (0.0, 2.0, 0.0), 3: (1.0, 0.0, 0.0)}, {0: (0.0, NAN, 0.0)}
        )

    def c_BlendShape_resetTargetVertices(self):
        return self._delta_case(lambda blend, value, **kw: blend.resetTargetVertices(0, value, **kw), [0, 1])

    def c_BlendShape_reduceTargetDeltas(self):
        return self._delta_case(lambda blend, value, **kw: blend.reduceTargetDeltas(0, tolerance=value, **kw), 0.5, NAN)

    def c_GeometryFilter_setDeformerWeights(self):
        transform, _shape = self.cube()
        cmds.cluster(transform, name="cluster#")
        cluster = mlib.getNode(cmds.ls(cmds.listHistory(transform), type="cluster", long=True)[0])
        weights = cluster.getFullName() + ".weightList[0].weights"

        def lock():
            cmds.setAttr(weights + "[3]", 1.0)
            cmds.setAttr(weights + "[3]", lock=True)

        return Case(
            call=lambda value, **kw: cluster.setDeformerWeights(value, vertices=[0, 3], **kw),
            good=[0.25, 0.5],
            bad=[0.25, NAN],
            lock=lock,
            state=lambda: tuple(_rounded(cmds.getAttr(f"{weights}[{index}]")) for index in (0, 3)),
        )

    def c_SkinCluster_pruneWeights(self):
        skin, mesh, _joints = self.skin(uneven=True)
        return Case(
            call=lambda value, **kw: skin.pruneWeights(value, **kw),
            good=0.2,
            bad=NAN,
            lock=lambda: cmds.setAttr(skin.getFullName() + ".weightList[0].weights[0]", lock=True),
            state=lambda: self.vertex_weights(skin, mesh),
        )

    def c_SkinCluster_setVertexWeights(self):
        skin, mesh, joints = self.skin()
        return Case(
            call=lambda value, **kw: skin.setWeights({joints[0]: value}, vertex=0, normalize=True, **kw),
            good=0.3,
            bad=NAN,
            lock=lambda: cmds.setAttr(skin.getFullName() + ".weightList[0].weights[1]", lock=True),
            state=lambda: self.vertex_weights(skin, mesh),
        )

    def c_SkinCluster_setBlendWeights(self):
        skin, _mesh, _joints = self.skin()
        blend = skin.getFullName() + ".blendWeights"

        def lock():
            cmds.setAttr(blend + "[1]", 0.0)
            cmds.setAttr(blend + "[1]", lock=True)

        return Case(
            call=lambda value, **kw: skin.setBlendWeights(value, vertices=[0, 1], **kw),
            good=[0.25, 0.5],
            bad=[0.25, NAN],
            lock=lock,
            state=lambda: tuple(_rounded(cmds.getAttr(f"{blend}[{index}]")) for index in (0, 1)),
        )

    # Transform の値の設定。
    def _xf_case(self, method, good, bad, locked, **extra):
        node = self.xf()
        target = mlib.getNode(node)
        return Case(
            call=lambda value, **kw: getattr(target, method)(value, **extra, **kw),
            good=good,
            bad=bad,
            lock=lambda: cmds.setAttr(node + "." + locked, lock=True),
            state=lambda: self.xf_state(node),
        )

    # 表示の設定。
    def _display_case(self, method, good, locked, read):
        node = self.xf()
        target = mlib.getNode(node)
        return Case(
            call=lambda value, **kw: getattr(target, method)(value, **kw),
            good=good,
            lock=lambda: cmds.setAttr(node + "." + locked, lock=True),
            state=lambda: _attrs(node, *read),
        )

    def _pair_case(self, method, good, locked, read, bad=None, **extra):
        names = [self.xf(), self.xf()]
        nodes = Nodes(names)
        return Case(
            call=lambda value, **kw: getattr(nodes, method)(value, **extra, **kw),
            good=good,
            bad=bad,
            lock=lambda: cmds.setAttr(names[1] + "." + locked, lock=True),
            state=lambda: tuple(_attrs(name, *read) for name in names),
        )

    # Joint。
    def _joint_case(self, method, good, locked, read, bad=None):
        name = self.joint()
        cmds.setAttr(name + ".r", 10.0, 20.0, 30.0)
        joint = mlib.getNode(name)
        return Case(
            call=lambda value, **kw: getattr(joint, method)(value, **kw),
            good=good,
            bad=bad,
            lock=lambda: cmds.setAttr(name + "." + locked, lock=True),
            state=lambda: _attrs(name, *read),
        )

    def _joints_case(self, method, good, locked, read, bad=None):
        names = [self.joint(), self.joint()]
        joints = Joints(names)
        return Case(
            call=lambda value, **kw: getattr(joints, method)(value, **kw),
            good=good,
            bad=bad,
            lock=lambda: cmds.setAttr(names[1] + "." + locked, lock=True),
            state=lambda: tuple(_attrs(name, *read) for name in names),
        )

    # 頂点・CV の位置。
    def _vertex_case(self, call, good, bad, lock_index=0):
        _transform, shape = self.cube()
        mesh = mlib.getNode(shape)
        return Case(
            call=lambda value, **kw: call(mesh, value, **kw),
            good=good,
            bad=bad,
            lock=lambda: cmds.setAttr(f"{shape}.pnts[{lock_index}].pntx", lock=True),
            state=lambda: self.points(shape + ".vtx[*]"),
        )

    def _curve_case(self, call, good, bad):
        _transform, shape = self.curve()
        curve = mlib.getNode(shape)
        return Case(
            call=lambda value, **kw: call(curve, value, **kw),
            good=good,
            bad=bad,
            lock=lambda: cmds.setAttr(shape + ".controlPoints[0].xValue", lock=True),
            state=lambda: self.points(shape + ".cv[*]"),
        )

    # キー。
    def _key_case(self, call, good, bad=None, modes=(False, True)):
        _node, curve = self.keyed()
        return Case(
            call=lambda value, **kw: call(curve, value, **kw),
            good=good,
            bad=bad,
            lock=lambda: self.lock_keys(curve),
            state=lambda: self.curve_state(curve),
            modes=modes,
        )

    def _delta_case(self, call, good, bad=None):
        blend = self.blend(baked=True)
        return Case(
            call=lambda value, **kw: call(blend, value, **kw),
            good=good,
            bad=bad,
            lock=lambda: cmds.setAttr(self.item(blend) + ".inputPointsTarget", lock=True),
            state=lambda: self.item_state(blend),
        )


class CheckArgumentTest(_CheckCase):
    """表の各行で、check=True の検査と、正しい値の結果を確かめる。"""

    def test_nonfinite_rejected_without_change(self):
        """check=True に有限でない値を渡すと ValueError で、シーンを変えない。"""
        for label, build in self.cases():
            for fast in build().modes:
                case = build()
                if case.bad is None:
                    continue
                with self.subTest(label, fast=fast):
                    before = case.state()
                    with self.assertRaises(ValueError):
                        case.call(case.bad, check=True, fast=fast) if case.modes != (False,) else case.call(case.bad, check=True)
                    self.assertEqual(case.state(), before)

    def test_locked_rejected_without_change(self):
        """check=True は、書き込む先の一部がロックされていれば RuntimeError で、ほかの成分・要素も書き換えない。"""
        for label, build in self.cases():
            for fast in build().modes:
                case = build()
                if case.lock is None:
                    continue
                with self.subTest(label, fast=fast):
                    case.lock()
                    before = case.state()
                    with self.assertRaises(RuntimeError):
                        case.call(case.good, check=True, fast=fast) if case.modes != (False,) else case.call(case.good, check=True)
                    self.assertEqual(case.state(), before)

    def test_valid_value_matches_unchecked(self):
        """正しい値なら、check=True は check=False と同じ結果になる。"""
        for label, build in self.cases():
            for fast in build().modes:
                with self.subTest(label, fast=fast):
                    results = []
                    for check in (False, True):
                        case = build()
                        kwargs = {"check": check} if case.modes == (False,) else {"check": check, "fast": fast}
                        before = case.state()
                        case.call(case.good, **kwargs)
                        results.append(case.state())
                    self.assertNotEqual(results[0], before, "正しい値で何も変わっていない(表の値を見直す)")
                    self.assertEqual(results[1], results[0])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
