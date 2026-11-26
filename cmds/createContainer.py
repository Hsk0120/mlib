"""containerを作り、指定したノードを所属させる(``cmds.container`` 相当)。"""

import maya.cmds as cmds

from ..decorator import _pick_alias, _require_bool, undoTransaction
from ..util import _UNSET


def createContainer(members=(), *, name=_UNSET, dag=False, n=_UNSET):
    """containerを作り、指定したノードを所属させる。

    作成のあとに ``addMembers`` を行うのと同じ。``cmds.container`` の規則(現在のcontainerへの自動での所属など)に従う。
    membersは作る前に確かめ、見つからないノードやほかのcontainerに入っているノードがあれば、何も作らずに例外にする。
    空のcontainerだけが必要なら ``mlib.createNode("container", name=...)`` でも作れる。
    ``dag=True`` ならDAGコンテナ(``cmds.container(type="dagContainer")``)を作る。
    fast引数は無い(cmds.containerと同じ機能がOpenMayaに無いため)。Undoが有効なら1回で戻せる。
    nameは ``cmds.container`` と同じ短縮名 ``n`` でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        members (str | Node | Iterable[Node | str]): 作ったあとに所属させるノード。省略すると空のまま。
        name (str): 付けたい名前。ほかのノードと重なる場合は、Mayaが重ならない名前に変える。
            既定は ``"container"``(``dag=True`` では ``"dagContainer"``)。
        dag (bool): True ならDAGコンテナを作る。
        n (str): nameの短縮名。nameと同時には指定できない。

    Returns:
        Container | DagContainer: 作ったcontainer。``dag=True`` ならDagContainer。

    Raises:
        TypeError: nameと短縮名 ``n`` を同時に指定した場合、またはdagがbool以外の場合。
        RuntimeError: membersに見つからないノードやほかのcontainerに入っているノードがある場合(何も作らない)、
            またはMayaが作成・所属を拒否した場合。

    Examples:
        >>> import mlib
        >>> owner = mlib.createContainer([node], name="arm_graph")
        >>> rig = mlib.createContainer([group], name="arm_rig", dag=True)
    """
    _require_bool(dag, "dag")
    name = _pick_alias(name, n, "name", "n", default="dagContainer" if dag else "container")
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.container import Container
    from ..nodes.node import Node

    # 作ってから失敗してUndoで戻すと、今の名前空間がルート以外のときにMayaが壊れることがあるため、作る前に確かめる。
    names = Container._resolve_new_members((members,))
    flags = {"type": "dagContainer"} if dag else {}
    with undoTransaction("mlibCreateDagContainer" if dag else "mlibCreateContainer"):
        container = Node(cmds.container(name=name, **flags))
        if names:
            cmds.container(container._full_name(), edit=True, addNode=names)
        return container
