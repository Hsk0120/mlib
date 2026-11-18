"""ウェイト転送の対応条件・自動バインド前検査・Undoを検証する。"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class SkinClusterCopyOptionsTest(NamespaceCase):
    CLEAR_SELECTION = True

    def setUp(self):
        super().setUp()
        cmds.currentUnit(linear="cm")
        self.joints = [self.make("joint", "joint#") for _ in range(2)]
        cmds.setAttr(self.joints[0] + ".tx", -1)
        cmds.setAttr(self.joints[1] + ".tx", 1)
        self.source = self._plane()
        self.source_skin = self._bind(self.source, self.joints)
        self.expected = [1, 0, 0, 1, 1, 0, 0, 1]
        self.source_skin.setWeights(self.joints, self.expected)

    def test_uv_transfer_ignores_separation_and_preserves_current_sets(self):
        target = self._plane(100)
        skin = self._bind(target, self.joints)
        for shape in (self.source, target):
            cmds.polyUVSet(shape, copy=True, uvSet="map1", newUVSet="transfer")
            cmds.polyUVSet(shape, currentUVSet=True, uvSet="map1")
        before = skin.getWeights(self.joints)
        self.flushUndo()
        result = self.source_skin.copyWeightsTo(skin, uvSpace=("transfer", "transfer"), influenceAssociation="oneToOne")
        self.assertEqual(result, skin)
        self.assertSequenceAlmostEqual(skin.getWeights(self.joints), self.expected)
        for shape in (self.source, target):
            self.assertEqual(cmds.polyUVSet(shape, query=True, currentUVSet=True), ["map1"])
        after = skin.getWeights(self.joints)
        cmds.undo()
        self.assertSequenceAlmostEqual(skin.getWeights(self.joints), before)
        self.assertUndoEmpty()
        cmds.redo()
        self.assertSequenceAlmostEqual(skin.getWeights(self.joints), after)

    def test_autobind_uv_and_single_undo(self):
        target = self._plane(100)
        self.flushUndo()
        skin = self.source_skin.copyWeightsTo(target, uvSpace=("map1", "map1"))
        self.assertSequenceAlmostEqual(skin.getWeights(self.joints), self.expected)
        cmds.undo()
        self.assertEqual(len(mlib.getNode(target).getSkinClusters()), 0)
        self.assertUndoEmpty()
        cmds.redo()
        skin = mlib.getNode(target).getSkinClusters()[0]
        self.assertSequenceAlmostEqual(skin.getWeights(self.joints), self.expected)

    def test_model_space_and_label_association(self):
        target = self._plane()
        joints = [self.make("joint", "other#") for _ in range(2)]
        for index, (source, destination) in enumerate(zip(self.joints, reversed(joints))):
            for joint in (source, destination):
                cmds.setAttr(joint + ".type", 18)
                cmds.setAttr(joint + ".otherType", "label" + str(index), type="string")
        skin = self._bind(target, joints)
        self.source_skin.copyWeightsTo(skin, surfaceAssociation="closestComponent", sampleSpace=1, influenceAssociation="label")
        self.assertSequenceAlmostEqual(skin.getWeights(list(reversed(joints))), self.expected)

    def test_missing_and_unassigned_uv_rejected_before_autobind(self):
        target = self._plane()
        for uv_space in (("missing", "map1"), ("map1", "missing")):
            self.flushUndo()
            with self.assertRaises(ValueError):
                self.source_skin.copyWeightsTo(target, uvSpace=uv_space)
            self.assertEqual(len(mlib.getNode(target).getSkinClusters()), 0)
            self.assertUndoEmpty()
        shape = mlib.getNode(target).getShape()
        om2.MFnMesh(shape.mpath()).clearUVs("map1")
        self.flushUndo()
        with self.assertRaisesRegex(ValueError, "割り当て"):
            self.source_skin.copyWeightsTo(target, uvSpace=("map1", "map1"))
        self.assertEqual(len(mlib.getNode(target).getSkinClusters()), 0)
        self.assertUndoEmpty()

    def test_invalid_options_rejected_before_autobind(self):
        target = self._plane()
        cases = (
            ({"surfaceAssociation": "bad"}, ValueError),
            ({"influenceAssociation": []}, ValueError),
            ({"influenceAssociation": ["name", "name"]}, ValueError),
            ({"influenceAssociation": [1]}, TypeError),
            ({"uvSpace": "map1"}, TypeError),
            ({"uvSpace": ("map1",)}, ValueError),
            ({"uvSpace": ("", "map1")}, ValueError),
            ({"sampleSpace": True}, TypeError),
            ({"sampleSpace": 2}, ValueError),
            ({"normalize": 1}, TypeError),
        )
        self.flushUndo()
        for flags, error in cases:
            with self.subTest(flags=flags), self.assertRaises(error):
                self.source_skin.copyWeightsTo(target, **flags)
        self.assertEqual(len(mlib.getNode(target).getSkinClusters()), 0)
        self.assertUndoEmpty()

    def test_blend_weights_and_locked_influence_match_native_command(self):
        skin = self._bind(self._plane(), self.joints)
        reference = self._bind(self._plane(), self.joints)
        for cluster in (self.source_skin, skin, reference):
            cmds.setAttr(cluster.getFullName() + ".skinningMethod", 2)
        self.source_skin.setBlendWeights([0, 0.25, 0.75, 1])
        cmds.setAttr(self.joints[0] + ".liw", True)
        self.source_skin.copyWeightsTo(skin, influenceAssociation="oneToOne", normalize=False)
        cmds.copySkinWeights(
            sourceSkin=self.source_skin.getFullName(),
            destinationSkin=reference.getFullName(),
            noMirror=True,
            surfaceAssociation="closestPoint",
            influenceAssociation="oneToOne",
            sampleSpace=0,
            normalize=False,
        )
        self.assertSequenceAlmostEqual(skin.getWeights(self.joints), reference.getWeights(self.joints))
        self.assertSequenceAlmostEqual(skin.getBlendWeights(), reference.getBlendWeights())
        self.assertSequenceAlmostEqual(skin.getBlendWeights(), [0, 0.25, 0.75, 1])

    def test_native_lock_behavior_does_not_unlock_targets(self):
        for lock in ("skin", "shape", "weights", "influence"):
            with self.subTest(lock=lock):
                target = self._plane()
                skin = self._bind(target, self.joints)
                shape = mlib.getNode(target).getShape()
                if lock == "skin":
                    cmds.lockNode(skin.getFullName(), lock=True)
                elif lock == "shape":
                    cmds.lockNode(shape.getFullName(), lock=True)
                elif lock == "weights":
                    cmds.setAttr(skin.getFullName() + ".weightList", lock=True)
                else:
                    cmds.setAttr(self.joints[0] + ".liw", True)
                try:
                    before = skin.getWeights(self.joints)
                    self.flushUndo()
                    if lock == "weights" and 20230000 <= om2.MGlobal.apiVersion() < 20240000:
                        with self.assertRaisesRegex(RuntimeError, "Undo"):
                            self.source_skin.copyWeightsTo(skin)
                        self.assertSequenceAlmostEqual(skin.getWeights(self.joints), before)
                        self.assertUndoEmpty()
                        continue
                    self.source_skin.copyWeightsTo(skin)
                    self.assertSequenceAlmostEqual(skin.getWeights(self.joints), self.expected)
                    if lock == "skin":
                        self.assertTrue(cmds.lockNode(skin.getFullName(), query=True, lock=True)[0])
                    elif lock == "shape":
                        self.assertTrue(cmds.lockNode(shape.getFullName(), query=True, lock=True)[0])
                    elif lock == "weights":
                        self.assertTrue(cmds.getAttr(skin.getFullName() + ".weightList", lock=True))
                    else:
                        self.assertTrue(cmds.getAttr(self.joints[0] + ".liw"))
                    cmds.undo()
                    self.assertSequenceAlmostEqual(skin.getWeights(self.joints), before)
                    self.assertUndoEmpty()
                finally:
                    cmds.lockNode(skin.getFullName(), lock=False)
                    cmds.lockNode(shape.getFullName(), lock=False)
                    cmds.setAttr(skin.getFullName() + ".weightList", lock=False)
                    cmds.setAttr(self.joints[0] + ".liw", False)

    def test_locked_weight_descendants_reject_only_unsupported_undo_version(self):
        for attribute in ("weightList[0]", "weightList[0].weights", "weightList[0].weights[0]"):
            with self.subTest(attribute=attribute):
                skin = self._bind(self._plane(), self.joints)
                before = skin.getWeights(self.joints)
                cmds.setAttr(skin.getFullName() + "." + attribute, lock=True)
                self.flushUndo()
                if 20230000 <= om2.MGlobal.apiVersion() < 20240000:
                    with self.assertRaisesRegex(RuntimeError, "Undo"):
                        self.source_skin.copyWeightsTo(skin)
                else:
                    self.source_skin.copyWeightsTo(skin)
                    self.assertSequenceAlmostEqual(skin.getWeights(self.joints), self.expected)
                    cmds.undo()
                self.assertSequenceAlmostEqual(skin.getWeights(self.joints), before)
                self.assertUndoEmpty()

    def test_surface_associations_and_spaces_match_native(self):
        for surface in ("closestPoint", "closestComponent", "rayCast"):
            for space in (0, 1):
                with self.subTest(surface=surface, space=space):
                    skin = self._bind(self._plane(100), self.joints)
                    reference = self._bind(self._plane(100), self.joints)
                    self.source_skin.copyWeightsTo(skin, surfaceAssociation=surface, sampleSpace=space)
                    cmds.copySkinWeights(
                        sourceSkin=self.source_skin.getFullName(),
                        destinationSkin=reference.getFullName(),
                        noMirror=True,
                        surfaceAssociation=surface,
                        influenceAssociation=["name", "closestJoint"],
                        sampleSpace=space,
                        normalize=True,
                    )
                    self.assertSequenceAlmostEqual(skin.getWeights(self.joints), reference.getWeights(self.joints))

    def test_overlapping_uv_matches_native_without_inventing_correspondence(self):
        shapes = []
        for _ in range(3):
            name = cmds.polyPlane(name=self.name("overlap#"), subdivisionsX=2, subdivisionsY=1, constructionHistory=False)[0]
            shape = mlib.getNode(name).getShape()
            fn = om2.MFnMesh(shape.mpath())
            fn.clearUVs("map1")
            fn.setUVs([0, 1, 1, 0], [0, 0, 1, 1], "map1")
            fn.assignUVs([4, 4], [0, 1, 2, 3, 0, 1, 2, 3], "map1")
            shapes.append(self._bind(name, self.joints))
        source, destination, reference = shapes
        source.setWeights(self.joints, [[1, 0] if index < 3 else [0, 1] for index in range(6)], rows=True)
        source.copyWeightsTo(destination, uvSpace=("map1", "map1"))
        cmds.copySkinWeights(
            sourceSkin=source.getFullName(),
            destinationSkin=reference.getFullName(),
            noMirror=True,
            uvSpace=("map1", "map1"),
            surfaceAssociation="closestPoint",
            influenceAssociation=["name", "closestJoint"],
            sampleSpace=0,
            normalize=True,
        )
        self.assertSequenceAlmostEqual(destination.getWeights(self.joints), reference.getWeights(self.joints))

    def _plane(self, x=0):
        node = cmds.polyPlane(name=self.name("plane#"), subdivisionsX=1, subdivisionsY=1, width=2, height=2, constructionHistory=False)[0]
        cmds.setAttr(node + ".tx", x)
        return node

    def _bind(self, mesh, joints):
        skin = mlib.getNode(cmds.skinCluster(joints, mesh, toSelectedBones=True, name=self.name("skin#"))[0])
        skin.setWeights(joints, [0.5, 0.5], broadcast=True)
        return skin


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
