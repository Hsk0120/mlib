"""Mayaの型名とクラスの対応を管理する。登録されていない型には、クラスを自動で作る。"""

import weakref

import maya.cmds as cmds

__all__ = ["NodeRegistry"]

for _name in ("collection_export", "discover_node_package", "get", "node_wrapper", "plug_wrapper"):
    globals().pop(_name, None)


#: node_type -> 継承チェーン(自身を先頭、基底型へ向かう順)の tuple。
_INHERITED_TYPES_CACHE = {}

#: クラスを自動で作る登録表。型の継承のキャッシュを消すときに、作ったクラスも捨てる。
_GENERATING_REGISTRIES = weakref.WeakSet()

#: Mayaの版で改名されたノード型(2025以前の名前 -> 2026以降の名前)。どちらの名前も全版で使える。
_RENAMED_NODE_TYPES = {"multDoubleLinear": "multDL", "addDoubleLinear": "addDL"}

#: 改名の両方向の対応。
_NODE_TYPE_ALIASES = dict(_RENAMED_NODE_TYPES, **{new: old for old, new in _RENAMED_NODE_TYPES.items()})

#: 版によって違う型名を、この版のMayaが認識する型名へ読み替えた結果(認識できた場合だけ保存する)。
_REAL_TYPE_CACHE = {}

#: Maya標準に加わった版が分かっているノード型(型名 -> 最初の版)。作成できない場合の案内に使う。
_NODE_TYPES_SINCE = dict.fromkeys(
    (
        "parentMatrix",
        "multiplyPointByMatrix",
        "multiplyVectorByMatrix",
        "crossProduct",
        "dotProduct",
        "rotateVector",
        "axisFromMatrix",
        "rowFromMatrix",
        "columnFromMatrix",
        "determinant",
        "sum",
        "multiply",
        "divide",
        "subtract",
        "absolute",
        "clampRange",
        "lerp",
        "length",
        "normalize",
        "equal",
        "greaterThan",
        "lessThan",
        "and",
        "or",
        "not",
        "max",
        "min",
        "power",
        "sin",
        "cos",
        "acos",
        "atan2",
        "floor",
        "ceil",
        "round",
        "truncate",
        "negate",
        "smoothStep",
        "average",
    ),
    2024,
)


def _inherited_node_types(node_type):
    """ノードタイプの継承チェーンを取得する。

    ``cmds.nodeType(node_type, isTypeName=True, inherited=True)`` を使う。
    これはノードが無くても、型名だけで継承を調べられる。
    ただし毎回 Maya に問い合わせると少し遅いので、Maya が認識した型名だけ結果を保存しておく。
    知らない型名は、後からプラグインで追加されるかもしれないので、結果を保存しない。
    Maya API 2.0 には同じことを調べる方法が無いため、cmds を使う。

    Args:
        node_type (str): Maya の nodeType 名。

    Returns:
        tuple[str, ...]: 継承チェーン。node_type 自身が先頭で、直接の親から基底の型へ向かって並ぶ。
            Maya が認識しない型名なら、node_type 自身だけの1要素の tuple。
    """
    cached = _INHERITED_TYPES_CACHE.get(node_type)
    if cached is not None:
        return cached
    try:
        chain = cmds.nodeType(node_type, isTypeName=True, inherited=True)
    except RuntimeError:
        return (node_type,)
    if not chain:
        return (node_type,)
    chain = tuple(reversed(chain))
    _INHERITED_TYPES_CACHE[node_type] = chain
    return chain


def _node_type_exists(node_type):
    """Mayaが型名として認識するnodeTypeかを判定する。

    :func:`_inherited_node_types` と同じ問い合わせと保存を使う。保存するのは認識できた型だけにする。
    知らない型名は、後からプラグインで追加されるかもしれないので、毎回問い合わせる。
    ``om2.MNodeClass(知らない型)`` は例外にならず、typeId 0 を返すだけ。そのため、型があるかどうかの判定は
    この cmds の問い合わせだけで行う。

    Args:
        node_type (str): Maya の nodeType 名。

    Returns:
        bool: ``cmds.nodeType(node_type, isTypeName=True)`` が型名として認識すれば True。
    """
    if node_type in _INHERITED_TYPES_CACHE:
        return True
    try:
        chain = cmds.nodeType(node_type, isTypeName=True, inherited=True)
    except RuntimeError:
        return False
    if chain:
        _INHERITED_TYPES_CACHE[node_type] = tuple(reversed(chain))
    return True


