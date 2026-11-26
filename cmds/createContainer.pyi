# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""containerを作り、指定したノードを所属させる(``cmds.container`` 相当)。"""

import maya.cmds as cmds
from ..decorator import _pick_alias, _require_bool, undoTransaction
from ..util import _UNSET
from typing import Iterable, Literal
from mlib.nodes.container import Container
from mlib.nodes.dagContainer import DagContainer
from mlib.nodes.node import Node
from typing import overload


@overload
def createContainer(members: str | Node | Iterable[Node | str] = ..., *, name: str = ..., dag: Literal[True], n: str = ...) -> DagContainer: ...
@overload
def createContainer(members: str | Node | Iterable[Node | str] = ..., *, name: str = ..., dag: Literal[False] = ..., n: str = ...) -> Container: ...
@overload
def createContainer(members: str | Node | Iterable[Node | str] = ..., *, name: str = ..., dag: bool = ..., n: str = ...) -> Container | DagContainer:
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
    ...
