"""アトリビュートの型名を、Maya API 2.0のアトリビュートの定義から求める(シーンは変えない)。

型名は ``cmds.getAttr(<プラグ名>, type=True)`` と同じ文字列で返す。次の2つに使う。

- Plugの派生クラスを選ぶ(:class:`~mlib.core.registry.NodeRegistry` のアトリビュート型のキー)。
- ``Plug.set()`` で、doubleArrayなどのデータ型かを判定する。

``cmds.getAttr(type=True)`` には、次のような問題がある。

- 存在しないマルチアトリビュートの要素を問い合わせると、要素を作ってしまう
  (blendShapeの ``weight[i]`` では ``parentDirectory[i]`` なども作られる)。
- nurbsSurfaceの ``patchUVIds`` の存在しない要素では、Mayaが異常終了する。
- meshの内部アトリビュート(``edge[i]``・``face[i]`` など)では例外になる。

このモジュールの関数はプラグの値を読まず、アトリビュートの定義(``MFnAttribute`` の各派生クラス)だけから
型名を決める。そのため、存在しない要素でもシーンを変えず、評価も起こさない。

アトリビュートの種類と結果:

.. list-table::
   :header-rows: 1

   * - アトリビュート
     - 結果
   * - 数値(``MFnNumericAttribute``)
     - ``bool``/``byte``/``char``/``short``/``long``/``float``/``double``/``addr`` と、
       数値のコンパウンドアトリビュートの ``double3``/``float3``/``long2`` など(``numericType()`` による)
   * - 単位(``MFnUnitAttribute``)
     - ``doubleLinear``/``floatLinear``/``doubleAngle``/``floatAngle``/``time``
   * - enum・message
     - ``enum``・``message``
   * - マトリクス(``MFnMatrixAttribute``)
     - ``matrix`` (float のマトリクスも ``cmds.getAttr`` と同じく ``matrix``)
   * - 型付き(``MFnTypedAttribute``)
     - ``string``/``matrix``/``doubleArray``/``Int32Array``/``mesh``/``nurbsCurve`` など。
       API 2.0 に列挙値の無いデータ型(``Int64Array``・``floatVectorArray``・
       データ型指定の ``double3`` など)は ``MFnAttribute.getAddAttrCmd()`` のデータ型名
   * - コンパウンドアトリビュート(``MFnCompoundAttribute``)・lightData
     - ``TdataCompound``
   * - 不透明(opaque)
     - ``getAddAttrCmd()`` のアトリビュート型名(``TattributeCtypeOf<...>``)

持っている値によって ``cmds.getAttr(type=True)`` の結果が変わるアトリビュートは、
値を読まないと型名が決まらないので ``None`` を返す。genericアトリビュート、どんなデータでも受け付けるtypedアトリビュート、
``geometry`` 型などがこれに当たる。

例外として、meshの ``controlPoints`` は ``float3`` を返す。アトリビュートの定義は ``double3`` だが、
Mayaは内部でfloatの頂点座標として扱い、``cmds.getAttr(type=True)`` も ``float3`` を返すためである
(nurbsCurve・nurbsSurface・latticeは ``double3``)。
"""

import math
import re
from functools import partial

import maya.api.OpenMaya as om2

from ..util import _angle_unit, _time_unit

__all__ = ["attributeType", "is_internal_data_type", "typed_data", "value_reader"]

_N = om2.MFnNumericData
_D = om2.MFnData

#: apiType だけで型名が決まるアトリビュート。
_API_TYPE_NAMES = {
    om2.MFn.kDoubleLinearAttribute: "doubleLinear",
    om2.MFn.kFloatLinearAttribute: "floatLinear",
    om2.MFn.kDoubleAngleAttribute: "doubleAngle",
    om2.MFn.kFloatAngleAttribute: "floatAngle",
    om2.MFn.kTimeAttribute: "time",
    om2.MFn.kEnumAttribute: "enum",
    om2.MFn.kMessageAttribute: "message",
    om2.MFn.kMatrixAttribute: "matrix",
    om2.MFn.kFloatMatrixAttribute: "matrix",
    om2.MFn.kCompoundAttribute: "TdataCompound",
    om2.MFn.kLightDataAttribute: "TdataCompound",
}

