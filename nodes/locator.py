"""Maya の locator シェイプを扱う。"""

from .shape import Shape


class Locator(Shape):
    """Mayaのlocatorシェイプを扱うクラス。表示の位置(localPosition)などの値の設定や接続はPlugで行う。"""
