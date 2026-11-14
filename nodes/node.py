"""Mayaの依存ノードとDAGノードを扱う基底クラス。"""

import inspect
import re
from operator import methodcaller
from typing import Optional

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import Object, _missing_member_message
from ..core.registry import _inherited_node_types, _node_type_exists, _real_node_type, _unknown_node_type_message
from ..decorator import _edit_context, _merge_flags, _pick_alias, _require_bool, _validated_flags, undoChunk, undoTransaction
from ..util import _UNSET, _angle_unit, _ArgumentError, _color_value, _time_unit

#: om2の数値データ型からaddAttrの型名への対応(moveAttrOrderでの再作成に使う)。
_MOVABLE_NUMERIC_TYPES = {
    om2.MFnNumericData.kBoolean: "bool",
    om2.MFnNumericData.kByte: "byte",
    om2.MFnNumericData.kShort: "short",
    om2.MFnNumericData.kInt: "long",
    om2.MFnNumericData.kLong: "long",
    om2.MFnNumericData.kFloat: "float",
    om2.MFnNumericData.kDouble: "double",
}  #: moveAttrOrder() が再作成できる数値アトリビュート型と cmds.addAttr(attributeType=) の対応。

#: ``cmds.listAttr(scalar=True)`` が除く、複数成分の数値型(double3 等。コンパウンドアトリビュートとして定義される)。
_MULTI_COMPONENT_NUMERIC_TYPES = frozenset(getattr(om2.MFnNumericData, name) for name in dir(om2.MFnNumericData) if name[:2] in ("k2", "k3", "k4"))

#: Node.getPlugs() が ``cmds.listAttr`` を使わず OpenMaya で列挙するフラグ(値は True のときだけ)。
_OM2_LIST_ATTR_FLAGS = frozenset(("keyable", "scalar"))


#: ラッパー型の選択で型名だけを読むために使い回す関数セット。setObject() で対象を差し替えるため、
#: ノードごとに MFnDependencyNode を作るより速い。値や名前を保持せず、呼出しのたびに対象を設定し直す。
_TYPE_NAME_FN = om2.MFnDependencyNode()


def _subclass_overrides(base, name):
    """baseの派生クラス(孫以降を含む)のいずれかがメソッドを上書きしているか調べる。

    呼出しのたびに現在の派生クラスを調べるため、後から定義・登録されたクラスも反映する。

    Args:
        base (type): 基底クラス。
        name (str): メソッド名。

    Returns:
        bool: 1つでも上書きしていればTrue。
    """
    original = getattr(base, name)
    stack = list(base.__subclasses__())
    while stack:
        cls = stack.pop()
        if getattr(cls, name, original) is not original:
            return True
        stack.extend(cls.__subclasses__())
    return False


def _node_type_name(mobject):
    """検証済みの依存ノードの MObject から nodeType 名を取得する。

    ``om2.MFnDependencyNode(mobject).typeName`` と同じ値を、使い回しの関数セットで読む。

    Args:
        mobject (om2.MObject): 有効な依存ノードの MObject。

    Returns:
        str: Maya の nodeType 名。
    """
    fn = _TYPE_NAME_FN
    fn.setObject(mobject)
    return fn.typeName


def _resolve_node(node):
    """ノードを表す入力を MObject と MDagPath へ解決する。

    Node.__new__ (返すクラスの選択)を通じて、Nodeの入力の解決が使う下位の処理。
    Node(...) の生成では __new__ で1回だけ呼び、結果を __init__ へ引き継ぐ。Plug・MPlug は
    所有ノード、コンポーネント(単体・複数形)は所有シェイプへ解決する。

    Args:
        node (str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
            対象のノードの名前、mlibのオブジェクト、またはMaya API 2.0のオブジェクト。
            ``"node.attribute"`` や ``"pCube1.vtx[0]"`` のような文字列も所有ノードへ解決する
            (インスタンス化されたノードは、名前が指すインスタンスのパスを保持する)。

    Returns:
        tuple[om2.MObject, om2.MDagPath | None]: 解決した MObject と、DAG ノードで
            あれば対応する MDagPath(非DAGノードでは None)。

    Raises:
        TypeError: 対応しない入力型、または依存ノード以外(アトリビュートなど)を指す MObject の場合。
        ValueError: 所有ノードは有効で、アトリビュートが ``deleteAttr`` で削除済みの Plug・MPlug の場合
            (:class:`mlib.plugs.plug.DeletedAttributeError`。``RuntimeError`` の派生でもある)。
        RuntimeError: 名前を解決できない(存在しない、または複数の対象に一致する)場合、
            または空・無効な(削除済みの)mlibのオブジェクトやom2のオブジェクトを指定した場合。
    """
    if isinstance(node, str):
        selection = om2.MSelectionList()
        try:
            selection.add(node)
        except RuntimeError as original_error:
            # MSelectionList は複数のノードに一致する名前も「存在しない」として拒否するため、
            # 利用者が原因を判別できるよう maya.cmds で一致数を確かめてからメッセージを選ぶ。
            matches = (cmds.ls(node, long=True) or []) if node else []
            if len(matches) > 1:
                raise RuntimeError(_not_unique_message(node, matches)) from original_error
            raise RuntimeError(f"ノードが見つかりません: {node}") from original_error
        if selection.length() != 1:
            # "dup.tx" のようなプラグ名・コンポーネント名は、同名ノードがあると複数の要素になる。
            matches = cmds.ls(node, long=True) or [node]
            raise RuntimeError(_not_unique_message(node, matches)) from None
        return Node._selection_owner(selection, 0, node)
    if isinstance(node, om2.MDagPath):
        if not node.isValid() or not om2.MObjectHandle(node.node()).isValid():
            raise RuntimeError("無効な(削除された)MDagPathからはノードを解決できません")
        dag_path = om2.MDagPath(node)
        return dag_path.node(), dag_path
    if isinstance(node, om2.MObject):
        if node.isNull():
            raise RuntimeError("nullのMObjectからはノードを解決できません")
        if not om2.MObjectHandle(node).isValid():
            raise RuntimeError("削除されたノードのMObjectからはノードを解決できません")
        if not node.hasFn(om2.MFn.kDependencyNode):
            raise TypeError("MObjectはディペンデンシーノードで指定してください(アトリビュート・コンポーネント・データは指定できません)")
        mobject = om2.MObject(node)
        dag_path = om2.MFnDagNode(mobject).getPath() if mobject.hasFn(om2.MFn.kDagNode) else None
        return mobject, dag_path
    # nodesとの循環importを避け、Plugは呼出し時に取得する(名前・API参照の解決では使わないため、その後で取得する)。
    from ..plugs.plug import DeletedAttributeError, Plug

    if isinstance(node, om2.MPlug):
        if node.isNull:
            raise RuntimeError("nullのMPlugからはノードを解決できません")
        owner = node.node()
        # 所有ノードが有効でも、deleteAttr で削除されたアトリビュートの MPlug は削除済みの対象として扱う
        # (mlib のコマンドと同じ。所有ノードが削除済みなら下の MObject の解決で RuntimeError)。
        if om2.MObjectHandle(owner).isValid() and not Plug._mplug_attribute_exists(node, owner):
            raise DeletedAttributeError("削除されたアトリビュートのMPlugからはノードを解決できません")
        return _resolve_node(owner)
    if isinstance(node, Node):
        if not node.isValid():
            raise RuntimeError("無効な(削除された)ノードは使えません")
        dag_path = node._current_dag_path()
        return om2.MObject(node._mobject), om2.MDagPath(dag_path) if dag_path is not None else None
    # Componentもnodesを参照するため、必要な分岐に達してからimportする。
    from ..components.component import Component, Components

    if isinstance(node, Plug):
        error = Plug._deleted_attribute_error(node)
        if error is not None:
            raise error
        return _resolve_node(node.getNode())
    if isinstance(node, (Component, Components)):
        return _resolve_node(node.shape)
    raise TypeError("nodeは名前・Node・Plug・Component・MObject・MDagPath・MPlugのどれかで指定してください")


def _not_unique_message(name, matches):
    """複数の対象に一致する名前の例外メッセージを作る。

    一致した対象を最大3件まで完全パスで示し、完全パスか ``mlib.ls`` での指定を案内する。

    Args:
        name (str): 解決しようとした名前。
        matches (Sequence[str]): 一致した対象の名前。

    Returns:
        str: 例外メッセージ。
    """
    shown = ", ".join(repr(match) for match in list(matches)[:3])
    more = f"、ほか{len(matches) - 3}個" if len(matches) > 3 else ""
    return f"名前が一意ではありません: {name!r}は{len(matches)}個のオブジェクトに一致します({shown}{more})。{list(matches)[0]!r}のようなフルパスを使うか、mlib.ls({name!r})で全部を取得してください"


def _require_node_name(name):
    """作成・改名に使うノード名の、Mayaが黙って置き換える文字を拒否する。

    Args:
        name (object): ノード名。文字列以外の検査はMayaに任せる。

    Returns:
        None: 値を返さない。

    Raises:
        ValueError: DAGパスの区切り ``|`` を含む場合。
    """
    if isinstance(name, str) and "|" in name:
        raise ValueError(f"ノード名に'|'は使えません(Mayaが黙って置き換えます): {name!r}。getNodeName()の結果のように、ノード名だけを渡してください")


def _is_deleted_api_object(value):
    """om2 オブジェクトが削除済みのノードを指すか判定する(空のオブジェクトは False)。

    Args:
        value (object): 判定する値。om2 の MObject・MDagPath・MPlug 以外は False。

    Returns:
        bool: 削除済みのノードを指す MObject・MDagPath・MPlug の場合は True。
            無効な MDagPath は、空のパスも含めて True(``Node(...)`` も区別しない)。
    """
    if isinstance(value, om2.MPlug):
        if value.isNull:
            return False
        value = value.node()
    if isinstance(value, om2.MDagPath):
        return not value.isValid() or not om2.MObjectHandle(value.node()).isValid()
    if isinstance(value, om2.MObject):
        return not value.isNull() and not om2.MObjectHandle(value).isValid()
    return False


def _resolve_input_or_none(other):
    """判定メソッド(``isParentOf`` など)の対象をノードへ解決する。

    ``mlib.Node._resolve_input`` と同じ規則で解決し、削除済みの対象(削除済みの Node、
    所有ノードが削除済みの Plug・Component、アトリビュートが ``deleteAttr`` で削除済みの Plug・MPlug、
    削除済みのノードを指す om2 オブジェクト)は例外にせず None を返す(判定は False)。

    Args:
        other (Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
            判定対象。

    Returns:
        Node | None: 解決した有効なノード。削除済みの対象は None。

    Raises:
        TypeError: 対応しない型の場合。
        RuntimeError: 名前を解決できない(存在しない、または複数のノードに一致する)場合、
            または空の MObject・MPlug の場合。
    """
    # 循環参照の回避: plugs は nodes を参照するため、使う時点で読み込む。
    from ..plugs.plug import DeletedAttributeError

    try:
        node = Node._resolve_input(other)
    except DeletedAttributeError:
        return None
    except RuntimeError:
        if _is_deleted_api_object(other):
            return None
        raise
    return node if node.isValid() else None


def _dump_movable_attr(plug):
    """並び替え対応の単純な動的アトリビュートから再作成に必要な情報を集める。

    数値(bool/byte/short/long/float/double)、enum、文字列型のコンパウンドアトリビュートでもマルチアトリビュートでもない
    トップレベル動的アトリビュートのみ対応する。

    Args:
        plug (Plug): ダンプ対象の動的アトリビュートプラグ。

    Returns:
        dict: addAttr() での再作成と値・状態の復元に必要な情報。

    Raises:
        TypeError: コンパウンドアトリビュート・マルチアトリビュート、または対応しないアトリビュート型の場合。
    """
    if plug.isMulti() or plug.isCompound():
        raise TypeError(f"コンパウンドアトリビュートとマルチアトリビュートは並べ替えられません: {plug.getFullName()}")
    attr = plug.mplug().attribute()
    definition = om2.MFnAttribute(attr)
    if not definition.connectable:
        raise TypeError(f"接続できないアトリビュートは、Mayaのコマンドでは作り直せません: {plug.getFullName()}")
    info = {
        "longName": plug.getLongName(),
        "shortName": plug.getShortName(),
        "niceName": plug.getNiceName(),
        "hidden": definition.hidden,  # addAttr(hidden=)の定義フラグ。Channel Boxの表示はkeyable/channelBox。
        "keyable": plug.isKeyable(),
        "channelBox": plug.mplug().isChannelBox,
        "locked": plug.isLocked(),
        "value": plug.get(),
        "flags": {
            flag: getattr(definition, property_name)
            for flag, property_name in (
                ("readable", "readable"),
                ("writable", "writable"),
                ("storable", "storable"),
                ("cachedInternally", "cached"),
                ("usedAsColor", "usedAsColor"),
                ("usedAsFilename", "usedAsFilename"),
                ("disconnectBehaviour", "disconnectBehavior"),
            )
        },
    }
    source = plug.getSource()
    info["source"] = _movable_connection_ref(source) if source is not None else None
    info["destinations"] = [_movable_connection_ref(target) for target in plug.getDestinations()]
    if attr.hasFn(om2.MFn.kNumericAttribute):
        numeric_type = om2.MFnNumericAttribute(attr).numericType()
        type_name = _MOVABLE_NUMERIC_TYPES.get(numeric_type)
        if type_name is None:
            raise TypeError(f"並べ替えに対応していない数値アトリビュートの型です: {plug.getFullName()}")
        info["attributeType"] = type_name
        if plug.hasMin():
            info["min"] = plug.getMin()
        if plug.hasMax():
            info["max"] = plug.getMax()
        if plug.hasSoftMin():
            info["softMin"] = plug.getSoftMin()
        if plug.hasSoftMax():
            info["softMax"] = plug.getSoftMax()
        info["defaultValue"] = plug._raw_default()
    elif attr.hasFn(om2.MFn.kEnumAttribute):
        info["attributeType"] = "enum"
        info["enumName"] = _enum_definition(plug)
        info["defaultValue"] = plug._raw_default()
    elif attr.hasFn(om2.MFn.kTypedAttribute) and om2.MFnTypedAttribute(attr).attrType() == om2.MFnData.kString:
        info["dataType"] = "string"
    else:
        raise TypeError(f"並べ替えに対応していないアトリビュートの型です: {plug.getFullName()}")
    return info


def _require_same_attr_definition(plug, flags):
    """addAttr(safe=True)で、既存のアトリビュートが要求した型と一致するか検証する。

    Args:
        plug (Plug): 既存のアトリビュート。
        flags (dict): 型を解決済みのaddAttrのフラグ(attributeType/dataType・multi)。

    Raises:
        TypeError: 型、またはマルチアトリビュートかどうかが一致しない場合。
    """
    existing = plug.getType()
    data_type = flags.get("dataType")
    if isinstance(data_type, (list, tuple)):
        matched = existing is None or existing in data_type
        requested = "/".join(data_type)
    else:
        requested = flags.get("attributeType") or data_type
        matched = existing == {"compound": "TdataCompound"}.get(requested, requested)
    if not matched:
        raise TypeError(f"アトリビュートは別の型ですでに存在します: {plug.getFullName()}は{existing!r}で、指定は{requested!r}です")
    if bool(flags.get("multi")) != plug.isMulti():
        raise TypeError(f"アトリビュートは別のマルチの設定ですでに存在します: {plug.getFullName()}")


def _enum_field_value(enum_name, field):
    """``enumName`` の定義(``"a:b:c"``・``"a=2:b=5"``)からフィールド名の値を求める。

    値を省いたフィールドは直前の値+1(先頭は0)で、Mayaの ``addAttr(enumName=...)`` と同じ。

    Args:
        enum_name (str | None): ``addAttr`` へ渡すenumNameの文字列。
        field (str): 値を求めるフィールド名(大文字・小文字を区別する完全一致)。

    Returns:
        int: フィールドの値。

    Raises:
        ValueError: enumNameが無い、またはfieldに一致するフィールドが無い場合。
    """
    if not isinstance(enum_name, str) or not enum_name:
        raise ValueError(f"defaultValue {field!r}でenumのフィールドを決めるには、enumNameが必要です")
    names = []
    value = -1
    for item in enum_name.split(":"):
        name, separator, number = item.partition("=")
        value = int(number) if separator else value + 1
        if name == field:
            return value
        names.append(name)
    raise ValueError(f"{field!r}という名前のenumのフィールドはありません(使える名前: {', '.join(repr(name) for name in names)})")


def _enum_definition(plug):
    """enum の全フィールドを ``cmds.attributeQuery(listEnum=True)`` と同じ書式の文字列にする。

    値の昇順に並べ、直前の値 + 1(先頭は0)と異なる値だけ ``名前=値`` と書く(例: ``a=1:b=5``)。

    Args:
        plug (Plug): enum アトリビュートのプラグ。

    Returns:
        str: ``addAttr(enumName=...)`` へそのまま渡せるフィールド定義。
    """
    parts = []
    expected = 0
    for name, value in plug.getEnumNames():
        parts.append(name if value == expected else f"{name}={value}")
        expected = value + 1
    return ":".join(parts)


def _scalar_attribute(attribute):
    """``cmds.listAttr(scalar=True)`` が列挙する、単一成分の数値・単位・enum 型か判定する。

    マルチアトリビュートであっても、要素が単一成分なら対象に含める(listAttr と同じ)。

    Args:
        attribute (om2.MObject): アトリビュート定義。

    Returns:
        bool: scalar として列挙する場合は True。
    """
    if attribute.hasFn(om2.MFn.kCompoundAttribute):
        return False
    if attribute.hasFn(om2.MFn.kNumericAttribute):
        return om2.MFnNumericAttribute(attribute).numericType() not in _MULTI_COMPONENT_NUMERIC_TYPES
    return attribute.hasFn(om2.MFn.kUnitAttribute) or attribute.hasFn(om2.MFn.kEnumAttribute)


def _writable_plug(plug):
    """Plug._require_writable() が通るか(ロック・入力接続・書込み禁止が無いか)を返す。

    Args:
        plug (Plug): 検査するプラグ。

    Returns:
        bool: 書き込める場合は True。シーンは変更しない。
    """
    try:
        plug._require_writable()
    except RuntimeError:
        return False
    return True


def _movable_connection_ref(plug):
    """削除する定義を保持せず、所有ノードと再解決用のパスを保存する。

    Args:
        plug (Plug): 変更前に存在する接続端点。

    Returns:
        tuple[Node, str]: 所有ノードとaliasを使わないアトリビュートパス。
    """
    return plug.getNode(), plug.mplug().partialName(includeNonMandatoryIndices=True, includeInstancedIndices=True, useFullAttributePath=True, useLongNames=True)


def _create_movable_attr(node, info):
    """退避した定義と値を再作成する。接続とロックは全定義の作成後に戻す。

    Args:
        node (Node): アトリビュートを追加する対象ノード。
        info (dict): _dump_movable_attr() が返した情報。

    Returns:
        Plug: 再作成したアトリビュートプラグ。
    """
    kwargs = dict(info["flags"], shortName=info["shortName"], hidden=info["hidden"])
    if info["niceName"]:
        kwargs["niceName"] = info["niceName"]
    if "min" in info:
        kwargs["minValue"] = info["min"]
    if "max" in info:
        kwargs["maxValue"] = info["max"]
    if "softMin" in info:
        kwargs["softMinValue"] = info["softMin"]
    if "softMax" in info:
        kwargs["softMaxValue"] = info["softMax"]
    if "enumName" in info:
        kwargs["enumName"] = info["enumName"]
    plug = node.addAttr(
        info["longName"], attributeType=info.get("attributeType"), dataType=info.get("dataType"), defaultValue=info.get("defaultValue"), **kwargs
    )
    if info["source"] is None:
        plug.set(info["value"])
    plug.setFlags(keyable=info["keyable"], channelBox=info["channelBox"])
    return plug


def _plug_key(mplug):
    """循環の探索で同じアトリビュートを同一視するキーを返す。

    Args:
        mplug (om2.MPlug): アトリビュート。

    Returns:
        tuple[int, str]: 所有ノードのハッシュと、論理番号を含むロング名のパス。
    """
    return (om2.MObjectHandle(mplug.node()).hashCode(), mplug.partialName(includeNonMandatoryIndices=True, useLongNames=True, useFullAttributePath=True))


