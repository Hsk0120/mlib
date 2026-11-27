"""references の関数(listReferences・createReference)の引数を、表から網羅して確かめる(段1〜3)。

リファレンスするファイルは ``__tests__/_output/temp/`` の一時フォルダーへ書き出す。結果は
cmds.ls(type="reference")・cmds.file(query=True, reference=True)・cmds.referenceQuery と突き合わせる。
リファレンスの作成は Undo に記録されない(cmds.file と同じ)ので、Undo の性質は当てはまらない。
作ったリファレンスと名前空間は、各呼び出しの前とテストの後で外す。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import pathlib
import shutil
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.common import references
from mlib.nodes.reference import Reference

TEMP = pathlib.Path(__file__).resolve().parents[3] / "_output" / "temp"


def _host(owner, **functions):
    """関数を、表の対象のメソッドとして呼べるようにする(部品は対象の型からメソッドを読むため)。"""

    def wrap(function):
        def method(self, *args, **kwargs):
            return function(*args, **kwargs)

        signature = inspect.signature(function)
        first = inspect.Parameter("self", inspect.Parameter.POSITIONAL_ONLY)
        method.__signature__ = signature.replace(parameters=[first, *signature.parameters.values()])
        method.__doc__ = function.__doc__
        return method

    return type(owner, (), {name: wrap(function) for name, function in functions.items()})()


def _write_asset(case, name="asset"):
    """名前空間の無い transform を1つ持つ .ma を書き出し、そのパスを返す。"""
    path = case.folder / (name + ".ma")
    if not path.exists():
        node = cmds.createNode("transform", name=case.ns + ":" + name + "Root", skipSelect=True)
        selection = cmds.ls(selection=True)
        cmds.select(node, replace=True)
        cmds.file(str(path), exportSelected=True, type="mayaAscii", force=True)
        cmds.select(selection or None, replace=True) if selection else cmds.select(clear=True)
        cmds.delete(node)
    return path


def _creator(case):
    case.cleanReferences()
    _write_asset(case)
    return _host("references", createReference=_create, listReferences=references.listReferences)


def _create(path, namespace=None):
    """createReference を呼び、確かめた後に外せるよう、作ったリファレンスを記録する。"""
    return references.createReference(path, namespace)


_create.__signature__ = inspect.signature(references.createReference)
_create.__doc__ = references.createReference.__doc__


def _lister(case):
    """zz・aa の順にリファレンスを作り(名前順と読み込み順が逆になる)、関数を呼ぶ対象を返す。"""
    case.cleanReferences()
    path = _write_asset(case)
    for namespace in ("mlibSweepRefZz", "mlibSweepRefAa"):
        cmds.file(str(path), reference=True, namespace=namespace)
    return _host("references", listReferences=references.listReferences)


def _reference_names():
    return [name for name in cmds.ls(type="reference") or [] if name != "sharedReferenceNode" and not name.startswith("_UNKNOWN_REF_NODE_")]


def _expect_list(case, call):
    kwargs = call.kwargs
    if kwargs.get("sortBy", "name") == "load":
        expected = [cmds.referenceQuery(path, referenceNode=True) for path in cmds.file(query=True, reference=True) or []]
    else:
        expected = _reference_names()
    case.assertEqual([reference.getName() for reference in call.result], expected)


def _expect_create(case, call):
    namespace = call.kwargs.get("namespace")
    case.assertIsInstance(call.result, Reference)
    case.assertTrue(cmds.referenceQuery(call.result.getName(), isLoaded=True))
    resolved = cmds.referenceQuery(call.result.getName(), filename=True, withoutCopyNumber=True)
    case.assertEqual(pathlib.Path(resolved).resolve(), pathlib.Path(str(call.kwargs["path"])).expanduser().resolve())
    if namespace is not None:
        case.assertEqual(cmds.referenceQuery(call.result.getName(), namespace=True).lstrip(":"), namespace.lstrip(":"))
    case.cleanReferences()


PATHS = (
    Lazy(lambda case: str(case.folder / "asset.ma"), "'<str のパス>'"),
    Lazy(lambda case: case.folder / "asset.ma", "<Path>"),
    Lazy(lambda case: (case.folder / "asset.ma").as_posix(), "'</ 区切りのパス>'"),
)


class _ReferenceCase(ArgumentSweepCase):
    """一時フォルダーを作り、テストで作ったリファレンスと名前空間を外す。"""

    def setUp(self):
        super().setUp()
        self.folder = TEMP / ("argumentSweep_" + self.ns)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.namespaces = set(cmds.namespaceInfo(":", listOnlyNamespaces=True) or [])

    def tearDown(self):
        self.cleanReferences()
        shutil.rmtree(str(self.folder), ignore_errors=True)
        super().tearDown()

    def cleanReferences(self):
        """一時フォルダーのファイルのリファレンスと、テストで増えた名前空間を外す。"""
        for path in cmds.file(query=True, reference=True) or []:
            if str(self.folder.as_posix()).lower() in pathlib.Path(path.split("{")[0]).as_posix().lower():
                cmds.file(path, removeReference=True)
        for namespace in set(cmds.namespaceInfo(":", listOnlyNamespaces=True) or []) - self.namespaces:
            if namespace != self.ns and cmds.namespace(exists=namespace):
                cmds.namespace(removeNamespace=namespace, deleteNamespaceContent=True)


METHODS = (
    Method(
        "listReferences",
        _lister,
        values={"sortBy": ("name", "load")},
        replace=("sortBy",),
        invalid={"topLevelOnly": (1, "yes", None), "sortBy": ("Name", "", "loaded", 1.5, None)},
        expect=_expect_list,
        writes=False,
    ),
    Method(
        "createReference",
        _creator,
        skipCalling={"positional": "2回目の読み込みは、リファレンスノードの名前が変わる"},
        args=(PATHS[0],),
        values={"path": PATHS, "namespace": (None, "mlibSweepRef", "mlibSweepRef_2", ":mlibSweepRefAbs")},
        replace=("path", "namespace"),
        invalid={"path": ("", None, 1.5, Lazy(lambda case: str(case.folder / "none.ma"), "'<無いファイル>'")), "namespace": (1.5, ["x"])},
        expect=_expect_create,
        writes=False,
    ),
)


class ReferencesArgumentSweepTest(_ReferenceCase):
    """references の関数の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
