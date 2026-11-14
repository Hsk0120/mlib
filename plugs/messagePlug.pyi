# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""messageアトリビュートを扱う。値は持たず、接続の端として使う。"""

from .plug import Plug



class MessagePlug(Plug):
    """messageアトリビュートを扱うPlug。値は持たず、接続の端として使う。"""
