# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""アニメーションカーブのキーを、「カーブ + キーの番号」で指すオブジェクトとして扱う。

:class:`Keyframe` は1つのキー、:class:`Keyframes` は複数のキー(複数のカーブにまたがってよい)を表す。

- 頂点(:class:`~mlib.components.vertex.Vertex`)と同じく、作ったときの番号を持ち続ける。
  キーを追加・削除したり、入力の順が入れ替わったりしたあとも同じキーを指すことは保証しない。
- ドリブンキーのカーブ(入力が時間でない animCurveU*)のキーも同じクラスで扱う。
  その場合の「時刻」は、カーブの入力の値を指す。
- 値と時刻の単位は :class:`~mlib.nodes.animCurve.AnimCurve` と同じ(角度は度、距離はcm、時間はフレーム)。

.. code-block:: python

    import mlib
    from mlib.common import Selection

    for curve, keys in Selection.getKeyframes().iterCurves():
        print(curve, [key.getValue() for key in keys])
    mlib.getNode("pCube1_translateX").getKeyframe(0).setValue(5)
"""

import maya.cmds as cmds
from ..decorator import _require_bool, undoChunk
from typing import Iterator
from mlib.nodes.animCurve import AnimCurve



class Keyframe:
    """アニメーションカーブの1つのキーを指すオブジェクト。

    Args:
        curve (AnimCurve): キーを持つカーブ。
        index (int): 0始まりのキー番号。

    Raises:
        TypeError: curveがAnimCurveでない場合。
        IndexError: indexがキーの数の範囲にない場合。
    """
    __slots__: tuple
    def __init__(self, curve, index) -> None: ...
    def __eq__(self, other):
        """同じカーブの同じ番号を指すか比較する。

        Args:
            other: 比較の相手。
        """
        ...
    def __hash__(self):
        """カーブと番号のハッシュを返す。"""
        ...
    def __repr__(self):
        """``Keyframe('pCube1_translateX', 3)`` の形で表示する。"""
        ...
    def getCurve(self) -> AnimCurve:
        """キーを持つカーブを返す。

        Returns:
            AnimCurve: 保持しているカーブ。
        """
        ...
    def getIndex(self) -> int:
        """キーの番号を返す。

        Returns:
            int: 作成時の0始まりのキー番号。
        """
        ...
    def isValid(self) -> bool:
        """カーブが有効で、番号がキーの数の範囲内にあるか調べる。

        Returns:
            bool: 有効ならTrue。番号が同じキーを指し続けているかまでは確かめない。
        """
        ...
    def getTime(self, *, timeUnit: str = ...) -> float:
        """キーの入力(時刻、またはドリブンキーの入力の値)を返す。

        Args:
            timeUnit (str): 入力が時間(T型)のときの単位。``"frame"`` / ``"sec"``。

        Returns:
            float: 入力の値。

        Raises:
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        ...
    def getValue(self, *, unit: str = ..., timeUnit: str = ...) -> float:
        """キーの値を返す。

        Args:
            unit (str): 出力が角度(A型)のときの単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 出力が時間のときの単位。``"frame"`` / ``"sec"``。

        Returns:
            float: 値。

        Raises:
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        ...
    def setValue(self, value: float, *, unit: str = ..., timeUnit: str = ..., fast: bool = ...) -> Keyframe:
        """キーの値を、接線の型を保ったまま変える。

        Args:
            value (float): 新しい値(:meth:`getValue` と同じ単位)。
            unit (str): 出力が角度(A型)のときの単位。``"deg"`` / ``"rad"``。
            timeUnit (str): 出力が時間のときの単位。``"frame"`` / ``"sec"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Keyframe: 自身。

        Raises:
            TypeError: 数値に変換できない型の場合、またはfastがboolでない場合。
            ValueError: 値が有限でない場合、または単位名に対応していない場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        ...
    def getTangent(self, *, unit: str = ...) -> dict:
        """接線の型・角度・ウェイト・ロックを返す。

        :meth:`AnimCurve.getTangent <mlib.nodes.animCurve.AnimCurve.getTangent>` と同じ。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。

        Returns:
            dict: AnimCurve.getTangent と同じ辞書。
        """
        ...
    def setTangent(self, *, unit: str = ..., fast: bool = ..., **kwargs) -> Keyframe:
        """接線を変える。

        :meth:`AnimCurve.setTangent <mlib.nodes.animCurve.AnimCurve.setTangent>` と同じ。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            **kwargs: AnimCurve.setTangent と同じフラグ。

        Returns:
            Keyframe: 自身。
        """
        ...
    def isBreakdown(self) -> bool:
        """ブレイクダウンキーか調べる。

        :meth:`AnimCurve.isBreakdown <mlib.nodes.animCurve.AnimCurve.isBreakdown>` と同じ。

        Returns:
            bool: ブレイクダウンキーならTrue。

        Raises:
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        ...
    def setBreakdown(self, state: bool = ...) -> Keyframe:
        """ブレイクダウンキーにする、または通常のキーへ戻す。

        :meth:`AnimCurve.setBreakdown <mlib.nodes.animCurve.AnimCurve.setBreakdown>` と同じ。

        Args:
            state (bool): Trueならブレイクダウンキー、Falseなら通常のキーにする。既定はTrue。

        Returns:
            Keyframe: 自身。

        Raises:
            TypeError: stateがboolでない場合。
            IndexError: 番号がキーの数の範囲から外れた場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        ...
    def move(self, *, timeOffset: float = ..., valueOffset: float = ..., unit: str = ..., timeUnit: str = ...) -> Keyframe:
        """キーの入力と値をずらす。

        :meth:`AnimCurve.moveKey <mlib.nodes.animCurve.AnimCurve.moveKey>` と同じ。
        入力は隣のキーを越えない(Mayaの ``keyframe -relative`` と同じ)。番号は変わらない。

        Args:
            timeOffset (float): 入力をずらす量。
            valueOffset (float): 値をずらす量。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 時間の単位。

        Returns:
            Keyframe: 自身。
        """
        ...
    def remove(self, *, keepCurve: bool = ..., fast: bool = ...) -> None:
        """キーを削除する。

        削除したあとは、同じカーブでこれより後ろの番号を持つオブジェクトが、別のキーを指すようになる。

        Args:
            keepCurve (bool): Trueなら、最後のキーを消してもカーブを残す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。
        """
        ...
    def select(self, *, add: bool = ...) -> Keyframe:
        """Graph Editor・Dope Sheet でこのキーを選択する。

        Args:
            add (bool): Trueなら今のキーの選択に加える。Falseなら置き換える。

        Returns:
            Keyframe: 自身。
        """
        ...
    def _require_valid(self):
        """カーブが有効で、番号が範囲内であることを確かめる。"""
        ...


