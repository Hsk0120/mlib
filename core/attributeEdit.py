"""動的アトリビュートを、シーンを変える前に組み立てて、OpenMayaで追加する。"""

import maya.api.OpenMaya as om2

from .nodeEdit import require_editable

_NUMERIC_TYPES = {
    "bool": om2.MFnNumericData.kBoolean,
    "byte": om2.MFnNumericData.kByte,
    "char": om2.MFnNumericData.kChar,
    "short": om2.MFnNumericData.kShort,
    "long": om2.MFnNumericData.kInt,
    "float": om2.MFnNumericData.kFloat,
    "double": om2.MFnNumericData.kDouble,
}
_DATA_TYPES = {
    "string": om2.MFnData.kString,
    "stringArray": om2.MFnData.kStringArray,
    "doubleArray": om2.MFnData.kDoubleArray,
    "floatArray": om2.MFnData.kFloatArray,
    "Int32Array": om2.MFnData.kIntArray,
    "vectorArray": om2.MFnData.kVectorArray,
    "pointArray": om2.MFnData.kPointArray,
    "matrixArray": om2.MFnData.kMatrixArray,
    "componentList": om2.MFnData.kComponentList,
    "matrix": om2.MFnData.kMatrix,
    "mesh": om2.MFnData.kMesh,
    "nurbsCurve": om2.MFnData.kNurbsCurve,
    "nurbsSurface": om2.MFnData.kNurbsSurface,
    "lattice": om2.MFnData.kLattice,
}
_PROPERTIES = {
    "keyable": "keyable",
    "hidden": "hidden",
    "readable": "readable",
    "writable": "writable",
    "storable": "storable",
    "connectable": "connectable",
    "multi": "array",
    "indexMatters": "indexMatters",
    "cachedInternally": "cached",
    "usedAsColor": "usedAsColor",
    "usedAsFilename": "usedAsFilename",
}
_DEFINITION_FLAGS = {
    "longName",
    "shortName",
    "attributeType",
    "dataType",
    "defaultValue",
    "minValue",
    "maxValue",
    "softMinValue",
    "softMaxValue",
    "enumName",
    "niceName",
    "numberOfChildren",
    "disconnectBehaviour",
    "hasMinValue",
    "hasMaxValue",
    "hasSoftMinValue",
    "hasSoftMaxValue",
} | set(_PROPERTIES)


def _build(flags, children=None):
    """まだノードに追加していない、アトリビュートの定義を作る。

    失敗してもシーンは変えない。

    Args:
        flags (dict): 形を整えてあるaddAttrのフラグ。
        children (list[MObject] | None): 先に作った子の定義。

    Returns:
        MObject: 新しいアトリビュートの定義。

    Raises:
        ValueError: longNameとshortNameのどちらも無い場合。
        NotImplementedError: fastで扱えないフラグや型の場合。
    """
    unsupported = set(flags) - _DEFINITION_FLAGS
    if unsupported:
        raise NotImplementedError(f"fastのaddAttrは次のフラグに対応していません: {', '.join(sorted(unsupported))}")
    name = flags.get("longName") or flags.get("shortName")
    short = flags.get("shortName") or name
    if not isinstance(name, str) or not name:
        raise ValueError("longNameかshortNameを指定してください")
    kind = flags.get("attributeType", "double")
    default = flags.get("defaultValue", 0)
    if flags.get("dataType"):
        kind = flags["dataType"]
        if kind not in _DATA_TYPES:
            raise NotImplementedError(f"fastのaddAttrは次のdataTypeに対応していません: {kind}")
        fn = om2.MFnTypedAttribute()
        obj = fn.create(name, short, _DATA_TYPES[kind])
    elif kind in _NUMERIC_TYPES:
        fn = om2.MFnNumericAttribute()
        obj = fn.create(name, short, _NUMERIC_TYPES[kind], default)
    elif children and kind.startswith(("double", "float", "long", "short")):
        if len(children) not in (2, 3):
            raise NotImplementedError("fastの数値コンパウンドアトリビュートは、子が2つか3つの場合だけに対応しています")
        fn = om2.MFnNumericAttribute()
        obj = fn.create(name, short, *children)
    elif kind in ("doubleAngle", "doubleLinear", "time"):
        fn = om2.MFnUnitAttribute()
        units = {"doubleAngle": fn.kAngle, "doubleLinear": fn.kDistance, "time": fn.kTime}
        # MFnUnitAttribute.createのtime既定値も現在の時間単位で受け取る。
        # Node.addAttrが事前変換したフレーム値を再度秒へ変換しない。
        obj = fn.create(name, short, units[kind], default)
    elif kind == "enum":
        fn = om2.MFnEnumAttribute()
        obj = fn.create(name, short, int(default))
        next_value = 0
        for field in str(flags.get("enumName", "")).split(":"):
            if "=" in field:
                field, raw_value = field.rsplit("=", 1)
                next_value = int(raw_value)
            if field:
                fn.addField(field, next_value)
            next_value += 1
    elif kind == "message":
        fn = om2.MFnMessageAttribute()
        obj = fn.create(name, short)
    elif kind in ("matrix", "fltMatrix"):
        fn = om2.MFnMatrixAttribute()
        obj = fn.create(name, short, fn.kFloat if kind == "fltMatrix" else fn.kDouble)
    elif kind == "compound":
        fn = om2.MFnCompoundAttribute()
        obj = fn.create(name, short)
        for child in children or []:
            fn.addChild(child)
    else:
        raise NotImplementedError(f"fastのaddAttrは次のattributeTypeに対応していません: {kind}")
    base = om2.MFnAttribute(obj)
    for flag, property_name in _PROPERTIES.items():
        if flag in flags:
            setattr(base, property_name, bool(flags[flag]))
    if "niceName" in flags:
        base.setNiceNameOverride(str(flags["niceName"]))
    if "disconnectBehaviour" in flags:
        base.disconnectBehavior = int(flags["disconnectBehaviour"])
    if "minValue" in flags and flags.get("hasMinValue", True):
        value = flags["minValue"]
        fn.setMin(value)
    if "maxValue" in flags and flags.get("hasMaxValue", True):
        value = flags["maxValue"]
        fn.setMax(value)
    if "softMinValue" in flags and flags.get("hasSoftMinValue", True):
        value = flags["softMinValue"]
        fn.setSoftMin(value)
    if "softMaxValue" in flags and flags.get("hasSoftMaxValue", True):
        value = flags["softMaxValue"]
        fn.setSoftMax(value)
    return obj


