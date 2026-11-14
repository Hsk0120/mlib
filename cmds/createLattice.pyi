# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""形状やコンポーネントにラティス(ffdデフォーマー)を作り、ffdを返す(``cmds.lattice`` 相当)。"""

import maya.cmds as cmds
from ..core.object import Object
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoChunk
from ..util import _UNSET
from typing import Iterable, Sequence
from mlib.components.component import Component
from mlib.nodes.geometryFilter import GeometryFilter
from mlib.nodes.node import Node


def _divisions(value: Sequence[int], name: str, minimum: int) -> tuple[int, int, int]:
    """3つの整数の分割数を確かめる。

    Args:
        value (Sequence[int]): S・T・U方向の分割数。
        name (str): 例外メッセージに使う引数名。
        minimum (int): 各値の下限。

    Returns:
        tuple[int, int, int]: 確かめた分割数。

    Raises:
        TypeError: 並びでない場合、または値がintでない場合(boolもintとして扱わない)。
        ValueError: 値の数が3でない場合、または下限より小さい場合。
    """
    ...

def createLattice(targets: str | Node | Component | Iterable, name: str | None = ..., divisions: Sequence[int] = ..., ldivisions: Sequence[int] = ..., objectCentered: bool = ..., *, n: str | None = ..., dv: Sequence[int] = ..., ldv: Sequence[int] = ..., oc: bool = ...) -> GeometryFilter:
    """形状またはコンポーネントにラティスを作り、ffdデフォーマーを返す。

    ラティスは対象を囲む大きさで作る。ラティスの形状は ``deformedLatticePoints`` の入力元に、
    基準のラティスは ``baseLatticeMatrix`` の入力元につながる。選択状態は使わず、現在の選択は変えない。
    fast引数は無い(OpenMayaにデフォーマーを作る同じ機能が無いため)。Undoが有効なら1回で戻せる。
    name・divisions・ldivisions・objectCenteredは ``cmds.lattice`` と同じ短縮名 ``n``・``dv``・``ldv``・``oc``
    でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        targets (str | Node | Component | Iterable): 変形する形状・そのtransform・コンポーネント。
        name (str | None): ffdに付ける名前。ラティスは ``<名前>Lattice``、基準は ``<名前>Base`` になる。
            NoneならMayaの既定の名前。既定はNone。
        divisions (Sequence[int]): ラティスのS・T・U方向の点の数。どれも2以上。既定は(2, 5, 2)。
        ldivisions (Sequence[int]): 変形の計算に使う、局所的な分割数。どれも1以上。既定は(2, 2, 2)。
        objectCentered (bool): Trueなら対象の中心に置く。Falseなら原点に置く。既定はTrue。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        dv (Sequence[int]): divisionsの短縮名。divisionsと同時には指定できない。
        ldv (Sequence[int]): ldivisionsの短縮名。ldivisionsと同時には指定できない。
        oc (bool): objectCenteredの短縮名。objectCenteredと同時には指定できない。

    Returns:
        GeometryFilter: 作ったffdデフォーマー。実際の型は、Mayaの ``ffd`` 型から作ったクラス(``mlib.nodes.Ffd``)。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、または引数の型が正しくない場合。
        ValueError: nameが空文字列か ``|`` を含む場合、分割数の個数や値が正しくない場合、
            または対象が空か無効な場合。
        RuntimeError: 名前からノードが見つからない場合、またはMayaが作成を拒否した場合。

    Examples:
        >>> import mlib
        >>> ffd = mlib.createLattice("head_geo", divisions=(3, 4, 3), name="head_ffd")
        >>> lattice = ffd.getPlug("deformedLatticePoints").getSource().getNode()

        >>> ffd = mlib.createLattice(["arm_geo", "hand_geo"], dv=(2, 6, 2), oc=True)
        >>> base = ffd.getPlug("baseLatticeMatrix").getSource().getNode()
    """
    ...