#: 数値アトリビュートの ``numericType()`` と型名。
_NUMERIC_TYPE_NAMES = {
    _N.kBoolean: "bool",
    _N.kByte: "byte",
    _N.kChar: "char",
    _N.kShort: "short",
    _N.k2Short: "short2",
    _N.k3Short: "short3",
    _N.kInt: "long",
    _N.k2Int: "long2",
    _N.k3Int: "long3",
    _N.kFloat: "float",
    _N.k2Float: "float2",
    _N.k3Float: "float3",
    _N.kDouble: "double",
    _N.k2Double: "double2",
    _N.k3Double: "double3",
    _N.k4Double: "double4",
    _N.kAddr: "addr",
}

#: 型付きアトリビュートの ``attrType()`` と型名。ここに無いデータ型は getAddAttrCmd() から求める。
_DATA_TYPE_NAMES = {
    _D.kString: "string",
    _D.kMatrix: "matrix",
    _D.kStringArray: "stringArray",
    _D.kDoubleArray: "doubleArray",
    _D.kFloatArray: "floatArray",
    _D.kIntArray: "Int32Array",
    _D.kPointArray: "pointArray",
    _D.kVectorArray: "vectorArray",
    _D.kMatrixArray: "matrixArray",
    _D.kComponentList: "componentList",
    _D.kMesh: "mesh",
    _D.kLattice: "lattice",
    _D.kNurbsCurve: "nurbsCurve",
    _D.kNurbsSurface: "nurbsSurface",
    _D.kSphere: "sphere",
    _D.kSubdSurface: "subd",
}

#: 値によって型が変わるため、アトリビュート定義だけでは型名が決まらない apiType。
_VALUE_DEPENDENT_API_TYPES = frozenset((om2.MFn.kGenericAttribute,))

#: getAddAttrCmd() のデータ型名のうち、保持する値によって型が変わるもの。
_VALUE_DEPENDENT_DATA_TYPES = frozenset(("geometry",))

#: getAddAttrCmd() のアトリビュート型名と ``cmds.getAttr(type=True)`` の型名が異なるもの。
#: ``typed`` は任意のデータを受け付ける型付きアトリビュートで、値によって型が変わる(None)。
_ADD_ATTR_TYPE_NAMES = {
    "reflectance": "reflectanceRGB",
    "spectrum": "spectrumRGB",
    "fltMatrix": "matrix",
    "compound": "TdataCompound",
    "lightData": "TdataCompound",
    "typed": None,
}

#: ``cmds.addAttr(dataType=...)`` で作成できるデータ型名(maya.cmds で値を読み書きできる型)。
#: 型付きアトリビュートのうちこれら以外(``nurbsPatchUVIds``・``polyFaces`` などの Maya 内部のデータ型)は、
#: 存在しないマルチアトリビュートの要素の値を maya.cmds で問い合わせると Maya が異常終了する場合がある。
_PUBLIC_DATA_TYPES = frozenset(_DATA_TYPE_NAMES.values()) | frozenset(
    (
        "Int64Array",
        "floatVectorArray",
        "reflectanceRGB",
        "spectrumRGB",
        "short2",
        "short3",
        "long2",
        "long3",
        "float2",
        "float3",
        "double2",
        "double3",
        "double4",
    )
)

_ADD_ATTR_DATA_TYPE = re.compile(r'-dataType "([^"]+)"')
_ADD_ATTR_ATTRIBUTE_TYPE = re.compile(r'-attributeType "([^"]+)"')

#: 自身の単位を持つため、数値の角度として換算しない値。
_SELF_UNIT_VALUES = (om2.MEulerRotation, om2.MQuaternion, om2.MAngle, om2.MDistance, om2.MTime, om2.MMatrix, om2.MTransformationMatrix)


