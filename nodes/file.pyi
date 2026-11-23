# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのfileノードを扱う。"""

from .texture2d import Texture2d



class File(Texture2d):
    """Mayaのfileノードを表すクラス。値の設定や接続はPlugで行う。"""
