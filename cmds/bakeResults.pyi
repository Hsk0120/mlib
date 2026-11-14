# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""アトリビュートの動きを、フレームごとのキーへ焼き込む(``cmds.bakeResults`` 相当)。"""

import math
import numbers
import re
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET
from typing import Sequence
from mlib.nodes.animCurve import AnimCurve
from mlib.nodes.node import Node

_REJECTED_FLAGS: frozenset

def bakeResults(nodes: Node | str | Sequence[Node | str], attributes: str | Sequence[str] | None = ..., time: tuple[float, float] | None = ..., sampleBy: float = ..., *, at: str | Sequence[str] | None = ..., t: tuple[float, float] | None = ..., sb: float = ..., **kwargs: object) -> list[AnimCurve]:
    """アトリビュートの動きをキーへ焼き込み、そのアニメーションカーブを返す。

    コンストレイント・エクスプレッション・ドリブンキーなどで動いているアトリビュートを、
    指定した範囲でフレームごとに評価し、キーにする。選択状態は使わない。

    - timeを省略すると、再生範囲(``mlib.Time.getPlaybackRange()``)を焼き込む。
    - attributesを省略すると、Mayaの既定(各ノードのキー設定可能なアトリビュート)を焼き込む。
    - Mayaの既定(``simulation=False``)では、入力を持たない静的なアトリビュートにはキーを作らない。
      ダイナミクスなど、すべてのフレームを順に評価する必要があるときは ``simulation=True`` を渡す。

    焼き込みで現在時刻が動いた場合は、終わったあと元の時刻へ戻す。
    fast引数は無い(OpenMayaに同じ機能が無いため)。Undoが有効なら1回で戻せる。
    専用の引数は ``cmds.bakeResults`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        nodes (Node | str | Sequence[Node | str]): 焼き込むノード、またはその並び。
        attributes (str | Sequence[str] | None): 焼き込むアトリビュート名。``"translateX"``・``"tx"`` や、
            コンパウンドアトリビュートの ``"translate"`` も指定できる。
            NoneならMayaの既定(キー設定可能なもの)。既定はNone。
        time (tuple[float, float] | None): 焼き込む範囲 (開始, 終了)。現在のUI時間単位のフレームで、両端を含む。
            Noneなら再生範囲。既定はNone。
        sampleBy (float): キーを作る間隔(フレーム)。正の数。既定は1。
        at (str | Sequence[str] | None): attributesの短縮名(Mayaの ``attribute``)。attributesと同時には指定できない。
        t (tuple[float, float] | None): timeの短縮名。timeと同時には指定できない。
        sb (float): sampleByの短縮名。sampleByと同時には指定できない。
        **kwargs (object): ``cmds.bakeResults`` のそのほかのフラグ。長い名前・短い名前のどちらでもよい。
            ``simulation``・``preserveOutsideKeys``・``sparseAnimCurveBake``・``disableImplicitControl``・
            ``minimizeRotation``・``shape``・``hierarchy`` など。
            ``attribute`` は ``attributes`` で指定するため受け付けない。query・editも受け付けない。

    Returns:
        list[AnimCurve]: 焼き込んだアトリビュートを動かすアニメーションカーブ(新しく作ったものと書き換えたもの)。
            対象はnodesのアトリビュートで、``shape`` が有効なら直下のShapeのアトリビュートも含む。
            ``hierarchy`` で増えた子孫のカーブは含まない。焼き込むものが無ければ空リスト。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、``**kwargs`` で受け付けないフラグを渡した場合、
            attributesが文字列・文字列の並び・Noneのどれでもない場合、またはtimeかsampleByが数値でない場合。
        ValueError: nodesが空の場合、timeが2つの有限な数値でない場合、timeの開始が終了より後の場合、
            またはsampleByが正の有限な数でない場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが焼き込みを拒否した場合。

    Examples:
        >>> import mlib
        >>> curves = mlib.bakeResults(["arm_CTRL", "leg_CTRL"], time=(1, 120), simulation=True)
        >>> curves = mlib.bakeResults("arm_CTRL", at=["tx", "ty"], t=(1, 24), sb=2)  # cmds.bakeResults と同じ短縮名
    """
    ...

def _attribute_names(attributes: str | Sequence[str] | None) -> list[str] | None:
    """attributesの指定を、cmds.bakeResultsへ渡すアトリビュート名のリストに揃える。

    Args:
        attributes (str | Sequence[str] | None): アトリビュート名、その並び、またはNone。

    Returns:
        list[str] | None: アトリビュート名。NoneはMayaの既定。

    Raises:
        TypeError: 文字列・文字列の並び・Noneのどれでもない場合。
        ValueError: 並びが空の場合、または空文字列を含む場合。
    """
    ...

def _time_range(time: Sequence[float]) -> tuple[float, float]:
    """timeの指定 (開始, 終了) を確かめる。

    Args:
        time (Sequence[float]): 開始と終了のフレーム。

    Returns:
        tuple[float, float]: (開始, 終了)。

    Raises:
        TypeError: 数値の並びでない場合。
        ValueError: 値が2つでない場合、有限でない場合、または開始が終了より後の場合。
    """
    ...

def _driving_curves(owner: str, names: list[str] | None) -> list[str]:
    """対象のアトリビュートへ直接つながるアニメーションカーブを返す。

    間にある単位変換ノードは飛ばしてたどる。

    Args:
        owner (str): ノードのフルパス。
        names (list[str] | None): 焼き込んだアトリビュート名。Noneはキー設定可能なアトリビュート。

    Returns:
        list[str]: アニメーションカーブの名前。接続の順に並び、同じものは1回だけ含む。
    """
    ...

def _attribute_base(name: str) -> str:
    """アトリビュートのパスから、末尾のアトリビュート名を返す。

    論理番号は除く(``"weight[0]"`` は ``"weight"`` になる)。

    Args:
        name (str): アトリビュート名またはパス。

    Returns:
        str: 論理番号を除いた末尾のアトリビュート名。
    """
    ...
