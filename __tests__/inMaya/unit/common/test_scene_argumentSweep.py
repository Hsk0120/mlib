"""Scene の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

ファイルはすべて ``__tests__/_output/temp/`` の一時フォルダーに作る。結果は cmds.file・cmds.ls と、
書き出したファイルの中身で突き合わせる。ファイルの操作は Undo に記録されない(docstring の Note)ので、
Undo の性質は当てはまらない。newFile・openFile・save は今のシーンを入れ替えるので、テストの後は新しいシーンにする。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import os
import pathlib
import shutil
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.common.scene import Scene
from mlib.nodes.reference import Reference

TEMP = pathlib.Path(__file__).resolve().parents[3] / "_output" / "temp"


def _host(owner, **functions):
    """クラスメソッドを、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _ensure_namespace(case):
    if not cmds.namespace(exists=case.ns):
        cmds.namespace(add=case.ns, parent=":")


def _asset(case):
    """名前空間の無い transform(assetRoot)を1つ持つ .ma を用意して、パスを返す。"""
    path = case.folder / "asset.ma"
    if not path.exists():
        node = cmds.createNode("transform", name="mlibSweepAssetRoot", skipSelect=True)
        cmds.select(node, replace=True)
        cmds.file(str(path), exportSelected=True, type="mayaAscii", force=True)
        cmds.select(clear=True)
        cmds.delete(node)
    return path


def _modified(case):
    """名前空間とノードを用意し、保存していない変更がある状態にする。"""
    _ensure_namespace(case)
    if not cmds.objExists(case.name("work")):
        case.make("transform", "work")
    cmds.file(modified=True)


_current_case = []


class _ScenePath(Scene):
    """書き出す前に、テストの名前空間があることを確かめる Scene(前の呼び出しで新しいシーンになっても同じ条件で確かめるため)。"""

    __slots__ = ()

    def export(self, nodes=None, *, force=False):
        _ensure_namespace(_current_case[0])
        return Scene.export(self, nodes, force=force)


_ScenePath.export.__doc__ = Scene.export.__doc__


def _classes(case):
    _current_case[:] = [case]
    _modified(case)
    return _host("Scene", newFile=Scene.newFile)


def _opener(case):
    _current_case[:] = [case]
    path = _asset(case)
    _modified(case)
    return Scene(str(path))


def _saver(case):
    _current_case[:] = [case]
    _modified(case)
    return Scene(str(case.folder / "saved.ma"))


def _importer(case):
    _current_case[:] = [case]
    _ensure_namespace(case)
    return Scene(str(_asset(case)))


def _exporter(case):
    _current_case[:] = [case]
    _ensure_namespace(case)
    for name in ("a", "b"):
        if not cmds.objExists(case.name(name)):
            case.make("transform", name)
    return _ScenePath(str(case.folder / "export.ma"))


def _queries(case):
    """名前の無い(一度も保存していない)新しいシーンにして、getCurrent・isModified を呼ぶ対象を返す。"""
    _current_case[:] = [case]
    cmds.file(new=True, force=True)
    _ensure_namespace(case)
    return _host("Scene", getCurrent=Scene.getCurrent, isModified=Scene.isModified)


def _queries_opened(case):
    """用意した .ma を開いたシーンにして、getCurrent・isModified を呼ぶ対象を返す。"""
    _current_case[:] = [case]
    cmds.file(str(_asset(case)), open=True, force=True)
    _ensure_namespace(case)
    return _host("Scene", getCurrent=Scene.getCurrent, isModified=Scene.isModified)


def _queries_modified(case):
    """保存していない変更がある状態にして、isModified を呼ぶ対象を返す。"""
    target = _queries(case)
    _modified(case)
    return target


def _not_current(case):
    """今のシーンでないファイルの Scene を返す(今のシーンは名前の無いシーン)。"""
    _queries(case)
    return Scene(str(_asset(case)))


def _current(case):
    """開いて今のシーンにしたファイルの Scene を返す(Windows では、大文字にしたパスで作る)。"""
    _queries_opened(case)
    path = str(_asset(case))
    return Scene(path.upper() if sys.platform == "win32" else path)


def _state(case, target):
    return [cmds.file(query=True, sceneName=True), len(cmds.ls())]


def _same_path(left, right):
    return os.path.normcase(os.path.normpath(str(left))) == os.path.normcase(os.path.normpath(str(right)))


def _expect_get_current(case, call):
    """cmds.file(query=True, sceneName=True) のパスの Scene。名前の無いシーンなら None。"""
    name = cmds.file(query=True, sceneName=True)
    if not name:
        case.assertIsNone(call.result)
        return
    case.assertIs(type(call.result), Scene)
    case.assertTrue(_same_path(call.result, name))
    case.assertTrue(call.result.isCurrent())


def _expect_is_modified(case, call):
    case.assertIs(call.result, bool(cmds.file(query=True, modified=True)))


def _expect_is_current(case, call):
    name = cmds.file(query=True, sceneName=True)
    case.assertIs(call.result, bool(name) and _same_path(call.target, name))


def _expect_new(case, call):
    """新しいシーンになる。次の呼び出しのため、保存していない変更がある状態へ戻す。"""
    case.assertIsNone(call.result)
    case.assertFalse(cmds.file(query=True, sceneName=True))
    case.assertFalse(cmds.objExists(case.name("work")))
    _modified(case)


