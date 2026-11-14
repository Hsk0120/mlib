"""Mayaのblinnノードを扱う。"""

from .reflect import Reflect


class Blinn(Reflect):
    """Mayaのblinnノードを表すクラス。値の設定や接続はPlugで行う。"""
