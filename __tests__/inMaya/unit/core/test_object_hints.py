"""``core/object.py`` の似た名前の案内(``_MEMBER_HINTS``)を1件ずつ確かめる。

- 表の全件を、案内が出るオブジェクト(間違えた名前を持たず、案内先を持つクラス)で参照し、
  AttributeError の文言に案内の文が入り、案内先のメソッドが実在することを確かめる。
- 案内の文に書いた呼び方を実際に実行し、間違えた名前が意味する結果(cmds で読んだ値)になることを確かめる。
- 案内が出ない名前・書いた呼び方では例外になる組は、本体との食い違いとして ``UNREACHABLE``・``BROKEN`` に書き、
  まだ食い違っていることを確かめる(直ったら表から外す)。
"""

import math
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.core.object import _MEMBER_HINTS
from mlib.plugs import Plug

#: 案内が出るオブジェクトが無い名前。直ったら外す(今は無い)。
UNREACHABLE = {}
#: 案内が出るが、案内の文に書いた呼び方が例外になる組。キーは (名前, 見本のラベル)。直ったら外す(今は無い)。
BROKEN = {}


def _entry(cls, hint):
    """クラスに出る案内の (案内先, 文) を返す。出なければ None。"""
    entries = hint if isinstance(hint[0], tuple) else (hint,)
    for required, text in entries:
        if required is None or hasattr(cls, required):
            return required, text
    return None


def _full(obj):
    return cmds.ls(str(obj), long=True)[0]


