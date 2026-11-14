# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのplace3dTextureノードを扱う。"""

from .transform import Transform



class Place3dTexture(Transform):
    """Mayaのplace3dTextureノードを扱うクラス。値の設定と接続はPlugで行う。"""
