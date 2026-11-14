# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""MayaのUndoの状態を、変更せずに調べる。"""

import maya.cmds as cmds


def isEnabled() -> bool:
    """今、Undoの記録が有効になっているか調べる。

    Undoの履歴や設定は変えない。

    Returns:
        bool: Undoの記録が有効ならTrue。
    """
    ...
