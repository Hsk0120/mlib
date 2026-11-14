# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""mlib の数学型と、変換の計算。

Vector 系・Quaternion・EulerRotate・Matrix は、OpenMaya API 2.0
(``maya.api.OpenMaya``)の MVector / MQuaternion / MEulerRotation / MMatrix を
継承した、値を書き換えられる型。そのまま om2 の関数へ渡せる。計算の意味は om2 と同じ。

easing だけは、標準ライブラリの math だけを使う関数の集まり(シーンには触れない)。
``MSpace`` は ``maya.api.OpenMaya.MSpace`` (空間の指定)を、そのままここからも使えるようにしたもの。
"""

from maya.api.OpenMaya import MSpace
from . import easing
from .eulerRotate import EulerRotate
from .matrix import Matrix
from .quaternion import Quaternion
from .scale import Scale
from .shear import Shear
from .translate import Translate
from .vector import Vector

__all__ = ['EulerRotate', 'MSpace', 'Matrix', 'Quaternion', 'Scale', 'Shear', 'Translate', 'Vector', 'easing']
