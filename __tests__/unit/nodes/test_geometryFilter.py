"""``mlib.nodes.geometryFilter`` のテスト。

- デフォーマー・AnimCurve・ObjectSet のメソッドと作成関数を確かめる。
- NurbsSurface・Transform・Vector・コンポーネント等のメソッド・引数の名前を確かめる。
- リグ・スキン向けの API の契約を固定する。
- スキンのウェイト編集向けの照会・編集の契約を固定する。
"""

import json
import math
import os
import shutil
import sys
import tempfile
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.cmds.createJointChain import createJointChain
from mlib.common import Selection
from mlib.nodes import GeometryFilter, Joint, Mesh, SkinCluster
from support.namespaceCase import NamespaceCase


class _Case(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibDeformAdd_"

    def cube(self, subdivisionsY=1):
        """1辺2cm の polyCube を作り、(transform 名, shape 名) を返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, subdivisionsY=subdivisionsY,
                                  constructionHistory=False)[0]
        transform = cmds.ls(transform, long=True)[0]
        return transform, cmds.listRelatives(transform, shapes=True, fullPath=True)[0]

    def skinned(self):
        """2段の cube を2本の joint へバインドし、(skin, mesh 名, joints, 未登録 joint) を返す。"""
        mesh, _ = self.cube(subdivisionsY=2)
        cmds.select(clear=True)
        j0 = cmds.joint(name=self.name("j0"), position=(0, -1, 0))
        j1 = cmds.joint(name=self.name("j1"), position=(0, 1, 0))
        cmds.select(clear=True)
        stranger = cmds.joint(name=self.name("stranger"))
        cmds.select(clear=True)
        name = cmds.skinCluster(j0, j1, mesh, toSelectedBones=True, name=self.name("skin"))[0]
        cmds.select(clear=True)
        return mlib.getNode(name), mesh, (j0, j1), stranger

    def keyed(self):
        """translateX の frame 1 に 0、frame 10 に 5 のキーを打ったカーブを返す。"""
        node = self.make("transform", "keyed#")
        cmds.setKeyframe(node, attribute="translateX", time=1, value=0.0)
        cmds.setKeyframe(node, attribute="translateX", time=10, value=5.0)
        return mlib.getNode(cmds.listConnections(node + ".tx", type="animCurve")[0])


class GeometryFilterTest(_Case):
    """GeometryFilter.getInputGeometry。"""

    def test_input_geometry_is_orig_shape(self):
        """skinCluster・cluster の入力は同じ transform の下の中間形状で、出力の形状とは別。"""
        skin, mesh, _, _ = self.skinned()
        cluster = mlib.createCluster(mesh)
        for deformer in (skin, cluster):
            with self.subTest(deformer=deformer.getType()):
                inputs = deformer.getInputGeometry()
                self.assertEqual(len(inputs), 1)
                self.assertTrue(cmds.getAttr(inputs[0].getFullName() + ".intermediateObject"))
                self.assertEqual(cmds.listRelatives(inputs[0].getFullName(), parent=True, fullPath=True)[0], mesh)
                self.assertNotEqual(inputs[0], deformer.getGeometry()[0])

    def test_deleted_raises(self):
        """削除済みのデフォーマーは RuntimeError。"""
        transform, _ = self.cube()
        cluster = mlib.createCluster(transform)
        cmds.delete(cluster.getFullName())
        with self.assertRaises(RuntimeError):
            cluster.getInputGeometry()


class _CaseMethodAdditions(NamespaceCase):
    """形状を作る補助。"""

    PREFIX = "mlibMethodAdd_"

    def surface(self):
        """2x3 スパン・3次の NURBS 平面を作り、シェイプのラッパーを返す。"""
        transform = cmds.nurbsPlane(name=self.name("plane#"), width=4, lengthRatio=1.5, patchesU=2, patchesV=3,
                                    degree=3, axis=(0, 1, 0), constructionHistory=False)[0]
        cmds.setAttr(transform + ".translate", 1, 2, 3)
        return mlib.getNode(cmds.listRelatives(transform, shapes=True, fullPath=True)[0])

    def cube(self):
        """1辺2cm の polyCube を作り、(transform, shape) のラッパーを返す。"""
        transform = cmds.polyCube(name=self.name("cube#"), width=2, height=2, depth=2, constructionHistory=False)[0]
        shape = cmds.listRelatives(transform, shapes=True, fullPath=True)[0]
        return mlib.getNode(transform), mlib.getNode(shape)


class GeometryFilterGeometryTest(_CaseMethodAdditions):
    """GeometryFilter.getGeometry はすべてのデフォーマーで変形する形状を返す。"""

    def test_get_geometry(self):
        """skinCluster・cluster・deltaMush の getGeometry が変形する形状(deformer -q -g)と一致する。"""
        transform, shape = self.cube()
        cmds.select(clear=True)
        joint = cmds.joint(name=self.name("jnt#"))
        skin = mlib.getNode(cmds.skinCluster(joint, transform.getFullName(), name=self.name("skin#"))[0])
        cluster = mlib.getNode(cmds.cluster(transform.getFullName(), name=self.name("cluster#"))[0])
        mush = mlib.getNode(cmds.deltaMush(transform.getFullName(), name=self.name("mush#"))[0])
        expected = cmds.ls(cmds.deformer(skin.getFullName(), query=True, geometry=True), long=True)
        for deformer in (skin, cluster, mush):
            with self.subTest(deformer=deformer.getType()):
                self.assertIsInstance(deformer, mlib.GeometryFilter)
                self.assertEqual([node.getFullName() for node in deformer.getGeometry()], expected)
        for name in cmds.ls(type="dagPose") or []:
            if not cmds.listConnections(name + ".members"):
                cmds.delete(name)


def _distance(first, second):
    """2点の距離(Python 3.7 には math.dist が無いため)。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def _world_points(name):
    selection = om2.MSelectionList()
    selection.add(name)
    path = selection.getDagPath(0)
    path.extendToShape()
    return [(p.x, p.y, p.z) for p in om2.MFnMesh(path).getPoints(om2.MSpace.kObject)]


class _RigCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, offset=(0, 0, 0)):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        cmds.move(offset[0], offset[1], offset[2], self.mesh)
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True, maximumInfluences=3)[0])
        cmds.select(clear=True)
        return self.skin


