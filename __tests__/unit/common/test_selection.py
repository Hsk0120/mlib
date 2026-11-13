"""選択の分類・名前変更追跡・欠落・Undo/RedoをMayaで検証する。

あわせて次も確かめる。

- mlib.common の公開APIの約束を固定する仕様テスト(担当D)。
- コンポーネント・Selectionの読みやすいrepr、Selection.getItems・getChannelBoxPlugsの仕様テスト。
- スキンのウェイト編集向けの照会・編集の契約を固定する。
"""

import math
import sys
from unittest import mock
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import (
    CurveFit,
    Deferred,
    DrivenKey,
    LOADED,
    MISSING,
    Namespace,
    Plugin,
    PluginPackage,
    references,
    ScriptJob,
    ScriptJobs,
    Selection,
    selection as selection_module,
    SKIPPED,
    undo,
    units,
    Version,
)
from mlib.common.selection import Selection
from mlib.components import CV, CVs, Edge, Edges, Face, UV, Vertex, Vertices
from mlib.nodes import GeometryFilter, Joint, Node, NurbsCurve, SkinCluster
from mlib.plugs import Plug
from support.namespaceCase import NamespaceCase


class SelectionTest(unittest.TestCase):
    def setUp(self):
        self.ns = "mlibSelection_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)
        self.mesh = cmds.polyCube(name=self.ns + ":mesh")[0]
        self.joint = cmds.createNode("joint", name=self.ns + ":joint")

    def tearDown(self):
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def test_capture_mixed_and_snapshot(self):
        cmds.select([self.joint, self.mesh + ".vtx[1:3]"], replace=True)
        selection = mlib.Selection.capture()
        cmds.select(clear=True)
        self.assertEqual(len(selection), 4)
        self.assertEqual(len(selection.getNodes(type="joint")), 1)
        self.assertEqual(selection.getComponents()[0].indices, (1, 2, 3))
        self.assertEqual(len(selection.getOwners()), 2)
        self.assertEqual(len(selection.filter(type="vtx")), 3)
        selection.select()
        self.assertEqual(len(cmds.ls(selection=True, flatten=True)), 4)
        cmds.undo()
        self.assertEqual(cmds.ls(selection=True), [])
        cmds.redo()
        self.assertEqual(len(cmds.ls(selection=True, flatten=True)), 4)

    def test_rename_and_missing_validation(self):
        selection = Selection([self.joint, self.mesh + ".f[0]"])
        renamed = cmds.rename(self.joint, self.ns + ":renamed")
        selection.select()
        self.assertIn(renamed, cmds.ls(selection=True))
        cmds.delete(self.mesh)
        cmds.select(clear=True)
        with self.assertRaises(RuntimeError):
            selection.select(missing="error")
        self.assertEqual(cmds.ls(selection=True), [])
        selection.select()
        self.assertEqual(cmds.ls(selection=True), [renamed])
        with self.assertRaises(ValueError):
            selection.select(missing="invalid")

    def test_plug_reference_and_delete(self):
        cmds.addAttr(self.joint, longName="amount", attributeType="double")
        selection = Selection([self.joint + ".amount"])
        self.assertEqual(len(selection.getPlugs()), 1)
        self.assertEqual(len(selection.filter(type="plug")), 1)
        cmds.renameAttr(self.joint + ".amount", "renamed")
        self.assertTrue(selection.getPlugs()[0].getFullName().endswith(".renamed"))
        cmds.deleteAttr(self.joint + ".renamed")
        self.assertEqual(selection.getPlugs(), [])
        with self.assertRaises(RuntimeError):
            selection.select(missing="error")

    def test_add_remove_and_empty(self):
        selection = Selection(self.joint)
        cmds.select(self.mesh)
        selection.select(mode="add")
        self.assertIn(self.joint, cmds.ls(selection=True))
        cmds.undo()
        self.assertEqual(cmds.ls(selection=True), [self.mesh])
        cmds.redo()
        selection.select(mode="remove")
        self.assertEqual(cmds.ls(selection=True), [self.mesh])
        cmds.undo()
        self.assertIn(self.joint, cmds.ls(selection=True))
        Selection().select()
        self.assertEqual(cmds.ls(selection=True), [])

    def test_component_kinds_and_objectset(self):
        curve = cmds.curve(name=self.ns + ":curve", degree=1, point=[(0, 0, 0), (1, 0, 0)])
        for suffix in ("e[0:1]", "f[0:1]", "map[0:1]"):
            selection = Selection(self.mesh + "." + suffix)
            self.assertEqual(len(selection), 2)
            self.assertEqual(len(selection.getComponents()), 1)
        self.assertEqual(len(Selection(curve + ".cv[*]")), 2)
        name = cmds.sets(self.mesh, name=self.ns + ":set")
        Selection(name).select()
        self.assertEqual(cmds.ls(selection=True), [name])

    def test_instanced_path_preserved(self):
        instance = cmds.instance(self.mesh, name=self.ns + ":instance")[0]
        selection = Selection(instance + ".vtx[0]")
        selection.select()
        self.assertIn(instance, cmds.ls(selection=True, long=True)[0])


