# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""列挙型(enum)のアトリビュートを扱う。値は整数で、フィールド名でも書き込める。"""

from .plug import Plug



class EnumPlug(Plug):
    """列挙型(enum)のアトリビュートを扱うPlug。

    - getは整数の値を返す。
    - setには整数の値か、フィールド名を渡せる。
    - getEnumName・getEnumValueで、名前と値を相互に変換できる。

    ``set("head")`` のようにフィールド名を渡すと、:meth:`getEnumValue` で値へ変換してから書き込む。
    名前は大文字・小文字を区別して、完全に一致するものを探す。通常・fast・safeのどれでも同じ。
    一致しない名前を渡すと、有効な名前を並べたValueErrorになる(``safe=True`` では失敗数1)。
    """
    def _set_value(self, value: int | str, *, uiUnits: bool = ..., fast: bool = ...) -> None:
        """フィールド名を整数の値へ変換してから、基底クラスの書き込みへ渡す。

        Args:
            value (int | str): enumの値、またはフィールド名。
            uiUnits (bool): 基底クラスの書き込みへそのまま渡す単位の指定。
            fast (bool): TrueならOpenMayaで直接更新する。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: フィールド名に一致するフィールドが無い場合。
        """
        ...
