"""Mayaが知っているノード型の名前かを返す(``cmds.allNodeTypes`` の照会)。"""

import maya.cmds as cmds


def isNodeType(type):
    """Mayaが知っているノード型の名前かを返す。

    プラグインの型は、そのプラグインを読み込んでいる間だけTrueになる。
    抽象型(``dagNode`` など、作成できない基底の型)もTrueになる。
    知らない型名を :func:`mlib.ls <mlib.cmds.ls.ls>` の ``type`` に渡すと、Mayaが警告を出して空を返すため、先に確かめるときに使う。

    Args:
        type (str): ノード型の名前(``"transform"``・``"joint"`` など)。

    Returns:
        bool: Mayaが知っている型ならTrue。

    Raises:
        TypeError: typeが文字列でない場合。

    Examples:
        >>> import mlib
        >>> solvers = mlib.ls(type="simplePhysicsSolver") if mlib.isNodeType("simplePhysicsSolver") else []
    """
    if not isinstance(type, str):
        raise TypeError(f"typeはノード型の名前の文字列で指定してください: {type.__class__.__name__}")
    # includeAbstractでは、抽象型の名前の後ろに " (abstract)" が付く。
    return any(entry.split(" ", 1)[0] == type for entry in cmds.allNodeTypes(includeAbstract=True))
