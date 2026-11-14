"""角度アトリビュートを扱う。"""

from .plug import Plug


class DoubleAnglePlug(Plug):
    """角度のアトリビュートを扱うPlug。

    get・setで扱う数値の単位は次のとおり。

    - 既定は度。
    - unit="rad"ならラジアン。
    - uiUnits=Trueなら、現在のUIの角度単位。
    """
