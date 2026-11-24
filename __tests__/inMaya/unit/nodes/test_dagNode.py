"""DAG共通基底と具象型の選択をMaya内で検証する。

あわせて次も確かめる。

- mlib Node/DAG APIを検証するMaya内テスト。
- Transform・DagNode・Joint・IkHandle のメソッドと createGroup を確かめる。
"""

import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import DagNode, Joint, Mesh, Node, Shape, Transform


class DagNodeTest(unittest.TestCase):
    """階層の共通化が参照と型の契約を維持することを確認する。"""

    def setUp(self):
        """テスト専用シーンを初期化する。"""
        cmds.file(new=True, force=True)

    def test_hierarchy_and_factory(self):
        """既存の具象型を維持し、DGのみのノードを拒否する。"""
        self.assertTrue(issubclass(Transform, DagNode))
        self.assertTrue(issubclass(Shape, DagNode))
        self.assertTrue(issubclass(DagNode, Node))
        for node_type, expected in (("transform", Transform), ("joint", Joint), ("mesh", Mesh)):
            name = cmds.createNode(node_type)
            self.assertIs(type(DagNode(name)), expected)
            self.assertIs(type(mlib.getNode(name)), expected)
        with self.assertRaises(TypeError):
            DagNode(cmds.createNode("network"))

    def test_shared_methods_and_parent(self):
        """共通実装を継承し、親取得とtransform取得の違いを保持する。"""
        for method in ("mpath",):
            self.assertIs(getattr(Transform, method), getattr(DagNode, method))
            self.assertIs(getattr(Shape, method), getattr(DagNode, method))
        parent = cmds.createNode("transform")
        child = cmds.createNode("transform", parent=parent)
        mesh = cmds.createNode("mesh", parent=child)
        root, transform, shape = map(DagNode, (parent, child, mesh))
        self.assertIsNone(root.getParent())
        self.assertEqual(transform.getParent(), root)
        self.assertEqual(shape.getParent(), transform)
        self.assertEqual(shape.getTransform(), transform)
        self.assertEqual(transform.getTransform(), transform)
        # mfn は最も具体的な function set(Transform は MFnTransform)。空の mesh の mfn() は MFnDagNode を返すので transform で確かめる。
        self.assertEqual(transform.mfn().object(), transform.mnode())
        self.assertIsInstance(transform.mfn(), om2.MFnTransform)


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

    def test_dag_paths_and_shapes(self):
        transform = self.create_transform("mlibNodeApiTransform")
        shape_name = cmds.createNode("mesh", parent=transform.getName())
        self.created.append(shape_name)
        shape = transform.getShape()

        self.assertEqual(transform.getName(full=True), "|" + transform.getName())
        self.assertEqual(len(transform.getShape(all=True)), 1)
        self.assertEqual(shape.getTransform().getName(), transform.getName())
        self.assertTrue(shape.getName(full=True).endswith("|" + shape_name))

    def test_ancestor_and_root_queries(self):
        grandparent = self.create_transform("mlibNodeApiRootGP")
        parent = self.create_transform("mlibNodeApiRootP")
        child = self.create_transform("mlibNodeApiRootC")
        parent.setParent(grandparent)
        child.setParent(parent)

        self.assertTrue(grandparent.isAncestorOf(child))
        self.assertTrue(grandparent.isAncestorOf(parent))
        self.assertTrue(parent.isAncestorOf(child))
        self.assertFalse(child.isAncestorOf(grandparent))
        self.assertFalse(grandparent.isAncestorOf(grandparent))

        self.assertEqual(child.getRoot().getName(full=True), grandparent.getName(full=True))
        self.assertEqual(parent.getRoot().getName(full=True), grandparent.getName(full=True))
        self.assertEqual(grandparent.getRoot().getName(full=True), grandparent.getName(full=True))

    def test_shape_is_intermediate_object(self):
        mesh_transform_name = cmds.polyCube(name="mlibNodeApiIntermediate", constructionHistory=False)[0]
        self.created.append(mesh_transform_name)
        shape = Node(mesh_transform_name).getShape()

        self.assertFalse(shape.isIntermediateObject())
        cmds.setAttr(shape.getName(full=True) + ".intermediateObject", True)
        self.assertTrue(shape.isIntermediateObject())

    def assert_channels(self, name, rotate, scale, places=9):
        for actual, expected in zip(cmds.getAttr(name + ".rotate")[0], rotate):
            self.assertAlmostEqual(actual, expected, places=places)
        for actual, expected in zip(cmds.getAttr(name + ".scale")[0], scale):
            self.assertAlmostEqual(actual, expected, places=places)