def _expect_open(case, call):
    """開いたシーンになる。次の呼び出しのため、保存していない変更がある状態へ戻す。"""
    case.assertIsNone(call.result)
    case.assertTrue(call.target.isCurrent())
    case.assertTrue(cmds.objExists("mlibSweepAssetRoot"))
    _modified(case)


def _expect_save(case, call):
    case.assertIsNone(call.result)
    case.assertTrue(pathlib.Path(str(call.target)).is_file())
    case.assertTrue(call.target.isCurrent())
    case.assertFalse(Scene.isModified())


def _expect_import(case, call):
    namespace = call.kwargs.get("namespace")
    names = [node.getName(full=True) for node in call.result]
    case.assertTrue(any(name.endswith("mlibSweepAssetRoot") for name in names))
    if namespace:
        case.assertTrue(any((namespace.lstrip(":") + ":mlibSweepAssetRoot") in name for name in names))
    case.removeAdded()


def _expect_reference(case, call):
    case.assertIsInstance(call.result, Reference)
    case.assertEqual(
        pathlib.Path(cmds.referenceQuery(call.result.getName(), filename=True, withoutCopyNumber=True)).resolve(), pathlib.Path(str(call.target)).resolve()
    )
    namespace = call.kwargs.get("namespace")
    if namespace:
        case.assertEqual(cmds.referenceQuery(call.result.getName(), namespace=True).lstrip(":"), namespace.lstrip(":"))
    case.removeAdded()


def _expect_export(case, call):
    text = pathlib.Path(str(call.target)).read_text(encoding="utf-8", errors="replace")
    nodes = call.kwargs.get("nodes")
    if nodes is None:
        case.assertIn(case.name("a"), text)
        case.assertIn(case.name("b"), text)
    else:
        case.assertIn(case.name("a"), text)


EXPORT_NODES = (
    None,
    Lazy(lambda case: mlib.getNode(case.name("a")), "<Node>"),
    Lazy(lambda case: mlib.ls(case.name("a")), "<Nodes>"),
    Lazy(lambda case: [mlib.getNode(case.name("a")), mlib.getNode(case.name("b"))], "[<Node>, <Node>]"),
    Lazy(lambda case: [case.name("a")], "['<名前>']"),
    Lazy(lambda case: case.name("a"), "'<名前>'"),
)

METHODS = (
    Method("getCurrent", _queries, expect=_expect_get_current, state=_state),
    Method("getCurrent", _queries_opened, expect=_expect_get_current, state=_state, variant="opened"),
    Method("isModified", _queries, expect=_expect_is_modified, state=_state),
    Method("isModified", _queries_modified, expect=_expect_is_modified, state=_state, variant="modified"),
    Method("isCurrent", _not_current, expect=_expect_is_current, state=_state),
    Method("isCurrent", _current, expect=_expect_is_current, state=_state, variant="opened"),
    Method("newFile", _classes, invalid={"force": (1, "yes", None)}, expect=_expect_new, state=_state, writes=False),
    Method("openFile", _opener, invalid={"force": (1, "yes", None)}, expect=_expect_open, state=_state, writes=False),
    Method("save", _saver, invalid={"force": (1, "yes", None)}, expect=_expect_save, state=_state, writes=False),
    Method(
        "importFile",
        _importer,
        values={"namespace": (None, "mlibSweepImp", ":mlibSweepImpAbs", "mlibSweepImp_2")},
        replace=("namespace",),
        invalid={"namespace": (1.5, ["x"])},
        expect=_expect_import,
        state=_state,
        writes=False,
    ),
    Method(
        "reference",
        _importer,
        values={"namespace": (None, "mlibSweepRef", ":mlibSweepRefAbs")},
        replace=("namespace",),
        invalid={"namespace": (1.5, ["x"])},
        expect=_expect_reference,
        state=_state,
        writes=False,
    ),
    Method(
        "export",
        _exporter,
        skipCalling={"defaults": "1回目に書いたファイルが残り、2回目は上書きの確認になる"},
        values={"nodes": EXPORT_NODES},
        replace=("nodes",),
        invalid={
            "nodes": (
                Lazy(lambda case: [], "[]"),
                Lazy(lambda case: [mlib.getNode(case.name("a")), case.name("b")], "[<Node>, '<名前>']"),
                1.5,
                Lazy(lambda case: case.name("nowhere"), "'<存在しない名前>'"),
            ),
            "force": (1, "yes", None),
        },
        expect=_expect_export,
        state=_state,
        writes=False,
    ),
)


class SceneArgumentSweepTest(ArgumentSweepCase):
    """Scene の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        self.folder = TEMP / ("argumentSweep_" + self.ns)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.namespaces = set(cmds.namespaceInfo(":", listOnlyNamespaces=True) or [])

    def tearDown(self):
        cmds.file(new=True, force=True)
        _current_case[:] = []
        shutil.rmtree(str(self.folder), ignore_errors=True)
        super().tearDown()

    def removeAdded(self):
        """インポート・リファレンスで増えたものを外す。"""
        for path in cmds.file(query=True, reference=True) or []:
            cmds.file(path, removeReference=True)
        for name in cmds.ls("mlibSweepAssetRoot*", long=True) or []:
            if cmds.objExists(name):
                cmds.delete(name)
        for namespace in set(cmds.namespaceInfo(":", listOnlyNamespaces=True) or []) - self.namespaces:
            if namespace != self.ns and cmds.namespace(exists=namespace):
                cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
