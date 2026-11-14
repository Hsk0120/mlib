"""文字列のアトリビュートを扱う。get・setで読み書きする。数値向けのresetは使えない。"""

from .plug import Plug


class StringPlug(Plug):
    """文字列のアトリビュートを扱うPlug。get・setで読み書きする。数値向けのresetは使えない。"""
