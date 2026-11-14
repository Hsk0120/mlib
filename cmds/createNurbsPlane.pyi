# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""NURBSの平面を作り、シェイプを返す(``cmds.nurbsPlane(constructionHistory=False)`` 相当)。

幅はMaya APIの内部単位(cm)で指定し、現在のUI単位には左右されない。コンストラクションヒストリは作らない。
作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。リボンの元になる面などに使う。

.. code-block:: python

    import mlib

    shape = mlib.createNurbsPlane(width=10.0, lengthRatio=0.1, patchesU=5, name="ribbon")
    shape = mlib.createNurbsPlane(w=10.0, lr=0.1, u=5, n="ribbon")  # cmds.nurbsPlane と同じ短縮名
"""

import maya.cmds as cmds
from ..core.shapeBuild import finish_shape, positive_size, require_name, resolve_parent
from ..decorator import _pick_alias, nativeUnits, preservedSelection, undoTransaction
from ..util import _UNSET, _finite_vector
from typing import Sequence
from mlib.nodes.node import Node
from mlib.nodes.nurbsSurface import NurbsSurface


def createNurbsPlane(width: float = ..., lengthRatio: float = ..., patchesU: int = ..., patchesV: int = ..., axis: Sequence[float] = ..., degree: int = ..., name: str | None = ..., parent: Node | str | None = ..., *, w: float = ..., lr: float = ..., u: int = ..., v: int = ..., ax: Sequence[float] = ..., d: int = ..., n: str | None = ...) -> NurbsSurface:
    """原点を中心とするNURBSの平面を作り、そのシェイプを返す。

    fast引数は無い(OpenMayaでは同じノット・CVの面を組み立て直すことになり、同じ結果を保つのが難しいため)。
    parent以外は ``cmds.nurbsPlane`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。
    U方向が幅(width)、V方向が長さ(``width * lengthRatio``)になる。

    Args:
        width (float): 幅(cm)。正の有限な値。既定は1。
        lengthRatio (float): 幅に対する長さの比。正の有限な値。既定は1。
        patchesU (int): U方向のパッチ(スパン)の数。1以上。既定は1。
        patchesV (int): V方向のパッチ(スパン)の数。1以上。既定は1。
        axis (Sequence[float]): 面の法線。0でない有限な3成分。既定は(0, 1, 0)。
            ``cmds.nurbsPlane`` の既定とは違い、:func:`createPolyPlane <mlib.cmds.createPolyPlane.createPolyPlane>`
            と同じ上向きにしている。
        degree (int): U・V方向の次数。1(直線)または3(曲線)。既定は3。
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前(``nurbsPlane1`` など)。既定はNone。
        parent (Node | str | None): Transformの親。Noneならワールド直下。
            親のローカル空間に、単位マトリクスで置く。
        w (float): widthの短縮名。widthと同時には指定できない。
        lr (float): lengthRatioの短縮名。lengthRatioと同時には指定できない。
        u (int): patchesUの短縮名。patchesUと同時には指定できない。
        v (int): patchesVの短縮名。patchesVと同時には指定できない。
        ax (Sequence[float]): axisの短縮名。axisと同時には指定できない。
        d (int): degreeの短縮名。degreeと同時には指定できない。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        NurbsSurface: 作った平面のシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、または引数の型が正しくない場合。
        ValueError: 幅や比が0以下か有限でない場合、またはパッチの数・軸・次数が正しくない場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。
    """
    ...

def _patch_count(value: int, name: str) -> int:
    """パッチの数を確かめる。

    Args:
        value (int): パッチの数。boolは受け付けない。
        name (str): 例外メッセージに使う引数名。

    Returns:
        int: 確かめたパッチの数。

    Raises:
        TypeError: intでない場合。
        ValueError: 1より小さい場合。
    """
    ...
