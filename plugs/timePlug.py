"""時間アトリビュートを扱う。"""

from .plug import Plug


class TimePlug(Plug):
    """時間のアトリビュートを扱うPlug。

    get・setで扱う数値の単位は、既定は現在のUIの時間単位でのフレーム、timeUnit="sec"なら秒になる。
    """
