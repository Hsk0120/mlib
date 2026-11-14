# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""形状の座標を取得・設定する処理。通常はcmdsを使い、fastはヒストリの無い形状へ直接書き込む。"""

from collections import namedtuple
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..maths.vector import _vectors_of_points
from ..util import _finite_vector
from .fastWrite import require_writable
from typing import Any, Iterable, NamedTuple, Sequence
from mlib.maths.vector import Vector
from mlib.nodes.mesh import Mesh
from mlib.nodes.nurbsCurve import NurbsCurve
from mlib.nodes.shape import Shape

_OM2_POINTS: tuple

class _Geometry(NamedTuple):
    path: Any
    fn: Any
    is_mesh: Any

def geometry(shape: Mesh | NurbsCurve, indices: Iterable[int], edit: bool = ...) -> _Geometry:
    """ShapeのDAGパスと関数セットを取得する。

    edit=Trueなら、直接書き込めるかどうかも調べる。
    Shapeの型と番号の範囲は、呼び出し側で確かめてあるものとする。

    edit=Trueで調べる内容は次のとおり。

    - inMesh・createへの入力と、Shapeノードのロック。
    - 指定した点のpnts・controlPointsとその子について、上の階層を含むロックと入力接続、
      それぞれのアトリビュートへ書き込めるかどうか。
    - 周期カーブでは、指定した独立CVに重なる末尾の重複CVも調べる。
    - indicesが空のUV更新では、点のPlugごとの検査はしない。

    Args:
        shape (Mesh | NurbsCurve): 型が決まっているShapeのオブジェクト。
        indices (Iterable[int]): 範囲を確かめてあるAPIの点番号。UVの番号ではない。
        edit (bool): Trueなら直接書き込むときの制限を調べる。Falseは取得だけに使う。

    Returns:
        _Geometry: ``path`` (このオブジェクトが持つDAGパス)・``fn`` (MFnMeshまたはMFnNurbsCurve)・``is_mesh`` (MeshならTrue)
            のnamedtuple。tupleとして展開できる。関数セットを取得するだけでは座標を書き換えない。

    Raises:
        RuntimeError: 直接書き込むときにロック・入力接続・書き込み禁止がある場合、またはShapeを参照できない場合。
        NotImplementedError: edit=Trueで、inMesh・createへの入力がある場合。
    """
    ...

def _points(shape: Shape, indices: Sequence[int], ws: bool = ...) -> Iterable[om2.MPoint]:
    """指定した点をom2.MPointで取得する。

    点は指定した順に並ぶ。1点だけのときは、すべての点を取得しない。

    Args:
        shape (Shape): 有効なMeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある点番号。
        ws (bool): Trueならワールド空間へ変換する。

    Returns:
        Iterable[om2.MPoint]: 指定順の点。距離はcm。
    """
    ...

def positions(shape: Shape, indices: Sequence[int], ws: bool = ...) -> list[tuple[float, float, float]]:
    """指定した点の座標をtupleで取得する。

    内部の座標計算に使う。単位はcmで、指定した順に並ぶ。

    Args:
        shape (Shape): 有効なMeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある点番号。
        ws (bool): Trueならワールド空間へ変換する。

    Returns:
        list[tuple[float, float, float]]: 指定した順の座標。1点だけのときは、すべての点を取得しない。
    """
    ...

def vectors(shape: Shape, indices: Sequence[int], ws: bool = ...) -> list[Vector]:
    """指定した点の座標を :class:`~mlib.maths.vector.Vector` で取得する。

    単位はcmで、指定した順に並ぶ。

    Args:
        shape (Shape): 有効なMeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある点番号。
        ws (bool): Trueならワールド空間へ変換する。

    Returns:
        list[Vector]: 指定した順の新しい座標。CVのwでは割らない。
    """
    ...

def command_indices(shape: Shape, indices: Sequence[int]) -> list[int]:
    """APIの点番号を、cmdsで使う番号へ置き換える。

    番号の順番と重複はそのまま保つ。

    Args:
        shape (Shape): MeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてあるAPIの番号。

    Returns:
        list[int]: cmds用の番号。周期カーブでは、末尾の重複CVを先頭の独立CVの番号に置き換える。
    """
    ...

def set_positions(shape: Shape, indices: Sequence[int], values: Sequence[Sequence[float]], ws: bool = ..., *, fast: bool = ...) -> None:
    """点の座標を書き込む。

    座標はcmで、確かめてあるものを渡す。Undoのまとまりは呼び出し元が管理する。

    Args:
        shape (Shape): MeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてあるAPIの番号。同じ番号が重なれば、後の値が残る。
        values (Sequence[Sequence[float]]): 番号と同じ数の、有限なXYZ。
        ws (bool): Trueならワールド座標として扱う。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: Mayaが書き込みを拒否した場合。すでに済んだ変更は元に戻さない。
        NotImplementedError: fastで、対応していない形状の場合。
    """
    ...

def _set_positions_fast(shape: Shape, indices: Sequence[int], values: Sequence[Sequence[float]], ws: bool = ...) -> None:
    """点の座標をOpenMayaでまとめて設定する。

    座標はcmで、確かめてあるものを渡す。CVのwは変えない。

    Args:
        shape (Shape): ヒストリの無いMeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある番号。
        values (Sequence[Sequence[float]]): 設定するXYZ。
        ws (bool): TrueならAPIのワールド座標、Falseならローカル座標として扱う。

    Returns:
        None: 値を返さない。

    Raises:
        ValueError: ワールド空間で、変換マトリクスが特異な(逆マトリクスを持たない)場合。
        RuntimeError: ロック・入力接続・書き込み禁止がある場合。
        NotImplementedError: 入力ヒストリのある形状の場合。
    """
    ...

def object_positions(shape: Shape, indices: Sequence[int], values: Sequence[Sequence[float]]) -> list[tuple[float, float, float]]:
    """APIのワールド座標を、ローカルのXYZへ変換する。

    CVのウェイト(w)はそのまま保つ。

    Args:
        shape (Shape): MeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある番号。
        values (Sequence[Sequence[float]]): APIのワールドXYZ。距離はcm。

    Returns:
        list[tuple[float, float, float]]: cmdsのobjectSpaceへ渡すcmの座標。

    Raises:
        ValueError: ワールドマトリクスが特異な(逆マトリクスを持たない)場合。
    """
    ...

def point_list(points: Iterable[Sequence[float] | om2.MPoint | om2.MVector]) -> list[tuple[float, float, float]]:
    """点の並びを、XYZのfloatのtupleのリストへ変換する。

    変換する前に、点の並びとして正しいかを確かめる。

    Args:
        points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): 点の並び。

    Returns:
        list[tuple[float, float, float]]: 変換済みの点。

    Raises:
        TypeError: 点の並びを順に取り出せない場合、または点や成分の型が正しくない場合。
        ValueError: 成分の数が3でない場合、または有限の値でない場合。
    """
    ...
