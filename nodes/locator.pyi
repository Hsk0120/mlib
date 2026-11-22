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
    def setPosition(self, value: Translate | Iterable[float], *, fast: bool = ..., check: bool = ...) -> None:
        """ロケーターの位置(localPosition)を設定する。

        Args:
            value (Translate | Iterable[float]): 新しいlocalPositionの値。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがboolでない場合、またはvalueが数値の並びでない場合。
            ValueError: check=Trueで、値が有限でない(NaN・無限大の)場合。
            RuntimeError: ノードが無効な場合、check=Trueでロック・入力の接続がある場合、
                またはMayaが書き込みを拒否した場合。

        Note:
            ``fast=True`` はOpenMayaで直接書き込む(Undoなし)。既定の ``False`` は通常の処理になる。
            fastがbool以外ならTypeErrorになる。直接書き込んだ後の変更は、自動では戻さない。
        """
        ...
