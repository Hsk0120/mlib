"""``mlib.plugs.plug`` のテスト。

- Node・Plug・MultiPlug・Namespace・Reference のメソッドと units の変換関数を確かめる。
"""

import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """名前空間の補助。"""

    PREFIX = "mlibNodePlugAddnp_"


class PlugStructureTest(_Case):
    """Plug の構造・定義フラグ・既定値・依存関係。"""

    def test_siblings_and_parents_all(self):
        """コンパウンドアトリビュートの兄弟と、マルチアトリビュートの要素を経由した祖先。"""
        node = mlib.getNode(self.make("transform"))
        self.assertEqual([plug.getAttributeName("short") for plug in node.tx.getSiblings()], ["ty", "tz"])
        self.assertEqual(node.translate.getSiblings(), [])
        self.assertEqual([plug.getAttributeName("short") for plug in node.tx.getParent(all=True)], ["t"])
        pma = mlib.getNode(self.make("plusMinusAverage", "pma#"))
        child = pma.getPlug("input3D[2].input3Dx")
        self.assertEqual([plug.getName() for plug in child.getParent(all=True)], [pma.getName() + ".i3[2]"])
        self.assertEqual([plug.getName() for plug in child.getParent(all=True, includeMulti=True)], [pma.getName() + ".i3[2]", pma.getName() + ".i3"])
        self.assertEqual(pma.getPlug("input1D[0]").getParent(all=True), [])
        self.assertEqual([plug.getName() for plug in pma.getPlug("input1D[0]").getParent(all=True, includeMulti=True)], [pma.getName() + ".i1"])
        with self.assertRaises(TypeError):
            child.getParent(all=True, includeMulti=1)

    def test_parent_all_and_include_multi(self):
        """getParent(all=True)は近い順のPlugsで、マルチアトリビュートの要素も通ってたどる。all=Falseはすぐ上の親かNone。"""
        node = mlib.getNode(self.make("transform"))
        cmds.addAttr(node.getFullName(), longName="outer", attributeType="compound", numberOfChildren=1, multi=True)
        cmds.addAttr(node.getFullName(), longName="inner", attributeType="compound", numberOfChildren=1, multi=True, parent="outer")
        cmds.addAttr(node.getFullName(), longName="leaf", attributeType="double", multi=True, parent="inner")
        name = node.getName()
        leaf = node.getPlug("outer[0].inner[3].leaf[2]")
        parents = leaf.getParent(all=True)
        self.assertIsInstance(parents, mlib.Plugs)
        self.assertEqual([plug.getFullName() for plug in parents], [name + ".outer[0].inner[3]", name + ".outer[0]"])
        self.assertEqual(
            [plug.getFullName() for plug in leaf.getParent(all=True, includeMulti=True)],
            [name + ".outer[0].inner[3].leaf", name + ".outer[0].inner[3]", name + ".outer[0].inner", name + ".outer[0]", name + ".outer"],
        )
        # all=False はコンパウンドアトリビュートの子だけが親を持つ(要素は子ではないのでNone)。
        self.assertIsNone(leaf.getParent())
        self.assertIsNone(leaf.getParent(all=False))
        inner_element = node.getPlug("outer[0].inner[3]")
        self.assertIsNone(inner_element.getParent())
        self.assertEqual([plug.getFullName() for plug in inner_element.getParent(all=True)], [name + ".outer[0]"])
        leaf_multi = node.getPlug("outer[0].inner[3].leaf")
        self.assertEqual(leaf_multi.getParent().getFullName(), name + ".outer[0].inner[3]")
        self.assertEqual(leaf_multi.getParent(all=True)[0], leaf_multi.getParent())
        # いちばん上のアトリビュートは空のPlugs。
        self.assertEqual(node.translate.getParent(all=True), [])
        self.assertIsInstance(node.translate.getParent(all=True), mlib.Plugs)
        self.assertEqual(node.tx.getParent(all=True), [node.tx.getParent()])
        # 要素は作らない。
        self.assertEqual(cmds.getAttr(name + ".outer", multiIndices=True) or [], [])

    def test_parent_argument_errors(self):
        """all・includeMultiはboolのキーワード専用。all=FalseでincludeMulti=TrueはTypeError。"""
        node = mlib.getNode(self.make("transform"))
        for call in (
            lambda: node.tx.getParent(includeMulti=True),
            lambda: node.tx.getParent(all=False, includeMulti=True),
            lambda: node.tx.getParent(all=1),
            lambda: node.tx.getParent(all=None),
            lambda: node.tx.getParent(all=True, includeMulti="yes"),
            lambda: node.tx.getParent(True),
        ):
            with self.assertRaises(TypeError):
                call()
        self.assertEqual(node.tx.getParent(all=False, includeMulti=False), node.translate)

    def test_is_valid_elements(self):
        """isValid(elements=True)は、通るマルチアトリビュートの要素が実在することも確かめる。要素は作らない。"""
        node = mlib.getNode(self.make("transform"))
        name = node.getFullName()
        cmds.addAttr(name, longName="outer", attributeType="compound", numberOfChildren=1, multi=True)
        cmds.addAttr(name, longName="values", attributeType="double", multi=True, parent="outer")
        cmds.setAttr(name + ".outer[2].values[5]", 1.0)
        cases = (
            ("outer", True),
            ("outer[2]", True),
            ("outer[2].values", True),
            ("outer[2].values[5]", True),
            ("outer[2].values[6]", False),
            ("outer[4]", False),
            ("outer[4].values", False),
            ("outer[4].values[5]", False),
        )
        for path, expected in cases:
            with self.subTest(path=path):
                plug = node.getPlug(path)
                self.assertTrue(plug.isValid())
                self.assertTrue(plug.isValid(elements=False))
                self.assertIs(plug.isValid(elements=True), expected)
        self.assertEqual(cmds.getAttr(name + ".outer", multiIndices=True), [2])
        self.assertEqual(cmds.getAttr(name + ".outer[2].values", multiIndices=True), [5])
        self.assertTrue(node.tx.isValid(elements=True))
        self.assertTrue(node.translate.isValid(elements=True))
        # 作れば True になり、消せば False に戻る。
        missing = node.getPlug("outer[2].values[6]")
        missing.set(3.0)
        self.assertTrue(missing.isValid(elements=True))
        cmds.removeMultiInstance(name + ".outer[2].values[6]", b=True)
        self.assertFalse(missing.isValid(elements=True))
        self.assertTrue(missing.isValid())
        with self.assertRaises(TypeError):
            node.tx.isValid(True)
        cmds.delete(name)
        self.assertFalse(missing.isValid())
        self.assertFalse(missing.isValid(elements=True))

    def test_is_default_value(self):
        """既定値なら True、変えると False。コンパウンドアトリビュートは子がすべて既定値なら True。"""
        node = mlib.getNode(self.make("transform"))
        self.assertTrue(node.tx.isDefaultValue())
        self.assertTrue(node.translate.isDefaultValue())
        node.ty.set(2.0)
        self.assertFalse(node.ty.isDefaultValue())
        self.assertFalse(node.translate.isDefaultValue())
        self.assertTrue(node.tx.isDefaultValue())

    def test_connected_indices(self):
        """接続のある要素(子の接続・出力接続を含む)の番号だけを返す。値だけの要素は含まない。"""
        a = mlib.getNode(self.make("transform"))
        pma = mlib.getNode(self.make("plusMinusAverage", "pma#"))
        cmds.connectAttr(a.getFullName() + ".tx", pma.getFullName() + ".input1D[3]")
        cmds.connectAttr(a.getFullName() + ".ty", pma.getFullName() + ".input1D[1]")
        cmds.setAttr(pma.getFullName() + ".input1D[7]", 2.0)
        cmds.connectAttr(a.getFullName() + ".tz", pma.getFullName() + ".input3D[5].input3Dy")
        self.assertEqual(pma.getPlug("input1D").getIndices(connected=True), [1, 3])
        self.assertEqual(pma.getPlug("input1D").getIndices(), [1, 3, 7])
        self.assertEqual(pma.getPlug("input3D").getIndices(connected=True), [5])
        self.assertEqual(pma.getPlug("input2D").getIndices(connected=True), [])
        b = mlib.getNode(self.make("transform"))
        cmds.connectAttr(a.getFullName() + ".worldMatrix[0]", b.getFullName() + ".offsetParentMatrix")
        self.assertEqual(a.getPlug("worldMatrix").getIndices(connected=True), [0])

    def test_deleted_plug_raises(self):
        """削除済みのノードの Plug は RuntimeError。"""
        node = mlib.getNode(self.make("transform"))
        plug, multi = node.tx, node.worldMatrix
        cmds.delete(node.getFullName())
        calls = (
            ("getSiblings", plug.getSiblings),
            ("getParent", plug.getParent),
            ("getParent(all)", lambda: plug.getParent(all=True)),
            ("getParent(all, includeMulti)", lambda: plug.getParent(all=True, includeMulti=True)),
            ("isDefaultValue", plug.isDefaultValue),
            ("isFromReferencedFile", plug.isFromReferencedFile),
            ("getLayeredPlug", plug.getLayeredPlug),
            ("getIndices(connected)", lambda: multi.getIndices(connected=True)),
        )
        for label, call in calls:
            with self.subTest(call=label):
                with self.assertRaises(RuntimeError):
                    call()