def _attach(node, attribute):
    """作ってあるアトリビュートの定義を、ノードへ1回で追加する。

    Args:
        node (Node): 追加先のノード。
        attribute (MObject): まだシーンに追加していないアトリビュートの定義。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: ノードがロックされているかリファレンスされている場合、または同じ名前のアトリビュートがある場合。
    """
    require_editable(node.mnode())
    fn = om2.MFnDependencyNode(node.mnode())
    name = om2.MFnAttribute(attribute).name
    if fn.hasAttribute(name):
        raise RuntimeError(f"アトリビュートはすでに存在します: {name}")
    modifier = om2.MDGModifier()
    modifier.addAttribute(node.mnode(), attribute)
    modifier.doIt()


def extra_children(name, flags, numeric, count, *, deferred, child_names, child_short_names, child_suffixes, sub_type):
    """自動で作る子の名前と成分の数を、親を追加する前に確かめる。

    Args:
        name (str): 親のロング名。
        flags (dict): 親の、形を整えてあるフラグ。変更しない。
        numeric (Match | None): 数値のコンパウンドアトリビュートの型名に一致した結果。
        count (int): 子の数。
        deferred (object): 子へ割り振る既定値。
        child_names (Sequence[str] | None): 子のロング名。
        child_short_names (Sequence[str] | None): 子のショート名。
        child_suffixes (Sequence[str] | None): 自動で作る名前の末尾に付ける文字。
        sub_type (str | None): 子に共通の型。

    Returns:
        list[tuple[str, str, dict]]: 子ごとの(ロング名, 型, 公開のaddAttrへ渡すフラグ)。

    Raises:
        ValueError: 子の名前・既定値・範囲の数が、子の数と違う場合。
    """
    if not count:
        return []
    suffixes = child_suffixes or ("RGBA" if flags.get("usedAsColor") else "XYZW")[:count]
    names = list(child_names or [name + suffix for suffix in suffixes])
    shorts = list(child_short_names or [])
    if len(names) != count or (shorts and len(shorts) != count):
        raise ValueError("子の名前の数が型と合っていません")
    limits = {key: flags[key] for key in ("minValue", "maxValue", "softMinValue", "softMaxValue") if key in flags}
    for value in list(limits.values()) + [deferred]:
        if isinstance(value, (tuple, list)) and len(value) != count:
            raise ValueError("子の値の数が型と合っていません")
    children = []
    for index, child_name in enumerate(names):
        child_flags = {"parent": name, "keyable": bool(flags.get("keyable", False))}
        if shorts:
            child_flags["shortName"] = shorts[index]
        for key, value in limits.items():
            child_flags[key] = value[index] if isinstance(value, (tuple, list)) else value
        if deferred is not None:
            child_flags["defaultValue"] = deferred[index] if isinstance(deferred, (tuple, list)) else deferred
        children.append((child_name, sub_type or (numeric.group(1) if numeric else "double"), child_flags))
    return children


