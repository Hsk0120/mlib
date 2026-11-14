"""containerを作り、指定したノードを所属させる(``cmds.container`` 相当)。

``cmds.container`` の規則(現在のcontainerへの自動での所属など)に従う。
空のcontainerだけが必要なら ``mlib.createNode("container", name=...)`` でも作れる。

.. code-block:: python

    import mlib

    owner = mlib.createContainer("arm_graph", members=[node])
"""

import maya.cmds as cmds

from ..decorator import _pick_alias, undoTransaction
from ..util import _UNSET


def createContainer(name=_UNSET, members=(), *, n=_UNSET):
    """containerを作り、指定したノードを所属させる。

    作成のあとに ``addMembers`` を行うのと同じ。
    fast引数は無い(cmds.containerと同じ機能がOpenMayaに無いため)。Undoが有効なら1回で戻せる。
    nameは ``cmds.container`` と同じ短縮名 ``n`` でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        name (str): 付けたい名前。ほかのノードと重なる場合は、Mayaが重ならない名前に変える。
            既定は ``"container"``。
        members (str | Node | Iterable[Node | str]): 作ったあとに所属させるノード。省略すると空のまま。
        n (str): nameの短縮名。nameと同時には指定できない。

    Returns:
        Container: 作ったcontainer。

    Raises:
        TypeError: nameと短縮名 ``n`` を同時に指定した場合。
        RuntimeError: Mayaが作成・所属を拒否した場合。
    """
    name = _pick_alias(name, n, "name", "n", default="container")
    return _create_container(name, members, "mlibCreateContainer")


def _create_container(name, members, chunk, **flags):
    """containerの作成と所属を、1回のUndoにまとめて行う。

    Args:
        name (str): 付けたい名前。
        members (Iterable): 所属させるノード。
        chunk (str): Undoチャンク名。
        **flags: ``cmds.container`` へ渡す型の指定。

    Returns:
        Container | DagContainer: 作ったcontainer。
    """
    # nodes はcmdsを参照するため、循環importを避けて関数内で読み込む。
    from ..nodes.node import Node

    with undoTransaction(chunk):
        container = Node(cmds.container(name=name, **flags))
        if members:
            container.addMembers(members)
        return container