class DeformerWeightsFileTest(_RigCase):

    def setUp(self):
        super().setUp()
        self.directory = tempfile.mkdtemp(prefix="mlibRig")
        self.path = os.path.join(self.directory, "deformer.json")

    def tearDown(self):
        shutil.rmtree(self.directory, ignore_errors=True)
        super().tearDown()

    def two_cubes(self):
        first = cmds.polyCube(name=self.name("a"))[0]
        second = cmds.polyCube(name=self.name("b"))[0]
        cluster = mlib.getNode(cmds.cluster(first, second, name=self.name("cl"))[0])
        return cluster

    def test_roundtrip_all_geometries(self):
        """全形状を書き、読み込むと同じ値に戻る。通常は Undo 1回。"""
        cluster = self.two_cubes()
        cluster.setDeformerWeights([0.1 * i for i in range(8)], geometryIndex=0)
        cluster.setDeformerWeights([0.5] * 8, geometryIndex=1)
        expected = [cluster.getDeformerWeights(geometryIndex=i) for i in (0, 1)]
        cluster.dumpDeformerWeights(self.path)
        with open(self.path, encoding="utf-8") as file:
            payload = json.load(file)
        self.assertEqual(payload["version"], 1)
        self.assertEqual([g["index"] for g in payload["geometries"]], [0, 1])
        self.assertEqual([g["numVertices"] for g in payload["geometries"]], [8, 8])
        cluster.setDeformerWeights([1.0] * 8, geometryIndex=0)
        cluster.setDeformerWeights([1.0] * 8, geometryIndex=1)
        self.flushUndo()
        self.assertIsNone(cluster.loadDeformerWeights(self.path))
        for index in (0, 1):
            self.assertSequenceAlmostEqual(cluster.getDeformerWeights(geometryIndex=index), expected[index], places=6)
        cmds.undo()
        for index in (0, 1):
            self.assertEqual(cluster.getDeformerWeights(geometryIndex=index), [1.0] * 8)
        self.assertUndoEmpty()

    def test_single_geometry_and_fast(self):
        """geometryIndex を指定すると1つだけ書く。fast は Undo に積まない。"""
        cluster = self.two_cubes()
        cluster.setDeformerWeights([0.25] * 8, geometryIndex=1)
        cluster.dumpDeformerWeights(self.path, geometryIndex=1)
        with open(self.path, encoding="utf-8") as file:
            self.assertEqual([g["index"] for g in json.load(file)["geometries"]], [1])
        cluster.setDeformerWeights([1.0] * 8, geometryIndex=1)
        self.flushUndo()
        cluster.loadDeformerWeights(self.path, fast=True)
        self.assertSequenceAlmostEqual(cluster.getDeformerWeights(geometryIndex=1), [0.25] * 8, places=6)
        self.assertUndoEmpty()

    def test_load_mismatch(self):
        """番号の無い形状・頂点数の違い・版の違いは ValueError で、何も変えない。"""
        cluster = self.two_cubes()
        cluster.dumpDeformerWeights(self.path)
        sphere = cmds.polySphere(name=self.name("sphere"))[0]
        single = mlib.getNode(cmds.cluster(sphere, name=self.name("cl2"))[0])
        self.assertRaises(ValueError, single.loadDeformerWeights, self.path)
        cube = cmds.polyCube(name=self.name("c"))[0]
        other = mlib.getNode(cmds.cluster(cube, name=self.name("cl3"))[0])
        self.assertRaises(ValueError, other.loadDeformerWeights, self.path)
        self.assertEqual(other.getDeformerWeights(), [1.0] * 8)
        with open(self.path, "w", encoding="utf-8") as file:
            json.dump({"version": 99, "geometries": []}, file)
        self.assertRaises(ValueError, cluster.loadDeformerWeights, self.path)
        self.assertRaises(TypeError, cluster.loadDeformerWeights, self.path, fast=1)

    def test_skin_cluster_rejected(self):
        skin = self.skinned()
        cluster = self.two_cubes()
        self.assertRaises(TypeError, skin.dumpDeformerWeights, self.path)
        self.assertRaises(TypeError, skin.loadDeformerWeights, self.path)
        self.assertRaises(TypeError, skin.copyDeformerWeightsTo, cluster)
        self.assertRaises(TypeError, cluster.copyDeformerWeightsTo, skin)
        self.assertRaises(IndexError, cluster.dumpDeformerWeights, self.path, geometryIndex=5)


