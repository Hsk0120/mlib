"""Referenceのメソッドの引数を、表から網羅して確かめる(段1〜3)。

表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
参照するファイルは ``__tests__/_output/`` の下へクラスで1回だけ書き、終わったら消す(シーンは新しくしない)。
"""

import inspect
import pathlib
import shutil
import sys
import unittest
import uuid

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import DELETED_NODE, MISSING_NAME, Lazy, Method

from mlib.nodes import Reference

#: getEdits の what と cmds.referenceQuery のフラグ。
EDIT_FLAGS = {"string": "editStrings", "node": "editNodes", "attr": "editAttrs"}
#: 参照するファイルの置き場(クラスの setUpClass で作る)。
_folder = {}


def _write_files():
    """子・親(子を入れ子で参照する)・置き換え用の3つの mayaAscii を書き、フォルダーを返す。"""
    folder = pathlib.Path(inspect.getfile(ArgumentSweepCase)).resolve().parent.parent / "_output" / ("argumentSweepReference_" + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    header = '//Maya ASCII 2022 scene\nrequires maya "2022";\n'
    child = folder / "child.ma"
    child.write_text(header + 'createNode transform -n "box";\ncreateNode locator -n "boxShape" -p "box";\n', encoding="utf-8")
    (folder / "parent.ma").write_text(header + f'file -r -ns "inner" -rfn "innerRN" "{child.as_posix()}";\ncreateNode transform -n "top";\n', encoding="utf-8")
    (folder / "other.ma").write_text(header + 'createNode transform -n "other";\n', encoding="utf-8")
    return folder


def _path(name):
    return (_folder["path"] / name).as_posix()


def _make_scene(case):
    """親(``outer``。子 ``inner`` を入れ子で参照)と子のもう1つの参照(``copy``)を作り、Editを2つ残す。

    Returns:
        dict[str, str]: ``outer``・``inner``・``copy`` の referenceノードの名前。
    """
    cmds.file(_path("parent.ma"), reference=True, namespace=case.name("outer"))
    cmds.file(_path("child.ma"), reference=True, namespace=case.name("copy"))
    top = case.name("outer:top")
    cmds.setAttr(top + ".translateX", 2.0)
    cmds.connectAttr(top + ".translateX", top + ".translateY")
    return {"outer": case.name("outerRN"), "inner": case.name("outer:innerRN"), "copy": case.name("copyRN")}


def _setup(kind, unload=False):
    def setup(case):
        names = _make_scene(case)
        if unload:
            cmds.file(unloadReference=names[kind])
        return Reference(names[kind])

    setup.__name__ = f"_make_{kind}"
    return setup


def _reference_names(case):
    return sorted(name for name in cmds.ls(type="reference") or [] if name.startswith(case.ns + ":"))


def _state(case, target):
    """名前空間のノード・値・接続に加え、参照ごとのロード・ロック・ファイル・Editと、入れ子の名前空間のノードを比べる。"""
    references = []
    for name in _reference_names(case):
        try:
            references.append(
                (
                    name,
                    cmds.referenceQuery(name, isLoaded=True),
                    cmds.getAttr(name + ".locked"),
                    cmds.referenceQuery(name, filename=True),
                    sorted(cmds.referenceQuery(name, editStrings=True, successfulEdits=True, failedEdits=True) or []),
                )
            )
        except RuntimeError:
            references.append((name, None))
    nodes = sorted(cmds.ls(case.ns + ":*", recursive=True, long=True) or [])
    return [*case.sceneState(), references, nodes]


def _expect_locked(case, call):
    case.assertIsNone(call.result)
    name = call.target.getName()
    case.assertEqual(cmds.getAttr(name + ".locked"), call.kwargs.get("state", True))
    case.assertEqual(cmds.file(cmds.referenceQuery(name, filename=True), query=True, lockReference=True), call.kwargs.get("state", True))


def _edits(name, command=None):
    flags = {"editCommand": command} if command else {}
    return cmds.referenceQuery(name, editStrings=True, successfulEdits=True, failedEdits=True, **flags) or []


def _expect_cleaned(case, call):
    case.assertIsNone(call.result)
    case.assertEqual(_edits(call.target.getName(), call.kwargs.get("editCommand")), [])


def _expect_filename(case, call):
    flags = {"unresolvedName": not call.kwargs.get("resolved", True), "withoutCopyNumber": not call.kwargs.get("withCopyNumber", False)}
    case.assertEqual(call.result, cmds.referenceQuery(call.target.getName(), filename=True, **flags))


def _expect_loaded(case, call):
    case.assertIsNone(call.result)
    case.assertEqual(cmds.referenceQuery(call.target.getName(), isLoaded=True), call.kwargs.get("state", True))


def _expect_parent(case, call):
    name = call.target.getName()
    flags = {"topReference": True} if call.kwargs.get("root") else {"parent": True}
    expected = cmds.referenceQuery(name, referenceNode=True, **flags)
    case.assertEqual(None if call.result is None else call.result.getName(), expected)


def _expect_edits(case, call):
    kwargs = call.kwargs
    flags = {EDIT_FLAGS[kwargs.get("what", "string")]: True}
    if kwargs.get("editCommand") is not None:
        flags["editCommand"] = kwargs["editCommand"]
    if kwargs.get("onReferenceNode") is not None:
        flags["onReferenceNode"] = str(kwargs["onReferenceNode"])
    expected = cmds.referenceQuery(call.target.getName(), successfulEdits=kwargs.get("successful", True), failedEdits=kwargs.get("failed", False), **flags)
    case.assertEqual(call.result, expected or [])


def _expect_removed_edits(case, call):
    """successful=True なら、指定したコマンドの成功した Edit が残らない。"""
    case.assertIsNone(call.result)
    if call.kwargs.get("successful", True):
        case.assertEqual(_edits(call.target.getName(), call.kwargs.get("editCommand")), [])


def _expect_replaced(case, call):
    case.assertIsNone(call.result)
    expected = pathlib.Path(str(call.kwargs["path"])).resolve().as_posix()
    actual = cmds.referenceQuery(call.target.getName(), filename=True, withoutCopyNumber=True)
    case.assertEqual(pathlib.Path(actual).resolve().as_posix().lower(), expected.lower())


def _expect_imported(case, call):
    case.assertFalse(cmds.objExists(case.name("copyRN")))
    case.assertTrue(call.result)
    case.assertTrue(all(node.isValid() and not cmds.referenceQuery(node.getName(), isNodeReferenced=True) for node in call.result))
    case.assertEqual(cmds.namespace(exists=case.name("copy")), not call.kwargs.get("removeNamespace", False))


def _plural_references(case):
    """段の最初に作った参照(outer・copy)を、複数形と単数の並びにする。"""
    singles = [Reference(case.name("outerRN")), Reference(case.name("copyRN"))]
    return mlib.Nodes(singles), singles


def _reference(kind, wrap=False):
    def make(case):
        name = case.name({"outer": "outerRN", "inner": "outer:innerRN", "copy": "copyRN"}[kind])
        return Reference(name) if wrap else name

    return Lazy(make, f"<{kind}RN{'のReference' if wrap else ''}>")


#: Mayaの編集コマンド(cleanEdits が受け付けるもの)。
CLEAN_COMMANDS = (None, "setAttr", "addAttr", "deleteAttr", "connectAttr", "disconnectAttr", "parent")
#: getEdits が受け付ける編集コマンド。
EDIT_COMMANDS = (None, "addAttr", "connectAttr", "deleteAttr", "disconnectAttr", "parent", "setAttr", "lock", "unlock")
#: 段2の編集コマンドの誤った値。
COMMAND_INVALID = (1.5, "", "argumentSweepNoSuchCommand")
#: 置き換えるファイルの候補(文字列・Path・区切りが逆斜線・同じファイル)。
PATH_VALUES = (
    Lazy(lambda case: _path("other.ma"), "<other.ma>"),
    Lazy(lambda case: _folder["path"] / "other.ma", "<other.maのPath>"),
    Lazy(lambda case: str(_folder["path"] / "other.ma").replace("/", "\\"), "<other.maの逆斜線>"),
    Lazy(lambda case: _path("child.ma"), "<child.ma>"),
)
#: 段2の置き換えるファイルの誤った値(空・無いファイル・数・None・削除済みのノード)。
PATH_INVALID = ("", Lazy(lambda case: _path("argumentSweepMissing.ma"), "<無いファイル>"), 1.5, None, DELETED_NODE)


#: 引数の無いメソッドを確かめるときに、参照を作る表の1行。
_NO_ARGS = Method("isLoaded", _setup("outer"))

#: 正しい呼び方の表。
METHODS = (
    Method("mfn", _setup("outer"), writes=False),
    Method("isReferenceLocked", _setup("outer")),
    Method("setReferenceLocked", _setup("outer"), expect=_expect_locked, state=_state, undoable=False),
    Method(
        "cleanEdits",
        _setup("outer", unload=True),
        values={"editCommand": CLEAN_COMMANDS},
        invalid={"editCommand": (1.5, "", "lock")},
        expect=_expect_cleaned,
        state=_state,
        undoable=False,
    ),
    Method("getFilename", _setup("copy"), expect=_expect_filename, plural=_plural_references),
    Method("getAssociatedNamespace", _setup("outer")),
    Method("getCopyNumber", _setup("copy")),
    Method("getCopyNumbers", _setup("copy")),
    Method("isUsingNamespaces", _setup("outer")),
    Method("isDeferred", _setup("outer")),
    Method("isLoaded", _setup("outer")),
    Method("setLoaded", _setup("outer"), expect=_expect_loaded, state=_state, undoable=False),
    Method("getNodes", _setup("outer")),
    Method("getParentReference", _setup("inner"), expect=_expect_parent),
    Method("getChildren", _setup("outer")),
    Method("isTopLevel", _setup("outer")),
    Method(
        "getEdits",
        _setup("outer"),
        values={"editCommand": EDIT_COMMANDS, "onReferenceNode": (_reference("outer"), _reference("outer", wrap=True), _reference("inner"))},
        invalid={
            "editCommand": COMMAND_INVALID,
            "onReferenceNode": (Lazy(lambda case: case.name("outer:top"), "<outer:top>"), DELETED_NODE, MISSING_NAME, 1.5),
        },
        expect=_expect_edits,
        limit=100,
    ),
    Method(
        "removeEdits",
        _setup("outer"),
        values={"editCommand": ("setAttr", "connectAttr", "parent")},
        invalid={"editCommand": (1.5, "")},
        expect=_expect_removed_edits,
        state=_state,
        # Undo に記録しない操作(docstring)なので、組ごとの作り直しと Undo の性質は確かめない。
        writes=False,
        limit=20,
    ),
    Method(
        "replaceFile",
        _setup("copy"),
        args=(PATH_VALUES[0],),
        values={"path": PATH_VALUES},
        replace=("path",),
        invalid={"path": PATH_INVALID},
        expect=_expect_replaced,
        state=_state,
        undoable=False,
    ),
    # ファイルの操作は Undo に記録しない(docstring)。
    Method("importContents", _setup("copy"), expect=_expect_imported, state=_state, undoable=False),
    Method("removeReference", _setup("copy"), state=_state, undoable=False),
)


class ReferenceArgumentSweepTest(ArgumentSweepCase):
    """Referenceのメソッドの引数を網羅する。"""

    METHODS = METHODS

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _folder["path"] = _write_files()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_folder.pop("path"), ignore_errors=True)
        super().tearDownClass()

    def test_noArguments(self):
        """引数の無いメソッドを1回ずつ呼び、cmds で読み直して確かめる(表は引数の無いメソッドを呼ばないため)。"""
        names = {kind: self.name(text) for kind, text in (("outer", "outerRN"), ("inner", "outer:innerRN"), ("copy", "copyRN"))}
        self.fresh(_NO_ARGS)
        outer, inner, copy = (Reference(names[kind]) for kind in ("outer", "inner", "copy"))
        filename = cmds.referenceQuery(names["copy"], filename=True)
        checks = (
            ("mfn", lambda: outer.mfn().name(), names["outer"]),
            ("isReferenceLocked", outer.isReferenceLocked, bool(cmds.file(cmds.referenceQuery(names["outer"], filename=True), query=True, lockReference=True))),
            ("getAssociatedNamespace", lambda: outer.getAssociatedNamespace().name.strip(":"), cmds.referenceQuery(names["outer"], namespace=True).strip(":")),
            ("getCopyNumber", copy.getCopyNumber, int(filename.rsplit("{", 1)[1].rstrip("}")) if "{" in filename else 0),
            ("getCopyNumbers", copy.getCopyNumbers, [int(value) for value in cmds.file(filename.split("{")[0], query=True, copyNumberList=True)]),
            ("isUsingNamespaces", outer.isUsingNamespaces, True),
            ("isDeferred", outer.isDeferred, bool(cmds.file(cmds.referenceQuery(names["outer"], filename=True), query=True, deferReference=True))),
            ("isLoaded", outer.isLoaded, cmds.referenceQuery(names["outer"], isLoaded=True)),
            (
                "getNodes",
                lambda: sorted(node.getName(full=True) for node in outer.getNodes()),
                sorted(cmds.ls(cmds.referenceQuery(names["outer"], nodes=True, dagPath=True), long=True)),
            ),
            ("getChildren", lambda: [node.getName() for node in outer.getChildren()], [names["inner"]]),
            ("isTopLevel", lambda: (outer.isTopLevel(), inner.isTopLevel()), (True, False)),
        )
        for name, call, expected in checks:
            with self.subTest(method=name):
                self.assertEqual(call(), expected)
        with self.subTest(method="cleanEdits(ロード中)"), self.assertRaises(RuntimeError):
            outer.cleanEdits()
        with self.subTest(method="setReferenceLocked(入れ子)"), self.assertRaises(NotImplementedError):
            inner.setReferenceLocked(True)
        cmds.file(unloadReference=names["copy"])
        with self.subTest(method="getNodes(アンロード)"), self.assertRaises(RuntimeError):
            copy.getNodes()
        with self.subTest(method="importContents(アンロード)"), self.assertRaises(RuntimeError):
            copy.importContents()
        with self.subTest(method="removeReference"):
            self.assertIsNone(copy.removeReference())
            self.assertFalse(cmds.objExists(names["copy"]))

    def fresh(self, method):
        self._remove_references()
        return super().fresh(method)

    def tearDown(self):
        self._remove_references()
        super().tearDown()

    def _remove_references(self):
        """名前空間の参照を外す(名前空間ごとの削除は、ロックされた referenceノードで止まるため)。"""
        for name in _reference_names(self):
            if cmds.objExists(name) and not cmds.referenceQuery(name, isNodeReferenced=True):
                cmds.file(removeReference=True, referenceNode=name)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
