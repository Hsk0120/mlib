"""Mayaのfileノードを扱う。"""

from .texture2d import Texture2d


class File(Texture2d):
    """Mayaのfileノードを表すクラス。値の設定や接続はPlugで行う。"""
