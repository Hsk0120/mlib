"""``Transform`` の取得・設定を、ランダムな値のノードで cmds・om2 と突き合わせるテスト。

乱数は種を固定した ``random.Random`` で作り、失敗したときは subTest に種・番号・入力の値が出る。
translate・rotate(6つの回転順序)・scale・shear・ピボット4種・rotateAxis と、親の階層(親にもランダムな値)を作り、
取得(getMatrix・getTranslation(at)・getRotate・getScale・getShear・getQuaternion・getTransformation)を
cmds.getAttr・cmds.xform・om2.MTransformationMatrix と比べる。設定(setMatrix・setTranslation・setRotate・setScale・
setTransformation・setParent。ws=True/False、fast=True/False)の後のワールドの位置・マトリクスが目標どおりかを
cmds で確かめ、通常は Undo 1回で戻り、fast は Undo に残らないことも確かめる。
"""

import math
import random
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.maths import EulerRotate, Matrix, Quaternion, Transformation
from mlib.nodes import Node

SEED = 20261130
COUNT = 40
ORDERS = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")


def fmt(values):
    """subTest に出すため、数値の並びを短い文字列にする。"""
    return "(" + ", ".join(f"{value:.17g}" for value in values) + ")"


def max_diff(a, b):
    """同じ長さの2つの並びの、成分の差の最大値を返す。"""
    return max(abs(x - y) for x, y in zip(list(a), list(b)))


def same_rotation_error(a, b):
    """2つのクォータニオンの差(qと-qは同じ回転)を、成分の差の最大値で返す。"""
    a, b = list(a), list(b)
    if sum(x * y for x, y in zip(a, b)) < 0:
        b = [-value for value in b]
    return max_diff(a, b)


def world_rotation(name):
    """ワールドマトリクスを om2.MTransformationMatrix で分解した回転のクォータニオンを返す。"""
    return om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(name + ".worldMatrix[0]"))).rotation(asQuaternion=True)


def random_values(rng, pivots=True, uniform=False, positive=False, shear=True, rotate_axis=True):
    """ノードへ書くランダムな値の辞書を返す(角度は度、cmds.setAttr の単位)。"""

    def vector(scale):
        return tuple(rng.uniform(-scale, scale) for _ in range(3))

    if uniform:
        size = rng.uniform(0.3, 2.5)
        scale = (size, size, size)
    else:
        scale = tuple((1 if positive else rng.choice((-1, 1))) * rng.uniform(0.3, 2.5) for _ in range(3))
    zero = (0.0, 0.0, 0.0)
    return {
        "rotateOrder": rng.randrange(6),
        "translate": vector(10.0),
        "rotate": vector(180.0),
        "scale": scale,
        "shear": vector(0.4) if shear else zero,
        "rotateAxis": vector(90.0) if rotate_axis else zero,
        "rotatePivot": vector(4.0) if pivots else zero,
        "rotatePivotTranslate": vector(2.0) if pivots else zero,
        "scalePivot": vector(4.0) if pivots else zero,
        "scalePivotTranslate": vector(2.0) if pivots else zero,
    }


def apply_values(name, values):
    """random_values の辞書を cmds.setAttr でノードへ書く。"""
    cmds.setAttr(name + ".rotateOrder", values["rotateOrder"])
    for key, value in values.items():
        if key != "rotateOrder":
            cmds.setAttr(name + "." + key, *value)


def describe(values):
    """subTest に出すため、値の辞書を短い文字列の辞書にする。"""
    return {key: fmt(value) if isinstance(value, tuple) else value for key, value in values.items()}


class TransformRandomCase(NamespaceCase):
    """ランダムな値の階層を作る補助を持つ基底。"""

    PREFIX = "mlibTransformRandom_"

    def build(self, rng, uniform_parents=False, child=None, positive_parents=False):
        """祖父・親・子の transform を作って、ランダムな値を入れる。

        Args:
            rng (random.Random): 乱数。
            uniform_parents (bool): True なら祖父・親を一様な正のスケール・シアーなしにする
                (ワールドの回転・スケールを目標どおりにできる場合を作る)。
            child (dict | None): 子へ入れる値。None ならランダム。
            positive_parents (bool): True なら祖父・親のスケールを正にする。

        Returns:
            tuple: (祖父, 親, 子) の名前と、各ノードへ入れた値の辞書のlist。
        """
        grand = self.make("transform", "grand#")
        parent = self.make("transform", "parent#", parent=grand)
        node = self.make("transform", "child#", parent=parent)
        values = []
        for name in (grand, parent):
            value = random_values(rng, uniform=uniform_parents, positive=positive_parents, shear=not uniform_parents)
            apply_values(name, value)
            values.append(value)
        value = child if child is not None else random_values(rng)
        apply_values(node, value)
        values.append(value)
        return grand, parent, node, values

    def assertClose(self, actual, expected, tol=1e-9, label=""):
        actual, expected = list(actual), list(expected)
        self.assertEqual(len(actual), len(expected))
        self.assertLessEqual(max_diff(actual, expected), tol, f"{label} actual={fmt(actual)} expected={fmt(expected)}")


