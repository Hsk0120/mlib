# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""mlibの数学型をJSONで書ける値へ変換し、読み込んだ値を元の型へ戻す。

数学型は ``{"type": "Matrix", "value": [...]}`` のように型名を付けた辞書にする。
``EulerRotate`` は度で書き、回転順の名前を ``"order"`` に付ける。``Quaternion``・``Matrix`` は
単位を持たないため、om2の成分をそのまま書く。小数は丸めない。
``Transformation`` は ``"value"`` を成分の辞書にし、角度は度、回転順は名前で書く。既定値のままの
rotateAxis・ピボット・jointOrient・inverseScale は書かず、読むときに既定値で補う。
"""

import math
import maya.api.OpenMaya as om2
from ..maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Transformation, Translate, Vector
from ..maths.eulerRotate import orderIndex
from typing import Any

_VECTOR_TYPES: tuple
_TYPE_NAMES: Any
_TRANSFORMATION_VECTORS: dict
_TRANSFORMATION_ANGLES: frozenset

def encode(value: object) -> Any:
    """値をJSONで書ける値へ変換する。

    辞書・list・tupleの中もたどって変換する。辞書のキーは文字列だけ使える。tupleはlistになる。
    om2の ``MVector``・``MQuaternion``・``MEulerRotation``・``MMatrix``・``MTransformationMatrix`` も、mlibの型名で書く。

    Args:
        value (object): 変換する値。None・bool・int・float・str・数学型と、それらを入れた辞書とlist。

    Returns:
        object: JSONで書ける値。入力の辞書・listは変更しない。

    Raises:
        TypeError: 対応しない型の場合、または辞書のキーが文字列でない場合。
        ValueError: floatがNaNか無限大の場合。
    """
    ...

def decode(value: object) -> Any:
    """:func:`encode` で書いた値を、数学型を含む元の値へ戻す。

    数学型にするのは、``{"type": <型名>, "value": [...]}`` (EulerRotateは ``"order"`` も)の形の辞書だけ。
    ほかの辞書・listは、中をたどって同じ形で返す。

    Args:
        value (object): JSONから読んだ値。

    Returns:
        object: 数学型へ戻した値。入力の辞書・listは変更しない。

    Raises:
        ValueError: 型名付きの辞書の成分の数が型と合わない場合。
    """
    ...

def _finite(value: float) -> float:
    """有限のfloatを返す。

    Args:
        value (float): 成分。

    Returns:
        float: 同じ値。

    Raises:
        ValueError: NaN・無限大の場合。
    """
    ...

def _is_math(value: dict) -> bool:
    """型名付きの数学型の辞書かを返す。

    Args:
        value (dict): JSONから読んだ辞書。

    Returns:
        bool: 数学型として戻す辞書ならTrue。
    """
    ...

def _decode_math(value: dict) -> Vector | Translate | Scale | Shear | Quaternion | EulerRotate | Matrix | Transformation:
    """型名付きの辞書から数学型を作る。

    Args:
        value (dict): :func:`_is_math` がTrueの辞書。

    Returns:
        Vector | Translate | Scale | Shear | Quaternion | EulerRotate | Matrix | Transformation: 新しい値。

    Raises:
        ValueError: 成分の数が型と合わない場合、または回転順が正しくない場合。
    """
    ...

def _encode_transformation(value: om2.MTransformationMatrix) -> dict:
    """Transformationの成分を、JSONで書ける辞書にする。

    Args:
        value (om2.MTransformationMatrix): 書き出す値。Transformationでなければ、Transformationへ写してから書く。

    Returns:
        dict: 成分の名前と値。角度は度、回転順は名前。既定値のままの補助の成分は入れない。

    Raises:
        ValueError: 成分がNaNか無限大の場合。
    """
    ...

def _decode_transformation(items: dict) -> Transformation:
    """成分の辞書からTransformationを作る。

    Args:
        items (dict): :func:`_encode_transformation` が書いた辞書。

    Returns:
        Transformation: 新しい値。書かれていない成分は既定値。

    Raises:
        ValueError: 知らない成分がある場合、成分が3個の数値でない場合、または回転順が正しくない場合。
    """
    ...
