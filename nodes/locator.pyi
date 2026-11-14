# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の locator シェイプを扱う。"""

from ..decorator import _require_bool
from ..maths import Translate
from .shape import Shape
from typing import Iterable



class Locator(Shape):
    """Mayaのlocatorシェイプを扱うクラス。"""
    def getPosition(self) -> Translate:
        """ロケーターの位置(localPosition)を取得する。

        Returns:
            Translate: localPositionの値。
        """
        ...
    def setPosition(self, value: Translate | Iterable[float], *, fast: bool = ...) -> Locator:
        """ロケーターの位置(localPosition)を設定する。

        Args:
            value (Translate | Iterable[float]): 新しいlocalPositionの値。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Locator: 自身。

        Note:
            ``fast=True`` はOpenMayaで直接書き込む(Undoなし)。既定の ``False`` は通常の処理になる。
            fastがbool以外ならTypeErrorになる。直接書き込んだ後の変更は、自動では戻さない。
        """
        ...
