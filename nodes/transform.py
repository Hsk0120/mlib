"""Transformノードを、マトリクスを使って操作する。"""

import math
import numbers
from typing import Any, Dict

import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.mel as mel
from maya.api.OpenMaya import MSpace

from ..components.pointComponent import _write_points
from ..core import geometryEdit as geometry_edit
from ..core.attributeType import value_reader
from ..core.fastWrite import require_writable, writable_compound
from ..core.nodeEdit import require_editable
from ..decorator import _edit_context, _merge_flags, _pick_alias, _require_bool, _transform_argument_hints, nativeUnits, undoChunk, undoTransaction
from ..maths import EulerRotate, Matrix, Quaternion, Scale, Shear, Translate, Vector
from ..maths.eulerRotate import orderIndex
from ..plugs.plug import Plug
from ..util import _UNSET, _angle_unit, _color_value, _finite, _finite_vector, _from_radians, _to_radians, _world_space, mirrorArguments
from .dagNode import DagNode
from .node import Node, Nodes

#: ターゲットの transform の値(位置・回転など)を使うコンストレイント。ターゲットは Transform に限る。
_TRANSFORM_SOURCE_CONSTRAINTS = frozenset(
    ("parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint", "aimConstraint", "poleVectorConstraint")
)


#: setLimitsのキーと、cmds.transformLimitsの値・有効化フラグ、値の種類(角度・距離・倍率)。
_LIMIT_FLAGS = {"translate" + axis: ("translation" + axis, "enableTranslation" + axis, "distance") for axis in "XYZ"}
_LIMIT_FLAGS.update({"rotate" + axis: ("rotation" + axis, "enableRotation" + axis, "angle") for axis in "XYZ"})
_LIMIT_FLAGS.update({"scale" + axis: ("scale" + axis, "enableScale" + axis, "scale") for axis in "XYZ"})

#: getLimitsのキーと、om2.MFnTransformの最小・最大の制限の種類の名前。
_LIMIT_TYPES = {
    prefix + axis: (f"k{kind}Min{axis}", f"k{kind}Max{axis}")
    for prefix, kind in (("translate", "Translate"), ("rotate", "Rotate"), ("scale", "Scale"))
    for axis in "XYZ"
}

#: rotateOrder の番号順の名前(Maya・om2 の番号と同じ順)。
_ROTATE_ORDER_NAMES = ("xyz", "yzx", "zxy", "xzy", "yxz", "zyx")

#: 変換アトリビュート名の照会キャッシュ。
_TRANSFORM_ATTRIBUTES = {}

#: getRotateでゼロとみなすスケール軸の長さ。Mayaは scale 0 を 1e-12 として評価する。
_NEAR_ZERO_AXIS = 1e-10

#: カーブ形状のJSONファイルの形式名と版。
_CURVE_SHAPES_FORMAT = "mlib.curveShapes"
_CURVE_SHAPES_VERSION = 1

#: om2.MFnNurbsCurveのフォームと、保存する名前・``setAttr -type nurbsCurve`` のフォーム番号。
_CURVE_FORM_NAMES = {om2.MFnNurbsCurve.kOpen: "open", om2.MFnNurbsCurve.kClosed: "closed", om2.MFnNurbsCurve.kPeriodic: "periodic"}
_CURVE_FORM_NUMBERS = {"open": 0, "closed": 1, "periodic": 2}


def _transform_attribute(name):
    """transformノード型のアトリビュートのMObjectを取得する。

    最初の1回だけMayaに問い合わせ、その後は保持した値を返す。
    jointなど、transformの派生型も同じアトリビュートのMObjectを共有する。そのため、
    ``om2.MPlug(node, attribute)`` で、名前で探さずにMPlugを作れる。

    Args:
        name (str): アトリビュートのロング名(``matrix``・``worldMatrix`` など)。

    Returns:
        om2.MObject: transformノード型のアトリビュート。
    """
    attribute = _TRANSFORM_ATTRIBUTES.get(name)
    if attribute is None:
        attribute = om2.MNodeClass("transform").attribute(name)
        _TRANSFORM_ATTRIBUTES[name] = attribute
    return attribute


def _match_scale_signs(quaternion, scale, shear, references):
    """分解したスケールの符号の組み合わせを、基準のスケールの符号に揃える。

    2つの軸のスケールの符号を同時に反転し、残りの軸のまわりに180度回せば、マトリクスは変わらない
    (Dを2つの軸が-1の対角マトリクスとすると、S·Sh·R = (S·D)·(D·Sh·D)·(D·R))。
    ただし、行列式(determinant)の符号は変えられない。そのため、referencesを先頭から順に調べ、
    反転が必要な軸が0個か2個(行列式の符号と合う)の最初の基準に揃える。
    どの基準とも合わない(違う軸が奇数個の)場合は、入力(om2の決まり)のまま返す。

    Args:
        quaternion (om2.MQuaternion): 分解した回転。
        scale (Iterable[float]): 分解したスケール。
        shear (Iterable[float]): 分解したシアー(XY、XZ、YZ)。
        references (Iterable[Iterable[float]]): 符号を合わせる基準のスケールの候補。
            優先する順に並べる(setScaleで指定された値、今のscaleチャンネルの値など)。

    Returns:
        tuple: (quaternion, scale, shear)。scaleとshearは3つの要素のtuple。
    """
    scale = tuple(scale)
    shear = tuple(shear)
    for reference in references:
        flips = tuple((value < 0.0) != (base < 0.0) for value, base in zip(scale, reference))
        count = sum(flips)
        if count == 0:
            return quaternion, scale, shear
        if count == 2:
            break
    else:
        return quaternion, scale, shear
    signs = tuple(-1.0 if flip else 1.0 for flip in flips)
    axis = [0.0, 0.0, 0.0]
    axis[flips.index(False)] = 1.0
    # om2 のクォータニオンの積は左を先に適用する。D(残りの軸まわりの 180 度)の後に元の回転。
    half_turn = om2.MQuaternion(axis[0], axis[1], axis[2], 0.0)
    return (
        om2.MQuaternion.__mul__(half_turn, quaternion),
        (scale[0] * signs[0], scale[1] * signs[1], scale[2] * signs[2]),
        (shear[0] * signs[0] * signs[1], shear[1] * signs[0] * signs[2], shear[2] * signs[1] * signs[2]),
    )


def _closest_euler(quaternion, reference):
    """回転をreferenceの回転順序で表し、referenceにいちばん近い同じ回転の解を返す。

    Args:
        quaternion (om2.MQuaternion): 変換する回転。
        reference (om2.MEulerRotation): 基準の回転。回転順序と、解を選ぶのに使う。

    Returns:
        om2.MEulerRotation: referenceと同じ回転順序で、referenceにいちばん近い解。
            ``MEulerRotation.closestSolution`` で求め、360度の周期と、中間の軸を反転した別の解も考えに入れる。
    """
    rotation = quaternion.asEulerRotation()
    rotation.reorderIt(reference.order)
    return rotation.closestSolution(reference)


def _unwritable_channel_message(plug):
    """チャンネルへの書き込みが失敗したときに、原因になった子を示すメッセージを作る。

    子がロックされている・入力が接続されているチャンネルへの書き込みの失敗に使う。

    Args:
        plug (Plug): 書き込みに失敗した、translate・rotateなどのコンパウンドアトリビュート。

    Returns:
        str | None: 例外のメッセージ。書き込みを妨げている子(または自身)が見つからなければNone。
    """
    for target in [plug] + list(plug.getChildren()):
        if target.isLocked():
            reason = "ロックされています"
        elif target.isDestination():
            source = target.getSource(skipConversionNodes=True)
            reason = f"{source.getFullName()}から接続されています" if source is not None else "入力が接続されています"
        else:
            continue
        return f"{plug.getFullName()}を設定できません: {target.getFullName()}は{reason}。ロックを解除するか切断してください。書き込めないチャンネルを飛ばすにはsafe=Trueを指定します"
    return None


def _curve_number(value, label):
    """カーブ形状のデータの数値を確かめる。

    Args:
        value (object): 確かめる値。
        label (str): 例外のメッセージに使う名前。

    Returns:
        float: 有限な数値。

    Raises:
        ValueError: boolか数値でない場合、またはNaN・無限大の場合。
    """
    if isinstance(value, bool) or not isinstance(value, numbers.Real) or not math.isfinite(value):
        raise ValueError(f"{label}は有限な数値で指定してください: {value!r}")
    return float(value)


def _curve_color(value, label):
    """カーブ形状のデータの表示色を確かめる。

    Args:
        value (object): カラー番号、(r, g, b)、またはNone。
        label (str): 例外のメッセージに使う名前。

    Returns:
        int | tuple[float, float, float] | None: :meth:`DagNode.setOverrideColor` へ渡せる値。

    Raises:
        ValueError: 表示色として正しくない場合。
    """
    try:
        index, rgb = _color_value(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label}: {error}") from error
    return rgb if index is None else index


def _checked_curve_shapes(data):
    """カーブ形状のデータを確かめ、適用に使う形に揃える。シーンは変えない。

    Args:
        data (dict): :meth:`Transform.getCurveShapesData` の形の辞書。

    Returns:
        tuple[object, list[dict]]: Transformの表示色と、確かめたShapeごとの辞書のリスト。

    Raises:
        TypeError: dataが辞書でない場合。
        ValueError: キーが無い場合、または値が正しくない場合。
    """
    if not isinstance(data, dict):
        raise TypeError(f"カーブ形状のデータはdictで指定してください: {type(data).__name__}")
    if "shapes" not in data or not isinstance(data["shapes"], list):
        raise ValueError("カーブ形状のデータには'shapes'のリストが必要です")
    color = _curve_color(data.get("color"), "color")
    entries = []
    for position, entry in enumerate(data["shapes"]):
        label = f"shapes[{position}]"
        if not isinstance(entry, dict):
            raise ValueError(f"{label}はdictで指定してください")
        missing = [key for key in ("name", "degree", "form", "knots", "points") if key not in entry]
        if missing:
            raise ValueError(f"{label}に{', '.join(missing)}がありません")
        name = entry["name"]
        if not isinstance(name, str) or not name or "|" in name or ":" in name:
            raise ValueError(f"{label}.nameは'|'と':'を含まない空でない名前で指定してください: {name!r}")
        degree = entry["degree"]
        if isinstance(degree, bool) or not isinstance(degree, int) or degree < 1:
            raise ValueError(f"{label}.degreeは1以上のintで指定してください: {degree!r}")
        form = entry["form"]
        if form not in _CURVE_FORM_NUMBERS:
            raise ValueError(f"{label}.formは'open'・'closed'・'periodic'のどれかで指定してください: {form!r}")
        points = entry["points"]
        if not isinstance(points, list) or len(points) < degree + 1:
            raise ValueError(f"{label}.pointsはdegree + 1個以上の点のリストで指定してください")
        checked_points = []
        for index, point in enumerate(points):
            if not isinstance(point, (list, tuple)) or len(point) != 3:
                raise ValueError(f"{label}.points[{index}]は3つの数値で指定してください")
            checked_points.append(tuple(_curve_number(value, f"{label}.points[{index}]") for value in point))
        knots = entry["knots"]
        if not isinstance(knots, list) or len(knots) != len(points) + degree - 1:
            raise ValueError(f"{label}.knotsはlen(points) + degree - 1({len(points) + degree - 1})個の数値のリストで指定してください")
        checked_knots = [_curve_number(value, f"{label}.knots") for value in knots]
        if any(later < earlier for earlier, later in zip(checked_knots, checked_knots[1:])):
            raise ValueError(f"{label}.knotsは減少しない並びで指定してください")
        line_width = _curve_number(entry.get("lineWidth", -1.0), f"{label}.lineWidth")
        entries.append(
            {
                "name": name,
                "degree": degree,
                "form": form,
                "knots": checked_knots,
                "points": checked_points,
                "color": _curve_color(entry.get("color"), f"{label}.color"),
                "lineWidth": line_width,
            }
        )
    return color, entries


def _rotation_components(ra, r, jo, rotateAxis, rotate, jointOrient):
    """getQuaternion・setQuaternionの回転の成分の指定を、(ra, r, jo)にまとめる。

    ロング名と短縮名のどちらで指定されても、1つの値にする。

    Args:
        ra (bool): rotateAxisの短縮名の値。指定されていなければ ``_UNSET``。
        r (bool): rotateの短縮名の値。
        jo (bool): jointOrientの短縮名の値。
        rotateAxis (bool): rotateAxisの値。
        rotate (bool): rotateの値。
        jointOrient (bool): jointOrientの値。

    Returns:
        tuple[bool, bool, bool]: (rotateAxis, rotate, jointOrient)。既定は(False, True, True)。

    Raises:
        TypeError: ロング名と短縮名を同時に指定した場合。
    """
    return (
        _pick_alias(rotateAxis, ra, "rotateAxis", "ra", default=False),
        _pick_alias(rotate, r, "rotate", "r", default=True),
        _pick_alias(jointOrient, jo, "jointOrient", "jo", default=True),
    )


def _quaternion_value(value):
    """クォータニオンの入力を確かめて、``om2.MQuaternion`` へ変える。

    Args:
        value (om2.MQuaternion | Iterable[float]): クォータニオン、またはXYZWの4つの数値。

    Returns:
        om2.MQuaternion: 新しい値。

    Raises:
        TypeError: クォータニオンでも数値の並びでもない場合。
        ValueError: 成分の数が4でない場合、または有限でない場合。
    """
    if isinstance(value, om2.MQuaternion):
        return om2.MQuaternion(value)
    if isinstance(value, (str, bytes)):
        raise TypeError(f"Quaternionはクォータニオンか4つの数値で指定してください: {value!r}")
    try:
        items = list(value)
    except TypeError:
        raise TypeError(f"Quaternionはクォータニオンか4つの数値で指定してください: {value!r}") from None
    if len(items) != 4:
        raise ValueError(f"Quaternionは4つの成分で指定してください: {len(items)}個")
    return om2.MQuaternion(*[_finite(item, "value") for item in items])


