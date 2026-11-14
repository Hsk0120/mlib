"""シーンの中の1つの対象を表す共通の基底クラスと、選択リストで対象の種類を見分ける補助。"""

import maya.api.OpenMaya as om2

#: maya.cmdsやほかのライブラリでよく使う名前と、mlibでの書き方の対応。値は (必要なメソッド名, 案内)、またはその組の列。
#: 必要なメソッドが対象のクラスに無ければ、その案内は表示しない。列では最初に当てはまる案内を使う(None は常に表示する)。
_MEMBER_HINTS = {
    "getAttr": ("getPlug", "getPlug(name).get()を使います"),
    "setAttr": ("getPlug", "getPlug(name).set(value)を使います"),
    "attr": ("getPlug", "getPlug(name)を使います"),
    "listAttr": ("getPlugs", "getPlugs()を使います"),
    "hasAttribute": ("hasAttr", "hasAttr(name)を使います"),
    "attributeExists": ("hasAttr", "hasAttr(name)を使います"),
    "addAttribute": ("addAttr", "addAttr(name, ...)を使います"),
    "deleteAttr": ("getPlug", "getPlug(name).delete()を使います"),
    "connectAttr": ("getPlug", "getPlug(name).connectTo(destination)を使います"),
    "disconnectAttr": ("getPlug", "getPlug(name).disconnect()を使います"),
    "lockAndHide": (
        ("setAttrFlags", "setAttrFlags(names, locked=True, keyable=False, channelBox=False)を使います"),
        ("setFlags", "setFlags(locked=True, keyable=False, channelBox=False)を使います"),
    ),
    "lockNode": ("setLocked", "setLocked(True)を使います"),
    "listConnections": ("getConnections", "getConnections()を使います"),
    "connections": ("getConnections", "getConnections()を使います"),
    "inputs": ("getSource", "getSource()を使います"),
    "outputs": ("getDestinations", "getDestinations()を使います"),
    "listRelatives": ("getChildren", "getChildren()かgetParent()を使います"),
    "getAllChildren": ("getChildren", "getChildren(allDescendents=True)を使います"),
    "listHistory": ("getHistory", "getHistory()を使います"),
    "history": ("getHistory", "getHistory()を使います"),
    "firstParent": ("getParent", "getParent()を使います"),
    "getAllParents": ("getParents", "getParents()を使います"),
    "parent": ("setParent", "setParent(parent)かgetParent()を使います"),
    "nodeType": ("getType", "getType()を使います"),
    "type": ("getType", "getType()を使います"),
    "name": ("getName", "getName()を使います。DAGパスを含まない名前はgetNodeName()です"),
    "nodeName": ("getNodeName", "getNodeName()を使います"),
    "longName": ("getFullName", "getFullName()を使います"),
    "fullPath": ("getFullName", "getFullName()を使います"),
    "fullPathName": ("getFullName", "getFullName()を使います"),
    "shortName": ("getNodeName", "getNodeName()を使います"),
    "exists": ("isValid", "isValid()を使います"),
    "getTranslate": ("getTranslation", "getTranslation()を使います。translateのチャンネルはt.get()です"),
    "setTranslate": ("setTranslation", "setTranslation((x, y, z))を使います。translateのチャンネルはt.set((x, y, z))です"),
    "getRotation": ("getRotate", "getRotate()を使います"),
    "setRotation": ("setRotate", "setRotate((x, y, z))を使います"),
    "xform": ("setMatrix", "getMatrix()/setMatrix()か、getTranslation()/setTranslation()を使います"),
    "getTransformation": ("getMatrix", "getMatrix()を使います"),
    "setTransformation": ("setMatrix", "setMatrix(matrix)を使います"),
    "orientJoint": ("orient", "orient()を使います"),
    "getValue": ("get", "get()を使います"),
    "setValue": ("set", "set(value)を使います"),
    "lock": ("setLocked", "setLocked(True)を使います"),
    "unlock": ("setLocked", "setLocked(False)を使います"),
    "mute": ("setMuted", "setMuted(True)を使います"),
    "unmute": ("setMuted", "setMuted(False)を使います"),
    "getAttrName": ("getShortName", "アトリビュートのパスはgetName().partition('.')[2]、短い名前はgetShortName()を使います"),
    "connect": ("connectTo", "connectTo(destination)を使います"),
    "select": (None, "mlib.select(obj)を使います"),
}


def _exists(name):
    """名前がシーンの対象を指しているかを調べる。

    選択リストへ追加できるかどうかで判定する。
    ほかと区別できる完全名なら、``cmds.objExists`` と同じ結果になる。
    範囲外のコンポーネント番号や、マルチアトリビュートのまだ作られていない要素も True になる。

    Args:
        name (str): 調べる完全名。

    Returns:
        bool: 選択リストへ追加できたら True。
    """
    try:
        om2.MSelectionList().add(name)
    except RuntimeError:
        return False
    return True