class TransformGetRandomTest(TransformRandomCase):
    """取得系を cmds・om2 と突き合わせる。"""

    def test_matrices_match_cmds(self):
        rng = random.Random(SEED)
        for index in range(COUNT):
            _grand, parent, name, values = self.build(rng)
            with self.subTest(seed=SEED, index=index, child=describe(values[2]), parent=describe(values[1]), grand=describe(values[0])):
                node = Node(name)
                self.assertClose(node.getMatrix(), cmds.getAttr(name + ".matrix"), label="local")
                self.assertClose(node.getMatrix(ws=True), cmds.getAttr(name + ".worldMatrix[0]"), label="world")
                self.assertClose(node.getMatrix(ws=True), cmds.xform(name, query=True, matrix=True, worldSpace=True), label="xform")
                self.assertClose(node.getMatrix(ws=True, parent=True), cmds.getAttr(name + ".parentMatrix[0]"), label="parent")
                self.assertClose(node.getMatrix(ws=True, inverse=True), cmds.getAttr(name + ".worldInverseMatrix[0]"), tol=1e-8, label="inverse")
                self.assertClose(node.getMatrix(parent=True), cmds.getAttr(parent + ".matrix"), tol=1e-8, label="local parent")
                transformation = node.getTransformation()
                self.assertIsInstance(transformation, Transformation)
                self.assertEqual(transformation.rotateOrder, values[2]["rotateOrder"])
                self.assertClose(transformation.matrix, cmds.getAttr(name + ".matrix"), label="transformation")
                self.assertClose(transformation.rotate, [math.radians(v) for v in values[2]["rotate"]], label="rotate")
                self.assertClose(transformation.scalePivot, values[2]["scalePivot"], label="sp")

    def test_translation_at_each_reference(self):
        rng = random.Random(SEED + 1)
        for index in range(COUNT):
            _grand, _parent, name, values = self.build(rng)
            with self.subTest(seed=SEED + 1, index=index, child=describe(values[2])):
                node = Node(name)
                parent_matrix = om2.MMatrix(cmds.getAttr(name + ".parentMatrix[0]"))
                world = om2.MMatrix(cmds.getAttr(name + ".worldMatrix[0]"))
                local = om2.MMatrix(cmds.getAttr(name + ".matrix"))
                self.assertClose(node.getTranslation(ws=True, at=0), [parent_matrix.getElement(3, c) for c in range(3)], label="at=0 ws")
                self.assertClose(node.getTranslation(at=0), (0, 0, 0), label="at=0")
                translate = cmds.getAttr(name + ".translate")[0]
                self.assertClose(node.getTranslation(at=1), translate, label="at=1")
                point = om2.MPoint(*translate) * parent_matrix
                self.assertClose(node.getTranslation(ws=True, at=1), (point.x, point.y, point.z), label="at=1 ws")
                pivot = cmds.xform(name, query=True, worldSpace=True, rotatePivot=True)
                self.assertClose(node.getTranslation(ws=True), pivot, tol=1e-8, label="at=2 ws")
                self.assertClose(node.getTranslation(ws=True, at=2), pivot, tol=1e-8, label="at=2 ws")
                local_pivot = om2.MPoint(*pivot) * parent_matrix.inverse()
                self.assertClose(node.getTranslation(), (local_pivot.x, local_pivot.y, local_pivot.z), tol=1e-8, label="at=2")
                self.assertClose(node.getTranslation(ws=True, at=3), cmds.xform(name, query=True, worldSpace=True, scalePivot=True), tol=1e-8, label="at=3 ws")
                self.assertClose(node.getTranslation(ws=True, at=4), [world.getElement(3, c) for c in range(3)], label="at=4 ws")
                self.assertClose(node.getTranslation(at=4), [local.getElement(3, c) for c in range(3)], label="at=4")

    def test_rotate_scale_shear_and_quaternion(self):
        rng = random.Random(SEED + 2)
        for index in range(COUNT):
            child = random_values(rng, positive=True, rotate_axis=index % 3 != 0)
            child["rotate"] = tuple(rng.uniform(-540.0, 540.0) for _ in range(3))
            _grand, _parent, name, values = self.build(rng, uniform_parents=index % 2 == 0, child=child, positive_parents=True)
            with self.subTest(seed=SEED + 2, index=index, child=describe(values[2]), uniformParents=index % 2 == 0):
                node = Node(name)
                order = values[2]["rotateOrder"]
                rotate = [math.radians(v) for v in values[2]["rotate"]]
                local = node.getRotate()
                self.assertEqual(local.order, order)
                axis = om2.MEulerRotation(*(math.radians(v) for v in values[2]["rotateAxis"])).asQuaternion()
                channel = om2.MEulerRotation(*rotate, order).asQuaternion()
                # ローカルの回転は rotateAxis を含む。rotateAxis が0なら、今のチャンネルに最も近い解なのでチャンネルの値そのものになる。
                self.assertLessEqual(same_rotation_error(local.asQuaternion(), axis * channel), 1e-9)
                if index % 3 == 0:
                    self.assertClose(local, rotate, tol=1e-9, label="getRotate")
                self.assertLessEqual(same_rotation_error(node.getQuaternion(), channel), 1e-9)
                self.assertLessEqual(same_rotation_error(node.getQuaternion(rotateAxis=True), axis * channel), 1e-9)
                other = (order + 1 + rng.randrange(5)) % 6
                reordered = node.getRotate(order=other)
                self.assertEqual(reordered.order, other)
                self.assertLessEqual(same_rotation_error(reordered.asQuaternion(), axis * channel), 1e-9)
                self.assertClose(node.getScale(), values[2]["scale"], label="scale")
                self.assertClose(node.getShear(), values[2]["shear"], label="shear")
                reference = om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(name + ".worldMatrix[0]")))
                world = node.getRotate(ws=True)
                self.assertEqual(world.order, order)
                self.assertLessEqual(same_rotation_error(world.asQuaternion(), reference.rotation(asQuaternion=True)), 1e-8)
                self.assertLessEqual(same_rotation_error(node.getQuaternion(ws=True, rotateAxis=True), reference.rotation(asQuaternion=True)), 1e-8)
                self.assertClose(node.getScale(ws=True), reference.scale(om2.MSpace.kWorld), tol=1e-8, label="world scale")
                self.assertClose(node.getShear(ws=True), reference.shear(om2.MSpace.kWorld), tol=1e-8, label="world shear")