class InsertInputTest(_Case):
    """Plug.insertInput。"""

    def test_insert_between_connection(self):
        """入力元 → node.input1、node.output → 自身になり、Undo 1回で元の接続に戻る。"""
        a, b = self.make("transform", "a#"), self.make("transform", "b#")
        mdl = self.make("multDoubleLinear", "mdl#")
        cmds.connectAttr(a + ".tx", b + ".ty")
        plug = mlib.getPlug(b + ".ty")
        self.flushUndo()
        self.assertIsNone(plug.insertInput(mdl, "input1", "output"))

        def after():
            self.assertEqual(cmds.listConnections(b + ".ty", source=True, destination=False, plugs=True), [cmds.ls(mdl)[0] + ".output"])
            self.assertEqual(cmds.listConnections(mdl + ".input1", source=True, destination=False, plugs=True), [cmds.ls(a)[0] + ".translateX"])

        def before():
            self.assertEqual(cmds.listConnections(b + ".ty", source=True, destination=False, plugs=True), [cmds.ls(a)[0] + ".translateX"])
            self.assertFalse(cmds.listConnections(mdl + ".input1", source=True, destination=False))

        self.assertUndoesInOneStep(before, after)

    def test_insert_skips_conversion_and_without_input(self):
        """unitConversion を飛ばした入力元をつなぐ。入力接続が無ければ出力だけをつなぐ。"""
        a, b = self.make("transform", "a#"), self.make("transform", "b#")
        mdl = self.make("multDoubleLinear", "mdl#")
        cmds.connectAttr(a + ".rx", b + ".ty")
        mlib.getPlug(b + ".ty").insertInput(mdl, "input1", "output")
        self.assertEqual(
            mlib.getPlug(mdl + ".input1").getConnections(input=True, skipConversionNodes=True).getFullName(), mlib.getPlug(a + ".rx").getFullName()
        )
        self.assertEqual(mlib.getPlug(b + ".ty").getConnections(input=True).getFullName(), mlib.getPlug(mdl + ".output").getFullName())
        c = self.make("transform", "c#")
        mdl2 = self.make("multDoubleLinear", "mdl#")
        mlib.getPlug(c + ".tz").insertInput(mdl2, "input1", "output")
        self.assertEqual(mlib.getPlug(c + ".tz").getConnections(input=True).getFullName(), mlib.getPlug(mdl2 + ".output").getFullName())
        self.assertIsNone(mlib.getPlug(mdl2 + ".input1").getConnections(input=True))

    def test_insert_errors(self):
        """引数の型・空文字列・存在しないアトリビュート・入力側の既存接続は例外で、接続は変わらない。"""
        a, b = self.make("transform", "a#"), self.make("transform", "b#")
        mdl = self.make("multDoubleLinear", "mdl#")
        cmds.connectAttr(a + ".tx", b + ".ty")
        cmds.connectAttr(a + ".tz", mdl + ".input1")
        plug = mlib.getPlug(b + ".ty")
        for args, error in (
            ((mdl, 1, "output"), TypeError),
            ((mdl, "input1", ""), ValueError),
            ((mdl, "nope", "output"), AttributeError),
            ((mdl, "input1", "output"), RuntimeError),
            ((5, "input1", "output"), TypeError),
        ):
            with self.subTest(args=args):
                with self.assertRaises(error):
                    plug.insertInput(*args)
                self.assertEqual(cmds.listConnections(b + ".ty", source=True, destination=False, plugs=True), [cmds.ls(a)[0] + ".translateX"])