def _is_writable(mplug):
    """アトリビュートへ今書き込めるか(ロック・animCurve以外の入力接続が無いか)を返す。

    Args:
        mplug (om2.MPlug): 調べるアトリビュート。

    Returns:
        bool: 自身・親(コンパウンドアトリビュート)・マルチアトリビュートの全体のどれもロックされておらず、
            自身と親の入力がanimCurveだけ(または無い)ならTrue。
    """
    current = mplug
    while True:
        if current.isLocked:
            return False
        source = current.source()
        if not source.isNull and not source.node().hasFn(om2.MFn.kAnimCurve):
            return False
        if current.isChild:
            current = current.parent()
        elif current.isElement:
            current = current.array()
            if current.isLocked:
                return False
            return True
        else:
            return True


def _attribute_names(attributes):
    """キー操作のアトリビュート名を、cmdsへ渡す名前のリストへ変換する。

    Args:
        attributes (str | Iterable[str] | None): アトリビュート名。

    Returns:
        list[str] | None: 名前のリスト。Noneは指定なし(Mayaの既定)。

    Raises:
        TypeError: 文字列・文字列の列・None以外の場合。
        ValueError: 空の列、または空文字列を含む場合。
    """
    if attributes is None:
        return None
    names = [attributes] if isinstance(attributes, str) else attributes
    try:
        names = list(names)
    except TypeError:
        raise TypeError("attributesは名前か名前の並びで指定してください") from None
    if any(not isinstance(name, str) for name in names):
        raise TypeError("attributesの要素は文字列で指定してください")
    if not names or not all(names):
        raise ValueError("attributesに空の名前は指定できません")
    return names