class _Case(NamespaceCase):
    """ノードを作る補助。"""

    PREFIX = "mlibDagAdd_"

    def transform(self, text="node#", parent=None):
        """transform を作り、ラッパーを返す。"""
        return mlib.getNode(cmds.ls(self.make("transform", text, parent), long=True)[0])

    def chain(self):
        """3つの joint の連鎖を作り、名前のリストを返す。"""
        cmds.select(clear=True)
        names = [cmds.joint(name=self.name(f"j{i}"), position=position) for i, position in enumerate(((0, 0, 0), (0, 2, 1), (0, 4, 0)))]
        cmds.select(clear=True)
        return [cmds.ls(name, long=True)[0] for name in names]

    def assertRaisesNoChange(self, error, read, call):
        """call が error を送出し、read の値を変えないことを確かめる。"""
        before = read()
        with self.assertRaises(error):
            call()
        self.assertEqual(read(), before)


class DagQueryTest(_Case):
    """getCommonAncestor・getBoundingBoxCorners・isInstanced・getInstanceIndex。"""

    def test_common_ancestor(self):
        root = self.transform("root#")
        hip = self.transform("hip#", root.getName(full=True))
        hand = self.transform("hand#", self.transform("arm#", hip.getName(full=True)).getName(full=True))
        foot = self.transform("foot#", self.transform("leg#", hip.getName(full=True)).getName(full=True))
        alone = self.transform("alone#")
        self.assertEqual(hand.getCommonAncestor(foot).getUuid(), hip.getUuid())
        self.assertEqual(hand.getCommonAncestor(foot.getName(full=True)).getUuid(), hip.getUuid())
        self.assertIs(hip.getCommonAncestor(hand), hip)
        self.assertEqual(hand.getCommonAncestor(root).getUuid(), root.getUuid())
        self.assertIs(hand.getCommonAncestor(hand), hand)
        self.assertIsNone(hand.getCommonAncestor(alone))
        network = cmds.createNode("network", name=self.name("net#"))
        with self.assertRaises(TypeError):
            hand.getCommonAncestor(network)
        cmds.delete(alone.getName(full=True))
        with self.assertRaises(RuntimeError):
            hand.getCommonAncestor(alone)

    def test_bounding_box_corners(self):
        """8隅は getBoundingBox の最小・最大の組み合わせ(ローカル・ワールドとも cmds.exactWorldBoundingBox と一致)。"""
        cube = cmds.polyCube(name=self.name("cube#"), width=2, height=4, depth=6, constructionHistory=False)[0]
        cmds.setAttr(cube + ".t", 1, 2, 3)
        cmds.setAttr(cube + ".r", 0, 45, 0)
        node = mlib.getNode(cube)
        corners = node.getBoundingBox(ws=True, corners=True)
        self.assertEqual(len(corners), 8)
        self.assertIsInstance(corners[0], mlib.Vector)
        xmin, ymin, zmin, xmax, ymax, zmax = cmds.exactWorldBoundingBox(cube)
        self.assertSequenceAlmostEqual(corners[0], (xmin, ymin, zmin), places=5)
        self.assertSequenceAlmostEqual(corners[1], (xmin, ymin, zmax), places=5)
        self.assertSequenceAlmostEqual(corners[7], (xmax, ymax, zmax), places=5)
        local = node.getShape().getBoundingBox(corners=True)
        self.assertSequenceAlmostEqual(local[0], (-1, -2, -3))
        self.assertSequenceAlmostEqual(local[7], (1, 2, 3))
        with self.assertRaises(TypeError):
            node.getBoundingBox(True, ws=True, corners=True)
        cmds.delete(cube)
        with self.assertRaises(RuntimeError):
            node.getBoundingBox(corners=True)

    def test_instances(self):
        cube = cmds.polyCube(name=self.name("cube#"), constructionHistory=False)[0]
        group = cmds.group(cube, name=self.name("grp#"))
        single = self.transform("single#")
        self.assertIs(single.isInstanced(), False)
        self.assertEqual(single.getInstanceIndex(), 0)
        cmds.instance(group, name=self.name("inst#"))
        shape = mlib.getNode(cmds.listRelatives(cube, shapes=True, fullPath=True)[0])
        instances = shape.getInstances()
        self.assertIs(shape.isInstanced(), True)
        self.assertEqual(sorted(node.getInstanceIndex() for node in instances), [0, 1])
        cmds.delete(single.getName(full=True))
        with self.assertRaises(RuntimeError):
            single.isInstanced()
        with self.assertRaises(RuntimeError):
            single.getInstanceIndex()