class TransformSetRandomTest(TransformRandomCase):
    """設定系の結果を cmds で確かめる。"""

    def check_undo(self, name, fast, before_world):
        """通常は Undo 1回でワールドマトリクスが戻り、fast は Undo に何も残らないことを確かめる。"""
        if fast:
            self.assertUndoEmpty()
        else:
            self.assertFalse(cmds.undoInfo(query=True, undoQueueEmpty=True))
            cmds.undo()
            self.assertClose(cmds.getAttr(name + ".worldMatrix[0]"), before_world, tol=1e-9, label="undo")

    def test_set_matrix_world_and_local(self):
        rng = random.Random(SEED + 3)
        for index in range(COUNT):
            _grand, _parent, name, values = self.build(rng)
            target = om2.MTransformationMatrix()
            target.setScale([rng.choice((-1, 1)) * rng.uniform(0.3, 2.5) for _ in range(3)], om2.MSpace.kTransform)
            target.setShear([rng.uniform(-0.4, 0.4) for _ in range(3)], om2.MSpace.kTransform)
            target.setRotation(om2.MEulerRotation(*(rng.uniform(-math.pi, math.pi) for _ in range(3)), rng.randrange(6)))
            target.setTranslation(om2.MVector(*(rng.uniform(-10, 10) for _ in range(3))), om2.MSpace.kTransform)
            matrix = target.asMatrix()
            fast = index % 2 == 1
            world = index % 4 < 2
            with self.subTest(seed=SEED + 3, index=index, fast=fast, ws=world, matrix=fmt(list(matrix)), child=describe(values[2])):
                node = Node(name)
                before = cmds.getAttr(name + ".worldMatrix[0]")
                pivots = [cmds.getAttr(name + "." + attr)[0] for attr in ("rotatePivot", "scalePivot", "rotateAxis")]
                self.flushUndo()
                node.setMatrix(Matrix(matrix), ws=world, fast=fast)
                attr = ".worldMatrix[0]" if world else ".matrix"
                self.assertClose(cmds.getAttr(name + attr), matrix, tol=1e-8, label="setMatrix")
                self.assertEqual([cmds.getAttr(name + "." + attr)[0] for attr in ("rotatePivot", "scalePivot", "rotateAxis")], pivots)
                self.check_undo(name, fast, before)

    def test_set_translation_world_at_each_reference(self):
        rng = random.Random(SEED + 4)
        for index in range(COUNT):
            _grand, _parent, name, values = self.build(rng)
            at = (1, 2, 3, 4)[index % 4]
            fast = index % 8 >= 4
            point = tuple(rng.uniform(-10.0, 10.0) for _ in range(3))
            with self.subTest(seed=SEED + 4, index=index, at=at, fast=fast, point=fmt(point), child=describe(values[2])):
                node = Node(name)
                before = cmds.getAttr(name + ".worldMatrix[0]")
                rotate = cmds.getAttr(name + ".rotate")[0]
                self.flushUndo()
                node.setTranslation(point, ws=True, at=at, fast=fast)
                if at == 1:
                    translate = om2.MPoint(*cmds.getAttr(name + ".translate")[0]) * om2.MMatrix(cmds.getAttr(name + ".parentMatrix[0]"))
                    actual = (translate.x, translate.y, translate.z)
                elif at == 2:
                    actual = cmds.xform(name, query=True, worldSpace=True, rotatePivot=True)
                elif at == 3:
                    actual = cmds.xform(name, query=True, worldSpace=True, scalePivot=True)
                else:
                    actual = cmds.getAttr(name + ".worldMatrix[0]")[12:15]
                self.assertClose(actual, point, tol=1e-8, label=f"at={at}")
                self.assertClose(node.getTranslation(ws=True, at=at), point, tol=1e-8, label="get")
                self.assertEqual(cmds.getAttr(name + ".rotate")[0], rotate)
                self.check_undo(name, fast, before)

    def test_set_rotate_world_keeps_pivot(self):
        rng = random.Random(SEED + 5)
        for index in range(COUNT):
            _grand, _parent, name, values = self.build(rng, uniform_parents=True, child=random_values(rng, positive=True))
            target = EulerRotate(*(rng.uniform(-math.pi, math.pi) for _ in range(3)), rng.randrange(6))
            fast = index % 2 == 1
            world = index % 4 < 2
            with self.subTest(seed=SEED + 5, index=index, fast=fast, ws=world, target=fmt(target), order=target.order, child=describe(values[2])):
                node = Node(name)
                before = cmds.getAttr(name + ".worldMatrix[0]")
                pivot = cmds.xform(name, query=True, worldSpace=True, rotatePivot=True)
                scale = cmds.getAttr(name + ".scale")[0]
                self.flushUndo()
                node.setRotate(target, ws=world, fast=fast)
                if world:
                    self.assertLessEqual(same_rotation_error(world_rotation(name), target.asQuaternion()), 1e-8)
                else:
                    order = cmds.getAttr(name + ".rotateOrder")
                    channel = om2.MEulerRotation(*(math.radians(v) for v in cmds.getAttr(name + ".rotate")[0]), order)
                    # ローカルの回転は rotateAxis * rotate なので、rotate は rotateAxis を除いた残り。
                    axis = om2.MEulerRotation(*(math.radians(v) for v in values[2]["rotateAxis"])).asQuaternion()
                    self.assertLessEqual(same_rotation_error(axis * channel.asQuaternion(), target.asQuaternion()), 1e-9)
                    # 書き込む値は、元のチャンネルに最も近い解。
                    old = om2.MEulerRotation(*(math.radians(v) for v in values[2]["rotate"]), order)
                    self.assertClose(channel, channel.closestSolution(old), tol=1e-8, label="closest")
                self.assertClose(cmds.xform(name, query=True, worldSpace=True, rotatePivot=True), pivot, tol=1e-8, label="pivot")
                self.assertEqual(cmds.getAttr(name + ".scale")[0], scale)
                self.check_undo(name, fast, before)

    def test_set_scale_local_and_world(self):
        rng = random.Random(SEED + 6)
        for index in range(COUNT):
            _grand, _parent, name, values = self.build(rng, uniform_parents=True, child=random_values(rng, positive=True))
            target = tuple(rng.uniform(0.2, 3.0) for _ in range(3))
            fast = index % 2 == 1
            world = index % 4 < 2
            with self.subTest(seed=SEED + 6, index=index, fast=fast, ws=world, target=fmt(target), child=describe(values[2])):
                node = Node(name)
                before = cmds.getAttr(name + ".worldMatrix[0]")
                rotate = cmds.getAttr(name + ".rotate")[0]
                self.flushUndo()
                node.setScale(target, ws=world, fast=fast)
                if world:
                    reference = om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(name + ".worldMatrix[0]")))
                    self.assertClose(reference.scale(om2.MSpace.kWorld), target, tol=1e-8, label="world scale")
                    self.assertClose(node.getScale(ws=True), target, tol=1e-8, label="getScale")
                else:
                    self.assertClose(cmds.getAttr(name + ".scale")[0], target, tol=1e-12, label="scale")
                self.assertEqual(cmds.getAttr(name + ".rotate")[0], rotate)
                self.check_undo(name, fast, before)

    def test_set_transformation(self):
        rng = random.Random(SEED + 7)
        source = self.make("transform", "source#")
        for index in range(COUNT):
            _grand, _parent, name, _values = self.build(rng)
            apply_values(source, random_values(rng))
            value = Node(source).getTransformation()
            fast = index % 2 == 1
            with self.subTest(seed=SEED + 7, index=index, fast=fast, value=repr(value)):
                node = Node(name)
                before = cmds.getAttr(name + ".worldMatrix[0]")
                self.flushUndo()
                node.setTransformation(value, fast=fast)
                self.assertClose(cmds.getAttr(name + ".matrix"), cmds.getAttr(source + ".matrix"), tol=1e-9, label="matrix")
                for attr in ("translate", "rotate", "scale", "shear", "rotateAxis", "rotatePivot", "scalePivotTranslate"):
                    self.assertClose(cmds.getAttr(name + "." + attr)[0], cmds.getAttr(source + "." + attr)[0], tol=1e-9, label=attr)
                self.assertEqual(cmds.getAttr(name + ".rotateOrder"), cmds.getAttr(source + ".rotateOrder"))
                self.check_undo(name, fast, before)

    def test_set_parent_keeps_world_or_local(self):
        rng = random.Random(SEED + 8)
        for index in range(COUNT):
            grand, parent, name, values = self.build(rng)
            other = self.make("transform", "other#")
            apply_values(other, random_values(rng))
            fast = index % 2 == 1
            relative = index % 4 >= 2
            destination = rng.choice((other, grand, None))
            with self.subTest(seed=SEED + 8, index=index, fast=fast, relative=relative, destination=destination, child=describe(values[2])):
                node = Node(name)
                world = cmds.getAttr(name + ".worldMatrix[0]")
                local = cmds.getAttr(name + ".matrix")
                self.flushUndo()
                node.setParent(destination, relative=relative, fast=fast)
                path = node.getName(full=True)
                parents = cmds.listRelatives(path, parent=True, fullPath=True)
                if destination is None:
                    self.assertIsNone(parents)
                else:
                    self.assertEqual(parents, cmds.ls(destination, long=True))
                if relative:
                    self.assertClose(cmds.getAttr(path + ".matrix"), local, tol=1e-9, label="local")
                else:
                    self.assertClose(cmds.getAttr(path + ".worldMatrix[0]"), world, tol=1e-8, label="world")
                if fast:
                    self.assertUndoEmpty()
                else:
                    cmds.undo()
                    self.assertEqual(cmds.listRelatives(path if cmds.objExists(path) else name, parent=True, fullPath=True), cmds.ls(parent, long=True))
                    self.assertClose(cmds.getAttr(name + ".worldMatrix[0]"), world, tol=1e-9, label="undo")


