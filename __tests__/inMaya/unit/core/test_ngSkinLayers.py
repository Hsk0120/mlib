"""ngSkinTools2 のレイヤーがある skinCluster の influence 解除を確かめる。

実物の ngSkinTools2 を読み込む。同梱のプラグインが無い Maya の版では飛ばす。
"""

import contextlib
import os
import sys
import types
import unittest
from unittest import mock

import maya.cmds as cmds
import maya.mel as mel

import mlib

mlib.reload()
from support.namespaceCase import NamespaceCase

from mlib.core import ngSkinLayers
from mlib.nodes import Joints, SkinCluster

CONTENTS = r"C:\ProgramData\Autodesk\ApplicationPlugins\ngskintools2\Contents"
VERSION = cmds.about(version=True).split()[0][:4]
PLUGIN = os.path.join(CONTENTS, "plug-ins", VERSION, "ngSkinTools2.mll")


@unittest.skipUnless(os.path.exists(PLUGIN), "ngSkinTools2 is not available for this Maya version")
class NgSkinLayersTest(NamespaceCase):
    """root→mid→tip と other にバインドし、2 枚のレイヤーで確かめる。"""

    PREFIX = "mlibSpecNgSkin_"
    ENABLE_UNDO = True

    @classmethod
    def setUpClass(cls):
        scripts = os.path.join(CONTENTS, "scripts")
        if scripts not in sys.path:
            sys.path.insert(0, scripts)
        cmds.loadPlugin(PLUGIN, quiet=True)

    def setUp(self):
        super().setUp()
        from ngSkinTools2 import api

        self.api = api
        cmds.select(clear=True)
        self.root = mlib.getNode(cmds.joint(name=self.name("root"), position=(0, 0, 0)))
        self.mid = mlib.getNode(cmds.joint(name=self.name("mid"), position=(1, 0, 0)))
        self.tip = mlib.getNode(cmds.joint(name=self.name("tip"), position=(2, 0, 0)))
        cmds.select(clear=True)
        self.other = mlib.getNode(cmds.joint(name=self.name("other"), position=(0, 2, 0)))
        cmds.select(clear=True)
        self.joints = (self.root, self.mid, self.tip, self.other)
        mesh = cmds.polyPlane(name=self.name("mesh"), constructionHistory=False, subdivisionsX=1, subdivisionsY=1)[0]
        name = cmds.skinCluster([joint.getName(full=True) for joint in self.joints], mesh, toSelectedBones=True)[0]
        cmds.select(clear=True)
        self.skin = SkinCluster(name)
        self.count = 4
        self.layers = api.init_layers(name)
        self.base = self.layers.add("base")
        for index, value in enumerate((0.5, 0.2, 0.2, 0.1)):
            self.base.set_weights(index, [value] * self.count)
        self.top = self.layers.add("top")
        self.top.set_weights(2, [0.25] * self.count)
        self.top.set_weights(1, [0.25] * self.count)

    def tearDown(self):
        self.layers.clear()
        super().tearDown()

    def assertSkin(self, expected):
        """{joint: 値} が全頂点の skinCluster のウェイトであることを確かめる。"""
        joints = list(expected)
        values = list(self.skin.getWeights([joint.getName(full=True) for joint in joints]))
        for position, value in enumerate(values):
            self.assertAlmostEqual(value, expected[joints[position % len(joints)]], places=5)

    def assertLayer(self, layer, index, value):
        """レイヤーの列が全頂点 value であることを確かめる。"""
        weights = layer.get_weights(index)
        self.assertEqual(len(weights), self.count)
        for actual in weights:
            self.assertAlmostEqual(actual, value, places=5)

    def _fresh_layers(self):
        """layers.list() から base と top を取り直す。"""
        return {layer.name: layer for layer in self.layers.list()}

    def test_starting_composite(self):
        self.assertSkin({self.root: 0.25, self.mid: 0.35, self.tip: 0.35, self.other: 0.05})

    def test_remove_moves_weight_in_every_layer(self):
        """レイヤーごとに移送し、合成結果は親子の和になる。Undo 1 回で戻る。"""
        cmds.flushUndo()
        Joints([self.tip]).removeInfluence()
        self.assertFalse(self.skin.hasInfluence(self.tip.getName(full=True)))
        layers = self._fresh_layers()
        self.assertLayer(layers["base"], 1, 0.4)
        self.assertLayer(layers["top"], 1, 0.5)
        self.assertLayer(layers["base"], 0, 0.5)
        self.assertLayer(layers["base"], 3, 0.1)
        self.assertNotIn(2, layers["base"].get_used_influences())
        self.assertSkin({self.root: 0.25, self.mid: 0.7, self.other: 0.05})
        cmds.undo()
        self.assertTrue(self.skin.hasInfluence(self.tip.getName(full=True)))
        layers = self._fresh_layers()
        self.assertLayer(layers["base"], 2, 0.2)
        self.assertLayer(layers["top"], 2, 0.25)
        self.assertSkin({self.root: 0.25, self.mid: 0.35, self.tip: 0.35, self.other: 0.05})

    def test_chain_collapses_to_remaining_ancestor(self):
        """親子を同時に外すと残る祖先へ集まる。"""
        Joints([self.tip, self.mid]).removeInfluence()
        layers = self._fresh_layers()
        self.assertLayer(layers["base"], 0, 0.9)
        self.assertLayer(layers["top"], 0, 0.5)
        self.assertSkin({self.root: 0.95, self.other: 0.05})

    def test_delete_and_fast_match(self):
        """delete も fast も同じ結果で、fast は Undo を積まない。"""
        self.tip.delete()
        self.assertSkin({self.root: 0.25, self.mid: 0.7, self.other: 0.05})
        cmds.undo()
        cmds.flushUndo()
        self.tip.delete(fast=True)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        self.assertTrue(cmds.undoInfo(query=True, state=True))
        layers = self._fresh_layers()
        self.assertLayer(layers["base"], 1, 0.4)
        self.assertSkin({self.root: 0.25, self.mid: 0.7, self.other: 0.05})

    def test_no_ancestor_redistributes_within_layer(self):
        """移送先が無ければ、レイヤーの中で残りへ比率を保って配る。"""
        self.other.delete(transferToParent=False)
        layers = self._fresh_layers()
        self.assertLayer(layers["base"], 0, 0.5 / 0.9)
        self.assertLayer(layers["base"], 1, 0.2 / 0.9)
        self.assertLayer(layers["base"], 2, 0.2 / 0.9)
        self.assertNotIn(3, layers["base"].get_used_influences())

    def test_locked_weight_is_restored(self):
        """ウェイトのロックがあっても移送し、元へ戻す。"""
        cmds.setAttr(self.other.getName(full=True) + ".liw", True)
        self.tip.delete()
        self.assertTrue(cmds.getAttr(self.other.getName(full=True) + ".liw"))
        self.assertSkin({self.root: 0.25, self.mid: 0.7, self.other: 0.05})

    def test_layers_keep_working_after_removal(self):
        """解除の後もレイヤーを編集できる。"""
        self.tip.delete()
        layers = self._fresh_layers()
        layers["top"].set_weights(0, [0.5] * self.count)
        self.assertEqual(mel.eval("pluginInfo -q -loaded ngSkinTools2"), True)
        self.assertEqual(len(self.layers.list()), 2)
        self.assertLayer(self._fresh_layers()["top"], 0, 0.5)


