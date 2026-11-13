"""``mlib.plugs.plug`` のテスト。

- プラグの API の契約を固定する。
"""

import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.plugs import CompoundPlug, MultiPlug, RampPlug
from support.namespaceCase import NamespaceCase


def _ramp(plug_name):
    """名前のプラグの MRampAttribute を作る。"""
    selection = om2.MSelectionList()
    selection.add(plug_name)
    return om2.MRampAttribute(selection.getPlug(0))


class _MultiCase(NamespaceCase):
    """コンパウンドの子を持つマルチアトリビュートを作る。"""

    def compound_multi(self):
        node = self.make("transform", "holder")
        cmds.addAttr(node, longName="items", attributeType="compound", numberOfChildren=2, multi=True)
        cmds.addAttr(node, longName="itemVec", attributeType="double3", parent="items")
        for axis in "XYZ":
            cmds.addAttr(node, longName="itemVec" + axis, attributeType="double", parent="itemVec")
        cmds.addAttr(node, longName="itemWeight", attributeType="double", parent="items")
        return node


class ProxyTest(NamespaceCase):

    def test_proxy_master(self):
        """プロキシは True と元の Plug、通常のアトリビュートは False と None。プロキシのプロキシは1段上。"""
        master = self.make("transform", "master")
        cmds.addAttr(master, longName="amount", attributeType="double", keyable=True)
        first = self.make("transform", "first")
        second = self.make("transform", "second")
        cmds.addAttr(first, longName="amountProxy", proxy=master + ".amount")
        cmds.addAttr(second, longName="amountProxy2", proxy=first + ".amountProxy")
        proxy = mlib.getNode(first).getPlug("amountProxy")
        self.assertTrue(proxy.isProxy())
        self.assertEqual(proxy.getProxyMaster(), mlib.getNode(master).getPlug("amount"))
        proxy2 = mlib.getNode(second).getPlug("amountProxy2")
        self.assertEqual(proxy2.getProxyMaster(), proxy)
        self.assertEqual(proxy2.getProxyMaster().getProxyMaster(), mlib.getNode(master).getPlug("amount"))
        plain = mlib.getNode(master).getPlug("amount")
        self.assertFalse(plain.isProxy())
        self.assertIsNone(plain.getProxyMaster())
        # om2 の判定と一致する。
        self.assertEqual(proxy.isProxy(), om2.MFnAttribute(proxy.mplug().attribute()).isProxyAttribute)


class AnimLayerCurveTest(NamespaceCase):

    def setUp(self):
        super().setUp()
        # 最上位のレイヤー(BaseAnimation)をこのテストが作ったときだけ、後片付けで消す。
        self.rootBefore = cmds.animLayer(query=True, root=True)

    def tearDown(self):
        for layer in cmds.ls(type="animLayer") or []:
            if cmds.objExists(layer) and layer.startswith(self.ns):
                cmds.delete(layer)
        root = cmds.animLayer(query=True, root=True)
        if root and not self.rootBefore and cmds.objExists(root):
            cmds.delete(root)
        super().tearDown()

    def test_layer_curve(self):
        """layer 指定はそのレイヤーのカーブ、属さないレイヤーは None、未指定は従来どおり。"""
        cube = cmds.polyCube(name=self.name("cube"))[0]
        cmds.setKeyframe(cube, attribute="translateX", time=1, value=1)
        plug = mlib.getNode(cube).getPlug("translateX")
        direct = plug.getAnimCurve()
        self.assertEqual(direct.getType(), "animCurveTL")
        layer = cmds.animLayer(self.name("L1"))
        empty = cmds.animLayer(self.name("L2"))
        base = cmds.animLayer(query=True, root=True)
        cmds.select(cube)
        cmds.animLayer(layer, edit=True, addSelectedObjects=True)
        cmds.select(clear=True)
        cmds.setKeyframe(cube, attribute="translateX", time=1, value=5, animLayer=layer)
        expected_layer = cmds.animLayer(layer, query=True, findCurveForPlug=cube + ".translateX")[0]
        expected_base = cmds.animLayer(base, query=True, findCurveForPlug=cube + ".translateX")[0]
        self.assertEqual(plug.getAnimCurve(layer=layer).getName(), expected_layer)
        self.assertEqual(plug.getAnimCurve(layer=mlib.getNode(layer)).getName(), expected_layer)
        self.assertEqual(plug.getAnimCurve(layer=base).getName(), expected_base)
        self.assertIsNone(plug.getAnimCurve(layer=empty))
        # 未指定は直接の入力(レイヤーのブレンドノード)なので animCurve ではない。
        self.assertIsNone(plug.getAnimCurve())
        self.assertIsNone(mlib.getNode(cube).getPlug("translateY").getAnimCurve(layer=layer))
        # どのレイヤーにも属さないプラグのベースレイヤーのカーブは、直接接続された animCurve。
        other = cmds.polyCube(name=self.name("other"))[0]
        cmds.setKeyframe(other, attribute="translateX", time=1, value=2)
        other_plug = mlib.getNode(other).getPlug("translateX")
        self.assertEqual(other_plug.getAnimCurve(layer=base), other_plug.getAnimCurve())
        self.assertIsNone(other_plug.getAnimCurve(layer=layer))

    def test_layer_errors(self):
        """animLayer 以外は TypeError、解決できない名前は RuntimeError。"""
        cube = cmds.polyCube(name=self.name("cube"))[0]
        plug = mlib.getNode(cube).getPlug("translateX")
        self.assertRaises(TypeError, plug.getAnimCurve, layer=1)
        self.assertRaises(TypeError, plug.getAnimCurve, layer=cube)
        self.assertRaises(RuntimeError, plug.getAnimCurve, layer=self.name("missingLayer"))


if __name__ == "__main__":
    unittest.main()
