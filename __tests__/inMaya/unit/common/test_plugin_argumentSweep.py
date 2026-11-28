"""Plugin の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

ロード・アンロードは小さい標準のプラグイン(quatNodes)で行い、cmds.pluginInfo・cmds.unknownPlugin で
読み直して突き合わせる。テストの後は、テストの前のロードの状態へ戻す。
プラグインのロードは Undo に残らない(シーンの状態も変えない)ので、Undo の性質は当てはまらない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Method

from mlib.common.plugin import Plugin
from mlib.common.version import Version

NAME = "quatNodes"
FAKE = ("mlibSweepUnknownA", "mlibSweepUnknownB")


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


def _loaded(case):
    if not cmds.pluginInfo(NAME, query=True, loaded=True):
        cmds.loadPlugin(NAME, quiet=True)
    return Plugin(NAME)


def _unloaded(case):
    if cmds.pluginInfo(NAME, query=True, loaded=True):
        cmds.unloadPlugin(NAME)
    return Plugin(NAME)


def _unknown(case):
    """未知のプラグインを2つ記録し、クラスメソッドを呼ぶ対象を返す。"""
    for name in FAKE:
        cmds.requires(name, "1.0")
    return _host("Plugin", removeUnknown=Plugin.removeUnknown, ensureNodePlugin=Plugin.ensureNodePlugin)


def _registered(case):
    """ロード済みのプラグイン(登録されている)。"""
    return _loaded(case)


def _never(case):
    """Maya が知らない名前のプラグイン。"""
    return Plugin("mlibSweepNoSuchPlugin")


def _unknown_nodes(case):
    """型が分からないノード(unknown・unknownDag・unknownTransform)を、テストの名前空間に作る。"""
    for kind in ("unknown", "unknownDag", "unknownTransform"):
        cmds.createNode(kind, name=case.name("lost_" + kind), skipSelect=True)
    return Plugin(NAME)


def _expect_loaded_list(case, call):
    case.assertTrue(all(type(item) is Plugin for item in call.result))
    case.assertEqual([item.name for item in call.result], cmds.pluginInfo(query=True, listPlugins=True) or [])
    case.assertIn(NAME, [item.name for item in call.result])


def _expect_list_unknown(case, call):
    case.assertIs(type(call.result), list)
    case.assertEqual(call.result, cmds.unknownPlugin(query=True, list=True) or [])
    case.assertTrue(set(FAKE) <= set(call.result))


def _expect_unknown_nodes(case, call):
    expected = cmds.ls(type=["unknown", "unknownDag", "unknownTransform"], long=True) or []
    case.assertEqual([node.getName(full=True) for node in call.result], expected)
    case.assertGreaterEqual(len(expected), 3)


def _expect_is_registered(case, call):
    case.assertIs(call.result, bool(cmds.pluginInfo(call.target.name, query=True, registered=True)))


def _expect_is_loaded(case, call):
    case.assertIs(call.result, bool(cmds.pluginInfo(call.target.name, query=True, loaded=True)))


def _expect_path(case, call):
    name = call.target.name
    registered = bool(cmds.pluginInfo(name, query=True, registered=True))
    case.assertEqual(call.result, cmds.pluginInfo(name, query=True, path=True) if registered else None)


def _state(case, target):
    return [case.sceneState(), bool(cmds.pluginInfo(NAME, query=True, loaded=True)), sorted(cmds.unknownPlugin(query=True, list=True) or [])]


def _expect_load(case, call):
    case.assertIsNone(call.result)
    case.assertTrue(cmds.pluginInfo(NAME, query=True, loaded=True))


def _expect_unload(case, call):
    case.assertIsNone(call.result)
    case.assertFalse(cmds.pluginInfo(NAME, query=True, loaded=True))


def _expect_version(case, call):
    raw = cmds.pluginInfo(NAME, query=True, version=True)
    if call.kwargs.get("text"):
        case.assertEqual(call.result, raw)
    else:
        case.assertEqual(call.result, Version(raw))


def _expect_remove(case, call):
    names = call.kwargs.get("names")
    removed = list(FAKE) if names is None else ([names] if isinstance(names, str) else list(names))
    unknown = cmds.unknownPlugin(query=True, list=True) or []
    case.assertFalse(set(removed) & set(unknown))
    if names is not None:
        case.assertEqual(call.result, removed)
        case.assertEqual(set(FAKE) - set(removed), set(unknown) & set(FAKE))


def _expect_ensure(case, call):
    case.assertIsNone(call.result)
    if call.kwargs["type"].startswith("HIK"):
        case.assertTrue(cmds.pluginInfo("mayaHIK", query=True, loaded=True))


METHODS = (
    Method("loaded", _loaded, function=Plugin.loaded, expect=_expect_loaded_list, state=_state, writes=False),
    Method("listUnknown", _unknown, function=Plugin.listUnknown, expect=_expect_list_unknown, state=_state),
    Method("listUnknownNodes", _unknown_nodes, function=Plugin.listUnknownNodes, expect=_expect_unknown_nodes, state=_state),
    Method("isRegistered", _registered, expect=_expect_is_registered, state=_state),
    Method("isRegistered", _never, variant="never", expect=_expect_is_registered, state=_state),
    Method("isLoaded", _loaded, expect=_expect_is_loaded, state=_state),
    Method("isLoaded", _unloaded, variant="unloaded", expect=_expect_is_loaded, state=_state),
    Method("isLoaded", _never, variant="never", expect=_expect_is_loaded, state=_state),
    Method("getPath", _loaded, expect=_expect_path, state=_state),
    Method("getPath", _never, variant="never", expect=_expect_path, state=_state),
    Method("load", _unloaded, invalid={"skipExisting": (1, "yes", None)}, expect=_expect_load, state=_state, undoable=False),
    Method("unload", _loaded, invalid={"force": (1, "yes", None)}, expect=_expect_unload, state=_state, undoable=False),
    Method("getVersion", _loaded, invalid={"text": (1, "yes", None)}, expect=_expect_version, state=_state),
    Method(
        "removeUnknown",
        _unknown,
        skipCalling={"defaults": "names=None の結果は Maya の未知のプラグインの一覧の順で、シーンを作り直すと順が変わる"},
        values={"names": (None, FAKE[0], [FAKE[0]], FAKE, list(FAKE))},
        replace=("names",),
        invalid={"names": ("mlibSweepNotUnknown", [FAKE[0], "mlibSweepNotUnknown"], 1.5, [1.5], {FAKE[0]: 1})},
        expect=_expect_remove,
        state=_state,
        undoable=False,
    ),
    Method(
        "ensureNodePlugin",
        _unknown,
        args=("transform",),
        values={"type": ("transform", "joint", "HIKCharacterNode", "HIKSolverNode", "unknownNodeTypeName")},
        replace=("type",),
        invalid={"type": (1.5, None)},
        expect=_expect_ensure,
        writes=False,
    ),
)


class PluginArgumentSweepTest(ArgumentSweepCase):
    """Plugin の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        self.was_loaded = bool(cmds.pluginInfo(NAME, query=True, loaded=True))

    def tearDown(self):
        loaded = bool(cmds.pluginInfo(NAME, query=True, loaded=True))
        if loaded and not self.was_loaded:
            cmds.unloadPlugin(NAME)
        elif self.was_loaded and not loaded:
            cmds.loadPlugin(NAME, quiet=True)
        unknown = set(cmds.unknownPlugin(query=True, list=True) or []) & set(FAKE)
        for name in unknown:
            cmds.unknownPlugin(name, remove=True)
        super().tearDown()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
