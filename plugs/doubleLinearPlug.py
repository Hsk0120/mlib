"""距離のアトリビュートを、Plug共通の読み書きで扱う。"""

from .plug import Plug


class DoubleLinearPlug(Plug):
    """距離のアトリビュートを扱うPlug。

    get・setで扱う数値の単位は、既定はcm、uiUnits=Trueなら現在のUIの距離単位になる。
    """
