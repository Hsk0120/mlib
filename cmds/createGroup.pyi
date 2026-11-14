# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""子を入れたグループ(空のtransform)を作り、Transformを返す(``cmds.group`` 相当)。

子はワールドでの姿勢を保ったまま、グループの下へ移す。グループのピボットはMayaと同じく、
子のバウンディングボックスの中心に置く。作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。

.. code-block:: python

    import mlib

    offset = mlib.createGroup(["arm_CTRL"], name="arm_CTRL_offset")
    empty = mlib.createGroup(name="rig_GRP")

    # cmds.group と同じ短縮名でも指定できる。
    world_group = mlib.createGroup(["hand_JNT"], n="hand_GRP", w=True)
"""

import maya.cmds as cmds
from ..core.shapeBuild import require_name, resolve_parent
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoTransaction
from ..util import _UNSET
from typing import Iterable
from mlib.nodes.node import Node
from mlib.nodes.transform import Transform


def createGroup(children: Iterable[Node | str] | Node | str = ..., name: str | None = ..., parent: Node | str | None = ..., *, world: bool = ..., n: str | None = ..., w: bool = ...) -> Transform:
    """子を入れたグループを作り、グループのTransformを返す。

    - childrenを省略すると、ワールド(またはparent)の直下に空のグループを作る(``cmds.group(empty=True)``)。
    - childrenを渡し、parentもworldも指定しなければ、Mayaと同じく子に共通する親の下に作る。

    子はワールドでの姿勢を保ったまま移し、グループのピボットは子のバウンディングボックスの中心に置く。
    fast引数は無い(OpenMayaで作っても効果がほぼ無いため)。Undoが有効なら1回で戻せる。
    name・worldは ``cmds.group`` と同じ短縮名 ``n``・``w`` でも指定できる(長い名前と短縮名は同時に指定できない)。
    parentの短縮名は無い。

    Args:
        children (Iterable[Node | str] | Node | str): グループに入れるtransform。1つならそのまま渡せる。既定は空。
        name (str | None): グループに付けたい名前。NoneならMayaの既定の名前(``group1`` など)。既定はNone。
        parent (Node | str | None): グループの親のtransform。Noneなら指定しない。
        world (bool): Trueならワールド直下に作る。parentとは同時に指定できない。既定はFalse。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        w (bool): worldの短縮名。worldと同時には指定できない。

    Returns:
        Transform: 作ったグループ。

    Raises:
        TypeError: 長い名前と短縮名を同時に指定した場合、nameが文字列でもNoneでもない場合、
            worldがboolでない場合、childrenの要素やparentがtransformでない場合、または対応していない型の場合。
        ValueError: nameが空文字列か ``|`` を含む場合、parentとworld=Trueを同時に指定した場合、
            または同じ子を2回渡した場合。
        RuntimeError: 子や親が名前から見つからないか無効な場合や、親が子の子孫の場合など、
            Mayaが作成を拒否した場合。

    Examples:
        >>> offset = mlib.createGroup(ctrl, name=ctrl.getName() + "_offset")
        >>> offset.getChildren()[0] == ctrl
        True
    """
    ...
