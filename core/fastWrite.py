"""アトリビュートの値を書き込む処理(cmdsとOpenMayaの両方)。独自プラグインは使わない。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import _require_bool
from .attributeType import NUMERIC_WRITERS, _convert_units, _require_number, _round_integer

_TYPED_DATA_FACTORIES = {
    om2.MFnData.kDoubleArray: om2.MFnDoubleArrayData,
    om2.MFnData.kIntArray: om2.MFnIntArrayData,
    om2.MFnData.kStringArray: om2.MFnStringArrayData,
    om2.MFnData.kVectorArray: om2.MFnVectorArrayData,
    om2.MFnData.kPointArray: om2.MFnPointArrayData,
    om2.MFnData.kMatrixArray: om2.MFnMatrixArrayData,
}


def require_supported_type(plug):
    """fastで書き込める型かを確かめる。

    子を持つ場合は、すべての子の定義を調べる。値と書き込めるかどうかは調べない。

    safeの部分更新の前に呼ぶ。こうすると、ロックや不正な値のエラーが先に出て、
    その後ろにある未対応の型が見えなくなるのを防げる。
    対応するデータ型(``doubleArray`` など)の表は、実際のデータを作るprepare_dataと共通にしている。

    Args:
        plug (om2.MPlug): 書き込み先。有効なことは確かめてあるもの。

    Returns:
        None: 値を返さない。

    Raises:
        NotImplementedError: 子を含め、fastで扱えない型がある場合。
    """
    attribute = plug.attribute()
    if plug.isCompound:
        for index in range(plug.numChildren()):
            require_supported_type(plug.child(index))
        return
    if attribute.hasFn(om2.MFn.kUnitAttribute) or attribute.hasFn(om2.MFn.kEnumAttribute):
        return
    if attribute.hasFn(om2.MFn.kNumericAttribute):
        if om2.MFnNumericAttribute(attribute).numericType() in NUMERIC_WRITERS:
            return
    elif attribute.hasFn(om2.MFn.kMatrixAttribute):
        return
    elif attribute.hasFn(om2.MFn.kTypedAttribute):
        kind = om2.MFnTypedAttribute(attribute).attrType()
        if kind in (om2.MFnData.kString, om2.MFnData.kMatrix) or kind in _TYPED_DATA_FACTORIES:
            return
    raise NotImplementedError(f"fastはこのアトリビュートの型に対応していません: {plug.name()}")


def _ancestor_plugs(mplug):
    """プラグ自身と、その上にあるプラグを順に列挙する。

    コンパウンドアトリビュートの親や、要素が属するマルチアトリビュートを上へたどる。
    ロックと入力接続は親やマルチアトリビュートにも付けられるので、書き込めるかどうかの検査で使う。

    Args:
        mplug (om2.MPlug): たどり始めるプラグ。

    Yields:
        om2.MPlug: まずmplug自身。次に親またはマルチアトリビュートを、いちばん上に着くまで順に返す。
    """
    current = mplug
    while True:
        yield current
        if current.isChild:
            current = current.parent()
        elif current.isElement:
            current = current.array()
        else:
            return


def require_writable(plug, _fn=None):
    """プラグへ書き込めるかを調べる。

    ロック・入力接続・書き込めないアトリビュートかどうかを、OpenMayaで調べる。

    Args:
        plug (om2.MPlug): 調べるプラグ。
        _fn (om2.MFnAttribute | None): 同じ更新の中で作ったアトリビュートの
            function set。省略すると新しく作る。値や検査の結果は保存しない。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: ロック・入力接続・書込み禁止がある場合。
    """
    for current in _ancestor_plugs(plug):
        if current.isLocked or current.isDestination:
            raise RuntimeError(f"アトリビュートがロックされているか、接続されています: {plug.name()}")
    fn = _fn
    if fn is None:
        fn = om2.MFnAttribute(plug.attribute())
    if not fn.writable:
        raise RuntimeError(f"アトリビュートは書き込めません: {plug.name()}")


def writable_compound(mplug):
    """プラグとその子へ書き込めるかを調べる。

    コンパウンドアトリビュートなら、すべての子も調べる。

    Args:
        mplug (om2.MPlug): 調べるプラグ。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: 自身または子にロック・入力接続・書込み禁止がある場合。
    """
    require_writable(mplug)
    if mplug.isCompound:
        for index in range(mplug.numChildren()):
            require_writable(mplug.child(index))


def require_range(plug, value, _fn=None):
    """値がアトリビュートのハード範囲に収まるかを調べる。

    cmds.setAttrと同じ検査をする。

    Args:
        plug (om2.MPlug): 調べるプラグ。
        value (float): 書き込む予定の値。単位を持つ型ではcm・rad・秒で渡す。
        _fn (om2.MFnNumericAttribute | om2.MFnUnitAttribute | None): 同じ更新の中で
            作ったfunction set。範囲と単位の定義は、呼ぶたびに取得し直す。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: 値が設定されたハード範囲外の場合。
    """
    fn = _fn
    if fn is None:
        attribute = plug.attribute()
        if attribute.hasFn(om2.MFn.kUnitAttribute):
            fn = om2.MFnUnitAttribute(attribute)
        elif attribute.hasFn(om2.MFn.kNumericAttribute):
            fn = om2.MFnNumericAttribute(attribute)
        else:
            return
    for exists, getter, lower in ((fn.hasMin, fn.getMin, True), (fn.hasMax, fn.getMax, False)):
        if not exists():
            continue
        limit = getter()
        if isinstance(limit, (om2.MAngle, om2.MDistance, om2.MTime)):
            limit = _convert_units(plug, limit, to_ui=False)
        if (lower and value < limit) or (not lower and value > limit):
            raise RuntimeError(f"値がアトリビュートの範囲を超えています: {plug.name()}")


def _prepared_writes(plug, value, _writable_checked=False):
    """書き込む内容の一覧を作る。

    書き込む前に、すべての成分の型と制限を調べる。そのうえで、OpenMayaで直接書き込む内容を並べる。

    Args:
        plug (om2.MPlug): 書き込み先。
        value (object): 内部単位(cm・rad・秒)の値。
        _writable_checked (bool): Trueなら、書き込めるかどうかを調べ直さない。
            呼び出し元が同じ更新の直前に、自身とすべての子へ :func:`require_writable` を済ませているときに使う。
            型・値・範囲の検査は省かない。

    Returns:
        list[tuple]: 書き込む内容の一覧。各要素は(setter, プラグ, 変換した値, function set)。
            function setは書き込みが終わるまで持っておく。

    Raises:
        TypeError: 数値型への数値以外、または文字列型への文字列以外の入力の場合。
        ValueError: コンパウンドアトリビュートの値の成分の数が、子の数と違う場合。
        RuntimeError: 書き込めない場合、またはハード範囲の外の場合(enumはフィールドの最小〜最大の外)。
        NotImplementedError: API 2.0で値を作れない型の場合。
    """
    attribute = plug.attribute()
    unit = attribute.hasFn(om2.MFn.kUnitAttribute)
    numeric = not unit and attribute.hasFn(om2.MFn.kNumericAttribute)
    if unit:
        fn = om2.MFnUnitAttribute(attribute)
    elif numeric:
        fn = om2.MFnNumericAttribute(attribute)
    else:
        fn = om2.MFnAttribute(attribute)
    if not _writable_checked:
        require_writable(plug, fn)
    if plug.isCompound:
        values = tuple(value)
        if len(values) != plug.numChildren():
            raise ValueError("コンパウンドアトリビュートの値の数が合っていません")
        writes = []
        for i, item in enumerate(values):
            writes.extend(_prepared_writes(plug.child(i), item, _writable_checked))
        return writes
    owner = None
    if unit:
        _require_number(plug, value)
        require_range(plug, value, fn)
        kind = fn.unitType()
        if kind == om2.MFnUnitAttribute.kAngle:
            setter, result = om2.MPlug.setMAngle, om2.MAngle(value, om2.MAngle.kRadians)
        elif kind == om2.MFnUnitAttribute.kDistance:
            setter, result = om2.MPlug.setMDistance, om2.MDistance(value, om2.MDistance.kCentimeters)
        else:
            setter, result = om2.MPlug.setMTime, om2.MTime(value, om2.MTime.kSeconds)
    elif attribute.hasFn(om2.MFn.kEnumAttribute):
        _require_number(plug, value)
        enum_fn = om2.MFnEnumAttribute(attribute)
        # cmds.setAttrと同じく、四捨五入前の値をフィールドの最小〜最大と比べる。
        if value < enum_fn.getMin() or value > enum_fn.getMax():
            raise RuntimeError(f"値がアトリビュートの範囲を超えています: {plug.name()}")
        setter, result = om2.MPlug.setInt, _round_integer(value)
    elif numeric:
        _require_number(plug, value)
        require_range(plug, value, fn)
        writer = NUMERIC_WRITERS.get(fn.numericType())
        if writer is None:
            raise NotImplementedError(f"fastはこの数値型に対応していません: {plug.name()}")
        setter, converter = writer
        result = converter(value)
    else:
        setter, result, owner = prepare_data(attribute, value, name=plug.name())
    return [(setter, plug, result, owner)]


def set_plug(plug, value, _writable_checked=False):
    """MPlugへ値を書き込む。Undoには記録しない。

    書き込む前に、すべての成分を調べる。順番は次のとおり。

    - すべての子の型がfastに対応するかを確かめる。未対応なら、ロックなどより先にNotImplementedErrorにする。
    - 書き込めるかどうか、入力の型、ハード範囲を確かめる。
    - 型付きデータを作り、準備した順に書き込む。

    入力の扱いは通常の経路(cmds.setAttr)と同じにする。整数型・enum・boolへ小数を渡すと四捨五入する。
    数値型への文字列や、文字列型への数値は変換せず、TypeErrorにする。
    function setは、データを渡し終えるまで持っておく。Undoの設定は変えない。
    検査を通った後のOpenMayaでの書き込みで失敗しても、先に書いた成分は自動では元に戻さない。

    Args:
        plug (om2.MPlug): 書き込み先。
        value (object): 角度はrad、距離はcm、時間は秒の値。
        _writable_checked (bool): 内部用。呼び出し元が直前に、自身とすべての子へ
            :func:`require_writable` を済ませているならTrue。その検査だけを繰り返さない。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: 入力の型が合わない場合(数値型へ数値以外、文字列型へ文字列以外を渡した場合)。
        ValueError: コンパウンドアトリビュートの値の成分の数が、子の数と違う場合。
        RuntimeError: 書き込めない場合、またはハード範囲の外の場合。
        NotImplementedError: API 2.0で対応していない型の場合。書き込めるかどうかより先に、書き込む前に止める。
    """
    require_supported_type(plug)
    writes = _prepared_writes(plug, value, _writable_checked)
    for setter, target, item, _owner in writes:
        # データを受け渡すまで作成用function setを保持する。
        setter(target, item)


def set_attr(name, *values, fast=False, **kwargs):
    """アトリビュートへ値を設定する。

    値はcmds.setAttrと同じ形で受け取る。fast=Trueを指定したときだけ、cmds.setAttrを使わずMPlugへ直接書き込む。

    Args:
        name (str): アトリビュート名。
        *values: cmds.setAttr と同じ形で、現在の Maya の単位の値。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。呼出元が明示的に指定する。
        **kwargs: setAttr のフラグ。fast のときに使えるフラグは限られる。

    Returns:
        object | None: 通常の経路では ``cmds.setAttr`` の戻り値。fastではNone。

    Raises:
        TypeError: fastがboolでない場合、またはfastで入力の型が合わない場合。
        NotImplementedError: fastで、``type`` と状態のフラグ以外のフラグを指定した場合。
    """
    _require_bool(fast, "fast")
    if not fast:
        return cmds.setAttr(name, *values, **kwargs)
    selection = om2.MSelectionList()
    selection.add(name)
    plug = selection.getPlug(0)
    flags = {"lock": "isLocked", "keyable": "isKeyable", "channelBox": "isChannelBox"}
    if not values and kwargs and set(kwargs) <= set(flags):
        for key, value in kwargs.items():
            setattr(plug, flags[key], bool(value))
        return None
    unsupported = set(kwargs) - {"type"}
    if unsupported:
        raise NotImplementedError(f"fastのsetAttrは次のフラグに対応していません: {', '.join(sorted(unsupported))}")
    value = values[0] if len(values) == 1 else values
    set_plug(plug, _convert_units(plug, value, to_ui=False))
    return None


def prepare_data(attribute, value, *, name=None):
    """マトリクスとtyped dataの値を、書き込める形に用意する。

    型と値を調べてから用意する。MPlugが無くても使える。

    Args:
        attribute (om2.MObject): アトリビュートの定義。ノードへ追加する前のものでもよい。
        value (object): 書き込む予定の値。
        name (str | None): エラーのメッセージに出す名前。

    Returns:
        tuple: (setter, 変換した値, function set)。function setは書き込みが終わるまで持っておく。

    Raises:
        TypeError: 文字列型へ文字列以外を渡した場合。
        NotImplementedError: fastで構築できない型の場合。
    """
    label = name or om2.MFnAttribute(attribute).name
    owner = None
    if attribute.hasFn(om2.MFn.kMatrixAttribute):
        matrix = value if isinstance(value, om2.MMatrix) else om2.MMatrix(value)
        owner = om2.MFnMatrixData()
        setter, result = om2.MPlug.setMObject, owner.create(matrix)
    elif attribute.hasFn(om2.MFn.kTypedAttribute):
        kind = om2.MFnTypedAttribute(attribute).attrType()
        if kind == om2.MFnData.kString:
            if not isinstance(value, str):
                # cmds.setAttr(type="string")と同じく、文字列以外を変換せずに拒否する。
                raise TypeError(f"{label}には文字列を指定してください: {value!r}")
            setter, result = om2.MPlug.setString, value
        elif kind == om2.MFnData.kMatrix:
            matrix = value if isinstance(value, om2.MMatrix) else om2.MMatrix(value)
            owner = om2.MFnMatrixData()
            setter, result = om2.MPlug.setMObject, owner.create(matrix)
        elif kind in _TYPED_DATA_FACTORIES:
            if kind == om2.MFnData.kMatrixArray:
                value = [item if isinstance(item, om2.MMatrix) else om2.MMatrix(item) for item in value]
            owner = _TYPED_DATA_FACTORIES[kind]()
            setter, result = om2.MPlug.setMObject, owner.create(value)
        else:
            raise NotImplementedError(f"fastはこのデータ型に対応していません: {label}")
    else:
        raise NotImplementedError(f"fastはこのアトリビュートの型に対応していません: {label}")
    return setter, result, owner