def _selection_plug(selection, index):
    """選択リストの要素がアトリビュートなら、そのMPlugを取得する。

    ``MSelectionList.getPlug`` は、要素がノードやコンポーネントのとき RuntimeError か
    TypeError になる(どちらになるかはMayaの版で違う)。そのため、どちらもNoneとして扱う。

    Args:
        selection (om2.MSelectionList): 選択リスト。
        index (int): 要素の番号。

    Returns:
        om2.MPlug | None: アトリビュートの要素ならMPlug。それ以外、またはnullのMPlugならNone。
    """
    try:
        plug = selection.getPlug(index)
    except (RuntimeError, TypeError):
        return None
    if plug.isNull:
        return None
    return plug


def _selection_component(selection, index):
    """選択リストの要素がコンポーネントなら、持ち主のDAGパスとコンポーネントを取得する。

    ``MSelectionList.getComponent`` は、要素がDGノードのとき RuntimeError か TypeError になる。
    要素がDAGノードだけのときは、nullのコンポーネントを返す。そのため、どちらもNoneとして扱う。

    Args:
        selection (om2.MSelectionList): 選択リスト。
        index (int): 要素の番号。

    Returns:
        tuple[om2.MDagPath, om2.MObject] | None: コンポーネントの要素なら(持ち主のDAGパス, コンポーネント)。
            DGノードやDAGノードだけの要素ならNone。
    """
    try:
        path, component = selection.getComponent(index)
    except (RuntimeError, TypeError):
        return None
    if component.isNull():
        return None
    return path, component


def _missing_member_message(obj, name, what="メソッド"):
    """無いメソッドやアトリビュートを参照したときの、AttributeErrorの文言を作る。

    クラスの公開メンバーから近い名前を候補に挙げる。
    maya.cmdsやほかのライブラリの名前なら、mlibでの書き方を案内する。

    Args:
        obj (object): 参照した対象。
        name (str): 参照した名前。
        what (str): 文言に使う種類(``"メソッドやMayaのアトリビュート"`` など)。

    Returns:
        str: 例外の文言。
    """
    # difflibは失敗時の文言を作るときだけ使うため、import mlibの時間に含めない。
    import difflib

    cls = type(obj)
    message = f"'{cls.__name__}'に{what}'{name}'はありません"
    hint = _MEMBER_HINTS.get(name, ())
    for required, text in hint if hint and isinstance(hint[0], tuple) else (hint,) if hint else ():
        if required is None or hasattr(cls, required):
            message += f"。{text}"
            break
    public = sorted({member for member in dir(cls) if not member.startswith("_")})
    # 0.6では短い名前に無関係な候補が出る(``nope`` に ``mnode``)ため、少し厳しくする。
    close = difflib.get_close_matches(name, public, n=3, cutoff=0.7)
    if close:
        message += f"。近い名前: {', '.join(close)}"
    return message


class _ObjectType(type):
    """Objectを呼んだときだけ入力の種類を見分けるメタクラス。派生クラスは通常どおり作る。"""

    def __call__(cls, *args, **kwargs):
        """Objectを呼んだときは、入力の種類を見分けて対応するオブジェクトを返す。

        派生クラスを呼んだときは、通常どおりインスタンスを作る。
        Objectが見分けて返したNode・Plug・Componentを、もう一度初期化することはない。

        Args:
            *args: Objectでは、対象を1つ指定する。派生クラスでは、インスタンスを作るときに渡す位置引数。
            **kwargs: 入力を見分けるとき、または派生クラスのインスタンスを作るときに渡すキーワード引数。

        Returns:
            Object: 見分けた対象のオブジェクト、または作った派生クラスのインスタンス。
        """
        if cls is Object:
            return cls._resolve_input(*args, **kwargs)
        return super().__call__(*args, **kwargs)


