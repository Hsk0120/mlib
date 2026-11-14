# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""倍精度の小数(double)のアトリビュートを扱う。get・set・resetはPlug共通の処理を使う。"""

from .plug import Plug



class DoublePlug(Plug):
    """倍精度の小数(double)のアトリビュートを扱うPlug。get・set・resetはPlug共通の処理を使う。"""