class NegativeScaleRandomTest(TransformRandomCase):
    """負のスケールと、中間の軸が ±90 度に近い回転の取得・設定。"""

    def test_world_rotate_follows_channel_scale_sign(self):
        rng = random.Random(SEED + 11)
        for index in range(COUNT):
            child = random_values(rng, shear=False)
            if all(value > 0 for value in child["scale"]):
                child["scale"] = (-child["scale"][0], *child["scale"][1:])
            _grand, _parent, name, values = self.build(rng, uniform_parents=True, child=child, positive_parents=True)
            with self.subTest(seed=SEED + 11, index=index, child=describe(values[2])):
                node = Node(name)
                order = values[2]["rotateOrder"]
                axis = om2.MEulerRotation(*(math.radians(v) for v in values[2]["rotateAxis"])).asQuaternion()
                channel = om2.MEulerRotation(*(math.radians(v) for v in values[2]["rotate"]), order).asQuaternion()
                parent_rotation = om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(name + ".parentMatrix[0]"))).rotation(asQuaternion=True)
                # スケールの符号をチャンネルに合わせるので、ワールドの回転は rotateAxis * rotate * 親の回転になる。
                expected = axis * channel * parent_rotation
                self.assertLessEqual(same_rotation_error(node.getRotate(ws=True).asQuaternion(), expected), 1e-8)
                self.assertLessEqual(same_rotation_error(node.getRotate().asQuaternion(), axis * channel), 1e-9)

    def test_set_rotate_world_with_negative_scale(self):
        rng = random.Random(SEED + 12)
        for index in range(COUNT):
            child = random_values(rng, shear=False)
            if all(value > 0 for value in child["scale"]):
                child["scale"] = (*child["scale"][:2], -child["scale"][2])
            grand, parent, name, values = self.build(rng, uniform_parents=True, child=child, positive_parents=True)
            target = EulerRotate(*(rng.uniform(-math.pi, math.pi) for _ in range(3)), rng.randrange(6))
            fast = index % 2 == 1
            with self.subTest(seed=SEED + 12, index=index, fast=fast, target=fmt(target), order=target.order, child=describe(values[2])):
                node = Node(name)
                scale = cmds.getAttr(name + ".scale")[0]
                node.setRotate(target, ws=True, fast=fast)
                self.assertEqual(cmds.getAttr(name + ".scale")[0], scale)
                self.assertLessEqual(same_rotation_error(node.getRotate(ws=True).asQuaternion(), target.asQuaternion()), 1e-8)
                # ワールドの 3x3 は、チャンネルのスケール * 目標の回転 * 親の一様なスケール。
                size = cmds.getAttr(parent + ".scale")[0][0] * cmds.getAttr(grand + ".scale")[0][0]
                rotation = target.asMatrix()
                world = om2.MMatrix(cmds.getAttr(name + ".worldMatrix[0]"))
                for row in range(3):
                    for col in range(3):
                        self.assertAlmostEqual(world.getElement(row, col), scale[row] * rotation.getElement(row, col) * size, places=8)

    def gimbal_cases(self, seed, offsets):
        """中間の軸を ±90 度 + offsets のどれかにした、(回転順序, 度の3成分) を順に返す。"""
        rng = random.Random(seed)
        for index in range(COUNT):
            order = index % 6
            values = [rng.uniform(-180.0, 180.0) for _ in range(3)]
            middle = "xyz".index(ORDERS[order][1])
            values[middle] = rng.choice((-90.0, 90.0)) + rng.choice((-1.0, 1.0)) * rng.choice(offsets)
            yield index, order, values

    def test_gimbal_channel_round_trip(self):
        node_name = self.make("transform", "gimbal#")
        node = Node(node_name)
        for index, order, values in self.gimbal_cases(SEED + 13, (0.0, 1e-2, 1.0)):
            with self.subTest(seed=SEED + 13, index=index, order=ORDERS[order], rotate=fmt(values)):
                cmds.setAttr(node_name + ".rotateOrder", order)
                cmds.setAttr(node_name + ".rotate", *values)
                matrix = cmds.getAttr(node_name + ".matrix")
                value = node.getRotate()
                self.assertEqual(value.order, order)
                self.assertClose(value.asDegrees(), values, tol=1e-6, label="channel")
                self.assertClose(value.asMatrix(), matrix, tol=1e-9, label="matrix")
                # 書き戻しても、チャンネルの値は変わらない。
                node.setRotate(value)
                self.assertClose(cmds.getAttr(node_name + ".rotate")[0], values, tol=1e-6, label="setRotate")
                node.setMatrix(Matrix(matrix))
                self.assertClose(cmds.getAttr(node_name + ".rotate")[0], values, tol=1e-6, label="setMatrix")

    def test_near_gimbal_channel_round_trip(self):
        node_name = self.make("transform", "nearGimbal#")
        node = Node(node_name)
        for index, order, values in self.gimbal_cases(SEED + 15, (1e-4, 3e-4, 5e-5)):
            with self.subTest(seed=SEED + 15, index=index, order=ORDERS[order], rotate=fmt(values)):
                cmds.setAttr(node_name + ".rotateOrder", order)
                cmds.setAttr(node_name + ".rotate", *values)
                matrix = cmds.getAttr(node_name + ".matrix")
                # docstring: Transform では今の rotate チャンネルにいちばん近い解を選び、setRotate と行き来しても
                # チャンネルの値が変わらない。
                self.assertClose(node.getRotate().asDegrees(), values, tol=1e-6, label="channel")
                node.setRotate(node.getRotate())
                self.assertClose(cmds.getAttr(node_name + ".rotate")[0], values, tol=1e-6, label="setRotate")
                node.setMatrix(Matrix(matrix))
                self.assertClose(cmds.getAttr(node_name + ".rotate")[0], values, tol=1e-6, label="setMatrix")


