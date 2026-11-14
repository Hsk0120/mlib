"""``mlib.plugs.plug`` のテスト。

- mlib Node/DAG APIを検証するMaya内テスト。
"""

import math
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()


class NodeApiTest(unittest.TestCase):
    """基本Node/DAG APIを検証する。"""

    namespace = ":mlibNodeApiTest"

    def setUp(self):
        self.created = []
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)
        cmds.namespace(add=self.namespace)

    def tearDown(self):
        for node in reversed(self.created):
            if cmds.objExists(node):
                cmds.delete(node)
        if cmds.namespace(exists=self.namespace):
            cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def create_transform(self, name):
        node = mlib.createNode(type="transform", name=name)
        self.created.append(node.getName())
        return node

    def test_plug_is_keyable_and_parent(self):
        transform = self.create_transform("mlibNodeApiPlugMeta")
        translate = transform.getPlug("translate")
        translate_x = transform.getPlug("translateX")

        self.assertTrue(translate_x.isKeyable())
        self.assertIsNone(translate.getParent())
        self.assertEqual(translate_x.getParent().getFullName(), translate.getFullName())

        cmds.setAttr(translate_x.getFullName(), keyable=False)
        self.assertFalse(translate_x.isKeyable())

    def test_plug_hidden_dynamic_limits_default_and_enum(self):
        transform = self.create_transform("mlibNodeApiPlugAttrMeta")
        cmds.addAttr(transform.getName(), longName="mlibTestNum", attributeType="double", min=0, max=10, defaultValue=5, hidden=True)
        cmds.addAttr(transform.getName(), longName="mlibTestNoLimit", attributeType="double", defaultValue=1.5)
        cmds.addAttr(transform.getName(), longName="mlibTestEnum", attributeType="enum", enumName="A:B:C", defaultValue=1)

        num_plug = transform.getPlug("mlibTestNum")
        self.assertTrue(num_plug.isDynamic())
        self.assertTrue(cmds.attributeQuery("mlibTestNum", node=transform.getName(), hidden=True))
        self.assertTrue(num_plug.isHidden())  # keyableでもChannel Box表示でもない。
        self.assertTrue(num_plug.hasMin())
        self.assertTrue(num_plug.hasMax())
        self.assertEqual(num_plug.getMin(), 0.0)
        self.assertEqual(num_plug.getMax(), 10.0)
        self.assertEqual(num_plug.getDefault(), 5.0)

        no_limit_plug = transform.getPlug("mlibTestNoLimit")
        self.assertFalse(cmds.attributeQuery("mlibTestNoLimit", node=transform.getName(), hidden=True))
        self.assertFalse(no_limit_plug.hasMin())
        self.assertFalse(no_limit_plug.hasMax())
        self.assertIsNone(no_limit_plug.getMin())
        self.assertIsNone(no_limit_plug.getMax())
        self.assertEqual(no_limit_plug.getDefault(), 1.5)

        enum_plug = transform.getPlug("mlibTestEnum")
        self.assertEqual(enum_plug.getDefault(), 1)
        self.assertEqual(enum_plug.getEnumName(), "B")

        # 静的(ノード組み込み)アトリビュートは動的アトリビュートではない。
        self.assertFalse(transform.getPlug("translateX").isDynamic())
        with self.assertRaises(TypeError):
            transform.getPlug("translateX").getEnumName()

    def test_plug_readable_writable_storable_and_soft_limits(self):
        transform = self.create_transform("mlibNodeApiPlugFlags")
        cmds.addAttr(transform.getName(), longName="mlibSoftAttr", attributeType="double", softMinValue=0, softMaxValue=10, defaultValue=2)
        plug = transform.getPlug("mlibSoftAttr")

        self.assertTrue(plug.isReadable())
        self.assertTrue(plug.isWritable())
        self.assertTrue(plug.isStorable())
        self.assertTrue(plug.hasSoftMin())
        self.assertTrue(plug.hasSoftMax())
        self.assertEqual(plug.getSoftMin(), 0.0)
        self.assertEqual(plug.getSoftMax(), 10.0)

        translate_x = transform.getPlug("translateX")
        self.assertTrue(translate_x.isReadable())
        self.assertTrue(translate_x.isWritable())
        self.assertTrue(translate_x.isStorable())
        self.assertFalse(translate_x.hasSoftMin())
        self.assertFalse(translate_x.hasSoftMax())

    def test_plug_anim_curve_and_mute(self):
        transform = self.create_transform("mlibNodeApiAnimCurve")
        plug = transform.getPlug("translateX")

        self.assertIsNone(plug.getAnimCurve())

        cmds.setKeyframe(plug.getFullName(), time=1, value=0.0)
        cmds.setKeyframe(plug.getFullName(), time=24, value=10.0)

        curve = plug.getAnimCurve()
        self.assertIsNotNone(curve)
        self.assertTrue(curve.isType("animCurve"))

        self.assertFalse(plug.isMuted())
        result = plug.setMuted(True)
        self.assertIs(result, plug)
        self.assertTrue(plug.isMuted())
        plug.setMuted(False)
        self.assertFalse(plug.isMuted())

        # 非 animCurve 接続では animCurve() は None を返す。
        other = self.create_transform("mlibNodeApiAnimCurveOther")
        other.getPlug("translateX").connectTo(transform.getPlug("translateY"))
        self.assertIsNone(transform.getPlug("translateY").getAnimCurve())

    def test_plug_delete_attr(self):
        transform = self.create_transform("mlibNodeApiDeleteAttr")
        cmds.addAttr(transform.getName(), longName="mlibDeleteMe", attributeType="double", defaultValue=1.0)
        plug = transform.getPlug("mlibDeleteMe")

        self.assertTrue(cmds.attributeQuery("mlibDeleteMe", node=transform.getName(), exists=True))
        plug.delete()
        self.assertFalse(cmds.attributeQuery("mlibDeleteMe", node=transform.getName(), exists=True))

        with self.assertRaises(RuntimeError):
            transform.getPlug("translateX").delete()

    def test_plug_delete_attr_force_unlocks_before_deleting(self):
        transform = self.create_transform("mlibNodeApiDeleteAttrForce")
        cmds.addAttr(transform.getName(), longName="mlibLockedDelete", attributeType="double", defaultValue=1.0)
        plug = transform.getPlug("mlibLockedDelete")
        plug.setFlags(locked=True)

        with self.assertRaises(RuntimeError):
            plug.delete()
        self.assertTrue(cmds.attributeQuery("mlibLockedDelete", node=transform.getName(), exists=True))

        plug.delete(force=True)
        self.assertFalse(cmds.attributeQuery("mlibLockedDelete", node=transform.getName(), exists=True))

    def test_plug_set_keyable_and_set_channel_box(self):
        transform = self.create_transform("mlibNodeApiKeyableCB")
        plug = transform.getPlug("translateX")

        result = plug.setFlags(keyable=False)
        self.assertIs(result, plug)
        self.assertFalse(plug.isKeyable())

        plug.setFlags(channelBox=True)
        self.assertFalse(plug.isKeyable())
        self.assertTrue(cmds.getAttr(plug.getFullName(), channelBox=True))

        plug.setFlags(keyable=True)
        self.assertTrue(plug.isKeyable())

    def test_plug_nice_name_and_is_connected_to(self):
        source = self.create_transform("mlibNodeApiNiceNameSource")
        target = self.create_transform("mlibNodeApiNiceNameTarget")

        self.assertEqual(source.getPlug("translateX").getNiceName(), "Translate X")

        source_plug = source.getPlug("translateX")
        targetPlug = target.getPlug("translateX")
        self.assertFalse(source_plug.isConnectedTo(targetPlug))

        source_plug.connectTo(targetPlug)
        self.assertTrue(source_plug.isConnectedTo(targetPlug))
        self.assertTrue(targetPlug.isConnectedTo(source_plug))
        self.assertFalse(source_plug.isConnectedTo(source.getPlug("translateY")))

    def test_plug_enum_value_reverses_enum_name(self):
        transform = self.create_transform("mlibNodeApiEnumValue")
        cmds.addAttr(transform.getName(), longName="mlibEnumValueAttr", attributeType="enum", enumName="A:B:C", defaultValue=0)
        plug = transform.getPlug("mlibEnumValueAttr")

        self.assertEqual(plug.getEnumValue("B"), 1)
        self.assertEqual(plug.getEnumValue(plug.getEnumName()), 0)
        with self.assertRaises(ValueError):
            plug.getEnumValue("NotAField")
        with self.assertRaises(TypeError):
            transform.getPlug("translateX").getEnumValue("A")

    def test_plug_get_dispatches_by_attribute_type_via_om2(self):
        # Plug.get() は bool/int/float/角度・距離・時間/enum/文字列を
        # MPlug 経由で直接読み取る。cmds.getAttr の結果と一致することを
        # 各アトリビュート型ごとに確認する(角度は度、距離・時間は現在のUI単位)。
        transform = self.create_transform("mlibNodeApiPlugGetTypes")
        name = transform.getName()
        cmds.addAttr(name, longName="mlibBool", attributeType="bool", defaultValue=True)
        cmds.addAttr(name, longName="mlibLong", attributeType="long", defaultValue=42)
        cmds.addAttr(name, longName="mlibShort", attributeType="short", defaultValue=7)
        cmds.addAttr(name, longName="mlibDouble", attributeType="double", defaultValue=1.5)
        cmds.addAttr(name, longName="mlibFloat", attributeType="float", defaultValue=2.5)
        cmds.addAttr(name, longName="mlibString", dataType="string")
        cmds.setAttr(name + ".mlibString", "hello", type="string")
        cmds.addAttr(name, longName="mlibEnum", attributeType="enum", enumName="A:B:C", defaultValue=2)
        cmds.addAttr(name, longName="mlibAngle", attributeType="doubleAngle", defaultValue=0.0)
        cmds.setAttr(name + ".mlibAngle", 90.0)
        cmds.addAttr(name, longName="mlibDistance", attributeType="doubleLinear", defaultValue=0.0)
        cmds.setAttr(name + ".mlibDistance", 5.0)
        cmds.addAttr(name, longName="mlibTime", attributeType="time", defaultValue=0.0)
        cmds.setAttr(name + ".mlibTime", 3.0)

        for attribute in (
            "mlibBool",
            "mlibLong",
            "mlibShort",
            "mlibDouble",
            "mlibFloat",
            "mlibString",
            "mlibEnum",
            "mlibAngle",
            "mlibDistance",
            "mlibTime",
            "translateX",
            "visibility",
        ):
            with self.subTest(attribute=attribute):
                plug_value = transform.getPlug(attribute).get()
                cmds_value = cmds.getAttr(f"{name}.{attribute}")
                if attribute == "mlibAngle":
                    # 角度の既定は度(cmds.getAttrのUI単位degと同じ)。radはunit="rad"。
                    self.assertAlmostEqual(transform.getPlug(attribute).get(unit="rad"), math.pi / 2)
                    cmds_value = 90.0
                elif attribute == "mlibTime":
                    # 時間の既定は現在のUI時間単位のフレーム(cmds.getAttrと同じ)。秒はtimeUnit="sec"。
                    self.assertAlmostEqual(transform.getPlug(attribute).get(timeUnit="sec"), 3.0 / 24)
                self.assertAlmostEqual(plug_value, cmds_value) if isinstance(cmds_value, float) else self.assertEqual(plug_value, cmds_value)

        self.assertIsInstance(transform.getPlug("mlibBool").get(), bool)
        self.assertIsInstance(transform.getPlug("mlibLong").get(), int)
        self.assertIsInstance(transform.getPlug("mlibString").get(), str)

        # 読み方は Plug ごとに一度だけ選んで保持するが、単位の変換は呼び出しごとに現在の
        # UI 単位で行う(同じ Plug で単位を変えても cmds.getAttr と一致する)。
        plugs = {attribute: transform.getPlug(attribute) for attribute in ("mlibDistance", "mlibTime", "mlibAngle", "translateX")}
        for plug in plugs.values():
            plug.get()
        previous = (cmds.currentUnit(query=True, linear=True), cmds.currentUnit(query=True, time=True))
        try:
            cmds.currentUnit(linear="mm", time="ntsc")
            for attribute, plug in plugs.items():
                with self.subTest(attribute=attribute, unit="mm/ntsc"):
                    self.assertAlmostEqual(plug.get(), {"mlibDistance": 5.0, "mlibTime": 3.75, "mlibAngle": 90.0, "translateX": 0.0}[attribute])
        finally:
            cmds.currentUnit(linear=previous[0], time=previous[1])

    def test_plug_get_falls_back_to_cmds_for_unsupported_typed_data(self):
        # stringArray は MFnTypedAttribute だが kString ではないため、
        # om2 の直接読み取りは対象外となり cmds.getAttr にフォールバックする。
        transform = self.create_transform("mlibNodeApiPlugGetFallback")
        cmds.addAttr(transform.getName(), longName="mlibStringArray", dataType="stringArray")
        cmds.setAttr(transform.getName() + ".mlibStringArray", 2, "a", "b", type="stringArray")

        value = transform.getPlug("mlibStringArray").get()
        self.assertEqual(value, cmds.getAttr(transform.getName() + ".mlibStringArray"))

    def assert_channels(self, name, rotate, scale, places=9):
        for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], rotate):
            self.assertAlmostEqual(actual, expected, places=places)
        for actual, expected in zip(cmds.getAttr(name + ".scale")[0], scale):
            self.assertAlmostEqual(actual, expected, places=places)

    def test_plug_structural_introspection_properties(self):
        transform = self.create_transform("mlibNodeApiPlugStructure")
        translatePlug = transform.getPlug("translate")
        translate_x_plug = transform.getPlug("translateX")
        world_matrix_plug = transform.getPlug("worldMatrix")

        self.assertTrue(translatePlug.isCompound())
        self.assertFalse(translatePlug.isMulti())
        self.assertFalse(translatePlug.isMultiElement())
        self.assertFalse(translatePlug.isChild())

        self.assertTrue(translate_x_plug.isChild())
        self.assertFalse(translate_x_plug.isCompound())

        self.assertTrue(world_matrix_plug.isMulti())

        self.assertIsInstance(translatePlug.mplug(), om2.MPlug)

        element = world_matrix_plug.getElement(0)
        self.assertTrue(element.isMultiElement())

    def test_plug_connection_introspection_and_disconnect(self):
        source = self.create_transform("mlibNodeApiPlugConnSource")
        target = self.create_transform("mlibNodeApiPlugConnTarget")
        source_plug = source.getPlug("translateX")
        targetPlug = target.getPlug("translateX")

        self.assertFalse(source_plug.isConnected())
        self.assertFalse(source_plug.isSource())
        self.assertFalse(targetPlug.isDestination())

        source_plug.connectTo(targetPlug)
        self.assertTrue(source_plug.isConnected())
        self.assertTrue(source_plug.isSource())
        self.assertFalse(source_plug.isDestination())
        self.assertTrue(targetPlug.isConnected())
        self.assertTrue(targetPlug.isDestination())
        self.assertFalse(targetPlug.isSource())

        destinations = source_plug.getDestinations()
        self.assertEqual([plug.getFullName() for plug in destinations], [targetPlug.getFullName()])

        result = source_plug.disconnectAll()
        self.assertIs(result, source_plug)
        self.assertFalse(source_plug.isConnected())
        self.assertFalse(targetPlug.isConnected())
        self.assertEqual(source_plug.getDestinations(), [])

    def test_plug_paths_reject_indices_beyond_logical_index_range(self):
        # MPlug.elementByLogicalIndex() は範囲外の番号を別の番号へ変換する(4294967296 は 0)。
        # アトリビュートパス・要素番号では別の要素へ読み替えず、例外にする。
        average = mlib.createNode(type="plusMinusAverage", name="mlibNodeApiIndexRange")
        self.created.append(average.getName())
        maximum = 2147483647
        self.assertEqual(average.getPlug(f"input1D[{maximum:d}]").mplug().logicalIndex(), maximum)
        for path in ("input1D[2147483648]", "input1D[4294967295]", "input1D[4294967296]", "input1D[4294967297]", "input3D[4294967296].input3Dx"):
            with self.subTest(path=path):
                with self.assertRaises(AttributeError) as context:
                    average.getPlug(path)
                self.assertIn(str(maximum), str(context.exception))
                self.assertFalse(average.hasAttr(path))
        multi_plug = average.getPlug("input1D")
        for index in (-1, maximum + 1, 4294967296):
            with self.subTest(index=index):
                with self.assertRaises(IndexError):
                    multi_plug.getElement(index)
                with self.assertRaises(IndexError):
                    multi_plug[index]
        # 要素は作られない(maya.cmds は 4294967296 を 2147483647 に切り詰めて作成する)。
        self.assertEqual(list(multi_plug.mplug().getExistingArrayAttributeIndices()), [])
        created = multi_plug[maximum]
        self.assertEqual(list(multi_plug.mplug().getExistingArrayAttributeIndices()), [])
        created.set(0)
        self.assertEqual(created.mplug().logicalIndex(), maximum)
        self.assertEqual(list(multi_plug.mplug().getExistingArrayAttributeIndices()), [maximum])

    def test_plug_rejects_mplug_of_another_node(self):
        from mlib.plugs import Plug

        first = self.create_transform("mlibNodeApiPlugOwnerA")
        second = self.create_transform("mlibNodeApiPlugOwnerB")
        first.addAttr("mlibDynamic", attributeType="double")
        for name in ("translateX", "mlibDynamic", "worldMatrix"):
            with self.subTest(attribute=name):
                mplug = first.getPlug(name).mplug()
                self.assertEqual(Plug(first, mplug).mplug(), mplug)
                # 静的アトリビュートは同じ型の別ノードにも存在するが、所有ノードでない node は拒否する。
                with self.assertRaises(RuntimeError) as context:
                    Plug(second, mplug)
                self.assertIn("owner node", str(context.exception))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