def _add_attr_type_name(attribute):
    """``MFnAttribute.getAddAttrCmd()`` の型の指定から、型名を求める。

    API 2.0の列挙値で表せない型に使う。データ型(``Int64Array``、データ型として指定した ``double3`` など)と、
    アトリビュート型(``reflectance``、opaqueアトリビュート)がある。

    Args:
        attribute (om2.MObject): アトリビュートのMObject。

    Returns:
        str | None: 型名。データ型を複数受け付けるアトリビュートと、値によって型が変わるアトリビュートはNone。
    """
    command = om2.MFnAttribute(attribute).getAddAttrCmd(True)
    data_types = _ADD_ATTR_DATA_TYPE.findall(command)
    if data_types:
        if len(data_types) != 1 or data_types[0] in _VALUE_DEPENDENT_DATA_TYPES:
            return None
        return data_types[0]
    match = _ADD_ATTR_ATTRIBUTE_TYPE.search(command)
    if match is None:
        return None
    name = match.group(1)
    return _ADD_ATTR_TYPE_NAMES.get(name, name)


def _is_mesh_control_points(mplug, attribute):
    """meshの ``controlPoints`` (Mayaがfloat3として扱うアトリビュート)のプラグか調べる。

    Args:
        mplug (om2.MPlug): 調べるプラグ。
        attribute (om2.MObject): プラグのアトリビュート。

    Returns:
        bool: meshの ``controlPoints`` ならTrue。
    """
    return mplug.node().hasFn(om2.MFn.kMesh) and om2.MFnAttribute(attribute).name == "controlPoints"


def attributeType(mplug):
    """プラグのアトリビュートの型名を、``cmds.getAttr(<プラグ名>, type=True)`` と同じ文字列で取得する。

    coreの関数の名前はsnake_caseが基本だが、この関数は今の名前のまま残している。
    ``Plug`` 側でアトリビュートの型ごとにクラスを選ぶ処理(``Plug._registry`` のキー)と、
    ``cmds.getAttr(type=True)`` の呼び方に合わせた名前のため。

    アトリビュートの定義だけから求めるので、シーンを変えない。存在しないマルチアトリビュートの要素や、
    ``cmds.getAttr`` が例外になるmeshの内部アトリビュートにも使える。
    マルチアトリビュートのプラグでは、要素の型名を返す
    (マルチアトリビュート全体に ``cmds.getAttr(type=True)`` を使った結果とは違う)。
    細かい規則はモジュールの説明を参照する。

    Args:
        mplug (om2.MPlug): 調べるプラグ。

    Returns:
        str | None: ``double3``/``doubleLinear``/``matrix`` などの型名。値によって型が変わる
            アトリビュート(genericアトリビュートなど)はNone。

    Raises:
        RuntimeError: アトリビュートが削除されて存在しない場合(Undoで戻せなくなった、
            削除済みの動的アトリビュートなど)。
    """
    attribute = mplug.attribute()
    api_type = attribute.apiType()
    name = _API_TYPE_NAMES.get(api_type)
    if name is not None:
        return name
    if attribute.hasFn(om2.MFn.kNumericAttribute):
        name = _NUMERIC_TYPE_NAMES.get(om2.MFnNumericAttribute(attribute).numericType())
        if name is None:
            return _add_attr_type_name(attribute)
        if name == "double3" and _is_mesh_control_points(mplug, attribute):
            return "float3"
        return name
    if api_type == om2.MFn.kTypedAttribute:
        data_type = om2.MFnTypedAttribute(attribute).attrType()
        name = _DATA_TYPE_NAMES.get(data_type)
        if name is not None:
            return name
        if data_type == _D.kAny:
            return None
        return _add_attr_type_name(attribute)
    if api_type in _VALUE_DEPENDENT_API_TYPES:
        return None
    return _add_attr_type_name(attribute)


