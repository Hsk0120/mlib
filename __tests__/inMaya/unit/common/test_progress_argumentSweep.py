"""progress.progressBar の引数を、表から網羅して確かめる(段1〜3)。

戻り値のジェネレーターを最後まで回し、元の要素が元の順に返ること、出力先(``io.StringIO``)と notify に
見出し・件数・百分率が渡ることを確かめる。バッチでは gui=True は RuntimeError(docstring の Raises)。
シーンを変えないので、Undo の性質は当てはまらない。
表の書き方と段の意味は ``support/argumentSweep.py`` と ``__tests__/README.md`` を参照する。
"""

import inspect
import io
import sys
import unittest

import mlib

mlib.reload()

from support.argumentSweep import ArgumentSweepCase
from support.argumentTable import Lazy, Method

from mlib.common import progress

_notified = []


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


def _consumed(iterable, **kwargs):
    """progressBar を呼び、ジェネレーターを最後まで回した要素を返す(回すまで検査しない形にも対応する)。"""
    return list(progress.progressBar(iterable, **kwargs))


_consumed.__signature__ = inspect.signature(progress.progressBar)
_consumed.__doc__ = progress.progressBar.__doc__


def _functions(case):
    _notified.clear()
    return _host("progress", progressBar=_consumed)


def _notify(text):
    _notified.append(text)


class _Stream:
    """write だけを持つ出力先(flush は任意)。"""

    def __init__(self):
        self.parts = []

    def __repr__(self):
        return "<write だけの出力先>"

    def write(self, text):
        self.parts.append(text)


def _expect_progress(case, call):
    kwargs = call.kwargs
    case.assertEqual(call.result, list(kwargs["iterable"]))
    stream = kwargs.get("stream")
    if isinstance(stream, io.TextIOWrapper):
        stream.flush()
        written = stream.buffer.getvalue().decode("utf-8")
    else:
        written = "".join(stream.getvalue() if isinstance(stream, io.StringIO) else getattr(stream, "parts", []))
    label = (kwargs.get("label") or "").rstrip()
    if not call.result:
        # 空の並びでは何も表示しない。
        _notified.clear()
        return
    if stream is not None and kwargs.get("gui") is not True:
        if label:
            case.assertIn(label, written)
        case.assertIn(str(len(call.result)), written)
    if kwargs.get("notify") is _notify:
        case.assertTrue(_notified)
        case.assertTrue(all("\n" not in text and "\r" not in text for text in _notified))
        if label:
            case.assertTrue(_notified[-1].startswith(label))
    _notified.clear()


def _generator():
    return (value * 2 for value in range(5))


STREAMS = (
    None,
    Lazy(lambda case: io.StringIO(), "<StringIO>"),
    Lazy(lambda case: io.TextIOWrapper(io.BytesIO(), encoding="utf-8"), "<TextIOWrapper>"),
    Lazy(lambda case: _Stream(), "<write だけの出力先>"),
)


METHODS = (
    Method(
        "progressBar",
        _functions,
        args=([1, 2, 3],),
        values={
            "iterable": ([1, 2, 3], (), range(10), "abc", {"a": 1, "b": 2}),
            "label": ("", "Export", "  trailing  ", "日本語"),
            "total": (None, 0, 3, 100, 1),
            "width": (30, 1, 5, 80),
            "stream": STREAMS,
            "notify": (None, _notify, lambda text: None),
            "gui": (None, False, True),
        },
        replace=("iterable", "label", "total", "width", "stream", "notify", "gui"),
        invalid={
            "iterable": (None, 1.5),
            "label": (1.5, None, ["Export"]),
            "total": (-1, 1.5, True, "3"),
            "width": (0, -1, 1.5, True, None),
            "stream": (1.5, "stdout"),
            "notify": (1.5, "print"),
            "gui": (1, "yes"),
        },
        expect=_expect_progress,
        writes=False,
        known={
            "invalid:stream=1.5": "write を持たない出力先で Raises に無い AttributeError",
            "invalid:stream='stdout'": "write を持たない出力先で Raises に無い AttributeError",
        },
        limit=120,
    ),
)


class ProgressArgumentSweepTest(ArgumentSweepCase):
    """progress.progressBar の引数を網羅する。"""

    METHODS = METHODS

    def test_progressBar_generator(self):
        """長さの無いジェネレーターも、元の要素を元の順に返す(total を省くと件数だけを表示する)。"""
        stream = io.StringIO()
        self.assertEqual(list(progress.progressBar(_generator(), label="gen", stream=stream)), [0, 2, 4, 6, 8])
        self.assertIn("gen", stream.getvalue())
        self.assertIn("5", stream.getvalue())


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
