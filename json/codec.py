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

#: 型名と、読み込むときに作るmlibのクラス。Vectorの派生クラスは、Vectorより先に判定する。
_VECTOR_TYPES = (("Translate", Translate), ("Scale", Scale), ("Shear", Shear), ("Vector", Vector))
_TYPE_NAMES = frozenset(name for name, _cls in _VECTOR_TYPES) | {"Quaternion", "EulerRotate", "Matrix"}
#: Transformationの成分の名前と、既定値(Noneは必ず書く成分)。角度の成分は度で書く。
_TRANSFORMATION_VECTORS = {
    "translate": None,
    "rotate": None,
    "scale": None,
    "shear": None,
    "rotateAxis": (0.0, 0.0, 0.0),
    "rotatePivot": (0.0, 0.0, 0.0),
    "rotatePivotTranslate": (0.0, 0.0, 0.0),
    "scalePivot": (0.0, 0.0, 0.0),
    "scalePivotTranslate": (0.0, 0.0, 0.0),
    "jointOrient": (0.0, 0.0, 0.0),
    "inverseScale": (1.0, 1.0, 1.0),
}
_TRANSFORMATION_ANGLES = frozenset(("rotate", "rotateAxis", "jointOrient"))


def encode(value):
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
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"有限でない数値はJSONへ書き出せません: {value!r}")
        return value
    if isinstance(value, om2.MTransformationMatrix):
        return {"type": "Transformation", "value": _encode_transformation(value)}
    if isinstance(value, om2.MEulerRotation):
        rotate = value if isinstance(value, EulerRotate) else EulerRotate(value.x, value.y, value.z, value.order)
        return {"type": "EulerRotate", "value": [_finite(item) for item in rotate.asDegrees()], "order": rotate.orderName}
    if isinstance(value, om2.MQuaternion):
        return {"type": "Quaternion", "value": [_finite(item) for item in (value.x, value.y, value.z, value.w)]}
    if isinstance(value, om2.MMatrix):
        return {"type": "Matrix", "value": [_finite(value[index]) for index in range(16)]}
    if isinstance(value, om2.MVector):
        name = next((name for name, cls in _VECTOR_TYPES if isinstance(value, cls)), "Vector")
        return {"type": name, "value": [_finite(item) for item in (value.x, value.y, value.z)]}
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError(f"JSONのオブジェクトのキーは文字列で指定してください: {type(key).__name__}")
            result[key] = encode(item)
        return result
    if isinstance(value, (list, tuple)):
        return [encode(item) for item in value]
    raise TypeError(f"{type(value).__name__}はJSONへ書き出せません")


def decode(value):
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
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    if _is_math(value):
        return _decode_math(value)
    return {key: decode(item) for key, item in value.items()}


def _finite(value):
    """有限のfloatを返す。

    Args:
        value (float): 成分。

    Returns:
        float: 同じ値。

    Raises:
        ValueError: NaN・無限大の場合。
    """
    if not math.isfinite(value):
        raise ValueError(f"有限でない数値はJSONへ書き出せません: {value!r}")
    return float(value)


def _is_math(value):
    """型名付きの数学型の辞書かを返す。

    Args:
        value (dict): JSONから読んだ辞書。

    Returns:
        bool: 数学型として戻す辞書ならTrue。
    """
    name = value.get("type")
    if name == "Transformation":
        return isinstance(value.get("value"), dict) and set(value) == {"type", "value"}
    if name not in _TYPE_NAMES or not isinstance(value.get("value"), list):
        return False
    expected = {"type", "value", "order"} if name == "EulerRotate" else {"type", "value"}
    return set(value) == expected


def _decode_math(value):
    """型名付きの辞書から数学型を作る。

    Args:
        value (dict): :func:`_is_math` がTrueの辞書。

    Returns:
        Vector | Translate | Scale | Shear | Quaternion | EulerRotate | Matrix | Transformation: 新しい値。

    Raises:
        ValueError: 成分の数が型と合わない場合、または回転順が正しくない場合。
    """
    name, items = value["type"], value["value"]
    if name == "Transformation":
        return _decode_transformation(items)
    sizes = {"Quaternion": 4, "Matrix": 16, "EulerRotate": 3}
    size = sizes.get(name, 3)
    if len(items) != size or not all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in items):
        raise ValueError(f"{name}のJSONは{size}個の数値で指定してください: {items!r}")
    if name == "EulerRotate":
        return EulerRotate.fromDegrees(items[0], items[1], items[2], value["order"])
    if name == "Quaternion":
        return Quaternion(items[0], items[1], items[2], items[3])
    if name == "Matrix":
        return Matrix(items)
    return dict(_VECTOR_TYPES)[name](items[0], items[1], items[2])


def _encode_transformation(value):
    """Transformationの成分を、JSONで書ける辞書にする。

    Args:
        value (om2.MTransformationMatrix): 書き出す値。Transformationでなければ、Transformationへ写してから書く。

    Returns:
        dict: 成分の名前と値。角度は度、回転順は名前。既定値のままの補助の成分は入れない。

    Raises:
        ValueError: 成分がNaNか無限大の場合。
    """
    source = value if isinstance(value, Transformation) else Transformation(value)
    rotate = source.rotate
    result = {"rotateOrder": rotate.orderName}
    for name, default in _TRANSFORMATION_VECTORS.items():
        item = getattr(source, name)
        if name == "rotate":
            items = tuple(rotate.asDegrees())
        elif name in _TRANSFORMATION_ANGLES:
            items = tuple(item.asEulerRotation().asDegrees())
        else:
            items = tuple(item)
        items = [_finite(component) for component in items]
        if default is None or any(abs(component - base) > 1e-12 for component, base in zip(items, default)):
            result[name] = items
    return result


def _decode_transformation(items):
    """成分の辞書からTransformationを作る。

    Args:
        items (dict): :func:`_encode_transformation` が書いた辞書。

    Returns:
        Transformation: 新しい値。書かれていない成分は既定値。

    Raises:
        ValueError: 知らない成分がある場合、成分が3個の数値でない場合、または回転順が正しくない場合。
    """
    unknown = set(items) - set(_TRANSFORMATION_VECTORS) - {"rotateOrder"}
    if unknown:
        raise ValueError(f"TransformationのJSONに知らない成分があります: {', '.join(sorted(unknown))}")
    order = orderIndex(items.get("rotateOrder", "xyz"))
    arguments = {}
    for name, item in items.items():
        if name == "rotateOrder":
            continue
        if not isinstance(item, list) or len(item) != 3 or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in item):
            raise ValueError(f"Transformationの{name}は3個の数値で指定してください: {item!r}")
        if name == "rotate":
            arguments[name] = EulerRotate.fromDegrees(item[0], item[1], item[2], order)
        elif name in _TRANSFORMATION_ANGLES:
            arguments[name] = EulerRotate.fromDegrees(item[0], item[1], item[2])
        else:
            arguments[name] = item
    return Transformation(rotateOrder=order, **arguments)
