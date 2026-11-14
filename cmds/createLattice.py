"""形状やコンポーネントにラティス(ffdデフォーマー)を作り、ffdを返す(``cmds.lattice`` 相当)。

ラティスの形状は ``deformedLatticePoints`` の入力元に、基準のラティスは ``baseLatticeMatrix`` の入力元に
つながる。作成は1回のUndoにまとめ、現在の選択は変えない。

.. code-block:: python

    import mlib

    ffd = mlib.createLattice("head_geo", divisions=(3, 4, 3), name="head_ffd")
    lattice = ffd.getPlug("deformedLatticePoints").getSource().getNode()
"""

import maya.cmds as cmds

from ..core.object import Object
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoChunk
from ..util import _UNSET


def _divisions(value, name, minimum):
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
    if isinstance(value, (str, bytes)):
        raise TypeError(f"{name}は3つのintの並びで指定してください")
    try:
        values = tuple(value)
    except TypeError:
        raise TypeError(f"{name}は3つのintの並びで指定してください: {type(value).__name__}") from None
    if len(values) != 3:
        raise ValueError(f"{name}は3つの値で指定してください: {len(values)}個")
    for item in values:
        if isinstance(item, bool) or not isinstance(item, int):
            raise TypeError(f"{name}の要素はintで指定してください: {type(item).__name__}")
        if item < minimum:
            raise ValueError(f"{name}の値は{minimum}以上で指定してください: {item}")
    return values


def createLattice(targets, name=_UNSET, divisions=_UNSET, ldivisions=_UNSET, objectCentered=_UNSET, *, n=_UNSET, dv=_UNSET, ldv=_UNSET, oc=_UNSET):
    """形状またはコンポーネントにラティスを作り、ffdデフォーマーを返す。

    選択状態は使わない。ラティスは対象を囲む大きさで作る。
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
        .. code-block:: python

            ffd = mlib.createLattice(["arm_geo", "hand_geo"], dv=(2, 6, 2), oc=True)
            base = ffd.getPlug("baseLatticeMatrix").getSource().getNode()
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    name = require_name(_pick_alias(name, n, "name", "n", default=None))
    divisions = _divisions(_pick_alias(divisions, dv, "divisions", "dv", default=(2, 5, 2)), "divisions", 2)
    ldivisions = _divisions(_pick_alias(ldivisions, ldv, "ldivisions", "ldv", default=(2, 2, 2)), "ldivisions", 1)
    objectCentered = _pick_alias(objectCentered, oc, "objectCentered", "oc", default=True)
    _require_bool(objectCentered, "objectCentered")
    target_names = Object._input_names(targets, allow_plugs=False)
    if not target_names:
        raise ValueError("ターゲットを1つ以上指定してください")
    flags = {"divisions": divisions, "ldivisions": ldivisions, "objectCentered": objectCentered}
    if name is not None:
        flags["name"] = name
    with undoChunk("mlibCreateLattice"), preservedSelection():
        result = cmds.lattice(*target_names, **flags)
        return Node(result[0])
