"""子を入れたグループ(空のtransform)を作り、Transformを返す(``cmds.group`` 相当)。"""

import maya.cmds as cmds

from ..core.shapeBuild import require_name, resolve_parent
from ..decorator import _pick_alias, _require_bool, preservedSelection, undoTransaction
from ..util import _UNSET


def createGroup(children=(), name=_UNSET, parent=None, *, world=_UNSET, n=_UNSET, w=_UNSET):
    """子を入れたグループを作り、グループのTransformを返す。

    - childrenを省略すると、ワールド(またはparent)の直下に空のグループを作る(``cmds.group(empty=True)``)。
    - childrenを渡し、parentもworldも指定しなければ、Mayaと同じく子に共通する親の下に作る。

    子はワールドでの姿勢を保ったまま移し、グループのピボットはMayaと同じく、子のバウンディングボックスの中心に置く。
    現在の選択は変えない。fast引数は無い(OpenMayaで作っても効果がほぼ無いため)。Undoが有効なら1回で戻せる。
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
        >>> import mlib
        >>> offset = mlib.createGroup(["arm_CTRL"], name="arm_CTRL_offset")
        >>> empty = mlib.createGroup(name="rig_GRP")
        >>> # cmds.group と同じ短縮名でも指定できる。
        >>> world_group = mlib.createGroup(["hand_JNT"], n="hand_GRP", w=True)

        >>> offset = mlib.createGroup(ctrl, name=ctrl.getName() + "_offset")
        >>> offset.getChildren()[0] == ctrl
        True
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node
    from ..nodes.transform import Transform

    name = require_name(_pick_alias(name, n, "name", "n", default=None))
    world = _pick_alias(world, w, "world", "w", default=False)
    _require_bool(world, "world")
    if world and parent is not None:
        raise ValueError("parentとworld=Trueは同時に指定できません")
    if isinstance(children, (str, Node)):
        children = [children]
    nodes = []
    for child in children:
        node = Node._resolve_input(child)
        if not node.isValid():
            raise RuntimeError("childが有効なノードではありません")
        if not isinstance(node, Transform):
            raise TypeError(f"childはtransformで指定してください: {node.getFullName()}")
        nodes.append(node)
    paths = [node.getFullName() for node in nodes]
    if len(set(paths)) != len(paths):
        raise ValueError("childrenに同じノードを2回指定できません")
    parent_node = resolve_parent(parent)
    flags = {}
    if name:
        flags["name"] = name
    if parent_node is not None:
        flags["parent"] = parent_node.getFullName()
    elif world:
        flags["world"] = True
    with undoTransaction("mlibCreateGroup"), preservedSelection():
        if paths:
            group = cmds.group(paths, **flags)
        else:
            group = cmds.group(empty=True, **flags)
        # cmds.group は短い名前を返すため、選択(作成直後のグループ)から一意な名前を得る。
        selected = cmds.ls(selection=True, long=True)
        return Node(selected[0] if selected else group)
