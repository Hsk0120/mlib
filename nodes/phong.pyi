# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのphongノードを扱う。"""

from .reflect import Reflect



class Phong(Reflect):
    """Mayaのphongノードを扱うクラス。値の設定と接続はPlugで行う。"""