class LayeredPlugTest(_Case):
    """Plug.getLayeredPlug。"""

    def setUp(self):
        super().setUp()
        self.layers = []

    def tearDown(self):
        for layer in self.layers:
            if cmds.objExists(layer):
                cmds.delete(layer)
        super().tearDown()

    def test_layered_plug_matches_anim_layer(self):
        """レイヤー指定は animLayer(layeredPlug) と一致し、既定は最上位、ベースはブレンドの連鎖の最も手前。"""
        node = self.make("transform", "a#")
        cmds.setKeyframe(node + ".tx", time=1, value=0.0)
        plug = mlib.getPlug(node + ".tx")
        self.assertIs(plug.getLayeredPlug(), plug)
        layer1 = cmds.animLayer("mlibNodePlugAddLayer1_" + uuid.uuid4().hex[:6])
        layer2 = cmds.animLayer("mlibNodePlugAddLayer2_" + uuid.uuid4().hex[:6])
        self.layers += [layer1, layer2]
        root = cmds.animLayer(query=True, root=True)
        if root not in self.layers:
            self.layers.append(root)
        cmds.animLayer(layer1, edit=True, attribute=node + ".tx")
        cmds.animLayer(layer2, edit=True, attribute=node + ".tx")
        for layer in (layer1, layer2):
            with self.subTest(layer=layer):
                expected = cmds.animLayer(layer, query=True, layeredPlug=node + ".tx")
                self.assertEqual(plug.getLayeredPlug(layer).getFullName(), mlib.getPlug(expected).getFullName())
        top = plug.getAnimLayers()[0]
        self.assertEqual(plug.getLayeredPlug().getFullName(), mlib.getPlug(cmds.animLayer(top, query=True, layeredPlug=node + ".tx")).getFullName())
        base = plug.getLayeredPlug(root)
        curve = plug.getAnimCurve(layer=root)
        self.assertEqual(base.getConnections(input=True).getNode().getFullName(), curve.getFullName())
        other = self.make("transform", "b#")
        self.assertIsNone(mlib.getPlug(other + ".tx").getLayeredPlug(layer1))
        for layer, error in ((5, TypeError), (other, TypeError), (self.name("missingLayer"), RuntimeError)):
            with self.subTest(layer=layer):
                with self.assertRaises(error):
                    plug.getLayeredPlug(layer)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