def is_internal_data_type(mplug):
    """Mayaの内部のデータ型を持つtypedアトリビュートか調べる。

    内部のデータ型とは、``cmds.addAttr`` では作れない型のこと。
    nurbsSurfaceの ``patchUVIds`` (``nurbsPatchUVIds``)などがある。
    こうした型では、存在しないマルチアトリビュートの要素の値や型をmaya.cmdsやMPlugで読むと、
    Mayaが異常終了することがある。

    mlibは、こうした存在しない要素の値を読まず、``Plug.get()`` でRuntimeErrorにする。
    要素のPlugを取得するだけなら、値は評価しない。
    どんなデータでも受け付けるtypedアトリビュート(値によって型が変わるアトリビュート)は対象外。

    Args:
        mplug (om2.MPlug): 調べるプラグ。

    Returns:
        bool: 内部のデータ型のtypedアトリビュートならTrue。
    """
    attribute = mplug.attribute()
    if attribute.apiType() != om2.MFn.kTypedAttribute:
        return False
    data_type = om2.MFnTypedAttribute(attribute).attrType()
    if data_type in _DATA_TYPE_NAMES or data_type == _D.kAny:
        return False
    name = _add_attr_type_name(attribute)
    return name is not None and name not in _PUBLIC_DATA_TYPES


def _require_number(plug, value):
    """数値・単位・enumのアトリビュートへの入力が、数値か確かめる。

    fastでない ``cmds.setAttr`` は、数値アトリビュートへの文字列・None・並びを受け付けない。
    fastと、単位アトリビュートの換算でもこれに合わせ、値を変換せずに例外にする。
    型が違うときの規則に合わせて、例外はTypeErrorにする。boolは数値として受け付ける。

    Args:
        plug (om2.MPlug): 書き込み先。例外のメッセージに使う。
        value (object): 書き込む値。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: 文字列・bytes・Noneの場合、またはfloatへ変換できない値の場合。
    """
    if not isinstance(value, (str, bytes)) and value is not None:
        try:
            float(value)
            return
        except (TypeError, ValueError):
            pass
    raise TypeError(f"{plug.name()}には数値を指定してください: {value!r}")


def _convert_units(plug, value, to_ui=True):
    """数値やコンパウンドアトリビュートの値の単位を変換する。

    単位の無い型は、そのまま返す。

    Args:
        plug (om2.MPlug): 型を調べるプラグ。
        value (object): 変換する値。
        to_ui (bool): Trueならcm/rad/秒からUI単位へ、Falseならその逆へ変換する。既定はTrue。

    Returns:
        object: 変換した値。マトリクスや、doubleArrayなどのデータ型の成分は単位を変換しない。

    Raises:
        RuntimeError: 単位アトリビュートへ数値でない値(文字列・Noneなど)を指定した場合。
    """
    if plug.isCompound:
        return tuple(_convert_units(plug.child(i), item, to_ui) for i, item in enumerate(value))
    attribute = plug.attribute()
    if not attribute.hasFn(om2.MFn.kUnitAttribute):
        return value
    unit_type = om2.MFnUnitAttribute(attribute).unitType()
    if unit_type == om2.MFnUnitAttribute.kInvalid:
        # Maya 2023のmesh.pnts子はUnitAttributeとして解決されても単位型が
        # kInvalidになる。座標の数値を維持し、存在しない単位を変換しない。
        return value
    unit_class, internal_unit = {
        om2.MFnUnitAttribute.kAngle: (om2.MAngle, om2.MAngle.kRadians),
        om2.MFnUnitAttribute.kDistance: (om2.MDistance, om2.MDistance.kCentimeters),
        om2.MFnUnitAttribute.kTime: (om2.MTime, om2.MTime.kSeconds),
    }[unit_type]
    if isinstance(value, unit_class):
        # 単位オブジェクトは元単位を保持するため、数値用の元単位を付け直さない。
        return value.asUnits(unit_class.uiUnit() if to_ui else internal_unit)
    # 文字列・None等はcmds.setAttrの数値アトリビュートと同じくRuntimeErrorにする。
    _require_number(plug, value)
    if to_ui:
        source_unit, target_unit = internal_unit, unit_class.uiUnit()
    else:
        source_unit, target_unit = unit_class.uiUnit(), internal_unit
    return unit_class(value, source_unit).asUnits(target_unit)