class Transform(DagNode):
    """Transformノードを扱うクラス。移動・回転・スケールなどの値を調べたり設定したりする。

    このクラスのオブジェクトは、ノードとそのDAGパスを持つ。

    - マトリクス・移動/回転/スケール(TRS)・ピボットを扱う。Shapeの頂点やCVの編集とは別のものとして扱う。
    - 距離はcm、角度はradを基本にする。MayaのUIの単位には左右されない。
    - ローカル側の基準が何かは、メソッドごとに違う。
    - 通常の変更はmaya.cmdsで行い、Undoに記録する。fastがあるメソッドでは、OpenMayaで直接書き換える。
    - safeを持つ設定のメソッドは、書き込めない成分をそのまま残す。ただし、目標の値と一致することや、
      全体を元に戻すことは保証しない。
    """

    def addConstraint(
        self,
        sources,
        type=_UNSET,
        maintainOffset=_UNSET,
        *,
        typ=_UNSET,
        mo=_UNSET,
        createCache=_UNSET,
        cc=_UNSET,
        decompRotationToChild=_UNSET,
        dr=_UNSET,
        deleteCache=_UNSET,
        dc=_UNSET,
        edit=_UNSET,
        e=_UNSET,
        layer=_UNSET,
        l=_UNSET,
        name=_UNSET,
        n=_UNSET,
        query=_UNSET,
        q=_UNSET,
        remove=_UNSET,
        rm=_UNSET,
        skipRotate=_UNSET,
        sr=_UNSET,
        skipTranslate=_UNSET,
        st=_UNSET,
        targetList=_UNSET,
        tl=_UNSET,
        weight=_UNSET,
        w=_UNSET,
        weightAliasList=_UNSET,
        wal=_UNSET,
        offset=_UNSET,
        o=_UNSET,
        skip=_UNSET,
        sk=_UNSET,
        scaleCompensate=_UNSET,
        sc=_UNSET,
        aimVector=_UNSET,
        aim=_UNSET,
        upVector=_UNSET,
        u=_UNSET,
        worldUpObject=_UNSET,
        wuo=_UNSET,
        worldUpType=_UNSET,
        wut=_UNSET,
        worldUpVector=_UNSET,
        wu=_UNSET,
        **kwargs,
    ):
        """指定したターゲットで自身を動かすコンストレイントを作る。

        選択されているものから対象を補うことはしない。通常のcmdsでの更新を、Undoが有効なら1回にまとめる。
        途中で失敗しても、それまでの変更は戻さない。

        Args:
            sources (Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug | Iterable):
                ターゲット。1つか、その並びで指定する。Plug・MPlugはそれを持つノード、Component・Componentsは
                それを持つShapeとして扱う。アトリビュートやコンポーネントの名前の文字列も同じ。
                parent・point・orient・scale・aim・poleVectorでは、Transform(Joint・IkHandleを含む)になる入力だけを受け付ける。
            type (str): コンストレイントの種類。parent、point、orient、scale、aim、poleVector、
                geometry、normal、tangent、pointOnPolyのどれか。末尾にConstraintを付けた名前も指定できる。既定はparent。
            maintainOffset (bool): MayaのmaintainOffset。parent・point・orient・scale・aimのときだけ渡す。既定はFalse。
            createCache (Sequence[float]): MayaのcreateCacheフラグ。開始・終了時刻の2値をUI時間単位で指定する。
            cc (Sequence[float]): createCacheの別名。同時指定は不可。
            decompRotationToChild (bool): MayaのdecompRotationToChildフラグ。省略時はMayaの既定に従う。
            dr (bool): decompRotationToChildの別名。同時指定は不可。
            deleteCache (bool): MayaのdeleteCacheフラグ。省略時はMayaの既定に従う。
            dc (bool): deleteCacheの別名。同時指定は不可。
            edit (bool): Trueは作成専用のこのメソッドでは拒否する。
            e (bool): editの別名。同時指定は不可。
            layer (str): Mayaのlayerフラグ。省略時はMayaの既定に従う。
            l (str): layerの別名。同時指定は不可。
            name (str): Mayaのnameフラグ。省略時はMayaの既定に従う。
            n (str): nameの別名。同時指定は不可。
            query (bool): Trueは作成専用のこのメソッドでは拒否する。
            q (bool): queryの別名。同時指定は不可。
            remove (bool): Mayaのremoveフラグ。省略時はMayaの既定に従う。
            rm (bool): removeの別名。同時指定は不可。
            skipRotate (str | Sequence[str]): MayaのskipRotateフラグ。省略時はMayaの既定に従う。
            sr (str | Sequence[str]): skipRotateの別名。同時指定は不可。
            skipTranslate (str | Sequence[str]): MayaのskipTranslateフラグ。省略時はMayaの既定に従う。
            st (str | Sequence[str]): skipTranslateの別名。同時指定は不可。
            targetList (bool): MayaのtargetListフラグ。省略時はMayaの既定に従う。
            tl (bool): targetListの別名。同時指定は不可。
            weight (float): Mayaのweightフラグ。省略時はMayaの既定に従う。
            w (float): weightの別名。同時指定は不可。
            weightAliasList (bool): MayaのweightAliasListフラグ。省略時はMayaの既定に従う。
            wal (bool): weightAliasListの別名。同時指定は不可。
            offset (Sequence[float]): Mayaのoffsetフラグ。(x, y, z)の3値を指定する。
            o (Sequence[float]): offsetの別名。同時指定は不可。
            skip (str | Sequence[str]): Mayaのskipフラグ。省略時はMayaの既定に従う。
            sk (str | Sequence[str]): skipの別名。同時指定は不可。
            scaleCompensate (bool): MayaのscaleCompensateフラグ。省略時はMayaの既定に従う。
            sc (bool): scaleCompensateの別名。同時指定は不可。
            aimVector (Sequence[float]): MayaのaimVectorフラグ。(x, y, z)の3値を指定する。
            aim (Sequence[float]): aimVectorの別名。同時指定は不可。
            upVector (Sequence[float]): MayaのupVectorフラグ。(x, y, z)の3値を指定する。
            u (Sequence[float]): upVectorの別名。同時指定は不可。
            worldUpObject (Node | Plug | Component | str | om2.MObject | om2.MDagPath | om2.MPlug): ワールドアップの基準にするノード。
                Plug・Componentは、それを持つノードとして扱う。Componentsは指定できない。
            wuo (Node | Plug | Component | str | om2.MObject | om2.MDagPath | om2.MPlug): worldUpObjectの別名。同時指定は不可。
            worldUpType (str): MayaのworldUpTypeフラグ。省略時はMayaの既定に従う。
            wut (str): worldUpTypeの別名。同時指定は不可。
            worldUpVector (Sequence[float]): MayaのworldUpVectorフラグ。(x, y, z)の3値を指定する。
            wu (Sequence[float]): worldUpVectorの別名。同時指定は不可。
            **kwargs: 選んだMayaのコンストレイントのコマンドへそのまま渡す、ほかの作成フラグ。
            typ (str): typeの別名。同時指定は不可。
            mo (bool): maintainOffsetの別名。同時指定は不可。

        Returns:
            Constraint: 種類に合ったクラスのオブジェクト。同じ種類のコンストレイントがすでにあれば、
                Mayaの規則でそこへターゲットが追加されることがある。

        Raises:
            TypeError: 種類の名前・ターゲットの型・ロング名と短縮名のフラグの指定が正しくない場合、
                または上に書いた6種類で、ターゲットがTransformでない場合。
            ValueError: 対応していない種類の場合、ターゲットが空の場合、query・editにTrueを指定した場合、
                またはworldUpObjectが無効な場合。
            RuntimeError: ノードが無効な場合、ターゲットの名前からノードを特定できない場合(存在しない場合や、
                複数のノードに一致する場合)、またはMayaが作成を拒否した場合。
            DeletedAttributeError: 削除されたアトリビュートのPlug・MPlugの場合。ValueErrorとRuntimeErrorの派生クラス。

        Note:
            PoleVectorにはRP IKハンドル、Geometry・Normal・PointOnPolyには対応する形状、TangentにはNURBSカーブが必要。
        """
        _merge_flags(
            kwargs,
            (
                (createCache, cc, "createCache", "cc"),
                (decompRotationToChild, dr, "decompRotationToChild", "dr"),
                (deleteCache, dc, "deleteCache", "dc"),
                (layer, l, "layer", "l"),
                (name, n, "name", "n"),
                (remove, rm, "remove", "rm"),
                (skipRotate, sr, "skipRotate", "sr"),
                (skipTranslate, st, "skipTranslate", "st"),
                (targetList, tl, "targetList", "tl"),
                (weight, w, "weight", "w"),
                (weightAliasList, wal, "weightAliasList", "wal"),
                (offset, o, "offset", "o"),
                (skip, sk, "skip", "sk"),
                (scaleCompensate, sc, "scaleCompensate", "sc"),
                (aimVector, aim, "aimVector", "aim"),
                (upVector, u, "upVector", "u"),
                (worldUpType, wut, "worldUpType", "wut"),
                (worldUpVector, wu, "worldUpVector", "wu"),
            ),
        )
        _merge_flags(kwargs, ((edit, e, "edit", "e"), (query, q, "query", "q"), (worldUpObject, wuo, "worldUpObject", "wuo")))
        type = _pick_alias(type, typ, "type", "typ", default="parent")
        maintainOffset = _pick_alias(maintainOffset, mo, "maintainOffset", "mo", default=False)
        with undoChunk("mlibTransformAddConstraint"):
            # 循環参照の回避: 同じパッケージ内で相互に参照するため、使う時点で読み込む。
            from .constraint import Constraint

            # 型登録を重複管理せず、Constraint 派生として明示登録された型名から判定する。
            # 抽象型 "constraint" は cmds に同名コマンドが無いので除く(生成クラスは含まれない)。
            supported = set(Node._registry._registered_types(base=Constraint)) - {"constraint"}
            if not isinstance(type, str):
                # addConstraint("parent", ctrl) のように型名とターゲットを逆に渡した場合は順序を案内する。
                if isinstance(sources, str) and (sources if sources.endswith("Constraint") else sources + "Constraint") in supported:
                    raise TypeError(
                        f"addConstraint()は最初にターゲット、コンストレイントの種類をtype=で受け取ります。addConstraint(target, type={sources!r})のように使います"
                    )
                raise TypeError(
                    f"typeは'parent'のような文字列で指定してください: {type.__class__.__name__}。addConstraint(target, type=\"parent\")のように使います"
                )
            command_name = type if type.endswith("Constraint") else type + "Constraint"
            if command_name not in supported:
                raise ValueError(f"対応していないコンストレイントの種類です: {type}")
            self._require_valid("コンストレイント")
            # 循環参照の回避: components は nodes を参照するため、使う時点で読み込む。
            from ..components.component import Component, Components
            from ..plugs.plug import Plug

            # Components は要素へ展開せず、所有シェイプを1つのターゲットとして扱う。
            if isinstance(sources, (Node, str, Plug, Component, Components, om2.MObject, om2.MDagPath, om2.MPlug)):
                sources = [sources]
            # ターゲットの transform の値を使う型。シェイプをターゲットにすると maya.cmds はターゲットの
            # 無い(追従しない)コンストレイントを黙って作るため、Transform 以外は TypeError にする。
            requires_transform = command_name in _TRANSFORM_SOURCE_CONSTRAINTS
            names = []
            for source in Nodes._resolve_inputs(sources):
                if source is None or (isinstance(source, str) and not source):
                    raise TypeError("コンストレイントのソースは空でない名前かNodeオブジェクトで指定してください")
                # 文字列も含めて所有ノードへ解決する。Plug・MPlug・"node.attribute" は所有ノード、
                # Component・"pCube1.vtx[0]" は所有シェイプをターゲットにする(maya.cmds へ
                # プラグ名・コンポーネント名をそのまま渡すとターゲットとして扱われないため)。
                source = Node._resolve_input(source)
                if not source.isValid():
                    raise RuntimeError("コンストレイントのターゲットが無効です")
                if requires_transform and not source.hasFn(om2.MFn.kTransform):
                    raise TypeError(
                        f"{command_name}のソースはトランスフォーム(ジョイントとIKハンドルを含む)で指定してください。シェイプ・コンポーネント・DGノードは指定できません: {source.__class__.__name__} {source.getName()!r}"
                    )
                names.append(source.getFullName())
            if not names:
                raise ValueError("コンストレイントのソースを1つ以上指定してください")

            command_kwargs = dict(kwargs)
            if command_kwargs.get("query") or command_kwargs.get("edit"):
                raise ValueError("addConstraintは作成だけに対応しています。照会と編集にはMayaのコンストレイントのコマンドを使います")
            if "worldUpObject" in command_kwargs:
                command_kwargs["worldUpObject"] = Node._input_name(command_kwargs["worldUpObject"])
            if command_name in {"parentConstraint", "pointConstraint", "orientConstraint", "scaleConstraint", "aimConstraint"}:
                command_kwargs["maintainOffset"] = maintainOffset
            result = getattr(cmds, command_name)(*names, self.getFullName(), **command_kwargs)
            return Node(result[0])

    def deleteConstraints(self, *, fast=False):
        """自身に働いているコンストレイントと、その入力側のpairBlendを削除する。

        - 上流へたどるのは、pairBlend・unitConversionだけ。unitConversionは削除せずに残す。
        - ターゲットのTransformとanimCurveは削除しない。姿勢を保つこと・ベイク・入力のつなぎ直しはしない。
        - 削除しないものへも出力を共有していないか、削除するものがリファレンス・ロックされていないかを、先に確かめる。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Trueなら入力を外してからOpenMayaで削除する。
                Falseならcmds.deleteで削除し、Undoが有効なら1回にまとめる。設定は変えない。
                後で失敗しても、接続を外したことや削除したことは自動では戻さない。

        Returns:
            list[str]: 削除したノードの、削除前の完全な名前を並べ替えたリスト。対象が無ければ空リスト。

        Raises:
            TypeError: fastがboolでない場合。
            RuntimeError: 無効なオブジェクトの場合、出力を共有している場合、削除するものがリファレンス・ロックされている場合、
                またはMayaの処理が失敗した場合。
        """
        with _edit_context("mlibTransformDeleteConstraints", fast):
            self._require_valid("編集")
            owner = self.mnode()
            deleting, bridges, objects = set(), set(), {}

            def key(obj):
                """1回の探索の中で、MObjectに軽い識別子を付ける。"""
                token = om2.MObjectHandle(obj).hashCode()
                objects[token] = obj
                return token

            def inputs(obj):
                """message以外の入力の接続元を、重複なしで取得する。"""
                result = {}
                for plug in om2.MFnDependencyNode(obj).getConnections():
                    if plug.attribute().hasFn(om2.MFn.kMessageAttribute):
                        continue
                    for source in plug.connectedTo(True, False):
                        if not source.attribute().hasFn(om2.MFn.kMessageAttribute):
                            result[key(source.node())] = source.node()
                return result.values()

            def upstream(obj, path):
                """constraintまで届く、決まった種類のノードだけを通る経路を記録する。"""
                token = key(obj)
                if token in path:
                    return False
                fn = om2.MFnDependencyNode(obj)
                if obj.hasFn(om2.MFn.kConstraint):
                    deleting.add(token)
                    return True
                if fn.typeName not in ("pairBlend", "unitConversion"):
                    return False
                found = False
                for source in inputs(obj):
                    found = upstream(source, path | {token}) or found
                if found:
                    (deleting if fn.typeName == "pairBlend" else bridges).add(token)
                return found

            owner_key = key(owner)
            for source in inputs(owner):
                upstream(source, {owner_key})
            allowed = deleting | bridges | {owner_key}
            for token in deleting | bridges:
                fn = om2.MFnDependencyNode(objects[token])
                for plug in fn.getConnections():
                    if plug.attribute().hasFn(om2.MFn.kMessageAttribute):
                        continue
                    for destination in plug.connectedTo(False, True):
                        if not destination.attribute().hasFn(om2.MFn.kMessageAttribute) and key(destination.node()) not in allowed:
                            raise RuntimeError(f"コンストレイントの経路に共有された出力があります: {fn.name()}")
            for token in deleting:
                require_editable(objects[token])
            names = sorted(Node(objects[token]).getFullName() for token in deleting)
            if names:
                if fast:
                    self._detach_inputs(objects[token] for token in deleting)
                    modifier = om2.MDagModifier()
                    for token in deleting:
                        modifier.deleteNode(objects[token], False)
                    modifier.doIt()
                else:
                    cmds.delete(names)
            return names

    def mfn(self):
        """このTransformのfunction setを取得する。

        Transformに使えるもののうち、最も具体的な ``om2.MFnTransform`` を返す。呼び出すたびに、
        このオブジェクトが持つDAGパスから新しく作る。Jointなどの派生型も、このfunction setを使う。

        Returns:
            om2.MFnTransform: この Transform の function set。

        Raises:
            RuntimeError: 保持していた DAG パスが無効な場合。
        """
        return om2.MFnTransform(self.mpath())

    def scaleGeometry(self, scale, worldSpace=_UNSET, pivot=(0.0, 0.0, 0.0), indices=None, *, fast=False, ws=_UNSET):
        """直下のShape(中間オブジェクトを除く)の頂点やCVを、拡大・縮小する。

        Transformのマトリクスは変えない。Shapeごとに確かめて書き換えるため、後のShapeで拒否されても、
        先に変えたShapeはそのまま残る。形状を共有しているインスタンスでは、すべてのインスタンスに影響する。

        Args:
            scale (float | Iterable[float]): 倍率。1つの数ならXYZに同じ倍率、3つならXYZごとの倍率。
            worldSpace (bool): Trueならワールド空間、Falseなら各Shapeのオブジェクト空間で拡大・縮小する。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 拡大・縮小の中心。worldSpaceで選んだ空間での位置で、単位はcm。既定は原点。
            indices (Iterable[int | tuple[int, int]] | None): 対象の頂点またはCVの番号。どのShapeにも同じ番号を使う。
                Noneならすべてが対象。サーフェスでは(U, V)の組で指定する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Trueで使えるのは、ヒストリの無いメッシュと周期的でないカーブだけ。
                Falseなら通常の方法で書き込み、Undoが有効なら1回にまとめる。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: fastや番号の型が正しくない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 倍率・中心・空間の指定が正しくない場合。
            IndexError: 番号が範囲外の場合。
            RuntimeError: Mayaが変更を拒否した場合。
            NotImplementedError: 対応していないShapeの場合、またはfastで書き換えられる条件に合わない場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        with _edit_context("mlibTransformScaleGeometry", fast):
            ws = _world_space(worldSpace)
            indices = None if indices is None else tuple(indices)
            scale = scale if isinstance(scale, numbers.Real) else tuple(scale)
            pivot = tuple(pivot)
            for shape in self.getShapes():
                shape.scaleGeometry(scale, worldSpace=ws, pivot=pivot, indices=indices, fast=fast)
            return self

    def mirrorGeometry(self, axis="x", worldSpace=_UNSET, pivot=(0.0, 0.0, 0.0), indices=None, *, fast=False, ws=_UNSET):
        """直下のShape(MeshとNurbsCurve。中間オブジェクトを除く)の頂点やCVを、中心pivotに対して反転する。

        処理は各Shapeの :meth:`Mesh.mirror <mlib.nodes.mesh.Mesh.mirror>`・
        :meth:`NurbsCurve.mirror <mlib.nodes.nurbsCurve.NurbsCurve.mirror>` と同じ。
        すべてのShapeについて、入力・番号の範囲・fastで書き換えられる条件を先に確かめてから、
        1回のUndoにまとめて行う(fastではUndoに記録しない)。

        Transformのマトリクスとトポロジーは変えない。マイナスのスケールで反転するのとは違う
        (位置と向きを反転するには :meth:`mirrorTransform` を使う)。
        形状を共有しているインスタンスでは、すべてのインスタンスに影響する。

        Args:
            axis (str | int): 反転の指定。反転する軸 ``"x"``・``"y"``・``"z"``、ミラー面 ``"YZ"``・``"XZ"``・``"XY"``、
                または0・1・2で指定する。xはYZ、yはXZ、zはXYと同じ。文字の順番と大文字・小文字は問わない。
            worldSpace (bool): Trueならワールド空間、Falseなら各Shapeのオブジェクト空間で反転する。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 反転の中心のXYZ(cm)。worldSpaceで選んだ空間での位置。
                既定は原点で、Transformのピボットは使わない。
            indices (Iterable[int] | None): 対象の頂点またはCVの番号。どのShapeにも同じ番号を使う。
                Noneならすべてが対象。空なら何も変えない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform: 自身。Shapeが無ければ何もしない。

        Raises:
            TypeError: worldSpace・fastがboolでない場合、axisが文字列でもintでもない場合、番号の型が正しくない場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: axis・pivotが正しくない場合、Mesh・NurbsCurve以外のShapeがある場合、またはworldSpace=Trueで
                変換のマトリクスがほぼ特異な場合。
            IndexError: 番号がどれかのShapeの範囲外の場合。
            RuntimeError: Transformが無効な場合、またはロックなどのためにMayaが書き込みを拒否した場合。
            NotImplementedError: fast=Trueで、入力のヒストリがあるShapeがある場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        self._require_valid("ジオメトリのミラー")
        # pivot・indicesに反復子を渡されても、全Shapeへ同じ値を使う。
        _, center = mirrorArguments(axis, pivot)
        indices = None if indices is None else tuple(indices)
        plans = []
        for shape in self.getShapes():
            planner = getattr(shape, "_mirror_plan", None)
            if planner is None:
                raise ValueError(f"mirrorGeometryはmeshとnurbsCurveのシェイプに対応しています: {shape.getFullName()}")
            plans.append(planner(axis, ws, center, indices, fast))
        _write_points(plans, fast, "mlibTransformMirrorGeometry")
        return self

    def getPivot(self, worldSpace=_UNSET, *, kind="rotate", ws=_UNSET):
        """回転ピボットかスケールピボットの位置を、cmで取得する。

        Args:
            worldSpace (bool): Trueならワールド空間。Falseなら、xformのobjectSpaceに当たる
                MSpace.kPreTransform。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            kind (str): どのピボットか。rotateは回転ピボット、scaleはスケールピボット。

        Returns:
            Translate: 位置の新しい値。ノードとは切り離されている。UIの距離の単位に関係なくcm。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: kindがrotateでもscaleでもない場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        if kind not in ("rotate", "scale"):
            raise ValueError("kindは'rotate'か'scale'で指定してください")
        # xformのobjectSpaceはMFnTransformのkPreTransformに対応する。
        fn = self.mfn()
        space = MSpace.kWorld if ws else MSpace.kPreTransform
        point = fn.rotatePivot(space) if kind == "rotate" else fn.scalePivot(space)
        return Translate(point.x, point.y, point.z)

    def setPivot(self, value, worldSpace=_UNSET, *, kind="rotate", preserve=True, fast=False, ws=_UNSET):
        """ピボットを動かす。既定ではノードの姿勢を保つ。

        Args:
            value (Iterable[float]): 新しいピボットの位置。XYZの3つの値で、UIの距離の単位に関係なくcm。
            worldSpace (bool): Trueならワールド空間。Falseなら、xformのobjectSpaceに当たる
                MSpace.kPreTransform。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            kind (str): どのピボットか。rotate・scale・bothのどれか。bothなら両方を同じ位置にする。
            preserve (bool): Trueなら、ピボットの補正値を調整してマトリクスを保つ。
                Falseなら補正しないので、姿勢が変わることがある。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: preserveがboolでない場合、対象がJointの場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: kindが正しくない場合、または座標の数や値(有限か)が正しくない場合。
            RuntimeError: ノードが無効な場合、変えるピボットや補正値(preserve=Trueのとき)の成分が
                ロックされている・入力が接続されている場合、またはMayaが設定を拒否した場合。
                ロックは通常でもfastでも書き換える前に確かめ、そのときは何も変えない。

        Note:
            Jointはピボットを単独で動かせないため、書き換える前に拒否する。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        with _edit_context("mlibTransformSetPivot", fast):
            ws = _world_space(worldSpace)
            if kind not in ("rotate", "scale", "both"):
                raise ValueError("kindは'rotate'・'scale'・'both'のどれかで指定してください")
            _require_bool(preserve, "preserve")
            if self.isType("joint"):
                raise TypeError("Jointは回転とスケールのピボットを別々に持てません")
            values = tuple(value)
            if len(values) != 3 or not all(math.isfinite(v) for v in values):
                raise ValueError("ピボットは3つの有限な座標で指定してください")
            kinds = ("scale", "rotate") if kind == "both" else (kind,)
            # APIはロックを迂回し、cmds.xformはロックされた成分を黙って飛ばすため、
            # 通常とfastのどちらも変更する補償値を含めて書く前に確認する。
            self._require_pivots_writable(kinds, preserve)
            if fast:
                fn = self.mfn()
                point = om2.MPoint(*values)
                space = MSpace.kWorld if ws else MSpace.kPreTransform
                for selected in kinds:
                    setter = fn.setRotatePivot if selected == "rotate" else fn.setScalePivot
                    setter(point, space, preserve)
                return self
            coordinates = [om2.MDistance(v).asUnits(om2.MDistance.uiUnit()) for v in values]
            flag = {"rotate": "rotatePivot", "scale": "scalePivot", "both": "pivots"}[kind]
            pivot_flags: Dict[str, Any] = {flag: coordinates}
            cmds.xform(self.getFullName(), worldSpace=ws, objectSpace=not ws, preserve=preserve, **pivot_flags)
            return self

    def centerPivot(self, *, fast=False):
        """回転ピボットとスケールピボットを、バウンディングボックスの中心へ動かす。

        通常はxform(centerPivots=True)で動かす。fastでは、APIで求めた中心をsetPivotへ渡す。
        preserve=Trueで、ピボットの補正値を調整する。コンポーネントの選択は使わない。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: fastがboolでない場合、またはfastで対象がJointの場合。
            RuntimeError: 無効なオブジェクトの場合、ピボットや補正値の成分がロックされている・入力が接続されている場合
                (通常でもfastでも書き換える前に確かめる)、またはMayaが書き換えを拒否した場合。
        """
        with _edit_context("mlibTransformCenterPivot", fast):
            if fast:
                center = self.mfn().boundingBox.center * self.mpath().exclusiveMatrix()
                return self.setPivot((center.x, center.y, center.z), worldSpace=True, kind="both", preserve=True, fast=fast)
            # fast(setPivot経由)と同じく、xformが黙って飛ばすロックを先に拒否する。
            self._require_pivots_writable(("scale", "rotate"), True)
            cmds.xform(self.getFullName(), centerPivots=True, preserve=True)
            return self

    def zeroTransformPivots(self):
        """回転ピボット・スケールピボットとその補正値を0にし、姿勢が変わらないようにtranslateを書き換える。

        ``cmds.xform(zeroTransformPivots=True)`` と同じ。
        ``setPivot((0, 0, 0), kind="both")`` は、補正値(rotatePivotTranslateなど)で姿勢を保つ。
        それに対して、こちらは補正値も0にし、そのずれをtranslateへ移す。
        書き換えるアトリビュートのロックと入力の接続は、書き換える前に確かめる
        (xformはそれらを黙って飛ばし、姿勢が変わってしまうため)。
        Undoが有効なら、1回のUndoで戻せる。fast引数は持たない。

        Returns:
            Transform: 自身。

        Raises:
            RuntimeError: ノードが無効な場合、またはtranslate・ピボット・補正値の成分がロックされている・入力が接続されている場合。
        """
        self._require_valid("ピボットのリセット")
        self._require_pivots_writable(("scale", "rotate"), True)
        plug = self.getPlug("translate").mplug()
        require_writable(plug)
        for index in range(plug.numChildren()):
            require_writable(plug.child(index))
        with undoChunk("mlibTransformZeroTransformPivots"):
            cmds.xform(self.getFullName(), zeroTransformPivots=True)
        return self

    def ungroup(self, *, world=False):
        """子を親(またはワールド)の下へ移して、グループを解く。

        ``cmds.ungroup`` に当たる。子はワールドでの姿勢を保ったまま移す。
        自身がShapeを持っていなければ、自身を削除する。Shapeを持っていれば、子だけを移して自身は残す(Mayaと同じ)。
        Undoが有効なら、1回のUndoで戻せる。

        Args:
            world (bool): Trueなら子をワールドの直下へ移す。既定はFalseで、自身の親の下へ移す。

        Returns:
            list[Transform]: 移した子。元の子の順に並ぶ。子が無ければ空リスト。

        Raises:
            TypeError: worldがboolでない場合。
            RuntimeError: ノードが無効な場合、またはMayaが処理を拒否した場合(ロックされたノードなど)。

        Examples:
            >>> children = group.ungroup()
        """
        _require_bool(world, "world")
        self._require_valid("グループの解除")
        children = [child.mnode() for child in self.getChildren()]
        with undoChunk("mlibTransformUngroup"):
            cmds.ungroup(self.getFullName(), world=world)
        return [Node(child) for child in children]

    def getChildren(
        self, shapes=False, intermediates=False, *, allDescendents=False, order="depthFirst", leaves=False, includeSelf=False, underWorld=False, type=None
    ):
        """条件に合う子、または子孫を取得する。

        Args:
            type (str | Iterable[str] | None): 結果をMayaのノード型で絞る。派生した型も含む(例: ``type="joint"``)。
                規則は :meth:`~mlib.nodes.dagNode.DagNode.getChildren` と同じ。
            shapes (bool): TrueならShapeも含める。既定はFalse(Transformだけ)。
            intermediates (bool): Trueなら中間オブジェクトも含める。
            allDescendents (bool): Trueなら子孫すべてを取得する。既定は直接の子だけ。
            order (str): 並べる順。depthFirstかbreadthFirst。
            leaves (bool): Trueなら、子にTransformを持たないTransform(末端)だけを、下の階層までたどって取得する。
            includeSelf (bool): Trueなら自身も対象にする。自身が末端のときに自身も取得したいときはTrueにする。
            underWorld (bool): Trueなら、Shapeの下のアンダーワールドも調べる。

        Returns:
            list[DagNode]: DAGの子の順に並んだノード。当てはまるものが無ければ空リスト。
        """
        return super().getChildren(
            shapes, intermediates, allDescendents=allDescendents, order=order, leaves=leaves, includeSelf=includeSelf, underWorld=underWorld, type=type
        )

    def getUnusedIntermediateShapes(self):
        """直下にある、使われていない中間オブジェクトのShapeのうち、削除できるものを取得する。

        出力の接続が無い中間オブジェクトのShapeが対象になる。shadingEngineへの通常のメンバーとしての接続は、
        出力の接続として数えない。入力のヒストリだけが残っているShapeも対象になる。

        次のShapeは除く。

        - リファレンスのもの・ノードがロックされているもの
        - インスタンスになっているもの・子のDAGノードを持つもの

        子のTransformより下は調べない。シーンは変えない。

        Returns:
            list[Shape]: 削除の候補。DAGの子の順に並ぶ。無ければ空リスト。

        Raises:
            RuntimeError: Transformが無効な場合、またはMayaからの取得が失敗した場合。
        """
        fn = om2.MFnDagNode(self.mpath())
        if fn.isFromReferencedFile or fn.isLocked:
            return []
        result = []
        for shape in self.getShapes(intermediates=True):
            shape_fn = om2.MFnDagNode(shape.mpath())
            if (
                not shape_fn.isIntermediateObject
                or shape_fn.isFromReferencedFile
                or shape_fn.isLocked
                or shape_fn.childCount()
                or len(om2.MDagPath.getAllPathsTo(shape.mnode())) > 1
            ):
                continue
            used = False
            for plug in shape_fn.getConnections():
                root = plug
                while root.isChild or root.isElement:
                    root = root.parent() if root.isChild else root.array()
                is_membership = om2.MFnAttribute(root.attribute()).name == "instObjGroups"
                for destination in plug.connectedTo(False, True):
                    if is_membership and destination.node().hasFn(om2.MFn.kShadingEngine) and om2.MFnAttribute(destination.attribute()).name == "dagSetMembers":
                        continue
                    used = True
                    break
                if used:
                    break
            if not used:
                result.append(shape)
        return result

    def deleteUnusedIntermediateShapes(self, *, fast=False):
        """直下にある、使われていない中間オブジェクトのShapeだけを削除する。

        判定はgetUnusedIntermediateShapes()と同じで、使われているもの・リファレンスのもの・ロックされているもの・
        インスタンスのものなどは残す。Transformや上流のヒストリのノードは削除しない。
        Maya標準の削除を1回のUndoにまとめ、途中で失敗したら元に戻す。
        通常の方法(fast=False)は、Undoが有効な状態で使う。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。TrueならShapeだけを直接削除する。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: fastがboolでない場合。
            RuntimeError: Transformが無効な場合、または削除が失敗した場合。
        """
        _require_bool(fast, "fast")
        shapes = self.getUnusedIntermediateShapes()
        if shapes:
            if fast:
                self._detach_inputs(shape.mnode() for shape in shapes)
                modifier = om2.MDagModifier()
                for shape in shapes:
                    modifier.deleteNode(shape.mnode(), False)
                modifier.doIt()
            else:
                with undoTransaction("mlibTransformDeleteUnusedIntermediateShapes"):
                    # 標準deleteは入力側の生成履歴も削除する場合があるため、
                    # Shapeへの入力だけをUndo可能に外し、上流ノードを保持する。
                    for shape in shapes:
                        for plug in om2.MFnDependencyNode(shape.mnode()).getConnections():
                            for source in plug.connectedTo(True, False):
                                cmds.disconnectAttr(source.name(), plug.name())
                    cmds.delete([shape.getFullName() for shape in shapes])
        return self

    def addShape(self, shape, *, fast=False):
        """シェイプをこのTransformの下へ移す。

        :meth:`~mlib.nodes.shape.Shape.setParent` と同じ操作を、受け取る側から行う。
        シェイプはローカルの形のまま移る。元のTransformは削除しない。

        Args:
            shape (Shape | str): 移すシェイプ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: shapeがシェイプでない場合、またはfastがboolでない場合。
            RuntimeError: 自身かシェイプが無効な場合、シェイプがインスタンス化されている場合、
                またはMayaが親の変更を拒否した場合。
            NotImplementedError: fastで、自身に同じ名前の子がある場合。
        """
        # shape は transform を参照するため、循環importを避けて関数内で読み込む。
        from .shape import Shape

        node = shape if isinstance(shape, Node) else Node._resolve_input(shape)
        if not isinstance(node, Shape):
            raise TypeError(f"addShapeにはシェイプを指定してください: {type(node).__name__}")
        node.setParent(self, fast=fast)
        return self

    def getShapes(self, intermediates=False):
        """このTransformの直下のShapeを取得する。

        Args:
            intermediates (bool): ``True`` なら中間オブジェクトのShapeも含める。

        Returns:
            list[Shape]: 条件に合うShapeのリスト。
        """
        if not self.isValid():
            return []
        # Shape以外の子はラッパーを作る前に除く(子の順と中間Shapeの扱いは同じ)。
        return self._direct_children(True, intermediates, shapes_only=True)

    def replaceShapes(self, source, *, keepSource=False, worldSpace=_UNSET, ws=_UNSET):
        """自身のShapeを、sourceのShape(中間オブジェクトを除く)に置き換える。

        コントローラーの形を差し替えるための操作。

        - 自身の直下にあるShape(中間オブジェクトも含む)を削除する。
        - sourceのShapeを ``cmds.parent(shape=True)`` で自身の直下へ移す。
        - 移したShapeの名前を ``<自身の名前>Shape`` に変える。2つ目からは ``<自身の名前>Shape<番号>`` にする。

        自身のtranslate・rotate・scale・pivot・接続・子のTransformは変えない。
        全体を1回のUndoにまとめ、途中で失敗したら元に戻す。

        Args:
            source (Transform | Shape | str): 形をもらう元。Transformなら直下のShape(中間オブジェクトを除く)すべて、
                Shapeならそれ1つを使う。
            keepSource (bool): Trueなら、sourceを複製して使い、元のノードは変えない。Falseなら、sourceの
                Shapeを移す。Shapeが無くなり子も残らなかった元のTransformは削除する。
            worldSpace (bool): Trueなら、元のTransformのワールドでの変換を形状に焼き込み、ワールドでの
                見た目を保つ。False(既定)なら、Shapeのローカル座標をそのまま使う(``parent -relative -shape``)。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: keepSource・worldSpaceがboolでない場合、sourceがTransformでもShapeでもない場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: sourceが自身・自身のShape・中間オブジェクトのShapeの場合、または使えるShapeが無い場合。
            RuntimeError: 自身かsourceが無効な場合、またはロック・リファレンスなどのためにMayaが変更を拒否した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(keepSource, "keepSource")
        _require_bool(worldSpace, "worldSpace")
        self._require_valid("シェイプの置き換え")
        source = source if isinstance(source, Node) else Node(source)
        if not source.isValid():
            raise RuntimeError("無効なコピー元からはシェイプを置き換えられません")
        if isinstance(source, Transform):
            holder = source
            shapes = source.getShapes()
        elif isinstance(source, DagNode) and source._require_mnode().hasFn(om2.MFn.kShape):
            if source.isIntermediateObject():
                raise ValueError("sourceに中間オブジェクトのシェイプは指定できません")
            holder = source.getParent()
            # DAG 上の Shape は常に親 Transform を持つ。
            assert holder is not None
            shapes = [source]
        else:
            raise TypeError("sourceはTransformかShapeで指定してください")
        if holder == self:
            raise ValueError("sourceに、対象のトランスフォームやそのシェイプは指定できません")
        if not shapes:
            raise ValueError(f"{source.getName()}に使えるシェイプがありません")
        with undoTransaction("mlibTransformReplaceShapes"):
            duplicate = None
            moving = [shape.getFullName() for shape in shapes]
            if keepSource:
                # Shapeだけの複製は親Transformごと作られるため、Transformを複製して同じ位置の子Shapeを使う。
                positions = [holder.getShapes(intermediates=True).index(shape) for shape in shapes]
                duplicate = cmds.duplicate(holder.getFullName(), returnRootsOnly=True)[0]
                duplicate = cmds.ls(duplicate, long=True)[0]
                copies = cmds.listRelatives(duplicate, shapes=True, fullPath=True) or []
                moving = [copies[position] for position in positions]
            old = [shape.getFullName() for shape in self.getShapes(intermediates=True)]
            if old:
                cmds.delete(old)
            target = self.getFullName()
            if worldSpace:
                matrix = list(holder.mpath().inclusiveMatrix())
                temporary = cmds.createNode("transform", name="mlibReplaceShapesTmp#", skipSelect=True)
                temporary = cmds.ls(temporary, long=True)[0]
                # xformの平行移動は現在のUI単位で解釈されるため、内部単位(cm)へ切り替えて渡す。
                with nativeUnits():
                    cmds.xform(temporary, worldSpace=True, matrix=matrix)
                cmds.parent(moving, temporary, shape=True, relative=True)
                temporary = cmds.ls(cmds.parent(temporary, target)[0], long=True)[0]
                # 取得元のワールド変換と自身の逆変換の差分を、Shapeの形状へ焼き込む。
                cmds.makeIdentity(temporary, apply=True, translate=True, rotate=True, scale=True)
                moving = cmds.listRelatives(temporary, shapes=True, fullPath=True) or []
                cmds.parent(moving, target, shape=True, relative=True)
                cmds.delete(temporary)
            else:
                cmds.parent(moving, target, shape=True, relative=True)
            if duplicate is not None:
                cmds.delete(duplicate)
            elif isinstance(holder, Transform) and holder.isValid() and not cmds.listRelatives(holder.getFullName(), children=True):
                cmds.delete(holder.getFullName())
            leaf = self.getFullName().rsplit("|", 1)[-1]
            for position, shape in enumerate(self.getShapes(intermediates=True)):
                cmds.rename(shape.getFullName(), leaf + ("Shape" if position == 0 else "Shape#"))
        return self

    def getCurveShapesData(self):
        """直下のカーブ形状(中間オブジェクトでないnurbsCurveのShape)を、JSONに書ける辞書で取得する。

        Shapeごとに、次の値をDAGの子の順に記録する。自身の表示色も記録する。

        - 名前(名前空間を除いた短い名前)
        - 次数・フォーム・ノット
        - オブジェクト空間でのCVの位置(cm。UIの長さの単位には左右されない)
        - 描画のオーバーライドの表示色・lineWidth

        bezierCurveなどのほかの種類のShapeと、中間オブジェクトのShapeは含めない。シーンは変えない。

        Returns:
            dict: ``{"color": 表示色, "shapes": [...]}``。``shapes`` の各要素は
                ``{"name", "degree", "form", "knots", "points", "color", "lineWidth"}`` を持つ辞書。
                ``form`` は ``"open"``・``"closed"``・``"periodic"`` のどれか。``points`` は ``[x, y, z]`` のリスト。表示色は :meth:`~mlib.nodes.dagNode.DagNode.getOverrideColor` と同じ
                (カラー番号・(r, g, b)・None)。

        Raises:
            RuntimeError: 自身が無効な場合。
        """
        self._require_valid("カーブ形状の取得")
        shapes = []
        for shape in self._curve_shapes():
            fn = om2.MFnNurbsCurve(shape.mpath())
            leaf = shape.getFullName().rsplit("|", 1)[-1]
            shapes.append(
                {
                    "name": leaf.rsplit(":", 1)[-1],
                    "degree": fn.degree,
                    "form": _CURVE_FORM_NAMES[fn.form],
                    "knots": list(fn.knots()),
                    "points": [[point.x, point.y, point.z] for point in fn.cvPositions(MSpace.kObject)],
                    "color": shape.getOverrideColor(),
                    "lineWidth": fn.findPlug("lineWidth", False).asDouble(),
                }
            )
        return {"color": self.getOverrideColor(), "shapes": shapes}

    def setCurveShapesData(self, data):
        """:meth:`getCurveShapesData` の形のデータで、直下のカーブ形状を作り直す。

        - 直下の中間オブジェクトでないnurbsCurveのShapeを削除し、データのShapeを順に作る(数は違ってもよい)。
        - ほかの種類のShape・中間オブジェクトのShape・子のTransformは残す。
        - CVの位置はオブジェクト空間なので、自身の位置・回転・スケールに対する形を保つ。
        - 新しいShapeの名前は、保存した名前に自身の名前空間を付けたもの。同じ名前がすでにあれば、
          Mayaが番号を付けて重ならないようにする。
        - 各Shapeと自身の表示色(Noneなら ``overrideEnabled`` を無効にする)と、lineWidthも戻す。
        - 削除したShapeの接続とヒストリは戻らない。

        データは、何かを変える前にすべて確かめる。全体を1回のUndoにまとめ、途中で失敗したら元に戻す。

        Args:
            data (dict): :meth:`getCurveShapesData` の形の辞書。``lineWidth`` を省いたShapeは-1(既定の太さ)になる。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: dataが辞書でない場合。
            ValueError: データのキーが無い場合、または値が正しくない場合(シーンは変えない)。
            RuntimeError: 自身が無効な場合、またはロック・リファレンスなどのためにMayaが変更を拒否した場合。
        """
        color, entries = _checked_curve_shapes(data)
        self._require_valid("カーブ形状の設定")
        with _edit_context("mlibTransformSetCurveShapesData", False, transaction=True):
            old = [shape.getFullName() for shape in self._curve_shapes()]
            if old:
                cmds.delete(old)
            target = self.getFullName()
            namespace = target.rsplit("|", 1)[-1].rpartition(":")[0]
            prefix = namespace + ":" if namespace else ""
            for entry in entries:
                created = cmds.createNode("nurbsCurve", name=prefix + entry["name"], parent=target, skipSelect=True)
                # 短い名前が重複する場合があるため、自身の直下のパスに絞る。
                path = [name for name in cmds.ls(created, long=True) if name.rsplit("|", 1)[0] == target][0]
                degree = entry["degree"]
                words = [degree, len(entry["points"]) - degree, _CURVE_FORM_NUMBERS[entry["form"]], "no", 3, len(entry["knots"])]
                words.extend(repr(value) for value in entry["knots"])
                words.append(len(entry["points"]))
                words.extend(repr(value) for point in entry["points"] for value in point)
                # フォームを指定してCVとノットをそのまま設定できるのは、MELの setAttr -type nurbsCurve だけ。
                # CV位置は現在のUI単位で解釈されるため、内部単位(cm)へ切り替えて渡す。
                with nativeUnits():
                    mel.eval(f'setAttr "{path}.cached" -type "nurbsCurve" {" ".join(str(word) for word in words)};')
                cmds.setAttr(path + ".lineWidth", entry["lineWidth"])
                if entry["color"] is not None:
                    Node(path).setOverrideColor(entry["color"])
            self.setOverrideColor(color)
        return self

    def exportCurveShapes(self, path):
        """直下のカーブ形状を、ヘッダー付きのJSONファイルへ書き出す。

        内容は :meth:`getCurveShapesData` と同じで、形式の名前は ``"mlib.curveShapes"`` (版1)。
        同じフォルダーの一時ファイルへ書いてから置き換える。フォルダーは作らない。

        Args:
            path (str | os.PathLike): 書き出し先。

        Returns:
            pathlib.Path: 書き出したファイルの絶対パス。

        Raises:
            RuntimeError: 自身が無効な場合。
            OSError: 書き出しに失敗した場合。
        """
        # 循環参照の回避: mlib.json はノードのクラスより後に読み込まれる。
        from ..json.file import dump

        return dump(self.getCurveShapesData(), path, _CURVE_SHAPES_FORMAT, _CURVE_SHAPES_VERSION)

    def importCurveShapes(self, path):
        """:meth:`exportCurveShapes` のファイルを読み込み、直下のカーブ形状を作り直す。

        作り直し方は :meth:`setCurveShapesData` と同じ。

        Args:
            path (str | os.PathLike): 読み込むファイル。

        Returns:
            Transform: 自身。

        Raises:
            ValueError: JSONとして読めない場合、形式の名前や版が違う場合、またはデータが正しくない場合(シーンは変えない)。
            RuntimeError: 自身が無効な場合、またはMayaが変更を拒否した場合。
            OSError: 読み込みに失敗した場合。
        """
        # 循環参照の回避: mlib.json はノードのクラスより後に読み込まれる。
        from ..json.file import load

        _header, data = load(path, _CURVE_SHAPES_FORMAT, _CURVE_SHAPES_VERSION)
        return self.setCurveShapesData(data)

    def getShape(self, index=0, intermediates=False):
        """指定した番号のShapeを取得する。

        Args:
            index (int): Shapeの番号。既定は0。
            intermediates (bool): ``True`` なら中間オブジェクトのShapeも含めて数える。

        Returns:
            Shape | None: 指定した番号のShape。範囲外ならNone。
        """
        shapes = self.getShapes(intermediates=intermediates)
        try:
            return shapes[index]
        except IndexError:
            return None

    def getTransform(self):
        """Transform自身を取得する。

        Returns:
            Transform: 自身。
        """
        return self

    def setParent(self, parent=None, relative=False, add=False, *, fast=False):
        """Transformの親を変える。

        Args:
            parent (Node | str | om2.MObject | om2.MDagPath | None): 新しい親。Noneならワールドの直下。
                ``Node(parent)`` で扱える型を受け付ける(Plug・Componentは、それを持つノードとして扱う)。
            relative (bool): Trueなら、親を変える前のローカルの変換をそのまま保つ。既定はFalseで、
                Mayaの既定の動き(ワールドでの姿勢を保つ)になる。
            add (bool): Trueなら、今の親はそのままにして、親をもう1つ加える。parentがNoneのときは使わない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。速くなるのは ``relative=True`` のときだけで、
                ワールドでの位置を保つ既定の動きでは、cmds.parentより遅い。
                Joint・インスタンス・親の追加には対応していない(NotImplementedError)。
                通常の方法では、Jointはcmds.parentの動きに従う。relative=Falseのときだけ、
                親のjointのscaleをinverseScaleへ接続する(relative=Trueでは接続しない。Mayaの仕様)。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: fastがboolでない場合、またはfastで、parentがTransformでない場合。
            RuntimeError: 自身が無効な場合、parentが自身か自身の子孫の場合(fastでも同じ)、
                またはfastで、ロック・リファレンスのために変えられない場合。
            NotImplementedError: fastで、Joint・インスタンス・add=Trueを指定した場合。
        """
        with _edit_context("mlibTransformSetParent", fast):
            self._require_valid("親子付け")
            if fast:
                return self._set_parent_fast(parent, relative, add)
            if parent is None:
                if self.getParent() is None and not self.mpath().isInstanced():
                    return self
                cmds.parent(self.getFullName(), world=True, relative=relative)
            else:
                target = parent if isinstance(parent, Node) else Node(parent)
                if isinstance(target, Transform):
                    self._require_not_own_descendant(target)
                parent_name = target.getFullName()
                # 古いMayaでは同じ親への再parentがエラーになる。
                # add=Trueはインスタンス操作なのでMayaの判定に委ねる。
                current = self.getParent()
                if not add and not self.mpath().isInstanced() and current is not None and current.mpath().fullPathName() == parent_name:
                    return self
                cmds.parent(self.getFullName(), parent_name, relative=relative, add=add)
            return self

    def matchTransform(self, target, position=True, rotation=True, scale=True, pivots=False):
        """自身の位置・回転・スケールなどを、指定したTransformに合わせる。選択されているものは使わない。

        空間・joint・ピボットの扱いは、maya.cmds.matchTransformと同じ。Undoが有効なら、1つのチャンクに記録する。
        fast引数は持たない。シアーが一致することや、マトリクス全体が同じになることは保証しない。

        Args:
            target (Transform | str | om2.MObject | om2.MDagPath): 合わせる先のTransformかjoint。
                mlib.Node._resolve_inputが受け付ける型を指定できる(Plugは、それを持つノードとして扱う)。
            position (bool): Trueなら位置を合わせる。
            rotation (bool): Trueなら回転を合わせる。
            scale (bool): Trueならスケールを合わせる。
            pivots (bool): Trueなら回転ピボット・スケールピボットも合わせる。

        Returns:
            Transform: 自身。すべてのフラグがFalseなら何も変えない。

        Raises:
            TypeError: targetがTransformではない場合。
            RuntimeError: ノードが無効な場合、またはMayaが変更を拒否した場合。
            DeletedAttributeError: targetに、アトリビュートが削除されたPlug・MPlugを渡した場合
                (ValueErrorとRuntimeErrorの両方の派生クラス)。
        """

        with undoChunk("mlibTransformMatchTransform"):
            target = Node._resolve_input(target)
            if not isinstance(target, Transform):
                raise TypeError("ターゲットはtransformかjointで指定してください")
            if any((position, rotation, scale, pivots)):
                cmds.matchTransform(self.getFullName(), target.getFullName(), position=position, rotation=rotation, scale=scale, pivots=pivots)
            return self

    def mirrorTransform(self, axis="x", worldSpace=_UNSET, pivot=(0.0, 0.0, 0.0), *, fast=False, ws=_UNSET):
        """位置と向きを、指定した空間でビヘイビアミラーする。

        回転の決まりはMatrix.mirrorと同じ。マイナスのスケールで形状を反転するのとは違う。

        - Shapeの頂点やCVは変えない。子孫は、普通の親子関係として一緒に動く。
        - 指定した空間でのスケールとシアーを保つ。ただし、親に均一でないスケールがある場合は、
          ローカルのスケールとシアーが変わることがある。

        Args:
            axis (str | int): 反転の指定。反転する軸 ``"x"``・``"y"``・``"z"``、ミラー面 ``"YZ"``・``"XZ"``・``"XY"``、
                または0・1・2で指定する。xはYZ、yはXZ、zはXYと同じ。文字の順番と大文字・小文字は問わない。
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間で反転する。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 反転の中心。worldSpaceで選んだ空間での位置で、内部の距離の単位のcm。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: fastがboolでない場合、axisが文字列でもintでもない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: axis・pivotが正しくない場合、親のマトリクスが特異な場合、
                または対応していないピボット・rotateAxisがある場合。
            RuntimeError: ロックや入力の接続のために書き換えられない場合。

        Note:
            setMatrix()と同じ制約があり、0でないピボットや、TransformのrotateAxisがあると、書き換える前に拒否する。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        with _edit_context("mlibTransformMirrorTransform", fast):
            ws = _world_space(worldSpace)
            _require_bool(ws, "worldSpace")
            _, center = mirrorArguments(axis, pivot)
            parent_node = self.getParent()
            parent = Matrix()
            if parent_node is not None and self.getPlug("inheritsTransform").get():
                # 親のチャンネル変更直後も評価済み値を取得する。
                parent = parent_node.getPlug("worldMatrix")[parent_node.mpath().instanceNumber()].get()
            offset = self.getPlug("offsetParentMatrix").get()
            effective_parent = offset * parent
            magnitude = max(1.0, *(sum(abs(effective_parent[row, col]) for col in range(3)) for row in range(3)))
            if abs(effective_parent.det4x4()) <= 1e-12 * magnitude**3:
                raise ValueError("親かoffsetParentMatrixが特異なため、ミラーできません")
            attributes = ["rotatePivot", "scalePivot", "rotatePivotTranslate", "scalePivotTranslate"]
            if not self._require_mnode().hasFn(om2.MFn.kJoint):
                attributes.append("rotateAxis")
            if any(any(self.getPlug(attr).get()) for attr in attributes):
                raise ValueError("mirrorTransformは、0でないピボットとトランスフォームのrotateAxisに対応していません")
            world = self.getMatrix(worldSpace=True)
            source = world if ws else world * parent.inverse()
            target = source.mirror(axis, center)
            target_world = target if ws else target * parent
            local = target_world * effective_parent.inverse()
            self.setMatrix(local, fast=fast)
            return self

    def getShadingEngines(self):
        """直下のShape(中間オブジェクトを除く)が使っているシェーディンググループのセットを取得する。

        Returns:
            list[ShadingEngine]: 直下の中間オブジェクトでないShapeが使っているセット。インスタンスのパスを保つ。
        """
        return list(dict.fromkeys(group for shape in self.getShapes() for group in shape.getShadingEngines()))

    @_transform_argument_hints
    def getMatrix(self, worldSpace=_UNSET, p=_UNSET, inv=_UNSET, *, parent=_UNSET, inverse=_UNSET, ws=_UNSET):
        """指定した空間の、評価済みのマトリクスを取得する。

        - p=Falseのローカルの値は、``matrix`` アトリビュートを使う。offsetParentMatrixは含まない。
        - ワールドの値は、このオブジェクトが持つDAGパスのinclusiveMatrixを使う。offsetParentMatrixも含む。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            p (bool): parentの短縮名。parentと同時には指定できない(TypeError)。
            inv (bool): inverseの短縮名。inverseと同時には指定できない(TypeError)。
            parent (bool): Trueなら、親側のマトリクスを取得する。worldSpace=Trueなら、持っているDAGパスのexclusiveMatrix。
                Falseなら、親のパスのinclusiveMatrix * exclusiveMatrixInverseで求める。既定はFalse。
            inverse (bool): Trueなら、選んだマトリクスの逆マトリクスを取得する。既定はFalse。

        Returns:
            Matrix: 呼び出した時点のマトリクスのコピー。シーンとは切り離されている。

        Raises:
            TypeError: ロング名と短縮名(worldSpaceとws、parentとp、inverseとinv)を同時に指定した場合。
            RuntimeError: ノード、または保持するDAGパスが無効な場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        p = _pick_alias(parent, p, "parent", "p", default=False)
        inv = _pick_alias(inverse, inv, "inverse", "inv", default=False)
        ws = _world_space(worldSpace)
        self._require_valid("マトリクスの取得")
        path = self.mpath()
        if ws:
            matrix = path.exclusiveMatrix() if p else path.inclusiveMatrix()
        elif p:
            parent = om2.MDagPath(path).pop()
            matrix = parent.inclusiveMatrix() * parent.exclusiveMatrixInverse()
        else:
            plug = om2.MPlug(self._require_mnode(), _transform_attribute("matrix"))
            matrix = om2.MFnMatrixData(plug.asMObject()).matrix()
        return Matrix._wrap(matrix.inverse() if inv else matrix)

    @_transform_argument_hints
    def setMatrix(self, matrix, worldSpace=_UNSET, safe=False, get=False, *, fast=False, ws=_UNSET):
        """マトリクスを分解して、translate・rotate・scale・shearのうち値が変わるものに設定する。

        - ピボット・rotateAxis・jointOrient・offsetParentMatrixは変えない。
        - スケールの符号と、同じ回転になるオイラー角の解は、今のチャンネルの値に近いものを選ぶ。
        - 分解した値が今のチャンネルの値(距離はcm・角度はradの内部の値)と完全に同じチャンネルは書き込まない。
          書き込まないチャンネルは、ロック・接続されていても例外にしない。attributeChangedの通知とUndoの記録も、
          書き込んだチャンネルの分だけになる(通常・fast・safeのどれでも同じ)。
        - safeで書けない成分を残した結果、渡したマトリクスと一致しないことがある。

        Args:
            matrix (Matrix | Iterable[float]): 設定するマトリクス。Matrix以外なら16個の値(行の順)で指定する。
            worldSpace (bool): Trueなら、ワールドのマトリクスとして受け取り、持っているDAGパスのexclusiveMatrixInverseで
                ローカルへ変換する。既定はFalseで、``matrix`` アトリビュートと同じ空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            safe (bool): Trueなら、書けない成分はそのままにして、書ける成分だけを変える。
            get (bool): Trueなら書き込まずに、設定する予定のローカルの値を返す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform | dict[str, Translate | EulerRotate | Scale | Shear]: 通常は自身。
                get=Trueなら、translate・rotate・scale・shearの辞書(距離はcm・角度はrad)。
                safe・fastに関係なく計算だけを行い、書き込めるかや、safeを当てた後の結果は確かめない。

        Raises:
            TypeError: fastがboolでない場合、``space=`` を指定した場合(``worldSpace=True`` を使うよう案内する)、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: マトリクスが正しくない・分解できない場合、またはワールドを指定したときに親側のマトリクスの
                逆が求められない場合。
            RuntimeError: ノードが無効な場合、またはMayaが書き込みを拒否した場合(ロック・入力の接続がある成分と、
                ``safe=True`` を案内する)。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        with _edit_context("mlibTransformSetMatrix", fast):
            local_matrix = self._local_matrix(matrix, _world_space(worldSpace))
            if safe or get:
                values = self._matrix_channel_values(local_matrix)
                if get:
                    return values
                self._apply_channel_values(values, safe=True, fast=fast)
            else:
                self._apply_local_matrix(local_matrix, fast=fast)
            return self

    @_transform_argument_hints
    def getTranslation(self, worldSpace=_UNSET, at=2, *, ws=_UNSET):
        """基準の位置を取得する。既定は回転ピボットの位置。

        既定の ``at=2`` は回転ピボットの位置で、MayaのLocal Axisの表示やコンストレイントが、ノードの位置として
        使う基準になる。translateチャンネルの値ではない。translateチャンネルの値は
        ``node.t.get()`` (または ``node.getPlug("translate").get()``)で取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseなら親側の空間で表した位置。
                getPivotのオブジェクト空間とは違う。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            at (int): どこを基準にするか。0以下は親の原点、1はtranslate、2は回転ピボット(既定)、
                3はスケールピボット、4以上はマトリクスの原点。

        Returns:
            Translate: cmで表した位置。ノードとは切り離されている。既定のat=2では、translateチャンネルの値ではない。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        if at >= 3:
            matrix = self.getMatrix(worldSpace=ws)
            if at >= 4:
                return matrix.translate
            point = om2.MPoint(self._static_value("scalePivot")) * matrix
        elif at < 1:
            point = om2.MPoint()
            if ws:
                point *= self.mpath().exclusiveMatrix()
        else:
            value = om2.MVector(self._static_value("translate"))
            if at >= 2:
                offset = om2.MVector(self._static_value("rotatePivot"))
                offset += om2.MVector(self._static_value("rotatePivotTranslate"))
                inv_scale = self._inverse_scale_values()
                value += om2.MVector(*(offset[i] / inv_scale[i] for i in range(3)))
            point = om2.MPoint(value)
            if ws:
                point *= self.mpath().exclusiveMatrix()
        return Translate(point.x, point.y, point.z)

    @_transform_argument_hints
    def setTranslation(self, value, worldSpace=_UNSET, at=2, safe=False, get=False, *, fast=False, ws=_UNSET):
        """指定した基準の位置へ動かす。ピボットと回転は変えない。

        既定の ``at=2`` では、回転ピボットの位置(MayaのLocal Axisの表示やコンストレイントが、ノードの位置として
        使う基準)がvalueに合うように、translateを書き換える。translateチャンネルへ値をそのまま書くときは、
        ``node.t.set((x, y, z))`` を使う。

        at=0以下では、位置をそのまま設定するのではなく、入力を親の空間へ変換した値から今のtranslateを
        引いた値を設定する。例えば、今が2で入力が5なら、translateは3になる。

        Args:
            value (Iterable[float]): cmで表した位置。
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            at (int): どこを基準にするか。getTranslationと同じ。既定は2(回転ピボット)。
            safe (bool): Trueなら、書けない成分は無視する。
            get (bool): Trueなら書き込まずに、設定する予定のローカルのtranslateの値だけを返す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform | list[float]: 自身。get=Trueなら、cmで表したXYZの3つの値のlist(シーンとは切り離されている)。
                safeを指定しても、書き込めるかを反映した最終的な結果の予想ではない。

        Raises:
            TypeError: worldSpaceがboolでない場合、``space=`` を指定した場合(``worldSpace=True`` を使うよう案内する)、
                worldSpaceとwsを同時に指定した場合、または ``setTranslation(1, 2, 3)`` のように
                成分を分けて渡した場合。
            RuntimeError: ノードが無効な場合、またはロック・入力の接続がある成分のために書き込めない場合
                (原因の成分と ``safe=True`` を案内する)。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        with _edit_context("mlibTransformSetTranslation", fast):
            ws = _world_space(worldSpace)
            point = om2.MPoint(tuple(value))
            if ws:
                point *= self.mpath().exclusiveMatrixInverse()
            current = om2.MVector(self._static_value("translate"))
            if at < 1:
                result = om2.MVector(point) - current
            else:
                result = current + (om2.MVector(point) - om2.MVector(tuple(self.getTranslation(at=at))))
            if get:
                return list(result)
            self._set_channel_value("translate", result, safe=safe, fast=fast)
            return self

    def translateBy(self, value, worldSpace=_UNSET, *, ws=_UNSET):
        """今の位置から相対的に移動する。

        ``cmds.move(relative=True)`` に当たる。

        - ``worldSpace=False``: 親の空間の軸(translateチャンネル)に沿って、valueを足す。
        - ``worldSpace=True``: ワールドの軸に沿ってvalueだけ動くように、translateを書き換える。

        書き込むのはtranslateだけで、ピボットと回転は変えない。Undoが有効なら、1回のUndoで戻せる。fast引数は持たない。

        Args:
            value (Iterable[float]): 移動量。XYZの3つの値で、単位はcm。
            worldSpace (bool): Trueならワールドの軸、既定のFalseなら親の空間の軸に沿って動かす。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: valueが数値の並びでない場合、worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: valueの値の数が3でない場合、または有限でない場合。
            RuntimeError: ノードが無効な場合、またはtranslateがロックされている・入力が接続されているために書き込めない場合。

        Examples:
            >>> node.translateBy((0, 1, 0))                 # 親の空間で上へ1cm
            >>> node.translateBy((5, 0, 0), ws=True)        # ワールドのX方向へ5cm
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        world = _world_space(worldSpace)
        delta = om2.MVector(_finite_vector(value, 3, "value"))
        self._require_valid("移動")
        with undoChunk("mlibTransformTranslateBy"):
            # at=1(translate の位置)を基準にすると、ワールド指定でも移動量だけを親の空間へ変換して足せる。
            current = om2.MVector(self.getTranslation(worldSpace=world, at=1))
            self.setTranslation(current + delta, worldSpace=world, at=1)
        return self

    @_transform_argument_hints
    def getRotate(self, worldSpace=_UNSET, *, order=None, ws=_UNSET):
        """指定した空間のマトリクスの回転を、オイラー角の回転として取得する。

        rotateAxisと、Jointの場合はjointOrientも含めた回転を返す。スケールの符号は、今のチャンネルの値に合わせる。

        回転順序と、同じ回転になる解のどれを選ぶかは、次の2つの規則に従う。

        * ``order`` を省いた場合と、ノードのrotateOrderと同じ順序を指定した場合は、ノードの
          rotateOrderで表す。同じ回転になる解は、Transformでは今のrotateチャンネルに、
          Jointでは0の回転にいちばん近いものを選ぶ(``setRotate`` と行き来してもチャンネルの値が変わらない)。
        * それ以外の順序を指定した場合は、クォータニオンを ``asEulerRotation().reorder(order)``
          でそのまま分解した値を返す(解は選び直さない)。``order=0`` (xyz)は、以前の ``getEuler`` と同じ値になる。

        Args:
            worldSpace (bool): Trueならワールド、既定のFalseならローカルのマトリクスの回転を取得する。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            order (int | str | None): 戻り値の回転順序。``"xyz"`` などの名前か、om2の番号
                (``MEulerRotation.kXYZ`` 〜 ``kZYX``。MayaのrotateOrderと同じ0〜5)で指定する。
                NoneならノードのrotateOrder。

        Returns:
            EulerRotate: 回転の値。中身はradで、ノードとは切り離されている。回転順序は ``order`` の指定のとおり
                (省いたときはノードのrotateOrder)。度の3つの値は ``getRotate().asDegrees()`` で取得する。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: orderに対応していない場合、またはマトリクスを分解できない場合。
                どれかのスケールの軸の長さが1e-10以下の場合も含む(Mayaはscaleの0を1e-12として計算する)。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        if order is not None:
            order = orderIndex(order)
        matrix = self.getMatrix(worldSpace=ws)
        for row in range(3):
            if math.sqrt(sum(matrix[row, col] ** 2 for col in range(3))) <= _NEAR_ZERO_AXIS:
                raise ValueError("スケールが0の軸があるマトリクスは分解できません")
        _, quaternion, _, _, reference = self._decompose_like_channels(matrix)
        if order is None or order == reference.order:
            return EulerRotate._wrap(_closest_euler(quaternion, self._rotate_reference(reference)))
        return EulerRotate._wrap(quaternion.asEulerRotation().reorder(order))

    @_transform_argument_hints
    def setRotate(self, value, worldSpace=_UNSET, safe=False, get=False, *, unit="deg", fast=False, ws=_UNSET):
        """指定した空間での回転を設定する。書き込むrotateには、今の値にいちばん近い同じ回転の解を使う。

        - 3つの数値は、ノードのrotateOrderの順に読む。EulerRotateは、値そのものが持つ回転順序を使う。
        - rotateAxisと、Jointの場合はjointOrientを保ち、マトリクスを通してチャンネルの値を計算する。
        - 書き込むのはrotateチャンネルだけで、translate・scale・shearは書き込まない。
          これらはロック・接続されていても例外にせず、通知やUndoの記録もrotateの分だけになる(通常・fast・safeのどれでも同じ)。
        - ピボットが0でない場合は、cmds.setAttrでrotateを設定したときと同じく、ピボットのまわりに回る。

        Args:
            value (Iterable[float] | EulerRotate | Quaternion): 回転の値。EulerRotate・Quaternionの代わりに、
                それぞれの元になっているOpenMayaの型も受け付ける。書き込むときはノードのrotateOrderに揃える。
            worldSpace (bool): Trueならワールド、既定のFalseならローカルのマトリクスでの回転として設定する。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            safe (bool): Trueなら、書けない成分はそのままにする。目標の回転と一致することは保証しない。
            get (bool): Trueなら書き込まずに、設定する予定のローカルのrotateの値を返す。
            unit (str): 3つの数値と、get=Trueのときの戻り値の角度の単位。既定の ``"deg"`` は度、``"rad"`` は
                ラジアン(``"degree"``・``"radians"`` などの別名も使える)。EulerRotate・Quaternionは自分の
                単位(rad)を持つので、unitに関係なく換算しない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform | list[float]: 通常は自身。get=Trueなら、unitの単位(既定は度)でXYZの3つの値のlist
                (シーンとは切り離されている)。safeを当てた後の最終的な結果を予想する値ではない。

        Raises:
            TypeError: fastがboolでない場合、unitが文字列でもNoneでもない場合、``space=`` を指定した場合
                (``worldSpace=True`` を使うよう案内する)、worldSpaceとwsを同時に指定した場合、
                または成分を分けて渡した場合。
            ValueError: unitが対応していない単位の名前の場合、値が3つでない場合、マトリクスを分解できない場合、
                または必要な親のマトリクスの逆が求められない場合。
            RuntimeError: ノードが無効な場合、またはアトリビュートに書き込めない場合(ロック・入力の接続がある
                成分と、``safe=True`` を案内する)。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        with _edit_context("mlibTransformSetRotate", fast):
            ws = _world_space(worldSpace)
            angle_unit = _angle_unit(unit)
            # 既定値 "deg" を持つため、unit=None でも None にならない。
            assert angle_unit is not None
            if not isinstance(value, (om2.MEulerRotation, om2.MQuaternion)):
                self._require_valid("値の設定")
                x, y, z = value
                x, y, z = _to_radians(x, angle_unit), _to_radians(y, angle_unit), _to_radians(z, angle_unit)
                # cmds.xform と同じく、3成分はノードの rotateOrder の値として解釈する。
                value = EulerRotate(x, y, z, self._rotate_order())
            matrix = self._replace_components(self.getMatrix(worldSpace=ws), rotate=value)
            rotation = self._matrix_channel_values(self._local_matrix(matrix, ws))["rotate"]
            if get:
                return [_from_radians(component, angle_unit) for component in rotation]
            self._set_channel_value("rotate", rotation, safe=safe, fast=fast)
            return self

    def rotateBy(self, value, worldSpace=_UNSET, *, unit="deg", ws=_UNSET):
        """今の向きから相対的に回転する。

        ``cmds.rotate(relative=True)`` に当たる。

        - ``worldSpace=False``: 自身のローカルの軸で回す(``cmds.rotate(relative=True, objectSpace=True)``)。
        - ``worldSpace=True``: ワールドの軸で回す(``cmds.rotate(relative=True, worldSpace=True)``)。

        3つの数値は、ノードのrotateOrderの順に読む(``cmds.rotate`` と同じ)。書き込むのはrotateだけ。
        値は :meth:`setRotate` と同じく、今のチャンネルの値にいちばん近い同じ回転の解にする
        (90度ずつ4回回すと、rotateは360になる)。
        Undoが有効なら、1回のUndoで戻せる。fast引数は持たない。

        Args:
            value (Iterable[float] | EulerRotate | Quaternion): 回転量。EulerRotate・Quaternionの代わりに、
                それぞれの元になっているOpenMayaの型も受け付け、その値が持つ回転順序・単位(rad)で読む。
            worldSpace (bool): Trueならワールドの軸、既定のFalseなら自身のローカルの軸で回す。
            unit (str): 3つの数値の角度の単位。既定の ``"deg"`` は度、``"rad"`` はラジアン(別名も使える)。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: valueが数値の並びでも回転の値でもない場合、worldSpaceがboolでない場合、
                unitが文字列でもNoneでもない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: valueの値の数が3でない・有限でない場合、unitが対応していない単位の名前の場合、
                またはマトリクスを分解できない(スケールが0の軸がある)場合。
            RuntimeError: ノードが無効な場合、またはrotateがロックされている・入力が接続されているために書き込めない場合。

        Examples:
            >>> node.rotateBy((0, 90, 0))              # 自身のY軸の周りに90度
            >>> node.rotateBy((0, 0, 45), ws=True)     # ワールドのZ軸の周りに45度
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        world = _world_space(worldSpace)
        angle_unit = _angle_unit(unit)
        self._require_valid("回転")
        if isinstance(value, om2.MQuaternion):
            delta = om2.MQuaternion(value)
        elif isinstance(value, om2.MEulerRotation):
            delta = value.asQuaternion()
        else:
            x, y, z = (_to_radians(component, angle_unit) for component in _finite_vector(value, 3, "value"))
            delta = om2.MEulerRotation(x, y, z, self._rotate_order()).asQuaternion()
        current = self.getRotate(worldSpace=world).asQuaternion()
        # om2 の積は左を先に適用する。ローカル軸の回転は自身の向きより先、ワールド軸の回転は後に掛ける。
        target = current * delta if world else delta * current
        with undoChunk("mlibTransformRotateBy"):
            self.setRotate(target, worldSpace=world)
        return self

    def getRotateOrder(self):
        """回転順序(``rotateOrder``)を名前で取得する。

        Returns:
            str: ``"xyz"``・``"yzx"``・``"zxy"``・``"xzy"``・``"yxz"``・``"zyx"`` のいずれか。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        return _ROTATE_ORDER_NAMES[self.getPlug("rotateOrder").get()]

    def setRotateOrder(self, order, preserve=True):
        """回転順序(``rotateOrder``)を変える。既定では、見た目の向きが変わらないように ``rotate`` も変える。

        - ``preserve=True``: ``cmds.xform(rotateOrder=..., preserve=True)`` と同じ。新しい回転順序で同じ向きに
          なる ``rotate`` を書き込む(アニメーションのキーは変えない)。
        - ``preserve=False``: ``rotateOrder`` だけを書き換えるので、向きが変わる。

        Undoが有効なら、1回のUndoで戻せる。

        Args:
            order (str | int): ``"xyz"`` などの名前(大文字・小文字は問わない)、またはMayaの番号(0〜5)。
            preserve (bool): Trueなら向きを保つ。既定はTrue。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: preserveがboolでない場合。
            ValueError: 対応していない回転順序の場合。
            RuntimeError: ノードが無効な場合、または ``rotateOrder``・``rotate`` のロック・入力の接続のために
                Mayaが書き込みを拒否した場合。
        """
        _require_bool(preserve, "preserve")
        index = orderIndex(order)
        name = self.getFullName()
        with undoChunk("mlibTransformSetRotateOrder"):
            if preserve:
                cmds.xform(name, rotateOrder=_ROTATE_ORDER_NAMES[index], preserve=True)
            else:
                cmds.setAttr(name + ".rotateOrder", index)
        return self

    def getScale(self, worldSpace=_UNSET, *, ws=_UNSET):
        """指定した空間でのスケールの値を取得する。

        Args:
            worldSpace (bool): Trueならワールドでの値。Falseならscaleチャンネルの値。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Scale: XYZの3つの値(単位なし)。ノードとは切り離されている。ローカルでは、SSCを除いた
                チャンネルの値。ワールドでは、APIの決まりでマトリクスを分解した値で、符号がチャンネルと
                同じとは限らない。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        if _world_space(worldSpace):
            return Scale(*om2.MTransformationMatrix(self.getMatrix(worldSpace=True)).scale(MSpace.kTransform))
        return self.getPlug("scale").get()

    @_transform_argument_hints
    def setScale(self, value, worldSpace=_UNSET, safe=False, get=False, *, fast=False, ws=_UNSET):
        """scaleチャンネルだけを設定する。

        ワールドを指定したときは、求めるスケールをローカルで設定する値へ変換する。
        変換しても、書き込むのはscaleだけで、rotateやshearは変えない。

        Args:
            value (Iterable[float]): XYZのスケールの3つの値(単位なし)。
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            safe (bool): Trueなら、書けない成分は無視する。
            get (bool): Trueなら書き込まずに、チャンネルの値を返す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform | list[float]: 自身。get=Trueなら、ローカルで設定する予定のXYZの値のlist(シーンとは切り離されている)。

        Raises:
            TypeError: worldSpace・fastがboolでない場合、``space=`` を指定した場合(``worldSpace=True`` を使うよう
                案内する)、worldSpaceとwsを同時に指定した場合、または成分を分けて渡した場合。
            ValueError: valueが3つの有限の値でない場合。
            RuntimeError: ノードが無効な場合、またはロック・入力の接続がある成分のために書き込めない場合
                (原因の成分と ``safe=True`` を案内する)。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        values = self._scale_channel_value(value, _world_space(worldSpace))
        if get:
            return values
        self._set_channel_value("scale", values, safe=safe, fast=fast)
        return self

    def scaleBy(self, value):
        """今のscaleチャンネルに倍率を掛ける。

        ``cmds.scale(relative=True)`` に当たる。書き込むのはscaleだけで、ピボットを中心に拡大する。
        Undoが有効なら、1回のUndoで戻せる。fast引数は持たない。

        Args:
            value (float | Iterable[float]): 倍率(単位なし)。1つの数ならXYZに同じ倍率、3つなら軸ごとの倍率。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: valueが数値でも数値の並びでもない(boolも含む)場合。
            ValueError: valueの値の数が3でない場合、または有限でない場合。
            RuntimeError: ノードが無効な場合、またはscaleがロックされている・入力が接続されているために書き込めない場合。

        Examples:
            >>> node.scaleBy(2)              # XYZとも2倍
            >>> node.scaleBy((1, 0.5, 1))    # Yだけ半分
        """
        if isinstance(value, numbers.Real) and not isinstance(value, bool):
            factors = (_finite(value, "value"),) * 3
        else:
            factors = _finite_vector(value, 3, "value")
        self._require_valid("スケール")
        current = self.getScale()
        with undoChunk("mlibTransformScaleBy"):
            self._set_channel_value("scale", [current[i] * factors[i] for i in range(3)])
        return self

    def getShear(self, worldSpace=_UNSET, *, ws=_UNSET):
        """指定した空間でのシアーの値を取得する。

        Args:
            worldSpace (bool): Trueならワールドでの値。Falseならshearチャンネルの値。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Shear: XY・XZ・YZの3つの値(単位なし)。ノードとは切り離されている。
                ローカルではチャンネルの値、ワールドではAPIの決まりでマトリクスを分解した値。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        if _world_space(worldSpace):
            return Shear(*om2.MTransformationMatrix(self.getMatrix(worldSpace=True)).shear(MSpace.kTransform))
        return self.getPlug("shear").get()

    def setShear(self, value, worldSpace=_UNSET, safe=False, get=False, *, fast=False, ws=_UNSET):
        """shearチャンネルだけを設定する。

        ワールドを指定したときは、求めるシアーをローカルで設定する値へ変換する。
        変換しても、書き込むのはshearだけで、rotateやscaleは変えない。

        Args:
            value (Iterable[float]): XY・XZ・YZのシアーの3つの値(単位なし)。
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            safe (bool): Trueなら、書けない成分は無視する。
            get (bool): Trueなら書き込まずに、チャンネルの値を返す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform | list[float]: 自身。get=Trueなら、ローカルで設定する予定のXY・XZ・YZの値のlist(シーンとは切り離されている)。

        Raises:
            TypeError: worldSpace・fastがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: valueが3つの有限の値でない場合。
            RuntimeError: ノードが無効な場合、またはロック・入力の接続がある成分のために書き込めない場合
                (原因の成分と ``safe=True`` を案内する)。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        values = self._scale_channel_value(value, _world_space(worldSpace), shear=True)
        if get:
            return values
        self._set_channel_value("shear", values, safe=safe, fast=fast)
        return self

    def getQuaternion(self, worldSpace=_UNSET, ra=_UNSET, r=_UNSET, jo=_UNSET, *, rotateAxis=_UNSET, rotate=_UNSET, jointOrient=_UNSET, ws=_UNSET):
        """選んだ回転の成分を合わせた回転を、クォータニオンで取得する。既定ではrotateAxisを含めない。

        - ローカル空間では、rotateAxis・rotate・(Jointの)jointOrientの順に、選んだ回転を合成する。
        - ワールド空間では、このオブジェクトが持つDAGパスのマトリクスから求め、含めない回転の成分を取り除く。

        ra・r・joで指定できる組み合わせは、setQuaternionと同じではない。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            ra (bool): rotateAxisの短縮名。
            r (bool): rotateの短縮名。
            jo (bool): jointOrientの短縮名。
            rotateAxis (bool): TrueならrotateAxisを含める。既定はFalse。
            rotate (bool): Trueならrotateを含める。既定はTrue。
            jointOrient (bool): TrueならjointOrientを含める。既定はTrue。

        Returns:
            Quaternion: 指定した成分を合成した回転。ノードとは切り離されている。成分の順はXYZW。

        Raises:
            TypeError: ロング名と短縮名(worldSpaceとws、rotateAxisとra、rotateとr、jointOrientとjo)を同時に指定した場合。
            ValueError: 回転の成分と空間の指定が、対応していない組み合わせの場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ra, r, jo = _rotation_components(ra, r, jo, rotateAxis, rotate, jointOrient)
        ws = _world_space(worldSpace)
        joint = self._require_mnode().hasFn(om2.MFn.kJoint)
        if ws:
            if (ra and not (r and jo)) or (not ra and r and not jo):
                raise ValueError("対応していない回転成分の組み合わせです")
            matrix = self.getMatrix(worldSpace=True, p=not (ra or r or (jo and joint)))
            q = om2.MQuaternion().setValue(om2.MMatrix(matrix).homogenize())
            if not ra and (r or (jo and joint)):
                q = self._component_quaternion("rotateAxis").inverse() * q
                if not r:
                    q = self._component_quaternion("rotate").inverse() * q
        else:
            if ra and not r and jo:
                raise ValueError("対応していない回転成分の組み合わせです")
            q = om2.MQuaternion()
            for enabled, name in ((ra, "rotateAxis"), (r, "rotate"), (jo and joint, "jointOrient")):
                if enabled:
                    q *= self._component_quaternion(name)
        return Quaternion._wrap(q)

    def setQuaternion(
        self,
        value,
        worldSpace=_UNSET,
        ra=_UNSET,
        r=_UNSET,
        jo=_UNSET,
        safe=False,
        get=False,
        *,
        unit="deg",
        fast=False,
        rotateAxis=_UNSET,
        rotate=_UNSET,
        jointOrient=_UNSET,
        ws=_UNSET,
    ):
        """回転の成分の指定に従って、rotate・jointOrient・rotateAxisのどれかを設定する。

        受け付ける組み合わせでは、書き込む先は次のようになる。

        - r=True: rotate
        - r=Falseで、Jointでjo=True: jointOrient
        - それ以外のr=False: rotateAxis

        ra・r・joで指定できる組み合わせは、getQuaternionと同じではない。

        Args:
            value (Quaternion | om2.MQuaternion | Iterable[float]): xyzwの回転。
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            ra (bool): rotateAxisの短縮名。
            r (bool): rotateの短縮名。
            jo (bool): jointOrientの短縮名。
            safe (bool): Trueなら、書けない成分は無視する。
            get (bool): Trueなら書き込まずに、計算したオイラー角の値を返す。
            unit (str): get=Trueのときの戻り値の角度の単位。既定の ``"deg"`` は度、``"rad"`` はラジアン
                (``"degree"`` などの別名も使える)。書き込みと、入力のクォータニオンには関係しない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            rotateAxis (bool): Trueなら、入力にrotateAxisを含むものとして扱う。既定はFalse。
            rotate (bool): Trueならrotateを書き換える。FalseならjointOrientかrotateAxisを書き換える。既定はTrue。
            jointOrient (bool): Trueなら、入力にjointOrientを含むものとして扱う。既定はTrue。

        Returns:
            Transform | list[float]: get=Falseなら自身。get=Trueなら、書き込む先のオイラー角の3つの値を
                unitの単位(既定は度)のlistで返す。このとき、safe・fastの指定に関係なくシーンは変えない。
                入力のQuaternionや、XYZWの4つの値を返すものではない。
                rotateに設定する予定の値はノードのrotateOrderの順、ほかの書き込み先はXYZの順。

        Raises:
            TypeError: valueがクォータニオンでも数値の並びでもない場合、unitが文字列でもNoneでもない場合、
                またはロング名と短縮名(worldSpaceとws、rotateAxisとra、rotateとr、jointOrientとjo)を同時に指定した場合。
            ValueError: valueの値の数が4でない・有限でない場合、回転の成分と空間の指定が対応していない組み合わせの場合、
                またはunitが対応していない単位の名前の場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ra, r, jo = _rotation_components(ra, r, jo, rotateAxis, rotate, jointOrient)
        with _edit_context("mlibTransformSetQuaternion", fast):
            angle_unit = _angle_unit(unit)
            # 既定値 "deg" を持つため、unit=None でも None にならない。
            assert angle_unit is not None
            name, rotation = self._quaternion_channel_values(value, _world_space(worldSpace), ra, r, jo)
            if get:
                return [_from_radians(component, angle_unit) for component in rotation]
            self._set_channel_value(name, rotation, safe=safe, fast=fast)
            return self

    def makeIdentity(
        self,
        *,
        apply=_UNSET,
        a=_UNSET,
        jointOrient=_UNSET,
        jo=_UNSET,
        normal=_UNSET,
        n=_UNSET,
        preserveNormals=_UNSET,
        pn=_UNSET,
        rotate=_UNSET,
        r=_UNSET,
        scale=_UNSET,
        s=_UNSET,
        translate=_UNSET,
        t=_UNSET,
        query=_UNSET,
        q=_UNSET,
        edit=_UNSET,
        e=_UNSET,
        **kwargs,
    ):
        """自身を対象にcmds.makeIdentityを実行する。

        省略したフラグはMayaの既定に従う。通常更新をUndo有効時にまとめ、途中失敗の変更は戻さない。

        Args:
            **kwargs (object): MayaのmakeIdentityへ渡す追加フラグ。
            apply (bool): Mayaのapplyフラグ。省略時はMayaの既定に従う。
            a (bool): applyの別名。同時指定は不可。
            jointOrient (bool): MayaのjointOrientフラグ。省略時はMayaの既定に従う。
            jo (bool): jointOrientの別名。同時指定は不可。
            normal (int): Mayaのnormalフラグ。省略時はMayaの既定に従う。
            n (int): normalの別名。同時指定は不可。
            preserveNormals (bool): MayaのpreserveNormalsフラグ。省略時はMayaの既定に従う。
            pn (bool): preserveNormalsの別名。同時指定は不可。
            rotate (bool): Mayaのrotateフラグ。省略時はMayaの既定に従う。
            r (bool): rotateの別名。同時指定は不可。
            scale (bool): Mayaのscaleフラグ。省略時はMayaの既定に従う。
            s (bool): scaleの別名。同時指定は不可。
            translate (bool): Mayaのtranslateフラグ。省略時はMayaの既定に従う。
            t (bool): translateの別名。同時指定は不可。
            query (bool): Mayaのqueryフラグ。省略時はMayaの既定に従う。
            q (bool): queryの別名。同時指定は不可。
            edit (bool): Mayaのeditフラグ。省略時はMayaの既定に従う。
            e (bool): editの別名。同時指定は不可。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: 長短フラグを同時指定した場合。
            RuntimeError: ノードが無効、または Maya が拒否した場合。
        """
        _merge_flags(
            kwargs,
            (
                (apply, a, "apply", "a"),
                (jointOrient, jo, "jointOrient", "jo"),
                (normal, n, "normal", "n"),
                (preserveNormals, pn, "preserveNormals", "pn"),
                (rotate, r, "rotate", "r"),
                (scale, s, "scale", "s"),
                (translate, t, "translate", "t"),
                (query, q, "query", "q"),
                (edit, e, "edit", "e"),
            ),
        )
        with undoChunk("mlibTransformMakeIdentity"):
            self._require_valid("トランスフォームのフリーズ")
            cmds.makeIdentity(self.getFullName(), **kwargs)
            return self

    def getOffsetParentMatrix(self):
        """``offsetParentMatrix`` アトリビュートの値を取得する。

        ワールドマトリクスは ``matrix(ローカル) * offsetParentMatrix * 親のワールドマトリクス`` になる。

        Returns:
            Matrix: 呼び出した時点の値のコピー。シーンとは切り離されている。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("offsetParentMatrixの取得")
        plug = self._dependency_fn().findPlug("offsetParentMatrix", False)
        return Matrix._wrap(om2.MFnMatrixData(plug.asMObject()).matrix())

    def setOffsetParentMatrix(self, matrix, *, fast=False):
        """``offsetParentMatrix`` アトリビュートにマトリクスを設定する。

        translate・rotateなどのチャンネルは変えないので、ワールドでの位置は変わる
        (位置を保ったまま移すには :meth:`freezeToOffsetParent` を使う)。

        Args:
            matrix (Matrix | om2.MMatrix | Sequence[float]): 設定するマトリクス。16個の数値でもよい。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: fastがboolでない場合。
            ValueError: matrixをマトリクスへ変換できない場合。
            RuntimeError: ノードが無効な場合、またはロック・入力の接続のためにMayaが設定を拒否した場合。
        """
        with _edit_context("mlibTransformSetOffsetParentMatrix", fast):
            value = matrix if isinstance(matrix, Matrix) else Matrix(matrix)
            self._require_valid("offsetParentMatrixの設定")
            self.getPlug("offsetParentMatrix").set(value, fast=fast)
            return self

    def freezeToOffsetParent(self):
        """今のローカルの変換を ``offsetParentMatrix`` へ移し、変換のチャンネルを初期値に戻す。

        translate・rotate・shearを0、scaleを1にする(Jointは ``jointOrient`` も0にする)。
        ワールドでの位置・向き・大きさが変わらないように、``offsetParentMatrix`` を
        ``(初期化後のmatrix)^-1 * 初期化前のmatrix * 初期化前のoffsetParentMatrix`` にする。

        - ピボット・``rotateAxis``・``rotateOrder`` は変えず、その分も ``offsetParentMatrix`` で補う
          (初期化した後に回転させると、ピボットとrotateAxisはこれまでどおり効く)。
        - Jointの ``segmentScaleCompensate`` の補正(inverseScale)は、親のスケールに合わせて動く値なので0にしない。
          呼び出した時点のワールドを保つように補う。

        書き込む前に、すべての対象が書き込めるかを確かめる。ロック・入力の接続(アニメーションのキーを含む)があれば、
        何も変えずにRuntimeErrorにする。fast引数は持たない。
        Undoが有効なら1回で戻せる。途中で失敗したら元に戻す。

        Returns:
            Transform: 自身。

        Raises:
            ValueError: 初期化した後のローカルのマトリクスの逆が求められない場合(inverseScaleが0のJointなど)。
            RuntimeError: ノードが無効な場合、または対象のチャンネル・offsetParentMatrixがロックされている・入力が接続されている場合。
        """
        self._require_valid("offsetParentMatrixへのフリーズ")
        fn = self._dependency_fn()
        resets = [("translate", (0.0, 0.0, 0.0)), ("rotate", (0.0, 0.0, 0.0)), ("scale", (1.0, 1.0, 1.0)), ("shear", (0.0, 0.0, 0.0))]
        if self._require_mnode().hasFn(om2.MFn.kJoint):
            resets.append(("jointOrient", (0.0, 0.0, 0.0)))
        for attribute in [name for name, _ in resets] + ["offsetParentMatrix"]:
            mplug = fn.findPlug(attribute, False)
            try:
                writable_compound(mplug)
            except RuntimeError as error:
                raise RuntimeError(f"offsetParentMatrixへフリーズできません: {error}") from error
        before = self.getMatrix()
        offset = self.getOffsetParentMatrix()
        name = self.getFullName()
        with undoTransaction("mlibTransformFreezeToOffsetParent"):
            for attribute, value in resets:
                cmds.setAttr(name + "." + attribute, *value)
            after = self.getMatrix()
            if after.isSingular():
                raise ValueError(f"{name}のoffsetParentMatrixへフリーズできません: リセットしたローカルマトリクスが特異です")
            new_offset = Matrix._wrap(after.inverse() * before * offset)
            cmds.setAttr(name + ".offsetParentMatrix", *tuple(new_offset), type="matrix")
        return self

    def eulerFilter(self):
        """rotateX/Y/Zの時間のアニメーションカーブ(animCurveTA)に、オイラーフィルターをかける。

        3本のカーブを1回の ``cmds.filterCurve(filter="euler")`` にまとめて渡す(Mayaのグラフエディターの
        Euler Filterと同じ)。入力に直接(単位変換のノードを飛ばして)つながっているanimCurveTAだけを対象にし、
        キーが無ければ何もしない。fast引数は持たない。Undoが有効なら1回で戻せる。

        Returns:
            Transform: 自身。

        Raises:
            RuntimeError: ノードが無効な場合、またはMayaがフィルターを拒否した場合。
        """
        self._require_valid("回転のフィルター")
        name = self.getFullName()
        curves = []
        for axis in "XYZ":
            for curve in cmds.listConnections(name + ".rotate" + axis, source=True, destination=False, type="animCurveTA", skipConversionNodes=True) or []:
                if curve not in curves:
                    curves.append(curve)
        if curves:
            with undoChunk("mlibTransformEulerFilter"):
                cmds.filterCurve(curves, filter="euler")
        return self

    def getClosestAxisToVector(self, refVector, includeNegative=True):
        """自身のローカルの軸のうち、ワールド空間での向きがいちばん近いものを求める。

        各ローカルの軸をワールドマトリクス(回転とスケールだけ。移動は無視する)で変換し、
        正規化してからrefVectorとの内積を比べ、いちばん大きいものを選ぶ。

        Args:
            refVector (Vector | Iterable[float]): 比べるワールド空間での向きのベクトル。
            includeNegative (bool): Trueなら、マイナス方向の軸(-x・-y・-z)も候補に入れる。

        Returns:
            str: いちばん近い軸の名前("x"・"y"・"z"。includeNegativeがTrueなら
                "-x"・"-y"・"-z" も返ることがある)。

        Raises:
            TypeError: refVectorが3つの数値の並びでもベクトルでもない場合、またはincludeNegativeがboolでない場合。
            ValueError: refVectorの値の数が3でない・有限でない場合、またはrefVectorか、どれかのローカルの軸が
                ワールドへ変換すると長さ0のベクトルになる場合。
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("軸の評価")
        _require_bool(includeNegative, "includeNegative")
        refVector = Vector(*geometry_edit.point_list([refVector])[0]).unit()
        matrix = self.getMatrix(worldSpace=True)
        axes = {"x": Vector(1.0, 0.0, 0.0), "y": Vector(0.0, 1.0, 0.0), "z": Vector(0.0, 0.0, 1.0)}
        if includeNegative:
            axes.update({f"-{name}": axis * -1.0 for name, axis in axes.items()})
        best_axis = None
        best_dot = None
        for name, axis in axes.items():
            world_axis = matrix.transformVector(axis).unit()
            dot = world_axis.dot(refVector)
            if best_dot is None or dot > best_dot:
                best_dot = dot
                best_axis = name
        return best_axis

    def getLimits(self, *, unit="deg"):
        """移動・回転・スケールの制限を、:meth:`setLimits` と同じ形の辞書で取得する。

        9つのチャンネル(``translateX``〜``scaleZ``)すべてについて ``(最小, 最大)`` を返す。制限が無効な側は ``None`` になる。
        ``node.setLimits(**other.getLimits())`` で、別のノードへ同じ制限を写せる(無効な側の値は写さない)。
        距離はcm、角度は ``unit`` の単位(既定は度)。UIの単位には左右されない。

        Args:
            unit (str): 回転の数値の単位。既定の ``"deg"`` は度、``"rad"`` はラジアン(別名も使える)。

        Returns:
            dict[str, tuple[float | None, float | None]]: チャンネルの名前ごとの ``(最小, 最大)``。

        Raises:
            TypeError: unitが文字列でもNoneでもない場合。
            ValueError: unitが対応していない単位の名前の場合。
            RuntimeError: ノードが無効な場合。

        Examples:
            >>> node.setLimits(rotateZ=(-45, 90))
            >>> node.getLimits()["rotateZ"]
            (-45.0, 90.0)
        """
        angle_unit = _angle_unit(unit)
        self._require_valid("リミットの取得")
        fn = self.mfn()
        result = {}
        for channel, kinds in _LIMIT_TYPES.items():
            sides = []
            for kind in kinds:
                limit = getattr(om2.MFnTransform, kind)
                if not fn.isLimited(limit):
                    sides.append(None)
                    continue
                # limitValue は内部単位(距離cm・角度rad)の値を返す。
                value = fn.limitValue(limit)
                sides.append(_from_radians(value, angle_unit) if channel.startswith("rotate") else float(value))
            result[channel] = tuple(sides)
        return result

    def setLimits(self, *, unit="deg", **limits):
        """移動・回転・スケールの制限を、``cmds.transformLimits`` で設定する。

        ``setLimits(translateX=(0, 10), rotateZ=(-45, 90), scaleY=(None, 2))`` のように、チャンネルの名前
        (``translateX``〜``scaleZ`` のロング名)に `` (最小, 最大)`` を渡す。

        - 片側を ``None`` にすると、その側の制限を無効にする(値は変えない)。
        - 値全体を ``None`` にすると、両側の制限を無効にする。
        - 指定しないチャンネルは変えない。

        距離はcm、角度は ``unit`` の単位(既定は度)で指定し、Mayaの今のUIの単位に換算して渡す。
        すべての指定を確かめてから、1回の ``cmds.transformLimits`` で設定する。Undoが有効なら、1回のUndoで戻せる。
        OpenMayaで制限のアトリビュートを書いても速くならないため、fast引数は持たない。

        Args:
            unit (str): 回転の数値の単位。既定の ``"deg"`` は度、``"rad"`` はラジアン(別名も使える)。
            **limits (tuple[float | None, float | None] | None): チャンネルの名前ごとの ``(最小, 最大)``。

        Returns:
            Transform: 自身。

        Raises:
            TypeError: 対応していないチャンネルの名前の場合、値が2つの要素の並びでもNoneでもない場合、
                要素が数値でもNoneでもない場合、またはunitが文字列でもNoneでもない場合。
            ValueError: unitが対応していない単位の名前の場合。
            RuntimeError: ノードが無効な場合、またはMayaが設定を拒否した場合(最小が最大より大きい場合など)。
        """
        angle_unit = _angle_unit(unit)
        unknown = sorted(set(limits) - set(_LIMIT_FLAGS))
        if unknown:
            raise TypeError(f"対応していないリミットのチャンネルです: {', '.join(unknown)}(translateX〜scaleZを使います)")
        self._require_valid("リミットの設定")
        name = self.getFullName()
        flags = {}
        for channel, value in limits.items():
            flag, enable_flag, kind = _LIMIT_FLAGS[channel]
            if value is None:
                value = (None, None)
            if isinstance(value, (str, bytes)) or not isinstance(value, (tuple, list)) or len(value) != 2:
                raise TypeError(f"{channel}のリミットは(min, max)の組かNoneで指定してください: {value!r}")
            current = None
            sides = []
            for index, side in enumerate(value):
                if side is None:
                    if current is None:
                        query_flags: Dict[str, Any] = {flag: True}
                        current = cmds.transformLimits(name, query=True, **query_flags)
                    side = current[index]
                    if kind == "distance":
                        # 照会は移動だけcm(内部単位)で返り、設定はUI単位で受け取る。
                        side = om2.MDistance(side, om2.MDistance.kCentimeters).asUnits(om2.MDistance.uiUnit())
                    sides.append(side)
                    continue
                if isinstance(side, bool) or not isinstance(side, numbers.Real):
                    raise TypeError(f"{channel}のリミットの値は数値かNoneで指定してください: {value!r}")
                if kind == "angle":
                    side = om2.MAngle(side, om2.MAngle.kDegrees if angle_unit == "deg" else om2.MAngle.kRadians).asUnits(om2.MAngle.uiUnit())
                elif kind == "distance":
                    side = om2.MDistance(side, om2.MDistance.kCentimeters).asUnits(om2.MDistance.uiUnit())
                sides.append(float(side))
            flags[flag] = tuple(sides)
            flags[enable_flag] = (value[0] is not None, value[1] is not None)
        if flags:
            with undoChunk("mlibTransformSetLimits"):
                cmds.transformLimits(name, **flags)
        return self

    def _color_targets(self, shape):
        """表示色を読み書きするノードを返す。

        Args:
            shape (bool): 確かめたshapeの指定。

        Returns:
            list[DagNode]: shapeがTrueなら直下の中間オブジェクトでないShape(無ければ自身)、Falseなら自身。
        """
        self._require_valid("表示アトリビュートの取得")
        return (self.getShapes() or [self]) if shape else [self]

    def _curve_shapes(self):
        """直下の中間オブジェクトでないnurbsCurveのShapeを返す。bezierCurveなどの派生型は含めない。

        Returns:
            list[Shape]: DAGの子の順に並んだShape。
        """
        return [shape for shape in self.getShapes() if shape.mnode().apiType() == om2.MFn.kNurbsCurve]

    def _local_matrix(self, matrix, ws):
        """setMatrixの入力を検証し、ローカル空間のマトリクスへ変換する。シーンは更新しない。

        Args:
            matrix (Matrix | Iterable[float]): 適用するマトリクス。
            ws (bool): 検証済みのワールド空間指定。Trueなら、このオブジェクトが持つDAGパスのexclusiveMatrixInverseを掛ける。

        Returns:
            Matrix: ローカル空間のマトリクス。

        Raises:
            ValueError: マトリクスが不正、またはワールド指定時の親が反転不能な場合。
            RuntimeError: ノードが無効な場合。
        """
        if not isinstance(matrix, Matrix):
            matrix = Matrix(matrix)
        self._require_valid("値の設定")
        if not ws:
            return matrix
        path = self.mpath()
        # Mayaの逆変換取得だけでは特異な親を拒否しないため、書込み前に検査する。
        if path.exclusiveMatrix().isSingular():
            raise ValueError("親のマトリクスが特異なため、ワールドマトリクスを適用できません")
        return matrix * Matrix._wrap(path.exclusiveMatrixInverse())

    @staticmethod
    def _detach_inputs(objects):
        """削除しない上流のノードが、孤立したヒストリとして一緒に削除されないようにする。

        削除するノードの入力の接続を、先に外しておく。

        Args:
            objects (Iterable[om2.MObject]): 削除する予定のノード。

        Returns:
            None: 値を返さない。

        Note:
            APIで直接書き換えるので、Undoには記録しない。削除に使うmodifierとは別に、先に確定させる。
        """
        modifier = om2.MDGModifier()
        connected = False
        for obj in objects:
            for plug in om2.MFnDependencyNode(obj).getConnections():
                for source in plug.connectedTo(True, False):
                    modifier.disconnect(source, plug)
                    connected = True
        if connected:
            modifier.doIt()

    def _set_parent_fast(self, parent, relative, add, *, validate_only=False):
        """対応しているTransformかだけを確かめて、APIで親を変える。

        Args:
            parent (Node | None): 新しい親。Noneならワールド。
            relative (bool): Trueなら、ローカルの変換を保つ。
            add (bool): Trueなら、今の親に加える。Trueには対応していない。
            validate_only (bool): Trueなら、すべてを先に確かめるためだけに使い、DAGは変えない。

        Returns:
            Transform: 自身。

        Raises:
            RuntimeError: リファレンス・ロック・循環・特異なマトリクスのために変えられない場合。
            NotImplementedError: Joint・インスタンス・親の追加の場合。
        """
        target = None if parent is None else Node._resolve_input(parent)
        if target is not None and not isinstance(target, Transform):
            raise TypeError("親はtransformで指定してください")
        if target is not None:
            self._require_not_own_descendant(target)
        path = self.mpath()
        if self._require_mnode().hasFn(om2.MFn.kJoint) or path.isInstanced() or (target is not None and target.mpath().isInstanced()) or add:
            raise NotImplementedError("fastのsetParentはジョイント・インスタンス・add=Trueに対応していません")
        require_editable(self._require_mnode())
        if target is not None:
            require_editable(target._require_mnode())
        current = self.getParent()
        if (current is None and target is None) or (current is not None and target is not None and current.mnode() == target.mnode()):
            return self
        world = None if relative else self.getMatrix(worldSpace=True)
        if world is not None:
            parent_matrix = Matrix() if target is None else target.getMatrix(worldSpace=True)
            opm = self.getPlug("offsetParentMatrix").get()
            if abs(parent_matrix.det4x4()) <= 1e-12 or abs(opm.det4x4()) <= 1e-12:
                raise RuntimeError("親かオフセットのマトリクスが特異なため、ワールドのトランスフォームを保てません")
            for name in ("translate", "rotate", "scale", "shear"):
                plug = self.getPlug(name).mplug()
                require_writable(plug)
                for index in range(plug.numChildren()):
                    require_writable(plug.child(index))
        if validate_only:
            return self
        modifier = om2.MDagModifier()
        new_parent = om2.MObject.kNullObj if target is None else target._require_mnode()
        modifier.reparentNode(self._require_mnode(), new_parent)
        modifier.doIt()
        # 自分の操作で変えたパスだけ再束縛し、無関係なインスタンスへ切り替えない。
        self._dag_path = om2.MDagPath.getAPathTo(self.mnode())
        if world is not None:
            self.setMatrix(world, worldSpace=True, fast=True)
        return self

    def _require_not_own_descendant(self, target):
        """親にしようとするノードが、自身または自身の子孫でないことを確かめる。

        Mayaはこの場合 ``Not enough objects or values.`` などの原因が分かりにくいエラーになるため、
        変更の前に分かる文言で拒否する。インスタンスでも判定できるよう、target の全パスの祖先を調べる。

        Args:
            target (Transform): 新しい親。

        Raises:
            RuntimeError: target が自身、または自身の子孫の場合。
        """
        own = self._require_mnode()
        for path in om2.MDagPath.getAllPathsTo(target._require_mnode()):
            while path.length():
                if path.node() == own:
                    raise RuntimeError(f"ノードを自分自身や自分の子孫の下へは親子付けできません: {self.getFullName()} -> {target.getFullName()}")
                path.pop()

    def _static_value(self, name):
        """ノード型に組み込みの数値アトリビュートの内部単位の値を、Plugのオブジェクトを作らずに読む。

        ``getPlug(name).get()`` と同じ読取関数(距離cm・角度rad)をMPlugへ直接適用する。
        コンパウンドアトリビュートは子の値のtuple、単一の値はその値を返す。計算の途中で何度も読む
        translate・ピボット等のために使い、値はキャッシュしない。ノードが無効な場合と
        読取関数を持たない型は、従来どおり ``getPlug(name).get()`` の結果・例外に委ねる。

        Args:
            name (str): 静的アトリビュートのロング名。

        Returns:
            tuple[float, ...] | object: コンパウンドアトリビュートなら子の値のtuple、それ以外は値。
        """
        if not self.isValid():
            # 無効なノードでは、従来と同じgetPlugの例外を送出する。
            return self.getPlug(name).get(unit="rad")
        plug = self._dependency_fn().findPlug(name, False)
        targets = [plug.child(index) for index in range(plug.numChildren())] if plug.isCompound else [plug]
        values = []
        for target in targets:
            reader = value_reader(target.attribute())
            # value_reader は読取関数か False(cmdsでの読取)を返す。
            if not callable(reader):
                value = self.getPlug(name).get(unit="rad")
                return tuple(value) if plug.isCompound else value
            values.append(reader(target))
        return tuple(values) if plug.isCompound else values[0]

    def _inverse_scale_values(self):
        """jointの有効なinverseScaleを返す。joint以外では、大きさ1のスケールを返す。"""
        if self._require_mnode().hasFn(om2.MFn.kJoint) and self._static_value("segmentScaleCompensate"):
            return self._static_value("inverseScale")
        return (1.0, 1.0, 1.0)

    def _scale_channel_value(self, value, ws, shear=False):
        """ワールドのscale/shear要求を、SSCを除いたチャンネル値へ変換する。

        Args:
            value: 変換・設定する入力値。
            ws: Trueはワールド空間、Falseはローカル空間。
            shear: XY/XZ/YZのシアー成分。
        """
        values = tuple(value)
        if len(values) != 3 or not all(math.isfinite(v) for v in values):
            raise ValueError("3つの有限な成分を指定してください")
        if ws:
            transform = om2.MTransformationMatrix(self.getMatrix(worldSpace=True))
            if shear:
                transform.setShear(values, MSpace.kTransform)
            else:
                transform.setScale(values, MSpace.kTransform)
            matrix = transform.asMatrix() * self.mpath().exclusiveMatrixInverse()
            matrix *= Matrix(scale=self._inverse_scale_values())
            transform = om2.MTransformationMatrix(matrix)
            values = transform.shear(MSpace.kTransform) if shear else transform.scale(MSpace.kTransform)
        return list(values)

    def _component_quaternion(self, name):
        """回転アトリビュートをQuaternionへ変換する。

        rotateはノードの回転順序、rotateAxis・jointOrient等はXYZで解釈する。

        Args:
            name (str): 回転アトリビュート名。

        Returns:
            om2.MQuaternion: 新しい回転値。
        """
        if name == "jointOrient" and not self._require_mnode().hasFn(om2.MFn.kJoint):
            value = self.getPlug(name).get(unit="rad")
        else:
            # 組み込みの角度アトリビュートは、getPlug(name).get()と同じ読取関数でPlugを作らずに読む。
            value = self._static_value(name)
        order = self._rotate_order() if name == "rotate" else om2.MEulerRotation.kXYZ
        return om2.MEulerRotation(*tuple(value), order).asQuaternion()

    def _rotate_order(self):
        """ノードの rotateOrder を om2 の回転順序の番号として取得する。

        Returns:
            int: 0(xyz)〜5(zyx)。om2.MEulerRotation.kXYZ〜kZYX と同じ番号。
        """
        return om2.MFnTransform(self.mnode()).rotation(om2.MSpace.kTransform).order

    def _require_pivots_writable(self, kinds, preserve):
        """変更するピボットと補償値の全成分が書き込めるか、更新前に検査する。

        Args:
            kinds (Iterable[str]): 検査するピボットの種類(rotate/scale)。
            preserve (bool): Trueは補償値(rotatePivotTranslate等)も検査する。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: いずれかの成分がロック・入力接続・書込み不能の場合。
        """
        for selected in kinds:
            names = [selected + "Pivot"]
            if preserve:
                names.append(selected + "PivotTranslate")
            for name in names:
                plug = self.getPlug(name).mplug()
                require_writable(plug)
                for index in range(plug.numChildren()):
                    require_writable(plug.child(index))

    def _channel_state(self):
        """現在の scale チャンネル値と rotate チャンネル値を内部単位で取得する。

        分解の解を現在のチャンネル値に近づけるための基準に使う。

        Returns:
            tuple: (scale の3成分の tuple, rotate の om2.MEulerRotation)。rotate は
            ラジアンで、順序はノードの rotateOrder。ノードが無効なら
            ((1.0, 1.0, 1.0), XYZ 順序の 0 回転)。
        """
        if not self.isValid():
            return (1.0, 1.0, 1.0), om2.MEulerRotation()
        # MFnTransform の scale() / rotation() は scale・rotate アトリビュートそのもの(joint でも
        # jointOrient を含まない)を返す。名前による findPlug より大幅に速い。
        fn = om2.MFnTransform(self.mnode())
        return tuple(fn.scale()), fn.rotation(om2.MSpace.kTransform)

    def _decompose_like_channels(self, matrix, scale_reference=None):
        """マトリクスを分解し、スケールの符号の組み合わせを基準のスケールへ揃える。

        om2.MTransformationMatrix の規約(行列式が負なら Z が負)で分解してから、
        :func:`_match_scale_signs` で符号を揃える。基準は scale_reference (指定時)、
        次に現在の scale チャンネル値の順に、行列式の符号と合う最初のもの。これにより
        scale が (-1, 1, 1) のようなミラーのノードでも、取得・設定の往復でチャンネル値の
        符号と回転が保たれ、``setScale`` では要求した符号がそのまま入る。

        Args:
            matrix (Matrix): 分解するマトリクス。
            scale_reference (Iterable[float] | None): 最優先で符号を合わせるスケール
                (``setScale`` で要求した値)。None なら現在の scale チャンネル値だけ。

        Returns:
            tuple: (translate(Translate), quaternion(om2.MQuaternion),
            scale(tuple), shear(tuple), reference(om2.MEulerRotation))。reference は
            現在の rotate チャンネル値で、Euler の解を選ぶ基準に使う。

        Raises:
            ValueError: マトリクスを分解できない場合(いずれかのスケール軸がゼロなど)。
        """
        # Matrix.decompose() と同じ検査・分解だが、使わない Euler などの生成を省く。
        transformation = matrix._checked_transformation()
        reference_scale, reference_rotate = self._channel_state()
        if scale_reference is None:
            references = (reference_scale,)
        else:
            references = (tuple(scale_reference), reference_scale)
        quaternion, scale, shear = _match_scale_signs(
            transformation.rotation(asQuaternion=True), transformation.scale(om2.MSpace.kTransform), transformation.shear(om2.MSpace.kTransform), references
        )
        return matrix.translate, quaternion, scale, shear, reference_rotate

    def _replace_components(self, matrix, rotate=None, scale=None, shear=None):
        """マトリクスの回転・スケール・シアーの一部を置き換えた新しいマトリクスを返す。

        置き換えない成分は :meth:`_decompose_like_channels` の分解値(スケールの符号を
        現在のチャンネルへ揃えた値)を使う。平行移動はマトリクスの値をそのまま保つ。

        Args:
            matrix (Matrix): 元のマトリクス。
            rotate (Iterable[float] | EulerRotate | Quaternion | None): 新しい回転。
                3成分は XYZ 順序のラジアン。None は現在の値。
            scale (Iterable[float] | None): 新しいスケール。None は現在の値。
            shear (Iterable[float] | None): 新しいシアー。None は現在の値。

        Returns:
            Matrix: 合成し直した新しいマトリクス。

        Raises:
            ValueError: 元のマトリクスを分解できない場合、または入力が不正な場合。
        """
        translate, quaternion, old_scale, old_shear, _ = self._decompose_like_channels(matrix)
        return Matrix(
            translate=translate,
            rotate=quaternion if rotate is None else rotate,
            scale=old_scale if scale is None else scale,
            shear=old_shear if shear is None else shear,
        )

    def _rotate_reference(self, reference):
        """:meth:`getRotate` が Euler の解を選ぶ基準を返す。

        transform ではマトリクスの回転と rotate チャンネルが同じ回転(rotateAxis が 0 の場合)
        なので、現在の rotate チャンネル値をそのまま基準にする。

        Args:
            reference (om2.MEulerRotation): 現在の rotate チャンネル値。

        Returns:
            om2.MEulerRotation: 基準の回転(順序はノードの rotateOrder)。
        """
        return reference

    def _channel_rotate(self, quaternion, reference):
        """ローカルマトリクスの回転を、rotate チャンネルへ書き込む値へ変換する。

        transformではrotateAxisを除いてrotateチャンネルの回転を求める。

        Args:
            quaternion (om2.MQuaternion): ローカルマトリクスの回転。
            reference (om2.MEulerRotation): 現在の rotate チャンネル値。

        Returns:
            om2.MEulerRotation: ノードの rotateOrder で表した、reference に最も近い解。
        """
        return _closest_euler(self._component_quaternion("rotateAxis").inverse() * quaternion, reference)

    def _quaternion_channel_values(self, value, ws, ra, r, jo):
        """回転の指定から書込み先とEuler値だけを求め、シーンは変更しない。

        Args:
            value (om2.MQuaternion | Iterable[float]): 入力回転。
            ws (bool): 検証済みのワールド空間指定。
            ra (bool): 入力へrotateAxisを含めるか。
            r (bool): rotateを更新するか。
            jo (bool): jointOrientを含めるか。

        Returns:
            tuple[str, om2.MEulerRotation]: 書込み先名とrad単位の計算値。
        """
        q = _quaternion_value(value)
        joint = self._require_mnode().hasFn(om2.MFn.kJoint)
        undo_ra = undo_r = None
        if ws:
            if not jo or (not r and (ra or not joint)):
                raise ValueError("対応していない回転成分の組み合わせです")
            jo = joint
            matrix = None
            if self.mpath().length() > 1:
                if not r:
                    undo_r = self._component_quaternion("rotate")
                    q = undo_r * q
                if not ra:
                    undo_ra = self._component_quaternion("rotateAxis")
                    q = undo_ra * q
                matrix = q.asMatrix() * self.mpath().exclusiveMatrixInverse()
            inv_scale = self._inverse_scale_values()
            if jo and inv_scale != (1.0, 1.0, 1.0):
                matrix = (q.asMatrix() if matrix is None else matrix) * Matrix(scale=inv_scale)
            if matrix is not None:
                q = om2.MQuaternion().setValue(om2.MMatrix(matrix).homogenize())
        else:
            jo = jo and joint
            if ra and not r and jo:
                raise ValueError("対応していない回転成分の組み合わせです")
        if undo_ra is not None:
            q = undo_ra.inverse() * q
        if undo_r is not None:
            q = undo_r.inverse() * q
        if r:
            if ra:
                q = self._component_quaternion("rotateAxis").inverse() * q
            if jo:
                q *= self._component_quaternion("jointOrient").inverse()
            return "rotate", q.asEulerRotation().reorder(self._rotate_order())
        return "jointOrient" if jo else "rotateAxis", q.asEulerRotation()

    def _apply_local_matrix(self, matrix, scale_reference=None, *, fast=False):
        """ローカルマトリクスの各成分をMayaアトリビュートへ適用する。

        マトリクスを1回だけ分解し、平行移動・回転・スケール・シアーのうち現在値と
        異なるものを順に書き込む(:meth:`_apply_channel_values`)。
        分解は om2.MTransformationMatrix の規約に、次の2点の選択を加えたもの。

        * スケールの符号の組み合わせは、行列式の符号が許す限り scale_reference
          (``setScale`` で要求した値)、次に現在の scale チャンネルに揃える
          (:meth:`_decompose_like_channels`)。
        * 回転はノードの rotateOrder で表し、等価な解のうち現在の rotate チャンネル値に
          最も近いものを選ぶ(``om2.MEulerRotation.closestSolution``)。

        同じマトリクスの再適用で、不要なスケール符号や等価なEuler解の変化を避ける。
        計算値は距離cm・角度radで、書込みは共通のPlug処理へ委譲する。
        ピボット・rotateAxis・jointOrient・SSCの補正を含める。

        Args:
            matrix (Matrix): ローカル空間のマトリクス。
            scale_reference (Iterable[float] | None): 最優先で符号を合わせるスケール。
                None なら現在の scale チャンネル値に合わせる。
            fast (bool): Trueなら各チャンネルをOpenMayaで更新する。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: マトリクスを分解できない場合。
            RuntimeError: Maya がアトリビュートの書き込みを拒否した場合。
        """
        self._apply_channel_values(self._matrix_channel_values(matrix, scale_reference), safe=False, fast=fast)

    def _apply_channel_values(self, values, safe=False, *, fast=False):
        """計算済みの内部単位値のうち、現在値と異なるものだけを辞書の保持順に設定する。

        書込み値が現在のチャンネル値(内部単位)と完全に一致するチャンネルは書き込まない。
        書き込まないチャンネルはロック・接続されていても例外にせず、通知・Undoの記録も残らない。

        Args:
            values (dict[str, Iterable[float]]): チャンネル名と設定値。
            safe (bool): 書けない成分を残す。通常時は失敗を伝播する。
            fast (bool): 子のPlugへ渡す更新モード。

        Returns:
            None: 値を返さない。
        """
        for name, value in values.items():
            value = tuple(value)
            if self._channel_equals(name, value):
                continue
            self._set_channel_value(name, value, safe=safe, fast=fast)

    def _channel_equals(self, name, value):
        """内部単位の書込み値が、チャンネルの現在値と完全に一致するかを返す。

        Args:
            name (str): 組み込みの数値アトリビュートのロング名。
            value (tuple | object): 書込み予定の値。コンパウンドアトリビュートは成分のtuple。

        Returns:
            bool: 成分数と各成分が完全に一致すればTrue。読取れない場合はFalse(書込みへ委ねる)。
        """
        try:
            current = self._static_value(name)
        except Exception:
            return False
        if isinstance(value, tuple):
            return isinstance(current, tuple) and len(current) == len(value) and all(float(a) == float(b) for a, b in zip(current, value))
        return current == value

    def _set_channel_value(self, name, value, safe=False, *, fast=False):
        """内部単位のチャンネル値を、基底Plug.setへ渡す。

        Double3の回転変換を再実行せず、入力された順序の数値を使う。
        通常更新はMayaに従い、fastは接続済み入力への直接書込みを拒否する。
        参照取得・tuple化の失敗はsafeで抑制しない。

        Args:
            name (str): 設定するチャンネル名。
            value (Iterable[float]): 数値列。距離cm、角度rad。
            safe (bool): Plug.setに対応する書込み失敗を数えるか。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Plug | int: Plug.setの戻り値。通常はPlug、safe=Trueは失敗数。
        """
        # Double3Plug._set_value の回転変換・単位処理を通さず、基底 Plug の書込みを骨格ごと使う。
        plug = self.getPlug(name)
        try:
            return Plug._set_template(plug, tuple(value), safe, fast=fast, unit="rad", _writer=Plug._set_value)
        except RuntimeError as error:
            message = None if safe else _unwritable_channel_message(plug)
            if message is None:
                raise
            raise RuntimeError(message) from error

    def _matrix_channel_values(self, matrix, scale_reference=None):
        """マトリクスからtranslate/rotate/scale/shearの設定値を計算する。シーンは更新しない。

        Args:
            matrix: 変換または数値計算に使うマトリクス。
            scale_reference: スケール補正の基準となるノードまたは値。
        """
        source = Matrix(matrix)
        inv_scale = self._inverse_scale_values()
        corrected = source * Matrix(scale=inv_scale)
        # Matrix 同士の積は常に Matrix。
        assert isinstance(corrected, Matrix)
        corrected.translate = source.translate
        _, q, scale, shear, reference = self._decompose_like_channels(corrected, scale_reference)
        if type(self)._channel_rotate is Transform._channel_rotate:
            # Transformの_channel_rotateと同じ式で、rotateAxisの読取を1回にする(値は同じ読取関数)。
            rotate_axis = self._component_quaternion("rotateAxis")
            rotation = _closest_euler(rotate_axis.inverse() * q, reference)
        else:
            # Joint等の上書きは独自の読取関数を使うため、従来どおり別に読む。
            rotation = self._channel_rotate(q, reference)
            rotate_axis = self._component_quaternion("rotateAxis")
        sp = self._static_value("scalePivot")
        rp = self._static_value("rotatePivot")
        spt = self._static_value("scalePivotTranslate")
        rpt = self._static_value("rotatePivotTranslate")
        orient = rotate_axis * rotation.asQuaternion()
        if self._require_mnode().hasFn(om2.MFn.kJoint):
            orient *= self._component_quaternion("jointOrient")
        base = (
            Matrix(translate=tuple(-v for v in sp))
            * Matrix(scale=scale, shear=shear)
            * Matrix(translate=sp)
            * Matrix(translate=spt)
            * Matrix(translate=tuple(-v for v in rp))
            * Matrix(rotate=orient)
            * Matrix(translate=rp)
            * Matrix(translate=rpt)
            * Matrix(scale=tuple(1.0 / v for v in inv_scale))
        )
        assert isinstance(base, Matrix)
        translate = source.translate - base.translate
        return {"translate": Translate(*translate), "rotate": EulerRotate._wrap(rotation), "scale": Scale(*scale), "shear": Shear(*shear)}
