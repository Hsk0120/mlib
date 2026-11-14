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
        self.assertEqual(NodeRef.fromData(std_json.loads(std_json.dumps(ref.toData()))), ref)
        self.assertEqual(ref.resolve().getFullName(), cmds.ls(self.joint, long=True)[0])
        mapped = ref.resolve(NameMapping(namespaceMap={self.ns: self.other}))
        self.assertEqual(mapped.getFullName(), cmds.ls(self.joint_b, long=True)[0])
        self.assertIsNone(ref.resolve(NameMapping(namespaceMap={self.ns: "missingNs"})))

    def test_node_ref_type_and_ambiguity(self):
        ref = NodeRef.capture(self.joint)
        full = cmds.ls(self.joint, long=True)[0]
        wrong_type = NodeRef(ref.name, ref.path, "transform")
        self.assertIsNone(wrong_type.resolve())
        twin = cmds.createNode("joint", name=self.name("arm"), parent=cmds.createNode("transform", name=self.name("g")))
        self.assertEqual(ref.resolve().getFullName(), full)
        self.assertIsNone(NodeRef(ref.name, None, "joint").resolve())
        self.assertTrue(cmds.objExists(twin))

    def test_plug_ref(self):
        node = mlib.getNode(self.joint)
        ref = PlugRef.capture(node.getPlug("tx"))
        self.assertEqual(ref.attribute, "translateX")
        self.assertEqual(PlugRef.capture(self.joint + ".worldMatrix[0]").attribute, "worldMatrix[0]")
        self.assertEqual(PlugRef.fromData(ref.toData()), ref)
        plug = ref.resolve(NameMapping(namespaceMap={self.ns: self.other}))
        self.assertEqual(plug.getNode(), mlib.getNode(self.joint_b))
        self.assertEqual(plug.getShortName(), "tx")
        self.assertIsNone(PlugRef(ref.node, "noSuchAttr").resolve())

    def test_component_ref(self):
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        shape = mlib.getNode(cube).getShape()
        ref = ComponentRef.capture(shape.getVertices([5, 1, 3]))
        self.assertEqual(ref.type, "vtx")
        self.assertEqual(ref.indices, (5, 1, 3))
        self.assertEqual(ComponentRef.fromData(ref.toData()), ref)
        resolved = ref.resolve()
        self.assertEqual(resolved.indices, (5, 1, 3))
        self.assertEqual(ComponentRef.capture(shape.getVertices([2])[0]).indices, (2,))
        self.assertIsNone(ComponentRef(ref.node, "vtx", [100]).resolve())
        with self.assertRaises(ValueError):
            ComponentRef(ref.node, "pt", [1])


class _OffsetSnapshot(Snapshot):
    """テスト用: ノードの translateX を書く最小の種類。"""

    FORMAT = "mlib.test.offset"
    VERSION = 1

    @classmethod
    def capture(cls, nodes):
        return cls({"items": [{"node": NodeRef.capture(node).toData(), "value": cmds.getAttr(str(node) + ".tx")} for node in nodes]})

    def apply(self, *, nameMap=None, replace=None, namespaceMap=None, fail=False):
        return self._run_apply({"nameMap": nameMap, "replace": replace, "namespaceMap": namespaceMap}, {"fail": fail})

    def _validate(self, mapping, report, options):
        for item in self._data["items"]:
            ref = NodeRef.fromData(item["node"])
            if ref.resolve(mapping) is None:
                report.addMissing(ref.mappedName(mapping))
            if item["value"] < 0:
                report.addError("negative value")

    def _apply(self, mapping, report, options, fast):
        for item in self._data["items"]:
            node = NodeRef.fromData(item["node"]).resolve(mapping)
            if node is not None:
                cmds.setAttr(node.getFullName() + ".tx", item["value"])
        if options["fail"]:
            raise RuntimeError("fail on purpose")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