def validate_extra_attribute(node, name, flags, count, deferred, children, *, validate_defaults=True):
    """シーンを変える前に、追加できないアトリビュートを見つけて例外にする。

    名前の重なりと、前もって確かめられる既定値(typedの既定値など)を調べる。

    Args:
        node (Node): 追加先のノード。
        name (str): 親のロング名。
        flags (dict): 親の、形を整えてあるフラグ。
        count (int): 子の数。
        deferred (object): 作った後に設定する既定値。
        children (list[tuple[str, str, dict]]): 確かめてある、子を作るための入力。
        validate_defaults (bool): Trueなら、fastでないときの既定値も追加する前に確かめる。既定はTrue。
            fastのときは、まだ追加していない親子の定義を作るときに確かめるのでFalseにする。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: マルチアトリビュートへ直接、既定値を設定しようとした場合。
        ValueError: 名前が空文字列の場合、または文字列でない場合。
        RuntimeError: 同じ名前のアトリビュートがある場合、または書き込めない定義へ既定値を渡した場合。
    """
    names = [(name, flags.get("shortName") or name)]
    names.extend((child, options.get("shortName") or child) for child, _, options in children)
    used = set()
    fn = om2.MFnDependencyNode(node.mnode())
    for long_name, short_name in names:
        for candidate in {long_name, short_name}:
            if not isinstance(candidate, str) or not candidate:
                raise ValueError("アトリビュート名は空でない文字列で指定してください")
            if candidate in used or fn.hasAttribute(candidate):
                raise RuntimeError(f"アトリビュートはすでに存在します: {candidate}")
        used.update((long_name, short_name))
    if not validate_defaults:
        return
    for child_name, child_type, options in children:
        kind = child_type[3:] if child_type.startswith("at:") else child_type
        if kind in _NUMERIC_TYPES or kind in ("doubleAngle", "doubleLinear", "time"):
            child_flags = dict(options, longName=child_name)
            child_flags.pop("parent")
            node._prepare_extra_attr_definition(child_flags, child_type, None, None, None)
            _build(child_flags)
    if deferred is None or count:
        return
    if flags.get("multi"):
        raise TypeError("マルチアトリビュート全体ではなく、マルチアトリビュートの要素へ設定してください")
    if not flags.get("writable", True):
        raise RuntimeError(f"アトリビュートは書き込めません: {name}")
    # 通常経路で扱える型までfast専用の対応範囲へ狭めない。
    # factoryを持つ型だけ登録前に値を検査し、それ以外は既存のMaya処理へ渡す。
    data_type = flags.get("dataType")
    if data_type in {"string", "matrix", "doubleArray", "Int32Array", "stringArray", "vectorArray", "pointArray", "matrixArray"}:
        # core の初期化順に依存しないよう、使う時点で読み込む。
        from .fastWrite import prepare_data

        if data_type == "matrix":
            # 循環参照の回避: maths は core を参照するため、使う時点で読み込む。
            from ..maths import Matrix

            deferred = Matrix(deferred)
        attribute = _build({"longName": name, "dataType": data_type})
        prepare_data(attribute, deferred, name=name)


def create_extra_attribute(node, name, flags, numeric, count, *, deferred, child_names, child_short_names, child_suffixes, sub_type):
    """Node.addAttrで追加する親と子の定義を、追加する前にすべて作ってから追加する。

    Args:
        node (Node): 追加先のノード。
        name (str): 親の名前。
        flags (dict): 親のフラグ。
        numeric (Match | None): 数値のコンパウンドアトリビュートの型名に一致した結果。
        count (int): 子の数。
        deferred (object): 子の既定値。
        child_names (Sequence[str] | None): 子のロング名。
        child_short_names (Sequence[str] | None): 子のショート名。
        child_suffixes (Sequence[str] | None): 子の名前の末尾に付ける文字。
        sub_type (str | None): 子の型。

    Returns:
        tuple | None: typedの既定値を書き込む計画。確かめてあり、データを持つオブジェクトも含む。無ければNone。

    Raises:
        TypeError: マルチアトリビュートそのものへ既定値を指定した場合、または文字列型へ文字列でない値を渡した場合。
        ValueError: 子の名前・既定値・範囲の数が、子の数と違う場合。
        RuntimeError: 書き込めないアトリビュートへ既定値を指定した場合。
        NotImplementedError: 既定値をfastで構築できない型の場合。
    """
    flags = dict(flags)
    children = []
    if count:
        definitions = extra_children(
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
        for key in ("minValue", "maxValue", "softMinValue", "softMaxValue"):
            flags.pop(key, None)
        for child_name, child_type, child_flags in definitions:
            child = dict(child_flags, longName=child_name, attributeType=child_type)
            child.pop("parent")
            child.setdefault("shortName", child_name)
            children.append(_build(child))
    attribute = _build(flags, children)
    prepared = None
    if deferred is not None and not count:
        # core の初期化順に依存しないよう、使う時点で読み込む。
        from .fastWrite import prepare_data

        definition = om2.MFnAttribute(attribute)
        if definition.array:
            raise TypeError("マルチアトリビュート全体ではなく、マルチアトリビュートの要素へ設定してください")
        if not definition.writable:
            raise RuntimeError(f"アトリビュートは書き込めません: {name}")
        if (
            attribute.hasFn(om2.MFn.kMatrixAttribute)
            or attribute.hasFn(om2.MFn.kTypedAttribute)
            and om2.MFnTypedAttribute(attribute).attrType() == om2.MFnData.kMatrix
        ):
            # 循環参照の回避: maths は core を参照するため、使う時点で読み込む。
            from ..maths import Matrix

            deferred = Matrix(deferred)
        prepared = prepare_data(attribute, deferred, name=name)
    _attach(node, attribute)
    return prepared