def _plain_angle_unit(unit, ui_units):
    """get/setの ``unit`` と ``uiUnits`` から、数値で表す角度の単位を決める。

    Args:
        unit (str | None): 角度の単位名。Noneなら度。
        ui_units (bool): Trueなら現在のUI単位を使う(unitとは同時に指定できない)。

    Returns:
        str | None: ``"deg"`` / ``"rad"``。uiUnits=TrueならNone(UI単位への換算に任せる)。

    Raises:
        TypeError: unitが文字列でもNoneでもない場合。
        ValueError: 対応していない単位名の場合、またはuiUnits=Trueとunitを同時に指定した場合。
    """
    if ui_units:
        if unit is not None:
            # 単位名の誤りを先に伝え、正しい名前なら同時指定を拒否する。
            _angle_unit(unit)
            raise ValueError("unitとuiUnits=Trueは同時に指定できません")
        return None
    return _angle_unit(unit)


def _plain_time_unit(time_unit, ui_units):
    """get/setの ``timeUnit`` と ``uiUnits`` から、数値で表す時間の単位を決める。

    Args:
        time_unit (str | None): 時間の単位名。Noneなら現在のUI時間単位のフレーム。
        ui_units (bool): Trueなら現在のUI単位を使う(timeUnitとは同時に指定できない)。

    Returns:
        str | None: ``"frame"`` / ``"sec"``。uiUnits=TrueならNone(UI単位への換算に任せる)。

    Raises:
        TypeError: timeUnitが文字列でもNoneでもない場合。
        ValueError: 対応していない単位名の場合、またはuiUnits=TrueとtimeUnitを同時に指定した場合。
    """
    if ui_units:
        if time_unit is not None:
            _time_unit(time_unit)
            raise ValueError("timeUnitとuiUnits=Trueは同時に指定できません")
        return None
    return _time_unit(time_unit)


def _to_seconds(value, time_unit):
    """時間の数値を、秒へ変換する。

    Args:
        value (float): 時間の数値。
        time_unit (str): ``"frame"`` (現在のUI時間単位) または ``"sec"``。

    Returns:
        float: 秒の値。secならそのまま返す。
    """
    if time_unit == "frame":
        return om2.MTime(value, om2.MTime.uiUnit()).asUnits(om2.MTime.kSeconds)
    return value


def _from_seconds(value, time_unit):
    """秒の数値を、指定した時間単位へ変換する。

    Args:
        value (float): 秒の値。
        time_unit (str): ``"frame"`` (現在のUI時間単位) または ``"sec"``。

    Returns:
        float: time_unitの単位で表した値。secならそのまま返す。
    """
    if time_unit == "frame":
        return om2.MTime(value, om2.MTime.kSeconds).asUnits(om2.MTime.uiUnit())
    return value


def _time_quantity(value, time_unit):
    """時間の数値を、指定した単位の ``om2.MTime`` にする。

    Args:
        value (float): 時間の数値。
        time_unit (str): ``"frame"`` (現在のUI時間単位) または ``"sec"``。

    Returns:
        om2.MTime: 時間の値。
    """
    return om2.MTime(value, om2.MTime.uiUnit() if time_unit == "frame" else om2.MTime.kSeconds)


def _is_angle_attribute(attribute):
    """角度の単位アトリビュート(doubleAngle・floatAngle)か調べる。

    Args:
        attribute (om2.MObject): アトリビュートの定義。

    Returns:
        bool: 角度の単位アトリビュートならTrue。
    """
    return _is_unit_attribute(attribute, om2.MFnUnitAttribute.kAngle)


