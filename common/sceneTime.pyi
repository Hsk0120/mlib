# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""シーンの現在時刻と、再生範囲・アニメーション範囲を扱う。"""

import contextlib
import math
import maya.cmds as cmds
import maya.mel as mel
from ..core.attributeType import _from_seconds, _to_seconds
from ..decorator import _require_bool
from ..util import _time_unit
from .environment import Environment
from typing import Any, Iterator, Literal
from mlib._stubtypes import GeneratorContextManager
from typing import overload
from typing_extensions import Self



class Time:
    """現在時刻と時間範囲を取得・変更する静的メソッドをまとめたクラス。

    インスタンスは作らず、``Time.getCurrent()`` のようにクラスから直接呼ぶ。

    時間の数値は、既定では現在のUI時間単位のフレームで扱う。``timeUnit="sec"`` を指定すると秒になる。
    変更はMayaの ``currentTime``・``playbackOptions`` と同じように行い、Undoの扱いも同じになる。
    fast引数は持たない。

    .. code-block:: python

        from mlib.common import Time

        start, end = Time.getRange()
        with Time.preserved():
            for frame in range(int(start), int(end) + 1):
                Time.setCurrent(frame)
                ...  # 各フレームの値を読む
    """
    def __new__(cls, *args, **kwargs) -> Self:
        """インスタンスを作らせない。

        Raises:
            TypeError: 常に送出する。
        """
        ...
    @staticmethod
    def getCurrent(*, timeUnit: str = ...) -> float:
        """現在時刻を取得する。

        Args:
            timeUnit (str): 戻り値の単位。``"frame"`` (現在のUI時間単位)または ``"sec"``。

        Returns:
            float: 現在時刻。
        """
        ...
    @staticmethod
    def setCurrent(value: float, *, timeUnit: str = ..., update: bool = ...) -> None:
        """現在時刻を変える。

        ``cmds.currentTime(value, update=update)`` と同じ働きをする。

        Args:
            value (float): 新しい時刻。
            timeUnit (str): valueの単位。``"frame"`` または ``"sec"``。
            update (bool): Trueなら、変えた時刻でシーンを評価し直す。直後に値を読める。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: valueが数値でない、またはupdateがbool以外の場合。
            ValueError: valueが有限でない、またはtimeUnitが未対応の単位名の場合。
        """
        ...
    @overload
    def getRange(*, animation: Literal[False] = ..., selected: Literal[True], timeUnit: str = ...) -> tuple[float, float] | None: ...
    @overload
    def getRange(*, animation: bool = ..., selected: Literal[False] = ..., timeUnit: str = ...) -> tuple[float, float]: ...
    @overload
    @staticmethod
    def getRange(*, animation: bool = ..., selected: bool = ..., timeUnit: str = ...) -> tuple[float, float] | None:
        """時間の範囲を取得する。

        既定では、再生範囲(タイムスライダーの開始・終了。``playbackOptions`` の ``minTime``・``maxTime``)を返す。

        ``selected=True`` は、タイムスライダーでShift+ドラッグで選んだ、赤く表示される範囲を返す。
        ``cmds.timeControl($gPlayBackSlider, query=True, rangeVisible=True)`` と ``rangeArray`` で調べる。
        Mayaの ``rangeArray`` の終わりは、範囲の次のフレームを指す。そこで1フレーム引いて、
        選んだ最後のフレームを返す。たとえば1〜10を選べば ``(1.0, 10.0)`` になる。
        クリックで1フレームだけ選んだ場合は、開始と終了が同じ値になる。

        Args:
            animation (bool): True なら、アニメーション範囲(レンジスライダーの両端。
                ``animationStartTime``・``animationEndTime``)を返す。
            selected (bool): True なら、タイムスライダーで選んだ範囲を返す。
            timeUnit (str): 戻り値の単位。``"frame"`` (現在のUI時間単位)または ``"sec"``。

        Returns:
            tuple[float, float] | None: (開始, 終了)。``selected=True`` では、範囲を選んでいない場合、
                バッチ(mayapy)の場合、タイムスライダーが無い場合はNone。

        Raises:
            TypeError: animation・selectedがbool以外の場合、またはanimationとselectedを両方Trueにした場合。
            ValueError: timeUnitが未対応の単位名の場合。
        """
        ...
    @staticmethod
    def setRange(start: float, end: float, *, animation: bool = ..., timeUnit: str = ...) -> None:
        """時間の範囲を変える。

        既定では、再生範囲(タイムスライダーの開始・終了)を変える。
        ``cmds.playbackOptions`` を1回呼ぶので、Undoの扱いもそれと同じになる。

        Args:
            start (float): 開始。
            end (float): 終了。start以上。
            animation (bool): True なら、アニメーション範囲(レンジスライダーの両端)を変える。
            timeUnit (str): start・endの単位。``"frame"`` または ``"sec"``。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: start・endが数値でない場合、またはanimationがbool以外の場合。
            ValueError: 有限でない、startがendより大きい、またはtimeUnitが未対応の単位名の場合。
        """
        ...
    @staticmethod
    def isPlaying() -> bool:
        """タイムスライダーで再生中かを調べる。

        ``cmds.play(query=True, state=True)`` と同じ。バッチ(mayapy)では常にFalse。

        Returns:
            bool: 再生中ならTrue。
        """
        ...
    @staticmethod
    def preserved() -> GeneratorContextManager[float]:
        """``with`` を抜けたときに元の時刻へ戻すコンテキストを作る。

        ``with`` の中では時刻を自由に変えてよい。抜けるときは、例外で抜けた場合も元の時刻へ戻す。

        Yields:
            float: 入る前の時刻(現在のUI時間単位のフレーム)。
        """
        ...

