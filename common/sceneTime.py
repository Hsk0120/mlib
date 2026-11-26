"""シーンの現在時刻と、再生範囲・アニメーション範囲を扱う。"""

import contextlib
import math

import maya.cmds as cmds
import maya.mel as mel

from ..core.attributeType import _from_seconds, _to_seconds
from ..decorator import _require_bool
from ..util import _required_time_unit
from .environment import Environment


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

    def __new__(cls, *args, **kwargs):
        """インスタンスを作らせない。

        Raises:
            TypeError: 常に送出する。
        """
        raise TypeError("Timeは静的メソッドだけを提供します。Time.getCurrent()のように直接呼び出してください")

    @staticmethod
    def getCurrent(*, timeUnit="frame"):
        """現在時刻を取得する。

        Args:
            timeUnit (str): 戻り値の単位。``"frame"`` (現在のUI時間単位)または ``"sec"``。

        Returns:
            float: 現在時刻。

        Raises:
            TypeError: timeUnitが文字列でない場合(Noneを含む)。
            ValueError: timeUnitが未対応の単位名の場合。
        """
        return _from_ui(cmds.currentTime(query=True), _required_time_unit(timeUnit))

    @staticmethod
    def setCurrent(value, *, timeUnit="frame", update=True):
        """現在時刻を変える。

        ``cmds.currentTime(value, update=update)`` と同じ働きをする。

        Args:
            value (float): 新しい時刻。
            timeUnit (str): valueの単位。``"frame"`` または ``"sec"``。
            update (bool): Trueなら、変えた時刻でシーンを評価し直す。直後に値を読める。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: valueが数値でない、timeUnitが文字列でない(Noneを含む)、またはupdateがbool以外の場合。
            ValueError: valueが有限でない、またはtimeUnitが未対応の単位名の場合。
        """
        unit = _required_time_unit(timeUnit)
        if not isinstance(update, bool):
            raise TypeError("updateはboolで指定してください")
        cmds.currentTime(_to_ui(_finite_time(value, "value"), unit), update=update)

    @staticmethod
    def getRange(*, animation=False, selected=False, timeUnit="frame"):
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
            TypeError: animation・selectedがbool以外の場合、animationとselectedを両方Trueにした場合、
                またはtimeUnitが文字列でない場合(Noneを含む)。
            ValueError: timeUnitが未対応の単位名の場合。
        """
        _require_bool(animation, "animation")
        _require_bool(selected, "selected")
        if animation and selected:
            raise TypeError("animationとselectedは同時に指定できません")
        unit = _required_time_unit(timeUnit)
        if selected:
            return _get_selected_range(unit)
        if animation:
            return _get_range("animationStartTime", "animationEndTime", unit)
        return _get_range("minTime", "maxTime", unit)

    @staticmethod
    def setRange(start, end, *, animation=False, timeUnit="frame"):
        """時間の範囲を変える。

        既定では、再生範囲(タイムスライダーの開始・終了)を変える。
        再生範囲はアニメーション範囲の中に収まる必要があるため、もう一方の範囲も次のように合わせて変える
        (Mayaが合わせて変えるのと同じ。ただしMayaだけに任せると、その変更はUndoで戻らない)。

        - 再生範囲を変えるとき: アニメーション範囲を、新しい再生範囲を含むまで広げる。
        - アニメーション範囲を変えるとき: 再生範囲を新しいアニメーション範囲の中へ縮める。重ならないときは、再生範囲もアニメーション範囲と同じにする。

        4つの値を ``cmds.playbackOptions`` の1回の呼び出しで書くので、Undoの扱いもそれと同じになる。
        Mayaの版で違い、Maya 2022ではUndoに記録されず、Maya 2027では記録される(1回のUndoで、もう一方の範囲も戻る)。

        Args:
            start (float): 開始。
            end (float): 終了。startより大きい値(同じ値にすると、Mayaが範囲を1フレーム広げるため)。
            animation (bool): True なら、アニメーション範囲(レンジスライダーの両端)を変える。
            timeUnit (str): start・endの単位。``"frame"`` または ``"sec"``。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: start・endが数値でない場合、animationがbool以外の場合、またはtimeUnitが文字列でない場合(Noneを含む)。
            ValueError: 有限でない、startがend以上、またはtimeUnitが未対応の単位名の場合。

        Note:
            Maya 2022では、範囲の変更がUndoに記録されない(Mayaの制限)。
        """
        _require_bool(animation, "animation")
        unit = _required_time_unit(timeUnit)
        _set_range(animation, start, end, unit)

    @staticmethod
    def isPlaying():
        """タイムスライダーで再生中かを調べる。

        ``cmds.play(query=True, state=True)`` と同じ。バッチ(mayapy)では常にFalse。

        Returns:
            bool: 再生中ならTrue。
        """
        return bool(cmds.play(query=True, state=True))

    @staticmethod
    @contextlib.contextmanager
    def preserved():
        """``with`` を抜けたときに元の時刻へ戻すコンテキストを作る。

        ``with`` の中では時刻を自由に変えてよい。抜けるときは、例外で抜けた場合も元の時刻へ戻す。

        Yields:
            float: 入る前の時刻(現在のUI時間単位のフレーム)。
        """
        original = cmds.currentTime(query=True)
        try:
            yield original
        finally:
            cmds.currentTime(original, update=True)


def _finite_time(value, name):
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
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name}は数値で指定してください: {type(value).__name__}")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name}は有限な数値で指定してください")
    return value


def _to_ui(value, unit):
    """指定単位の時刻をUI時間単位のフレームへ変換する。

    Args:
        value (float): 時刻。
        unit (str): valueの単位(``"frame"`` / ``"sec"``)。

    Returns:
        float: UI時間単位のフレーム。
    """
    return value if unit == "frame" else _from_seconds(value, "frame")


def _from_ui(value, unit):
    """UI時間単位のフレームを指定単位へ変換する。

    Args:
        value (float): UI時間単位のフレーム。
        unit (str): 戻り値の単位(``"frame"`` / ``"sec"``)。

    Returns:
        float: 指定単位の時刻。
    """
    return float(value) if unit == "frame" else _to_seconds(value, "frame")


def _get_range(start_flag, end_flag, unit):
    """playbackOptions の範囲を取得する。

    Args:
        start_flag (str): 開始のフラグ名。
        end_flag (str): 終了のフラグ名。
        unit (str): 戻り値の単位。

    Returns:
        tuple[float, float]: (開始, 終了)。
    """
    return (_from_ui(cmds.playbackOptions(query=True, **{start_flag: True}), unit), _from_ui(cmds.playbackOptions(query=True, **{end_flag: True}), unit))


def _get_selected_range(unit):
    """タイムスライダーで選んだ範囲を取得する。

    Args:
        unit (str): 戻り値の単位。

    Returns:
        tuple[float, float] | None: (開始, 選んだ最後のフレーム)。選んでいない・バッチ・タイムスライダーが無い場合はNone。
    """
    if Environment.isBatch():
        return None
    try:
        # タイムスライダーの名前はMayaのUIが保持するグローバル変数から取得する。
        slider = mel.eval("global string $gPlayBackSlider; $mlibPlayBackSlider = $gPlayBackSlider;")
    except RuntimeError:
        return None
    if not slider or not cmds.timeControl(slider, exists=True):
        return None
    if not cmds.timeControl(slider, query=True, rangeVisible=True):
        return None
    start, end = cmds.timeControl(slider, query=True, rangeArray=True)
    return _from_ui(start, unit), _from_ui(float(end) - 1.0, unit)


def _set_range(animation, start, end, unit):
    """playbackOptions の範囲を、もう一方の範囲と合わせて1回の呼び出しで設定する。

    Args:
        animation (bool): Trueならアニメーション範囲、Falseなら再生範囲を変える。
        start (float): 開始。
        end (float): 終了。
        unit (str): start・endの単位。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: start・endが数値でない場合。
        ValueError: 有限でない、またはstartがend以上の場合。
    """
    start, end = _finite_time(start, "start"), _finite_time(end, "end")
    if start >= end:
        raise ValueError(f"startはendより小さくしてください: {start} >= {end}")
    start, end = _to_ui(start, unit), _to_ui(end, unit)
    if animation:
        play_start = max(cmds.playbackOptions(query=True, minTime=True), start)
        play_end = min(cmds.playbackOptions(query=True, maxTime=True), end)
        if play_start >= play_end:
            play_start, play_end = start, end
        anim_start, anim_end = start, end
    else:
        play_start, play_end = start, end
        anim_start = min(cmds.playbackOptions(query=True, animationStartTime=True), start)
        anim_end = max(cmds.playbackOptions(query=True, animationEndTime=True), end)
    # Mayaが黙って合わせる値も含めて書き、1回のUndoで両方の範囲が戻るようにする。
    cmds.playbackOptions(minTime=play_start, maxTime=play_end, animationStartTime=anim_start, animationEndTime=anim_end)
