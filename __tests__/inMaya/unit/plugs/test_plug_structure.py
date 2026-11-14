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

    def test_siblings_and_all_parents(self):
        """コンパウンドアトリビュートの兄弟と、マルチアトリビュートの要素を経由した祖先。"""
        node = mlib.getNode(self.make("transform"))
        self.assertEqual([plug.getShortName() for plug in node.tx.getSiblings()], ["ty", "tz"])
        self.assertEqual(node.translate.getSiblings(), [])
        self.assertEqual([plug.getShortName() for plug in node.tx.getAllParents()], ["t"])
        pma = mlib.getNode(self.make("plusMinusAverage", "pma#"))
        child = pma.getPlug("input3D[2].input3Dx")
        self.assertEqual([plug.getName() for plug in child.getAllParents()], [pma.getName() + ".i3[2]"])
        self.assertEqual([plug.getName() for plug in child.getAllParents(includeMulti=True)], [pma.getName() + ".i3[2]", pma.getName() + ".i3"])
        self.assertEqual(pma.getPlug("input1D[0]").getAllParents(), [])
        self.assertEqual([plug.getName() for plug in pma.getPlug("input1D[0]").getAllParents(includeMulti=True)], [pma.getName() + ".i1"])
        with self.assertRaises(TypeError):
            child.getAllParents(includeMulti=1)

    def test_definition_flags(self):
        """connectable・usedAsColor・worldSpace の定義フラグが attributeQuery と一致する。"""
        name = self.make("transform")
        node = mlib.getNode(name)
        for attribute in ("translateX", "worldMatrix", "overrideColorRGB", "message"):
            with self.subTest(attribute=attribute):
                plug = node.getPlug(attribute)
                self.assertEqual(plug.isUsedAsColor(), cmds.attributeQuery(attribute, node=name, usedAsColor=True))
                self.assertIs(plug.isConnectable(), True)
        self.assertTrue(node.worldMatrix.isWorldSpace())
        self.assertFalse(node.tx.isWorldSpace())
        self.assertTrue(node.getPlug("overrideColorRGB").isUsedAsColor())

    def test_is_default_value(self):
        """既定値なら True、変えると False。コンパウンドアトリビュートは子がすべて既定値なら True。"""
        node = mlib.getNode(self.make("transform"))
        self.assertTrue(node.tx.isDefaultValue())
        self.assertTrue(node.translate.isDefaultValue())
        node.ty.set(2.0)
        self.assertFalse(node.ty.isDefaultValue())
        self.assertFalse(node.translate.isDefaultValue())
        self.assertTrue(node.tx.isDefaultValue())

    def test_affected_and_affecting_match_cmds(self):
        """getAffected/getAffecting のロング名が cmds.affects(by=True)/cmds.affects と一致する。"""
        name = self.make("transform")
        node = mlib.getNode(name)
        for attribute in ("translateX", "rotate", "visibility"):
            with self.subTest(attribute=attribute):
                plug = node.getPlug(attribute)
                self.assertEqual(sorted(p.getLongName() for p in plug.getAffected()), sorted(set(cmds.affects(attribute, name, by=True) or [])))
                self.assertEqual(sorted(p.getLongName() for p in plug.getAffecting()), sorted(set(cmds.affects(attribute, name) or [])))
        self.assertIn("matrix", [p.getLongName() for p in node.tx.getAffected()])

    def test_affected_multi_child_is_folded(self):
        """マルチアトリビュートの中の子は、そのマルチアトリビュート全体の Plug にまとめる。"""
        pma = mlib.getNode(self.make("plusMinusAverage", "pma#"))
        names = [p.getLongName() for p in pma.getPlug("operation").getAffected()]
        self.assertIn("output3D", names)
        affecting = [p.getLongName() for p in pma.getPlug("output3Dx").getAffecting()]
        self.assertIn("input3D", affecting)
        self.assertNotIn("input3Dx", affecting)

    def test_connected_indices(self):
        """接続のある要素(子の接続・出力接続を含む)の番号だけを返す。値だけの要素は含まない。"""
        a = mlib.getNode(self.make("transform"))
        pma = mlib.getNode(self.make("plusMinusAverage", "pma#"))
        cmds.connectAttr(a.getFullName() + ".tx", pma.getFullName() + ".input1D[3]")
        cmds.connectAttr(a.getFullName() + ".ty", pma.getFullName() + ".input1D[1]")
        cmds.setAttr(pma.getFullName() + ".input1D[7]", 2.0)
        cmds.connectAttr(a.getFullName() + ".tz", pma.getFullName() + ".input3D[5].input3Dy")
        self.assertEqual(pma.getPlug("input1D").getConnectedIndices(), [1, 3])
        self.assertEqual(pma.getPlug("input1D").getIndices(), [1, 3, 7])
        self.assertEqual(pma.getPlug("input3D").getConnectedIndices(), [5])
        self.assertEqual(pma.getPlug("input2D").getConnectedIndices(), [])
        b = mlib.getNode(self.make("transform"))
        cmds.connectAttr(a.getFullName() + ".worldMatrix[0]", b.getFullName() + ".offsetParentMatrix")
        self.assertEqual(a.getPlug("worldMatrix").getConnectedIndices(), [0])

    def test_deleted_plug_raises(self):
        """削除済みのノードの Plug は RuntimeError。"""
        node = mlib.getNode(self.make("transform"))
        plug, multi = node.tx, node.worldMatrix
        cmds.delete(node.getFullName())
        for call in (
            plug.getSiblings,
            plug.getAllParents,
            plug.isConnectable,
            plug.isUsedAsColor,
            plug.isWorldSpace,
            plug.isDefaultValue,
            plug.isFromReferencedFile,
            plug.getAffected,
            plug.getAffecting,
            plug.getLayeredPlug,
            multi.getConnectedIndices,
        ):
            with self.subTest(call=call.__name__):
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
        self.assertIs(plug.insertInput(mdl, "input1", "output"), plug)

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
        self.assertEqual(mlib.getPlug(mdl + ".input1").getSource(skipConversionNodes=True).getFullName(), mlib.getPlug(a + ".rx").getFullName())
        self.assertEqual(mlib.getPlug(b + ".ty").getSource().getFullName(), mlib.getPlug(mdl + ".output").getFullName())
        c = self.make("transform", "c#")
        mdl2 = self.make("multDoubleLinear", "mdl#")
        mlib.getPlug(c + ".tz").insertInput(mdl2, "input1", "output")
        self.assertEqual(mlib.getPlug(c + ".tz").getSource().getFullName(), mlib.getPlug(mdl2 + ".output").getFullName())
        self.assertIsNone(mlib.getPlug(mdl2 + ".input1").getSource())

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
            ((mdl, "nope", "output"), RuntimeError),
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
        self.assertEqual(base.getSource().getNode().getFullName(), curve.getFullName())
        other = self.make("transform", "b#")
        self.assertIsNone(mlib.getPlug(other + ".tx").getLayeredPlug(layer1))
        for layer, error in ((5, TypeError), (other, TypeError), (self.name("missingLayer"), RuntimeError)):
            with self.subTest(layer=layer):
                with self.assertRaises(error):
                    plug.getLayeredPlug(layer)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