class CopyDeformerWeightsTest(_RigCase):

    def test_copy_and_undo(self):
        first = cmds.polyCube(name=self.name("a"))[0]
        second = cmds.polyCube(name=self.name("b"))[0]
        source = mlib.getNode(cmds.cluster(first, name=self.name("src"))[0])
        target = mlib.getNode(cmds.cluster(second, name=self.name("dst"))[0])
        values = [0.1 * i for i in range(8)]
        source.setDeformerWeights(values)
        self.flushUndo()
        result = source.copyDeformerWeightsTo(target.getName())
        self.assertEqual(result.getUuid(), target.getUuid())
        self.assertSequenceAlmostEqual(target.getDeformerWeights(), values, places=6)
        cmds.undo()
        self.assertEqual(target.getDeformerWeights(), [1.0] * 8)
        self.assertUndoEmpty()
        target.setDeformerWeights([1.0] * 8)
        self.flushUndo()
        source.copyDeformerWeightsTo(target, fast=True)
        self.assertSequenceAlmostEqual(target.getDeformerWeights(), values, places=6)
        self.assertUndoEmpty()

    def test_other_geometry_and_errors(self):
        first = cmds.polyCube(name=self.name("a"))[0]
        second = cmds.polyCube(name=self.name("b"))[0]
        sphere = cmds.polySphere(name=self.name("s"))[0]
        cluster = mlib.getNode(cmds.cluster(first, second, name=self.name("cl"))[0])
        cluster.setDeformerWeights([0.3] * 8, geometryIndex=0)
        cluster.copyDeformerWeightsTo(cluster, geometryIndex=0, otherGeometryIndex=1)
        self.assertSequenceAlmostEqual(cluster.getDeformerWeights(geometryIndex=1), [0.3] * 8, places=6)
        other = mlib.getNode(cmds.cluster(sphere, name=self.name("cls"))[0])
        self.assertRaises(ValueError, cluster.copyDeformerWeightsTo, other)
        self.assertRaises(TypeError, cluster.copyDeformerWeightsTo, first)
        self.assertRaises(IndexError, cluster.copyDeformerWeightsTo, cluster, otherGeometryIndex=4)
        self.assertRaises(TypeError, cluster.copyDeformerWeightsTo, cluster, fast=1)


