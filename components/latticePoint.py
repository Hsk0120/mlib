"""ラティスの点と、点の集まり。"""

import maya.api.OpenMaya as om2

from .component import _MultiIndexComponent, _MultiIndexComponents
from .pointComponent import PointComponent, PointComponents


def _lattice_divisions(shape):
    """ラティスのS・T・U方向の分割数(点の数)を取得する。

    Args:
        shape (Node): 型を確かめてあるラティスのシェイプ。

    Returns:
        tuple[int, int, int]: (sDivisions, tDivisions, uDivisions)。
    """
    dependency = om2.MFnDependencyNode(shape.mnode())
    return tuple(dependency.findPlug(name, False).asInt() for name in ("sDivisions", "tDivisions", "uDivisions"))


class LatticePoint(_MultiIndexComponent, PointComponent):
    """ラティスの点1つを表すクラス。

    ラティスのShapeと点の番号(``pt[s][t][u]``)を持ち、今のXYZ座標を取得・編集する。

    - 持っている :attr:`index` は、``s + t * S + u * S * T`` の通し番号(S・Tは ``sDivisions``・``tDivisions``)。
      ``om2.MItGeometry`` の並びと同じになる。``(s, t, u)`` は :meth:`getMultiIndex` で取得する。
    - 座標の単位はcm。ラティスのシェイプのオブジェクト空間(既定のラティスは1辺1の立方体)か、ワールド空間で扱う。
    - 分割数を変えると、同じ番号が別の点を指すようになる。
    - 座標の取得・書き込み・反転は :class:`~mlib.components.pointComponent.PointComponent` と同じ。
      fastでは ``MItGeometry.setAllPositions`` を使う。
    """

    shape_type = "lattice"
    component_type = "pt"
    index_size = 3

    @classmethod
    def _element_count(cls, shape):
        """ラティスの点の数(``S * T * U``)を返す。

        Args:
            shape (Node): 型を確かめてあるラティスのシェイプ。

        Returns:
            int: 点の数。
        """
        s, t, u = _lattice_divisions(shape)
        return s * t * u

    @classmethod
    def _multi_indices(cls, shape, indices, command=False):  # noqa: ARG003  # 基底が command= で呼ぶ契約の引数。
        """通し番号を ``(s, t, u)`` へ変換する。

        Args:
            shape (Node): 型を確かめてあるラティスのシェイプ。
            indices (Iterable[int]): 範囲を確かめてある通し番号。
            command (bool): Trueならcmdsで使う番号にする。ラティスではどちらも同じ番号になる。

        Returns:
            list[tuple[int, int, int]]: ``(s, t, u)``。指定した順に並ぶ。
        """
        count_s, count_t, _ = _lattice_divisions(shape)
        result = []
        for index in indices:
            rest, s = divmod(index, count_s)
            u, t = divmod(rest, count_t)
            result.append((s, t, u))
        return result

    @classmethod
    def _flat_indices(cls, shape, numbers):
        """``(s, t, u)`` を通し番号へ変換する。

        Args:
            shape (Node): 型を確かめてあるラティスのシェイプ。
            numbers (Iterable[tuple[int, int, int]]): 0以上の ``(s, t, u)``。

        Returns:
            list[int]: 通し番号。指定した順に並ぶ。

        Raises:
            IndexError: 番号が分割数の範囲の外にある場合。
        """
        count_s, count_t, count_u = _lattice_divisions(shape)
        result = []
        for s, t, u in numbers:
            if s >= count_s or t >= count_t or u >= count_u:
                raise IndexError(f"コンポーネントの番号が範囲外です: {(s, t, u)}")
            result.append(s + (t + u * count_t) * count_s)
        return result


class LatticePoints(_MultiIndexComponents, PointComponents):
    """同じラティスにある点の集まりを表すクラス。

    点を1つずつ取り出したり、座標をまとめて扱ったりする。
    ``LatticePoints(shape)`` で全部の点を取得できる。
    番号の指定には、通し番号と ``(s, t, u)`` を混ぜて使える。名前は範囲にまとめない。
    """

    component_class = LatticePoint
