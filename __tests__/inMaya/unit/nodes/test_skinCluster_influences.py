"""ゼロウェイト追加・ノード色の設定とUndo/Redoを実Mayaで確認する。

あわせて次も確かめる。

- 共通メソッドのMaya結果・単位・Undo/Redoを検証する。
"""

import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()


class CommonMethodsTest(unittest.TestCase):
    def setUp(self):
        self.namespace = "mlibCommon_" + uuid.uuid4().hex
        cmds.namespace(add=self.namespace)

    def tearDown(self):
        cmds.namespace(removeNamespace=self.namespace, deleteNamespaceContent=True)

    def create(self, name, type="transform", **kwargs):
        return mlib.createNode(type, name=self.namespace + ":" + name, **kwargs)

    def skin(self):
        joints = [self.create("joint" + str(i), type="joint") for i in range(3)]
        mesh = cmds.polyCube(name=self.namespace + ":mesh")[0]
        skin = mlib.getNode(cmds.skinCluster([j.getFullName() for j in joints], mesh)[0])
        return joints, mlib.getNode(mesh), skin

    def test_unused_influences_undo_and_joint_survival(self):
        joints, mesh, skin = self.skin()
        names = [joint.getFullName() for joint in joints]
        skin.setWeights(names, [1, 0, 0], broadcast=True)
        self.assertEqual([node.getUuid() for node in skin.getUnusedInfluences()], [j.getUuid() for j in joints[1:]])
        before = list(skin.getWeights(names))
        removed = skin.removeUnusedInfluences()
        self.assertEqual([node.getUuid() for node in removed], [j.getUuid() for j in joints[1:]])
        self.assertTrue(all(j.isValid() for j in joints))
        self.assertEqual(len(skin.getInfluences()), 1)
        cmds.undo()
        self.assertEqual(list(skin.getWeights(names)), before)
        cmds.redo()
        self.assertEqual(len(skin.getInfluences()), 1)
        self.assertEqual(skin.removeUnusedInfluences(), [])

    def test_unused_influences_keep_small_weights_and_reject_empty_binding(self):
        joints, mesh, skin = self.skin()
        names = [joint.getFullName() for joint in joints]
        skin.setWeights(names, [1 - 1e-8, 1e-8, 0], broadcast=True)
        self.assertEqual([node.getUuid() for node in skin.getUnusedInfluences()], [joints[2].getUuid()])
        skin.setWeights(names, [0, 0, 0], broadcast=True)
        with self.assertRaises(ValueError):
            skin.removeUnusedInfluences()
        self.assertEqual(len(skin.getInfluences()), 3)


class InfluencesColorsTest(unittest.TestCase):
    def setUp(self):
        self.ns = "mlibIC_" + uuid.uuid4().hex
        cmds.namespace(add=self.ns)

    def tearDown(self):
        cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)

    def getNode(self, kind):
        return mlib.createNode(kind, name=self.ns + ":" + kind)

    def test_add_zero_influences_and_undo(self):
        joints = [self.getNode("joint") for _ in range(4)]
        mesh = cmds.polyCube(name=self.ns + ":mesh")[0]
        name = cmds.skinCluster([j.getFullName() for j in joints[:2]], mesh, name=self.ns + ":skin")[0]
        skin = mlib.getNode(name)
        pose = skin.getBindPose()
        if pose:
            cmds.rename(pose.getFullName(), self.ns + ":pose")
        vertices = cmds.ls(mesh + ".vtx[*]", flatten=True)
        for v in vertices:
            cmds.skinPercent(name, v, transformValue=[(joints[0].getFullName(), 0.25), (joints[1].getFullName(), 0.75)])
        # 合計1でない保存ウェイトも再正規化されないことを確認する。
        cmds.setAttr(name + ".normalizeWeights", 0)
        cmds.skinPercent(name, vertices[0], normalize=False, transformValue=[(joints[0].getFullName(), 0.2), (joints[1].getFullName(), 0.3)])
        joints[0].getPlug("lockInfluenceWeights").set(True)
        for normalization in (0, 1, 2):
            for obey in (False, True):
                with self.subTest(normalization=normalization, obey=obey):
                    cmds.setAttr(name + ".normalizeWeights", normalization)
                    cmds.setAttr(name + ".maintainMaxInfluences", obey)
                    cmds.setAttr(name + ".maxInfluences", 2)
                    before = [[cmds.skinPercent(name, v, query=True, transform=j.getFullName()) for j in joints[:2]] for v in vertices]
                    indices = [skin.mfn().indexForInfluenceObject(j.mpath()) for j in joints[:2]]
                    raw = [[cmds.getAttr(f"{name}.weightList[{v}].weights[{i}]") for i in indices] for v in range(len(vertices))]
                    skin.addInfluences([joints[2], joints[3], joints[2], joints[0]])
                    for i, v in enumerate(vertices):
                        after = [cmds.skinPercent(name, v, query=True, transform=j.getFullName()) for j in joints]
                        self.assertEqual(after[:2], before[i])
                        self.assertEqual(after[2:], [0, 0])
                        self.assertEqual([cmds.getAttr(f"{name}.weightList[{i}].weights[{k}]") for k in indices], raw[i])
                    self.assertTrue(joints[0].getPlug("lockInfluenceWeights").get())
                    cmds.undo()
                    self.assertEqual(len(skin.getInfluences()), 2)
                    cmds.redo()
                    self.assertEqual(len(skin.getInfluences()), 4)
                    cmds.undo()
        other = self.getNode("transform")
        with self.assertRaises(ValueError):
            skin.addInfluences([joints[2], other])
        self.assertEqual(len(skin.getInfluences()), 2)
        skin.addInfluences([])
        skin.addInfluences(joints[0])
        self.assertEqual(len(skin.getInfluences()), 2)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
