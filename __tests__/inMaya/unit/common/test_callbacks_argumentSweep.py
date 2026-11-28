"""Callbacks の公開メソッドの引数を、表から網羅して確かめる(段1〜3)。

登録したコールバックが呼ばれることを、現在時刻の変更(timeChange・timeChanged)・アトリビュートの変更で起こして確かめ、
時刻の単位は om2 の ``MTime`` で換算して突き合わせる。シーンのイベントは識別子が返ることだけを見る。
登録はシーンを変えないので、Undo の性質は当てはまらない。登録したものは、各呼び出しの後とテストの後で解除する。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import sys
import unittest

import maya.api.OpenMaya as om2
import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.common.callbacks import Callbacks

_calls = []


def _record(*args):
    _calls.append(args)
    return True


def _callbacks(case):
    case.release()
    case.make("transform", "watched")
    callbacks = Callbacks()
    case.groups.append(callbacks)
    _calls.clear()
    return callbacks


def _registered(case):
    """timeChanged へ1つ登録した Callbacks。"""
    callbacks = _callbacks(case)
    callbacks.addEventCallback("timeChanged", _record)
    return callbacks


def _poke_time():
    """現在時刻を動かして戻す(timeChanged を起こす)。"""
    frame = cmds.currentTime(query=True)
    cmds.currentTime(frame + 1.0)
    cmds.currentTime(frame)


def _expect_new(case, call):
    """作った直後は何も登録していない(時刻を変えても呼ばれず、remove も何もせずに終わる)。"""
    case.assertIsInstance(call.result, Callbacks)
    _calls.clear()
    _poke_time()
    case.assertFalse(_calls)
    case.assertIsNone(call.result.remove())


def _expect_removed(case, call):
    """解除した後は、時刻を変えても呼ばれない。対象は使い回すので、次の呼び出しのために登録し直す。"""
    case.assertIsNone(call.result)
    _calls.clear()
    _poke_time()
    case.assertFalse(_calls)
    call.target.addEventCallback("timeChanged", _record)
    _poke_time()
    case.assertTrue(_calls)
    _calls.clear()


def _expect_id(case, call):
    case.assertIsInstance(call.result, int)
    case.assertNotIsInstance(call.result, bool)


def _then_remove(expect):
    """確かめた後に、対象の Callbacks の登録をすべて解除する(読むだけの表は対象を使い回すため)。"""

    def run(case, call):
        try:
            expect(case, call)
        finally:
            call.target.remove()
            _calls.clear()

    return run


def _expect_time(case, call):
    """現在時刻を変えると、timeUnit の単位の時刻で呼ばれる。"""
    _expect_id(case, call)
    _calls.clear()
    frame = cmds.currentTime(query=True)
    cmds.currentTime(frame + 3.0)
    cmds.currentTime(frame)
    unit = call.kwargs.get("timeUnit", "frame")
    expected = frame + 3.0 if unit == "frame" else om2.MTime(frame + 3.0, om2.MTime.uiUnit()).asUnits(om2.MTime.kSeconds)
    case.assertTrue(_calls)
    case.assertAlmostEqual(_calls[0][0], expected, places=6)


def _expect_event(case, call):
    _expect_id(case, call)
    if call.kwargs["event"] == "timeChanged" and call.kwargs["callback"] is not print:
        _calls.clear()
        frame = cmds.currentTime(query=True)
        cmds.currentTime(frame + 1.0)
        cmds.currentTime(frame)
        case.assertTrue(_calls)


def _expect_attribute(case, call):
    """見張るノードのアトリビュートを変えると、(message, Plug) で呼ばれる。"""
    _expect_id(case, call)
    _calls.clear()
    cmds.setAttr(case.name("watched.translateX"), 2.0)
    case.assertTrue(_calls)
    message, plug = _calls[-1]
    case.assertTrue(message & om2.MNodeMessage.kAttributeSet)
    case.assertEqual(str(plug).rpartition(".")[2], "translateX")


def _mobject(case):
    selection = om2.MSelectionList()
    selection.add(case.name("watched"))
    return selection.getDependNode(0)


#: このMayaで登録できるシーンのイベント(一部の版にしか無いものは除く)。
SCENE_EVENTS = (
    "beforeNew",
    "afterNew",
    "afterOpen",
    "beforeSave",
    "afterImport",
    "beforeReference",
    "afterCreateReference",
    "sceneUpdate",
    "mayaExiting",
    "beforeNewCheck",
    "beforeSaveCheck",
    "beforeOpenCheck",
    "beforeImportCheck",
    "beforeExportCheck",
    "beforeCreateReferenceCheck",
    "beforeLoadReferenceCheck",
)
CALLABLES = (_record, lambda *args: _record(*args), print)
CALLABLE_INVALID = ("print", None, 1.5)

#: 登録の戻り値は、呼ぶたびに別の値になるコールバックの ID。2回の戻り値は比べられない。
SKIP_ID = dict.fromkeys(("defaults", "positional"), "戻り値は登録のたびに変わるコールバックの ID")

METHODS = (
    Method("__init__", _callbacks, function=Callbacks, expect=_expect_new, writes=False),
    Method("remove", _registered, expect=_expect_removed, writes=False),
    Method(
        "addSceneCallback",
        _callbacks,
        skipCalling=SKIP_ID,
        args=("afterNew", _record),
        values={"event": SCENE_EVENTS, "callback": CALLABLES},
        replace=("event", "callback"),
        invalid={"event": ("AfterNew", "afterNewCheck", "", "nowhere", 1.5, None), "callback": CALLABLE_INVALID},
        expect=_then_remove(_expect_id),
        writes=False,
    ),
    Method(
        "addEventCallback",
        _callbacks,
        skipCalling=SKIP_ID,
        args=("timeChanged", _record),
        values={"event": ("timeChanged", "SelectionChanged", "idle", "NewSceneOpened"), "callback": CALLABLES},
        replace=("event", "callback"),
        invalid={"event": ("timechanged", "", "nowhere", 1.5, None), "callback": CALLABLE_INVALID},
        expect=_then_remove(_expect_event),
        writes=False,
    ),
    Method(
        "addTimeChangeCallback",
        _callbacks,
        skipCalling=SKIP_ID,
        args=(_record,),
        values={"callback": (_record, lambda *args: _record(*args)), "timeUnit": ("frame", "sec")},
        replace=("callback", "timeUnit"),
        invalid={"callback": CALLABLE_INVALID, "timeUnit": ("frames ", "deg", "", 1.5, None)},
        expect=_then_remove(_expect_time),
        writes=False,
    ),
    Method(
        "addAttributeChangedCallback",
        _callbacks,
        skipCalling=SKIP_ID,
        args=(Lazy(lambda case: case.name("watched"), "'<名前>'"), _record),
        values={
            "node": (
                Lazy(lambda case: case.name("watched"), "'<名前>'"),
                Lazy(lambda case: mlib.getNode(case.name("watched")), "<Node>"),
                Lazy(_mobject, "<MObject>"),
            ),
            "callback": (_record, lambda *args: _record(*args)),
        },
        replace=("node", "callback"),
        invalid={
            "node": (None, 1.5, Lazy(lambda case: case.name("nowhere"), "'<存在しない名前>'"), Lazy(lambda case: case.deletedNode(), "<削除済みのノード>")),
            "callback": CALLABLE_INVALID,
        },
        expect=_then_remove(_expect_attribute),
        writes=False,
    ),
)


class CallbacksArgumentSweepTest(ArgumentSweepCase):
    """Callbacks の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        self.groups = []

    def tearDown(self):
        self.release()
        super().tearDown()

    def release(self):
        """これまでに作った Callbacks の登録を解除する。"""
        while self.groups:
            self.groups.pop().remove()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