class JointRandomTest(TransformRandomCase):
    """jointOrient・inverseScale を持つ Joint の取得・設定を突き合わせる。"""

    def build_joints(self, rng, positive=False, pivots=False):
        """親子の joint を作り、ランダムな値を入れる(既定ではピボットは0)。"""
        cmds.select(clear=True)
        root = cmds.joint(name=self.name("root#"))
        child = cmds.joint(name=self.name("child#"))
        values = []
        for name in (root, child):
            value = random_values(rng, pivots=pivots, positive=positive, shear=False)
            value["jointOrient"] = tuple(rng.uniform(-180.0, 180.0) for _ in range(3))
            apply_values(name, value)
            cmds.setAttr(name + ".segmentScaleCompensate", rng.random() < 0.5)
            values.append(value)
        return root, child, values

    def test_getters_match_cmds(self):
        rng = random.Random(SEED + 9)
        for index in range(COUNT):
            _root, name, values = self.build_joints(rng, positive=True)
            with self.subTest(seed=SEED + 9, index=index, child=describe(values[1]), root=describe(values[0])):
                node = Node(name)
                self.assertClose(node.getMatrix(), cmds.getAttr(name + ".matrix"), label="local")
                self.assertClose(node.getMatrix(ws=True), cmds.getAttr(name + ".worldMatrix[0]"), label="world")
                self.assertClose(node.getTransformation().matrix, cmds.getAttr(name + ".matrix"), label="transformation")
                self.assertClose(node.getJointOrient(), [math.radians(v) for v in values[1]["jointOrient"]], label="jointOrient")
                self.assertClose(node.getTranslation(ws=True), cmds.xform(name, query=True, worldSpace=True, rotatePivot=True), tol=1e-8, label="at=2")
                self.assertClose(node.getTranslation(ws=True, at=4), cmds.getAttr(name + ".worldMatrix[0]")[12:15], label="at=4")
                reference = om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(name + ".worldMatrix[0]")))
                self.assertLessEqual(same_rotation_error(node.getRotate(ws=True).asQuaternion(), reference.rotation(asQuaternion=True)), 1e-8)
                order = values[1]["rotateOrder"]
                channel = om2.MEulerRotation(*(math.radians(v) for v in values[1]["rotate"]), order).asQuaternion()
                orient = om2.MEulerRotation(*(math.radians(v) for v in values[1]["jointOrient"])).asQuaternion()
                axis = om2.MEulerRotation(*(math.radians(v) for v in values[1]["rotateAxis"])).asQuaternion()
                self.assertLessEqual(same_rotation_error(node.getQuaternion(), channel * orient), 1e-9)
                self.assertLessEqual(same_rotation_error(node.getQuaternion(rotateAxis=True), axis * channel * orient), 1e-9)
                # getRotate はローカルのマトリクスの回転。segmentScaleCompensate の 1/inverseScale も含むマトリクスを分解する。
                local = om2.MTransformationMatrix(om2.MMatrix(cmds.getAttr(name + ".matrix"))).rotation(asQuaternion=True)
                self.assertLessEqual(same_rotation_error(node.getRotate().asQuaternion(), local), 1e-9)
                if not cmds.getAttr(name + ".segmentScaleCompensate"):
                    self.assertLessEqual(same_rotation_error(node.getRotate().asQuaternion(), axis * channel * orient), 1e-9)

    def test_getters_with_pivots_match_cmds(self):
        rng = random.Random(SEED + 14)
        for index in range(COUNT):
            _root, name, values = self.build_joints(rng, positive=True, pivots=True)
            with self.subTest(seed=SEED + 14, index=index, child=describe(values[1]), root=describe(values[0])):
                node = Node(name)
                self.assertClose(node.getMatrix(), cmds.getAttr(name + ".matrix"), label="local")
                self.assertClose(node.getMatrix(ws=True), cmds.getAttr(name + ".worldMatrix[0]"), label="world")
                self.assertClose(node.getTransformation().matrix, cmds.getAttr(name + ".matrix"), tol=1e-8, label="transformation")
                self.assertClose(node.getTranslation(ws=True, at=3), cmds.xform(name, query=True, worldSpace=True, scalePivot=True), tol=1e-8, label="at=3")
                self.assertClose(node.getTranslation(ws=True, at=4), cmds.getAttr(name + ".worldMatrix[0]")[12:15], label="at=4")

    def test_rotate_pivot_position_with_pivots(self):
        rng = random.Random(SEED + 14)
        for index in range(COUNT):
            _root, name, values = self.build_joints(rng, positive=True, pivots=True)
            with self.subTest(seed=SEED + 14, index=index, child=describe(values[1]), root=describe(values[0])):
                node = Node(name)
                self.assertClose(node.getTranslation(ws=True), cmds.xform(name, query=True, worldSpace=True, rotatePivot=True), tol=1e-8, label="at=2")
                # setTranslation(at=2) も、cmds.xform の回転ピボットを目標の位置へ合わせる(通常・fast)。
                for fast in (False, True):
                    point = tuple(rng.uniform(-10, 10) for _ in range(3))
                    node.setTranslation(point, ws=True, fast=fast)
                    self.assertClose(cmds.xform(name, query=True, worldSpace=True, rotatePivot=True), point, tol=1e-8, label=f"setTranslation fast={fast}")

    def test_setters_reach_world_targets(self):
        rng = random.Random(SEED + 10)
        for index in range(COUNT):
            root, name, values = self.build_joints(rng, positive=True)
            # 親の scale を一様にして、ワールドの回転を目標どおりにできるようにする。
            size = rng.uniform(0.5, 2.0)
            cmds.setAttr(root + ".scale", size, size, size)
            fast = index % 2 == 1
            kind = ("matrix", "rotate", "translate")[index % 3]
            target = om2.MTransformationMatrix()
            target.setRotation(om2.MEulerRotation(*(rng.uniform(-math.pi, math.pi) for _ in range(3)), rng.randrange(6)))
            target.setScale([rng.uniform(0.3, 2.5) for _ in range(3)], om2.MSpace.kTransform)
            target.setTranslation(om2.MVector(*(rng.uniform(-10, 10) for _ in range(3))), om2.MSpace.kTransform)
            with self.subTest(seed=SEED + 10, index=index, fast=fast, kind=kind, target=fmt(list(target.asMatrix())), child=describe(values[1])):
                node = Node(name)
                before = cmds.getAttr(name + ".worldMatrix[0]")
                self.flushUndo()
                if kind == "matrix":
                    node.setMatrix(Matrix(target.asMatrix()), ws=True, fast=fast)
                    self.assertClose(cmds.getAttr(name + ".worldMatrix[0]"), target.asMatrix(), tol=1e-8, label="setMatrix")
                elif kind == "rotate":
                    quaternion = Quaternion(target.rotation(asQuaternion=True))
                    pivot = cmds.xform(name, query=True, worldSpace=True, rotatePivot=True)
                    node.setRotate(quaternion, ws=True, fast=fast)
                    self.assertLessEqual(same_rotation_error(world_rotation(name), quaternion), 1e-8)
                    self.assertClose(cmds.xform(name, query=True, worldSpace=True, rotatePivot=True), pivot, tol=1e-8, label="pivot")
                else:
                    point = tuple(target.translation(om2.MSpace.kTransform))
                    node.setTranslation(point, ws=True, fast=fast)
                    self.assertClose(cmds.xform(name, query=True, worldSpace=True, rotatePivot=True), point, tol=1e-8, label="setTranslation")
                self.check_undo(name, fast, before)

    def check_undo(self, name, fast, before_world):
        """通常は Undo 1回でワールドマトリクスが戻り、fast は Undo に何も残らないことを確かめる。"""
        if fast:
            self.assertUndoEmpty()
        else:
            cmds.undo()
            self.assertClose(cmds.getAttr(name + ".worldMatrix[0]"), before_world, tol=1e-9, label="undo")


if __name__ == "__main__":
    import sys

    unittest.main(argv=[sys.argv[0]])
