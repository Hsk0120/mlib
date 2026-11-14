# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
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
from typing import Any, Callable, Literal

__all__ = ['attributeType', 'is_internal_data_type', 'typed_data', 'value_reader']
_N: Any
_D: Any
_API_TYPE_NAMES: dict
_NUMERIC_TYPE_NAMES: dict
_DATA_TYPE_NAMES: dict
_VALUE_DEPENDENT_API_TYPES: frozenset
_VALUE_DEPENDENT_DATA_TYPES: frozenset
_ADD_ATTR_TYPE_NAMES: dict
_PUBLIC_DATA_TYPES: Any
_ADD_ATTR_DATA_TYPE: Any
_ADD_ATTR_ATTRIBUTE_TYPE: Any
_SELF_UNIT_VALUES: tuple

def _add_attr_type_name(attribute: om2.MObject) -> str | None:
    """``MFnAttribute.getAddAttrCmd()`` の型の指定から、型名を求める。

    API 2.0の列挙値で表せない型に使う。データ型(``Int64Array``、データ型として指定した ``double3`` など)と、
    アトリビュート型(``reflectance``、opaqueアトリビュート)がある。

    Args:
        attribute (om2.MObject): アトリビュートのMObject。

    Returns:
        str | None: 型名。データ型を複数受け付けるアトリビュートと、値によって型が変わるアトリビュートはNone。
    """
    ...

def _is_mesh_control_points(mplug: om2.MPlug, attribute: om2.MObject) -> bool:
    """meshの ``controlPoints`` (Mayaがfloat3として扱うアトリビュート)のプラグか調べる。

    Args:
        mplug (om2.MPlug): 調べるプラグ。
        attribute (om2.MObject): プラグのアトリビュート。

    Returns:
        bool: meshの ``controlPoints`` ならTrue。
    """
    ...

def attributeType(mplug: om2.MPlug) -> str | None:
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
    ...

def is_internal_data_type(mplug: om2.MPlug) -> bool:
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
    ...

def _require_number(plug: om2.MPlug, value: object) -> None:
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
    ...

def _convert_units(plug: om2.MPlug, value: object, to_ui: bool = ...) -> Any:
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
    ...

def _plain_angle_unit(unit: str | None, ui_units: bool) -> str | None:
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
    ...

def _plain_time_unit(time_unit: str | None, ui_units: bool) -> str | None:
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
    ...

def _to_seconds(value: float, time_unit: str) -> float:
    """時間の数値を、秒へ変換する。

    Args:
        value (float): 時間の数値。
        time_unit (str): ``"frame"`` (現在のUI時間単位) または ``"sec"``。

    Returns:
        float: 秒の値。secならそのまま返す。
    """
    ...

def _from_seconds(value: float, time_unit: str) -> float:
    """秒の数値を、指定した時間単位へ変換する。

    Args:
        value (float): 秒の値。
        time_unit (str): ``"frame"`` (現在のUI時間単位) または ``"sec"``。

    Returns:
        float: time_unitの単位で表した値。secならそのまま返す。
    """
    ...

def _time_quantity(value: float, time_unit: str) -> om2.MTime:
    """時間の数値を、指定した単位の ``om2.MTime`` にする。

    Args:
        value (float): 時間の数値。
        time_unit (str): ``"frame"`` (現在のUI時間単位) または ``"sec"``。

    Returns:
        om2.MTime: 時間の値。
    """
    ...

def _is_angle_attribute(attribute: om2.MObject) -> bool:
    """角度の単位アトリビュート(doubleAngle・floatAngle)か調べる。

    Args:
        attribute (om2.MObject): アトリビュートの定義。

    Returns:
        bool: 角度の単位アトリビュートならTrue。
    """
    ...

def _is_unit_attribute(attribute: om2.MObject, unit_type: int) -> bool:
    """指定した種類の単位アトリビュートか調べる。

    Args:
        attribute (om2.MObject): アトリビュートの定義。
        unit_type (int): ``om2.MFnUnitAttribute.kAngle`` などの単位の種類。

    Returns:
        bool: 指定した種類の単位アトリビュートならTrue。
    """
    ...

def _convert_unit_numbers(plug: om2.MPlug, value: object, unit_type: int, convert: Callable[..., Any]) -> Any:
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
    ...

def _convert_angles(plug: om2.MPlug, value: object, unit: str | None, to_internal: bool = ...) -> Any:
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
    ...

def _convert_times(plug: om2.MPlug, value: object, time_unit: str | None, to_internal: bool = ...) -> Any:
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
    ...

def _read_angle(mplug: om2.MPlug) -> float:
    """角度アトリビュートの値をラジアンで返す。

    UIの角度単位に依存しない。

    Args:
        mplug (om2.MPlug): 角度アトリビュートのプラグ。

    Returns:
        float: rad単位の値。
    """
    ...

def _read_distance(mplug: om2.MPlug) -> float:
    """距離アトリビュートの値をcmで返す。

    Args:
        mplug (om2.MPlug): 距離アトリビュートのプラグ。

    Returns:
        float: 内部単位の値。
    """
    ...

def _read_time(mplug: om2.MPlug) -> float:
    """時間アトリビュートの値を秒で返す。

    Args:
        mplug (om2.MPlug): 時間アトリビュートのプラグ。

    Returns:
        float: 内部単位の値。
    """
    ...

def _round_integer(value: int | float) -> int:
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
    ...

def _round_bool(value: int | float) -> bool:
    """数値をboolにする。

    ``cmds.setAttr`` と同じく、四捨五入した値が0でなければTrueにする(0.4はFalse、0.6はTrue)。

    Args:
        value (int | float): 数値。範囲(0〜1)は呼び出し元で確かめる。

    Returns:
        bool: 四捨五入した値が0以外ならTrue。
    """
    ...
_NUMERIC_ACCESS: dict
_NUMERIC_READERS: dict
NUMERIC_WRITERS: dict
_UNIT_READERS: dict
_CMDS_READER: bool

def typed_data(mplug: om2.MPlug) -> om2.MObject:
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
    ...

def _read_array(mplug: om2.MPlug, factory: type, tuples: bool = ...) -> list | None:
    """doubleArrayなどのデータ型の値を、要素の数にかかわらずlistで返す。

    Args:
        mplug (om2.MPlug): 読み取るプラグ。
        factory (type): データのfunction set。
        tuples (bool): Trueなら、点・ベクトル・マトリクスの各要素をtupleへ変換する。既定はFalse。

    Returns:
        list | None: 値のコピー。要素が無ければ[]、初期化されていないデータならNone。
    """
    ...
_ARRAY_READERS: dict

def value_reader(attribute: om2.MObject) -> Callable[..., Any] | Literal[False]:
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
    ...
