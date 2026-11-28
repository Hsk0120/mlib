"""ScriptJob の公開メソッドの引数を、表から網羅して確かめる(段1〜4)。

scriptJob は Maya の GUI でしか登録できない(バッチでは cmds.scriptJob が ID を返さない)。
バッチ(mayapy)では ``test_scriptJob.py`` と同じ代役(:class:`_FakeScriptJob`)で cmds.scriptJob を置き換え、
引数の検査・Maya へ渡すフラグ・exists・stop を確かめる。GUI では実際に登録し、cmds.scriptJob(exists=ID) と突き合わせる。
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
from mlib.common import ScriptJob

#: バッチ(mayapy)か。バッチでは cmds.scriptJob を代役に置き換える。
BATCH = bool(cmds.about(batch=True))

#: 表の呼び出しが登録した監視(呼び出しごとに解除する)。
_created = []


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


def _construct(**kwargs):
    """ScriptJob を作り、後で解除できるよう覚えておく(``__init__`` の引数・docstring を持つ関数として表へ渡す)。"""
    job = ScriptJob(**kwargs)
    _created.append(job)
    return job


_signature = inspect.signature(ScriptJob.__init__)
_construct.__signature__ = _signature.replace(parameters=list(_signature.parameters.values())[1:])
_construct.__doc__ = ScriptJob.__init__.__doc__


def _noop():
    """登録に渡すだけの処理。"""


def _watched(case):
    """監視するアトリビュートを持つ transform を作る。"""
    return case.make("transform", "watched")


def _job(case):
    """SelectionChanged の監視を1つ登録して返す。"""
    _release(case, None)
    _watched(case)
    return _construct(event="SelectionChanged", callback=_noop)


def _stopped(case):
    """登録してから解除した監視を返す。"""
    job = _job(case)
    job.stop()
    return job


def _release(case, target):
    """表の呼び出しが登録した監視をすべて解除する。"""
    while _created:
        _created.pop().stop()


def _registered(job):
    """Maya(バッチでは代役)に、この監視が登録されているか。"""
    return bool(script_job_module.cmds.scriptJob(exists=job.id))


def _state(case, target):
    """シーンの状態と、表の呼び出しが登録して残っている監視の数。"""
    return [case.sceneState(), len([job for job in _created if _registered(job)])]


def _expect_init(case, call):
    """登録した監視は ID を持ち、Maya に登録されている。バッチでは、Maya へ渡したフラグも確かめる。"""
    job = call.result
    case.assertIsInstance(job, ScriptJob)
    case.assertIsInstance(job.id, int)
    case.assertTrue(job.exists())
    case.assertTrue(_registered(job))
    if not BATCH:
        return
    kwargs = call.kwargs
    options = case.fake.registered[-1]
    case.assertIs(options["killWithScene"], kwargs.get("killWithScene", False))
    case.assertIs(options["compressUndo"], kwargs.get("compressUndo", False))
    if kwargs.get("event") is not None:
        case.assertEqual(options["event"], [kwargs["event"], kwargs["callback"]])
    elif kwargs.get("attribute") is not None:
        case.assertEqual(options["attributeChange"], [mlib.getPlug(kwargs["attribute"])._full_name(), kwargs["callback"]])
    else:
        case.assertEqual(options["uiDeleted"], [kwargs["uiDeleted"], kwargs["callback"]])
    for name in ("allChildren", "runOnce", "protected"):
        case.assertIs(options.get(name, False), kwargs.get(name, False))
    case.assertEqual(options.get("parent"), kwargs.get("parent"))


def _expect_exists(case, call):
    case.assertIs(call.result, _registered(call.target))


def _expect_stop(case, call):
    """解除した監視は Maya から消え、exists は False。もう一度呼んでも何もしない。"""
    case.assertIsNone(call.result)
    case.assertFalse(_registered(call.target))
    case.assertFalse(call.target.exists())
    case.assertIsNone(call.target.stop())


CALLABLES = (_noop, lambda: None, print)
CALLABLE_INVALID = ("print", None, 1.5)
BOOL_INVALID = (1, "yes", None)
BOOL_NAMES = ("killWithScene", "compressUndo", "allChildren", "runOnce", "protected")
#: 監視を持たせるUIの名前。バッチの代役は名前をそのまま受ける(GUI では、無いUIの名前を Maya が拒否して RuntimeError になる)。
UI_NAMES = (None, "mlibSweepNoSuchWindow")
UI_INVALID = ("", 1.5, ["window"])
WATCHED = Lazy(lambda case: case.name("watched.translateX"), "'<名前>.translateX'")
ATTRIBUTES = (
    WATCHED,
    Lazy(lambda case: case.name("watched.translate"), "'<名前>.translate'"),
    Lazy(lambda case: mlib.getPlug(case.name("watched.translateX")), "<Plug>"),
    Lazy(lambda case: mlib.getPlug(case.name("watched.translateX")).mplug(), "<MPlug>"),
)
#: allChildren は attribute と一緒のときだけ使える(event・uiDeleted の行では True も誤り)。
ALL_CHILDREN_INVALID = (True, 1, "yes", None)


def _invalid(**extra):
    """bool の引数・callback・parent の誤った値に、行ごとの値を足した段2の表を返す。"""
    table = dict(dict.fromkeys(BOOL_NAMES, BOOL_INVALID), callback=CALLABLE_INVALID, parent=UI_INVALID)
    table.update(extra)
    return table


#: 2回の登録は別の ID の別の監視になるので、戻り値どうしを比べられない。
SKIP_DEFAULTS = {"defaults": "呼ぶたびに別の ID の監視を登録するので、2回の戻り値を比べられない"}

METHODS = (
    Method(
        "__init__",
        _watched,
        function=_construct,
        kwargs={"event": "SelectionChanged", "callback": _noop},
        values={"event": ("SelectionChanged", "timeChanged", "SceneOpened"), "callback": CALLABLES, "parent": UI_NAMES},
        replace=("event", "callback", "parent"),
        # event を外すと、event・attribute・uiDeleted のどれも指定しない呼び方になる。足すと、2つを指定した呼び方になる。
        invalid=_invalid(event=(None,), attribute=(WATCHED,), uiDeleted=("mlibSweepWindow",), allChildren=ALL_CHILDREN_INVALID),
        expect=_expect_init,
        state=_state,
        reset=_release,
        writes=False,
        variant="event",
        skipCalling=SKIP_DEFAULTS,
    ),
    Method(
        "__init__",
        _watched,
        function=_construct,
        kwargs={"attribute": WATCHED, "callback": _noop},
        values={"attribute": ATTRIBUTES, "callback": CALLABLES, "parent": UI_NAMES},
        replace=("attribute", "callback", "parent"),
        invalid=_invalid(
            attribute=(None, 1.5, Lazy(lambda case: case.name("watched.noSuchAttribute"), "'<無いアトリビュート>'")),
            event=("SelectionChanged",),
            uiDeleted=("mlibSweepWindow",),
        ),
        expect=_expect_init,
        state=_state,
        reset=_release,
        writes=False,
        variant="attribute",
        skipCalling=SKIP_DEFAULTS,
    ),
    Method(
        "__init__",
        _watched,
        function=_construct,
        kwargs={"uiDeleted": "mlibSweepNoSuchWindow", "callback": _noop},
        values={"callback": CALLABLES, "parent": UI_NAMES},
        replace=("callback", "parent"),
        invalid=_invalid(uiDeleted=("", 1.5, None), event=("SelectionChanged",), attribute=(WATCHED,), allChildren=ALL_CHILDREN_INVALID),
        expect=_expect_init,
        state=_state,
        reset=_release,
        writes=False,
        variant="uiDeleted",
        skipCalling=SKIP_DEFAULTS,
    ),
    Method("exists", _job, expect=_expect_exists, state=_state, writes=False),
    Method("exists", _stopped, expect=_expect_exists, state=_state, writes=False, variant="stopped"),
    Method("stop", _job, expect=_expect_stop, state=_state, undoable=False),
    Method("stop", _stopped, expect=_expect_stop, state=_state, undoable=False, variant="stopped"),
)


class ScriptJobArgumentSweepTest(ArgumentSweepCase):
    """ScriptJob の公開メソッドの引数を網羅する。"""

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


class ScriptJobBatchTest(unittest.TestCase):
    """代役を使わないバッチでの動き。"""

    def test_batch_is_rejected(self):
        """バッチでは、正しい引数でも RuntimeError になる(docstring の Raises)。誤った引数は、その前に TypeError・ValueError になる。"""
        if not BATCH:
            self.skipTest("GUI では scriptJob を登録できる")
        with self.assertRaises(RuntimeError):
            ScriptJob(event="SelectionChanged", callback=_noop)
        with self.assertRaises(TypeError):
            ScriptJob(event="SelectionChanged", callback="print")
        with self.assertRaises(ValueError):
            ScriptJob(callback=_noop)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
