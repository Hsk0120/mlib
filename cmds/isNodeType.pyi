# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaが知っているノード型の名前かを返す(``cmds.allNodeTypes`` の照会)。"""

import maya.cmds as cmds


def isNodeType(name: str) -> bool:
    """Mayaが知っているノード型の名前かを返す。

    プラグインの型は、そのプラグインを読み込んでいる間だけTrueになる。
    抽象型(``dagNode`` など、作成できない基底の型)もTrueになる。
    知らない型名を :func:`mlib.ls <mlib.cmds.ls.ls>` の ``type`` に渡すと、Mayaが警告を出して空を返すため、先に確かめるときに使う。

    Args:
        name (str): ノード型の名前(``"transform"``・``"joint"`` など)。

    Returns:
        bool: Mayaが知っている型ならTrue。

    Raises:
        TypeError: nameが文字列でない場合。

    Examples:
        >>> import mlib
        >>> solvers = mlib.ls(type="simplePhysicsSolver") if mlib.isNodeType("simplePhysicsSolver") else []
    """
    ...