class MergedDagQueryTest(_Case):
    """フラグ・引数へまとめた DagNode の照会(getShape(all=)・getParent(instances=)・getBoundingBox(corners=)・getDrawColor(mode=))。"""

    def test_get_shape_all_by_node_kind(self):
        """getShape(all=True) は、Shape なら自身1つ、Transform なら直下の Shape すべて、それ以外の DAG ノードなら空の Nodes。"""
        cube = mlib.getNode(cmds.polyCube(name=self.name("cube#"))[0])
        cmds.select(clear=True)
        shape = cube.getShape()
        expected = [cmds.ls(name, long=True)[0] for name in cmds.listRelatives(cube.getName(full=True), shapes=True, noIntermediate=True, fullPath=True)]
        with self.subTest(kind="Transform"):
            shapes = cube.getShape(all=True)
            self.assertIsInstance(shapes, mlib.Nodes)
            self.assertEqual([node.getName(full=True) for node in shapes], expected)
            self.assertEqual(shapes[0], cube.getShape(0))
        with self.subTest(kind="Transform intermediates"):
            cmds.cluster(cube.getName(full=True))
            cmds.select(clear=True)
            every = cmds.listRelatives(cube.getName(full=True), shapes=True, fullPath=True)
            self.assertGreater(len(every), 1)
            self.assertEqual([node.getName(full=True) for node in cube.getShape(intermediates=True, all=True)], every)
            self.assertEqual([node.getName(full=True) for node in cube.getShape(all=True)], expected)
        with self.subTest(kind="Shape"):
            shapes = shape.getShape(all=True)
            self.assertIsInstance(shapes, mlib.Nodes)
            self.assertEqual(list(shapes), [shape])
            # Shape では intermediates を無視する。
            self.assertEqual(list(shape.getShape(intermediates=True, all=True)), [shape])
        with self.subTest(kind="empty Transform"):
            empty = self.transform().getShape(all=True)
            self.assertIsInstance(empty, mlib.Nodes)
            self.assertEqual(list(empty), [])
        with self.subTest(kind="other DagNode"):
            # Transform でも Shape でもない DAG ノードの動き(DagNode の実装)は、空の集まりと None。
            node = self.transform()
            others = DagNode.getShape(node, all=True)
            self.assertIsInstance(others, mlib.Nodes)
            self.assertEqual(list(others), [])
            self.assertIsNone(DagNode.getShape(node))

    def test_get_shape_all_rejects_index_and_non_bool(self):
        """all=True と index は同時に指定できず、all は bool だけ(Transform・Shape とも TypeError)。"""
        cube = mlib.getNode(cmds.polyCube(name=self.name("cube#"), constructionHistory=False)[0])
        for node in (cube, cube.getShape()):
            for call in (
                lambda: node.getShape(1, all=True),
                lambda: node.getShape(index=2, all=True),
                lambda: node.getShape(all=1),
                lambda: node.getShape(all=None),
            ):
                with self.subTest(node=type(node).__name__), self.assertRaises(TypeError):
                    call()
            # all=False(既定)は今までどおり1つ(無ければ None)。
            self.assertEqual(node.getShape(all=False), cube.getShape())
        self.assertIsNone(cube.getShape(5))

    def test_get_parent_instances_matches_cmds(self):
        """getParent(instances=True) は cmds.listRelatives(allParents=True) と同じ親、indirect=True は全インスタンスのパスの親。"""
        top = self.transform("top#")
        g1 = self.transform("g1#", top.getName(full=True))
        g2 = self.transform("g2#", top.getName(full=True))
        leaf = self.transform("leaf#", g1.getName(full=True))
        cmds.parent(leaf.getName(full=True), g2.getName(full=True), addObject=True, relative=True)
        cmds.select(clear=True)
        parents = leaf.getParent(instances=True)
        self.assertIsInstance(parents, mlib.Nodes)
        self.assertEqual([node.getName(full=True) for node in parents], cmds.listRelatives(leaf.getName(full=True), allParents=True, fullPath=True))
        self.assertEqual(parents, [g1, g2])
        indirect = leaf.getParent(instances=True, indirect=True)
        self.assertEqual([node.getName(full=True) for node in indirect], [g1.getName(full=True), g2.getName(full=True)])
        # ワールド直下は空の集まり。既定の getParent() は1つ(ワールド直下は None)。
        self.assertEqual(list(top.getParent(instances=True)), [])
        self.assertIsInstance(top.getParent(instances=True), mlib.Nodes)
        self.assertIsNone(top.getParent())
        self.assertEqual(leaf.getParent(), g1)
        self.assertEqual(leaf.getParent(2), top)

    def test_get_parent_exclusive_arguments(self):
        """instances=True と step は同時に指定できず、indirect は instances=True のときだけ使える(TypeError)。"""
        parent = self.transform("parent#")
        node = self.transform("node#", parent.getName(full=True))
        cases = (
            ("step", lambda: node.getParent(2, instances=True)),
            ("step keyword", lambda: node.getParent(step=0, instances=True)),
            ("indirect only", lambda: node.getParent(indirect=True)),
            ("instances int", lambda: node.getParent(instances=1)),
            ("indirect int", lambda: node.getParent(instances=True, indirect=1)),
            ("positional", lambda: node.getParent(1, True)),
        )
        for label, call in cases:
            with self.subTest(label), self.assertRaises(TypeError):
                call()

    def test_bounding_box_corners_with_invisible(self):
        """getBoundingBox(corners=True, includeInvisible=True) は、非表示の子を含むボックスの8つの隅を返す。"""
        group = self.transform("group#")
        shown = cmds.polyCube(name=self.name("shown#"), constructionHistory=False)[0]
        hidden = cmds.polyCube(name=self.name("hidden#"), constructionHistory=False)[0]
        shown, hidden = cmds.parent(shown, hidden, group.getName(full=True))
        cmds.setAttr(hidden + ".translate", 5, 2, -3)
        cmds.setAttr(hidden + ".visibility", False)
        cmds.setAttr(group.getName(full=True) + ".translate", 1, 0, 0)
        cmds.select(clear=True)
        for world in (False, True):
            for invisible in (False, True):
                with self.subTest(worldSpace=world, includeInvisible=invisible):
                    box = group.getBoundingBox(ws=world, includeInvisible=invisible)
                    corners = group.getBoundingBox(ws=world, includeInvisible=invisible, corners=True)
                    self.assertEqual(len(corners), 8)
                    self.assertTrue(all(isinstance(corner, mlib.Vector) for corner in corners))
                    expected = [(x, y, z) for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]
                    for corner, values in zip(corners, expected):
                        self.assertSequenceAlmostEqual(tuple(corner), values)
                    if invisible and world:
                        raw = cmds.xform(group.getName(full=True), query=True, boundingBoxInvisible=True, worldSpace=True)
                        self.assertSequenceAlmostEqual(tuple(corners[0]), raw[:3])
                        self.assertSequenceAlmostEqual(tuple(corners[7]), raw[3:])
        visible = group.getBoundingBox(ws=True, corners=True)
        included = group.getBoundingBox(ws=True, corners=True, includeInvisible=True)
        # 非表示の子(x=5 の先)を含めると、最大の隅が広がる。
        self.assertGreater(included[7].x, visible[7].x + 1.0)
        for flags in ({"corners": 1}, {"includeInvisible": 1}, {"corners": True, "includeInvisible": None}):
            with self.subTest(flags=flags), self.assertRaises(TypeError):
                group.getBoundingBox(**flags)

    def test_draw_color_modes(self):
        """getDrawColor(mode=) は MFnDagNode の描画色と同じ値を返す。既定は dormant。知らない名前は ValueError、str 以外は TypeError。"""
        import maya.OpenMaya as om1  # API 1.0 の MFnDagNode と突き合わせるため。

        curve = mlib.getNode(cmds.circle(name=self.name("circle#"), constructionHistory=False)[0]).getShape()
        cmds.select(clear=True)
        selection = om1.MSelectionList()
        selection.add(curve.getName(full=True))
        path = om1.MDagPath()
        selection.getDagPath(0, path)
        fn = om1.MFnDagNode(path)
        for mode, raw in (("dormant", fn.dormantColor), ("active", fn.activeColor), ("hilite", fn.hiliteColor)):
            with self.subTest(mode=mode):
                color = raw()
                self.assertSequenceAlmostEqual(curve.getDrawColor(mode=mode), (color.r, color.g, color.b, color.a))
        self.assertEqual(curve.getDrawColor(), curve.getDrawColor(mode="dormant"))
        self.assertIsNone(curve.getDrawColor(mode="override"))
        curve.setColor((1.0, 0.5, 0.25))
        override = curve.getDrawColor(mode="override")
        self.assertSequenceAlmostEqual(override[:3], (1.0, 0.5, 0.25))
        for mode, error in (("Dormant", ValueError), ("", ValueError), ("selected", ValueError), (0, TypeError), (None, TypeError)):
            with self.subTest(mode=mode), self.assertRaises(error):
                curve.getDrawColor(mode=mode)
        with self.assertRaises(TypeError):
            curve.getDrawColor("active")


if __name__ == "__main__":
    unittest.main()
