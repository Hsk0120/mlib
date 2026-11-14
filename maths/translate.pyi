# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""平行移動を表す3成分のベクトル値。"""

from .vector import Vector



class Translate(Vector):
    """位置・平行移動を表す、3成分のベクトル(om2.MVectorの派生)。

    値・演算・比較は、すべて :class:`~mlib.maths.vector.Vector` と同じ。
    om2のMVectorを継承しているので、``MFnTransform.setTranslation`` などへそのまま渡せる。
    位置をマトリクスで変換するときは、:meth:`mlib.maths.matrix.Matrix.transformPoint` か
    ``om2.MPoint(t) * m`` を使う(``t * m`` は平行移動を含まない、方向の変換になる)。
    """
    __slots__: tuple
