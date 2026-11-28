"""``mlib.logger`` の公開の関数と MayaHandler の引数を、表から網羅して確かめる(段1〜4)。

関数は ``support.argumentSweep`` がメソッドとして呼べるよう、入れ物のクラス(:class:`_Functions`)のメソッドにして表へ渡す。
ログの関数(debug・info・warning・error)は、呼んでいる間だけ共通のロガーへ記録用のハンドラーを足し、
出たレコードのレベルと本文を確かめる。print は書き込み先(StringIO)の中身を、標準の print の決まりで求めた文字列と突き合わせる。
どれもシーンを変えないので、Undo・fast の性質は当てはまらない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import io
import logging
import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib import logger


class _Recorder(logging.Handler):
    """出たレコードを覚えるだけのハンドラー。"""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.records = []

    def emit(self, record):
        self.records.append(record)


class _Functions:
    """``mlib.logger`` の関数を、表から呼べるメソッドとして持つ入れ物。"""


def _as_method(function, record=False):
    """関数を、同じ引数・docstring を持つ :class:`_Functions` のメソッドにする。

    record なら、呼んでいる間に共通のロガーへ出たレコードを集め、[戻り値, [(レベル, 本文), ...]] を返す。
    """
    signature = inspect.signature(function)

    def method(self, *args, **kwargs):
        if not record:
            return function(*args, **kwargs)
        recorder = _Recorder()
        target = logger.getLogger()
        target.addHandler(recorder)
        try:
            result = function(*args, **kwargs)
        finally:
            target.removeHandler(recorder)
        return [result, [(item.levelno, item.getMessage()) for item in recorder.records]]

    method.__signature__ = signature.replace(parameters=[inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD), *signature.parameters.values()])
    method.__doc__ = function.__doc__
    method.__name__ = function.__name__
    return method


#: ログの関数と、出るレコードのレベル。
LEVELS = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR}

for _name in LEVELS:
    setattr(_Functions, _name, _as_method(getattr(logger, _name), record=True))
for _name in ("getLogger", "print"):
    setattr(_Functions, _name, _as_method(getattr(logger, _name)))


def _raise_with_notify(exceptionType, *args, **kwargs):
    """raiseWithNotify を呼び、指定した型で送り出された例外を戻り値にする(それ以外の例外はそのまま出す)。

    raiseWithNotify は必ず例外を送り出す関数なので、表では、送り出された例外を戻り値として確かめる。
    """
    try:
        logger.raiseWithNotify(exceptionType, *args, **kwargs)
    except Exception as error:
        if isinstance(exceptionType, type) and type(error) is exceptionType:
            return error
        raise
    return None


_raise_with_notify.__signature__ = inspect.signature(logger.raiseWithNotify)
_raise_with_notify.__doc__ = logger.raiseWithNotify.__doc__
_Functions.raiseWithNotify = _as_method(_raise_with_notify, record=True)


def _functions(case):
    return _Functions()


def _handler(case):
    return logger.MayaHandler()


class _BrokenFormatter(logging.Formatter):
    """書式の適用で必ず失敗する Formatter。"""

    def format(self, record):
        raise ValueError("mlibSweep formatter")


def _broken_handler(case):
    """Formatter が失敗するハンドラー(標準の書式に戻して出すことを確かめる)。"""
    handler = logger.MayaHandler()
    handler.setFormatter(_BrokenFormatter())
    return handler


def _record(level, message="mlib argumentSweep %s", args=("値",), exc_info=None):
    return logging.LogRecord(logger.LOGGER_NAME, level, __file__, 1, message, args, exc_info)


def _raised():
    """例外の情報(exc_info)を作る。"""
    try:
        raise KeyError("mlibSweep")
    except KeyError:
        return sys.exc_info()


def _expect_none(case, call):
    case.assertIsNone(call.result)


def _expect_logger(case, call):
    """パッケージ名のロガーで、レベルは DEBUG、親へは伝えず、MayaHandler を1つだけ持つ。何度呼んでも同じもの。"""
    case.assertIs(call.result, logging.getLogger("mlib"))
    case.assertEqual(call.result.level, logging.DEBUG)
    case.assertFalse(call.result.propagate)
    case.assertEqual(len([handler for handler in call.result.handlers if isinstance(handler, logger.MayaHandler)]), 1)
    case.assertIs(logger.getLogger(), call.result)


def _expect_log(name):
    """値を返さず、決まったレベルのレコードを1つ出す。本文は標準の logging と同じ(引数があれば ``%`` で埋める)。"""

    def expect(case, call):
        result, records = call.result
        message, args = call.kwargs["message"], tuple(call.kwargs.get("args", ()))
        case.assertIsNone(result)
        case.assertEqual(records, [(LEVELS[name], str(message) % args if args else str(message))])

    return expect


def _expect_print(case, call):
    """書き込み先の中身は、標準の print と同じ(値を sep でつなぎ、最後に end を付ける)。"""
    kwargs = call.kwargs
    case.assertIsNone(call.result)
    if not isinstance(kwargs.get("file"), io.StringIO):
        return
    sep = " " if kwargs.get("sep", " ") is None else kwargs.get("sep", " ")
    end = "\n" if kwargs.get("end", "\n") is None else kwargs.get("end", "\n")
    case.assertEqual(kwargs["file"].getvalue(), sep.join(str(item) for item in kwargs.get("objects", ())) + end)


def _expect_raise(case, call):
    """指定した型の例外を、本文と追加の引数を持たせて送り出し、その前にエラーを1つ知らせる。原因は fromException のとおり。"""
    error, records = call.result
    kwargs = call.kwargs
    case.assertIs(type(error), kwargs["exceptionType"])
    case.assertEqual(error.args, (kwargs["message"], *kwargs.get("args", ())))
    case.assertEqual(records, [(logging.ERROR, kwargs["message"])])
    case.assertIs(error.__cause__, kwargs.get("fromException"))
    case.assertIs(error.__suppress_context__, "fromException" in kwargs)


def _format_mismatch(stage, kwargs):
    """書式の ``%s`` の数と、書式の引数の数が合わない呼び方か。"""
    return str(kwargs.get("message")).count("%s") != len(tuple(kwargs.get("args", ()))) and bool(kwargs.get("args"))


#: ログの本文の候補(書式の文字列・文字列でない値)。
MESSAGES = ("mlib argumentSweep %s", "mlib argumentSweep", "", "日本語の本文", 1.5, None, ValueError("mlibSweep"))
#: logging へ渡すオプションの候補。
# stacklevel は Python 3.8 から(Maya 2022 の Python 3.7 には無い)。
LOG_OPTIONS = ({"exc_info": True}, {"stack_info": True}, {"extra": {"mlibSweep": 1}}) + (({"stacklevel": 2},) if sys.version_info >= (3, 8) else ())


def _log_row(name):
    return Method(
        name,
        _functions,
        args=("mlib argumentSweep",),
        values={"message": MESSAGES, "*": (("値",), (1.5,), ()), "**": LOG_OPTIONS},
        replace=("message",),
        expect=_expect_log(name),
        writes=False,
        known={
            _format_mismatch: "書式と引数の数が合わないと TypeError がそのまま出る(Raises に無い。標準の logging のハンドラーは、"
            "書式の失敗を握って stderr へ出す)"
        },
    )


#: 表を名前から作るログの関数(行の有無を確かめるテストは、この並びも行として数える)。
SWEPT = ("debug", "info", "warning", "error")

#: 出力する値の候補。
OBJECTS = (("a", 1), (), ("日本語",), (None, 1.5, ["x"]))
STRING_IO = Lazy(lambda case: io.StringIO(), "<StringIO>")

METHODS = (
    Method(
        "emit",
        _handler,
        args=(_record(logging.INFO),),
        values={
            "record": (
                _record(logging.DEBUG),
                _record(logging.INFO),
                _record(logging.WARNING),
                _record(logging.ERROR),
                _record(logging.CRITICAL),
                _record(logging.ERROR, "<b>mlib</b> & argumentSweep", ()),
                _record(logging.ERROR, exc_info=_raised()),
                _record(logging.INFO, 1.5, ()),
            )
        },
        replace=("record",),
        # logging.Handler の決まりで、emit へは logging が LogRecord だけを渡す(型は確かめない)ので、違う型の値は確かめない。
        invalid={"record": ()},
        expect=_expect_none,
        writes=False,
    ),
    Method(
        "emit",
        _broken_handler,
        args=(_record(logging.WARNING),),
        values={"record": (_record(logging.INFO), _record(logging.WARNING), _record(logging.ERROR, exc_info=_raised()))},
        replace=("record",),
        invalid={"record": ()},
        expect=_expect_none,
        writes=False,
        variant="brokenFormatter",
    ),
    Method("getLogger", _functions, expect=_expect_logger),
    *(_log_row(name) for name in SWEPT),
    Method(
        "print",
        _functions,
        args=("a", 1),
        kwargs={"file": STRING_IO},
        values={"*": OBJECTS, "sep": (" ", None, "", ", "), "end": ("\n", None, "", "\r\n"), "file": (STRING_IO, None)},
        replace=("sep", "end", "file"),
        expect=_expect_print,
        writes=False,
        known={
            "invalid:*": "標準の print へそのまま渡すので、str でない sep・end と write を持たない file は TypeError・AttributeError になり"
            "(docstring に Raises が無い)、bool でない flush は受け付ける"
        },
    ),
    Method(
        "raiseWithNotify",
        _functions,
        args=(ValueError, "mlib argumentSweep"),
        values={
            "exceptionType": (ValueError, RuntimeError, KeyError, Exception),
            "message": ("mlib argumentSweep", "", "日本語の本文"),
            "*": ((), ("extra", 1)),
            "fromException": (None, KeyError("mlibSweep cause")),
        },
        replace=("exceptionType", "message", "fromException"),
        invalid={"exceptionType": (None, 1.5, "ValueError"), "fromException": (1.5, "abc", KeyError)},
        expect=_expect_raise,
        writes=False,
        known={"invalid:message=1.5": "message は型を確かめずに、ログと例外へそのまま渡す(docstring は str)"},
    ),
)


class LoggerArgumentSweepTest(ArgumentSweepCase):
    """``mlib.logger`` の公開の関数と MayaHandler の引数を網羅する。"""

    METHODS = METHODS


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
