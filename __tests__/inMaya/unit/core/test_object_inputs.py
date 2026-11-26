"""各基底クラスの名前・Node・Plug入力解決 を検証するMaya内テスト。"""

import sys
import unittest
import uuid

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()
from mlib.common.selection import Selection
from mlib.components import Vertex, Vertices
from mlib.nodes import Node
from mlib.plugs import MultiPlug, Plug


class CoerceTest(unittest.TestCase):
    """Node/文字列の混在入力を正規化する共通ヘルパーを検証する。"""

    def setUp(self):
        self.created = []

    def tearDown(self):
        for name in reversed(self.created):
            if cmds.objExists(name):
                cmds.delete(name)

    def create_transform(self, name):
        node_name = cmds.createNode("transform", name=name)
        self.created.append(node_name)
        return Node(node_name)

    def test_to_name_passes_through_string_without_resolving(self):
        # 存在しない名前でも解決を試みず、そのまま返す。
        from mlib.core.object import Object

        self.assertEqual(Object._input_name("doesNotExistYet"), "doesNotExistYet")

    def test_to_name_uses_full_name_for_node(self):
        from mlib.core.object import Object

        node = self.create_transform("mlibCoerceToName")
        self.assertEqual(Object._input_name(node), node.getName(full=True))

    def test_to_name_rejects_invalid_types_and_empty_string(self):
        from mlib.core.object import Object

        with self.assertRaises(TypeError):
            Object._input_name(123)
        with self.assertRaises(ValueError):
            Object._input_name("")

    def test_to_names_wraps_single_node_or_string(self):
        from mlib.core.object import Object

        node = self.create_transform("mlibCoerceToNamesSingle")
        self.assertEqual(Object._input_names(node), [node.getName(full=True)])
        self.assertEqual(Object._input_names("literalName"), ["literalName"])

    def test_to_names_rejects_mixed_iterable(self):
        from mlib.core.object import Object

        node = self.create_transform("mlibCoerceToNamesMixed")
        with self.assertRaises(TypeError):
            Object._input_names([node, "literalName"])

    def test_to_names_empty_iterable_returns_empty_list(self):
        from mlib.core.object import Object

        self.assertEqual(Object._input_names([]), [])

    def test_to_names_propagates_element_errors(self):
        from mlib.core.object import Object

        with self.assertRaises(TypeError):
            Object._input_names([123])
        with self.assertRaises(ValueError):
            Object._input_names([""])

    def test_to_node_returns_same_instance_for_node_input(self):
        from mlib.nodes.node import Node

        node = self.create_transform("mlibCoerceToNodeSame")
        self.assertIs(Node._resolve_input(node), node)

    def test_to_node_resolves_string_to_node(self):
        from mlib.nodes.node import Node

        node = self.create_transform("mlibCoerceToNodeResolve")
        resolved = Node._resolve_input(node.getName())
        self.assertIsInstance(resolved, Node)
        self.assertEqual(resolved.getName(full=True), node.getName(full=True))

    def test_to_node_rejects_invalid_type(self):
        from mlib.nodes.node import Node

        with self.assertRaises(TypeError):
            Node._resolve_input(123)

    def test_to_node_raises_when_string_does_not_resolve(self):
        from mlib.nodes.node import Node

        with self.assertRaises(RuntimeError):
            Node._resolve_input("mlibCoerceDoesNotExist")