def _maya_year():
    """現在のMayaの年版を cmds から独立に求める。

    Returns:
        int: 2027などの年版。
    """
    return int(str(cmds.about(version=True)).split(".")[0])


class SelectionSpecTest(unittest.TestCase):
    """Selectionの展開・重複除去・選択反映・Undoを固定する。"""

    def setUp(self):
        """一時名前空間に立方体とtransformを作り、選択を保存する。"""
        self.ns = "mlibSpecDSel_" + uuid.uuid4().hex[:8]
        cmds.namespace(add=self.ns)
        self.mesh = cmds.polyCube(name=self.ns + ":mesh", constructionHistory=False)[0]
        self.node = cmds.createNode("transform", name=self.ns + ":node")
        self.previous = cmds.ls(selection=True, long=True)

    def tearDown(self):
        """選択を戻し、一時名前空間を削除する。"""
        cmds.select(clear=True)
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        existing = [name for name in self.previous if cmds.objExists(name)]
        if existing:
            cmds.select(existing, replace=True)

    def test_empty_and_duplicates(self):
        """空の集合は長さ0。同じ完全名は最初の1件だけを保持する。"""
        self.assertEqual(len(Selection()), 0)
        selection = Selection([self.node, Node(self.node), "|" + self.node])
        self.assertEqual(len(selection), 1)
        self.assertIsInstance(selection[0], Node)

    def test_ranges_expand_and_slices_are_tuples(self):
        """範囲名は単体コンポーネントへ展開し、sliceはtuple、itemsは独立したlist。"""
        selection = Selection(self.mesh + ".vtx[2:4]")
        self.assertEqual(len(selection), 3)
        self.assertTrue(all(isinstance(item, Vertex) for item in selection))
        self.assertEqual([item.index for item in selection], [2, 3, 4])
        self.assertIsInstance(selection[0:2], tuple)
        items = selection.items
        items.clear()
        self.assertEqual(len(selection), 3)
        self.assertIsInstance(selection[-1], Vertex)

    def test_mixed_items_and_owner(self):
        """ノード・アトリビュート・コンポーネントを保持順で持ち、所有ノードは重複を除く。"""
        selection = Selection([self.node, self.node + ".tx", self.mesh + ".f[0]", self.mesh + ".vtx[0]"])
        self.assertEqual(len(selection), 4)
        self.assertIsInstance(selection[1], Plug)
        self.assertEqual(len(selection.getPlugs()), 1)
        self.assertEqual(len(selection.getComponents()), 2)
        owners = [owner.getName() for owner in selection.getOwners()]
        self.assertEqual(len(owners), 2)
        self.assertEqual(len(selection.filter("plug")), 1)
        self.assertEqual(len(selection.filter("vertex")), len(selection.filter("vtx")))
        self.assertEqual(len(selection.filter("transform")), 1)

    def test_capture_is_a_snapshot(self):
        """captureは現在選択を取得時点の順で保持し、その後の選択変更に追従しない。"""
        cmds.select(self.node, self.mesh + ".vtx[1]", replace=True)
        captured = Selection.capture()
        cmds.select(clear=True)
        self.assertEqual(len(captured), 2)
        self.assertIsInstance(captured[0], Node)
        self.assertIsInstance(captured[1], Vertex)
        captured.select()
        self.assertEqual(len(cmds.ls(selection=True, flatten=True)), 2)

    def test_unsupported_item_is_rejected(self):
        """非対応型はTypeError、存在しない名前はRuntimeError。"""
        with self.assertRaises(TypeError):
            Selection([5])
        with self.assertRaises(RuntimeError):
            Selection([self.ns + ":missing"])

    def test_select_modes_and_undo(self):
        """replace/add/removeで選択を変え、1回のUndoで直前の選択へ戻る。"""
        cmds.select(self.node, replace=True)
        Selection(self.mesh).select(mode="add")
        self.assertEqual(len(cmds.ls(selection=True)), 2)
        Selection(self.node).select(mode="remove")
        self.assertEqual(cmds.ls(selection=True), [self.mesh])
        cmds.undo()
        self.assertEqual(len(cmds.ls(selection=True)), 2)
        Selection().select()
        self.assertEqual(cmds.ls(selection=True), [])
        Selection().select(mode="add")
        self.assertEqual(cmds.ls(selection=True), [])

    def test_select_validation(self):
        """modeとmissingの不正はValueError。missing=errorは変更前に失敗する。"""
        selection = Selection([self.node])
        with self.assertRaises(ValueError):
            selection.select(mode="toggle")
        with self.assertRaises(ValueError):
            Selection().select(missing="ignore")
        cmds.select(self.mesh, replace=True)
        cmds.delete(self.node)
        with self.assertRaises(RuntimeError):
            selection.select(missing="error")
        self.assertEqual(cmds.ls(selection=True), [self.mesh])
        self.assertEqual(selection.getNodes(), [])
        self.assertEqual(len(selection), 1)


