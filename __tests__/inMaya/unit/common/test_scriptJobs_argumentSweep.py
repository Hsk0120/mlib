"""ScriptJobs の公開メソッドの引数を、表から網羅して確かめる(段1〜4)。

scriptJob は Maya の GUI でしか登録できない(バッチでは cmds.scriptJob が ID を返さない)。
バッチ(mayapy)では ``test_scriptJob.py`` と同じ代役(:class:`_FakeScriptJob`)で cmds.scriptJob を置き換え、
GUI では実際に登録して、cmds.scriptJob(exists=ID) と突き合わせる。
登録はシーンを変えないので、Undo の性質は当てはまらない。登録した監視は、各呼び出しの後で解除する。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import sys
import unittest
from unittest import mock

import maya.cmds as cmds

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

import mlib.common.scriptJob as script_job_module
from mlib.common import ScriptJob, ScriptJobs

#: バッチ(mayapy)か。バッチでは cmds.scriptJob を代役に置き換える。
BATCH = bool(cmds.about(batch=True))

#: 表の setup と呼び出しが作ったグループ(呼び出しごとに監視を解除する)。
_groups = []


class _FakeScriptJob:
    """cmds.scriptJob の代役。登録の引数を記録し、ID・exists・kill に答える。"""

    def __init__(self):
        self.registered = []
        self.alive = set()

    def __call__(self, **kwargs):
        if "exists" in kwargs:
            return kwargs["exists"] in self.alive
        if "kill" in kwargs:
            self.alive.discard(kwargs["kill"])
            return None
        self.registered.append(kwargs)
        job_id = 1000 + len(self.registered)
        self.alive.add(job_id)
        return job_id


class _BatchStub:
    """バッチでも登録の処理まで進めるための、Environment の代役(isBatch だけを持つ)。"""

    @staticmethod
    def isBatch():
        return False


def _construct():
    """ScriptJobs を作り、後で監視を解除できるよう覚えておく(``__init__`` の引数・docstring を持つ関数として表へ渡す)。"""
    group = ScriptJobs()
    _groups.append(group)
    return group


_signature = inspect.signature(ScriptJobs.__init__)
_construct.__signature__ = _signature.replace(parameters=list(_signature.parameters.values())[1:])
_construct.__doc__ = ScriptJobs.__init__.__doc__


def _noop():
    """登録に渡すだけの処理。"""


def _release(case, target):
    """表の setup と呼び出しが作ったグループの監視を、すべて解除する。"""
    while _groups:
        _groups.pop().stop()


def _empty(case):
    """監視を持たないグループを返す(監視するアトリビュートを持つ transform も作る)。"""
    _release(case, None)
    case.make("transform", "watched")
    return _construct()


def _group(case):
    """イベントとアトリビュートの監視を1つずつ持つグループを返す。持たせた監視は ``sweepJobs`` に覚える。"""
    group = _empty(case)
    group.sweepJobs = [
        group.add("event", event="SelectionChanged", callback=_noop),
        group.add("attribute", attribute=case.name("watched.translateX"), callback=_noop),
    ]
    return group


def _registered(job):
    """Maya(バッチでは代役)に、この監視が登録されているか。"""
    return bool(script_job_module.cmds.scriptJob(exists=job.id))


def _expect_init(case, call):
    """作ったばかりのグループは監視を持たず、exists は False。"""
    case.assertIsInstance(call.result, ScriptJobs)
    case.assertFalse(call.result.exists())
    case.assertIsNone(call.result.stop())


def _expect_add(case, call):
    """登録した監視を返し、同じキーでもう一度呼ぶと、登録し直さずに同じ監視を返す。"""
    job = call.result
    case.assertIsInstance(job, ScriptJob)
    case.assertTrue(_registered(job))
    case.assertTrue(call.target.exists())
    case.assertIs(call.target.add(call.kwargs["key"], event="timeChanged", callback=_noop), job)


def _expect_exists(case, call):
    jobs = getattr(call.target, "sweepJobs", [])
    case.assertIs(call.result, bool(jobs) and all(_registered(job) for job in jobs))


def _expect_stopped(case, call):
    """グループの監視はすべて Maya から消え、exists は False。もう一度呼んでも何もしない。"""
    for job in getattr(call.target, "sweepJobs", []):
        case.assertFalse(_registered(job))
    case.assertFalse(call.target.exists())
    case.assertIsNone(call.target.stop())


def _expect_stop(case, call):
    case.assertIsNone(call.result)
    _expect_stopped(case, call)


WATCHED = Lazy(lambda case: case.name("watched.translateX"), "'<名前>.translateX'")
#: add の登録の指定(ScriptJob へ渡すキーワード引数)。
OPTIONS = (
    {"event": "SelectionChanged", "callback": _noop},
    {"event": "timeChanged", "callback": print, "killWithScene": True, "compressUndo": True, "runOnce": True, "protected": True},
    {"attribute": WATCHED, "callback": _noop, "allChildren": True},
    {"uiDeleted": "mlibSweepNoSuchWindow", "callback": _noop},
)
#: add の登録の指定の誤り(ScriptJob が TypeError・ValueError にする)。
OPTIONS_INVALID = (
    {"event": "SelectionChanged", "callback": "print"},
    {"callback": _noop},
    {"event": "SelectionChanged", "attribute": WATCHED, "callback": _noop},
    {"event": "SelectionChanged", "callback": _noop, "runOnce": 1},
)

#: 2回の登録は別の ID の別の監視になるので、戻り値どうしを比べられない。
SKIP_ADD = {"positional": "呼ぶたびに別の ID の監視を登録するので、2回の戻り値を比べられない"}

METHODS = (
    Method("__init__", _empty, function=_construct, expect=_expect_init, reset=_release, writes=False),
    Method(
        "add",
        _empty,
        args=("key",),
        kwargs={"event": "SelectionChanged", "callback": _noop},
        values={"key": ("key", "", 1, ("a", 1), None, 1.5), "**": OPTIONS},
        replace=("key",),
        invalid={"key": ([], {}), "**": OPTIONS_INVALID},
        expect=_expect_add,
        reset=_release,
        undoable=False,
        skipCalling=SKIP_ADD,
    ),
    Method("exists", _group, expect=_expect_exists, writes=False),
    Method("exists", _empty, expect=_expect_exists, writes=False, variant="empty"),
    Method("stop", _group, expect=_expect_stop, undoable=False),
    Method("stop", _empty, expect=_expect_stop, undoable=False, variant="empty"),
    Method("temporary", _group, expect=_expect_stopped, context=True, undoable=False),
)


class ScriptJobsArgumentSweepTest(ArgumentSweepCase):
    """ScriptJobs の公開メソッドの引数を網羅する。"""

    METHODS = METHODS

    def setUp(self):
        super().setUp()
        self.fake = _FakeScriptJob()
        if BATCH:
            for patcher in (mock.patch.object(script_job_module, "Environment", _BatchStub), mock.patch.object(script_job_module.cmds, "scriptJob", self.fake)):
                patcher.start()
                self.addCleanup(patcher.stop)

    def tearDown(self):
        _release(self, None)
        super().tearDown()

    def test_temporary_yields_itself_and_stops_jobs_added_inside(self):
        """temporary は自身を渡し、with の中で足した監視も、抜けたときに解除する。入れ子は RuntimeError。"""
        group = _group(self)
        with group.temporary() as active:
            self.assertIs(active, group)
            inside = group.add("inside", event="timeChanged", callback=_noop)
            self.assertTrue(_registered(inside))
            with self.assertRaises(RuntimeError), group.temporary():
                pass
        self.assertFalse(_registered(inside))
        self.assertFalse(group.exists())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