def _real_node_type(node_type):
    """版によって違うノード型名を、このMayaが認識する名前へ読み替える。

    2026で名前が変わった ``multDoubleLinear``/``multDL``・``addDoubleLinear``/``addDL`` が対象。
    どの版でも、その版の名前へ読み替える。
    それ以外の名前と、どちらの名前も認識できない場合は、そのまま返す。

    Args:
        node_type (object): ノード型名。文字列以外はそのまま返す。

    Returns:
        object: この版の型名、または入力の値。
    """
    if not isinstance(node_type, str):
        return node_type
    alias = _NODE_TYPE_ALIASES.get(node_type)
    if alias is None:
        return node_type
    cached = _REAL_TYPE_CACHE.get(node_type)
    if cached is not None:
        return cached
    if _node_type_exists(node_type):
        resolved = node_type
    elif _node_type_exists(alias):
        resolved = alias
    else:
        return node_type
    _REAL_TYPE_CACHE[node_type] = resolved
    return resolved


def _real_node_types(value):
    """``ls(type=...)`` などで指定した型名を、この版の名前へ読み替える。

    型名は文字列1つか、文字列の並びで受け付ける。

    Args:
        value (object): 型名、型名の並び、またはそれ以外の値。

    Returns:
        object: 読み替えた値。並びはlistにする。それ以外の値はそのまま返す。
    """
    if isinstance(value, str):
        return _real_node_type(value)
    if isinstance(value, (list, tuple)):
        return [_real_node_type(item) for item in value]
    return value


def _unknown_node_type_message(node_type):
    """作成できないノード型名の例外メッセージを作る。

    Args:
        node_type (str): Mayaが認識しないノード型名。

    Returns:
        str: 例外メッセージ。Maya標準に加わった版が分かっている型なら、その版を案内する。
    """
    try:
        version = cmds.about(majorVersion=True)
    except (AttributeError, RuntimeError, TypeError):
        version = "unknown"
    since = _NODE_TYPES_SINCE.get(node_type)
    if since is not None:
        return f"Mayaにないノード型です: {node_type}(このMaya {version}にはありません。Maya {since}以降が必要です)"
    return f"Mayaにないノード型です: {node_type}(このMaya {version}にないか、この型を提供するプラグインが読み込まれていません)"


def _clear_type_hierarchy_cache():
    """型の継承の保存内容と、自動で作ったクラスを消す。

    クラスを自動で作るすべての登録表が対象。プラグインのロード・アンロードの後に呼ぶ。
    次に型を選ぶときに継承を調べ直し、クラスを作り直す。
    消す前に持っていた自動のクラスでは、これ以降のオブジェクトに対して ``isinstance`` がFalseになる。

    Returns:
        None: 値を返さない。
    """
    _INHERITED_TYPES_CACHE.clear()
    _REAL_TYPE_CACHE.clear()
    for registry in list(_GENERATING_REGISTRIES):
        registry._invalidate_generated()


def _generated_class_name(node_type):
    """Maya の nodeType 名から、自動で作るクラスの名前を決める。

    先頭の1文字を大文字にする(``pointLight`` → ``PointLight``)。
    先頭がもともと大文字の型名(``AISEnvFacade`` など)は、そのまま使う。

    Args:
        node_type (str): Maya の nodeType 名。

    Returns:
        str: 自動で作るクラスの名前。
    """
    return node_type[0].upper() + node_type[1:]