class _Case(NamespaceCase):
    PREFIX = "mlibSpecRepr_"

    def setUp(self):
        super().setUp()
        transform = cmds.polyCube(name=self.name("box"), constructionHistory=False)[0]
        self.mesh = mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])
        self.mesh_name = self.mesh.getName()


class SelectionReadableReprTest(_Case):

    def test_repr_and_get_items(self):
        transform = self.mesh.getParent()
        plug = transform.getPlug("translateX")
        selection = Selection([transform, Vertex(self.mesh, 1), plug])
        self.assertEqual(repr(selection),
                         f"Selection([{transform!r}, Vertex('{self.mesh_name}.vtx[1]'), {plug!r}])")
        items = selection.getItems()
        self.assertEqual(items, selection.items)
        self.assertEqual(items, [transform, Vertex(self.mesh, 1), plug])
        items.append("extra")
        self.assertEqual(len(selection), 3)
        self.assertEqual(repr(Selection()), "Selection([])")
        many = Selection([Vertices(self.mesh), Edges(self.mesh)])
        text = repr(many)
        self.assertTrue(text.startswith("Selection([Vertex("))
        self.assertTrue(text.endswith(", ...], count=20)"))
        self.assertEqual(text.count("Vertex("), 8)
        self.assertEqual(text.count("Edge("), 2)

    @unittest.skipUnless(cmds.about(batch=True), "Batch-only empty result")
    def test_channel_box_plugs_are_empty_in_batch(self):
        self.assertEqual(Selection.getChannelBoxPlugs(), [])

    @unittest.skipIf(cmds.about(batch=True), "Requires the Maya GUI channel box")
    def test_channel_box_plugs_match_cmds_in_gui(self):
        """GUIでは、現在のChannel Boxの照会結果から組み立てたPlugと一致する。"""
        name = "mainChannelBox"
        expected = []
        for attributes_flag, objects_flag in selection_module._CHANNEL_BOX_SECTIONS:
            attributes = cmds.channelBox(name, query=True, **{attributes_flag: True}) or []
            for owner in cmds.channelBox(name, query=True, **{objects_flag: True}) or [] if attributes else []:
                for attribute in attributes:
                    if cmds.objExists(owner + "." + attribute):
                        expected.append(mlib.getPlug(owner + "." + attribute).getFullName())
        actual = [plug.getFullName() for plug in Selection.getChannelBoxPlugs()]
        self.assertEqual(actual, list(dict.fromkeys(expected)))

    def test_channel_box_plugs_from_simulated_channel_box(self):
        """Channel Boxの各区分の選択を、区分の順・選択順のPlugへ変換し、存在しない組合せと重複を除く。"""
        transform = self.mesh.getParent().getFullName()
        mesh = self.mesh.getFullName()
        other = self.make("transform", "other")
        answers = {
            "selectedMainAttributes": ["ty", "tx"],
            "mainObjectList": [transform, other],
            "selectedShapeAttributes": ["castsShadows", "noSuchAttr"],
            "shapeObjectList": [mesh],
            "selectedHistoryAttributes": None,
            "historyObjectList": [transform],
            "selectedOutputAttributes": ["tx"],
            "outputObjectList": [transform],
        }
        original_about = cmds.about
        original_channel_box = cmds.channelBox
        original_mel = selection_module.mel

        class _Mel(object):
            @staticmethod
            def eval(command):
                return "mainChannelBox"

        def about(*args, **kwargs):
            if kwargs.get("batch") or kwargs.get("b"):
                return False
            return original_about(*args, **kwargs)

        def channel_box(name, **kwargs):
            if kwargs.get("exists"):
                return True
            for flag, value in answers.items():
                if kwargs.get(flag):
                    return value
            raise AssertionError(kwargs)

        cmds.about = about
        cmds.channelBox = channel_box
        selection_module.mel = _Mel
        try:
            plugs = Selection.getChannelBoxPlugs()
        finally:
            cmds.about = original_about
            cmds.channelBox = original_channel_box
            selection_module.mel = original_mel
        self.assertEqual([plug.getFullName() for plug in plugs],
                         [mlib.getPlug(name).getFullName() for name in (
                             transform + ".ty", transform + ".tx", other + ".ty", other + ".tx",
                             mesh + ".castsShadows")])