class ObjectHintTest(NamespaceCase):
    """見本のシーンを作り、案内ごとに文言と案内先の呼び方を確かめる。"""

    PREFIX = "mlibSpecObjectHints_"
    UNLOCK_NODES = True

    def setUp(self):
        super().setUp()
        self.baseline = set(cmds.ls(uuid=True))
        self.root = mlib.getNode(self.make("transform", "root"))
        self.child = mlib.getNode(self.make("transform", "child", parent=str(self.root)))
        self.other = mlib.getNode(self.make("transform", "other"))
        self.joint = mlib.getNode(self.make("joint", "joint"))
        self.tip = mlib.getNode(self.make("joint", "tip", parent=str(self.joint)))
        cmds.setAttr(str(self.tip) + ".translate", 1.0, 0.5, 0.0)
        self.mesh = mlib.createPoly("cube", name=self.name("cube"))
        self.skin = mlib.bindSkin([self.joint], self.mesh.getTransform(), name=self.name("skin"))
        cmds.setKeyframe(str(self.child) + ".translateX", time=1, value=1.0)
        cmds.setKeyframe(str(self.child) + ".translateX", time=5, value=3.0)
        self.curve = mlib.getNode(cmds.listConnections(str(self.child) + ".translateX", source=True)[0])
        self.pose = mlib.createDagPose([self.child], name=self.name("pose"))
        for node in (self.child, self.joint, self.mesh, self.skin, self.curve, self.pose):
            cmds.addAttr(str(node), longName="hintValue", attributeType="double", keyable=True)
        self.samples = {
            "transform": self.child,
            "joint": self.joint,
            "mesh": self.mesh,
            "skinCluster": self.skin,
            "animCurve": self.curve,
            "dagPose": self.pose,
            "plug": self.other.getPlug("translateY"),
            "compoundPlug": self.other.getPlug("translate"),
        }

    def tearDown(self):
        # 名前空間の外にできたノード(bindPose など)も消す。
        extra = [cmds.ls(uuid)[0] for uuid in set(cmds.ls(uuid=True)) - self.baseline if cmds.ls(uuid)]
        if extra:
            cmds.lockNode(extra, lock=False)
            cmds.delete(extra)
        super().tearDown()

    def shown(self, name):
        """名前の案内が出る見本の (ラベル, オブジェクト, 案内先, 文) を返す。"""
        result = []
        for label, obj in self.samples.items():
            cls = type(obj)
            entry = None if hasattr(cls, name) else _entry(cls, _MEMBER_HINTS[name])
            # 同じ名前のMayaのアトリビュートがあるノードでは、案内でなくそのPlugを返す。
            if entry and not isinstance(obj, Plug) and cmds.attributeQuery(name, node=str(obj), exists=True):
                entry = None
            if entry:
                result.append((label, obj, *entry))
        return result

    def test_every_hint_is_shown_with_an_existing_target(self):
        """表の全件で、案内が出る見本の AttributeError の文に案内の文が入り、案内先が実在する。"""
        for name in _MEMBER_HINTS:
            shown = self.shown(name)
            with self.subTest(name=name):
                if name in UNREACHABLE:
                    self.assertEqual(shown, [], f"{name} の案内が出るようになった(UNREACHABLE から外す)")
                    continue
                self.assertTrue(shown, f"{name} の案内が出る見本が無い")
                for label, obj, required, text in shown:
                    with self.assertRaises(AttributeError) as context:
                        getattr(obj, name)
                    self.assertIn(text, str(context.exception), label)
                    if required is not None:
                        self.assertTrue(callable(getattr(obj, required)), f"{label}: 案内先 {required} が無い")

    def test_every_hint_has_a_check(self):
        """表の全件に、案内の呼び方を実行する確かめ方がある(UNREACHABLE を除く)。"""
        missing = [name for name in _MEMBER_HINTS if name not in UNREACHABLE and not hasattr(self, "check_" + name)]
        self.assertEqual(missing, [])

    def test_broken_advice_still_fails(self):
        """BROKEN に書いた組は、まだ案内の呼び方が例外になる(直ったら BROKEN から外す)。"""
        for (name, label), reason in BROKEN.items():
            with self.subTest(name=name, sample=label, reason=reason):
                self.assertIn(label, [shown[0] for shown in self.shown(name)])
                with self.assertRaises((TypeError, ValueError, AttributeError)):
                    getattr(self, "check_" + name)(self.samples[label])

    # ------------------------------------------------------------------
    # 案内ごとの確かめ方。obj は案内が出る見本。

    def _value_plug(self, obj):
        return f"{obj}.hintValue"

    def check_getAttr(self, obj):
        cmds.setAttr(self._value_plug(obj), 2.5)
        self.assertEqual(obj.getPlug("hintValue").get(), cmds.getAttr(self._value_plug(obj)))

    def check_setAttr(self, obj):
        obj.getPlug("hintValue").set(4.25)
        self.assertEqual(cmds.getAttr(self._value_plug(obj)), 4.25)

    def check_attr(self, obj):
        self.assertEqual(cmds.ls(str(obj.getPlug("hintValue"))), cmds.ls(self._value_plug(obj)))

    def check_listAttr(self, obj):
        # getPlugs はマルチアトリビュートであるコンパウンドアトリビュートの子を含めない(docstring)ので、含まれる側で比べる。
        names = [plug.getName().partition(".")[2] for plug in obj.getPlugs()]
        listed = set(cmds.listAttr(str(obj)) + cmds.listAttr(str(obj), shortNames=True))
        self.assertIn("hintValue", [plug.getAttributeName() for plug in obj.getPlugs()])
        self.assertEqual([name for name in names if name not in listed], [])

    def check_hasAttribute(self, obj):
        for attr in ("hintValue", "noSuchHintAttr"):
            self.assertEqual(obj.hasAttr(attr), cmds.attributeQuery(attr, node=str(obj), exists=True))

    check_attributeExists = check_hasAttribute

    def check_addAttribute(self, obj):
        obj.addAttr("hintAdded", type="double")
        self.assertTrue(cmds.attributeQuery("hintAdded", node=str(obj), exists=True))

    def check_deleteAttr(self, obj):
        obj.getPlug("hintValue").delete()
        self.assertFalse(cmds.attributeQuery("hintValue", node=str(obj), exists=True))

    def check_connectAttr(self, obj):
        destination = self.make("transform", "destination#") + ".translateZ"
        obj.getPlug("hintValue").connectTo(destination)
        self.assertTrue(cmds.isConnected(self._value_plug(obj), destination))

    def check_disconnectAttr(self, obj):
        source = str(self.other) + ".translateZ"
        cmds.connectAttr(source, self._value_plug(obj))
        obj.getPlug("hintValue").disconnect()
        self.assertFalse(cmds.isConnected(source, self._value_plug(obj)))

    def check_lockAndHide(self, obj):
        if isinstance(obj, Plug):
            obj.setFlags(locked=True, keyable=False, channelBox=False, children=True)
            name = str(obj)
        else:
            obj.setAttrFlags(["hintValue"], locked=True, keyable=False, channelBox=False, children=True)
            name = self._value_plug(obj)
        # 案内の呼び方は子にも掛ける(children=True)ので、コンパウンドアトリビュートの子も比べる。
        node, attr = name.split(".", 1)
        for plug in [name] + [f"{node}.{child}" for child in cmds.attributeQuery(attr, node=node, listChildren=True) or []]:
            self.assertTrue(cmds.getAttr(plug, lock=True), plug)
            self.assertFalse(cmds.getAttr(plug, keyable=True), plug)
            self.assertFalse(cmds.getAttr(plug, channelBox=True), plug)

    def check_lockNode(self, obj):
        # Plug では、案内どおり持ち主のノードをロックする。
        node = obj.getNode() if isinstance(obj, Plug) else obj
        node.setLocked(True)
        self.assertTrue(cmds.lockNode(str(node), query=True, lock=True)[0])
        node.setLocked(False)

    def _connections(self, obj, children=True, **flags):
        """cmds.listConnections の相手(Plug は子の接続も含む。getConnections の checkChildren の既定)。"""
        names = [str(obj)]
        if isinstance(obj, Plug) and children:
            node, attr = str(obj).split(".", 1)
            names += [f"{node}.{child}" for child in cmds.attributeQuery(attr, node=node, listChildren=True) or []]
        return sorted({_full(name) for item in names for name in cmds.listConnections(item, plugs=True, **flags) or []})

    def check_listConnections(self, obj):
        self._connect_around(obj)
        self.assertEqual(sorted(_full(item) for item in obj.getConnections()), self._connections(obj))

    check_connections = check_listConnections

    def _connect_around(self, obj):
        """入力と出力の接続を1つずつ作る。"""
        if isinstance(obj, Plug):
            node = str(obj).split(".")[0]
            cmds.connectAttr(str(self.child) + ".translateY", node + ".translateY", force=True)
            cmds.connectAttr(node + ".translateY", str(self.child) + ".translateZ", force=True)
        else:
            cmds.connectAttr(str(self.other) + ".translateY", self._value_plug(obj), force=True)
            cmds.connectAttr(self._value_plug(obj), str(self.other) + ".scaleZ", force=True)

    def check_inputs(self, obj):
        self._connect_around(obj)
        # input=True は自身の直接の入力1つ(子はたどらない)。
        expected = self._connections(obj, children=False, source=True, destination=False)
        result = obj.getConnections(input=True)
        self.assertEqual([_full(result)] if result is not None else [], expected)

    def check_outputs(self, obj):
        self._connect_around(obj)
        expected = self._connections(obj, children=False, source=False, destination=True)
        self.assertEqual(sorted(_full(item) for item in obj.getConnections(output=True)), expected)

    def check_listRelatives(self, obj):
        if isinstance(obj, Plug):
            node, attr = str(obj).split(".", 1)
            self.assertEqual([item.getAttributeName() for item in obj.getChildren()], cmds.attributeQuery(attr, node=node, listChildren=True))
            self.assertEqual(obj.getParent(), None)
            return
        children = cmds.listRelatives(str(obj), children=True, fullPath=True) or []
        self.assertEqual([_full(item) for item in obj.getChildren()], children)
        parents = cmds.listRelatives(str(obj), parent=True, fullPath=True) or []
        parent = obj.getParent()
        self.assertEqual([_full(parent)] if parent is not None else [], parents)

    def check_getAllChildren(self, obj):
        if isinstance(obj, Plug):
            node, attr = str(obj).split(".", 1)
            expected = cmds.attributeQuery(attr, node=node, listChildren=True) or []
            self.assertEqual([item.getAttributeName() for item in obj.getDescendants()], expected)
            return
        expected = cmds.listRelatives(str(obj), allDescendents=True, fullPath=True) or []
        self.assertEqual(sorted(_full(item) for item in obj.getChildren(allDescendents=True)), sorted(expected))

    def check_listHistory(self, obj):
        expected = [_full(name) for name in cmds.listHistory(str(obj)) or [] if _full(name) != _full(obj)]
        self.assertEqual([_full(item) for item in obj.getHistory()], expected)

    check_history = check_listHistory

    def check_firstParent(self, obj):
        if isinstance(obj, Plug):
            node, attr = str(obj).split(".", 1)
            parent = cmds.attributeQuery(attr, node=node, listParent=True)
            result = obj.getParent()
            self.assertEqual(result.getAttributeName() if result is not None else None, parent[0] if parent else None)
            return
        parents = cmds.listRelatives(str(obj), parent=True, fullPath=True) or []
        parent = obj.getParent()
        self.assertEqual([_full(parent)] if parent is not None else [], parents)

    def check_getAllParents(self, obj):
        if isinstance(obj, Plug):
            node, attr = str(obj).split(".", 1)
            expected = cmds.attributeQuery(attr, node=node, listParent=True) or []
            self.assertEqual([item.getAttributeName() for item in obj.getParent(all=True)], expected)
            return
        path = _full(obj).split("|")[1:-1]
        expected = ["|" + "|".join(path[: index + 1]) for index in reversed(range(len(path)))]
        self.assertEqual([_full(item) for item in obj.getParent(all=True)], expected)
        self.assertEqual([_full(item) for item in obj.getParent(instances=True)], cmds.listRelatives(str(obj), allParents=True, fullPath=True) or [])

    def check_parent(self, obj):
        target = self.other if not obj.isType("shape") else mlib.getNode(self.make("transform", "shapeParent"))
        obj.setParent(target, relative=obj.isType("shape"))
        self.assertEqual(cmds.listRelatives(str(obj), parent=True, fullPath=True), [_full(target)])
        self.assertEqual(_full(obj.getParent()), _full(target))

    def check_nodeType(self, obj):
        if isinstance(obj, Plug):
            self.assertEqual(obj.getType(), cmds.getAttr(str(obj), type=True))
        else:
            self.assertEqual(obj.getType(), cmds.nodeType(str(obj)))

    check_type = check_nodeType

    def check_name(self, obj):
        if isinstance(obj, Plug):
            self.assertEqual(cmds.ls(obj.getName(), long=True), cmds.ls(str(obj), long=True))
            return
        self.assertEqual(obj.getName(short=True), cmds.ls(str(obj), long=True)[0].split("|")[-1])
        self.assertEqual(obj.getName(), cmds.ls(str(obj))[0])

    def check_nodeName(self, obj):
        if isinstance(obj, Plug):
            node = str(obj).split(".")[0]
            self.assertEqual(obj.getNode().getName(), cmds.ls(node)[0])
            return
        self.assertEqual(obj.getName(short=True), cmds.ls(str(obj), long=True)[0].split("|")[-1])

    def check_shortName(self, obj):
        if isinstance(obj, Plug):
            node, attr = str(obj).split(".", 1)
            self.assertEqual(obj.getAttributeName(kind="short"), cmds.attributeQuery(attr, node=node, shortName=True))
            return
        self.check_nodeName(obj)

    def check_longName(self, obj):
        if isinstance(obj, Plug):
            node, attr = str(obj).split(".", 1)
            self.assertEqual(obj.getAttributeName(), cmds.attributeQuery(attr, node=node, longName=True))
            return
        self.assertEqual(obj.getName(full=True), cmds.ls(str(obj), long=True)[0])

    def check_fullPath(self, obj):
        if isinstance(obj, Plug):
            # Plug の getName(full=True) は cmds で1つに決まる名前(ノードの完全なパスでない)。指す対象が同じことを確かめる。
            self.assertEqual(cmds.ls(obj.getName(full=True), long=True), cmds.ls(str(obj), long=True))
            return
        self.assertEqual(obj.getName(full=True), cmds.ls(str(obj), long=True)[0])

    check_fullPathName = check_fullPath

    def check_exists(self, obj):
        self.assertTrue(obj.isValid())
        if not hasattr(obj, "getCurve"):
            self.assertEqual(obj.isValid(), cmds.objExists(str(obj)))

    def check_getTranslate(self, obj):
        cmds.setAttr(str(obj) + ".translate", 1.0, -2.0, 3.5)
        expected = cmds.getAttr(str(obj) + ".translate")[0]
        self.assertSequenceAlmostEqual(obj.getTranslation(), expected)
        self.assertSequenceAlmostEqual(obj.t.get(), expected)

    def check_setTranslate(self, obj):
        obj.setTranslation((1.0, 2.0, 3.0))
        self.assertSequenceAlmostEqual(cmds.getAttr(str(obj) + ".translate")[0], (1.0, 2.0, 3.0))
        obj.t.set((4.0, 5.0, 6.0))
        self.assertSequenceAlmostEqual(cmds.getAttr(str(obj) + ".translate")[0], (4.0, 5.0, 6.0))

    def check_getRotation(self, obj):
        cmds.setAttr(str(obj) + ".rotate", 10.0, 20.0, 30.0)
        self.assertSequenceAlmostEqual(obj.getRotate(), [math.radians(v) for v in cmds.getAttr(str(obj) + ".rotate")[0]])

    def check_setRotation(self, obj):
        obj.setRotate((10.0, 20.0, 30.0))
        self.assertSequenceAlmostEqual(cmds.getAttr(str(obj) + ".rotate")[0], (10.0, 20.0, 30.0))

    def check_xform(self, obj):
        cmds.setAttr(str(obj) + ".translate", 1.0, 2.0, 3.0)
        matrix = obj.getMatrix()
        self.assertSequenceAlmostEqual([matrix[i] for i in range(16)], cmds.xform(str(obj), query=True, matrix=True))
        cmds.setAttr(str(obj) + ".translate", 0.0, 0.0, 0.0)
        obj.setMatrix(matrix)
        self.assertSequenceAlmostEqual(cmds.getAttr(str(obj) + ".translate")[0], (1.0, 2.0, 3.0))
        obj.setTranslation((4.0, 5.0, 6.0))
        self.assertSequenceAlmostEqual(obj.getTranslation(), cmds.getAttr(str(obj) + ".translate")[0])

    def check_getTransformation(self, obj):
        if hasattr(obj, "getMemberIndices"):
            member = obj.getMembers()[0]
            matrix = obj.getMatrix(member)
        else:
            matrix = obj.getMatrix()
        self.assertEqual(len(list(matrix)), 16)

    def check_orientJoint(self, obj):
        copy = cmds.duplicate(str(obj))[0]
        obj.orient()
        cmds.joint(copy, edit=True, orientJoint="xyz", secondaryAxisOrient="yup", children=True, zeroScaleOrient=True)
        self.assertSequenceAlmostEqual(cmds.getAttr(str(obj) + ".jointOrient")[0], cmds.getAttr(copy + ".jointOrient")[0])

    def check_getValue(self, obj):
        cmds.setAttr(str(self.other) + ".translate", 1.0, 2.0, 3.0)
        value = obj.get()
        expected = cmds.getAttr(str(obj))
        self.assertSequenceAlmostEqual(
            value if isinstance(value, (list, tuple)) or hasattr(value, "__len__") else [value], expected[0] if isinstance(expected, list) else [expected]
        )

    def check_setValue(self, obj):
        value = (1.0, 2.0, 3.0) if obj.isCompound() else 2.0
        obj.set(value)
        expected = cmds.getAttr(str(obj))
        self.assertSequenceAlmostEqual(expected[0] if isinstance(expected, list) else [expected], value if isinstance(value, tuple) else [value])

    def check_lock(self, obj):
        obj.setLocked(True)
        if isinstance(obj, Plug):
            self.assertTrue(cmds.getAttr(str(obj), lock=True))
        else:
            self.assertTrue(cmds.lockNode(str(obj), query=True, lock=True)[0])
            obj.setLocked(False)

    def check_unlock(self, obj):
        if isinstance(obj, Plug):
            cmds.setAttr(str(obj), lock=True)
            obj.setLocked(False)
            self.assertFalse(cmds.getAttr(str(obj), lock=True))
        else:
            cmds.lockNode(str(obj), lock=True)
            obj.setLocked(False)
            self.assertFalse(cmds.lockNode(str(obj), query=True, lock=True)[0])

    def check_mute(self, obj):
        # cmds.mute はアニメーションの付いたアトリビュートにだけ mute ノードを挟む。
        cmds.setKeyframe(str(obj), time=1)
        obj.setMuted(True)
        self.assertTrue(self._muted(obj))

    def check_unmute(self, obj):
        cmds.setKeyframe(str(obj), time=1)
        cmds.mute(str(obj))
        self.assertTrue(self._muted(obj))
        obj.setMuted(False)
        self.assertFalse(self._muted(obj))

    def _muted(self, obj):
        """mute ノードが入力につながっていれば True(cmds.mute の query は版で戻り値が揃わない)。"""
        names = [str(obj)] + [
            f"{str(obj).split('.')[0]}.{child}"
            for child in cmds.attributeQuery(str(obj).split(".", 1)[1], node=str(obj).split(".")[0], listChildren=True) or []
        ]
        return any(cmds.listConnections(name, source=True, destination=False, type="mute") for name in names)

    def check_getAttrName(self, obj):
        node, attr = str(obj).split(".", 1)
        self.assertEqual(obj.getName().partition(".")[2], cmds.attributeQuery(attr, node=node, shortName=True))
        self.assertEqual(obj.getAttributeName(kind="short"), cmds.attributeQuery(attr, node=node, shortName=True))

    def check_select(self, obj):
        cmds.select(str(obj), replace=True)
        expected = cmds.ls(selection=True, long=True)
        cmds.select(clear=True)
        mlib.select(obj)
        self.assertEqual(cmds.ls(selection=True, long=True), expected)

    def _curve_name(self, obj):
        return obj.getName()

    def check_getTangent(self, obj):
        tangent = obj.getKeyframes(0).getTangent()
        curve = self._curve_name(obj)
        self.assertEqual(tangent["inTangentType"], cmds.keyTangent(curve, index=(0, 0), query=True, inTangentType=True)[0])
        self.assertEqual(tangent["outTangentType"], cmds.keyTangent(curve, index=(0, 0), query=True, outTangentType=True)[0])
        self.assertAlmostEqual(tangent["outAngle"], cmds.keyTangent(curve, index=(0, 0), query=True, outAngle=True)[0], places=6)

    def check_setTangent(self, obj):
        obj.getKeyframes(0).setTangent(inTangentType="linear", outTangentType="linear")
        curve = self._curve_name(obj)
        self.assertEqual(cmds.keyTangent(curve, index=(0, 0), query=True, inTangentType=True), ["linear"])
        self.assertEqual(cmds.keyTangent(curve, index=(0, 0), query=True, outTangentType=True), ["linear"])

    def check_isBreakdown(self, obj):
        curve = self._curve_name(obj)
        cmds.keyframe(curve, index=(1, 1), breakdown=True)
        for index in (0, 1):
            self.assertEqual(obj.getKeyframes(index).isBreakdown(), bool(cmds.keyframe(curve, index=(index, index), query=True, breakdown=True)))

    def check_setBreakdown(self, obj):
        curve = self._curve_name(obj)
        obj.getKeyframes(1).setBreakdown(True)
        self.assertTrue(cmds.keyframe(curve, index=(1, 1), query=True, breakdown=True))
        obj.getKeyframes(1).setBreakdown(False)
        self.assertFalse(cmds.keyframe(curve, index=(1, 1), query=True, breakdown=True))

    def check_mesh(self, obj):
        expected = cmds.skinCluster(str(obj), query=True, geometry=True)
        self.assertEqual(_full(obj.getGeometry()), _full(expected[0]))

    def check_mesh_path(self, obj):
        expected = cmds.skinCluster(str(obj), query=True, geometry=True)
        self.assertEqual(obj.getGeometry().mpath().fullPathName(), _full(expected[0]))


def _hint_test(name):
    def test(self):
        if name in UNREACHABLE:
            self.skipTest(UNREACHABLE[name])
        shown = [item for item in self.shown(name) if (name, item[0]) not in BROKEN]
        for label, obj, _required, _text in shown:
            with self.subTest(sample=label):
                getattr(self, "check_" + name)(obj)

    test.__doc__ = f"{name} の案内の呼び方を実行し、間違えた名前が意味する結果になる。"
    return test


for _name in _MEMBER_HINTS:
    setattr(ObjectHintTest, f"test_hint_{_name}", _hint_test(_name))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