class _SkinCase(NamespaceCase):
    """root→mid→tip の chain と、それにバインドした円柱を作る。"""

    def chain(self):
        cmds.select(clear=True)
        self.root = cmds.joint(name=self.name("root"), position=(0, -2, 0))
        self.mid = cmds.joint(name=self.name("mid"), position=(0, 0, 0))
        self.tip = cmds.joint(name=self.name("tip"), position=(0, 2, 0))
        cmds.select(clear=True)
        return [self.root, self.mid, self.tip]

    def skinned(self, max_influences=3):
        joints = self.chain()
        self.mesh = cmds.polyCylinder(name=self.name("geo"), height=4, subdivisionsHeight=8)[0]
        self.skin = SkinCluster(cmds.skinCluster(joints, self.mesh, toSelectedBones=True,
                                                 maximumInfluences=max_influences)[0])
        cmds.select(clear=True)
        return self.skin

    def raw(self, skin=None):
        skin = skin or self.skin
        return [round(value, 6) for value in skin.getWeights([self.root, self.mid, self.tip])]


class GeometryFilterSkinToolsTest(_SkinCase):

    def test_classes_derive_from_geometry_filter(self):
        """SkinCluster・Cluster・BlendShape と生成クラス(deltaMush)は GeometryFilter の派生。"""
        skin = self.skinned()
        cube = cmds.polyCube(name=self.name("cube"))[0]
        cluster = mlib.getNode(cmds.cluster(cube, name=self.name("cl"))[0])
        mush = mlib.getNode(cmds.deltaMush(self.mesh, name=self.name("mush"))[0])
        for node in (skin, cluster, mush):
            with self.subTest(node=node.getType()):
                self.assertIsInstance(node, GeometryFilter)
        self.assertIs(type(cluster), mlib.Cluster)

    def test_deformer_weights_default_and_write(self):
        """値の無い頂点は1、書いた値を読み戻し、通常は Undo 1 回で戻る。"""
        cube = cmds.polyCube(name=self.name("cube"))[0]
        cluster = mlib.getNode(cmds.cluster(cube, name=self.name("cl"))[0])
        self.assertEqual(cluster.getDeformerWeights(), [1.0] * 8)
        cmds.flushUndo()
        self.assertIs(cluster.setDeformerWeights([0.25, 0.5], vertices=[2, 3]), cluster)
        values = cluster.getDeformerWeights()
        self.assertEqual(values[2:4], [0.25, 0.5])
        self.assertEqual(values[0], 1.0)
        cluster.setDeformerWeights([0.1] * 8)
        self.assertTrue(all(abs(value - 0.1) < 1e-6 for value in cluster.getDeformerWeights()))
        cmds.undo()
        cmds.undo()
        self.assertEqual(cluster.getDeformerWeights(), [1.0] * 8)

    def test_deformer_weights_fast(self):
        """fast=True は同じ値を Undo なしで書く。"""
        cube = cmds.polyCube(name=self.name("cube"))[0]
        cluster = mlib.getNode(cmds.cluster(cube, name=self.name("cl"))[0])
        cmds.flushUndo()
        cluster.setDeformerWeights([0.0, 0.75], vertices=[0, 7], fast=True)
        self.assertEqual(cluster.getDeformerWeights()[0], 0.0)
        self.assertAlmostEqual(cluster.getDeformerWeights()[7], 0.75, places=6)
        self.assertFalse(cmds.undoInfo(query=True, undoName=True))

    def test_deformer_weights_errors(self):
        """不正な入力は変更前に型どおりの例外。"""
        skin = self.skinned()
        cube = cmds.polyCube(name=self.name("cube"))[0]
        cluster = mlib.getNode(cmds.cluster(cube, name=self.name("cl"))[0])
        cases = (
            (TypeError, lambda: skin.getDeformerWeights()),
            (TypeError, lambda: cluster.getDeformerWeights(geometryIndex=True)),
            (IndexError, lambda: cluster.getDeformerWeights(geometryIndex=5)),
            (ValueError, lambda: cluster.setDeformerWeights([1.0])),
            (ValueError, lambda: cluster.setDeformerWeights([1.0, 1.0], vertices=[1, 1])),
            (ValueError, lambda: cluster.setDeformerWeights([math.nan], vertices=[0])),
            (IndexError, lambda: cluster.setDeformerWeights([1.0], vertices=[8])),
            (TypeError, lambda: cluster.setDeformerWeights(["a"], vertices=[0])),
            (TypeError, lambda: cluster.setDeformerWeights([1.0], vertices=[0], fast=1)),
        )
        for error, call in cases:
            with self.subTest(error=error.__name__):
                self.assertRaises(error, call)
        self.assertEqual(cluster.getDeformerWeights(), [1.0] * 8)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