class CoerceObjectInputTest(unittest.TestCase):
    """Plug・コンポーネント・om2 オブジェクト・コレクションの正規化を検証する。"""

    def setUp(self):
        self.namespace = "mlibCoerce_" + uuid.uuid4().hex[:12]
        cmds.namespace(add=self.namespace)
        cmds.namespace(setNamespace=":" + self.namespace)
        self.group = Node(cmds.createNode("transform", name="grp"))
        self.other_group = Node(cmds.createNode("transform", name="otherGrp"))
        # 短い名前が重複するノード(grp|dup と otherGrp|dup)。
        self.node = Node(cmds.createNode("transform", name="dup", parent=self.group.getName(full=True)))
        self.twin = Node(cmds.createNode("transform", name="dup", parent=self.other_group.getName(full=True)))
        self.network = Node(cmds.createNode("network", name="net"))
        self.cube = cmds.polyCube(name="cube", constructionHistory=False)[0]
        self.mesh = Node(self.cube).getShape()

    def tearDown(self):
        cmds.namespace(setNamespace=":")
        if cmds.namespace(exists=":" + self.namespace):
            cmds.namespace(removeNamespace=":" + self.namespace, deleteNamespaceContent=True)

    def test_plug_and_mplug_become_unique_plug_names(self):
        from mlib.core.object import Object
        from mlib.nodes.node import Node

        plug = self.node.getPlug("tx")
        expected = self.node.getName() + ".translateX"
        self.assertEqual(Object._input_name(plug), expected)
        self.assertEqual(Object._input_name(plug.mplug()), expected)
        # MPlug.name() は短いノード名だけのため同名ノードと区別できない。
        self.assertNotEqual(plug.mplug().name(), expected)
        self.assertEqual(len(cmds.ls(Object._input_name(plug.mplug()))), 1)
        self.assertEqual(Plug._plug_path(plug.mplug()), "translateX")
        self.assertEqual(Node._unique_node_name(self.node.mnode()), self.node.getName())

    def test_multi_plug_is_not_expanded(self):
        from mlib.core.object import Object

        self.network.addAttr("values", attributeType="double", multi=True)
        multi_plug = self.network.getPlug("values")
        multi_plug[0].set(1.0)
        self.assertIsInstance(multi_plug, MultiPlug)
        self.assertEqual(Object._input_name(multi_plug), self.network.getName() + ".values")
        self.assertEqual(Object._input_names(multi_plug), [self.network.getName() + ".values"])
        self.assertEqual(Object._input_names([multi_plug, multi_plug[0]]), [self.network.getName() + ".values", self.network.getName() + ".values[0]"])

    def test_components_are_expanded(self):
        from mlib.core.object import Object

        vertex = Vertex(self.mesh, 1)
        vertices = Vertices(self.mesh, [2, 3])
        prefix = self.mesh.getName(full=True) + ".vtx"
        self.assertEqual(Object._input_name(vertex), prefix + "[1]")
        # 連続する番号は範囲指定にまとめる(要素ごとの名前は getNames(full=True))。
        self.assertEqual(Object._input_names(vertices), [prefix + "[2:3]"])
        self.assertEqual(vertices.getNames(full=True), [prefix + "[2]", prefix + "[3]"])
        self.assertEqual(Object._input_names([vertex, vertices]), [prefix + "[1]", prefix + "[2:3]"])
        with self.assertRaises(TypeError):
            Object._input_name(vertices)

    def test_compact_names_keep_held_order(self):
        from mlib.core.object import Object

        prefix = self.mesh.getName(full=True) + ".vtx"
        vertices = Vertices(self.mesh, [0, 1, 2, 5, 3, 4, 7])
        self.assertEqual(vertices.getNames(full=True, compact=True), [prefix + "[0:2]", prefix + "[5]", prefix + "[3:4]", prefix + "[7]"])
        self.assertEqual(Vertices(self.mesh, []).getNames(full=True, compact=True), [])
        self.assertEqual(Object._input_names(Vertices(self.mesh, [])), [])
        # 展開した結果は要素ごとの名前と同じ順序・同じ要素になる。
        expanded = cmds.ls(vertices.getNames(full=True, compact=True), flatten=True, long=True)
        self.assertEqual(sorted(expanded), sorted(cmds.ls(vertices.getNames(full=True), flatten=True, long=True)))
        # compact=True だけなら、最短の名前のまま範囲にまとめる。展開すると要素ごとの名前(getNames())に戻る。
        short = vertices.getNames(compact=True)
        short_prefix = cmds.ls(prefix + "[0]")[0].rsplit("[", 1)[0]
        self.assertEqual(short, [short_prefix + "[0:2]", short_prefix + "[5]", short_prefix + "[3:4]", short_prefix + "[7]"])
        self.assertEqual(cmds.ls(short, flatten=True), vertices.getNames())
        self.assertEqual(cmds.ls(short, flatten=True, long=True), cmds.ls(vertices.getNames(full=True), flatten=True, long=True))
        self.assertEqual(Vertices(self.mesh, []).getNames(compact=True), [])
        # 既定(full=False・compact=False)を明示しても同じ。
        self.assertEqual(vertices.getNames(full=False, compact=False), vertices.getNames())
        for flags in ({"full": 1}, {"compact": 1}, {"full": None}, {"compact": "yes"}):
            with self.subTest(flags=flags):
                with self.assertRaises(TypeError):
                    vertices.getNames(**flags)
        everything = Vertices(self.mesh)
        self.assertEqual(Object._input_names(everything), [prefix + f"[0:{self.mesh.getNumVertices() - 1:d}]"])
        # 検証はまとめて行い、範囲外の番号を含むコレクションは ValueError になる。
        cmds.polyDelFacet(self.mesh.getName(full=True) + ".f[0:4]")
        with self.assertRaises(ValueError):
            Object._input_names(vertices)

    def test_api_objects(self):
        from mlib.core.object import Object

        self.assertEqual(Object._input_name(self.node.mnode()), self.node.getName(full=True))
        self.assertEqual(Object._input_name(self.network.mnode()), self.network.getName())
        self.assertEqual(Object._input_name(self.node.mpath()), self.node.getName(full=True))
        with self.assertRaises(TypeError):
            Object._input_name(self.node.getPlug("tx").mplug().attribute())
        with self.assertRaises(ValueError):
            Object._input_name(om2.MObject())
        with self.assertRaises(ValueError):
            Object._input_name(om2.MPlug())

    def test_instanced_dag_path_is_preserved(self):
        from mlib.core.object import Object

        instance = cmds.instance(self.cube, name="cubeInstance")[0]
        selection = om2.MSelectionList()
        selection.add(instance + "|" + self.mesh.getName(short=True))
        path = selection.getDagPath(0)
        self.assertIn("cubeInstance", Object._input_name(path))
        self.assertEqual(Object._input_name(path), path.fullPathName())

    def test_nested_iterables_selection_and_generators(self):
        from mlib.core.object import Object

        vertex = Vertex(self.mesh, 0)
        selection = Selection([self.twin, vertex])
        names = Object._input_names([self.node, [self.twin.mnode(), (item for item in [vertex])], selection])
        self.assertEqual(
            names,
            [self.node.getName(full=True), self.twin.getName(full=True), vertex.getName(full=True), self.twin.getName(full=True), vertex.getName(full=True)],
        )

    def test_invalid_objects_raise_value_error(self):
        from mlib.core.object import Object

        plug = self.twin.getPlug("tx")
        mobject = self.twin.mnode()
        path = self.twin.mpath()
        mplug = plug.mplug()
        vertex = Vertex(self.mesh, 0)
        cmds.delete(self.twin.getName(full=True), self.cube)
        for value in (self.twin, plug, mobject, path, mplug, vertex):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(ValueError):
                    Object._input_name(value)

    def test_to_node_resolves_owners(self):
        from mlib.nodes.node import Node

        plug = self.node.getPlug("tx")
        self.assertIs(Node._resolve_input(plug), self.node)
        self.assertEqual(Node._resolve_input(plug.mplug()).getName(full=True), self.node.getName(full=True))
        self.assertEqual(Node._resolve_input(self.node.mnode()).getName(full=True), self.node.getName(full=True))
        self.assertEqual(Node._resolve_input(self.node.mpath()).getName(full=True), self.node.getName(full=True))
        self.assertIs(Node._resolve_input(Vertex(self.mesh, 0)), self.mesh)
        self.assertIs(Node._resolve_input(Vertices(self.mesh, [0, 1])), self.mesh)
        with self.assertRaises(TypeError):
            Node._resolve_input(Selection([self.node]))

    def test_to_node_rejects_plugs_of_deleted_attributes(self):
        from mlib.core.object import Object
        from mlib.nodes.node import Node
        from mlib.plugs.plug import DeletedAttributeError

        plug = self.network.addAttr("doomed", attributeType="double")
        mplug = om2.MPlug(plug.mplug())
        self.assertIs(Node._resolve_input(plug), self.network)
        self.assertEqual(Node._resolve_input(mplug).getName(full=True), self.network.getName(full=True))
        cmds.deleteAttr(self.network.getName() + ".doomed")
        # 所有ノードは有効なため、所有ノードを返すと削除済みの対象を黙って受け付けてしまう。
        # to_name と同じく ValueError(クラスの親は1つにする決まりのため、RuntimeError の派生ではない)。
        for value in (plug, mplug):
            for convert in (Node._resolve_input, Object._input_name, Node._input_name):
                with self.subTest(value=type(value).__name__, convert=convert.__name__):
                    with self.assertRaises(ValueError):
                        convert(value)
            with self.assertRaises(DeletedAttributeError) as context:
                Node._resolve_input(value)
            self.assertNotIsInstance(context.exception, RuntimeError)
        # 所有ノードが削除済みの Plug は従来どおり無効な所有ノードを返す(扱いは呼び出し側)。
        doomed = self.twin.getPlug("tx")
        cmds.delete(self.twin.getName(full=True))
        self.assertIs(Node._resolve_input(doomed), self.twin)
        self.assertFalse(Node._resolve_input(doomed).isValid())

    def test_to_node_name_resolves_owner_full_paths(self):
        from mlib.nodes.node import Node

        plug = self.node.getPlug("tx")
        self.assertEqual(Node._input_name(plug), self.node.getName(full=True))
        self.assertEqual(Node._input_name(plug.mplug()), self.node.getName(full=True))
        self.assertEqual(Node._input_name(plug.getName(full=True)), self.node.getName(full=True))
        self.assertEqual(Node._input_name(Vertex(self.mesh, 0)), self.mesh.getName(full=True))
        self.assertEqual(Node._input_name(self.network.mnode()), self.network.getName())
        with self.assertRaises(TypeError):
            Node._input_name(Vertices(self.mesh, [0, 1]))
        with self.assertRaises(RuntimeError):
            Node._input_name(self.node.getName(short=True))  # 2つの dup に一致する
        doomed = self.twin.getPlug("tx")
        cmds.delete(self.twin.getName(full=True))
        with self.assertRaises(ValueError):
            Node._input_name(doomed)
        with self.assertRaises(ValueError):
            Node._input_name("")

    def test_to_plug(self):

        plug = self.node.getPlug("tx")
        self.assertIs(Plug._resolve_input(plug), plug)
        self.assertEqual(Plug._resolve_input(plug.mplug()).getName(full=True), plug.getName(full=True))
        self.assertEqual(Plug._resolve_input(plug.getName(full=True)).getName(full=True), plug.getName(full=True))
        with self.assertRaises(RuntimeError):
            # 短い名前だけでは2つの dup に一致する(存在しない名前と同じく解決できない)。
            Plug._resolve_input(self.node.getName(short=True) + ".tx")
        with self.assertRaises(TypeError):
            Plug._resolve_input(self.node.getName(full=True))
        with self.assertRaises(AttributeError):
            Plug._resolve_input(self.node.getName(full=True) + ".mlibCoerceMissing")
        with self.assertRaises(TypeError):
            Plug._resolve_input(self.node)
        self.assertIsInstance(Plug._resolve_input(plug.mplug()), Plug)

    def test_to_names_can_reject_plugs(self):
        from mlib.core.object import Object

        plug = self.node.getPlug("tx")
        names = [self.node.getName(full=True), plug.getName(full=True)]
        self.assertEqual(Object._input_names([self.node, plug]), names)
        for value in (plug, plug.mplug(), [self.node, [plug]], Selection([self.node, plug])):
            with self.subTest(value=type(value).__name__):
                with self.assertRaises(TypeError):
                    Object._input_names(value, allow_plugs=False)
        # 文字列は解決しないため、アトリビュート名の文字列はそのまま渡す。
        self.assertEqual(Object._input_names(names, allow_plugs=False), names)

    def test_attribute_path_plug(self):

        average = Node(cmds.createNode("plusMinusAverage", name="pma"))
        mobject = average.mnode()
        cases = {"input1D[3]": "input1D[3]", "input3D[2].input3Dx": "input3D[2].input3Dx", "i3[2].i3y": "input3D[2].input3Dy", "output3D": "output3D"}
        for path, expected in cases.items():
            with self.subTest(path=path):
                mplug = Plug._attribute_path_plug(mobject, path)
                self.assertEqual(Plug._plug_path(mplug), expected)
                self.assertFalse(Plug._has_unresolved_index(mplug))
        for path in (
            "input3Dx",
            "input1D[0:2]",
            "missing",
            "operation[0]",
            "input1D.foo",
            "input3D.input3Dx",
            "input1D[2147483648]",
            "input1D[4294967296]",
            "input3D[4294967297].input3Dx",
        ):
            with self.subTest(path=path):
                self.assertIsNone(Plug._attribute_path_plug(mobject, path))
        # 論理番号の上限(符号付き 32 ビット整数の最大値)までは解決する。
        self.assertEqual(Plug._attribute_path_plug(mobject, "input1D[2147483647]").logicalIndex(), 2147483647)
        self.assertEqual(list(average.getPlug("input1D").mplug().getExistingArrayAttributeIndices()), [])
        cmds.aliasAttr("mlibCoerceAlias", average.getName() + ".input1D[4]")
        self.assertEqual(Plug._plug_path(Plug._attribute_path_plug(mobject, "mlibCoerceAlias")), "mlibCoerceAlias")
        self.assertEqual(Plug._attribute_path_plug(mobject, "mlibCoerceAlias").logicalIndex(), 4)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
