"""Editの種類と保存元referenceノードによる絞り込みを検証する。"""

import sys
import tempfile
import unittest
from pathlib import Path

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class ReferenceEditFiltersTest(NamespaceCase):
    def test_filters_match_native_for_loaded_and_unloaded_reference(self):
        node = self.make(text="source")
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "source.ma")
            cmds.select(node, replace=True)
            cmds.file(path, exportSelected=True, force=True, type="mayaAscii")
            cmds.file(path, reference=True, namespace=self.ns + "Ref")
            ref_name = cmds.file(path, query=True, referenceNode=True)
            reference = mlib.getNode(ref_name)
            try:
                referenced = next(n for n in cmds.referenceQuery(ref_name, nodes=True) if cmds.nodeType(n) == "transform")
                cmds.setAttr(referenced + ".tx", 4)
                cmds.addAttr(referenced, longName="extra", attributeType="double")
                cmds.setAttr(referenced + ".extra", 3)
                methods = ((reference.getEditStrings, "editStrings"), (reference.getEditNodeNames, "editNodes"), (reference.getEditAttrNames, "editAttrs"))
                for loaded in (True, False):
                    if not loaded:
                        cmds.file(unloadReference=ref_name)
                    self.flushUndo()
                    for method, flag in methods:
                        for command in (None, "setAttr", "addAttr", "connectAttr"):
                            for source in (None, reference, ref_name):
                                native_flags = {flag: True, "successfulEdits": True, "failedEdits": False}
                                if command is not None:
                                    native_flags["editCommand"] = command
                                if source is not None:
                                    native_flags["onReferenceNode"] = ref_name
                                expected = cmds.referenceQuery(ref_name, **native_flags) or []
                                self.assertEqual(method(editCommand=command, onReferenceNode=source), expected)
                        with self.assertRaises(ValueError):
                            method(editCommand="invalid")
                        with self.assertRaises(TypeError):
                            method(editCommand=["setAttr"])
                        with self.assertRaises(TypeError):
                            method(onReferenceNode=mlib.getNode(node))
                    self.assertUndoEmpty()
            finally:
                cmds.file(removeReference=True, referenceNode=ref_name)

    def test_nested_stored_edits_keep_original_names(self):
        with tempfile.TemporaryDirectory() as directory:
            leaf = Path(directory) / "leaf.ma"
            middle = Path(directory) / "middle.ma"
            leaf.write_text('//Maya ASCII 2022 scene\nrequires maya "2022";\ncreateNode transform -n "leaf";\n', encoding="utf-8")
            middle.write_text(
                "//Maya ASCII 2022 scene\n"
                'file -rdi 1 -ns "child" -rfn "childRN" -typ "mayaAscii" "' + leaf.as_posix() + '";\n'
                'file -r -dr 1 -ns "child" -rfn "childRN" -typ "mayaAscii" "' + leaf.as_posix() + '";\n'
                'requires maya "2022";\ncreateNode reference -n "childRN";\n'
                'setAttr ".ed" -type "dataReferenceEdits" "childRN" "childRN" 0 "childRN" 1\n'
                '2 "|child:leaf" "translate" " -type \\"double3\\" 2 0 0";\nlockNode -l 1;\n',
                encoding="utf-8",
            )
            cmds.file(str(middle), reference=True, namespace=self.ns + "Outer")
            top_name = cmds.file(str(middle), query=True, referenceNode=True)
            try:
                top = mlib.getNode(top_name)
                child = top.getChildren()[0]
                target = next(n for n in cmds.referenceQuery(child.getName(), nodes=True) if cmds.nodeType(n) == "transform")
                cmds.setAttr(target + ".ty", 5)
                for owner in (top, child):
                    expected = (
                        cmds.referenceQuery(
                            child.getName(), editStrings=True, successfulEdits=True, failedEdits=False, editCommand="setAttr", onReferenceNode=owner.getName()
                        )
                        or []
                    )
                    self.assertTrue(expected)
                    self.assertEqual(child.getEditStrings(editCommand="setAttr", onReferenceNode=owner), expected)
                inner = child.getEditStrings(editCommand="setAttr", onReferenceNode=child)
                outer = child.getEditStrings(editCommand="setAttr", onReferenceNode=top)
                self.assertNotEqual(inner, outer)
            finally:
                cmds.file(removeReference=True, referenceNode=top_name)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
