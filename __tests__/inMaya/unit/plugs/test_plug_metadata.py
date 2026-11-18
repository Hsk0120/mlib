"""追加アトリビュートの表示名とカテゴリの照会を検証する。"""

import sys
import tempfile
import unittest
from pathlib import Path

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class PlugMetadataTest(NamespaceCase):
    UNLOCK_NODES = True

    def make_extra(self, **flags):
        name = self.make()
        cmds.addAttr(name, longName="extraValue", attributeType="double", **flags)
        return mlib.getPlug(name + ".extraValue")

    def test_nice_name_undo_reset_and_connections(self):
        source, destination = self.make_extra(), self.make_extra()
        source.set(4)
        destination.connect(source)
        original_name = destination.getFullName()
        before = destination.getNiceName()
        self.flushUndo()
        self.assertIsNone(destination.setNiceName("Weight Display"))
        self.assertEqual(destination.getNiceName(), "Weight Display")
        self.assertEqual(destination.getFullName(), original_name)
        self.assertEqual(destination.get(), 4)
        self.assertEqual(destination.getSource(), source)
        cmds.undo()
        self.assertEqual(destination.getNiceName(), before)
        self.assertUndoEmpty()
        cmds.redo()
        self.assertEqual(destination.getNiceName(), "Weight Display")
        destination.setNiceName("")
        self.assertEqual(destination.getNiceName(), before)
        cmds.undo()
        self.assertEqual(destination.getNiceName(), "Weight Display")

    def test_categories_and_uncreated_elements(self):
        plug = self.make_extra(category=["rig", "export"], multi=True)
        element = plug[9]
        standard = mlib.getPlug(self.make() + ".tx")
        self.flushUndo()
        self.assertEqual(set(plug.getCategories()), {"rig", "export"})
        self.assertEqual(element.getCategories(), plug.getCategories())
        self.assertEqual(plug.getIndices(), [])
        self.assertEqual(standard.getCategories(), [])
        self.assertUndoEmpty()
        plug.setNiceName("Samples")
        self.assertEqual(element.getNiceName(), "Samples[9]")
        with self.assertRaises(TypeError):
            element.setNiceName("One Sample")

    def test_rejections_are_before_changes(self):
        plug = self.make_extra()
        before = plug.getNiceName()
        for value in (None, 1, False):
            with self.assertRaises(TypeError):
                plug.setNiceName(value)
        with self.assertRaises(ValueError):
            plug.setNiceName("invalid\x00name")
        plug.setLocked(True)
        with self.assertRaises(RuntimeError):
            plug.setNiceName("locked")
        plug.setLocked(False)
        node = plug.getFullName().split(".")[0]
        cmds.lockNode(node, lock=True)
        with self.assertRaises(RuntimeError):
            plug.setNiceName("locked")
        cmds.lockNode(node, lock=False)
        with self.assertRaises(TypeError):
            mlib.getPlug(node + ".tx").setNiceName("standard")
        self.assertEqual(plug.getNiceName(), before)
        cmds.delete(node)
        with self.assertRaises(RuntimeError):
            plug.getCategories()

    def test_compound_definition_children_and_proxy(self):
        node = self.make()
        cmds.addAttr(node, longName="group", attributeType="compound", numberOfChildren=1)
        cmds.addAttr(node, longName="childValue", attributeType="double", parent="group", category="nested")
        group, child = mlib.getPlug(node + ".group"), mlib.getPlug(node + ".childValue")
        group.setNiceName("Group Display")
        child.setNiceName("Child Display")
        self.assertEqual(group.getNiceName(), "Group Display")
        self.assertEqual(child.getNiceName(), "Child Display")
        self.assertEqual(child.getCategories(), ["nested"])
        cmds.addAttr(node, longName="array", attributeType="compound", numberOfChildren=1, multi=True)
        cmds.addAttr(node, longName="arrayChild", attributeType="double", parent="array")
        with self.assertRaises(TypeError):
            mlib.getPlug(node + ".array[3].arrayChild").setNiceName("Element Child")
        cmds.addAttr(node, longName="proxyValue", proxy=child.getFullName())
        with self.assertRaises(TypeError):
            mlib.getPlug(node + ".proxyValue").setNiceName("Proxy")

    def test_file_roundtrip_reference_and_plural(self):
        plug = self.make_extra(category="rig")
        other = self.make_extra()
        mlib.ls(plug.getFullName(), other.getFullName()).setNiceName("Display")
        self.assertEqual(other.getNiceName(), "Display")
        node = plug.getFullName().split(".")[0]
        with tempfile.TemporaryDirectory() as directory:
            for extension, file_type in (("ma", "mayaAscii"), ("mb", "mayaBinary")):
                path = str(Path(directory) / ("metadata." + extension))
                cmds.select(node, replace=True)
                cmds.file(path, force=True, exportSelected=True, type=file_type)
                namespace = self.ns + "Import" + extension
                self.extra_namespaces.append(namespace)
                imported = cmds.file(path, i=True, namespace=namespace, returnNewNodes=True)
                name = next(name for name in imported if cmds.attributeQuery("extraValue", node=name, exists=True))
                restored = mlib.getPlug(name + ".extraValue")
                self.assertEqual(restored.getNiceName(), "Display")
                self.assertIn("rig", restored.getCategories())
                cmds.file(path, reference=True, namespace=self.ns + "Ref" + extension)
                reference = cmds.file(path, query=True, referenceNode=True)
                try:
                    referenced = next(name for name in cmds.referenceQuery(reference, nodes=True) if cmds.attributeQuery("extraValue", node=name, exists=True))
                    with self.assertRaises(RuntimeError):
                        mlib.getPlug(referenced + ".extraValue").setNiceName("Forbidden")
                finally:
                    cmds.file(removeReference=True, referenceNode=reference)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
