# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""アニメカーブ1本の内容を辞書へ読み出し、同じ内容のカーブへ書き戻す(mlib.jsonの内部の補助)。

:class:`~mlib.json.animationSnapshot.AnimationSnapshot` と
:class:`~mlib.json.drivenKeysSnapshot.DrivenKeysSnapshot` の両方が使う。カーブの辞書は次の形::

    {"curveType": "animCurveTL", "weighted": False, "preInfinity": "constant", "postInfinity": "constant",
     "keys": [{"input": 1.0, "value": 2.5, "inType": "auto", "outType": "auto",
               "inAngle": 0.0, "inWeight": 1.0, "outAngle": 0.0, "outWeight": 1.0,
               "lock": True, "weightLock": True, "breakdown": False}, ...]}

単位はmlibの既定に合わせる。UIの単位には左右されない。

- ``input``: 時間の入力(animCurveT*)は、保存したときのUIの時間の単位でのフレーム。
  単位の無い入力(animCurveU*)は、呼び出し側が決める単位(ドリブンキーではドライバーのmlibの単位)。
- ``value``: 出力が角度なら度、距離ならcm、時間ならフレーム。それ以外は単位なし。
- 接線の角度: 横軸を ``input`` の単位、縦軸を ``value`` の単位とした平面での向き(度)。
- 接線のウェイト: Mayaと同じく、長さの1/3(ウェイト付き接線のカーブでは、Graph Editorの表示と同じ値)。
  単位の無い入力のカーブや、ウェイトの無いカーブでは、Mayaの表示(1.0)と合わないことがある。
  ただし、保存して書き戻せば同じ形になる。