class Object(metaclass=_ObjectType):
    """Node・Plug・単数のComponentに共通する基底クラス。

    対象を探すときは :func:`~mlib.ls` を使う。

    Objectに対象を1つ渡すと、その種類に合ったオブジェクトを返す。
    アトリビュートやコンポーネントを渡しても、持ち主のノードには置き換えない。
    すでにあるObjectを渡すと、削除されていても同じインスタンスを返す。
    複数の対象は受け付けない。ノードの作成・複製や、選択の変更はしない。
    """

    def asString(self):
        """今の対象の名前を文字列で返す。

        Node・Plug・Componentそれぞれの ``str()`` と同じ名前を返す。
        名前は保存せず、毎回取得し直すので、名前の変更や親の付け替えにも追いつく。
        対象が無効なときの扱いも、それぞれの型の ``str()`` と同じ。

        Returns:
            str: Mayaのコマンドへ渡せる対象の名前。

        Raises:
            RuntimeError: 対象が無効で、それぞれの型の文字列への変換が止める場合。
        """
        return str(self)

    @staticmethod
    def _resolve_input(value):
        """1つの対象から、Node・Plug・Componentのどれかを作る。

        Args:
            value (str | Object | om2.MObject | om2.MDagPath | om2.MPlug | tuple):
                名前、すでにあるオブジェクト、またはOpenMayaの参照。
                OpenMayaのコンポーネントは ``(MDagPath, MObject)`` の組で渡す。

        Returns:
            Object: すでにあるオブジェクトなら、無効でも同じインスタンス。それ以外は種類に合った新しいオブジェクト。

        Raises:
            TypeError: 入力の型、MObjectの種類、OpenMayaのコンポーネントの組や種類に対応していない場合。
            ValueError: 空文字列や空のMPlugの場合、またはコンポーネントが1つの要素でない場合。
            IndexError: OpenMayaのコンポーネントの番号が、シェイプの範囲の外の場合。
            RuntimeError: 名前の対象が無い場合、1つに決まらない場合、またはOpenMayaの参照が無効な場合。
        """
        # 循環参照の回避: components は core を参照するため、使う時点で読み込む。
        from ..components.component import Component
        from ..nodes.node import Node
        from ..plugs.plug import Plug

        if isinstance(value, Object):
            return value
        if isinstance(value, om2.MPlug):
            return Plug._resolve_input(value)
        if isinstance(value, (om2.MObject, om2.MDagPath)):
            return Node._resolve_input(value)
        if isinstance(value, tuple):
            return Component._resolve_input(value)
        if not isinstance(value, str):
            raise TypeError("シーン内のオブジェクトの参照か名前を指定してください")
        if not value:
            raise ValueError("オブジェクト名は空でない文字列で指定してください")
        selection = om2.MSelectionList()
        selection.add(value)
        if selection.length() != 1:
            raise RuntimeError(f"対象を1つに決められません: {value}")
        if _selection_plug(selection, 0) is not None:
            return Plug._resolve_input(value)
        found = _selection_component(selection, 0)
        if found is not None:
            return Component._resolve_input(found)
        return Node._resolve_input(value)

    @staticmethod
    def _classes():
        """種類の判定に使う mlib のクラスを取得する。

        import が循環しないように、呼んだときに読み込む。

        Returns:
            tuple[type, type, type, type]: Node、Plug、Component、Components。
        """
        # 循環参照の回避: components は core を参照するため、使う時点で読み込む。
        from ..components.component import Component, Components
        from ..nodes.node import Node
        from ..plugs.plug import Plug

        return Node, Plug, Component, Components

    @staticmethod
    def _unsupported(value):
        """対応しない入力型の TypeError を作る。

        Args:
            value (object): 入力値。

        Returns:
            TypeError: 送出する例外。
        """
        return TypeError(f"str・Node・Plug・Component・om2.MObject・om2.MDagPath・om2.MPlugのどれかを指定してください: {type(value).__name__}")

    @staticmethod
    def _name(value, node_class, plug_class, component_class):
        """1つの対象を名前へ変換する。Object._input_name の中身。

        Args:
            value (object): 変換する対象。
            node_class (type): Node クラス。
            plug_class (type): Plug クラス。
            component_class (type): Component クラス。

        Returns:
            str: maya.cmds へ渡せる名前。

        Raises:
            TypeError: 対応しない型の場合。
            ValueError: 空文字列、または無効な対象の場合。
        """
        # 循環参照の回避: nodes は core を参照するため、使う時点で読み込む。
        from ..nodes.node import Node as _InputNode
        from ..plugs.plug import Plug as _InputPlug

        if isinstance(value, str):
            name = value
        elif isinstance(value, node_class):
            name = value.getFullName()
            if not name:
                raise ValueError("無効な(削除された)Nodeは使えません")
        elif isinstance(value, plug_class):
            name = value.getFullName()
            if not name:
                raise ValueError("無効なPlugは使えません(ノードかアトリビュートが削除されています)")
        elif isinstance(value, component_class):
            try:
                name = value.getFullName()
            except (RuntimeError, IndexError) as error:
                raise ValueError(f"無効なComponentは使えません: {error}") from error
        elif isinstance(value, om2.MPlug):
            name = _InputPlug._mplug_name(value)
        elif isinstance(value, om2.MDagPath):
            if not value.isValid() or not om2.MObjectHandle(value.node()).isValid():
                raise ValueError("無効な(削除された)MDagPathは使えません")
            name = value.fullPathName()
        elif isinstance(value, om2.MObject):
            name = _InputNode._mobject_name(value)
        else:
            raise Object._unsupported(value)
        if not name:
            raise ValueError("オブジェクト名は空でない文字列で指定してください")
        return name

    @staticmethod
    def _input_name(value):
        """1つの対象を、maya.cmds へ渡せる名前へ変換する。

        名前は、ほかと区別できるものにする。文字列は Maya へ問い合わせず、そのまま返す。
        対象が実在する Node が必要なときは、Node._resolve_input を使う。変換の決まりはモジュールの説明を参照。

        Args:
            value (str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug):
                変換する対象。

        Returns:
            str: maya.cmds が対象を見つけられる名前。

        Raises:
            TypeError: 対応しない型の場合、MObject が依存ノード以外を指す場合、または
                Components などの複数の対象を渡した場合(その場合は Object._input_names を使う)。
            ValueError: 空文字列の場合、または対象が無効な(削除された・範囲外の)場合。
        """
        node_class, plug_class, component_class, _ = Object._classes()
        return Object._name(value, node_class, plug_class, component_class)

    @staticmethod
    def _flatten_inputs(values):
        """入れ子になった対象の並びを、平らな1つのリストにする。

        どの型どうしを混ぜてよいかは、呼び出し側が確かめる。

        Args:
            values (object): 1つの対象、または入れ子にもなる対象の並び。

        Returns:
            list: 元の順番のままの対象。Componentsは、番号を範囲にまとめるため展開しない。

        Raises:
            TypeError: 対応していない型の場合。
        """
        singles = (str,) + Object._classes() + (om2.MObject, om2.MDagPath, om2.MPlug)
        result = []

        def collect(value):
            """1つの対象はそのまま入れ、入れ物だけを展開する。"""
            if isinstance(value, singles):
                result.append(value)
                return
            try:
                iterator = iter(value)
            except TypeError:
                raise Object._unsupported(value) from None
            for item in iterator:
                collect(item)

        collect(values)
        return result

    @staticmethod
    def _input_names(values, allow_plugs=True):
        """対象を名前のリストへ変換する。

        1つの対象、コレクション、順に取り出せるもののどれでも受け付ける。

        - 1つの対象(Object._input_name が受け付ける型)は、要素が1つのリストになる。
        - ``Components``・``Selection``・``Joints`` などのコレクションと、list・tuple・set・ジェネレーター
          などは、入れ子も含めて元の順番のまま展開する。
        - ``MultiPlug`` は要素へ展開せず、マルチアトリビュートそのものの名前にする。
        - ``Components`` はすべての番号をまとめて1回だけ確かめる。並び順で続いている番号は、
          ``|cube|cubeShape.vtx[0:9]`` のような範囲の名前にまとめる(要素が多くても、
          maya.cmds へ渡す名前は増えない)。

        Args:
            values (object): 変換する対象。1つの対象、または対象を要素に持つ、順に取り出せるもの。
            allow_plugs (bool): False なら、Plug(``MultiPlug`` を含む)と ``om2.MPlug`` を
                TypeError にする。アトリビュートを渡しても maya.cmds が何もしないコマンドで使う
                (文字列は Maya へ問い合わせないので、この検査の対象外)。

        Returns:
            list[str]: 変換した名前のリスト。空のものを渡したら空リスト。

        Raises:
            TypeError: どれかの要素が対応しない型の場合。allow_plugs が False で、
                Plug・MPlug が含まれる場合。同じ並びに文字列とNodeが混ざっている場合。
            ValueError: どれかの要素が空文字列の場合、または対象が無効な場合。
        """
        # 循環参照の回避: nodes は core を参照するため、使う時点で読み込む。
        from ..nodes.node import Nodes as _InputNodes

        node_class, plug_class, component_class, components_class = Object._classes()
        singles = (str, node_class, plug_class, component_class, om2.MObject, om2.MDagPath, om2.MPlug)
        names = []

        def collect(value):
            """1つの対象は名前にし、Componentsは範囲の名前へまとめ、入れ物だけを展開する。"""
            if not allow_plugs and isinstance(value, (plug_class, om2.MPlug)):
                raise TypeError(
                    f"ここではアトリビュート(Plug・MPlug)を指定できません: {type(value).__name__}(持ち主のノードを対象にするにはplug.getNode()を渡します)"
                )
            if isinstance(value, singles):
                names.append(Object._name(value, node_class, plug_class, component_class))
                return
            if isinstance(value, components_class):
                try:
                    # すべての番号の確認はコレクションごとに1回だけ行い、続いている番号は範囲にまとめる。
                    names.extend(value.getCompactNames())
                except (RuntimeError, IndexError) as error:
                    raise ValueError(f"無効なComponentは使えません: {error}") from error
                return
            try:
                iterator = iter(value)
            except TypeError:
                raise Object._unsupported(value) from None
            for item in iterator:
                collect(item)

        items = Object._flatten_inputs(values)
        _InputNodes._validate_inputs(items)
        collect(items)
        return names