def _is_unit_attribute(attribute, unit_type):
    """指定した種類の単位アトリビュートか調べる。

    Args:
        attribute (om2.MObject): アトリビュートの定義。
        unit_type (int): ``om2.MFnUnitAttribute.kAngle`` などの単位の種類。

    Returns:
        bool: 指定した種類の単位アトリビュートならTrue。
    """
    return attribute.hasFn(om2.MFn.kUnitAttribute) and om2.MFnUnitAttribute(attribute).unitType() == unit_type


def _convert_unit_numbers(plug, value, unit_type, convert):
    """指定した種類の単位アトリビュートの数値だけを換算する。

    角度と時間で共通の処理。コンパウンドアトリビュートは、子の定義ごとに換算する。
    次のものは換算せず、そのまま返す。

    - 指定した種類でない子。
    - 自分で単位を持つ値(EulerRotate・Quaternion・MAngle・MTime・マトリクスなど)。
    - 数値でない値。
    - 成分の数が子の数と違う入力(正しいかは書き込む側で確かめる)。

    Args:
        plug (om2.MPlug): 型を調べるプラグ。
        value (object): 換算する値。
        unit_type (int): 換算する単位の種類(``om2.MFnUnitAttribute.kAngle`` など)。
        convert (callable): 数値1つを換算する関数。

    Returns:
        object: 換算した値。換算した成分を含むコンパウンドアトリビュートはtupleで返し、
            換算しなかった値は入力をそのまま返す。
    """
    if value is None or isinstance(value, (str, bytes) + _SELF_UNIT_VALUES):
        return value
    if plug.isArray:
        return value
    if plug.isCompound:
        try:
            items = tuple(value)
        except TypeError:
            return value
        if len(items) != plug.numChildren():
            return value
        converted = tuple(_convert_unit_numbers(plug.child(index), item, unit_type, convert) for index, item in enumerate(items))
        if all(new is old for new, old in zip(converted, items)):
            return value
        return converted
    if not isinstance(value, (int, float)) or not _is_unit_attribute(plug.attribute(), unit_type):
        return value
    return convert(value)


def _convert_angles(plug, value, unit, to_internal=True):
    """角度アトリビュートの数値を、指定した単位とラジアン(内部の単位)の間で換算する。

    コンパウンドアトリビュートは、子の定義ごとに換算する。
    角度でない子、自分で単位を持つ値(EulerRotate・Quaternion・MAngle・マトリクスなど)、数値でない値は、そのまま返す。
    成分の数が子の数と違う入力も換算しない(正しいかは書き込む側で確かめる)。

    Args:
        plug (om2.MPlug): 型を調べるプラグ。
        value (object): 換算する値。
        unit (str | None): ``"deg"`` / ``"rad"``。``"rad"`` とNoneなら換算しない。
        to_internal (bool): Trueなら指定した単位からradへ、Falseならradから指定した単位へ換算する。既定はTrue。

    Returns:
        object: 換算した値。換算した成分を含むコンパウンドアトリビュートはtupleで返し、
            換算しなかった値は入力をそのまま返す。
    """
    if unit != "deg":
        return value
    return _convert_unit_numbers(plug, value, om2.MFnUnitAttribute.kAngle, math.radians if to_internal else math.degrees)


def _convert_times(plug, value, time_unit, to_internal=True):
    """時間アトリビュートの数値を、指定した単位と秒(内部の単位)の間で換算する。

    コンパウンドアトリビュートは、子の定義ごとに換算する。
    時間でない子、``om2.MTime`` などの自分で単位を持つ値、数値でない値は、そのまま返す
    (:func:`_convert_angles` と同じ規則)。

    Args:
        plug (om2.MPlug): 型を調べるプラグ。
        value (object): 換算する値。
        time_unit (str | None): ``"frame"`` / ``"sec"``。``"sec"`` とNoneなら換算しない。
        to_internal (bool): Trueなら指定した単位から秒へ、Falseなら秒から指定した単位へ換算する。既定はTrue。

    Returns:
        object: 換算した値。換算しなかった値は入力をそのまま返す。
    """
    if time_unit != "frame":
        return value
    return _convert_unit_numbers(plug, value, om2.MFnUnitAttribute.kTime, partial(_to_seconds if to_internal else _from_seconds, time_unit=time_unit))


