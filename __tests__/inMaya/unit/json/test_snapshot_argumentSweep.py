"""Snapshot(基底)と ValidationReport の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

基底のメソッド(load・save・validate・apply)は、PoseSnapshot のインスタンスで呼ぶ。
保存先は ``__tests__/_output/temp/`` の一時フォルダー。適用の結果は cmds.getAttr で読み直して突き合わせる。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import json as std_json
import os
import pathlib
import re
import shutil
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.json import NameMapping, PoseSnapshot, ValidationReport

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


def _known(stage, name, values, reason):
    """場合の名前を、fnmatch の記号([ など)を文字として扱う形にして返す。"""
    return {f"{stage}:" + re.sub(r"([*?[])", r"[\1]", f"{name}={value!r}"): reason for value in values}


class _PathLike:
    """os.PathLike を満たすだけの、str でも Path でもないパス。"""

    def __init__(self, path):
        self.path = str(path)

    def __fspath__(self):
        return self.path

    def __repr__(self):
        return "<PathLike>"


VALUES = (("root", "translateX", 1.5), ("root", "rotateY", 30.0), ("arm", "blend", 0.25))


def _build(case):
    """root と子の arm を作り、値を書いてポーズを取得し、値を変えて PoseSnapshot を返す。"""
    root = case.make("transform", "root")
    arm = case.make("joint", "arm", parent=root)
    cmds.addAttr(arm, longName="blend", attributeType="double", keyable=True)
    for node, attr, value in VALUES:
        cmds.setAttr(case.name(node) + "." + attr, value)
    snapshot = PoseSnapshot.capture([root, arm])
    for node, attr, _ in VALUES:
        cmds.setAttr(case.name(node) + "." + attr, 0.0)
    return snapshot


def _loader(case):
    """保存したファイル(正しい形・形式名の違う形)を用意し、PoseSnapshot.load を呼ぶ対象を返す。"""
    _build(case).save(str(case.folder / "pose.json"))
    (case.folder / "wrong.json").write_text(std_json.dumps({"header": {"format": "mlib.other", "version": 1}, "data": {}}), encoding="utf-8")
    (case.folder / "broken.json").write_text("{", encoding="utf-8")
    return _host("PoseSnapshot", load=PoseSnapshot.load)


def _report(case):
    report = ValidationReport()
    report._add_missing(case.name("missing"))
    report._add_skipped(case.name("root.translateX"), "locked")
    return report


def _mapped(case, kwargs):
    """適用の引数で、名前空間の root・arm がそれぞれ自分自身に対応づくか(NameMapping で求める)。"""
    mapping = NameMapping(nameMap=kwargs.get("nameMap"), replace=kwargs.get("replace"), namespaceMap=kwargs.get("namespaceMap"))
    return {node: mapping.convert(case.name(node)) == case.name(node) for node in ("root", "arm")}


def _expect_validate(case, call):
    case.assertIsInstance(call.result, ValidationReport)
    case.assertEqual(not call.result.missing, all(_mapped(case, call.kwargs).values()))


def _expect_apply(case, call):
    """自分に対応づくノードは保存した値へ戻り、そうでないノードは見つからないものとして記録して値を変えない。"""
    case.assertIsInstance(call.result, ValidationReport)
    mapped = _mapped(case, call.kwargs)
    case.assertEqual(not call.result.missing, all(mapped.values()))
    for node, attr, value in VALUES:
        case.assertAlmostEqual(cmds.getAttr(case.name(node) + "." + attr), value if mapped[node] else 0.0, places=6)


def _expect_save(case, call):
    path = pathlib.Path(os.fspath(call.kwargs["path"]))
    case.assertIsInstance(call.result, pathlib.Path)
    case.assertTrue(call.result.is_absolute())
    case.assertEqual(os.path.normcase(str(call.result)), os.path.normcase(str(path.resolve())))
    raw = std_json.loads(call.result.read_text(encoding="utf-8"))
    case.assertEqual(raw["header"]["format"], PoseSnapshot.FORMAT)
    case.assertEqual(PoseSnapshot.load(call.result).toData(), call.target.toData())


def _expect_load(case, call):
    case.assertIsInstance(call.result, PoseSnapshot)
    case.assertIsNotNone(call.result.header)
    case.assertEqual(call.result.header.format, PoseSnapshot.FORMAT)
    attrs = {entry["node"]["name"].split(":")[-1]: entry["attrs"] for entry in call.result.toData()["nodes"]}
    for node, attr, value in VALUES:
        case.assertAlmostEqual(attrs[node][attr], value, places=6)


def _expect_warn(case, call):
    case.assertIsNone(call.result)


#: 名前の対応づけの候補(自分に対応づく・見つからない名前へ対応づく)。
NAME_MAPS = (None, {}, {"root": "root"}, {"root": "nowhere"}, {"other": "x"})
REPLACES = (None, [], [("root", "root")], [("root", "nowhere")], (("arm", "leg"),), [["_L_", "_R_"]])
NAMESPACE_MAPS = (
    None,
    {},
    Lazy(lambda case: {case.ns: case.ns}, "{<名前空間>: <名前空間>}"),
    Lazy(lambda case: {":" + case.ns: case.ns}, "{':<名前空間>': <名前空間>}"),
    Lazy(lambda case: {case.ns: "nowhere"}, "{<名前空間>: 'nowhere'}"),
)
#: 名前の対応づけの誤った値。
NAME_MAP_INVALID = ("abc", 1.5, {"root": 1}, {1: "root"}, [("root", "x")])
REPLACE_INVALID = ("abc", 1.5, [("root",)], [("", "x")], [("root", 1)], [1])
NAMESPACE_MAP_INVALID = ("abc", 1.5, {1: "x"}, {"x": None})
MAPPING_VALUES = {"nameMap": NAME_MAPS, "replace": REPLACES, "namespaceMap": NAMESPACE_MAPS}
MAPPING_INVALID = {"nameMap": NAME_MAP_INVALID, "replace": REPLACE_INVALID, "namespaceMap": NAMESPACE_MAP_INVALID}
MAPPING_NAMES = ("nameMap", "replace", "namespaceMap")


def _save_paths():
    return (
        Lazy(lambda case: str(case.folder / "pose.json"), "'<str のパス>'"),
        Lazy(lambda case: case.folder / "pose.json", "<Path>"),
        Lazy(lambda case: _PathLike(case.folder / "pose.json"), "<PathLike>"),
        Lazy(lambda case: str(case.folder / "new" / "deep" / "pose.json"), "'<無いフォルダーの中>'"),
        Lazy(lambda case: str(case.folder / "日本語 の 名前.json"), "'<日本語と空白の名前>'"),
    )


#: 対応づけの値を検査しない validate は、Raises が無いのに NameMapping の TypeError・ValueError になる(findings4 の J1)。
KNOWN_VALIDATE = {}
for _name in MAPPING_NAMES:
    KNOWN_VALIDATE.update(_known("invalid", _name, MAPPING_INVALID[_name], "Raises が無いのに TypeError・ValueError になる(対応づけの値の誤り)"))
#: apply の Raises は ValueError だけで、対応づけの型の誤りは Raises に無い TypeError になる(findings4 の J1)。
KNOWN_APPLY = {}
for _name in MAPPING_NAMES:
    _values = [value for value in MAPPING_INVALID[_name] if value not in ([("root",)], [("", "x")])]
    KNOWN_APPLY.update(_known("invalid", _name, _values, "Raises に無い TypeError(対応づけの型の誤り)"))
#: パスに str・PathLike でない値を渡すと、Raises に無い TypeError になる(findings4 の J2)。
KNOWN_PATH = _known("invalid", "path", (None, 1.5), "Raises に無い TypeError(パスでない値)")


class _TempFolderCase(ArgumentSweepCase):
    """``__tests__/_output/temp/`` に、テストごとの一時フォルダーを作る。"""

    def setUp(self):
        super().setUp()
        self.folder = TEMP / ("argumentSweep_" + self.ns)
        self.folder.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(str(self.folder), ignore_errors=True)
        super().tearDown()


METHODS = (
    Method(
        "validate",
        _build,
        values=MAPPING_VALUES,
        replace=MAPPING_NAMES,
        invalid=MAPPING_INVALID,
        expect=_expect_validate,
        writes=False,
        known=KNOWN_VALIDATE,
        limit=60,
    ),
    Method("apply", _build, values=MAPPING_VALUES, replace=MAPPING_NAMES, invalid=MAPPING_INVALID, expect=_expect_apply, known=KNOWN_APPLY, limit=60),
    Method(
        "save",
        _build,
        args=(Lazy(lambda case: str(case.folder / "pose.json"), "'<str のパス>'"),),
        values={"path": _save_paths()},
        replace=("path",),
        invalid={"path": (None, 1.5, Lazy(lambda case: str(case.folder), "'<フォルダー>'"))},
        expect=_expect_save,
        known=KNOWN_PATH,
    ),
    Method(
        "load",
        _loader,
        args=(Lazy(lambda case: str(case.folder / "pose.json"), "'<str のパス>'"),),
        values={
            "path": (
                Lazy(lambda case: str(case.folder / "pose.json"), "'<str のパス>'"),
                Lazy(lambda case: case.folder / "pose.json", "<Path>"),
                Lazy(lambda case: _PathLike(case.folder / "pose.json"), "<PathLike>"),
            )
        },
        replace=("path",),
        invalid={
            "path": (
                None,
                1.5,
                Lazy(lambda case: str(case.folder / "none.json"), "'<無いファイル>'"),
                Lazy(lambda case: str(case.folder / "wrong.json"), "'<形式名の違うファイル>'"),
                Lazy(lambda case: str(case.folder / "broken.json"), "'<壊れたファイル>'"),
                Lazy(lambda case: str(case.folder), "'<フォルダー>'"),
            )
        },
        expect=_expect_load,
        writes=False,
        known=KNOWN_PATH,
    ),
    Method(
        "warn",
        _report,
        args=("PoseSnapshot",),
        values={"label": ("PoseSnapshot", "", "日本語")},
        invalid={"label": (None, 1.5)},
        expect=_expect_warn,
        writes=False,
        known=_known("invalid", "label", (None, 1.5), "文字列でない label を受け付ける(Raises が無い)"),
    ),
)


class SnapshotArgumentSweepTest(_TempFolderCase):
    """Snapshot(基底)と ValidationReport の公開メソッドの引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
