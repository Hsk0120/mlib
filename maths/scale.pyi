# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""スケールを表す3成分のベクトル値。"""

from .vector import Vector



class Scale(Vector):
    """スケールを表す、3成分のベクトル(om2.MVectorの派生)。

    値・演算・比較は、すべて :class:`~mlib.maths.vector.Vector` と同じ。
    """
    __slots__: tuple
