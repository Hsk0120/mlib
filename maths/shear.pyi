# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""XY・XZ・YZ のシアーを表す3成分のベクトル値。"""

from .vector import Vector



class Shear(Vector):
    """XY・XZ・YZのシアーを表す、3成分のベクトル(om2.MVectorの派生)。

    型で用途を区別するだけで、ほかの型との演算を止める検査はしない。
    値・演算・比較は、すべて :class:`~mlib.maths.vector.Vector` と同じ。
    """
    __slots__: tuple
