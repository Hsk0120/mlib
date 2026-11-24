"""形状とTransformからのスキニング関係照会を実Mayaで検証する。"""

import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()


class GeometrySkinQueriesTest(unittest.TestCase):
    def setUp(self):
        self.ns = "geometrySkin_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)
        self.joint = cmds.createNode("joint", name=self.ns + ":joint")

    def tearDown(self):
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def bind(self, geometry):
        skin = mlib.getNode(cmds.skinCluster(self.joint, geometry, toSelectedBones=True, name=self.ns + ":skin")[0])
        pose = skin.getBindPose()
        if not pose.getName(full=True).startswith(self.ns + ":"):
            cmds.rename(pose.getName(full=True), self.ns + ":pose")
        return skin

    def cube(self):
        return mlib.getNode(cmds.polyCube(name=self.ns + ":mesh")[0])

    def test_mesh_curve_surface_and_no_undo_entry(self):
        geometries = [
            self.cube(),
            mlib.getNode(cmds.curve(name=self.ns + ":curve", degree=1, point=[(0, 0, 0), (0, 1, 0), (1, 2, 0)])),
            mlib.getNode(cmds.nurbsPlane(name=self.ns + ":surface")[0]),
        ]
        for geometry in geometries:
            with self.subTest(geometry=geometry.getName(full=True)):
                self.assertEqual(geometry.getSkinClusters(), [])
                self.assertEqual(geometry.getBindPoses(), [])
                skin = self.bind(geometry.getName(full=True))
                shape = geometry.getShape()
                undo_name = cmds.undoInfo(query=True, undoName=True)
                selected = cmds.ls(selection=True, long=True)
                self.assertEqual(geometry.getSkinClusters(), [skin])
                self.assertEqual(shape.getSkinClusters(), [skin])
                self.assertEqual(shape.getBindPoses(), [skin.getBindPose()])
                self.assertEqual(geometry.getBindPoses(), [skin.getBindPose()])
                self.assertEqual(cmds.undoInfo(query=True, undoName=True), undo_name)
                self.assertEqual(cmds.ls(selection=True, long=True), selected)

    def test_multiple_shapes_shared_pose_and_missing_pose(self):
        first, second = self.cube(), self.cube()
        skin_a, skin_b = self.bind(first.getName(full=True)), self.bind(second.getName(full=True))
        shape_b = second.getShape()
        cmds.parent(shape_b.getName(full=True), first.getName(full=True), shape=True, relative=True)
        pose = skin_a.getBindPose()
        if skin_b.getBindPose() != pose:
            cmds.connectAttr(pose.getName(full=True) + ".message", skin_b.getName(full=True) + ".bindPose", force=True)
        self.assertEqual(first.getSkinClusters(), [skin_a, skin_b])
        self.assertEqual(first.getBindPoses(), [pose])
        for skin in (skin_a, skin_b):
            cmds.disconnectAttr(pose.getName(full=True) + ".message", skin.getName(full=True) + ".bindPose")
        self.assertEqual(first.getBindPoses(), [])
        self.assertEqual(second.getSkinClusters(), [])

    def test_excludes_blendshape_target_history(self):
        base, target = self.cube(), self.cube()
        base_skin, target_skin = self.bind(base.getName(full=True)), self.bind(target.getName(full=True))
        cmds.blendShape(target.getName(full=True), base.getName(full=True), name=self.ns + ":blend", after=True)
        self.assertIn(target_skin, base.getHistory(type="skinCluster"))
        self.assertEqual(base.getSkinClusters(), [base_skin])
        self.assertEqual(base.getBindPoses(), [base_skin.getBindPose()])

    def test_non_geometry_and_direct_children_only(self):
        group = mlib.getNode(cmds.createNode("transform", name=self.ns + ":group"))
        geometry = self.cube()
        self.bind(geometry.getName(full=True))
        cmds.parent(geometry.getName(full=True), group.getName(full=True))
        self.assertEqual(group.getSkinClusters(), [])
        self.assertEqual(group.getBindPoses(), [])
        camera = mlib.getNode(cmds.camera(name=self.ns + ":camera")[0])
        self.assertEqual(camera.getSkinClusters(), [])
        self.assertEqual(camera.getShape().getBindPoses(), [])

    def test_multiple_skin_deformers_in_chain(self):
        geometry = self.cube()
        first = self.bind(geometry.getName(full=True))
        # バージョン固有の複数バインドフラグに依存せず、標準deformerで直列接続。
        second = mlib.getNode(cmds.deformer(geometry.getName(full=True), type="skinCluster", name=self.ns + ":secondSkin")[0])
        self.assertEqual(geometry.getSkinClusters(), [second, first])
        self.assertEqual(geometry.getBindPoses(), [first.getBindPose()])

    def test_intermediates_instances_and_joint_compatibility(self):
        geometry = self.cube()
        skin = self.bind(geometry.getName(full=True))
        original = next(s for s in geometry.getShape(intermediates=True, all=True) if cmds.getAttr(s.getName(full=True) + ".intermediateObject"))
        self.assertEqual(original.getSkinClusters(), [])
        instance = mlib.getNode(cmds.instance(geometry.getName(full=True), name=self.ns + ":instance")[0])
        self.assertEqual(instance.getSkinClusters(), [skin])
        self.assertEqual(instance.getShape().getSkinClusters(), [skin])
        self.assertEqual(mlib.getNode(self.joint).getSkinClusters(), [skin])
        self.assertEqual(mlib.getNode(self.joint).getBindPoses(), [skin.getBindPose()])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
