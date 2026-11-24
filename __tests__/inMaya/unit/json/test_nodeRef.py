"""``mlib.json.nodeRef`` のテスト。

- mlib.json の基盤(codec・file・名前の対応付け・参照・Snapshot 基底)を確かめる。
"""

import json as std_json
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.json import ComponentRef, NameMapping, NodeRef, PlugRef, Snapshot


class ReferenceTest(NamespaceCase):
    """ノード・Plug・コンポーネントの参照。"""

    PREFIX = "mlibSpecJsonRef_"

    def setUp(self):
        super().setUp()
        self.other = self.ns + "B"
        cmds.namespace(add=self.other)
        self.extra_namespaces.append(self.other)
        self.root = cmds.createNode("transform", name=self.name("root"))
        self.joint = cmds.createNode("joint", name=self.name("arm"), parent=self.root)
        self.root_b = cmds.createNode("transform", name=self.other + ":root")
        self.joint_b = cmds.createNode("joint", name=self.other + ":arm", parent=self.root_b)

    def test_node_ref(self):
        ref = NodeRef.capture(self.joint)
        self.assertEqual(ref.name, self.name("arm"))
        self.assertEqual(ref.type, "joint")
        self.assertTrue(ref.path.startswith("|"))
        self.assertEqual(NodeRef._from_data(std_json.loads(std_json.dumps(ref._to_data()))), ref)
        self.assertEqual(ref.resolve().getName(full=True), cmds.ls(self.joint, long=True)[0])
        mapped = ref.resolve(NameMapping(namespaceMap={self.ns: self.other}))
        self.assertEqual(mapped.getName(full=True), cmds.ls(self.joint_b, long=True)[0])
        self.assertIsNone(ref.resolve(NameMapping(namespaceMap={self.ns: "missingNs"})))

    def test_node_ref_type_and_ambiguity(self):
        ref = NodeRef.capture(self.joint)
        full = cmds.ls(self.joint, long=True)[0]
        wrong_type = NodeRef(ref.name, ref.path, "transform")
        self.assertIsNone(wrong_type.resolve())
        twin = cmds.createNode("joint", name=self.name("arm"), parent=cmds.createNode("transform", name=self.name("g")))
        self.assertEqual(ref.resolve().getName(full=True), full)
        self.assertIsNone(NodeRef(ref.name, None, "joint").resolve())
        self.assertTrue(cmds.objExists(twin))

    def test_plug_ref(self):
        node = mlib.getNode(self.joint)
        ref = PlugRef.capture(node.getPlug("tx"))
        self.assertEqual(ref.attribute, "translateX")
        self.assertEqual(PlugRef.capture(self.joint + ".worldMatrix[0]").attribute, "worldMatrix[0]")
        self.assertEqual(PlugRef._from_data(ref._to_data()), ref)
        plug = ref.resolve(NameMapping(namespaceMap={self.ns: self.other}))
        self.assertEqual(plug.getNode(), mlib.getNode(self.joint_b))
        self.assertEqual(plug.getAttributeName("short"), "tx")
        self.assertIsNone(PlugRef(ref.node, "noSuchAttr").resolve())

    def test_component_ref(self):
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        shape = mlib.getNode(cube).getShape()
        ref = ComponentRef.capture(shape.getVertices([5, 1, 3]))
        self.assertEqual(ref.type, "vtx")
        self.assertEqual(ref.indices, (5, 1, 3))
        self.assertEqual(ComponentRef._from_data(ref._to_data()), ref)
        resolved = ref.resolve()
        self.assertEqual(resolved.indices, (5, 1, 3))
        self.assertEqual(ComponentRef.capture(shape.getVertices([2])[0]).indices, (2,))
        self.assertIsNone(ComponentRef(ref.node, "vtx", [100]).resolve())
        with self.assertRaises(ValueError):
            ComponentRef(ref.node, "pt", [1])

    def test_repr_and_equality(self):
        """3つの参照の表記と、ほかの型との比較を確かめる。"""
        node = NodeRef("chrA:arm", "|chrA:arm", "joint")
        plug = PlugRef(node, "translateX")
        component = ComponentRef(node, "vtx", [1, 2, 3])
        self.assertEqual(repr(node), "NodeRef('chrA:arm', type='joint')")
        self.assertEqual(repr(plug), "PlugRef('chrA:arm.translateX')")
        self.assertEqual(repr(component), "ComponentRef('chrA:arm', 'vtx', 3 indices)")
        for ref in (node, plug, component):
            with self.subTest(ref=repr(ref)):
                self.assertNotEqual(ref, "chrA:arm")
                self.assertIs(ref.__eq__(1), NotImplemented)
        self.assertNotEqual(plug, PlugRef(node, "translateY"))
        self.assertNotEqual(component, ComponentRef(node, "vtx", [1, 2]))
        self.assertEqual(NodeRef("a", "", "").path, None)
        self.assertEqual(plug._mapped_name(NameMapping(namespaceMap={"chrA": "chrB"})), "chrB:arm.translateX")

    def test_invalid_arguments(self):
        """参照の作成の不正な引数を、docstringどおりの例外の型にすることを確かめる。"""
        node = NodeRef("a")
        for factory, error in (
            (lambda: NodeRef(1), TypeError),
            (lambda: NodeRef(""), ValueError),
            (lambda: NodeRef("|a"), ValueError),
            (lambda: NodeRef("a", 1), TypeError),
            (lambda: NodeRef("a", None, 1), TypeError),
            (lambda: PlugRef("a", "tx"), TypeError),
            (lambda: PlugRef(node, 1), TypeError),
            (lambda: PlugRef(node, ""), ValueError),
            (lambda: ComponentRef("a", "vtx", [0]), TypeError),
            (lambda: ComponentRef(node, "vtx", [1.0]), TypeError),
            (lambda: ComponentRef(node, "vtx", [True]), TypeError),
            (lambda: ComponentRef(node, "vtx", [-1]), ValueError),
            (lambda: ComponentRef.capture(self.joint), TypeError),
        ):
            with self.subTest(error=error), self.assertRaises(error):
                factory()
        for ref_type in (NodeRef, PlugRef, ComponentRef):
            with self.subTest(ref_type=ref_type.__name__), self.assertRaises(TypeError):
                ref_type._from_data({"name": "a", "node": {"name": "a"}, "attr": "tx", "type": "vtx", "indices": [0]}).resolve("a")

    @unittest.expectedFailure
    def test_capture_missing_raises_value_error(self):
        """docstringのとおり、無いノード・Plugの記録をValueErrorにすることを確かめる。"""
        # findings/json.md「NodeRef.capture・PlugRef.captureの無いものの例外の型」: 実際はRuntimeError・MissingAttributeError。
        with self.assertRaises(ValueError):
            NodeRef.capture(self.name("noSuchNode"))
        with self.assertRaises(ValueError):
            PlugRef.capture(self.joint + ".noSuchAttr")

    def test_invalid_data(self):
        """壊れた参照の辞書をValueErrorにすることを確かめる。"""
        node = {"name": "a", "path": None, "type": None}
        for factory, data in (
            (NodeRef._from_data, []),
            (NodeRef._from_data, {"path": "|a"}),
            (NodeRef._from_data, {"name": 1}),
            (NodeRef._from_data, {"name": "a", "type": 5}),
            (PlugRef._from_data, {"node": node}),
            (PlugRef._from_data, {"node": node, "attr": 1}),
            (PlugRef._from_data, {"node": {"name": 1}, "attr": "tx"}),
            (ComponentRef._from_data, []),
            (ComponentRef._from_data, {"node": node, "type": "vtx"}),
            (ComponentRef._from_data, {"node": node, "type": "vtx", "indices": [0.5]}),
            (ComponentRef._from_data, {"node": node, "type": "vtx", "indices": [-1]}),
            (ComponentRef._from_data, {"node": node, "type": "bogus", "indices": [0]}),
        ):
            with self.subTest(data=data), self.assertRaises(ValueError):
                factory(data)

    def test_capture_deleted_and_resolve_missing(self):
        """削除したノード・Plugの記録をRuntimeErrorにし、シェイプが無いコンポーネントはNoneを返すことを確かめる。"""
        node = mlib.getNode(self.joint)
        plug = node.getPlug("tx")
        cmds.delete(self.joint)
        with self.assertRaises(RuntimeError):
            NodeRef.capture(node)
        with self.assertRaises(RuntimeError):
            PlugRef.capture(plug)
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        ref = ComponentRef.capture(mlib.getNode(cube).getShape().getVertices([0]))
        self.assertEqual(ref.resolve(NameMapping(namespaceMap={self.ns: self.other})), None)
        self.assertEqual(ref._mapped_name(NameMapping(namespaceMap={self.ns: self.other})), self.other + ":cubeShape.vtx[...]")


class _OffsetSnapshot(Snapshot):
    """テスト用: ノードの translateX を書く最小の種類。"""

    FORMAT = "mlib.test.offset"
    VERSION = 1

    @classmethod
    def capture(cls, nodes):
        return cls({"items": [{"node": NodeRef.capture(node)._to_data(), "value": cmds.getAttr(str(node) + ".tx")} for node in nodes]})

    def apply(self, *, nameMap=None, replace=None, namespaceMap=None, fail=False):
        return self._run_apply({"nameMap": nameMap, "replace": replace, "namespaceMap": namespaceMap}, {"fail": fail})

    def _validate(self, mapping, report, options):
        for item in self._data["items"]:
            ref = NodeRef._from_data(item["node"])
            if ref.resolve(mapping) is None:
                report._add_missing(ref._mapped_name(mapping))
            if item["value"] < 0:
                report._add_error("negative value")

    def _apply(self, mapping, report, options, fast):
        for item in self._data["items"]:
            node = NodeRef._from_data(item["node"]).resolve(mapping)
            if node is not None:
                cmds.setAttr(node.getName(full=True) + ".tx", item["value"])
        if options["fail"]:
            raise RuntimeError("fail on purpose")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
