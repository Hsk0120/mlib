"""DAGコンテナを作り、指定したノードを所属させる(``cmds.container(type="dagContainer")`` 相当)。

.. code-block:: python

    import mlib

    owner = mlib.createDagContainer("arm_rig", members=[group])
"""

from ..decorator import _pick_alias
from ..util import _UNSET
from .createContainer import _create_container


def createDagContainer(name=_UNSET, members=(), *, n=_UNSET):
    """DAGコンテナを作り、指定したノードを所属させる。

    作成のあとに ``addMembers`` を行うのと同じ。処理は :func:`~mlib.cmds.createContainer.createContainer` と同じで、
    作るノードの型だけが違う。fast引数は無い。
    nameは ``cmds.container`` と同じ短縮名 ``n`` でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        name (str): 付けたい名前。ほかのノードと重なる場合は、Mayaが重ならない名前に変える。
            既定は ``"dagContainer"``。
        members (str | Node | Iterable[Node | str]): 作ったあとに所属させるノード。省略すると空のまま。
        n (str): nameの短縮名。nameと同時には指定できない。

    Returns:
        DagContainer: 作ったコンテナ。

    Raises:
        TypeError: nameと短縮名 ``n`` を同時に指定した場合。
        RuntimeError: Mayaが作成・所属を拒否した場合。
    """
    name = _pick_alias(name, n, "name", "n", default="dagContainer")
    return _create_container(name, members, "mlibCreateDagContainer", type="dagContainer")
