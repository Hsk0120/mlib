"""MayaのUndoの状態を、変更せずに調べる。"""

import maya.cmds as cmds


def isEnabled():
    """今、Undoの記録が有効になっているか調べる。

    Undoの履歴や設定は変えない。

    Returns:
        bool: Undoの記録が有効ならTrue。
    """
    return bool(cmds.undoInfo(query=True, state=True))


# reload時にも廃止した公開名を残さない。
for _obsolete_name in ("is_enabled", "enabled"):
    globals().pop(_obsolete_name, None)