def _read_angle(mplug):
    """角度アトリビュートの値をラジアンで返す。

    UIの角度単位に依存しない。

    Args:
        mplug (om2.MPlug): 角度アトリビュートのプラグ。

    Returns:
        float: rad単位の値。
    """
    return mplug.asMAngle().asRadians()


def _read_distance(mplug):
    """距離アトリビュートの値をcmで返す。

    Args:
        mplug (om2.MPlug): 距離アトリビュートのプラグ。

    Returns:
        float: 内部単位の値。
    """
    return mplug.asMDistance().asCentimeters()


def _read_time(mplug):
    """時間アトリビュートの値を秒で返す。

    Args:
        mplug (om2.MPlug): 時間アトリビュートのプラグ。

    Returns:
        float: 内部単位の値。
    """
    return mplug.asMTime().asUnits(om2.MTime.kSeconds)


def _round_integer(value):
    """小数を四捨五入して整数にする。

    ``cmds.setAttr`` と同じく、0から遠い側へ丸める(2.5は3、-2.5は-3、2.4999は2)。
    整数型・enum・boolのfastの書き込みで、fastでない ``cmds.setAttr`` と入力の意味をそろえるために使う。
    整数はそのまま返す。

    Args:
        value (int | float): 数値。型は呼び出し元で確かめる。

    Returns:
        int: 四捨五入した整数。

    Raises:
        ValueError: nanの場合。
        OverflowError: 無限大の場合。
    """
    if isinstance(value, int):
        return int(value)
    value = float(value)
    rounded = math.floor(abs(value) + 0.5)
    return int(rounded) if value >= 0 else -int(rounded)


def _round_bool(value):
    """数値をboolにする。

    ``cmds.setAttr`` と同じく、四捨五入した値が0でなければTrueにする(0.4はFalse、0.6はTrue)。

    Args:
        value (int | float): 数値。範囲(0〜1)は呼び出し元で確かめる。

    Returns:
        bool: 四捨五入した値が0以外ならTrue。
    """
    return _round_integer(value) != 0


#: 型名 -> (読取、fast setter、入力変換)。数値はOpenMayaで直接読む。
#: floatは読取時にdouble精度で取得し、書込時にはfloatへ設定する。
#: 整数型とboolの入力変換は、cmds.setAttrと同じ四捨五入にする(切捨てにしない)。
_NUMERIC_ACCESS = {
    "bool": (om2.MPlug.asBool, om2.MPlug.setBool, _round_bool),
    "byte": (om2.MPlug.asInt, om2.MPlug.setInt, _round_integer),
    "char": (om2.MPlug.asChar, om2.MPlug.setInt, _round_integer),
    "short": (om2.MPlug.asInt, om2.MPlug.setInt, _round_integer),
    "long": (om2.MPlug.asInt, om2.MPlug.setInt, _round_integer),
    "float": (om2.MPlug.asDouble, om2.MPlug.setFloat, float),
    "double": (om2.MPlug.asDouble, om2.MPlug.setDouble, float),
}
_NUMERIC_READERS = {kind: _NUMERIC_ACCESS[name][0] for kind, name in _NUMERIC_TYPE_NAMES.items() if name in _NUMERIC_ACCESS}
#: 数値アトリビュートの種類と、値を書く関数・変換する型。
NUMERIC_WRITERS = {kind: _NUMERIC_ACCESS[name][1:] for kind, name in _NUMERIC_TYPE_NAMES.items() if name in _NUMERIC_ACCESS}

#: 単位アトリビュートの ``unitType()`` と、値を読む関数。
_UNIT_READERS = {om2.MFnUnitAttribute.kAngle: _read_angle, om2.MFnUnitAttribute.kDistance: _read_distance, om2.MFnUnitAttribute.kTime: _read_time}

