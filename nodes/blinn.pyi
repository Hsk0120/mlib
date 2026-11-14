# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのblinnノードを扱う。"""

from .reflect import Reflect



class Blinn(Reflect):
    """Mayaのblinnノードを表すクラス。値の設定や接続はPlugで行う。"""
