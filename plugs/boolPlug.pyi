# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""真偽値(bool)のアトリビュートと、値を反転する操作を提供する。"""

from .plug import Plug



class BoolPlug(Plug):
    """bool型のアトリビュートを扱うPlug。"""
    def toggle(self, *, fast: bool = ...) -> Plug:
        """真偽値を反転する。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。:meth:`set` へそのまま渡す。

        Returns:
            Plug: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
            RuntimeError: アトリビュートが無効な場合、またはロックや入力の接続があって書き込めない場合。
        """
        ...
