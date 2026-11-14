# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ポリゴンの平面を作り、シェイプを返す(``cmds.polyPlane(constructionHistory=False)`` 相当)。"""

import maya.cmds as cmds
from ..core.shapeBuild import create_poly, positive_size, require_name, resolve_parent, subdivision_counts
from ..decorator import _pick_alias
from ..util import _UNSET, _finite_vector
from typing import Sequence
from mlib.nodes.mesh import Mesh
from mlib.nodes.node import Node


def createPolyPlane(width: float = ..., height: float = ..., subdivisions: Sequence[int] = ..., axis: Sequence[float] = ..., name: str | None = ..., parent: Node | str | None = ..., *, w: float = ..., h: float = ..., ax: Sequence[float] = ..., n: str | None = ...) -> Mesh:
    """原点を中心とするポリゴンの平面を作り、そのシェイプを返す。

    大きさはMaya APIの内部単位(cm)で指定し、現在のUI単位には左右されない。コンストラクションヒストリは作らない。
    作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。
    fast引数は無い(Mayaのコマンドと同じUV・法線のメッシュをOpenMayaで組み立て直すことになり、同じ結果を保つのが難しいため)。
    width・height・axis・nameは ``cmds.polyPlane`` と同じ短縮名でも指定できる(長い名前と短縮名は同時に指定できない)。
    subdivisionsは ``subdivisionsX/Y`` をまとめたmlib独自の引数のため、短縮名は無い。

    Args:
        width (float): 幅(cm)。既定は1。
        height (float): 高さ(奥行き方向の長さ、cm)。既定は1。
        subdivisions (Sequence[int]): 幅・高さ方向の分割数(``subdivisionsX/Y``)。既定は(10, 10)。
        axis (Sequence[float]): 面の法線。0でない有限な3成分。既定は(0, 1, 0)。
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前。既定はNone。
        parent (Node | str | None): Transformの親。Noneならワールド直下。
            親のローカル空間に、単位マトリクスで置く。
        w (float): widthの短縮名。widthと同時には指定できない。
        h (float): heightの短縮名。heightと同時には指定できない。
        ax (Sequence[float]): axisの短縮名。axisと同時には指定できない。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        Mesh: 作ったメッシュのシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、または引数の型が正しくない場合。
        ValueError: 大きさが0以下か有限でない場合、または分割数や軸が正しくない場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> shape = mlib.createPolyPlane(width=10.0, height=10.0, subdivisions=(4, 4), name="floor")
        >>> transform = shape.getTransform()
    """
    ...

def _axis(value: Sequence[float]) -> tuple[float, float, float]:
    """軸の方向を確かめる。

    Args:
        value (Sequence[float]): 方向。

    Returns:
        tuple[float, float, float]: 確かめた方向。

    Raises:
        TypeError: 数値の並びでない場合。
        ValueError: 成分が3つでない場合、有限でない場合、または0の場合。
    """
    ...