class Node(Object):
    """Mayaのノードを扱うクラス。

    このクラスのオブジェクトは、Mayaのノードを1つ指す。DAGノードでは、どのインスタンスかを表す
    DAGパスも1つ持つ。

    - 返すオブジェクトのクラスは、ノードの型(nodeType)で決まる。登録されたクラスがあればそれを、
      無ければ最も近い登録済みの祖先の型のクラスを、それも無ければNodeを使う。
    - Nodeを渡しても、新しいオブジェクトを返す。Mayaのノードは複製しない。
    - 名前・MDagPath・既存のオブジェクトを渡すと、そのDAGパスを持つ。MObject・MPlugを渡すと、最初のパスを使う。
    - 持っているパスのインスタンスが消えても、別のパスへは切り替えない。パスを使う操作はRuntimeErrorになる。
    - ``str(node)`` は、名前の変更や親の変更に追従した最短の一意な名前を返す。削除済みなら空文字列。

    取得専用のクラスで、ノードの作成は :func:`mlib.createNode` で行う(``Node.create`` や
    ``Node(name, create=True)`` のような作り方は無い)。``isinstance`` の階層は、mlibで書いたクラスの
    継承のとおりになる。Mayaの抽象的な祖先の型(``weightGeometryFilter``・``containerBase``・``entity`` など)の
    クラスは含まない。

    Mayaの型の継承で判定するときは、:meth:`isType` か、:meth:`getType` の ``inherited=True`` を使う。

    Args:
        node (str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
            名前か、ノードを指すもの。Plug・MPlugはそれを持つノードを、Component・Componentsは
            それを持つシェイプを指す。

    Raises:
        TypeError: 入力の型が不正な場合、または指定したクラスと対象のノードの型が合わない場合。
        ValueError: ノードは有効だが、アトリビュートだけが削除済みのPlugを渡した場合。
            MPlugも同じ。DeletedAttributeError(RuntimeErrorの派生でもある)になる。
        RuntimeError: 対象が空・削除済み・存在しない・一意でない場合。
    """

    _registry = None  #: mlib.__init__ が構築後に注入する NodeRegistry。
    _mobject: "om2.MObject"  #: 参照するノードの MObject(__init__・_resolve が設定する)。
    _dag_path: "Optional[om2.MDagPath]"  #: DAG ノードの保持パス。非DAGはNone。
    _handle: "om2.MObjectHandle"  #: 有効性の判定に使う MObject のハンドル。
    _fn_cache = None  #: _dependency_fn() が初回に作る MFnDependencyNode(ノードごとに1つ)。

    def __new__(cls, node, *args, **kwargs):
        """ノードの型に合ったクラスのオブジェクトを作る。

        入力は一度だけ解決し、nodeTypeに登録されたクラスを選ぶ。登録が無い型では、登録表の決まりで
        選んだクラスを使う(それも無ければNode)。具体的なクラスを指定して呼んだ場合、そのクラスの
        派生でない型は拒否する。黙って別の型へ差し替えることはしない。ノードは作らない。

        Args:
            node (str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
                対象のノードの名前、mlibのオブジェクト、またはMaya API 2.0のオブジェクト。
                Plug・MPlugはそれを持つノードを、Component・Componentsはそれを持つシェイプを指す。
            *args (object): 選んだクラスの ``__init__`` へ渡す位置引数。
            **kwargs (object): 選んだクラスの ``__init__`` へ渡すキーワード引数。
                ``create`` は受け付けない(``__init__`` がTypeErrorにする)。

        Returns:
            Node: 解決したMayaのノードを指す、型に合ったクラスの新しいオブジェクト。

        Raises:
            TypeError: 入力の型が対応していない場合、指定したクラスと対象の型が合わない場合、
                または選んだクラスの ``__init__`` が受け付けない引数(廃止した ``create`` など)を渡した場合。
            ValueError: アトリビュートが ``deleteAttr`` で削除済みのPlug・MPlugを渡した場合
                (``DeletedAttributeError``。RuntimeErrorの派生でもある)。
            RuntimeError: ノードを解決できない場合。
        """
        if args or kwargs:
            # 廃止した create= 等、__init__ が受けない引数は入力を解決する前に TypeError にする。
            inspect.signature(cls.__init__).bind(None, node, *args, **kwargs)
        registry = cls._registry
        if registry is None:
            return super().__new__(cls)
        # 入力の解決(名前の検索など)は1回だけ行い、結果を __init__ へ引き継ぐ。
        resolved = _resolve_node(node)
        resolved_class = registry.wrapper_class(_node_type_name(resolved[0]))
        if cls is not Node and not issubclass(resolved_class, cls):
            message = f"{cls.__name__}には対応するノードが必要です: {resolved_class.__name__}"
            if getattr(cls, "_generated", False):
                # 登録表の作り直し(reload・register)で無効になった生成クラスを保持したまま使った場合の案内。
                message += f"(mlib.reload()や登録表の変更をまたいで保持した生成クラスは古くなっています。mlib.nodes.{cls.__name__}を取得し直してください)"
            raise TypeError(message)
        instance = super().__new__(resolved_class)
        instance._pending_resolution = resolved
        return instance

    def __init__(self, node):
        """入力を解決し、MObjectと、DAGノードならMDagPathを持つ。

        既存のNodeを渡した場合は、同じMObjectとDAGパス(インスタンス)を指す新しいオブジェクトになる。

        Args:
            node (str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
                対象のノードの名前、mlibのオブジェクト、またはMaya API 2.0のオブジェクト。
                Plug・MPlugはそれを持つノードを、Component・Componentsはそれを持つシェイプを指す。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 入力の型が対応していない場合。
            ValueError: アトリビュートが ``deleteAttr`` で削除済みのPlug・MPlugを渡した場合
                (``DeletedAttributeError``。RuntimeErrorの派生でもある)。
            RuntimeError: ノード名を解決できない場合。
        """
        # __new__ が解決済みの結果を引き継いだ場合は、同じ入力を再び解決しない。
        resolved = vars(self).pop("_pending_resolution", None)
        if resolved is None:
            self._resolve(node)
            return
        # 有効性の判定は名前の取得のたびに行うため、ハンドルは一度だけ作って再利用する。
        # __setattr__ を通さず、解決済みの値を直接保持する(大量の参照を作る経路の負荷を抑える)。
        handle = om2.MObjectHandle(resolved[0])
        vars(self).update(_mobject=resolved[0], _dag_path=resolved[1], _handle=handle, _identity_hash=handle.hashCode())

    def __eq__(self, other):
        """同じノードを指しているか比べる。

        どちらも生存しているときだけ等しくなる。DAGノードでは、インスタンスのパスも区別する。

        Args:
            other: 比較・演算の相手。
        """
        if not isinstance(other, Node):
            return NotImplemented
        if not self.isAlive() or not other.isAlive():
            return False
        if self._dag_path is not None and other._dag_path is not None:
            return self._dag_path == other._dag_path
        return self._mobject == other._mobject

    def __hash__(self):
        """作ったときのMayaのハンドルのハッシュを返す。名前を変えても、削除しても変わらない。"""
        return self._identity_hash

    def __repr__(self):
        """デバッグ用に、クラス名とノード名を含む文字列を返す。

        Returns:
            str: 有効なら型名とノード名、無効なら型名とinvalidを含む文字列。
        """
        if self.isValid():
            return f"{type(self).__name__}({self.getName()!r})"
        return f"<{type(self).__name__} invalid>"

    def __str__(self):
        """Mayaのノードの最短の一意な名前を返す。

        maya.cmdsは文字列以外の引数に ``str()`` を使うので、Nodeを ``cmds.select(node)`` のように
        そのまま渡せる。呼び出すたびに求め直すので、名前の変更や親子付けの変更に追従する。

        :meth:`getName` と違い、削除済みのノードやUndoで無効になったノードでも、例外にせず空文字列を返す
        (maya.cmdsへ渡したときに、Maya側のエラーになるようにするため)。

        Returns:
            str: 最短の一意な名前。無効なノードでは空文字列。
        """
        handle = self._handle
        if handle is None or not handle.isValid():
            return ""
        return self.getName()

    def __getattr__(self, name):
        """Pythonの属性に無い名前を、MayaのアトリビュートのPlugとして取得する。

        ``node.translateX`` のように書くと、そのアトリビュートのPlugが返る。型スタブでも戻り値はPlugになる。
        そのため、``mlib.getNode()`` が返す基底のNode型のまま派生クラス(Jointなど)のメソッドを呼ぶと、
        静的解析ではPlugとして扱われて警告になる。派生クラスのメソッドを補完で使うときは、
        ``Joint("joint1")`` のように取得するか、``isinstance`` で型を絞る。

        Args:
            name (str): 取得しようとしたPythonの属性の名前。

        Returns:
            Plug: 見つかったMayaのアトリビュートのPlug。

        Raises:
            AttributeError: ``_`` で始まる名前、または存在しないMayaのアトリビュートを指定した場合。
                文言は ``'Joint'にメソッドやMayaのアトリビュート'orientJoint'はありません`` の形になる。
                近い名前のメソッドと、maya.cmdsやほかのライブラリの名前に対応するmlibの書き方も案内する。
                :meth:`getPlug` がRuntimeErrorにする名前もAttributeErrorにする。たとえば ``input3Dx`` のような、
                マルチアトリビュートであるコンパウンドアトリビュートの子を、要素の番号なしで指定した場合。
                ``hasattr`` や ``getattr(node, name, default)`` を使えるようにするためで、
                元のRuntimeErrorは ``__cause__`` に入る。
            RuntimeError: ノードが無効な場合。
        """
        if name.startswith("_"):
            raise AttributeError(name)
        self._require_valid("アトリビュートの取得")
        try:
            return self.getPlug(name)
        except (AttributeError, RuntimeError) as error:
            raise AttributeError(_missing_member_message(self, name, "メソッドやMayaのアトリビュート")) from error

    def __setattr__(self, name, value):
        """Mayaのアトリビュートの名前への代入を、そのPlugの :meth:`~mlib.plugs.plug.Plug.set` にする。

        ``node.tx = 5`` は ``node.getPlug("tx").set(5)`` と同じ。Undoに記録し、角度は度で受け取る
        (``node.t = (1, 2, 3)`` も同じ)。

        ``_`` で始まる名前と、クラスで定義された名前(メソッド・プロパティ・クラス属性)は、
        ふつうのPythonの代入として扱う。それ以外の名前で、Pythonの属性をオブジェクトへ追加することはできない。

        Args:
            name (str): 代入する名前。
            value (object): 値。

        Returns:
            None: 値を返さない。

        Raises:
            AttributeError: その名前のMayaのアトリビュートが無い場合。
            RuntimeError: ノードが無効な場合、またはMayaが書込みを拒否した場合。
            TypeError: 値の型がアトリビュートに合わない場合(Plug.setと同じ)。
            ValueError: 値の成分の数や範囲が合わない場合(Plug.setと同じ)。
        """
        if name[:1] == "_" or hasattr(type(self), name):
            object.__setattr__(self, name, value)
            return
        self._require_valid("アトリビュートの設定")
        try:
            plug = self.getPlug(name)
        except (AttributeError, RuntimeError) as error:
            raise AttributeError(
                f"{_missing_member_message(self, name, 'Mayaのアトリビュート')}(mlibのノードにPythonのアトリビュートは追加できません)"
            ) from error
        plug.set(value)

    def getShadingEngines(self):
        """このノードから直接つながっているShadingEngineを取得する。

        同じものは1回だけ含む。

        Returns:
            list[ShadingEngine]: 直接の接続先のShadingEngine。テクスチャからヒストリをたどって探すものではない。
        """
        # 循環参照の回避: 同じパッケージ内で相互に参照するため、使う時点で読み込む。
        from .shadingEngine import ShadingEngine

        result, seen = [], set()
        for plug in self._dependency_fn().getConnections():
            for destination in plug.connectedTo(False, True):
                obj = destination.node()
                key = om2.MObjectHandle(obj).hashCode()
                if obj.hasFn(om2.MFn.kShadingEngine) and key not in seen:
                    seen.add(key)
                    result.append(ShadingEngine(obj))
        return result

    def sameNode(self, other):
        """同じMayaのノードを指しているか調べる。

        ``==`` と違い、DAGノードのインスタンス(パス)の違いは区別しない。

        Args:
            other (object): 比べる相手。Node以外ならFalse。

        Returns:
            bool: どちらも生存していて、同じMayaのノードを指していればTrue。
        """
        return isinstance(other, Node) and self.isAlive() and other.isAlive() and self._mobject == other._mobject

    def isValid(self):
        """シーン上でノードが有効か調べる。

        ノードそのものが有効かを返し、このオブジェクトが持つDAGパスは確かめない。
        持っているパスのインスタンスだけが削除されても、ノードが残っていればTrueになる。
        その場合、パスを使う操作はRuntimeErrorになる。

        Returns:
            bool: ノードのハンドルが有効なら ``True``。
        """
        handle = self._handle
        return handle is not None and handle.isValid()

    def isAlive(self):
        """ノードのMayaのオブジェクトが、メモリ上に残っているか調べる。

        Returns:
            bool: MObjectHandle.isAlive() の結果。削除済みでも、Undoのために残っているノードはTrueになることがある。
        """
        handle = self._handle
        return handle is not None and handle.isAlive()

    def mnode(self):
        """このオブジェクトが持つ、Maya API 2.0のMObjectを返す。

        Returns:
            om2.MObject: このオブジェクトが指すノードのMObject。
        """
        return self._mobject

    def mfn(self):
        """このノードに使えるOpenMayaのfunction setのうち、最も具体的なものを取得する。

        呼び出すたびに新しく作る。Nodeでは ``om2.MFnDependencyNode`` を返す。DagNodeは ``MFnDagNode``、
        Transformは ``MFnTransform`` のように、派生クラスが最も具体的なfunction setを返すよう上書きする。
        内部のキャッシュとは別のものなので、戻り値を持ち続けてもほかの取得に影響しない。

        Returns:
            om2.MFnDependencyNode: このノードの function set。

        Raises:
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        return self._alive_fn()

    def getType(self, inherited=False):
        """Mayaのノードの型の名前、または型の継承の並びを取得する。

        動的に作ったクラスも含め、mlibのクラス名ではなく、MayaのnodeTypeの名前をそのまま返す。

        Args:
            inherited (bool): Trueなら、``cmds.nodeType(inherited=True)`` と同じ順で継承の並びを返す
                (基底の型から自身の型へ。``node`` は含まない)。既定はFalseで、型の名前だけを返す。

        Returns:
            str | list[str]: 既定ではMayaのnodeTypeの名前。inherited=Trueでは、継承の並びの新しいリスト。

        Raises:
            TypeError: inheritedがbool以外の場合。
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        _require_bool(inherited, "inherited")
        type_name = self._alive_fn().typeName
        if not inherited:
            return type_name
        return list(reversed(_inherited_node_types(type_name)))

    def hasFn(self, fn):
        """このノードのMObjectが、指定したOpenMayaの関数型に対応するか調べる。

        ``mnode().hasFn(fn)`` と同じ。Mayaのノードの型の継承(:meth:`isType`)ではなく、
        ``om2.MFn.kDagNode`` のようなAPIの関数型で判定する。

        Args:
            fn (int): ``om2.MFn`` の定数。

        Returns:
            bool: 対応していればTrue。

        Raises:
            TypeError: fnがint以外の場合。
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        if not isinstance(fn, int) or isinstance(fn, bool):
            raise TypeError("fnはint(om2.MFnの定数)で指定してください")
        self._alive_fn()
        return self._mobject.hasFn(fn)

    def getTypeId(self):
        """Maya内部のtypeIdを整数で取得する。

        同じMayaのセッションの中で、ノードの型を速く比べるときに使う。
        プラグインの版や環境によって値が変わることがあるので、ファイルなどへの保存には向かない。

        Returns:
            int: MTypeIdを数値にしたもの。

        Raises:
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        return self._alive_fn().typeId.id()

    def getPluginName(self):
        """ノードの型を登録したプラグインの名前を取得する。

        Returns:
            str: プラグインの名前。Maya本体のノードの型では空文字列。

        Raises:
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        return self._alive_fn().pluginName

    def getClassification(self):
        """ノードの型の分類の文字列を取得する。

        Returns:
            list[str]: ``MNodeClass.classification`` を1つだけ入れたリスト。分類が無ければ ``[""]``。
        """
        # cmdsは分類なしでも[""]を返す。その既存の返却形を維持する。
        return [om2.MNodeClass(self.getType()).classification]

    def isType(self, nodeType):
        """このノードの型が、指定した型そのものか、その派生の型か調べる。

        ``cmds.nodeType(inherited=True)`` が返す継承の並びで判定する。たとえばmeshノードは
        ``isType("shape")`` でTrueになる。Maya 2026で名前が変わった型は、どちらの名前でも判定できる
        (``isType("multDoubleLinear")`` と ``isType("multDL")``)。

        Args:
            nodeType (str): 調べるMayaのノードの型の名前。

        Returns:
            bool: 継承の並びにnodeTypeが含まれていればTrue。

        Raises:
            ValueError: nodeTypeが空文字列か、文字列以外の場合。
        """
        if not isinstance(nodeType, str) or not nodeType:
            raise ValueError("nodeTypeは空でない文字列で指定してください")
        if not self.isValid():
            return False
        return _real_node_type(nodeType) in _inherited_node_types(self._alive_fn().typeName)

    def isLocked(self):
        """ノードそのものがロックされているか調べる。

        アトリビュートごとのロックはPlug.isLocked()で調べる。

        Returns:
            bool: ロックされていればTrue。

        Raises:
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        return self._alive_fn().isLocked

    def setLocked(self, state=True, *, fast=False):
        """ノードそのもののロックを設定する。

        アトリビュートごとのロックはPlug.setLocked()を使う。
        通常は ``cmds.lockNode`` で変更し、Undoに記録する。``fast=True`` では
        ``MFnDependencyNode.isLocked`` を直接変更し、Undoに記録しない。

        Args:
            state (bool): Trueならロック、Falseなら解除する。既定はTrue。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Node: 自身。

        Raises:
            TypeError: stateかfastがbool以外の場合。
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合、またはMayaが変更を拒否した場合。
        """
        with _edit_context("mlibNodeSetLocked", fast):
            _require_bool(state, "state")
            fn = self._alive_fn()
            if fast:
                fn.isLocked = state
            else:
                cmds.lockNode(self.getFullName(), lock=state)
            return self

    def isFromReferencedFile(self):
        """ノードがリファレンスしたファイルから読み込まれたものか調べる。

        Returns:
            bool: リファレンスから読み込まれたノードならTrue。

        Raises:
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        return self._alive_fn().isFromReferencedFile

    def getReference(self):
        """このノードを読み込んだリファレンスノードを取得する。

        ``cmds.referenceQuery(node, referenceNode=True)`` と同じく、入れ子のリファレンスでは、
        ノードを直接読み込んだ最も内側のリファレンスノードを返す。

        Returns:
            Reference | None: リファレンスノード。リファレンスから読み込まれたノードでなければ ``None``。

        Raises:
            RuntimeError: ノードが削除済み・無効な場合。
        """
        self._require_valid("リファレンスの取得")
        if not self._alive_fn().isFromReferencedFile:
            return None
        return Node._from_name(cmds.referenceQuery(self.getFullName(), referenceNode=True))

    def isDefaultNode(self):
        """Mayaの既定のノードか調べる。

        既定のノードは、``time1``・``lambert1``・``defaultLightSet`` のように、新しいシーンに必ずあるノード。
        ``cmds.ls(defaultNodes=True)`` に含まれるノードでTrueになる。

        Returns:
            bool: 既定のノードならTrue。

        Raises:
            RuntimeError: ノードが削除済み・無効な場合。
        """
        self._require_valid("照会")
        return self._alive_fn().isDefaultNode

    def getSets(self, type=None):
        """このノードが入っているセット(objectSetとその派生の型)を取得する。

        ``cmds.listSets(object=node)`` と同じく、ノード自身がメンバーになっているセットを返す。

        - Shapeでは、コンポーネント(``f[0]`` など)だけがメンバーになっているセット(シェーディンググループなど)も含む。
        - Transformでは、Transform自身が入っているセットだけを返す。Shapeのセットは含まない。

        Args:
            type (str | None): セットのノードの型で絞る(``"shadingEngine"`` など)。派生の型も含む。Noneなら絞らない。

        Returns:
            list[ObjectSet]: セットのオブジェクト(``ShadingEngine`` などの派生の型も含む)。名前の順。無ければ空リスト。

        Raises:
            TypeError: typeが文字列・None以外の場合。
            ValueError: typeが空文字列の場合。
            RuntimeError: ノードが削除済み・無効な場合。
        """
        if type is not None:
            if not isinstance(type, str):
                raise TypeError("typeはstrかNoneで指定してください")
            if not type:
                raise ValueError("typeは空でない文字列で指定してください")
        self._require_valid("セットの取得")
        names = cmds.listSets(object=self.getFullName()) or []
        sets = [Node._from_name(name) for name in sorted(names)]
        return [node for node in sets if type is None or node.isType(type)]

    def isAncestorOf(self, other):
        """otherが、このノードの子孫か調べる。

        このオブジェクトが持つDAGパスで判定する。

        Args:
            other (Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
                調べる対象か、その名前。Plugはそれを持つノードを、Componentはそれを持つシェイプを指す。

        Returns:
            bool: 自身を除く子孫ならTrue。otherがDAGノードでない場合、無効なノードの場合、
                削除済みのアトリビュートの場合はFalse。

        Raises:
            TypeError: otherの型が対応していない場合。
            RuntimeError: 名前を解決できない場合、MObject・MPlugが空の場合、
                または自身が削除済みか無効な場合(持っているパスのインスタンスが消えた場合も含む)。
        """
        self._require_valid("子孫の取得")
        other_node = _resolve_input_or_none(other)
        self_full = self.getFullName()
        if other_node is None or not self_full:
            return False
        other_full = other_node.getFullName()
        return other_full != self_full and other_full.startswith(self_full + "|")

    def isParentOf(self, other):
        """保持するDAGパスで、otherが自身の直接の子か判定する。

        Args:
            other (Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
                対象の参照や名前。Plugは所有ノード、Componentは所有シェイプへ解決する。

        Returns:
            bool: 直接の子ならTrue。非DAG・無効なノード・削除済みアトリビュートはFalse。

        Raises:
            TypeError: otherが未対応型の場合。
            RuntimeError: 名前を解決できない、MObject・MPlugが空、または保持インスタンスが消失した場合。
        """
        other_node = _resolve_input_or_none(other)
        self_full = self.getFullName()
        if other_node is None or not self_full:
            return False
        other_full = other_node.getFullName()
        parent_prefix, separator, _ = other_full.rpartition("|")
        return bool(separator) and parent_prefix == self_full

    def isRoot(self):
        """DAGノードがワールドの直下にあるか調べる。

        Returns:
            bool: このオブジェクトが持つDAGパスの長さが1ならTrue。

        Raises:
            RuntimeError: DAGパスを持っていない(DAGノードでない)場合。
        """
        dag_path = self._current_dag_path()
        if dag_path is None:
            raise RuntimeError("ノードがDAGノードではありません")
        return dag_path.length() == 1

    def getNodeName(self, removeNamespace=False):
        """DAGパスを付けないノード名を取得する。

        DGノードにも使える。DAGの別の階層に同じ名前のノードがあっても、親のパスは付けない。
        そのため、Mayaのコマンドへ渡す一意な名前が必要なときはgetNameを使う。

        Args:
            removeNamespace (bool): ``True`` なら、ネームスペースも取り除く。既定はFalse。

        Returns:
            str: ネームスペースを含むノード名。``removeNamespace`` が ``True`` なら、
                ネームスペースを含まないノード名。

        Raises:
            RuntimeError: ノードが削除済みの場合、またはUndoで作成が取り消された(無効な)場合。
        """
        self._require_named()
        node_name = self._alive_fn().name()
        if removeNamespace:
            node_name = node_name.rsplit(":", 1)[-1]
        return node_name

    def getNamespace(self):
        """ノードが入っているネームスペースを取得する。

        Returns:
            Namespace: ノードが入っているネームスペース。
        """
        # common.namespace がNodeを参照するため、
        # 循環回避のためここで遅延 import する(mlib で意図的な相互依存の一つ)。
        from ..common import Namespace

        node_name = self.getNodeName()
        if ":" not in node_name:
            return Namespace(":")
        return Namespace(node_name.rsplit(":", 1)[0])

    def setNamespace(self, namespace, *, fast=False):
        """ノードを指定したネームスペースへ移す。

        移す先のネームスペースが無ければ作る。

        Args:
            namespace (str | Namespace): 移す先のネームスペースの名前。末尾の ``":"`` は付けても付けなくてもよい。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Node: 自身。ネームスペース付きの名前は :meth:`getNodeName` で取得する。

        Raises:
            ValueError: namespaceが空文字列か、文字列でない場合。
            RuntimeError: ネームスペースへ移せなかった場合。
        """
        with _edit_context("mlibNodeSetNamespace", fast):
            # common.namespaceとnodesの相互依存を避けるための遅延import。getNamespaceと同じ理由。
            from ..common import Namespace

            self._require_valid("名前の変更")
            if isinstance(namespace, Namespace):
                target_namespace = namespace
            elif isinstance(namespace, str) and namespace:
                target_namespace = Namespace(namespace)
            else:
                raise ValueError("namespaceは空でない文字列で指定してください")
            if not target_namespace.exists() and target_namespace.name != ":":
                if fast:
                    om2.MNamespace.addNamespace(target_namespace.name)
                else:
                    target_namespace = Namespace.create(target_namespace)
            namespace_name = target_namespace.name
            node_name = self.getNodeName(True)
            new_name = f"{namespace_name}:{node_name}" if namespace_name != ":" else node_name
            return self.rename(new_name, fast=fast)

    def delete(self, *, safe=False, fast=False):
        """このノードを、Mayaの標準の決まりで削除する。

        DAGの子も削除する。1回のUndoで戻せる。
        派生クラスは、このメソッドを上書きして専用の削除処理を書ける。

        削除の前に、自身とDAGの子孫を調べる。次のノードが含まれていれば、何も削除せずにRuntimeErrorにする。

        - ロックされたノード、リファレンスのノード。
        - 既定のノードや共有のノードなど、Mayaが削除を拒否するノード
          (``cmds.ls(undeletable=True)`` が返すもの。time1・persp・defaultLayerなど)。

        通常の経路の文言は、cmds.deleteと同じく要素ごとに示す(``ロックされたノード'x'は削除できません``・
        ``'x'は削除できません。ロックされた子か、読み取り専用の子があります``・``削除できないノードです: 'x'``)。
        fastでのロック・リファレンスの文言は ``ノードがロックされているか、リファレンスです: x``。

        Args:
            safe (bool): Trueなら、自身かDAGの子孫にDGの接続がある場合は削除しない。
                入力・出力・message・セットやマテリアルの接続をすべて含む。
                Falseならふつうに削除する。ロックの解除や、例外を抑えることはしない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: safeがboolでない場合。
            RuntimeError: 対象が無効な場合、ロック・リファレンス・削除できないノードを含む場合、
                またはMayaが削除を拒否した場合。
        """
        with _edit_context("mlibNodeDelete", fast):
            _require_bool(safe, "safe")
            self._require_valid("削除")
            if safe and self._has_delete_connections():
                return
            # 循環参照の回避: core は nodes を参照するため、使う時点で読み込む。
            from ..core.nodeEdit import delete_nodes

            delete_nodes([self], fast=fast)

    def rename(self, name, ignoreShape=False, *, fast=False):
        """ノード名を変更する。

        名前が重なったときの連番など、Mayaが直した後の名前は、戻り値の :meth:`getNodeName` で取得する。

        Args:
            name (str): 新しいノード名。DAGパスの区切りの ``|`` は含められない
                (Mayaが黙って別の文字へ置き換えるため、受け付けない)。
            ignoreShape (bool): ``True`` なら、Shapeの名前は変えない。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Node: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: nameに ``|`` を含む場合。
            RuntimeError: ノードが無効(削除済み)の場合(``無効な<クラス名>のため、名前の変更はできません``。
                fastも同じ)、このオブジェクトが持つDAGパスのインスタンスが削除された場合、
                またはMayaが名前の変更を拒否した場合。
        """
        with _edit_context("mlibNodeRename", fast):
            _require_node_name(name)
            # cmds.renameへ空の名前を渡すと文言の無いRuntimeErrorになるため、先に判定する。
            self._require_valid("名前の変更")
            if fast:
                # 循環参照の回避: core は nodes を参照するため、使う時点で読み込む。
                from ..core.nodeEdit import rename_node

                rename_node(self.mnode(), name, ignoreShape)
            else:
                cmds.rename(self.getName(), name, ignoreShape=ignoreShape)
            return self

    def duplicate(self, name=None, *, suffix=None, **kwargs):
        """このノードを複製する。

        :func:`mlib.duplicate` (``cmds.duplicate``)で複製し、1回のUndoで戻せる。
        複製したノードは、その型に合ったクラスで返す(``Joint`` なら ``Joint``、``Transform`` なら ``Transform``)。
        shape(``Mesh`` など)を複製すると、Mayaは親のtransformごと複製する。
        その場合は、複製の中で自身と同じ位置にあるshapeを返す。

        Args:
            name (str | None): 複製の名前。NoneならMayaの既定の名前(連番)。
            suffix (str | None): 複製したノードとDAGの子孫すべての名前を、「複製元の名前 + suffix」にする
                (:func:`mlib.duplicate` のsuffixと同じ)。Noneなら名前を変えない。
            **kwargs (object): ``cmds.duplicate`` のフラグ(``parentOnly``・``inputConnections``・
                ``upstreamNodes`` など。短縮名も使える)。

        Returns:
            Node: 複製した新しいノード(いちばん上のもの)。

        Raises:
            TypeError: フラグのロング名と短縮名を同時に指定した場合、またはsuffixが文字列・None以外の場合。
            ValueError: suffixが不正な場合、またはrenameChildren=Trueと同時に指定した場合。
            RuntimeError: ノードが無効(削除済み)の場合(``無効な<クラス名>のため、複製はできません``)、
                またはMayaが複製を拒否した場合。
        """
        # cmds.duplicateはnodesを参照するため、循環importを避けて関数内で読み込む。
        from ..cmds.duplicate import duplicate

        self._require_valid("複製")
        if name is not None:
            kwargs["name"] = name
        copied = duplicate(self, suffix=suffix, **kwargs)
        if not self.mnode().hasFn(om2.MFn.kShape) or copied.mnode().hasFn(om2.MFn.kShape):
            return copied
        # shapeの複製は親transformの複製になるため、同じ並びの位置にある子を自身の複製とする。
        parent = om2.MFnDagNode(self.mpath().transform())
        index = [parent.child(i) for i in range(parent.childCount())].index(self.mnode())
        copied_fn = om2.MFnDagNode(copied.mnode())
        if index >= copied_fn.childCount():
            raise RuntimeError(f"{self}の複製されたシェイプが見つかりません")
        return Node(copied_fn.child(index))

    def select(self, **kwargs):
        """このノードを選択する。

        既定では、今の選択を置き換える。:func:`mlib.select` (``cmds.select``)で選択し、1回のUndoで戻せる。

        Args:
            **kwargs (object): ``cmds.select`` のフラグ(``add``・``deselect``・``toggle``・
                ``hierarchy`` など。短縮名も使える)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: フラグのロング名と短縮名を同時に指定した場合。
            RuntimeError: ノードが無効(削除済み)の場合(``無効な<クラス名>のため、選択はできません``)、
                またはMayaが選択を拒否した場合。
        """
        # cmds.selectはnodesを参照するため、循環importを避けて関数内で読み込む。
        from ..cmds.select import select

        self._require_valid("選択")
        select(self, **kwargs)

    def getConnections(
        self,
        s=True,
        d=True,
        c=False,
        t=None,
        et=False,
        scn=False,
        source=True,
        destination=True,
        connections=False,
        type=None,
        exactType=False,
        skipConversionNodes=False,
        asPair=False,
        asNode=False,
        index=None,
    ):
        """接続を取得する。

        結果はPlug・Node・ペアのどれかの形で返す。既定では、直接つながっている相手を返す
        (``cmds.listConnections`` と同じ)。

        ``skipConversionNodes=True`` (または ``scn=True``)では、:meth:`~mlib.plugs.plug.Plug.getSource` /
        :meth:`~mlib.plugs.plug.Plug.getDestinations` と同じく、unitConversionの仲間
        (unitConversion・unitToTimeConversion・timeToUnitConversion)を飛ばして、その先を返す。

        Args:
            s (bool): Trueなら入力を含める。sourceと両方Trueのときだけ含める。
            d (bool): Trueなら出力を含める。destinationと両方Trueのときだけ含める。
            c (bool): connectionsの短縮名。
            t (str | None): typeの短縮名。
            et (bool): exactTypeの短縮名。
            scn (bool): skipConversionNodesの短縮名。skipConversionNodesとどちらかがTrueなら、変換ノードを飛ばす。
            source (bool): Trueなら入力を含める。
            destination (bool): Trueなら出力を含める。
            connections (bool): Trueなら、自身の側と相手の側のペアで返す。
            type (str | None): 接続先のノードの型で絞る。
            exactType (bool): Trueなら、型の名前が完全に一致するものだけに絞る。
            skipConversionNodes (bool): 既定はFalseで、直接つながっている相手を返す(``cmds.listConnections`` と同じ)。
                Trueなら、unitConversionの仲間を飛ばす。
            asPair (bool): Trueなら、自身の側のPlugと相手の側のペアで返す。
            asNode (bool): Trueなら、相手の側をNodeで返す。
            index (int | None): 結果のうち1件だけを返すときの番号。範囲外ならNone。

        Returns:
            list | Plug | Node | tuple | None: 条件に合う結果。
        """
        # 循環参照の回避: plugs は nodes を参照するため、使う時点で読み込む。
        from ..plugs.plug import Plug

        pairs = []
        as_pair = asPair or c or connections
        skip_conversion = scn or skipConversionNodes
        directions = [incoming for incoming, enabled in ((True, s and source), (False, d and destination)) if enabled]

        def collect(mplug, local):
            """Plug.getConnections(asPair=True, 子・要素の展開なし)と同じ順で直接の接続を集める。

            その中の重複の統合は、下の_connection_resultsが同じ初出順で行うため省く。

            Args:
                mplug (om2.MPlug): 接続をたどる自身側のプラグ。
                local (Plug | None): ペアの自身側。ペアで返さない場合はNone。

            Returns:
                None: 値を返さない。
            """
            for incoming in directions:
                if skip_conversion:
                    if incoming:
                        source_plug = mplug.source()
                        targets = [] if source_plug.isNull else [source_plug]
                    else:
                        targets = mplug.destinations()
                else:
                    targets = mplug.connectedTo(incoming, not incoming)
                pairs.extend((local, Plug(Plug._node_from_mplug(target), target)) for target in targets)

        # ペアで返さない場合、自身側のPlugは結果にも重複の判定にも使わない。
        # 接続の照会を上書きする派生クラスが無ければ、自身側のPlugを作らずMPlugから直接たどる。
        local_unused = not as_pair and not _subclass_overrides(Plug, "getConnections")
        for mp in self._dependency_fn().getConnections():
            if local_unused:
                collect(mp, None)
                continue
            local = Plug(self, mp)
            if local.__class__.getConnections is not Plug.getConnections:
                # 派生クラスが接続の照会を上書きする場合は、その実装を通す(引数typeが組込みを隠すため__class__)。
                pairs.extend(
                    local.getConnections(
                        s, d, source=source, destination=destination, skipConversionNodes=skip_conversion, asPair=True, checkChildren=False, checkElements=False
                    )
                )
                continue
            collect(local.mplug(), local)
        return Plug._connection_results(pairs, type or t, exactType or et, as_pair, asNode, index)

    def setKey(self, attributes=None, *, unit=None, timeUnit=None, uiUnits=False, **kwargs):
        """複数のアトリビュートへ、まとめてキーを設定する(``cmds.setKeyframe(node, attribute=[...])`` にあたる)。

        ``value`` / ``v`` は、:meth:`~mlib.plugs.plug.Plug.get` と同じ決まりの数値(角度は度、距離はcm)で受け取り、
        アトリビュートごとに換算する。fast引数は持たない(:meth:`~mlib.plugs.plug.Plug.setKey` と同じく、
        OpenMayaで打っても速くならないため)。

        Args:
            attributes (str | Iterable[str] | None): アトリビュート名。Noneなら、キーを設定できるすべてのアトリビュート
                (``cmds.setKeyframe(node)`` と同じ)。
            unit (str | None): 角度のvalueの単位。None(既定)と ``"deg"`` は度、``"rad"`` はラジアン。
            timeUnit (str | None): ``time`` / ``t`` の数値の単位。None(既定)と ``"frame"`` は今のUIの時間単位のフレーム、
                ``"sec"`` は秒(数値か、数値の並びだけを受け付ける)。
            uiUnits (bool): Trueなら、valueを今のUIの単位の数値で受け取る。既定はFalse。
            **kwargs: MayaのsetKeyframeのフラグ(``time``・``value``・``inTangentType`` など)。
                ``attribute`` / ``at`` は、ここではなく引数attributesで指定する。

        Returns:
            Node: 自身。

        Raises:
            TypeError: attributesが文字列・文字列の並び・None以外の場合、``attribute`` / ``at`` をkwargsに渡した場合、
                単位の型が不正な場合、または ``timeUnit="sec"`` でtimeに数値以外を指定した場合。
            ValueError: attributesが空の並びの場合、単位の名前が不正な場合、またはuiUnits=Trueと単位を同時に指定した場合。
            RuntimeError: ノードが無効な場合、またはMayaがキーの設定を拒否した場合。
        """
        # plugs は nodes を参照するため、循環importを避けて関数内で読み込む。
        from ..plugs.plug import _key_flags_to_ui

        if "attribute" in kwargs or "at" in kwargs:
            raise TypeError("アトリビュート名はattributes引数で渡してください")
        names = _attribute_names(attributes)
        # 値を含まないフラグで単位の引数だけを先に検査する(不正な指定でシーンを変えない)。
        _key_flags_to_ui(None, {}, unit, timeUnit, uiUnits)
        with undoChunk("mlibNodeSetKey"):
            self._require_valid("キーの設定")
            has_value = "value" in kwargs or "v" in kwargs
            if has_value and not uiUnits:
                # 値の換算はアトリビュートの種類(角度・距離)ごとに違うため、アトリビュートごとに打つ。
                plugs = [self.getPlug(name) for name in names] if names is not None else self.getPlugs(keyable=True, scalar=True)
                for plug in plugs:
                    cmds.setKeyframe(plug.getFullName(), **_key_flags_to_ui(plug.mplug(), kwargs, unit, timeUnit, uiUnits))
                return self
            flags = _key_flags_to_ui(None, kwargs, None, timeUnit, True)
            if names is not None:
                flags["attribute"] = names
            cmds.setKeyframe(self.getFullName(), **flags)
            return self

    def removeKey(self, attributes=None, *, time=None, timeUnit=None):
        """複数のアトリビュートのキーを削除する(``cmds.cutKey(node, attribute=[...], clear=True)`` にあたる)。

        キーのクリップボードは変えない。キーをすべて削除すると、Mayaと同じく、空になったカーブも削除される。
        fast引数は持たない(OpenMayaでキーを1つずつ消すほうが、cmds.cutKeyより遅いため)。

        Args:
            attributes (str | Iterable[str] | None): アトリビュート名。Noneなら、キーのあるすべてのアトリビュート。
            time (float | Sequence[float] | None): 削除する時刻、または両端を含む範囲 ``(start, end)``。Noneならすべてのキー。
            timeUnit (str | None): timeの単位。None(既定)と ``"frame"`` は今のUIの時間単位のフレーム、``"sec"`` は秒。

        Returns:
            Node: 自身。キーが無ければ何もしない。

        Raises:
            TypeError: attributesが文字列・文字列の並び・None以外の場合、timeが数値・2つの数値の並び・None以外の場合、
                またはtimeUnitが文字列・None以外の場合。
            ValueError: attributesが空の並びの場合、timeが有限でない場合、範囲の始まりが終わりより大きい場合、
                またはtimeUnitが対応していない単位の名前の場合。
            RuntimeError: ノードが無効な場合、またはMayaが削除を拒否した場合。
        """
        # plugs は nodes を参照するため、循環importを避けて関数内で読み込む。
        from ..plugs.plug import _cut_key_flags

        names = _attribute_names(attributes)
        flags = _cut_key_flags(time, timeUnit)
        with undoChunk("mlibNodeRemoveKey"):
            self._require_valid("キーの削除")
            if names is not None:
                flags["attribute"] = names
            cmds.cutKey(self.getFullName(), clear=True, **flags)
            return self

    def moveKey(self, attributes=None, *, time=None, timeOffset=0, valueOffset=0, unit=None, timeUnit=None):
        """複数のアトリビュートのキーの、時刻と値をずらす。

        1回のUndoで戻せる。値の換算はアトリビュートの種類(角度・距離)ごとに違うため、アトリビュートごとに
        :meth:`Plug.moveKey <mlib.plugs.plug.Plug.moveKey>` と同じ処理を行う。fast引数は持たない。

        Args:
            attributes (str | Iterable[str] | None): アトリビュート名。Noneなら、キーを設定できるスカラーの
                アトリビュートのうち、キーのあるもの。
            time (float | Sequence[float] | None): 動かすキーの時刻、または両端を含む範囲。Noneならすべてのキー。
            timeOffset (float): 時刻の移動量。
            valueOffset (float): 値の移動量(角度は度、距離はcm)。
            unit (str | None): 角度のvalueOffsetの単位。None(既定)と ``"deg"`` は度、``"rad"`` はラジアン。
            timeUnit (str | None): time・timeOffsetの単位。None(既定)と ``"frame"`` はフレーム、``"sec"`` は秒。

        Returns:
            Node: 自身。

        Raises:
            TypeError: attributesが文字列・文字列の並び・None以外の場合、またはほかの引数の型が不正な場合。
            ValueError: attributesが空の並びの場合、有限でない値を渡した場合、または単位の名前が対応していない場合。
            RuntimeError: ノードが無効な場合、またはMayaが移動を拒否した場合。
        """
        # plugs は nodes を参照するため、循環importを避けて関数内で読み込む。
        from ..plugs.plug import _move_key_flags, _move_plug_keys

        names = _attribute_names(attributes)
        with undoChunk("mlibNodeMoveKey"):
            self._require_valid("キーの移動")
            plugs = [self.getPlug(name) for name in names] if names is not None else self.getPlugs(keyable=True, scalar=True)
            flags = [(plug, _move_key_flags(plug, time, timeOffset, valueOffset, unit, timeUnit)) for plug in plugs]
            for plug, plug_flags in flags:
                _move_plug_keys(plug.getFullName(), plug_flags)
            return self

    def getHistory(self, type=None, future=False):
        """ヒストリのノードを取得する。

        ``MItDependencyGraph`` でヒストリをたどって探す。

        Args:
            type (str | None): ノードの型で絞る。派生の型も含む。Noneなら絞らない。
            future (bool): Trueなら下流を、Falseなら上流を探す。既定はFalse。

        Returns:
            list[Node]: ``cmds.listHistory`` と同じ順(深さ優先)。自身は含まず、同じものは1回だけ含む。
                見つからなければ空リスト。Shapeを持つTransformでは、``listHistory`` と同じく、
                中間オブジェクトでない直下のShapeのヒストリを返す。DAGノードは最初のDAGパスで返す。

        Raises:
            RuntimeError: 無効な(削除済みの)ノードの場合。
        """
        self._require_valid("ヒストリの取得")
        # cmds.listHistory(leaf=True) と同じく、Shapeを持つTransformは中間オブジェクトでない
        # 直下のShapeから探索する(Transform自身の入出力は含めない)。
        roots = [self._mobject]
        if self._mobject.hasFn(om2.MFn.kTransform):
            dag = om2.MFnDagNode(self._mobject)
            shapes = []
            for index in range(dag.childCount()):
                child = dag.child(index)
                if child.hasFn(om2.MFn.kShape) and not om2.MFnDagNode(child).isIntermediateObject:
                    shapes.append(child)
            roots = shapes or roots
        direction = om2.MItDependencyGraph.kDownstream if future else om2.MItDependencyGraph.kUpstream
        result = []
        uuid_fn = om2.MFnDependencyNode()

        def uuid_of(mobject):
            """重複判定用のUUID文字列(ノードごとに一意)。"""
            uuid_fn.setObject(mobject)
            return uuid_fn.uuid().asString()

        seen = {uuid_of(self._mobject)}
        for root in roots:
            # listHistory と同じ深さ優先・ノード単位の順。各ノードは最初の出現だけを残す。
            iterator = om2.MItDependencyGraph(root, om2.MFn.kInvalid, direction, om2.MItDependencyGraph.kDepthFirst, om2.MItDependencyGraph.kNodeLevel)
            while not iterator.isDone():
                mobject = iterator.currentNode()
                iterator.next()
                key = uuid_of(mobject)
                if key in seen:
                    continue
                seen.add(key)
                node = Node._wrap_resolved(*_resolve_node(mobject))
                if type is None or node.isType(type):
                    result.append(node)
        return result

    def findCycles(self):
        """このノードを通るDGの循環(cycle)を、アトリビュートの並びで取得する。

        ``cmds.cycleCheck(node, list=True)`` は、循環に関わるアトリビュートを順不同でまとめて返す
        (このノードを含む強連結の部分)。そこから、接続(出力→入力)と、同じノードの中の入力→出力の
        つながりをたどり、このノードを通る単純な循環を1つずつ取り出す。

        - 各循環は、このノードの入力アトリビュートから始まる。
        - 並びは ``[自身の入力, 自身の出力, 次のノードの入力, 次のノードの出力, ...]`` の流れの順。
          最後の要素の次は先頭へ戻る。
        - ``cycleCheck`` と同じく、接続による循環だけを調べる。DAGの親子による暗黙の依存
          (子のworldMatrixで親を動かすなど)は ``cycleCheck`` が報告しないため含まない。

        シーンは変更しない。

        Returns:
            list[list[Plug]]: 循環ごとのアトリビュートの並び。循環が無ければ空リスト。

        Raises:
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        # nodes/plugsの相互依存を避けるため遅延importする。
        from ..plugs.plug import Plug

        self._require_valid("循環の検索")
        names = cmds.cycleCheck(self.getFullName(), list=True) or []
        own = om2.MObjectHandle(self._mobject)
        plugs = {}
        for name in names:
            selection = om2.MSelectionList()
            selection.add(name)
            mplug = selection.getPlug(0)
            plugs[_plug_key(mplug)] = mplug
        edges = {key: [] for key in plugs}
        for key, mplug in plugs.items():
            edges[key].extend(target for target in map(_plug_key, mplug.destinations()) if target in plugs)
            if mplug.isDestination:
                # 同じノードの出力(循環上で入力接続を持たないもの)へ、入力から依存の辺を張る。
                edges[key].extend(other for other, candidate in plugs.items() if other[0] == key[0] and other != key and not candidate.isDestination)
        starts = [key for key, mplug in plugs.items() if mplug.isDestination and om2.MObjectHandle(mplug.node()) == own]
        cycles = []
        seen = set()
        for start in starts:
            stack = [(start, [start])]
            while stack:
                key, path = stack.pop()
                for following in edges[key]:
                    if following == start and frozenset(path) not in seen:
                        seen.add(frozenset(path))
                        cycles.append(path)
                    elif following != start and following not in path:
                        stack.append((following, path + [following]))
        owners = {}

        def owner(mplug):
            """MPlugの持ち主のノードのオブジェクトを返す。自身なら自身を返し、同じノードには同じオブジェクトを使い回す。"""
            handle = om2.MObjectHandle(mplug.node())
            if handle == own:
                return self
            if handle.hashCode() not in owners:
                owners[handle.hashCode()] = Node._wrap_resolved(*_resolve_node(mplug.node()))
            return owners[handle.hashCode()]

        return [[Plug(owner(plugs[key]), plugs[key]) for key in path] for path in cycles]

    def resetAttrs(self, attributes=None, *, fast=False):
        """アトリビュートを既定値へ戻す。

        指定したアトリビュートを戻す。省略したときは、書き込めてキーを設定できるアトリビュートを戻す。
        Transformでも同じ決まりで、省略時はtranslate・rotate・scale・shearに限らず、キーを設定できるもの
        すべて(visibilityなども含む)を戻す。

        Args:
            attributes (str | Plug | Iterable[str | Plug] | None): アトリビュート名か、このノードのPlug
                (名前と混ぜてもよい)。Noneなら、キーを設定できる数値・単位付き・enumのアトリビュートを対象にする。
                そのうち、マルチアトリビュート・ロック・入力の接続・書込み禁止・対応していない型のものは除く
                (通常とfastで同じものを選ぶ)。明示したアトリビュートのエラーは、除かずにそのまま例外にする。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            list[Plug]: 既定値へ戻したアトリビュート。すべての変更を1回のUndoにまとめる。

        Raises:
            AttributeError: 指定したアトリビュートが存在しない場合。
            TypeError: 名前・Plug以外を指定した場合、または明示したアトリビュートが既定値へ戻せない型の場合。
            ValueError: 別のノードのPlugを指定した場合。
            RuntimeError: 明示したアトリビュートが、ロックや接続などで書き込めない場合。
        """
        with _edit_context("mlibNodeResetAttrs", fast):
            if attributes is None:
                # getPlugs(keyable, scalar) は cmds.listAttr と同じ列挙を om2 で行うため、fastでもcmdsを呼ばない。
                # listAttr(scalar=True) はマルチアトリビュートも返すためマルチアトリビュートを除く(要素ごとのresetが必要)。
                plugs = [
                    plug
                    for plug in self.getPlugs(keyable=True, scalar=True)
                    if not plug.mplug().isArray and plug.getDefault() is not None and not plug.isDestination()
                ]
                # 通常/fastとも、ロック・入力接続・書込み禁止をfastの書込みと同じ検査で除く。
                plugs = [plug for plug in plugs if _writable_plug(plug)]
            else:
                plugs = self._plugs_from(attributes)
            for plug in plugs:
                plug.reset(fast=fast)
            return plugs

    def setAttrFlags(self, attributes, locked=None, keyable=None, channelBox=None, *, children=False, fast=False):
        """アトリビュートのロック・キーを設定できるか・チャンネルボックスへの表示を変更する。

        先に状態の型を確かめ、すべてのアトリビュートを解決してから、順に変更する。
        途中で失敗しても、それまでの変更は自動では戻さない。変更は各Plugの :meth:`Plug.setFlags` で行う。

        Args:
            attributes (str | Plug | Iterable[str | Plug]): アトリビュート名か、このノードのPlug(名前と混ぜてもよい)。
            locked (bool | None): Trueならロック、Falseなら解除する。Noneなら変えない。
            keyable (bool | None): キーを設定できるようにするか。Noneなら変えない。
            channelBox (bool | None): チャンネルボックスに表示するか。Noneなら変えない。
                keyable=Trueなら、Mayaによって表示される。
            children (bool): Trueなら、コンパウンドアトリビュート(``t`` など)の子(``tx`` など)にも同じ状態を設定する。
                既定はFalseで、指定したアトリビュートだけを変える(Mayaの ``setAttr`` と同じく、親のkeyableと
                チャンネルボックスの表示は子へ及ばない。ロックは親から子へ受け継がれる)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Node: 自身。

        Raises:
            AttributeError: 指定したアトリビュートが存在しない場合。
            TypeError: 必須の引数が足りない場合、fast・childrenや状態の型が不正な場合、
                または名前・Plug以外を指定した場合。
            ValueError: 別のノードのPlugを指定した場合。
            RuntimeError: Mayaが変更を拒否した場合。
        """
        with _edit_context("mlibNodeSetAttrFlags", fast):
            flags = _validated_flags(locked, keyable, channelBox)
            _require_bool(children, "children")
            plugs = self._plugs_from(attributes)
            if flags:
                for plug in plugs:
                    plug.setFlags(locked=locked, keyable=keyable, channelBox=channelBox, children=children, fast=fast)
            return self

    def getPlugs(self, userDefined=False, includeChildren=True, *, writable=False, **listAttrFlags):
        """アトリビュートの一覧を、Plugのオブジェクトで取得する。

        - ``userDefined=True``: ユーザーが追加した(動的な)アトリビュートだけを、Mayaの定義から追加した順に、
          型に合ったPlugで作る。cmdsは使わない。マルチアトリビュートはMultiPlugになり、
          非表示やkeyableでないものも含む。
        - それ以外: ``cmds.listAttr`` の条件(``keyable=True`` など)で取得する。
          フラグ無し・``keyable=True``・``scalar=True`` (組み合わせてもよい)では ``cmds.listAttr`` を呼ばず、
          OpenMayaで定義をたどって同じ順・同じ結果を求める。トップレベルの定義の順に並べ、
          コンパウンドアトリビュートの子は親のすぐ後に置く。マルチアトリビュートであるコンパウンドアトリビュートの子は含めない。

        Args:
            userDefined (bool): Trueなら、ユーザー定義のアトリビュートだけを返す。listAttrのフラグとは同時に指定できない。
                既定はFalse。
            includeChildren (bool): Trueなら、コンパウンドアトリビュートの子も含める。Falseならトップレベルだけ。既定はTrue。
            writable (bool): Trueなら、今書き込めるものだけに絞る。書き込めるのは、ロックされておらず、
                animCurve以外からの入力の接続が無いもの(親・子のロックと入力も見る)。
                animCurveが直接つながったものは含める。既定はFalse。
            **listAttrFlags: ``userDefined=False`` のときに ``cmds.listAttr`` へ渡すフラグ。

        Returns:
            list[Plug]: 新しいリスト。userDefinedでは追加した順、それ以外はlistAttrの順。
                解決できないパスは省き、見つからなければ空リスト。
                名前が必要なら ``[plug.getLongName() for plug in ...]`` を使う。

        Raises:
            TypeError: userDefined・includeChildren・writableがboolでない場合、
                またはuserDefined=TrueとlistAttrのフラグを同時に指定した場合。
            RuntimeError: ノードが無効な場合、listAttrが失敗した場合、
                またはuserDefined=TrueかつincludeChildren=Trueで、マルチアトリビュートである
                コンパウンドアトリビュートの子(番号を指定していないもの)が含まれる場合。
        """
        _require_bool(userDefined, "userDefined")
        _require_bool(includeChildren, "includeChildren")
        _require_bool(writable, "writable")
        self._require_valid("アトリビュートの一覧の取得")
        plugs = self._list_plugs(userDefined, includeChildren, listAttrFlags)
        if writable:
            plugs = [plug for plug in plugs if _is_writable(plug.mplug())]
        return plugs

    def getAliases(self):
        """このノードのアトリビュートのエイリアス(別名)を取得する。

        Returns:
            list[tuple[str, Plug]]: ``(エイリアス名, 対応するPlug)`` のリスト。
                エイリアスが無ければ空リスト。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("エイリアスの取得")
        # マルチアトリビュート・コンパウンドアトリビュートパスはgetPlugで解決し、別のMayaコマンドで名前を再解決しない。
        return [(alias, self.getPlug(name)) for alias, name in self._dependency_fn().getAliasList()]

    def addAttr(
        self,
        longName=_UNSET,
        type=None,
        subType=None,
        channelBox=_UNSET,
        childNames=None,
        childShortNames=None,
        childSuffixes=None,
        proxy=_UNSET,
        getPlug=True,
        *,
        safe=False,
        fast=False,
        unit="deg",
        timeUnit="frame",
        attributeType=_UNSET,
        at=_UNSET,
        binaryTag=_UNSET,
        bt=_UNSET,
        cachedInternally=_UNSET,
        ci=_UNSET,
        category=_UNSET,
        ct=_UNSET,
        dataType=_UNSET,
        dt=_UNSET,
        defaultValue=_UNSET,
        dv=_UNSET,
        disconnectBehaviour=_UNSET,
        dcb=_UNSET,
        edit=_UNSET,
        e=_UNSET,
        enforcingUniqueName=_UNSET,
        eun=_UNSET,
        enumName=_UNSET,
        en=_UNSET,
        exists=_UNSET,
        ex=_UNSET,
        fromPlugin=_UNSET,
        fp=_UNSET,
        hasMaxValue=_UNSET,
        hxv=_UNSET,
        hasMinValue=_UNSET,
        hnv=_UNSET,
        hasSoftMaxValue=_UNSET,
        hsx=_UNSET,
        hasSoftMinValue=_UNSET,
        hsn=_UNSET,
        hidden=_UNSET,
        h=_UNSET,
        indexMatters=_UNSET,
        im=_UNSET,
        internalSet=_UNSET,
        keyable=_UNSET,
        k=_UNSET,
        ln=_UNSET,
        maxValue=_UNSET,
        max=_UNSET,
        minValue=_UNSET,
        min=_UNSET,
        multi=_UNSET,
        m=_UNSET,
        niceName=_UNSET,
        nn=_UNSET,
        numberOfChildren=_UNSET,
        nc=_UNSET,
        parent=_UNSET,
        p=_UNSET,
        pxy=_UNSET,
        query=_UNSET,
        q=_UNSET,
        readable=_UNSET,
        r=_UNSET,
        shortName=_UNSET,
        sn=_UNSET,
        softMaxValue=_UNSET,
        smx=_UNSET,
        softMinValue=_UNSET,
        smn=_UNSET,
        storable=_UNSET,
        s=_UNSET,
        usedAsColor=_UNSET,
        uac=_UNSET,
        usedAsFilename=_UNSET,
        uaf=_UNSET,
        usedAsProxy=_UNSET,
        uap=_UNSET,
        worldSpace=_UNSET,
        ws=_UNSET,
        writable=_UNSET,
        w=_UNSET,
        cb=_UNSET,
        **kwargs,
    ):
        """アトリビュートを追加する。

        型・既定値・フラグを指定して追加する。作るためだけのメソッドで、query/edit=Trueは受け付けない。
        ロング名と、対応する短縮名は同時に指定できない。

        型は、proxyの元のアトリビュート、明示したtype、attributeType/dataTypeの順に使う。
        どれも省いたときはdoubleになる。

        単位のある型では、数値の既定値と範囲を次の単位で指定する。om2.MAngle・om2.MTimeなどの
        単位付きの値は、そのまま使う。

        - 距離: cm。
        - 時間(time): timeUnitの単位(既定は今のUIの時間単位のフレーム)。
        - 角度(doubleAngle、またはsubType="doubleAngle"の子): unitの単位(既定は度)。

        通常は、Undoが有効ならUndoに記録する。fastではUndoの設定を変えずにOpenMayaで追加する。
        fastで対応していない型や定義のフラグは、追加する前に拒否する。

        Args:
            longName (str): ロング名。lnかsnだけを指定してもよい。
            type (str | None): 型の名前。at:/dt:の接頭辞も付けられる。指定すると、attributeType/dataTypeより優先する。
            subType (str | None): 自動で作る子の、共通の型。
            channelBox (bool): Trueならチャンネルボックスに表示する。cbでも指定できる。
            childNames (Sequence[str] | None): 子のロング名。
            childShortNames (Sequence[str] | None): 子の短縮名。
            childSuffixes (Sequence[str] | None): 親の名前の後ろに付けて子の名前にする接尾辞。
            proxy (Plug | str | None): プロキシの元にするアトリビュート。
            getPlug (bool): 既定のTrueなら追加したPlugを、FalseならNoneを返す。
            safe (bool): Trueなら、何度実行しても同じ結果になるようにする。同じ名前のアトリビュートがすでにあれば
                何も変えずに、そのPlug(getPlug=FalseならNone)を返す。既存の既定値・範囲・表示などは変えない。
                ただし、既存のアトリビュートの型(getType()で比べる)や、マルチアトリビュートかどうかが
                指定と違う場合は、safeでもTypeErrorにする。既定のFalseでは、名前が重なるとMayaのエラー
                (RuntimeError)になる。``Plug.set(safe=True)`` (失敗した数を返す)とは意味が違う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            unit (str): 角度のアトリビュートの、数値の既定値・min/max・softMin/softMaxの単位。既定の ``"deg"`` は度、
                ``"rad"`` はラジアン(``"degree"`` / ``"radians"`` などの別名も使える)。Mayaのフラグではない。
            timeUnit (str): 時間のアトリビュートの、数値の既定値・min/max・softMin/softMaxの単位。既定の ``"frame"`` は
                今のUIの時間単位のフレーム、``"sec"`` は秒(``"frames"`` / ``"seconds"`` などの別名も使える)。
                Mayaのフラグではない。
            attributeType (str): MayaのattributeTypeフラグ。
            at (str): attributeTypeの別名。
            binaryTag (str): MayaのbinaryTagフラグ。
            bt (str): binaryTagの別名。
            cachedInternally (bool): MayaのcachedInternallyフラグ。
            ci (bool): cachedInternallyの別名。
            category (str | Sequence[str]): Mayaのcategoryフラグ。
            ct (str | Sequence[str]): categoryの別名。
            dataType (str | Sequence[str]): MayaのdataTypeフラグ。
            dt (str | Sequence[str]): dataTypeの別名。
            defaultValue (object): 追加する型に合った既定値。数値のコンパウンドアトリビュートは成分を並べて、
                型付きのデータはPlug.setと同じ形で指定する。
            dv (object): defaultValueの別名。
            disconnectBehaviour (int): MayaのdisconnectBehaviourフラグ。
            dcb (int): disconnectBehaviourの別名。
            edit (bool): Trueは受け付けない(作るためだけのメソッドのため)。
            e (bool): editの別名。
            enforcingUniqueName (bool): MayaのenforcingUniqueNameフラグ。
            eun (bool): enforcingUniqueNameの別名。
            enumName (str): MayaのenumNameフラグ。
            en (str): enumNameの別名。
            exists (bool): Mayaのexistsフラグ。
            ex (bool): existsの別名。
            fromPlugin (bool): MayaのfromPluginフラグ。
            fp (bool): fromPluginの別名。
            hasMaxValue (bool): MayaのhasMaxValueフラグ。
            hxv (bool): hasMaxValueの別名。
            hasMinValue (bool): MayaのhasMinValueフラグ。
            hnv (bool): hasMinValueの別名。
            hasSoftMaxValue (bool): MayaのhasSoftMaxValueフラグ。
            hsx (bool): hasSoftMaxValueの別名。
            hasSoftMinValue (bool): MayaのhasSoftMinValueフラグ。
            hsn (bool): hasSoftMinValueの別名。
            hidden (bool): Mayaのhiddenフラグ。
            h (bool): hiddenの別名。
            indexMatters (bool): MayaのindexMattersフラグ。
            im (bool): indexMattersの別名。
            internalSet (bool): MayaのinternalSetフラグ。
            keyable (bool): Mayaのkeyableフラグ。
            k (bool): keyableの別名。
            ln (str): longNameの別名。
            maxValue (float | om2.MAngle | om2.MDistance | om2.MTime): MayaのmaxValueフラグ。
            max (float | om2.MAngle | om2.MDistance | om2.MTime): maxValueの別名。
            minValue (float | om2.MAngle | om2.MDistance | om2.MTime): MayaのminValueフラグ。
            min (float | om2.MAngle | om2.MDistance | om2.MTime): minValueの別名。
            multi (bool): Mayaのmultiフラグ。
            m (bool): multiの別名。
            niceName (str): MayaのniceNameフラグ。
            nn (str): niceNameの別名。
            numberOfChildren (int): MayaのnumberOfChildrenフラグ。
            nc (int): numberOfChildrenの別名。
            parent (str): 親にする既存のコンパウンドアトリビュートの名前。ノードの親を指定するものではない。
            p (str): parentの別名。
            pxy (Plug | str | None): proxyの別名。
            query (bool): Trueは受け付けない(作るためだけのメソッドのため)。
            q (bool): queryの別名。
            readable (bool): Mayaのreadableフラグ。
            r (bool): readableの別名。
            shortName (str): MayaのshortNameフラグ。
            sn (str): shortNameの別名。
            softMaxValue (float | om2.MAngle | om2.MDistance | om2.MTime): MayaのsoftMaxValueフラグ。
            smx (float | om2.MAngle | om2.MDistance | om2.MTime): softMaxValueの別名。
            softMinValue (float | om2.MAngle | om2.MDistance | om2.MTime): MayaのsoftMinValueフラグ。
            smn (float | om2.MAngle | om2.MDistance | om2.MTime): softMinValueの別名。
            storable (bool): Mayaのstorableフラグ。
            s (bool): storableの別名。
            usedAsColor (bool): MayaのusedAsColorフラグ。
            uac (bool): usedAsColorの別名。
            usedAsFilename (bool): MayaのusedAsFilenameフラグ。
            uaf (bool): usedAsFilenameの別名。
            usedAsProxy (bool): MayaのusedAsProxyフラグ。
            uap (bool): usedAsProxyの別名。
            worldSpace (bool): MayaのworldSpaceフラグ。
            ws (bool): worldSpaceの別名。worldSpaceと同時には指定できない。
            writable (bool): Mayaのwritableフラグ。
            w (bool): writableの別名。
            cb (bool): channelBoxの別名。
            **kwargs: Mayaへ渡すほかのフラグ。Pythonの予約語と同じ短縮名のisは、辞書を展開して渡す。
                internalSetとは同時に指定できない。

        Returns:
            Plug | None: getPlug=Trueなら追加したPlug。getPlug=FalseならNone。
                getPlug=Falseでも、アトリビュートの追加と既定値などの設定は行う。

        Raises:
            TypeError: ロング名と短縮名を同時に指定した場合、fast・safeがbool以外の場合、
                unitが文字列・None以外の場合、またはsafe=Trueで、既存のアトリビュートの型や
                マルチアトリビュートかどうかが指定と違う場合。
            ValueError: 名前を省いた場合、型の接頭辞が不正な場合、解決した結果attributeTypeとdataTypeを
                両方指定することになった場合、query/edit=Trueの場合、unitが対応していない単位の名前の場合、
                またはenumのdefaultValueのフィールド名がenumNameに無い場合。
            NotImplementedError: fastで、対応していない型や定義のフラグを指定した場合。

        Note:
            子の名前・成分の数と、確かめられる型付きの既定値は、追加する前に検査する。
            通常の経路で子を追加するときだけは公開のaddAttrを呼ぶので、派生クラスの上書き(override)も呼ばれる。
            fastでは、親と子の定義をまとめて作る。
            Maya・上書きしたメソッド・作成後の既定値や表示やproxyの接続が失敗しても、
            すでに済んだ追加は戻さない。
        """
        _merge_flags(
            kwargs,
            (
                (attributeType, at, "attributeType", "at"),
                (binaryTag, bt, "binaryTag", "bt"),
                (cachedInternally, ci, "cachedInternally", "ci"),
                (category, ct, "category", "ct"),
                (dataType, dt, "dataType", "dt"),
                (defaultValue, dv, "defaultValue", "dv"),
                (disconnectBehaviour, dcb, "disconnectBehaviour", "dcb"),
                (enforcingUniqueName, eun, "enforcingUniqueName", "eun"),
                (enumName, en, "enumName", "en"),
                (exists, ex, "exists", "ex"),
                (fromPlugin, fp, "fromPlugin", "fp"),
                (hasMaxValue, hxv, "hasMaxValue", "hxv"),
                (hasMinValue, hnv, "hasMinValue", "hnv"),
                (hasSoftMaxValue, hsx, "hasSoftMaxValue", "hsx"),
                (hasSoftMinValue, hsn, "hasSoftMinValue", "hsn"),
                (hidden, h, "hidden", "h"),
                (indexMatters, im, "indexMatters", "im"),
            ),
        )
        _merge_flags(kwargs, ((edit, e, "edit", "e"),))
        if "is" in kwargs:
            if internalSet is not _UNSET:
                raise _ArgumentError("'internalSet'と'is'は同時に指定できません")
            internalSet = kwargs.pop("is")
        if internalSet is not _UNSET:
            kwargs["internalSet"] = internalSet
        _merge_flags(kwargs, ((keyable, k, "keyable", "k"),))
        longName = _pick_alias(longName, ln, "longName", "ln", default="")
        _merge_flags(
            kwargs,
            (
                (maxValue, max, "maxValue", "max"),
                (minValue, min, "minValue", "min"),
                (multi, m, "multi", "m"),
                (niceName, nn, "niceName", "nn"),
                (numberOfChildren, nc, "numberOfChildren", "nc"),
                (parent, p, "parent", "p"),
            ),
        )
        proxy = _pick_alias(proxy, pxy, "proxy", "pxy", default=None)
        _merge_flags(
            kwargs,
            (
                (readable, r, "readable", "r"),
                (softMaxValue, smx, "softMaxValue", "smx"),
                (softMinValue, smn, "softMinValue", "smn"),
                (storable, s, "storable", "s"),
                (usedAsColor, uac, "usedAsColor", "uac"),
                (usedAsFilename, uaf, "usedAsFilename", "uaf"),
                (worldSpace, ws, "worldSpace", "ws"),
                (writable, w, "writable", "w"),
            ),
        )
        _merge_flags(kwargs, ((query, q, "query", "q"), (shortName, sn, "shortName", "sn"), (usedAsProxy, uap, "usedAsProxy", "uap")))
        channelBox = _pick_alias(channelBox, cb, "channelBox", "cb", default=False)
        _require_bool(safe, "safe")
        angle_unit = _angle_unit(unit)
        assert angle_unit is not None  # 既定値 "deg" を使うため None にならない。
        time_unit = _time_unit(timeUnit)
        assert time_unit is not None  # 既定値 "frame" を使うため None にならない。
        with _edit_context("mlibNodeAddAttr", fast):
            # 循環参照の回避: plugs は nodes を参照するため、使う時点で読み込む。
            from ..plugs.plug import Plug

            flags = {key: value for key, value in kwargs.items() if value is not None}
            if flags.get("query") or flags.get("edit"):
                raise ValueError("addAttrは作成だけに対応しています")
            if longName:
                flags["longName"] = longName
            name = flags.get("longName") or flags.get("shortName")
            if not isinstance(name, str) or not name:
                raise ValueError("longNameかshortNameを指定してください")
            show = channelBox or flags.pop("channelBox", False)
            proxy = proxy or flags.pop("proxy", None)
            if proxy is not None:
                proxy = Plug._resolve_input(proxy)
                type = proxy.getType()
                flags["usedAsProxy"] = True
            numeric, count, deferred = self._prepare_extra_attr_definition(
                flags, type, childNames, childShortNames, childSuffixes, sub_type=subType, angle_unit=angle_unit, time_unit=time_unit
            )
            if safe and self.hasAttr(name):
                existing = self.getPlug(name)
                _require_same_attr_definition(existing, flags)
                return existing if getPlug else None
            prepared = self._create_extra_attr_definition(
                name, flags, numeric, count, deferred, childNames, childShortNames, childSuffixes, subType, fast=fast, time_unit=time_unit
            )
            if not getPlug and (deferred is None or count) and not show and proxy is None:
                return None
            plug = self.getPlug(name)
            if deferred is not None and not count:
                if fast and prepared is not None:
                    setter, value, owner = prepared
                    setter(plug.mplug(), value)
                else:
                    plug.set(deferred, fast=fast)
            if show:
                plug.setFlags(channelBox=True, fast=fast)
            if proxy is not None:
                proxy.connectTo(plug, fast=fast)
            return plug if getPlug else None

    def moveAttrOrder(self, name, offset):
        """ユーザー定義のアトリビュートを、チャンネルボックスの上で前後へ動かす。

        Mayaにはアトリビュートを並べ替えるAPIが無い。そこで、移動元と移動先のうち手前の位置から
        末尾までのアトリビュートをまとめて削除し、新しい順で作り直す。

        - 移動先より後ろにある、移動と関係ないアトリビュートも作り直す。
        - 対応しているのは、数値・enum・文字列の型で、コンパウンドアトリビュートでもマルチアトリビュートでもない、
          トップレベルの動的なアトリビュートだけ。
        - 作り直すものに対応していないアトリビュートが含まれる場合は、何も変えずに例外にする。

        並べ替えが必要なときはUndoが有効であることを求め、作り直す途中で失敗したらUndoで元に戻そうとする。
        成功すると、削除前に取得したPlugは無効になるので、必要なPlugを取得し直す。

        Args:
            name (str): 動かすユーザー定義のアトリビュートのロング名。
            offset (int): 動かす位置の数。正の値なら末尾の方へ、負の値なら先頭の方へ動かす。
                範囲を超えて指定すると、先頭や末尾で止まる。

        Returns:
            Node: 自身。すべての変更を1回のUndoにまとめる。

        Raises:
            TypeError: 作り直す範囲に、コンパウンドアトリビュート・マルチアトリビュート・対応していない型の
                アトリビュートが含まれる場合。cmdsで作り直せないnon-connectableの定義も、変更する前に拒否する。
            ValueError: nameが、トップレベルのユーザー定義のアトリビュートの一覧に無い場合。
            RuntimeError: ノードが無効な場合、または安全に元へ戻すために必要なUndoが無効な場合。
        """
        # aliasAttrが管理する内部の保存領域は、表示順の変更や再作成の対象にしない。
        names = [om2.MFnAttribute(attribute).name for attribute in self._user_attributes()]
        names = [name for name in names if name != "attributeAliasList"]
        if name not in names:
            raise ValueError(f"{name}は{self.getFullName()}の最上位のユーザー定義アトリビュートではありません")
        old_index = names.index(name)
        new_index = max(0, min(len(names) - 1, old_index + offset))
        if new_index == old_index:
            return self
        if not cmds.undoInfo(query=True, state=True):
            raise RuntimeError("moveAttrOrderには、失敗したときにアトリビュートを復元するためのUndoが必要です")
        window_start = min(old_index, new_index)
        # Mayaの削除Undoは定義を末尾へ戻すため、元の並びの逆順に削除する。
        to_remove = list(reversed(names[window_start:]))
        names.remove(name)
        names.insert(new_index, name)
        to_recreate = names[window_start:]

        infos = [_dump_movable_attr(self.getPlug(attr_name)) for attr_name in to_recreate]
        aliases = [(alias, attr_name) for alias, attr_name in self._dependency_fn().getAliasList() if attr_name in to_recreate]
        connections = {}
        for info in infos:
            endpoint = self, info["longName"]
            pairs = [(endpoint, destination) for destination in info["destinations"]]
            if info["source"] is not None:
                pairs.append((info["source"], endpoint))
            for source, destination in pairs:
                key = source[0].getUuid(), source[1], destination[0].getUuid(), destination[1]
                connections[key] = source, destination
        # 削除後は古いPlugを使わず、全定義を作ってから接続を再解決する。
        # 途中のMayaエラーでは、この処理のチャンクだけをUndoして元の状態へ戻す。
        with undoTransaction("mlibNodeMoveAttrOrder"):
            for alias, _ in aliases:
                cmds.aliasAttr(self.getFullName() + "." + alias, remove=True)
            for attr_name in to_remove:
                self.getPlug(attr_name).delete(force=True)
            for info in infos:
                _create_movable_attr(self, info)
            for alias, attr_name in aliases:
                self.getPlug(attr_name).setAlias(alias)
            for source, destination in connections.values():
                source[0].getPlug(source[1]).connectTo(destination[0].getPlug(destination[1]))
            for info in infos:
                plug = self.getPlug(info["longName"])
                if info["locked"]:
                    plug.setFlags(locked=True)
        return self

    def getPlug(self, name):
        """このノードのアトリビュートを取得する。

        値を評価したり、マルチアトリビュートの要素を作ったりはしない。

        Args:
            name (str): ロング名・短縮名・エイリアス、またはノード名を除いたパス。
                マルチアトリビュートの要素と子は、``input3D[2].input3Dx`` のように指定できる。
                論理番号は0〜2147483647。

        Returns:
            Plug: このノードを持ち主とする、型に合ったクラスの新しいオブジェクト。
                まだ作られていないマルチアトリビュートの要素も取得できる。genericの型は基底のPlugになり、
                値の型はgetのときに判断する。

        Raises:
            ValueError: nameが空か、文字列以外の場合。
            RuntimeError: ノードが無効な場合、または ``input3Dx`` のように、決まっていない論理番号を含む場合。
            MissingAttributeError: アトリビュートが存在しない場合(文言は ``アトリビュートが見つかりません: <ノード名>.<name>``)。
                ``AttributeError`` と ``RuntimeError`` の両方の派生で、``mlib.getPlug("node.name")`` と同じ例外。
            AttributeError: 論理番号が上限を超える場合。
        """
        # nodes/plugsの相互依存を避けるため遅延importする。
        from ..plugs.plug import MAX_LOGICAL_INDEX, MissingAttributeError, Plug

        if not isinstance(name, str) or not name:
            raise ValueError("nameは空でないアトリビュートのパスで指定してください")
        self._require_valid("アトリビュートの取得")

        if "[" not in name:
            # 論理番号を含まない名前(``boundingBox.boundingBoxMin`` のような子アトリビュートの
            # パスを含む)は、従来どおり findPlug で解決する。
            try:
                mplug = self._dependency_fn().findPlug(name, False)
            except RuntimeError:
                mplug = None  # エイリアス名は findPlug で解決できないため、下で解決する。
            if mplug is not None:
                return Plug(self, mplug)

        mplug = Plug._attribute_path_plug(self._mobject, name)
        if mplug is None:
            if Plug._has_out_of_range_index(name):
                raise AttributeError(f"マルチアトリビュートの要素の論理番号は0〜{MAX_LOGICAL_INDEX}で指定してください: {self.getName()}.{name}")
            raise MissingAttributeError(f"アトリビュートが見つかりません: {self.getName()}.{name}")
        return Plug(self, mplug)

    def hasAttr(self, name):
        """アトリビュートがあるか調べる。

        :meth:`getPlug` で取得できるかどうかで判定する。

        Args:
            name (str): アトリビュート名か、アトリビュートのパス。

        Returns:
            bool: アトリビュートを取得できれば ``True``。
        """
        try:
            self.getPlug(name)
        except (AttributeError, RuntimeError, ValueError):
            return False
        return True

    def getUuid(self):
        """ノードのMayaのUUIDを取得する。

        Returns:
            str | None: ノードのUUID。ノードが無効なら ``None``。
        """
        if not self.isValid():
            return None
        return om2.MFnDependencyNode(self._mobject).uuid().asString()

    def getName(self):
        """最短の一意な名前を取得する。

        Mayaのコマンドへ渡すと、このオブジェクトが持つインスタンスを指せる名前になる。

        - DAGノード: このオブジェクトが持つDAGパスのpartialPathName。
        - DGノード: ノード名。

        名前は覚えておかず、呼ぶたびにMayaから取得する。
        別の階層に同じ短い名前のノードがあると、一意にするために親を含む部分的なパス(``grp1|ctrl`` など)になる。
        新しい名前を組み立てる元にするとき(接尾辞の付け替えなど)は、:meth:`getNodeName` を使う。

        Returns:
            str: 今の名前。

        Raises:
            RuntimeError: ノードが削除済みか、Undoで作成が取り消された(無効な)場合、
                またはノードは有効だが、このオブジェクトが持つDAGパスのインスタンスが削除された場合。
        """
        self._require_named()
        dag_path = self._dag_path
        if dag_path is None:
            return self._dependency_fn().name()
        if not dag_path.isValid():
            self._current_dag_path()  # 保持するDAGインスタンスが消えた場合は RuntimeError にする。
        return dag_path.partialPathName()

    def getFullName(self):
        """完全な名前を取得する。

        DAGノードでは、このオブジェクトが持つインスタンスの完全なDAGパスを返す。DGノードではノード名を返す。

        Returns:
            str: DAGノードではワールドから始まる完全なパス。DGノードではノード名。
                ノードそのものが無効なら空文字列。

        Raises:
            RuntimeError: ノードは有効だが、このオブジェクトが持つDAGパスのインスタンスが削除された場合。
        """
        handle = self._handle
        if handle is None or not handle.isValid():
            return ""
        dag_path = self._dag_path
        if dag_path is None:
            return self._dependency_fn().name()
        if not dag_path.isValid():
            self._current_dag_path()  # 保持するDAGインスタンスが消えた場合は RuntimeError にする。
        return dag_path.fullPathName()

    def _list_plugs(self, userDefined, includeChildren, listAttrFlags):
        """:meth:`getPlugs` の列挙の本体(writableで絞る前)。"""
        if userDefined:
            if listAttrFlags:
                raise TypeError(f"userDefined=TrueはlistAttrのフラグと同時に指定できません: {', '.join(sorted(listAttrFlags))}")
            # 名前へ変換して再検索せず、定義から型付きPlugを作る。マルチアトリビュートの要素は展開しない。
            from ..plugs.plug import Plug

            return [Plug(self, om2.MPlug(self._mobject, attribute)) for attribute in self._user_attributes(includeChildren)]
        if all(name in _OM2_LIST_ATTR_FLAGS and value is True for name, value in listAttrFlags.items()):
            # 循環参照の回避: plugs は nodes を参照するため、使う時点で読み込む。
            from ..plugs.plug import Plug

            return [Plug(self, om2.MPlug(self._mobject, attribute)) for attribute in self._listed_attributes(includeChildren, **listAttrFlags)]
        names = cmds.listAttr(self.getFullName(), **listAttrFlags) or []
        plugs = []
        for name in names:
            try:
                plug = self.getPlug(name)
            except (AttributeError, RuntimeError, ValueError):
                continue
            if includeChildren or not plug.mplug().isChild:
                plugs.append(plug)
        return plugs

    def _plugs_from(self, attributes):
        """名前と自身のPlugが混在する指定を、自身のPlugの列へ解決する。

        Args:
            attributes (str | Plug | Iterable[str | Plug]): アトリビュート名・Plug、またはその列。

        Returns:
            list[Plug]: 指定順のPlug。

        Raises:
            AttributeError: 名前のアトリビュートが存在しない場合。
            TypeError: 名前・Plug以外の要素を含む場合。
            ValueError: 名前が空、または別のノードのPlugを含む場合。
        """
        # plugsはnodesを参照するため、循環importを避けて関数内で読み込む。
        from ..plugs.plug import Plug

        if isinstance(attributes, (str, Plug)):
            attributes = [attributes]
        plugs = []
        for item in attributes:
            if isinstance(item, Plug):
                if not item.getNode().sameNode(self):
                    raise ValueError(f"Plug {item.getFullName()!r}は{self.getName()!r}のものではありません")
                plugs.append(item)
            elif isinstance(item, str):
                if not item:
                    raise ValueError("アトリビュート名は空でない文字列で指定してください")
                plugs.append(self.getPlug(item))
            else:
                raise TypeError(f"attributesはこのノードの名前かPlugで指定してください: {type(item).__name__}")
        return plugs

    @staticmethod
    def _create_node(node_type, flags, *, fast=False):
        """Mayaのノードを作り、実際のnodeTypeに合ったクラスのオブジェクトを返す(作成処理の唯一の実体)。

        :func:`mlib.createNode` と :meth:`Container.createNode` が呼ぶ内部ヘルパーで、Undoチャンクは
        呼出し側で管理する。Mayaが認識しない型名(標準プラグインのロード後も未知の型)を拒否する。
        cmds.createNodeは未知の型でも例外にせずunknownノードを作るため、ここで止める。型名の照会で
        認識できる名前は作成前に判定する。2026で改名された型(``multDoubleLinear``/``multDL``・
        ``addDoubleLinear``/``addDL``)はどちらの名前もその版の型名へ読み替える。照会では分からない
        名前は、通常経路では作成した結果がunknownノードなら削除して拒否し(Undoの記録は
        作成と削除が対になる)、fastでは作成前に拒否する。jointの下へ作ったjointは、``cmds.joint`` と
        同じく親の ``scale`` を ``inverseScale`` へ接続する(通常経路は作成と同じUndoの単位)。

        Args:
            node_type (str): Maya nodeType名。
            flags (dict): createNodeへ渡す正規化済みのフラグ。parent/pを所有ノード名へ変換する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Node: 作った(sharedでは共有した)ノードの、実際のnodeTypeに合ったクラスのオブジェクト。
                登録表の規則で選んだクラス(登録型・動的クラス・Node)になる。

        Raises:
            TypeError: parentが未対応型・複数対象の場合。
            ValueError: nodeType名が空文字列または文字列以外、nameに ``|`` を含む、またはparentが
                空文字列・無効な参照の場合。
            RuntimeError: Mayaが認識しないnodeType名の場合(この版に無い型は、標準で追加された版が
                分かっていればその版を示す)、親名を解決できない場合、またはMayaが
                プラグインのロードやノード作成を拒否した場合。
            NotImplementedError: fastで未対応のフラグを指定した場合。
        """
        if not isinstance(node_type, str) or not node_type:
            raise ValueError("typeは空でない文字列で指定してください")
        # 2026で改名された型(multDoubleLinear→multDL等)は、どの版でもその版の型名へ読み替える。
        node_type = _real_node_type(node_type)
        # 遅延公開の__getattr__を毎回通らないよう、実装モジュールから直接取得する。
        from ..common.plugin import Plugin

        Plugin.ensureNodePlugin(node_type)
        # 型名の照会・OpenMayaでは解決できないがcmds.createNodeが互換名として作成する名前は、通常経路では
        # 作成した結果がunknownノードかどうかで判定し、fastはOpenMayaが作成できないため作成前に拒否する。
        known = _node_type_exists(node_type)
        if not known and fast:
            raise RuntimeError(_unknown_node_type_message(node_type))
        _require_node_name(flags.get("name"))
        for key in ("parent", "p"):
            if flags.get(key) is not None:
                flags[key] = Node._input_name(flags[key])
        parent = flags.get("parent") or flags.get("p")
        if fast:
            # nodeEditはNodeを参照するため、循環importを避けて関数内で読み込む。
            from ..core.nodeEdit import create_node

            obj = create_node(node_type, flags)
            # 作成したばかりの有効なMObjectなので、Node(obj)と同じ解決・型選択を入口の再判定なしで行う。
            node = Node._wrap_resolved(*_resolve_node(obj))
            return Node._connect_joint_parent(node, parent, fast=True)
        if known:
            created = cmds.createNode(node_type, **flags)
        else:
            unknown_types = ["unknown", "unknownDag", "unknownTransform"]
            existing = set(cmds.ls(type=unknown_types, uuid=True) or [])
            selection = cmds.ls(selection=True, long=True) or []
            created = cmds.createNode(node_type, **flags)
            if isinstance(created, str) and cmds.objExists(created):
                uuid = (cmds.ls(created, uuid=True) or [None])[0]
                if cmds.nodeType(created) in unknown_types and uuid not in existing:
                    # 未知の名前でMayaが作ったunknownノードは消し、作成前の選択へ戻してから拒否する。
                    cmds.delete(created)
                    cmds.select(selection, replace=True) if selection else cmds.select(clear=True)
                    raise RuntimeError(_unknown_node_type_message(node_type))
        if created is None:
            # shared=Trueで同名・同型のノードが既にある場合、cmds.createNodeは作成せずNoneを返す。
            name = flags.get("name") or flags.get("n")
            if not name:
                raise RuntimeError(f"Mayaが{node_type}型のノードを作成しませんでした")
            return Node(name)
        return Node._connect_joint_parent(Node(created), parent, fast=False)

    @staticmethod
    def _connect_joint_parent(node, parent, *, fast):
        """jointの下へ作ったjointの inverseScale へ、親の scale を接続する(``cmds.joint`` と同じ)。

        Args:
            node (Node): 作成したノード。
            parent (str | None): 作成時に指定した親の完全パス。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            Node: node。jointでない、または親がjointでない場合は何もしない。
        """
        if parent is None or not node.mnode().hasFn(om2.MFn.kJoint):
            return node
        parent_node = node.getParent()
        if parent_node is not None and parent_node.mnode().hasFn(om2.MFn.kJoint):
            node.connectInverseScale(parent_node, fast=fast)
        return node

    def _has_delete_connections(self):
        """自身とDAG子孫のDG接続をOMで検査する。

        Returns:
            bool: 接続が一つでもあればTrue。DAG階層関係自体は接続に数えない。
        """
        pending, seen = [self.mnode()], set()
        while pending:
            obj = pending.pop()
            fn = om2.MFnDependencyNode(obj)
            key = fn.uuid().asString()
            if key in seen:
                continue
            seen.add(key)
            if len(fn.getConnections()):
                return True
            if obj.hasFn(om2.MFn.kDagNode):
                dag = om2.MFnDagNode(obj)
                pending.extend(dag.child(i) for i in range(dag.childCount()))
        return False

    @staticmethod
    def _selection_owner(selection, index, name=None, plug=False):
        """MSelectionList の要素を所有するノードの MObject と DAG パスを返す。

        ノード・コンポーネントの要素は選択されたインスタンスの DAG パスを返す。
        アトリビュート(プラグ)の要素は ``MSelectionList.getDagPath()`` を使えず、選択リスト自体も
        インスタンスの情報を持たないため、インスタンス化された DAG ノードのアトリビュートは
        次の順にノード部分からインスタンスのパスを求める。

        1. name(要素を追加したときの文字列)。``|grpB|box1|boxShape.castsShadows`` は
           ``|grpB|box1|boxShape`` のインスタンスを指す。
        2. 選択文字列。``worldMatrix[1]`` のようなインスタンスごとのアトリビュートは、要素番号の
           インスタンスが選択文字列に現れる。

        ``|box1.castsShadows`` のように transform の名前でシェイプのアトリビュートを指す文字列は、
        ノード部分が指す transform のパスを所有シェイプまで伸ばす(``|box1|boxShape``)。
        どちらからも求められない場合は最初のインスタンスのパスを返す。

        Args:
            selection (om2.MSelectionList): 対象を含む選択リスト。
            index (int): 要素の位置。
            name (str | None): 要素を追加したときの文字列。分かっている場合に指定する。
            plug (bool): 要素がアトリビュート(``getPlug`` で取得できる要素)と分かっている場合は True。
                インスタンス化されていない DAG ノードはパスが1つだけなので、失敗すると分かっている
                ``getDagPath()`` の例外処理を省いてそのパスを返す(結果は False の場合と同じ)。

        Returns:
            tuple[om2.MObject, om2.MDagPath | None]: 所有ノードの MObject と、DAG ノードで
                あれば DAG パス(DG ノードは None)。
        """
        mobject = selection.getDependNode(index)
        if not mobject.hasFn(om2.MFn.kDagNode):
            return mobject, None
        fn = None
        if plug:
            fn = om2.MFnDagNode(mobject)
            if not fn.isInstanced():
                return mobject, fn.getPath()
        try:
            return mobject, selection.getDagPath(index)
        except (RuntimeError, TypeError):
            pass
        if fn is None:
            fn = om2.MFnDagNode(mobject)
        if fn.isInstanced():
            candidates = [name] if name else []
            candidates.extend(selection.getSelectionStrings(index))
            for text in candidates:
                # ノード名には "." を含められないため、最初の "." までがノード部分になる。
                owner = om2.MSelectionList()
                try:
                    owner.add(text.split(".", 1)[0])
                    dag_path = owner.getDagPath(0)
                except (RuntimeError, TypeError):
                    continue
                if dag_path.node() == mobject:
                    return mobject, dag_path
                # transform の名前でシェイプのアトリビュートを指す場合は、名前が指す transform の
                # インスタンスの下にある所有シェイプまでパスを伸ばす。
                for child in range(dag_path.childCount()):
                    if dag_path.child(child) == mobject:
                        dag_path.push(mobject)
                        return mobject, dag_path
        return mobject, fn.getPath()

    @staticmethod
    def _unique_node_name(mobject):
        """ノードの MObject から maya.cmds で一意に解決できる最短名を返す。

        DAG ノードは最初のインスタンスの最短一意パス(``MDagPath.partialPathName()``)、
        DG ノードはノード名を返す。``Node.getName()`` と同じ規則。

        Args:
            mobject (om2.MObject): 依存ノードの MObject。

        Returns:
            str: 最短一意名。
        """
        if mobject.hasFn(om2.MFn.kDagNode):
            return om2.MFnDagNode(mobject).getPath().partialPathName()
        return om2.MFnDependencyNode(mobject).name()

    @staticmethod
    def _mobject_name(mobject):
        """依存ノードの MObject を完全 DAG パスまたは DG ノード名へ変換する。

        Args:
            mobject (om2.MObject): 変換対象。

        Returns:
            str: 完全 DAG パス(最初のインスタンス)、または DG ノード名。

        Raises:
            TypeError: アトリビュート・コンポーネント・データなど依存ノード以外を指す場合。
            ValueError: 空、または削除済みノードの MObject の場合。
        """
        if mobject.isNull():
            raise ValueError("MObjectにnullは指定できません")
        if not om2.MObjectHandle(mobject).isValid():
            raise ValueError("削除されたノードのMObjectは指定できません")
        if not mobject.hasFn(om2.MFn.kDependencyNode):
            raise TypeError("MObjectはディペンデンシーノードで指定してください(アトリビュート・コンポーネント・データは指定できません)")
        if mobject.hasFn(om2.MFn.kDagNode):
            return om2.MFnDagNode(mobject).getPath().fullPathName()
        return om2.MFnDependencyNode(mobject).name()

    @staticmethod
    def _resolve_input(value):
        """対象を Node インスタンスへ変換する。

        Plug・MPlug は所有ノード、Component・Components は所有シェイプへ解決する。

        Args:
            value (Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
                変換対象。

        Returns:
            Node: value が Node ならそのまま、Plug なら ``plug.getNode()``、コンポーネントなら
                ``shape``。それ以外は ``Node(value)`` (Mayaで解決し、型に合ったクラスのオブジェクトを返す)。
                削除済みの Node と、所有ノードが削除済みの Plug・Component は例外にせずそのまま
                返す(``Node.isValid()`` が ``False``。扱いは呼び出し側で決める)。

        Raises:
            TypeError: 対応しない型の場合。
            ValueError: 所有ノードは有効で、アトリビュートが ``deleteAttr`` で削除済みの Plug・MPlug の場合
                (:class:`DeletedAttributeError`。``RuntimeError`` の派生でもある)。
            RuntimeError: 名前を解決できない(存在しない、または複数のノードに一致する)場合、
                または空・削除済みのノードを指す om2 オブジェクトの場合(``Node(value)`` と同じ)。
        """
        if isinstance(value, Node):
            return value
        if isinstance(value, str):
            # Node(value) と同じ解決・型選択を、生成の入口の再判定なしで行う。
            return Node._wrap_resolved(*_resolve_node(value))
        # 循環importを避け、入力型の判定に使う参照型をここで取得する(Node・名前の分岐では使わない)。
        from ..components.component import Component, Components
        from ..plugs.plug import Plug

        if isinstance(value, Plug):
            error = Plug._deleted_attribute_error(value)
            if error is not None:
                raise error
            return value.getNode()
        if isinstance(value, (Component, Components)):
            return value.shape
        if isinstance(value, (om2.MObject, om2.MDagPath, om2.MPlug)):
            return Node(value)
        raise Object._unsupported(value)

    @staticmethod
    def _input_name(value):
        """ノードが必要な単一の引数(``parent`` など)を、所有ノードの完全パスへ変換する。

        Node._resolve_input と同じ規則で解決する(Plug・MPlug は所有ノード、Component は所有シェイプ)。
        ``"node.attribute"`` 形式の文字列も所有ノードになるため、maya.cmds のように
        プラグ名の ``parent`` が黙って無視されることはない。

        Args:
            value (str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug): 変換対象。

        Returns:
            str: 所有ノードの完全 DAG パス(DG ノードはノード名)。

        Raises:
            TypeError: 対応しない型、または Components などの複数の対象を渡した場合。
            ValueError: 空文字列、または無効な(削除済みの。アトリビュートだけが削除された Plug・MPlug を
                含む)対象の場合。
            RuntimeError: 文字列を解決できない(存在しない、または複数のノードに一致する)場合。
        """
        # 型と有効性の検査は Object._input_name と同じ規則(TypeError / ValueError)にそろえる。
        Object._input_name(value)
        return Node._resolve_input(value).getFullName()

    def _resolve(self, node):
        """ノードを表す入力を内部 API オブジェクトへ変換する。

        Args:
            node (str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug):
                対象ノードを表す入力(_resolve_node と同じ)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対応しないノード入力型の場合。
            ValueError: アトリビュートが ``deleteAttr`` で削除済みの Plug・MPlug の場合
                (``DeletedAttributeError``。RuntimeError の派生でもある)。
            RuntimeError: ノード名を解決できない場合。
        """
        self._mobject, self._dag_path = _resolve_node(node)
        # 有効性の判定は名前の取得のたびに行うため、ハンドルは一度だけ作って再利用する。
        self._handle = om2.MObjectHandle(self._mobject)
        self._identity_hash = self._handle.hashCode()
        self._fn_cache = None

    def _alive_fn(self):
        """破棄されていないことを確かめて、保持するノードの MFnDependencyNode を返す。

        Undo の記録から消えて破棄されたノード(削除後の flushUndo 等)へ関数セットを作ると
        Maya が異常終了するため、その前に RuntimeError にする。Undo で戻せる削除済みノード
        (生存中)は従来どおり問い合わせる。

        Returns:
            om2.MFnDependencyNode: このノードの関数セット。

        Raises:
            RuntimeError: ノードが破棄されている場合。
        """
        handle = self._handle
        if handle is None or not handle.isAlive():
            raise RuntimeError("無効なノードは使えません")
        return om2.MFnDependencyNode(self._mobject)

    def _dependency_fn(self):
        """保持するノードの MFnDependencyNode を返す(作成は初回の1回だけ)。

        名前・アトリビュートの問い合わせのたびに関数セットを作り直さないためのキャッシュ。
        ノードが有効(:meth:`isValid`)であることを呼び出し側で確かめてから使う。

        Returns:
            om2.MFnDependencyNode: このノードの関数セット。
        """
        fn = self._fn_cache
        if fn is None:
            fn = self._fn_cache = om2.MFnDependencyNode(self._mobject)
        return fn

    @staticmethod
    def _wrap_dag_path(dag_path):
        """呼出し元が作った有効なMDagPathを、名前や入力を解決し直さずにオブジェクトにする。

        ``Node(dag_path)`` と同じ型選択(nodeTypeの登録、無ければMaya継承に沿って生成したクラス)と
        初期化を行い、入力の種類判定・MDagPathの複製だけを省く。パスが無効なら ``Node(dag_path)`` と
        同じ例外を送出する。子・親の列挙のように、API で直前に取得・延長・短縮したパスにだけ使う。

        Args:
            dag_path (om2.MDagPath): 有効なDAGパス。作るオブジェクトがそのまま持つため、
                呼出し元は以後このオブジェクトを変更しない。

        Returns:
            DagNode: 実際のノードの型に合ったクラスのオブジェクト。
        """
        # アンダーワールドの根を指すパスなど、延長・短縮の結果が無効な場合は Node(...) と同じ例外にする。
        if not dag_path.isValid():
            return Node(dag_path)
        mobject = dag_path.node()
        handle = om2.MObjectHandle(mobject)
        if not handle.isValid():
            return Node(dag_path)
        # 有効性を確かめたハンドルは、ラッパーが保持するハンドルとしてそのまま使う。
        return Node._wrap_resolved(mobject, dag_path, handle)

    @staticmethod
    def _wrap_resolved(mobject, dag_path, handle=None):
        """APIで直前に解決した有効なMObjectとDAGパスを、入力を解決し直さずにオブジェクトにする。

        ``Node(dag_path)``・``Node(mobject)`` と同じ型選択(nodeTypeの登録、無ければMaya継承に沿って生成したクラス)と
        初期化(選んだクラスの ``__init__``)を行い、入力の種類判定・有効性検査・複製だけを省く。
        ``_resolve_node`` の戻り値や、``MSelectionList``・``MItDag`` 等から取得したばかりの値にだけ使う。

        Args:
            mobject (om2.MObject): 有効な依存ノードの MObject。DAG ノードでは ``dag_path.node()`` と同じノード。
            dag_path (om2.MDagPath | None): DAG ノードの有効なパス。DG ノードは None。
                作るオブジェクトがそのまま持つため、呼出し元は以後これらのオブジェクトを変更しない。
            handle (om2.MObjectHandle | None): 呼出し元が mobject から作ったハンドル。指定すると
                作るオブジェクトが持つハンドルとして使い、作り直さない。

        Returns:
            Node: 実際のノードの型に合ったクラスのオブジェクト。
        """
        registry = Node._registry
        if registry is None:
            return Node(dag_path if dag_path is not None else mobject)
        resolved_class = registry.wrapper_class(_node_type_name(mobject))
        instance = object.__new__(resolved_class)
        if resolved_class.__init__ is Node.__init__:
            # __init__ を上書きしないクラスでは、Node.__init__ の解決済み入力の分岐と同じ属性を直接設定する。
            if handle is None:
                handle = om2.MObjectHandle(mobject)
            instance.__dict__.update(_mobject=mobject, _dag_path=dag_path, _handle=handle, _identity_hash=handle.hashCode())
            return instance
        instance._pending_resolution = (mobject, dag_path)
        instance.__init__(dag_path if dag_path is not None else mobject)
        return instance

    @staticmethod
    def _from_name(value):
        """ノードを表す入力を解決し、``Node(value)`` と同じクラスの選び方でオブジェクトにする。

        ``Node._wrap_resolved(*_resolve_node(value))`` の短縮。生成の入口(``Node.__new__``)の
        再判定を省くため、cmds・common のように解決済みの名前・MObject を多数ラップする側で使う。

        Args:
            value (str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug):
                ``_resolve_node`` が受け付ける入力。

        Returns:
            Node: 実際のノードの型に合ったクラスのオブジェクト。

        Raises:
            TypeError: 対応しない入力型の場合。
            RuntimeError: 名前を解決できない、または無効な参照の場合。
        """
        return Node._wrap_resolved(*_resolve_node(value))

    def _require_named(self):
        """名前の取得の前にノードが有効か確かめる。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが削除済み、またはUndoで作成が取り消された場合。
        """
        handle = self._handle
        if handle is None or not handle.isValid():
            raise RuntimeError(f"{type(self).__name__}は削除されたか、Undoで取り消されました。使う前にisValid()で確かめてください")

    def _require_valid(self, action):
        """操作の前にノードが有効か確かめ、無効なら統一した文言で拒否する。

        Args:
            action (str): 例外メッセージに使う動作の名詞句(``"名前の変更"``・``"削除"`` 等)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが削除済み・無効な場合。文言は
                ``無効な<クラス名>のため、<action>はできません``。
        """
        if not self.isValid():
            raise RuntimeError(f"無効な{type(self).__name__}のため、{action}はできません")

    def _current_dag_path(self):
        """このオブジェクトが持つDAGパスを返す。消えたインスタンスを、別のパスへ切り替えない。

        ノードごと削除された場合は、Undoの記録に残る間(MDagPathが有効のまま古いパスを返す間)も
        無効として扱う。

        Returns:
            om2.MDagPath | None: 保持しているパス。非DAGはNone。

        Raises:
            RuntimeError: 保持しているDAGインスタンス、またはノード自体が削除された場合。
        """
        dag_path = self._dag_path
        if dag_path is not None:
            if not dag_path.isValid():
                raise RuntimeError("参照していたDAGのインスタンスはすでに存在しません")
            handle = self._handle
            if handle is not None and not handle.isValid():
                # 削除直後のMDagPathはisValid()がTrueのまま空のパス・削除前の名前を返すため、
                # ノードのハンドルでも確かめる。
                raise RuntimeError("参照していたDAGノードはすでに存在しません")
        return dag_path

    @staticmethod
    def _prepare_extra_attr_definition(
        flags, attribute_type, child_names, child_short_names, child_suffixes, *, sub_type=None, angle_unit="rad", time_unit="frame"
    ):
        """追加する型・子数・既定値と単位を、Mayaへの書込み前に解決する。

        Args:
            flags (dict): 正規化済みフラグ。型と単位をこの辞書へ反映する。
            attribute_type (str | None): 明示された型。
            child_names (Sequence[str] | None): 子のロング名。
            child_short_names (Sequence[str] | None): 子のショート名。
            child_suffixes (Sequence[str] | None): 子名の接尾辞。
            sub_type (str | None): 自動生成する子の共通型。doubleAngleなら子の値をradへ換算する。
            angle_unit (str): 角度の数値の単位(``"deg"`` / ``"rad"``)。
            time_unit (str): 時間の数値の単位(``"frame"`` / ``"sec"``)。

        Returns:
            tuple: 数値のコンパウンドアトリビュートの一致情報・子数・作成後に設定する既定値。
        """
        if attribute_type is not None:
            flags.pop("attributeType", None)
            flags.pop("dataType", None)
            prefix, separator, kind = attribute_type.partition(":")
            if separator:
                if prefix not in ("at", "dt"):
                    raise ValueError("型にはat:かdt:の接頭辞を付けてください")
                key = "attributeType" if prefix == "at" else "dataType"
            else:
                kind = attribute_type
                key = (
                    "dataType"
                    if kind
                    in {
                        "string",
                        "matrix",
                        "stringArray",
                        "doubleArray",
                        "floatArray",
                        "Int32Array",
                        "Int64Array",
                        "vectorArray",
                        "floatVectorArray",
                        "pointArray",
                        "matrixArray",
                        "mesh",
                        "nurbsCurve",
                        "nurbsSurface",
                        "lattice",
                        "componentList",
                        "polyFaces",
                        "reflectanceRGB",
                        "spectrumRGB",
                    }
                    else "attributeType"
                )
            flags[key] = kind
        elif not (flags.get("attributeType") or flags.get("dataType")):
            flags["attributeType"] = "double"
        if flags.get("attributeType") and flags.get("dataType"):
            raise ValueError("attributeTypeとdataTypeは同時に指定できません")
        kind = flags.get("attributeType")
        numeric = re.fullmatch(r"(double|float|long|short)([234])", kind or "")
        count = int(numeric.group(2)) if numeric else 0
        if kind == "compound" and (child_names or child_short_names or child_suffixes):
            count = flags.get("numberOfChildren") or len(child_names or child_short_names or child_suffixes)
            flags["numberOfChildren"] = count
        if numeric:
            # 固定子数型へncを渡すMayaエラーを事前検出する。
            if "numberOfChildren" in flags and flags.pop("numberOfChildren") != count:
                raise ValueError("ベクトルの子の数が型と合っていません")
        if kind == "enum" and isinstance(flags.get("defaultValue"), str):
            flags["defaultValue"] = _enum_field_value(flags.get("enumName"), flags["defaultValue"])
        deferred = None
        if count or flags.get("dataType"):
            deferred = flags.pop("defaultValue", None)
        if count and sub_type == "doubleAngle" and angle_unit != "rad":
            # 角度の子へ配る範囲・既定値をここで一度だけradへ換算し、子のaddAttrにはunit="rad"で渡す。
            def to_radians(value):
                """数値・数値列の角度をradへ換算する。単位付きの値はそのまま返す。"""
                if isinstance(value, (tuple, list)):
                    return type(value)(to_radians(item) for item in value)
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    return om2.MAngle(value, om2.MAngle.kDegrees).asRadians()
                return value

            for flag in ("minValue", "maxValue", "softMinValue", "softMaxValue"):
                if flag in flags:
                    flags[flag] = to_radians(flags[flag])
            deferred = to_radians(deferred)
        angle_input = om2.MAngle.kDegrees if angle_unit == "deg" else om2.MAngle.kRadians
        time_input = om2.MTime.uiUnit() if time_unit == "frame" else om2.MTime.kSeconds
        unit = {
            "doubleAngle": (om2.MAngle, om2.MAngle.kRadians),
            "doubleLinear": (om2.MDistance, om2.MDistance.kCentimeters),
            "time": (om2.MTime, om2.MTime.kSeconds),
        }.get(kind)
        if unit:
            cls, internal = unit
            for flag in ("defaultValue", "minValue", "maxValue", "softMinValue", "softMaxValue"):
                if flag in flags:
                    value = flags[flag]
                    source = {om2.MAngle: angle_input, om2.MTime: time_input}.get(cls, internal)
                    quantity = value if isinstance(value, cls) else cls(value, source)
                    flags[flag] = quantity.asUnits(cls.uiUnit() if cls is om2.MTime else internal)
        return numeric, count, deferred

    def _create_extra_attr_definition(
        self, name, flags, numeric, count, deferred, child_names, child_short_names, child_suffixes, sub_type, *, fast=False, time_unit="frame"
    ):
        """親と子の定義を従来の順序で追加する。

        通常は子を公開addAttrへ順に委譲する。fastは未登録の親子定義を一括構築して追加する。

        Args:
            name (str): 親アトリビュート名。
            flags (dict): 親へ渡すフラグ。子用の範囲値を取り出す。
            numeric (object): 数値のコンパウンドアトリビュートの一致情報。
            count (int): 子数。
            deferred (object): 子に渡す既定値。
            child_names (Sequence[str] | None): 子のロング名。
            child_short_names (Sequence[str] | None): 子のショート名。
            child_suffixes (Sequence[str] | None): 子名の接尾辞。
            sub_type (str | None): 子の型。
            fast (bool): Trueなら定義をOpenMayaで追加する。
            time_unit (str): 時間の子の数値の単位(``"frame"`` / ``"sec"``)。子のaddAttrへ渡す。
        """
        # 循環参照の回避: core は nodes を参照するため、使う時点で読み込む。
        from ..core.attributeEdit import extra_children, validate_extra_attribute

        children = extra_children(
            name,
            flags,
            numeric,
            count,
            deferred=deferred,
            child_names=child_names,
            child_short_names=child_short_names,
            child_suffixes=child_suffixes,
            sub_type=sub_type,
        )
        validate_extra_attribute(self, name, flags, count, deferred, children, validate_defaults=not fast)
        if fast:
            # 循環参照の回避: core は nodes を参照するため、使う時点で読み込む。
            from ..core.attributeEdit import create_extra_attribute

            return create_extra_attribute(
                self,
                name,
                flags,
                numeric,
                count,
                deferred=deferred,
                child_names=child_names,
                child_short_names=child_short_names,
                child_suffixes=child_suffixes,
                sub_type=sub_type,
            )
        if count:
            # 子の範囲・既定値は子へ指定し、親には渡さない。
            for key in ("minValue", "maxValue", "softMinValue", "softMaxValue"):
                flags.pop(key, None)
            cmds.addAttr(self.getFullName(), **flags)
            for child_name, child_type, child_flags in children:
                # 角度の子の値は_prepare_extra_attr_definitionでrad換算済み。時間の子は親と同じ単位で渡す。
                self.addAttr(child_name, child_type, getPlug=False, fast=fast, unit="rad", timeUnit=time_unit, **child_flags)
        else:
            cmds.addAttr(self.getFullName(), **flags)
        # 通常経路はcmdsが値まで設定するため、呼出し側へ渡すものはない。
        return None

    def _listed_attributes(self, include_children=True, keyable=False, scalar=False):
        """``cmds.listAttr`` と同じ順で、getPlugs() が返すアトリビュート定義を列挙する。

        トップレベルの定義を定義順に辿り、マルチアトリビュートでないコンパウンドアトリビュートは子を親の直後へ深さ優先で並べる
        (マルチアトリビュートであるコンパウンドアトリビュートの子は、番号の無い名前を Plug にできないため listAttr の結果からも除かれる)。

        Args:
            include_children (bool): Falseならトップレベルの定義だけを返す。
            keyable (bool): Trueならプラグがkeyableのものだけ(``listAttr(keyable=True)``)。
            scalar (bool): Trueなら単一成分の数値・単位・enumだけ(``listAttr(scalar=True)``)。

        Returns:
            list[om2.MObject]: アトリビュート定義。マルチアトリビュートの要素の取得・作成は行わない。
        """
        fn = self._dependency_fn()
        ordered = []

        def visit(attribute):
            """定義を追加し、マルチアトリビュートでないコンパウンドアトリビュートなら子を続けて追加する。"""
            ordered.append(attribute)
            if include_children and attribute.hasFn(om2.MFn.kCompoundAttribute) and not om2.MFnAttribute(attribute).array:
                compound = om2.MFnCompoundAttribute(attribute)
                for index in range(compound.numChildren()):
                    visit(compound.child(index))

        for index in range(fn.attributeCount()):
            attribute = fn.attribute(index)
            if om2.MFnAttribute(attribute).parent.isNull():
                visit(attribute)
        if keyable:
            # 定義でなくプラグのkeyable(Shapeのvisibility等はノードが上書きする)で判定する。
            ordered = [attribute for attribute in ordered if om2.MPlug(self._mobject, attribute).isKeyable]
        if scalar:
            ordered = [attribute for attribute in ordered if _scalar_attribute(attribute)]
        return ordered

    def _user_attributes(self, include_children=False):
        """動的アトリビュートの定義を追加順に列挙する。

        Args:
            include_children (bool): Trueならコンパウンドアトリビュートの子の定義も含める。

        Yields:
            om2.MObject: アトリビュート定義。マルチアトリビュートの要素の取得・作成は行わない。
        """
        fn = self._dependency_fn()
        # 静的・拡張アトリビュートはattributeClassで先に除き、MFnAttributeの作成を動的なものだけにする。
        # kLocalDynamicAttrはMFnAttribute.dynamicがTrueのものと同じで、列挙の順序も変えない。
        local_dynamic = om2.MFnDependencyNode.kLocalDynamicAttr
        for index in range(fn.attributeCount()):
            attribute = fn.attribute(index)
            if fn.attributeClass(attribute) != local_dynamic:
                continue
            definition = om2.MFnAttribute(attribute)
            if definition.dynamic and (include_children or definition.parent.isNull()):
                yield attribute


class Nodes:
    """複数のノードを、渡した順にまとめて持つクラス。

    要素の型は、まとめるときに確かめる。

    - 同じノードで同じDAGパスのものだけを1つにまとめる。インスタンスのパスが違えば別の要素として持つ。
    - コピーやスライスは、同じNodeのオブジェクトを共有する。シーンのノードは複製しない。
    - ``len``・番号での取り出し(sliceなら同じ型)・``for``・``bool``・``+``・``==``・:meth:`sort` が使える。
    - そのまま ``maya.cmds`` へ渡せる(cmdsが並びとして、各ノードの名前へ展開する)。
    - ``==`` を定義しているので、listと同じくハッシュできない(dictのキーやsetの要素にできない)。

    ``item_class`` は、派生のクラス(:class:`~mlib.nodes.joint.Joints` など)が受け付ける要素の型を
    宣言するクラス属性。
    """

    item_class = Node
    __hash__ = None  # type: ignore[assignment]

    def __init__(self, names=()):
        """入力からノードを解決し、要素の型を確かめてから持つ。

        Args:
            names (object | Iterable[object]): 名前・Node・APIのオブジェクトなど、またはその並び。
                名前を1つだけ渡してもよい。

        Raises:
            TypeError: 解決したノードがitem_classの派生でない場合。
            ValueError: 入力を解決するときに、不正なものが見つかった場合。
            RuntimeError: 名前を解決できない場合、または無効なノードの場合。
        """
        if isinstance(names, (str, Node)):
            names = [names]
        else:
            try:
                names = iter(names)
            except TypeError:
                names = [names]
        names = Nodes._resolve_inputs(names)
        # 重複の判定は (UUID, 完全パス) の一致で行う(構築時だけ使用。以後の改名・親変更はNode参照が追跡する)。
        # 同じノードはハンドルのハッシュが等しいため、ハッシュごとに分けて、同じハッシュの要素が
        # 既にある場合だけキーを求めて比べる。完全パスの取得は階層の深さに比例して重いため、
        # 重複の無い要素では求めない。キーが一致する組は必ず同じハッシュなので結果は変わらない。
        items, buckets = [], {}
        for value in names:
            node = Node._resolve_input(value)
            if not node.isValid():
                raise RuntimeError("無効なノードは収集できません")
            if not isinstance(node, self.item_class):
                raise TypeError(f"{type(self).__name__}には{self.item_class.__name__}を指定してください: {type(node).__name__}")
            # 保持インスタンスが削除されたDAG参照は、キーを求めた場合と同じRuntimeErrorにする。
            node._current_dag_path()
            bucket = buckets.get(node._identity_hash)
            if bucket is None:
                buckets[node._identity_hash] = [[node, None]]
                items.append(node)
                continue
            key = Nodes._duplicate_key(node)
            for entry in bucket:
                if entry[1] is None:
                    entry[1] = Nodes._duplicate_key(entry[0])
                if entry[1] == key:
                    break
            else:
                bucket.append([node, key])
                items.append(node)
        self._items = items

    def __iter__(self):
        """要素を順に返す。

        Returns:
            Iterator: 要素を持っている順に返すイテレータ。
        """
        return iter(self._items)

    def __len__(self):
        """要素の数を返す。

        Returns:
            int: 要素の数。
        """
        return len(self._items)

    def __getitem__(self, index):
        """番号で要素を取り出す。

        intならNodeを、sliceなら同じ型の新しいまとまりを返す。取り出したNodeは、元と同じオブジェクト。
        シーンで探し直したり、有効かどうかを確かめ直したりはしない。まとめた後で削除されたノードもそのまま持つ。

        Args:
            index (int | slice): Pythonのlistと同じ番号。負の数とboolも、listと同じ決まりで扱う。

        Returns:
            Node | Nodes: 同じNodeのオブジェクト、または同じNodeを共有する新しいまとまり。
        """
        if not isinstance(index, slice):
            return self._items[index]
        result = self.copy()
        result._items = self._items[index]
        return result

    def __repr__(self):
        """クラス名と要素を表す文字列を返す。

        Returns:
            str: クラス名と、持っている要素を表す文字列。
        """
        return f"{type(self).__name__}({self._items!r})"

    def __eq__(self, other):
        """同じ並びのノードを持っているか比べる。

        Args:
            other (Nodes | list | tuple): 比べる相手。Nodesの派生の型の違いは問わない。

        Returns:
            bool: 要素の数が同じで、同じ位置のNodeどうしが ``==`` で等しければTrue。
                対応していない型ならNotImplemented。
        """
        if not isinstance(other, (Nodes, list, tuple)):
            return NotImplemented
        others = other._items if isinstance(other, Nodes) else other
        return len(self._items) == len(others) and all(a == b for a, b in zip(self._items, others))

    def __class_getitem__(cls, item):
        """型注釈の ``Nodes[Transform]`` を、実行時にも書けるようにする。

        クラス自身を返す。型スタブでは ``Nodes`` が要素の型を受け取り、``mlib.ls(type="transform")[0]`` を
        ``Transform`` として補完する。実行時には要素の型を確かめない。

        Args:
            item (object): 要素の型。

        Returns:
            type: クラス自身。
        """
        return cls

    def __getattr__(self, name):
        """1つのノードのメソッドを、すべての要素へ呼ぶ関数として取得する。

        このクラスに無い公開メソッドの名前(``setTranslation`` など)を取得すると、関数が返る。
        その関数は、各要素の同じ名前のメソッドを同じ引数で順に呼び、戻り値を同じ順のリストで返す
        (:meth:`callEach` と同じ)。

        - 呼ぶ前に、すべての要素がそのメソッドを持ち、有効であることを確かめる。
        - 通常は1回のUndoにまとめる。``fast=True`` は、そのまま各メソッドへ渡す。
        - 要素が無いときは ``item_class`` のメソッドの名前を受け付け、空のリストを返す。

        Args:
            name (str): 1つのノードの公開メソッドの名前。

        Returns:
            Callable[..., list]: 各要素のメソッドを呼び、戻り値を要素の順のリストで返す関数。

        Raises:
            AttributeError: ``_`` で始まる名前の場合、またはどの要素(空なら ``item_class``)も持たないメソッドの名前の場合。
        """
        items = self.__dict__.get("_items")
        classes = [type(node) for node in items] if items else [self.item_class]
        if name.startswith("_") or items is None or not any(callable(getattr(cls, name, None)) for cls in classes):
            raise AttributeError(f"{type(self).__name__!r}オブジェクトにアトリビュート{name!r}はありません")

        def forward(*args, **kwargs):
            fast = kwargs.pop("fast", None)
            return self._forward(name, args, fast, **kwargs)

        forward.__name__ = name
        forward.__qualname__ = f"{type(self).__name__}.{name}"
        forward.__doc__ = f"各要素の {name}() を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"
        return forward

    def __add__(self, other):
        """後ろへほかのNodes・list・tupleをつないだ、新しいまとまりを返す。

        返すまとまりの型は左辺と同じ。入力は作るときと同じ決まりで解決し、重なり(同じノードで
        同じDAGパス)は先に出てきたほうを残す。要素の型も、作るときと同じく確かめる
        (``Joints + [transform]`` はTypeError)。相手の並びは単独で解決するので、``nodes + ["name"]`` のように
        名前の並びもつなげる(相手の並びの中で名前とNodeを混ぜると、作るときと同じくTypeError)。

        Args:
            other (Nodes | list | tuple): 後ろへつなぐ並び。名前・Nodeなどの並び。

        Returns:
            Nodes: 左辺と同じ型の新しいまとまり。自身と相手は変更しない。

        Raises:
            TypeError: 相手が対応していない型の場合、または要素の型が合わない場合。
            RuntimeError: 解決できないものか、無効なノードを含む場合。
        """
        if not isinstance(other, (Nodes, list, tuple)):
            return NotImplemented
        return type(self)(self._items + Nodes._items_of(other))

    def __radd__(self, other):
        """``list + Nodes`` のように、左辺がlist・tupleのときにつないだ新しいまとまりを返す。

        返すまとまりの型は右辺(自身)と同じ。

        Args:
            other (list | tuple): 前へつなぐ並び。

        Returns:
            Nodes: 右辺(自身)と同じ型の新しいまとまり。

        Raises:
            TypeError: 相手が対応していない型の場合、または要素の型が合わない場合。
            RuntimeError: 解決できないものか、無効なノードを含む場合。
        """
        if not isinstance(other, (list, tuple)):
            return NotImplemented
        return type(self)(Nodes._items_of(other) + self._items)

    def sort(self, key=None, reverse=False):
        """要素をその場で並べ替える。

        ``key`` を省くと、ノードの完全な名前(:meth:`Node.getFullName`)の順にする。
        Nodeは大小を比べられないため、Pythonのlistと違い、要素そのものは比べない。
        並べ替えるのはこのまとまりの要素の順だけ。:meth:`copy`・スライス・``+`` で作った
        別のまとまりの順は変わらない(各要素のNodeのオブジェクトは共有している)。

        Args:
            key (Callable[[Node], object] | None): 各Nodeから、比べるための値を返す関数。Noneなら完全な名前。
            reverse (bool): Trueなら大きい順にする。既定はFalse。

        Returns:
            Nodes: 並べ替えた自身(新しいまとまりは作らない)。

        Raises:
            TypeError: keyが呼び出せないものの場合、またはreverseがbool以外の場合。
            RuntimeError: keyを省いたときに、無効なノードを含む場合。
        """
        _require_bool(reverse, "reverse")
        if key is not None and not callable(key):
            raise TypeError("keyは呼び出せるオブジェクトかNoneで指定してください")
        if key is None:
            for node in self._items:
                node._require_valid("並べ替え")
            key = methodcaller("getFullName")
        self._items.sort(key=key, reverse=reverse)
        return self

    def setAttrFlags(self, attributes, locked=None, keyable=None, channelBox=None, *, fast=False):
        """各ノードへ、順に :meth:`Node.setAttrFlags` を呼ぶ。

        このクラスでまとめて書き込めるメソッドは、:meth:`setAttrFlags`・:meth:`resetAttrs`・:meth:`setLocked`・
        :meth:`setOverrideColor`・:meth:`setOutlinerColor`・:meth:`setVisibility`・:meth:`show`・:meth:`hide`・:meth:`setParent`
        (:class:`~mlib.nodes.joint.Joints` では ``setRadius``・``setSegmentScaleCompensate`` も)。
        通常は全体を1回のUndoにまとめる。書き込む前に、すべての要素がメソッドを持つことを確かめる。

        Args:
            attributes (str | Plug | Iterable[str | Plug]): :meth:`Node.setAttrFlags` と同じ。
                すべての要素で同じ名前のアトリビュートを使うので、Plugではなく名前で指定する。
            locked (bool | None): :meth:`Node.setAttrFlags` と同じ。
            keyable (bool | None): :meth:`Node.setAttrFlags` と同じ。
            channelBox (bool | None): :meth:`Node.setAttrFlags` と同じ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。

        Raises:
            AttributeError: :meth:`Node.setAttrFlags` と同じ。
            TypeError: :meth:`Node.setAttrFlags` と同じ。
            RuntimeError: 無効なノードを含む場合、またはMayaが変更を拒否した場合。それまでの要素の変更は
                自動では戻さない(通常はUndoで戻せる)。
        """
        self._forward("setAttrFlags", (attributes, locked, keyable, channelBox), fast)
        return self

    def resetAttrs(self, attributes=None, *, fast=False):
        """各ノードへ、順に :meth:`Node.resetAttrs` を呼ぶ。

        Args:
            attributes (str | Iterable[str] | None): :meth:`Node.resetAttrs` と同じ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            list[Plug]: すべての要素で既定値へ戻したアトリビュート(要素の順)。通常は1回のUndoにまとめる。

        Raises:
            AttributeError: :meth:`Node.resetAttrs` と同じ。
            TypeError: :meth:`Node.resetAttrs` と同じ。
            RuntimeError: 無効なノードを含む場合、またはアトリビュートを書き込めない場合。
        """
        results = self._forward("resetAttrs", (attributes,), fast)
        return [plug for plugs in results for plug in plugs]

    def setLocked(self, state=True, *, fast=False):
        """各ノードへ、順に :meth:`Node.setLocked` を呼ぶ。

        Args:
            state (bool): Trueならロック、Falseなら解除する。既定はTrue。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。

        Raises:
            TypeError: stateかfastがbool以外の場合。
            RuntimeError: 無効なノードを含む場合、またはMayaが変更を拒否した場合。
        """
        self._forward("setLocked", (state,), fast)
        return self

    def getOverrideColor(self, *, shape=False):
        """各DAGノードの :meth:`~mlib.nodes.dagNode.DagNode.getOverrideColor` を、要素の順に取得する。

        Args:
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.getOverrideColor` と同じ。既定False。

        Returns:
            list[int | tuple[float, float, float] | None]: 各ノードの描画のオーバーライドの表示色。

        Raises:
            TypeError: DAGノード以外を含む場合。
            RuntimeError: 無効なノードを含む場合。
        """
        self._require_method("getOverrideColor")
        return [node.getOverrideColor(shape=shape) for node in self._items]

    def setOverrideColor(self, color, *, shape=False, fast=False):
        """各DAGノードへ、順に :meth:`~mlib.nodes.dagNode.DagNode.setOverrideColor` を呼ぶ。

        Args:
            color (object): :meth:`~mlib.nodes.dagNode.DagNode.setOverrideColor` と同じ。
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.setOverrideColor` と同じ。既定False。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。通常は全体を1回のUndoにまとめる。

        Raises:
            TypeError: DAGノード以外を含む、色の指定が不正、またはfastがbool以外の場合。
            ValueError: 色の指定が不正な場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        self._forward("setOverrideColor", (color,), fast, shape=shape)
        return self

    def setOverrideColors(self, colors, *, shape=False, fast=False):
        """各DAGノードへ、それぞれ違う色で :meth:`~mlib.nodes.dagNode.DagNode.setOverrideColor` を呼ぶ。

        Args:
            colors (Iterable[object]): ノードと同じ数の色。要素の順に1色ずつ使う。書き込む前に、すべての色を確かめる。
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.setOverrideColor` と同じ。既定False。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。通常は全体を1回のUndoにまとめる。

        Raises:
            TypeError: DAGノード以外を含む、色の指定が不正、またはfastがbool以外の場合。
            ValueError: 色の数がノードの数と違う、または色の指定が不正な場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        self._set_each_color("setOverrideColor", colors, shape, fast)
        return self

    def getOutlinerColor(self, *, shape=False):
        """各DAGノードの :meth:`~mlib.nodes.dagNode.DagNode.getOutlinerColor` を、要素の順に取得する。

        Args:
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.getOutlinerColor` と同じ。既定False。

        Returns:
            list[tuple[float, float, float] | None]: 各ノードのアウトライナーの文字色。

        Raises:
            TypeError: DAGノード以外を含む場合。
            RuntimeError: 無効なノードを含む場合。
        """
        self._require_method("getOutlinerColor")
        return [node.getOutlinerColor(shape=shape) for node in self._items]

    def setOutlinerColor(self, color, *, shape=False, fast=False):
        """各DAGノードへ、順に :meth:`~mlib.nodes.dagNode.DagNode.setOutlinerColor` を呼ぶ。

        Args:
            color (object): :meth:`~mlib.nodes.dagNode.DagNode.setOutlinerColor` と同じ。
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.setOutlinerColor` と同じ。既定False。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。通常は全体を1回のUndoにまとめる。

        Raises:
            TypeError: DAGノード以外を含む、色の指定が不正、またはfastがbool以外の場合。
            ValueError: 色の指定が不正な場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        self._forward("setOutlinerColor", (color,), fast, shape=shape)
        return self

    def setOutlinerColors(self, colors, *, shape=False, fast=False):
        """各DAGノードへ、それぞれ違う色で :meth:`~mlib.nodes.dagNode.DagNode.setOutlinerColor` を呼ぶ。

        Args:
            colors (Iterable[object]): ノードと同じ数の色。要素の順に1色ずつ使う。書き込む前に、すべての色を確かめる。
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.setOutlinerColor` と同じ。既定False。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。通常は全体を1回のUndoにまとめる。

        Raises:
            TypeError: DAGノード以外を含む、色の指定が不正、またはfastがbool以外の場合。
            ValueError: 色の数がノードの数と違う、または色の指定が不正な場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        self._set_each_color("setOutlinerColor", colors, shape, fast)
        return self

    def setVisibility(self, state, *, fast=False):
        """各DAGノードへ、順に :meth:`~mlib.nodes.dagNode.DagNode.setVisibility` を呼ぶ。

        Args:
            state (bool): Trueなら表示、Falseなら非表示にする。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。

        Raises:
            TypeError: DAGノード以外を含む、またはstate・fastがbool以外の場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        self._forward("setVisibility", (state,), fast)
        return self

    def show(self, *, fast=False):
        """各DAGノードへ、順に :meth:`~mlib.nodes.dagNode.DagNode.show` を呼ぶ。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。

        Raises:
            TypeError: DAGノード以外を含む、またはfastがbool以外の場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        self._forward("show", (), fast)
        return self

    def hide(self, *, fast=False):
        """各DAGノードへ、順に :meth:`~mlib.nodes.dagNode.DagNode.hide` を呼ぶ。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。

        Raises:
            TypeError: DAGノード以外を含む、またはfastがbool以外の場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        self._forward("hide", (), fast)
        return self

    def setParent(self, parent=None, relative=False, add=False, *, fast=False):
        """各Transformへ、順に :meth:`~mlib.nodes.transform.Transform.setParent` を呼ぶ。

        Args:
            parent (object | None): 親。Noneならワールド。
            relative (bool): :meth:`~mlib.nodes.transform.Transform.setParent` と同じ。
            add (bool): :meth:`~mlib.nodes.transform.Transform.setParent` と同じ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Nodes: 自身。各要素は、親を変えた後のパスを指す。

        Raises:
            TypeError: Transform以外を含む場合。
            ValueError: :meth:`~mlib.nodes.transform.Transform.setParent` と同じ。
            RuntimeError: 無効なノードを含む場合、parentがどれかの要素自身かその子孫の場合、
                またはMayaが親の変更を拒否した場合。parentは、どの要素も変える前に確かめる。
        """
        if parent is not None:
            target = Node._resolve_input(parent)
            for node in self._items:
                # Transform 以外の要素は _forward が TypeError にするため、ここでは Transform だけを調べる。
                check = getattr(node, "_require_not_own_descendant", None)
                if check is not None and node.isValid() and target.isValid() and target.hasFn(om2.MFn.kTransform):
                    check(target)
        self._forward("setParent", (parent, relative, add), fast)
        return self

    def getNames(self):
        """各ノードの一意な名前を取得する(:meth:`Node.getName` を並べたもの)。

        Returns:
            list[str]: 要素の順のノード名。

        Raises:
            RuntimeError: 無効なノードを含む場合。
        """
        return [node.getName() for node in self._items]

    def select(self, **kwargs):
        """すべてのノードを一度に選択する。

        既定では今の選択を置き換え、要素の順に選択する。:func:`mlib.select` (``cmds.select``)で選択し、
        1回のUndoで戻せる。要素が無いまま置き換えると、選択が外れる(``cmds.select`` に空の並びを渡したときと同じ)。

        Args:
            **kwargs (object): ``cmds.select`` のフラグ(``add``・``deselect``・``toggle`` など。短縮名も使える)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: フラグのロング名と短縮名を同時に指定した場合。
            RuntimeError: 無効なノードを含む場合、またはMayaが選択を拒否した場合。
        """
        # cmds.selectはnodesを参照するため、循環importを避けて関数内で読み込む。
        from ..cmds.select import select

        for node in self._items:
            node._require_valid("選択")
        select(list(self._items), **kwargs)

    def callEach(self, method, *args, **kwargs):
        """各ノードの公開メソッドを、同じ引数で順に呼ぶ。

        戻り値は、要素の順のリストで返す。

        - 呼ぶ前に、すべての要素がそのメソッドを持ち、有効であることを確かめる。
        - 通常は1回のUndoにまとめる。``fast=True`` はそのまま各メソッドへ渡し、Undoはまとめない。
        - 後の要素で失敗しても、それまでの変更は自動では戻さない。
        - 要素ごとに違う引数で呼ぶときは、``for`` で1つずつ呼ぶ。

        Args:
            method (str): 1つのノードの公開メソッドの名前(``"resetAttrs"`` など)。
            *args (object): 各メソッドへ渡す位置引数。
            **kwargs (object): 各メソッドへ渡すキーワード引数。

        Returns:
            list: 要素の順の戻り値。

        Raises:
            TypeError: methodが文字列でない場合、またはそのメソッドを持たない要素を含む場合。
            ValueError: methodが空の場合、``_`` で始まる内部の名前の場合、または特殊メソッドの場合。
            RuntimeError: 無効なノードを含む場合。各メソッドの例外は、そのまま送出する。
        """
        if not isinstance(method, str):
            raise TypeError("methodはメソッド名の文字列で指定してください")
        if not method or method.startswith("_"):
            raise ValueError(f"methodは公開メソッドの名前で指定してください: {method!r}")
        fast = kwargs.pop("fast", None)
        return self._forward(method, args, fast, **kwargs)

    def copy(self):
        """同じ型の、別のまとまりを作って返す。

        要素のNodeのオブジェクトは共有する。並べ替えなどは、元のまとまりに影響しない。

        Returns:
            Nodes: 同じNodeを共有する、同じ型の新しいまとまり。
        """
        result = object.__new__(type(self))
        result.__dict__.update(self.__dict__)
        result._items = list(self._items)
        return result

    def _forward(self, method, args, fast, **kwargs):
        """保持順の各ノードへ単数のメソッドを適用し、結果の列を返す。

        全要素がメソッドを持ち有効であることを書込みの前に確かめ、通常は1回のUndoにまとめる。

        Args:
            method (str): 単数のノードのメソッド名。
            args (tuple): 位置引数。
            fast (bool | None): メソッドへ渡すfast。Noneはfast引数の無いメソッド。
            **kwargs (object): メソッドへそのまま渡すキーワード引数。

        Returns:
            list: 要素順の戻り値。

        Raises:
            TypeError: メソッドを持たない要素を含む場合、またはfastがbool以外の場合。
            RuntimeError: 無効な要素を含む場合。
        """
        self._require_method(method)
        for node in self._items:
            node._require_valid(method)
        if fast is not None:
            kwargs["fast"] = fast
        with _edit_context(f"mlib{type(self).__name__}{method[:1].upper()}{method[1:]}", bool(fast)):
            return [getattr(node, method)(*args, **kwargs) for node in self._items]

    def _require_method(self, method):
        """全要素が単数のメソッドを持つことを確かめる。

        Args:
            method (str): 単数のノードのメソッド名。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: メソッドを持たない要素を含む場合。
        """
        missing = [node for node in self._items if not callable(getattr(type(node), method, None))]
        if missing:
            raise TypeError(f"{type(self).__name__}.{method}()には、すべての要素が{method}()に対応している必要があります。{missing[0]!r}は対応していません")

    def _set_each_color(self, method, colors, shape, fast):
        """保持順の各ノードへ、対応する色で単数のメソッドを適用する。

        Args:
            method (str): 単数のノードのメソッド名。
            colors (Iterable[object]): ノードと同数の色の指定。
            shape (bool): メソッドへ渡すshape。
            fast (bool): メソッドへ渡すfast。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: DAGノード以外を含む、色の指定が不正、またはfastがbool以外の場合。
            ValueError: 色の数がノードの数と違う、または色の指定が不正な場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        _require_bool(shape, "shape")
        _require_bool(fast, "fast")
        colors = list(colors)
        if len(colors) != len(self._items):
            raise ValueError(f"{type(self).__name__}.{method}s()には色を{len(self._items)}個指定してください: {len(colors)}個")
        for color in colors:
            _color_value(color)
        self._require_method(method)
        for node in self._items:
            node._require_valid(method)
        with _edit_context(f"mlib{type(self).__name__}{method[:1].upper()}{method[1:]}s", fast):
            for node, color in zip(self._items, colors):
                getattr(node, method)(color, shape=shape, fast=fast)

    @staticmethod
    def _resolve_inputs(values):
        """対象列を一度だけ展開し、名前とNodeの混在を変換前に拒否する。

        Args:
            values (object): 単体、または対象の反復可能列。既存のAPI型も保持する。

        Returns:
            list: 入力順の対象。空列は空のまま返す。

        Raises:
            TypeError: 同じ対象列に文字列とNodeが混在している場合。
        """
        result = Object._flatten_inputs(values)
        Nodes._validate_inputs(result)
        return result

    @staticmethod
    def _items_of(values):
        """結合の相手を単独で解決し、Node参照のlistを返す。

        Args:
            values (Nodes | list | tuple): 結合の相手。

        Returns:
            list[Node]: 相手の保持順のNode参照。Nodesはそのまま、列はNodesの構築と同じ規則で解決する。
        """
        if isinstance(values, Nodes):
            return list(values._items)
        return Nodes(values)._items

    @staticmethod
    def _duplicate_key(node):
        """構築時の重複判定に使うキーを返す。

        Args:
            node (Node): 有効なノード参照。

        Returns:
            tuple[str | None, str]: UUIDと、DAGの完全パスまたはDGのノード名。
        """
        return (node.getUuid(), node.getFullName())

    @staticmethod
    def _validate_inputs(values):
        """展開済み対象列の名前とNodeの混在を拒否する。

        Args:
            values (list): Objectが展開した対象列。値の変換は行わない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 名前とNodeが混在する場合。
        """
        if any(isinstance(value, str) for value in values) and any(isinstance(value, Node) for value in values):
            raise TypeError("同じ対象の集まりに、名前とNodeオブジェクトは混ぜられません")