固定(fixed)以外の接線も角度とウェイトを記録する。ただし書き戻すときは、Mayaが接線の型から計算し直す。
"""

import math
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
from ..core.attributeType import _convert_units, _from_seconds, _to_seconds
from ..nodes.animCurve import _TANGENT_NAMES, _TANGENT_TYPES, AnimCurve
from typing import Iterable

_INFINITY_TYPES: tuple
_KEY_FIELDS: dict
_OUT_ONLY_TANGENTS: tuple
_TIME_TOLERANCE: float

def _is_time_input(curve_type: str) -> bool:
    """カーブの型の入力が時間かを返す。

    Args:
        curve_type (str): ``"animCurveTL"`` など。

    Returns:
        bool: animCurveT*ならTrue。
    """
    ...

def _output_kind(curve_type: str) -> str:
    """カーブの型の出力の種類を返す。

    Args:
        curve_type (str): ``"animCurveTL"`` など。

    Returns:
        str: ``"A"`` (角度)・``"L"`` (距離)・``"T"`` (時間)・``"U"`` (無次元)。
    """
    ...

def _require_curve(data: object):
    """カーブの辞書の形を確かめる。

    Args:
        data (object): :func:`_read_curve` の形の辞書。

    Raises:
        ValueError: 辞書の形・型・値が正しくない場合。
    """
    ...

def _read_curve(curve: str, input_scale: float = ..., input_range: tuple[float, float] | None = ...) -> dict:
    """カーブのキーと設定を辞書へ読み出す。

    すべてのキー、または範囲の中のキーを読む。

    Args:
        curve (str): animCurveノードの名前。
        input_scale (float): 単位の無い入力のカーブで、Mayaの入力の値に掛けて ``input`` にする倍率。
            入力が時間のカーブでは使わない。
        input_range (tuple[float, float] | None): 読むキーの範囲。``input`` の単位で、両端を含む。Noneならすべてのキー。

    Returns:
        dict: モジュールの説明の形の新しい辞書。
    """
    ...

def _transform_keys(keys: list[dict], scale: float = ..., offset: float = ..., value_scale: float = ...) -> list[dict]:
    """キーの入力を ``input * scale + offset`` へ動かした、新しいlistを返す。

    接線も同じ倍率で伸ばす。

    Args:
        keys (list[dict]): キーの辞書の並び。変更しない。
        scale (float): 入力の倍率(fpsの換算)。
        offset (float): 入力へ足す量。
        value_scale (float): 値の倍率(時間出力のカーブのfps換算)。

    Returns:
        list[dict]: 新しいキーの辞書の並び。
    """
    ...

def _merge_keys(existing: list[dict], incoming: list[dict], mode: str, input_range: tuple[float, float] | None = ...) -> list[dict]:
    """既存のキーと読み込んだキーを、適用の方法に従って1つの並びにする。

    Args:
        existing (list[dict]): カーブにあるキー。
        incoming (list[dict]): 読み込んだキー(移動済み)。
        mode (str): ``"replace"``・``"insert"``・``"merge"``。
        input_range (tuple[float, float] | None): insertで置き換える範囲。Noneは読み込んだキーの範囲。

    Returns:
        list[dict]: 入力の小さい順に並べたキー。同じ時刻のキーがあれば、読み込んだキーを使う。
    """
    ...

def _write_curve(curve: str, data: dict, keys: list[dict], input_scale: float = ..., fast: bool = ...):
    """カーブのすべてのキーを消し、指定したキーと設定で書き直す。

    通常はcmds(setKeyframe・keyTangent)で書くので、呼び出し側のUndoにまとまる。
    fastはOpenMayaで書く(出力が時間のカーブは、fastでもcmdsで書く)。

    Args:
        curve (str): animCurveノードの名前。
        data (dict): ``weighted``・``preInfinity``・``postInfinity`` を持つカーブの辞書。
        keys (list[dict]): 書くキー(入力の小さい順)。
        input_scale (float): 単位の無い入力で、``input`` をMayaの入力の値へ戻すときに割る倍率。
        fast (bool): TrueはOpenMayaで書く。
    """
    ...

def _write_cmds(node: AnimCurve, time_input: bool, weighted: bool, entries: list[dict]):
    """cmdsでキーを書き直す(Undo可能)。

    Args:
        node (AnimCurve): 書き込むカーブ。
        time_input (bool): Trueなら入力が時間。
        weighted (bool): Trueならウェイト付き接線にする。
        entries (list[dict]): :func:`_write_curve` が内部の単位へ直したキー。
    """
    ...

def _write_fast(node: AnimCurve, time_input: bool, weighted: bool, entries: list[dict]):
    """OpenMayaでキーを書き直す(Undoなし)。

    Args:
        node (AnimCurve): 書き込むカーブ。出力が時間でないもの。
        time_input (bool): Trueなら入力が時間。
        weighted (bool): Trueならウェイト付き接線にする。
        entries (list[dict]): :func:`_write_curve` が内部の単位へ直したキー。
    """
    ...

def _ranges(indices: Iterable[int]) -> list[tuple[int, int]]:
    """番号の並びを、続いている番号ごとの ``(最初, 最後)`` の並びにする。

    Args:
        indices (Iterable[int]): 小さい順の番号。

    Returns:
        list[tuple[int, int]]: keyTangentのindexフラグへ渡す範囲。
    """
    ...

def _angle_weight(x: float, y: float) -> tuple[float, float]:
    """接線のベクトルを角度(度)とウェイトにする。

    Args:
        x (float): 横軸の成分。
        y (float): 縦軸の成分。

    Returns:
        tuple[float, float]: 角度(度)と、ベクトルの長さの1/3。
    """
    ...

def _tangent_xy(angle: float, weight: float) -> tuple[float, float]:
    """角度(度)とウェイトを接線のベクトルへ戻す。

    Args:
        angle (float): 角度(度)。
        weight (float): ウェイト。

    Returns:
        tuple[float, float]: 横軸・縦軸の成分。
    """
    ...

def _to_internal(kind: str, value: float) -> float:
    """mlibの単位の値を、Mayaの内部の単位(rad・cm・秒)へ直す。

    Args:
        kind (str): :func:`_output_kind` の種類。
        value (float): 度・cm・フレーム・単位なしの値。

    Returns:
        float: 内部の単位の値。
    """
    ...

def _from_internal(kind: str, value: float) -> float:
    """Mayaの内部の単位の値を、mlibの単位(度・cm・フレーム)へ直す。

    Args:
        kind (str): :func:`_output_kind` の種類。
        value (float): 内部の単位の値。

    Returns:
        float: mlibの単位の値。
    """
    ...