class _FakeLayer:
    """ngSkinTools2のレイヤーの代わり。列の読み書きを記録する。"""

    def __init__(self, columns):
        self.columns = {index: list(values) for index, values in columns.items()}
        self.writes = []

    def get_used_influences(self):
        return list(self.columns)

    def get_weights(self, index):
        return list(self.columns[index])

    def set_weights(self, index, values, undo_enabled=True):
        self.writes.append((index, list(values), undo_enabled))
        self.columns[index] = list(values)


class _FakeApi:
    """ngSkinTools2.apiの代わり。"""

    def __init__(self, layers, enabled=True):
        self.layers = layers
        self.enabled = enabled
        self.suspended = []

    def get_layers_enabled(self, skin_name):
        return self.enabled

    def Layers(self, skin_name):
        api = self

        class _Layers:
            data_node = skin_name + "_data"

            def list(self):
                return api.layers

        return _Layers()

    @contextlib.contextmanager
    def suspend_updates(self, data_node):
        self.suspended.append(data_node)
        yield


class MoveLayerWeightsLogicTest(unittest.TestCase):
    """ngSkinTools2の代わりの部品で、レイヤーごとの移し方を確かめる(どのMayaの版でも実行する)。"""

    def run_move(self, api, *, fast=False):
        """偽のngSkinTools2を読み込ませて、_move_layer_weightsを呼ぶ。"""
        package = types.ModuleType("ngSkinTools2")
        package.api = api
        fake_cmds = mock.Mock()
        fake_cmds.pluginInfo.return_value = True
        with mock.patch.dict(sys.modules, {"ngSkinTools2": package, "ngSkinTools2.api": api}), mock.patch.object(ngSkinLayers, "cmds", fake_cmds):
            return ngSkinLayers._move_layer_weights("skin", {2: 1}, [3], [0, 1], 2, fast=fast)

    def test_moves_and_redistributes_per_layer(self):
        """移し先へ足し、移し先が無い列は残りへ比率で配り、残りが0の頂点は等しく分ける。外す列から書く。"""
        moving = _FakeLayer({0: [0.5, 0.0], 1: [0.2, 0.0], 2: [0.2, 0.0], 3: [0.1, 1.0]})
        unused = _FakeLayer({1: [1.0, 1.0]})
        empty = _FakeLayer({2: [0.0, 0.0]})
        api = _FakeApi([moving, unused, empty])
        self.assertTrue(self.run_move(api))
        self.assertEqual(api.suspended, ["skin_data"])
        expected = {0: [0.5 / 0.9, 0.5], 1: [0.4 / 0.9, 0.5], 2: [0.0, 0.0], 3: [0.0, 0.0]}
        for index, values in expected.items():
            for actual, value in zip(moving.columns[index], values):
                self.assertAlmostEqual(actual, value)
        self.assertEqual([write[0] for write in moving.writes][:2], [2, 3])
        self.assertTrue(all(write[2] for write in moving.writes))
        self.assertEqual(unused.writes, [])
        self.assertEqual(empty.writes, [])

    def test_fast_disables_layer_undo(self):
        """fastではレイヤーのUndoを記録しない。"""
        layer = _FakeLayer({1: [0.0, 0.0], 2: [1.0, 1.0]})
        self.assertTrue(self.run_move(_FakeApi([layer]), fast=True))
        self.assertTrue(layer.writes)
        self.assertFalse(any(write[2] for write in layer.writes))

    def test_unavailable_layers_return_false(self):
        """レイヤーが無効か、ngSkinTools2をimportできなければ、書き込まずFalseを返す。"""
        layer = _FakeLayer({2: [1.0, 1.0]})
        self.assertFalse(self.run_move(_FakeApi([layer], enabled=False)))
        self.assertEqual(layer.writes, [])
        fake_cmds = mock.Mock()
        fake_cmds.pluginInfo.return_value = True
        with mock.patch.dict(sys.modules, {"ngSkinTools2": None}), mock.patch.object(ngSkinLayers, "cmds", fake_cmds):
            self.assertIsNone(ngSkinLayers._layer_api("skin"))


if __name__ == "__main__":
    unittest.main()