def _distance(first, second):
    """2点の距離(Python 3.7 には math.dist が無いため)。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


class _SkinCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, max_influences=3):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True,
                                                 maximumInfluences=max_influences)[0])
        cmds.select(clear=True)
        return self.skin

    def raw(self, skin=None):
        skin = skin or self.skin
        return [round(value, 6) for value in skin.getWeights([self.root, self.mid, self.tip])]


class SoftSelectionTest(_SkinCase):

    def tearDown(self):
        cmds.softSelect(softSelectEnabled=self.soft_state)
        super().tearDown()

    def setUp(self):
        super().setUp()
        self.soft_state = cmds.softSelect(query=True, softSelectEnabled=True)

    def test_without_soft_select(self):
        """ソフト選択が無効なら、選んだ頂点を重み1で返す。"""
        cmds.softSelect(softSelectEnabled=False)
        plane = cmds.polyPlane(name=self.name("p"))[0]
        cmds.select(plane + ".vtx[3]", plane + ".vtx[5]")
        result = Selection.getSoftSelection()
        self.assertEqual(list(result.values()), [{3: 1.0, 5: 1.0}])
        self.assertEqual(list(result)[0], mlib.getNode(plane).getShape())
        cmds.select(clear=True)
        self.assertEqual(Selection.getSoftSelection(), {})

    def test_with_soft_select(self):
        """ソフト選択が有効なら、選んだ頂点は1、周りの頂点は0〜1の重みになる。"""
        cmds.softSelect(softSelectEnabled=True, softSelectDistance=0.5, softSelectFalloff=0)
        plane = cmds.polyPlane(name=self.name("p"), subdivisionsX=10, subdivisionsY=10)[0]
        cmds.select(plane + ".vtx[60]")
        weights = list(Selection.getSoftSelection().values())[0]
        self.assertAlmostEqual(weights[60], 1.0)
        self.assertGreater(len(weights), 1)
        self.assertTrue(all(0.0 < value <= 1.0 for value in weights.values()))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
