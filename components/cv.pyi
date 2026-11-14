# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""NURBS カーブの CV と CV コレクション。"""

from ..core.geometryEdit import command_indices
from .pointComponent import PointComponent, PointComponents
from typing import Any, Iterator
from typing import overload



class CV(PointComponent):
    """NURBSカーブのCV1つを表すクラス。

    NurbsCurveのShapeと、OpenMayaでのCVの番号を持つ。
    NurbsSurfaceのCV(番号が2つあるもの)は扱わない(SurfaceCVを使う)。

    周期カーブでも、番号はnumCVsの範囲のAPIの番号で持つ。
    cmdsへ渡す名前では、末尾で重なっているCVを、先頭側の同じCVの番号に直す。
    """
    shape_type: str
    component_type: str
    count_attribute: str
    def getFullName(self) -> str:
        """cmdsへ渡すCVの名前を返す。

        周期カーブの末尾で重なっているCVは、先頭側の同じCVの番号に直す。

        Returns:
            str: 同じ位置を編集できるMayaのコンポーネント名。indexはAPIの番号のまま変わらない。
        """
        ...


class CVs(PointComponents):
    """同じNURBSカーブにあるCVの集まりを表すクラス。

    CVを1つずつ取り出したり、座標をまとめて扱ったりする。
    番号はOpenMayaの番号で、持っている順を保つ。

    周期カーブの末尾と先頭のCVは、APIでは別の番号として持てる。
    ただしcmdsへ渡す名前では、同じCVの番号になることがある。そのため、名前は範囲にまとめない。
    """
    def __iter__(self) -> Iterator[CV]: ...
    @overload
    def __getitem__(self, index: int) -> CV: ...
    @overload
    def __getitem__(self, index: slice) -> CVs: ...
    component_class: Any
    def getFullNames(self) -> list[str]:
        """cmdsへ渡すCVの名前を、持っている順に返す。

        周期カーブの末尾で重なっているCVは、先頭側の同じCVの名前になる。

        Returns:
            list[str]: 持っている順のMayaのコンポーネント名。indicesはAPIの番号のまま変わらない。

        Raises:
            TypeError: シェイプの種類がNurbsCurveでない場合。
            IndexError: 持っている番号が、今のCVの範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getCompactNames(self) -> list[str]:
        """cmdsへ渡すCVの名前を返す。

        周期カーブのCVの対応を保つため、範囲にはまとめない。

        Returns:
            list[str]: getFullNamesと同じ、持っている順のMayaのコンポーネント名。

        Raises:
            TypeError: シェイプの種類がNurbsCurveでない場合。
            IndexError: 持っている番号が、今のCVの範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def _repr_indices(self) -> list[int]:
        """reprに表示する番号を、cmdsで使うCVの番号に直して返す。

        周期カーブの末尾で重なっているCVは、先頭側のCVと同じ名前になるので、表示では重なりを除く。

        Returns:
            list[int]: 表示用の番号。持っている順に並び、重なりは除く。
        """
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.cv.CV.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
