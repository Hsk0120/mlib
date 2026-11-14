# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""MayaのphongEノードを扱う。"""

from .reflect import Reflect



class PhongE(Reflect):
    """MayaのphongEノードを扱うクラス。値の設定と接続はPlugで行う。"""
