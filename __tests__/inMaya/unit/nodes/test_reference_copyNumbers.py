"""同じファイルのコピー番号と追加アトリビュートの由来を検証する。"""

import sys
import tempfile
import unittest
from pathlib import Path

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class ReferenceCopyNumbersTest(NamespaceCase):
    def test_multiple_copies_and_referenced_attribute_origin(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = str(Path(directory) / "reference.ma")
            source = cmds.createNode("transform", name=self.ns + ":source")
            cmds.addAttr(source, longName="authored", attributeType="double")
            cmds.select(source, replace=True)
            cmds.file(filename, force=True, exportSelected=True, type="mayaAscii")
            cmds.delete(source)
            references = []
            try:
                for index in range(3):
                    namespace = self.ns + "copy" + str(index)
                    self.extra_namespaces.append(namespace)
                    new_nodes = cmds.file(filename, reference=True, namespace=namespace, returnNewNodes=True)
                    reference = cmds.referenceQuery(new_nodes[0], referenceNode=True)
                    references.append(reference)
                wrapped = mlib.getNode(references[0])
                self.assertEqual(wrapped.getCopyNumbers(), [0, 1, 2])
                source = next(node for node in wrapped.getNodes() if node.hasAttr("authored"))
                self.assertFalse(source.getPlug("authored").isNewAttribute())
                added = source.addAttr("addedLocally", attributeType="double")
                self.assertTrue(added.isNewAttribute())
                cmds.file(removeReference=True, referenceNode=references[1])
                self.assertEqual(wrapped.getCopyNumbers(), [0, 2])
            finally:
                for reference in references:
                    if cmds.objExists(reference):
                        cmds.file(removeReference=True, referenceNode=reference)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