#: :func:`value_reader` が「MPlug から直接読めない(``cmds.getAttr`` で読む)」ことを表す値。
_CMDS_READER = False


def typed_data(mplug):
    """typedアトリビュートのデータを取得する。

    値がまだ設定されていない(初期化されていない)場合だけ、nullとして返す。

    Args:
        mplug (om2.MPlug): ノードとアトリビュートが有効であることを確かめてあるプラグ。

    Returns:
        om2.MObject: 読み出したデータのMObject。初期化されていなければnull。
            listなどのPythonの値への変換は、呼び出し元が行う。

    Raises:
        RuntimeError: nullであること以外の理由で、データを取得できない場合。
    """
    try:
        return mplug.asMObject()
    except RuntimeError:
        # asMObjectはnullでもkFailureを送出する。データハンドルでnullだけを
        # 確認し、借りたハンドルは必ず解放する。評価失敗を空値へ読み替えない。
        handle = mplug.asMDataHandle()
        try:
            if handle.data().isNull():
                return om2.MObject.kNullObj
        finally:
            mplug.destructHandle(handle)
        raise


def _read_array(mplug, factory, tuples=False):
    """doubleArrayなどのデータ型の値を、要素の数にかかわらずlistで返す。

    Args:
        mplug (om2.MPlug): 読み取るプラグ。
        factory (type): データのfunction set。
        tuples (bool): Trueなら、点・ベクトル・マトリクスの各要素をtupleへ変換する。既定はFalse。

    Returns:
        list | None: 値のコピー。要素が無ければ[]、初期化されていないデータならNone。
    """
    data = typed_data(mplug)
    if data.isNull():
        return None
    values = factory(data).array()
    if tuples:
        return [tuple(value) for value in values]
    return list(values)


_ARRAY_READERS = {
    _D.kDoubleArray: partial(_read_array, factory=om2.MFnDoubleArrayData),
    _D.kIntArray: partial(_read_array, factory=om2.MFnIntArrayData),
    _D.kStringArray: partial(_read_array, factory=om2.MFnStringArrayData),
    _D.kVectorArray: partial(_read_array, factory=om2.MFnVectorArrayData, tuples=True),
    _D.kPointArray: partial(_read_array, factory=om2.MFnPointArrayData, tuples=True),
    _D.kMatrixArray: partial(_read_array, factory=om2.MFnMatrixArrayData, tuples=True),
}


def value_reader(attribute):
    """``Plug.get()`` がMPlugから直接値を読むための関数を、アトリビュートの定義から選ぶ。

    関数を選ぶだけで、値は読まない。呼び出し元のPlugがこの関数を持っておき、getのたびに今の値を取得する。

    Args:
        attribute (om2.MObject): アトリビュートのMObject。

    Returns:
        callable | Literal[False]: MPlugを受け取って値を返す関数。対象は、bool/int/float系の数値アトリビュート、
            角度・距離・時間の単位アトリビュート、enum、文字列、
            doubleArray/Int32Array/stringArray/vectorArray/pointArray/matrixArray。
            それ以外は ``_CMDS_READER`` を返す。この場合、genericのマトリクスかの判定や、
            cmdsでの読み取りは呼び出し元が行う。
    """
    if attribute.hasFn(om2.MFn.kNumericAttribute):
        return _NUMERIC_READERS.get(om2.MFnNumericAttribute(attribute).numericType(), _CMDS_READER)
    if attribute.hasFn(om2.MFn.kUnitAttribute):
        return _UNIT_READERS.get(om2.MFnUnitAttribute(attribute).unitType(), _CMDS_READER)
    if attribute.hasFn(om2.MFn.kEnumAttribute):
        return om2.MPlug.asInt
    if attribute.hasFn(om2.MFn.kTypedAttribute):
        kind = om2.MFnTypedAttribute(attribute).attrType()
        if kind == om2.MFnData.kString:
            return om2.MPlug.asString
        return _ARRAY_READERS.get(kind, _CMDS_READER)
    return _CMDS_READER
