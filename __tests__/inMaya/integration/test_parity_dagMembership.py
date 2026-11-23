"""DAGパス別の所属とインスタンス属性を検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class DagMembershipTest(NamespaceCase):
    def test_surface_shader_assignments(self):
        root = cmds.nurbsPlane(name=self.name("surface"), constructionHistory=False)[0]
        shape = mlib.getNode(root).getShape()
        shaders, indices = shape.getPatchShaders()
        objects, native = shape.mfn().getConnectedShaders(shape.mpath().instanceNumber())
        self.assertEqual(indices, list(native))
        self.assertEqual([s.mnode() for s in shaders], list(objects))
        self.assertEqual(len(indices), shape.mfn().numPatches)

    def test_set_paths_and_version_limit(self):
        root = cmds.polyCube(name=self.name("cube"))[0]
        set_node = mlib.getNode(cmds.sets(root + ".f[0:2]", name=self.name("set")))
        if not hasattr(om2.MFnSet, "getMemberPaths"):
            with self.assertRaises(NotImplementedError):
                set_node.getMembers(dagOnly=True)
            return
        for shading in (False, True):
            result = set_node.getMembers(dagOnly=True, shadingOnly=shading)
            native = om2.MFnSet(set_node.mnode()).getMemberPaths(shading)
            self.assertEqual([n.getFullName() for n in result], [p.fullPathName() for p in native])

    def test_instanced_attribute_definition(self):
        node = mlib.createNode("transform", name=self.name("node"))
        for attr in ("worldMatrix", "translateX", "matrix"):
            plug = node.getPlug(attr)
            self.assertEqual(plug.isInstancedAttribute(), om2.MFnDagNode(node.mnode()).isInstancedAttribute(plug.mplug().attribute()))
        dependency = mlib.createNode("network", name=self.name("dg"))
        self.assertFalse(dependency.getPlug("message").isInstancedAttribute())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