def _finite_time(value: float, name: str) -> float:
    """時刻の数値を検証する。

    Args:
        value (float): 時刻。boolは受け付けない。
        name (str): 例外メッセージに使う引数名。

    Returns:
        float: 検証した値。

    Raises:
        TypeError: 数値でない場合。
        ValueError: 有限でない場合。
    """
    ...

def _to_ui(value: float, unit: str) -> float:
    """指定単位の時刻をUI時間単位のフレームへ変換する。

    Args:
        value (float): 時刻。
        unit (str): valueの単位(``"frame"`` / ``"sec"``)。

    Returns:
        float: UI時間単位のフレーム。
    """
    ...

def _from_ui(value: float, unit: str) -> float:
    """UI時間単位のフレームを指定単位へ変換する。

    Args:
        value (float): UI時間単位のフレーム。
        unit (str): 戻り値の単位(``"frame"`` / ``"sec"``)。

    Returns:
        float: 指定単位の時刻。
    """
    ...

def _get_range(start_flag: str, end_flag: str, unit: str) -> tuple[float, float]:
    """playbackOptions の範囲を取得する。

    Args:
        start_flag (str): 開始のフラグ名。
        end_flag (str): 終了のフラグ名。
        unit (str): 戻り値の単位。

    Returns:
        tuple[float, float]: (開始, 終了)。
    """
    ...

def _get_selected_range(unit: str) -> tuple[float, float] | None:
    """タイムスライダーで選んだ範囲を取得する。

    Args:
        unit (str): 戻り値の単位。

    Returns:
        tuple[float, float] | None: (開始, 選んだ最後のフレーム)。選んでいない・バッチ・タイムスライダーが無い場合はNone。
    """
    ...

def _set_range(start_flag: str, end_flag: str, start: float, end: float, unit: str) -> None:
    """playbackOptions の範囲を設定する。

    Args:
        start_flag (str): 開始のフラグ名。
        end_flag (str): 終了のフラグ名。
        start (float): 開始。
        end (float): 終了。
        unit (str): start・endの単位。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: start・endが数値でない場合。
        ValueError: 有限でない、またはstartがendより大きい場合。
    """
    ...
