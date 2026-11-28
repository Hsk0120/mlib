# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""containerを作り、指定したノードを所属させる(``cmds.container`` 相当)。"""

import maya.cmds as cmds
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias, _require_bool, undoTransaction
from ..util import _UNSET
from typing import Iterable, Literal
from mlib.nodes.container import Container
from mlib.nodes.dagContainer import DagContainer
from mlib.nodes.node import Node
from typing import overload


@overload
def createContainer(members: Node | str | Iterable[Node | str] | None = ..., *, name: str | None = ..., n: str | None = ..., dag: Literal[True]) -> DagContainer: ...
@overload
def createContainer(members: Node | str | Iterable[Node | str] | None = ..., *, name: str | None = ..., n: str | None = ..., dag: Literal[False] = ...) -> Container: ...
@overload
def createContainer(members: Node | str | Iterable[Node | str] | None = ..., *, name: str | None = ..., n: str | None = ..., dag: bool = ...) -> Container | DagContainer:
    """containerを作り、指定したノードを所属させる。

    作成のあとに ``addMembers`` を行うのと同じ。``cmds.container`` の規則(現在のcontainerへの自動での所属など)に従う。
    membersは作る前に確かめ、見つからないノードやほかのcontainerに入っているノードがあれば、何も作らずに例外にする。
    空のcontainerだけが必要なら ``mlib.createNode("container", name=...)`` でも作れる。
    ``dag=True`` ならDAGコンテナ(``cmds.container(type="dagContainer")``)を作る。
    fast引数は無い(cmds.containerと同じ機能がOpenMayaに無いため)。Undoが有効なら1回で戻せる。
    名前は作ったあとに付ける(``cmds.container`` のnameフラグは、Redoで名前空間を失うため)。
    nameは ``cmds.container`` と同じ短縮名 ``n`` でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        members (Node | str | Iterable[Node | str] | None): 作ったあとに所属させるノード。Noneと空の並びは空のまま。既定はNone。
            同じ並びに名前とNodeは混ぜられない。
        name (str | None): 付けたい名前。ほかのノードと重なる場合は、Mayaが重ならない名前に変える。
            Noneなら ``"container"``(``dag=True`` では ``"dagContainer"``)。既定はNone。
        n (str | None): nameの短縮名。nameと同時には指定できない。
        dag (bool): True ならDAGコンテナを作る。既定はFalse。

    Returns:
        Container | DagContainer: 作ったcontainer。``dag=True`` ならDagContainer。

    Raises:
        TypeError: nameと短縮名 ``n`` を同時に指定した場合、dagがbool以外の場合、
            nameが文字列でもNoneでもない場合、またはmembersの同じ並びに名前とNodeを混ぜた場合(Nodesと同じ決まり)。
        ValueError: nameが空文字列か ``|`` を含む場合。
        RuntimeError: membersに見つからないノードやほかのcontainerに入っているノードがある場合(何も作らない)、
            またはMayaが作成・所属を拒否した場合。

    Examples:
        >>> import mlib
        >>> owner = mlib.createContainer([node], name="arm_graph")
        >>> rig = mlib.createContainer([group], name="arm_rig", dag=True)
    """
    ...