class NodeRegistry:
    """ノード型・アトリビュート型などの名前と、クラスを対応づける登録表。

    ``generate_classes=True`` の表は、Maya が認識するが登録されていない nodeType に対して、
    クラスを自動で作って返す。自動で作るクラスの親は、Maya の継承チェーン
    (``cmds.nodeType(inherited=True)``)の上で最も近い登録済みのクラスになる。

    登録済みのクラスと、作る対象の間にある抽象型(weightGeometryFilter・containerBase・
    entity など)のクラスは作らない。そのため、自動で作ったクラスどうしの ``isinstance`` は
    Maya の継承を表さない。継承を判定するときは ``Node.isType()`` を使う。
    """

    def __init__(self, fallback_class, resolve_inherited_types=False, generate_classes=False):
        """登録表を作る。最初は何も登録されていない。

        Args:
            fallback_class (type): 登録されていない名前に使うクラス。Maya が認識しない
                型名では、クラスを自動で作らずにこのクラスを返す。
            resolve_inherited_types (bool): ``True`` なら、そのままの名前で登録が無いとき、
                Maya のノードタイプの継承チェーンをたどり、最も近い登録済みの祖先の型のクラスを返す
                (Plug のアトリビュート型のように、Mayaのノードタイプの継承と関係ない名前の表では使わない)。
                ``generate_classes=True`` では、この設定に関わらず継承チェーンを使う。
            generate_classes (bool): ``True`` なら、そのままの名前で登録が無く Maya が認識する型に
                対して、クラスを自動で作って保存する。親は最も近い登録済みの祖先の型
                (無ければ fallback_class)。祖先の型のクラスをそのまま返すことはしない。

        Returns:
            None: 値を返さない。
        """
        self._fallback_class = fallback_class
        self._resolve_inherited_types = resolve_inherited_types
        self._generate_classes = generate_classes
        self._classes = {}
        #: 自動で作ったクラスの保存先(nodeType -> class)。登録表を変えたときと、型の継承の保存内容を消したときに空にする。
        self._generated = {}
        if generate_classes:
            _GENERATING_REGISTRIES.add(self)

    def register(self, node_type, wrapper_class):
        """名前にクラスを登録する。同じ名前がすでにあれば上書きする。

        NodeのnodeTypeとPlugのアトリビュート型の両方で使う。
        名前が空でないstrで、値がクラスであることを確かめる。
        自動で作ったクラスは、親の候補が変わるので、すべて捨てる。

        Args:
            node_type (str): 登録する名前。空にはできない。
            wrapper_class (type): 対応するクラス。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: キーが文字列以外、またはwrapper_classがクラス以外の場合。
            ValueError: キーが空文字列の場合。
        """
        self._require_entry(node_type, wrapper_class)
        self._classes[node_type] = wrapper_class
        self._invalidate_generated()

    def clear(self):
        """この表の登録と、自動で作ったクラスを空にする。fallback_classと継承をたどる設定はそのまま。"""
        self._classes.clear()
        self._invalidate_generated()

    def replace(self, wrappers):
        """この表の登録をまるごと置き換える。

        置き換える前に、すべての名前が空でないstrで、値がクラスであることを確かめる。
        確かめるのはこの形だけ。確認で失敗したら、今の登録と自動で作ったクラスはそのまま残す。

        Args:
            wrappers (Mapping[str, type]): 登録する名前とクラスの対応。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: キーが文字列以外、または値がクラス以外の場合。
            ValueError: キーが空文字列の場合。
        """
        validated = {}
        for node_type, wrapper_class in wrappers.items():
            self._require_entry(node_type, wrapper_class)
            validated[node_type] = wrapper_class
        self._classes.clear()
        self._classes.update(validated)
        self._invalidate_generated()

    def wrapper_class(self, node_type):
        """名前に対応するクラスを返す。

        登録が無ければ、設定に従って、自動で作ったクラス・祖先の型のクラス・fallback_classのどれかを使う。
        探す順番は次のとおり。

        1. そのままの名前の登録
        2. すでに自動で作ったクラス
        3. クラスを自動で作る(generate_classes=True)
        4. 最も近い登録済みの祖先の型(resolve_inherited_types=True)
        5. fallback_class

        Maya が認識しない型名ではクラスを作らず、fallback_classを返す(知らない型名は、後からプラグインで
        追加されるかもしれないので、見つからなかった結果は保存しない)。

        Args:
            node_type (str): 登録した名前。継承をたどる表やクラスを自動で作る表では、MayaのnodeType名。

        Returns:
            type: 名前どおりの登録、自動で作ったクラス、最も近い登録済みの祖先の型、またはfallback_classのクラス。
        """
        resolved = self._classes.get(node_type)
        if resolved is not None:
            return resolved
        if self._generate_classes:
            resolved = self._generated.get(node_type)
            if resolved is not None:
                return resolved
            if _node_type_exists(node_type):
                return self._generate_class(node_type)
            return self._fallback_class
        if self._resolve_inherited_types:
            for ancestor in _inherited_node_types(node_type)[1:]:
                resolved = self._classes.get(ancestor)
                if resolved is not None:
                    return resolved
        return self._fallback_class

    def lookup(self, key):
        """登録したクラスを返す。登録が無ければ ``None``。

        fallback_classを使わず、「その名前そのままの登録があるか」だけを知りたいときに使う
        (例: Plug のアトリビュート型で処理を振り分けるとき)。自動で作ったクラスは登録ではないので返さない。

        Args:
            key (str | None): 登録した名前(nodeType やアトリビュート型など)。None は登録が無いものとして扱う。

        Returns:
            type | None: 登録済みクラス。
        """
        return self._classes.get(key)

    def _generate_class(self, node_type):
        """登録されていない型のクラスを自動で作る。

        Maya が認識する型が対象。作ったクラスは保存してから返す。
        親は、継承チェーンの上で最も近い登録済みのクラスにする。チェーンに登録が無ければ
        fallback_classを親にする。間にある抽象型のクラスは作らない。

        Args:
            node_type (str): Maya が認識する nodeType 名。

        Returns:
            type: 作ったクラス。``_generated_node_type`` に型名、``_generated`` に True を持つ。
        """
        parent = self._fallback_class
        parent_type = None
        for ancestor in _inherited_node_types(node_type)[1:]:
            registered = self._classes.get(ancestor)
            if registered is not None:
                parent = registered
                parent_type = ancestor
                break
        name = _generated_class_name(node_type)
        package = self._fallback_class.__module__.rpartition(".")[0] or self._fallback_class.__module__
        parent_text = f"``{parent_type}``" if parent_type is not None else f"``{parent.__name__}``(登録祖先型なし)"
        namespace = {
            "__slots__": (),
            "__module__": package,
            "__qualname__": name,
            "__doc__": (
                f"Mayaのノードタイプ ``{node_type}`` に対応する自動生成クラス。親は {parent_text}。\n\n"
                "手書きクラスは無い。Maya の継承チェーン上で登録クラスとの間にある抽象型の\n"
                "クラスは生成しないため、``isinstance`` は Maya の継承を表さない。継承の判定は\n"
                "``isType()`` を使う。登録表の変更・プラグインのロード/アンロード・``mlib.reload()``\n"
                "で作り直されるため、保持したクラス参照は取り直す。"
            ),
            "_generated_node_type": node_type,
            "_generated": True,
        }
        generated = type(name, (parent,), namespace)
        self._generated[node_type] = generated
        return generated

    def _invalidate_generated(self):
        """自動で作ったクラスの保存先を空にする。次に必要になったときに作り直す。

        Returns:
            None: 値を返さない。
        """
        self._generated.clear()

    def _registered_types(self, base=None):
        """登録した型名を返す。自動で作ったクラスの型名は含まない。

        Args:
            base (type | None): 指定すると、このクラスか、その派生クラスが登録された
                型名だけを返す。

        Returns:
            list[str]: 登録した名前。名前順に並ぶ。
        """
        if base is None:
            return sorted(self._classes)
        return sorted(key for key, wrapper in self._classes.items() if issubclass(wrapper, base))

    @staticmethod
    def _require_entry(node_type, wrapper_class):
        """登録する型名とクラスを確かめる。すでにある名前の上書きは止めない。

        Args:
            node_type (str): 登録する型名。
            wrapper_class (type): 対応するクラス。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 型名が文字列以外、またはwrapper_classがクラスではない場合。
            ValueError: 型名が空文字列の場合。
        """
        if not isinstance(node_type, str):
            raise TypeError("node_typeはstrで指定してください")
        if not node_type:
            raise ValueError("node_typeは空でない文字列で指定してください")
        if not isinstance(wrapper_class, type):
            raise TypeError("wrapper_classはクラスで指定してください")

    def _snapshot(self):
        """今の登録をコピーして返す。

        拡張の登録を始める前に呼ぶ。

        Returns:
            dict[str, type]: この登録表だけが、元に戻すときに使う内部の状態。
        """
        return dict(self._classes)

    def _restore(self, snapshot):
        """登録を、保存しておいた状態へ戻す。

        登録の途中で失敗したときに使う。保存した内容は確かめてあるので、登録し直さずにそのまま戻す。
        自動で作ったクラスは捨てる。

        Args:
            snapshot (dict[str, type]): _snapshotで取得した内部の状態。

        Returns:
            None: 値を返さない。
        """
        self._classes.clear()
        self._classes.update(snapshot)
        self._invalidate_generated()