class Keyframes:
    """キーの集まり。

    複数のカーブにまたがってよい。カーブは最初に出てきた順に、カーブの中のキーは番号の小さい順に並べて持つ。

    Args:
        keyframes (Iterable[Keyframe]): キーのオブジェクト。同じキーは1つにまとめる。

    Raises:
        TypeError: Keyframeでないものを含む場合。
    """
    __hash__: None
    def __init__(self, keyframes=...) -> None: ...
    def __len__(self):
        """キーの数を返す。"""
        ...
    def __iter__(self):
        """カーブごとに、番号の小さい順で :class:`Keyframe` を返す。"""
        ...
    def __getitem__(self, index: int) -> Keyframe:
        """位置で :class:`Keyframe` を返す。

        Args:
            index (int): 並びの位置。負の値なら末尾から数える。

        Returns:
            Keyframe: その位置のキー。
        """
        ...
    def __contains__(self, item):
        """同じカーブの同じ番号を含むか返す。"""
        ...
    def __eq__(self, other):
        """同じカーブと番号の組を、同じ順で持つか比べる。"""
        ...
    def __repr__(self):
        """``Keyframes(count=4, curves=2)`` の形で表示する。"""
        ...
    def getCurves(self) -> list[AnimCurve]:
        """キーを持つカーブを返す。

        Returns:
            list[AnimCurve]: カーブ(最初に出てきた順。同じものは1回だけ)。
        """
        ...
    def iterCurves(self) -> Iterator[tuple[AnimCurve, Keyframes]]:
        """カーブごとに、そのカーブのキーの集まりを返す。

        Yields:
            tuple[AnimCurve, Keyframes]: カーブと、そのカーブのキー(番号の小さい順)。
        """
        ...
    def getIndices(self, curve: AnimCurve) -> list[int]:
        """指定したカーブのキーの番号を返す。

        Args:
            curve (AnimCurve): カーブ。

        Returns:
            list[int]: 番号(小さい順)。このカーブのキーが無ければ空。
        """
        ...
    def getTimes(self, *, timeUnit: str = ...) -> list[float]:
        """各キーの入力を返す(並びはforで取り出す順と同じ)。

        Args:
            timeUnit (str): 入力が時間(T型)のときの単位。

        Returns:
            list[float]: 入力の値。
        """
        ...
    def getValues(self, *, unit: str = ..., timeUnit: str = ...) -> list[float]:
        """各キーの値を返す(並びはforで取り出す順と同じ)。

        Args:
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 出力が時間のときの単位。

        Returns:
            list[float]: 値。
        """
        ...
    def setValue(self, value: float, *, unit: str = ..., timeUnit: str = ..., fast: bool = ...) -> Keyframes:
        """すべてのキーに同じ値を書き込む(1回のUndoで戻せる)。

        Args:
            value (float): 新しい値。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 出力が時間のときの単位。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Keyframes: 自身。
        """
        ...
    def setTangent(self, *, unit: str = ..., fast: bool = ..., **kwargs) -> Keyframes:
        """すべてのキーの接線を変える(1回のUndoで戻せる)。引数は :meth:`Keyframe.setTangent` と同じ。

        fast=Trueでも全体を1つのUndoチャンクの中で呼ぶ。ただし、OpenMayaでの更新はUndoに記録されない。

        Args:
            unit (str): 角度の単位。``"deg"`` / ``"rad"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            **kwargs: :meth:`AnimCurve.setTangent <mlib.nodes.animCurve.AnimCurve.setTangent>` と同じフラグ。

        Returns:
            Keyframes: 自身。

        Raises:
            TypeError: unitが文字列でもNoneでもない場合。
            ValueError: フラグが空か知らないものの場合、unitに対応していない場合、
                またはfastで正しくない値や、global・知らない接線の型を指定した場合。
            IndexError: キーの番号が正しくない場合。
            RuntimeError: カーブが無効(削除済み)の場合。
            NotImplementedError: fastで、入力側の接線にstepnextを指定した場合。
        """
        ...
    def move(self, *, timeOffset: float = ..., valueOffset: float = ..., unit: str = ..., timeUnit: str = ...) -> Keyframes:
        """すべてのキーの入力と値をずらす。

        カーブごとに1回で動かし、全体を1回のUndoで戻せる。
        同じカーブの対象のキーどうしは一緒に動くため、互いを越えられない制限は受けない。

        Args:
            timeOffset (float): 入力をずらす量。
            valueOffset (float): 値をずらす量。
            unit (str): 出力が角度のときの単位。
            timeUnit (str): 時間の単位。

        Returns:
            Keyframes: 自身。
        """
        ...
    def remove(self, *, keepCurve: bool = ..., fast: bool = ...) -> None:
        """すべてのキーを削除する(1回のUndoで戻せる)。

        削除したあとは、この集まりのオブジェクトが別のキーを指すことがある。

        Args:
            keepCurve (bool): Trueなら、すべてのキーを消してもカーブを残す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。
        """
        ...
    def select(self, *, add: bool = ...) -> Keyframes:
        """Graph Editor・Dope Sheet でこれらのキーを選択する。

        空の集まりで add=False なら、キーの選択を外す。

        Args:
            add (bool): Trueなら今のキーの選択に加える。Falseなら置き換える。

        Returns:
            Keyframes: 自身。

        Raises:
            TypeError: addがboolでない場合。
            RuntimeError: カーブが無効(削除済み)の場合。
        """
        ...

def _keyframe(curve, index):
    """確認を省いて :class:`Keyframe` を作る(番号を確認済みの集まりから取り出すときに使う)。"""
    ...
