"""``mlib.decorator`` の公開の入口の引数を、表から網羅して確かめる(段1〜3)。

入口はコンテキストを返すだけなので、入れ物のクラス(:class:`_Decorators`)のメソッドで ``with`` に入り、
中で決まった操作をしてから抜ける。段3の「Undo 1回で戻る」は、そのままチャンクの性質の確かめになる。
引数の無い入口(nativeUnits・preservedSelection・viewportOff)は、表の呼び出しが0件なので、別のテストで確かめる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib import decorator


class _Decorators:
    """``mlib.decorator`` の入口を、表から呼べるメソッドとして持つ入れ物。

    Attributes:
        node (str): チャンクの中で値を変えるノード。
        joint (str | None): preservedSkinShape で動かすジョイント。
        mesh (str | None): preservedSkinShape で形を比べるメッシュ。
    """

    def __init__(self, node, joint=None, mesh=None):
        self.node = node
        self.joint = joint
        self.mesh = mesh


def _as_method(function, body):
    """入口を、同じ引数・docstring を持つメソッドにする。body(self, context) が ``with`` の中身と戻り値を決める。"""
    signature = inspect.signature(function)

    def method(self, **kwargs):
        return body(self, function(**kwargs))

    method.__signature__ = signature.replace(parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD), *signature.parameters.values()])
    method.__doc__ = function.__doc__
    method.__name__ = function.__name__
    return method


def _two_edits(self, context):
    """チャンクの中で2つの値を変え、閉じたあとの Undo の名前を返す。"""
    with context:
        cmds.setAttr(self.node + ".translateX", 1.5)
        cmds.setAttr(self.node + ".translateY", -2.0)
    return cmds.undoInfo(query=True, undoName=True)


def _rotate_joint(self, context):
    """保護の中でジョイントを回し、(skinClusterの数, 回す前の点, 抜けたあとの点) を返す。"""
    before = cmds.xform(self.mesh + ".vtx[*]", query=True, worldSpace=True, translation=True)
    with context as skins:
        cmds.setAttr(self.joint + ".rotateZ", 40.0)
    return [len(skins), before, cmds.xform(self.mesh + ".vtx[*]", query=True, worldSpace=True, translation=True)]


for _name, _body in (("undoChunk", _two_edits), ("undoTransaction", _two_edits), ("preservedSkinShape", _rotate_joint)):
    setattr(_Decorators, _name, _as_method(getattr(decorator, _name), _body))


def _node(case):
    return _Decorators(case.make("transform", "edited"))


def _skinned(case):
    """root→tip のジョイントにバインドした円柱を作る。"""
    cmds.select(clear=True)
    root = cmds.joint(name=case.name("root"), position=(0, -1, 0))
    cmds.joint(name=case.name("tip"), position=(0, 1, 0))
    cmds.select(clear=True)
    mesh = cmds.polyCylinder(name=case.name("geo"), height=2, subdivisionsHeight=2, subdivisionsAxis=6, constructionHistory=False)[0]
    cmds.skinCluster(root, case.name("tip"), mesh, toSelectedBones=True, name=case.name("skin"))
    cmds.select(clear=True)
    return _Decorators(case.make("transform", "edited"), root, mesh)


def _expect_chunk(case, call):
    """名前を付けたチャンクは、その名前で Undo キューに残る。"""
    name = call.kwargs.get("name")
    if name:
        case.assertEqual(call.result, name)


def _expect_shape(case, call):
    """保護の中でジョイントを回しても、メッシュの点は回す前と同じ(ジョイントを渡さなければ保護しない)。"""
    count, before, after = call.result
    joints = list(call.kwargs["joints"])
    case.assertEqual(count, 1 if joints else 0)
    if joints:
        case.assertSequenceAlmostEqual(after, before, places=4)


def _joint_names(*texts):
    return Lazy(lambda case: [case.name(text) for text in texts], f"[{', '.join(texts)}]")


METHODS = (
    Method("undoChunk", _node, values={"name": (None, "mlibSweepChunk", "")}, invalid={"name": (1.5, ["a"])}, expect=_expect_chunk),
    Method("undoTransaction", _node, values={"name": (None, "mlibSweepTransaction", "")}, invalid={"name": (1.5, ["a"])}, expect=_expect_chunk),
    Method(
        "preservedSkinShape",
        _skinned,
        args=(_joint_names("root", "tip"),),
        values={"joints": (_joint_names("root"), Lazy(lambda case: mlib.Joints([case.name("root"), case.name("tip")]), "Joints(root, tip)"), ())},
        replace=("joints",),
        invalid={"joints": (_joint_names("missing"), _joint_names("geo"), 1.5)},
        expect=_expect_shape,
    ),
)


class DecoratorArgumentSweepTest(ArgumentSweepCase):
    """``mlib.decorator`` の公開の入口の引数を網羅する。"""

    METHODS = METHODS

    def test_native_units_inside_and_restored(self):
        """nativeUnits(引数なし)は中で cm・rad にし、抜けたら元の単位に戻す(例外でも戻す)。"""
        cmds.currentUnit(linear="mm", angle="deg")
        with decorator.nativeUnits():
            self.assertEqual(om2.MDistance.uiUnit(), om2.MDistance.kCentimeters)
            self.assertEqual(om2.MAngle.uiUnit(), om2.MAngle.kRadians)
        self.assertEqual(cmds.currentUnit(query=True, linear=True), "mm")
        with self.assertRaises(KeyError), decorator.nativeUnits():
            raise KeyError("x")
        self.assertEqual(cmds.currentUnit(query=True, angle=True), "deg")

    def test_preserved_selection_restores_survivors(self):
        """preservedSelection(引数なし)は抜けたら選択を戻し、消えたものは除く。Undo 1回で中の変更も戻る。"""
        a, b = self.make("transform", "a"), self.make("transform", "b")
        cmds.select(a, b, replace=True)
        cmds.flushUndo()
        with decorator.preservedSelection():
            cmds.select(clear=True)
            cmds.delete(b)
        self.assertEqual(cmds.ls(selection=True), [a])
        cmds.undo()
        self.assertTrue(cmds.objExists(b))

    def test_viewport_off_in_batch_does_nothing(self):
        """viewportOff(引数なし)はバッチでは表示を変えず、中の処理だけを行う。"""
        if not cmds.about(batch=True):
            self.skipTest("GUI では unitGui のテストで確かめる")
        with decorator.viewportOff():
            node = self.make("transform", "inside")
        self.assertTrue(cmds.objExists(node))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
