"""``Plug.getLayeredPlug``・``Plug.getAnimLayers`` が、プロキシ・mute・pairBlend を通ってレイヤーをたどることのテスト。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class _LayerCase(NamespaceCase):
    """レイヤーに入れたtranslateXを持つtransformを作り、作ったレイヤーを後で消す。"""

    PREFIX = "mlibLayerInputs_"

    def setUp(self):
        super().setUp()
        self.root_before = cmds.animLayer(query=True, root=True)
        self.layers = []

    def tearDown(self):
        for layer in self.layers:
            if cmds.objExists(layer):
                cmds.delete(layer)
        root = cmds.animLayer(query=True, root=True)
        if root and not self.root_before and cmds.objExists(root):
            cmds.delete(root)
        super().tearDown()

    def layered(self):
        """キーを打ったtranslateXを1つのレイヤーへ入れ、(ノード名, レイヤー名, ブレンドノード名)を返す。"""
        node = self.make("transform", "layered#")
        cmds.setKeyframe(node + ".tx", time=1, value=0.0)
        layer = cmds.animLayer(self.name("layer"))
        self.layers.append(layer)
        cmds.animLayer(layer, edit=True, attribute=node + ".tx")
        blend = cmds.listConnections(node + ".tx", source=True, destination=False)[0]
        self.assertTrue(cmds.objectType(blend).startswith("animBlendNode"))
        return node, layer, blend


class LayeredPlugThroughNodesTest(_LayerCase):
    """プロキシ・mute・pairBlend の先のレイヤーの入力。"""

    def test_proxy(self):
        """プロキシのPlugは元のアトリビュートのつながりをたどり、元と同じ入力とレイヤーを返す。"""
        node, layer, blend = self.layered()
        holder = self.make("transform", "holder#")
        cmds.addAttr(holder, longName="txProxy", proxy=node + ".tx")
        proxy = mlib.getPlug(holder + ".txProxy")
        master = mlib.getPlug(node + ".tx")
        expected = mlib.getPlug(blend + ".inputB")
        self.assertEqual(proxy.getLayeredPlug(layer), expected)
        self.assertEqual(proxy.getLayeredPlug(), master.getLayeredPlug())
        self.assertEqual(proxy.getAnimLayers().getNames(), master.getAnimLayers().getNames())

    def test_proxy_without_master(self):
        """元との接続が切れたプロキシは、元を返さず、レイヤーも無い(自身を返す)。"""
        node = self.make("transform", "master#")
        cmds.addAttr(node, longName="amount", attributeType="double", keyable=True)
        holder = self.make("transform", "holder#")
        cmds.addAttr(holder, longName="amountProxy", proxy=node + ".amount")
        cmds.disconnectAttr(node + ".amount", holder + ".amountProxy")
        proxy = mlib.getPlug(holder + ".amountProxy")
        self.assertTrue(proxy.isProxy())
        self.assertIsNone(proxy.getProxyMaster())
        self.assertEqual(len(proxy.getAnimLayers()), 0)
        self.assertIs(proxy.getLayeredPlug(), proxy)

    def test_mute(self):
        """muteを挟んでも、その先のレイヤーのブレンドノードのinputBを返す。"""
        node, layer, blend = self.layered()
        cmds.mute(node + ".tx")
        source = cmds.listConnections(node + ".tx", source=True, destination=False)[0]
        self.assertEqual(cmds.objectType(source), "mute")
        plug = mlib.getPlug(node + ".tx")
        self.assertEqual(plug.getLayeredPlug(layer), mlib.getPlug(blend + ".inputB"))
        self.assertIn(layer, plug.getAnimLayers().getNames())

    def test_pair_blend(self):
        """pairBlendは使っている側の入力をたどる。使っていない側(mode=2)ならレイヤーは見つからない。"""
        node, layer, blend = self.layered()
        pair = cmds.createNode("pairBlend", name=self.name("pair#"))
        output = cmds.listConnections(node + ".tx", source=True, destination=False, plugs=True)[0]
        cmds.disconnectAttr(output, node + ".tx")
        cmds.connectAttr(output, pair + ".inTranslateX1")
        cmds.connectAttr(pair + ".outTranslateX", node + ".tx")
        plug = mlib.getPlug(node + ".tx")
        self.assertEqual(plug.getLayeredPlug(layer), mlib.getPlug(blend + ".inputB"))
        cmds.setAttr(pair + ".translateXMode", 2)
        self.assertIsNone(plug.getLayeredPlug(layer))
        self.assertIs(plug.getLayeredPlug(), plug)
        cmds.setAttr(pair + ".translateXMode", 1)
        self.assertEqual(plug.getLayeredPlug(layer), mlib.getPlug(blend + ".inputB"))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
