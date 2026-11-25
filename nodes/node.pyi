# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaの依存ノードとDAGノードを扱う基底クラス。"""

import inspect
import numbers
import re
from operator import methodcaller
from typing import Optional
import maya.api.OpenMaya as om2
import maya.cmds as cmds
import maya.OpenMaya as om1
from ..core.listMethods import _ListMethods
from ..core.object import Object, _missing_member_message
from ..core.registry import _inherited_node_types, _node_type_exists, _real_node_type, _unknown_node_type_message
from ..decorator import _edit_context, _merge_flags, _pick_alias, _require_bool, _validated_flags, undoChunk, undoTransaction
from ..util import _UNSET, _angle_unit, _ArgumentError, _color_value, _time_unit
from typing import Any, Callable, Generic, Iterable, Iterator, Literal, Sequence
from mlib.common.namespace import Namespace
from mlib.components.component import Component
from mlib.components.component import Components
from mlib.components.pointComponent import PointComponent
from mlib.components.pointComponent import PointComponents
from mlib.maths.eulerRotate import EulerRotate
from mlib.maths.matrix import Matrix
from mlib.maths.quaternion import Quaternion
from mlib.maths.scale import Scale
from mlib.maths.shear import Shear
from mlib.maths.transformation import Transformation
from mlib.maths.translate import Translate
from mlib.maths.vector import Vector
from mlib.nodes.constraint import Constraint
from mlib.nodes.container import Container
from mlib.nodes.dagNode import DagNode
from mlib.nodes.dagPose import DagPose
from mlib.nodes.objectSet import ObjectSet
from mlib.nodes.reference import Reference
from mlib.nodes.shadingEngine import ShadingEngine
from mlib.nodes.shape import Shape
from mlib.nodes.skinCluster import SkinClusters
from mlib.nodes.transform import Transform
from mlib.plugs.plug import Plug
from mlib.plugs.plug import Plugs
from typing import overload
from typing_extensions import Self
from typing_extensions import TypeVar
import os
import pathlib

_MOVABLE_NUMERIC_TYPES: dict
_EXTRA_DATA_TYPES: frozenset
_EXTRA_VECTOR_TYPE: Any
_EXTRA_UNIT_TYPES: dict
_MULTI_COMPONENT_NUMERIC_TYPES: frozenset
_OM2_LIST_ATTR_FLAGS: frozenset
_TYPE_NAME_FN: Any

def _subclass_overrides(base: type, name: str) -> bool:
    """baseの派生クラス(孫以降を含む)のいずれかがメソッドを上書きしているか調べる。

    呼出しのたびに現在の派生クラスを調べるため、後から定義・登録されたクラスも反映する。

    Args:
        base (type): 基底クラス。
        name (str): メソッド名。

    Returns:
        bool: 1つでも上書きしていればTrue。
    """
    ...

def _node_type_name(mobject: om2.MObject) -> str:
    """検証済みの依存ノードの MObject から nodeType 名を取得する。

    ``om2.MFnDependencyNode(mobject).typeName`` と同じ値を、使い回しの関数セットで読む。

    Args:
        mobject (om2.MObject): 有効な依存ノードの MObject。

    Returns:
        str: Maya の nodeType 名。
    """
    ...

def _resolve_node(node: str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug) -> tuple[om2.MObject, om2.MDagPath | None]:
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
            (:class:`mlib.plugs.plug.DeletedAttributeError`)。
        RuntimeError: 名前を解決できない(存在しない、または複数の対象に一致する)場合、
            または空・無効な(削除済みの)mlibのオブジェクトやom2のオブジェクトを指定した場合。
    """
    ...

def _not_unique_message(name: str, matches: Sequence[str]) -> str:
    """複数の対象に一致する名前の例外メッセージを作る。

    一致した対象を最大3件まで完全パスで示し、完全パスか ``mlib.ls`` での指定を案内する。

    Args:
        name (str): 解決しようとした名前。
        matches (Sequence[str]): 一致した対象の名前。

    Returns:
        str: 例外メッセージ。
    """
    ...

def _require_node_name(name: object) -> None:
    """作成・改名に使うノード名の、Mayaが黙って置き換える文字を拒否する。

    Args:
        name (object): ノード名。文字列以外の検査はMayaに任せる。

    Returns:
        None: 値を返さない。

    Raises:
        ValueError: DAGパスの区切り ``|`` を含む場合。
    """
    ...

def _is_deleted_api_object(value: object) -> bool:
    """om2 オブジェクトが削除済みのノードを指すか判定する(空のオブジェクトは False)。

    Args:
        value (object): 判定する値。om2 の MObject・MDagPath・MPlug 以外は False。

    Returns:
        bool: 削除済みのノードを指す MObject・MDagPath・MPlug の場合は True。
            無効な MDagPath は、空のパスも含めて True(``Node(...)`` も区別しない)。
    """
    ...

def _resolve_input_or_none(other: Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug) -> Node | None:
    """判定メソッド(``isAncestorOf`` など)の対象をノードへ解決する。

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
    ...

def _dump_movable_attr(plug: Plug) -> dict:
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
    ...

def _require_same_attr_definition(plug: Plug, flags: dict):
    """addAttr(skipExisting=True)で、既存のアトリビュートが要求した型と一致するか検証する。

    Args:
        plug (Plug): 既存のアトリビュート。
        flags (dict): 型を解決済みのaddAttrのフラグ(attributeType/dataType・multi)。

    Raises:
        TypeError: 型、またはマルチアトリビュートかどうかが一致しない場合。
    """
    ...

def _enum_field_value(enum_name: str | None, field: str) -> int:
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
    ...

def _enum_definition(plug: Plug) -> str:
    """enum の全フィールドを ``cmds.attributeQuery(listEnum=True)`` と同じ書式の文字列にする。

    値の昇順に並べ、直前の値 + 1(先頭は0)と異なる値だけ ``名前=値`` と書く(例: ``a=1:b=5``)。

    Args:
        plug (Plug): enum アトリビュートのプラグ。

    Returns:
        str: ``addAttr(enumName=...)`` へそのまま渡せるフィールド定義。
    """
    ...

def _scalar_attribute(attribute: om2.MObject) -> bool:
    """``cmds.listAttr(scalar=True)`` が列挙する、単一成分の数値・単位・enum 型か判定する。

    マルチアトリビュートであっても、要素が単一成分なら対象に含める(listAttr と同じ)。

    Args:
        attribute (om2.MObject): アトリビュート定義。

    Returns:
        bool: scalar として列挙する場合は True。
    """
    ...

def _writable_plug(plug: Plug) -> bool:
    """Plug._require_writable() が通るか(ロック・入力接続・書込み禁止が無いか)を返す。

    Args:
        plug (Plug): 検査するプラグ。

    Returns:
        bool: 書き込める場合は True。シーンは変更しない。
    """
    ...

def _movable_connection_ref(plug: Plug) -> tuple[Node, str]:
    """削除する定義を保持せず、所有ノードと再解決用のパスを保存する。

    Args:
        plug (Plug): 変更前に存在する接続端点。

    Returns:
        tuple[Node, str]: 所有ノードとaliasを使わないアトリビュートパス。
    """
    ...

def _create_movable_attr(node: Node, info: dict) -> Plug:
    """退避した定義と値を再作成する。接続とロックは全定義の作成後に戻す。

    Args:
        node (Node): アトリビュートを追加する対象ノード。
        info (dict): _dump_movable_attr() が返した情報。

    Returns:
        Plug: 再作成したアトリビュートプラグ。
    """
    ...

def _plug_key(mplug: om2.MPlug) -> tuple[int, str]:
    """循環の探索で同じアトリビュートを同一視するキーを返す。

    Args:
        mplug (om2.MPlug): アトリビュート。

    Returns:
        tuple[int, str]: 所有ノードのハッシュと、論理番号を含むロング名のパス。
    """
    ...

def _is_writable(mplug: om2.MPlug) -> bool:
    """アトリビュートへ今書き込めるか(ロック・animCurve以外の入力接続が無いか)を返す。

    Args:
        mplug (om2.MPlug): 調べるアトリビュート。

    Returns:
        bool: 自身・親(コンパウンドアトリビュート)・マルチアトリビュートの全体のどれもロックされておらず、
            自身と親の入力がanimCurveだけ(または無い)ならTrue。
    """
    ...

def _attribute_names(attributes: str | Iterable[str] | None) -> list[str] | None:
    """キー操作のアトリビュート名を、cmdsへ渡す名前のリストへ変換する。

    Args:
        attributes (str | Iterable[str] | None): アトリビュート名。

    Returns:
        list[str] | None: 名前のリスト。Noneは指定なし(Mayaの既定)。

    Raises:
        TypeError: 文字列・文字列の列・None以外の場合。
        ValueError: 空の列、または空文字列を含む場合。
    """
    ...


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
            MPlugも同じ。DeletedAttributeErrorになる。
        RuntimeError: 対象が空・削除済み・存在しない・一意でない場合。
    """
    _registry: None
    _mobject: 'om2.MObject'
    _dag_path: 'Optional[om2.MDagPath]'
    _handle: 'om2.MObjectHandle'
    _fn_cache: None
    def __new__(cls, node: str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug, *args: object, **kwargs: object) -> Self:
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
                (``DeletedAttributeError``)。
            RuntimeError: ノードを解決できない場合。
        """
        ...
    def __init__(self, node: str | Node | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug) -> None:
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
                (``DeletedAttributeError``)。
            RuntimeError: ノード名を解決できない場合。
        """
        ...
    def __eq__(self, other):
        """同じノードを指しているか比べる。

        どちらも生存しているときだけ等しくなる。DAGノードでは、インスタンスのパスも区別する。

        Args:
            other: 比較・演算の相手。
        """
        ...
    def __hash__(self):
        """作ったときのMayaのハンドルのハッシュを返す。名前を変えても、削除しても変わらない。"""
        ...
    def __repr__(self) -> str:
        """デバッグ用に、クラス名とノード名を含む文字列を返す。

        Returns:
            str: 有効なら型名とノード名、無効なら型名とinvalidを含む文字列。
        """
        ...
    def __str__(self) -> str:
        """Mayaのノードの最短の一意な名前を返す。

        maya.cmdsは文字列以外の引数に ``str()`` を使うので、Nodeを ``cmds.select(node)`` のように
        そのまま渡せる。呼び出すたびに求め直すので、名前の変更や親子付けの変更に追従する。

        :meth:`getName` と違い、削除済みのノードやUndoで無効になったノードでも、例外にせず空文字列を返す
        (maya.cmdsへ渡したときに、Maya側のエラーになるようにするため)。

        Returns:
            str: 最短の一意な名前。無効なノードでは空文字列。
        """
        ...
    def __getattr__(self, name: str) -> Plug:
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
        ...
    def __setattr__(self, name: str, value: object) -> None:
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
        ...
    @staticmethod
    def setDgTimingEnabled(state: bool) -> None:
        """Maya全体のDG時間計測を有効・無効にする。

        個々のノードの計測の開始・停止(:meth:`setDgTimer`)とは別の、全体の設定。診断操作のためUndoには記録されない。
        計測結果のリセットやUndo設定の変更は行わない。fast引数は持たない(診断設定のため)。

        Args:
            state (bool): Trueなら全体の計測を有効にする。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでない場合。
        """
        ...
    def getShadingEngines(self) -> Nodes[ShadingEngine]:
        """このノードから直接つながっているShadingEngineを取得する。

        同じものは1回だけ含む。

        Returns:
            Nodes[ShadingEngine]: 直接の接続先のShadingEngine。テクスチャからヒストリをたどって探すものではない。
        """
        ...
    def sameNode(self, other: object) -> bool:
        """同じMayaのノードを指しているか調べる。

        ``==`` と違い、DAGノードのインスタンス(パス)の違いは区別しない。

        Args:
            other (object): 比べる相手。Node以外ならFalse。

        Returns:
            bool: どちらも生存していて、同じMayaのノードを指していればTrue。
        """
        ...
    def isValid(self) -> bool:
        """シーン上でノードが有効か調べる。

        ノードそのものが有効かを返し、このオブジェクトが持つDAGパスは確かめない。
        持っているパスのインスタンスだけが削除されても、ノードが残っていればTrueになる。
        その場合、パスを使う操作はRuntimeErrorになる。

        Returns:
            bool: ノードのハンドルが有効なら ``True``。
        """
        ...
    def isAlive(self) -> bool:
        """ノードのMayaのオブジェクトが、メモリ上に残っているか調べる。

        Returns:
            bool: MObjectHandle.isAlive() の結果。削除済みでも、Undoのために残っているノードはTrueになることがある。
        """
        ...
    def mnode(self) -> om2.MObject:
        """このオブジェクトが持つ、Maya API 2.0のMObjectを返す。

        Returns:
            om2.MObject: このオブジェクトが指すノードのMObject。
        """
        ...
    @overload
    def getDgTimer(self, metric: None = ..., *, timerType: int = ..., callbacks: Literal[True], state: Literal[False] = ...) -> list[tuple[str, float]]: ...
    @overload
    def getDgTimer(self, metric: None = ..., *, timerType: int = ..., callbacks: Literal[False] = ..., state: Literal[True]) -> int: ...
    @overload
    def getDgTimer(self, metric: int, *, timerType: int = ..., callbacks: Literal[False] = ..., state: Literal[False] = ...) -> float: ...
    @overload
    def getDgTimer(self, metric: int | None = ..., *, timerType: int = ..., callbacks: bool = ..., state: bool = ...) -> float | list[tuple[str, float]] | int:
        """指定したDG処理の計測値を取得する。``callbacks=True`` はコールバックの種類別の値、``state=True`` は計測の状態。

        計測は開始せず、Mayaが持っている結果だけを返す。未計測の値は0になり得るため、0を処理が実行されていない証拠にはしない。

        Args:
            metric (int | None): MFnDependencyNodeのkTimerMetric_*定数(0〜8)。callbacks・stateを指定しないときは必須。
            timerType (int): kTimerType_self(0、既定)、inclusive(1)、count(2)。
            callbacks (bool): Trueなら、コールバックの種類別の計測値を返す。metric・stateとは同時に指定できない。既定はFalse。
            state (bool): Trueなら、このノードの計測の状態を返す。metric・callbacksとは同時に指定できない。既定はFalse。

        Returns:
            float | list[tuple[str, float]] | int: self・inclusiveなら秒、countなら回数を表す値。
                callbacks=Trueなら、(コールバック名, 計測値)の新しいリスト(Mayaの列挙順)。
                state=Trueなら、MFnDependencyNodeのkTimerOn・kTimerOff・kTimerUninitialized・kTimerInvalidState。

        Raises:
            TypeError: metric・timerTypeがintでない場合、callbacks・stateがboolでない場合、
                metric・callbacks・stateのちょうど1つを指定していない場合。
            ValueError: 定数が範囲外の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setDgTimer(self, state: bool | None = ..., *, reset: bool = ...) -> None:
        """このノードのDG計測を開始・停止する。``reset=True`` なら、たまった計測結果を消す。

        診断用の計測の状態を変えるだけなので、Undoには記録しない。Undoの設定は変えない。
        計測には実行の負荷があり、全体の計測の設定(:meth:`setDgTimingEnabled`)や評価の方式によって、記録される項目が違う。
        fast引数は持たない(シーンの値の編集ではないため)。

        Args:
            state (bool | None): Trueで開始、Falseで停止。過去の結果は消さない。既定のNoneなら、開始・停止は変えない。
            reset (bool): Trueなら、このノードにたまった計測結果を消す(stateも指定したときは、消してから開始・停止する)。
                既定はFalse。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでもNoneでもない場合、resetがboolでない場合、またはstateもresetも指定していない場合。
            RuntimeError: ノードが無効な場合。

        Examples:
            >>> node.setDgTimer(True)                 # 計測を始める
            >>> node.setDgTimer(reset=True)           # 止めずに結果だけ消す
            >>> node.setDgTimer(False, reset=True)    # 結果を消して止める
        """
        ...
    def mfn(self) -> om2.MFnDependencyNode:
        """このノードに使えるOpenMayaのfunction setのうち、最も具体的なものを取得する。

        呼び出すたびに新しく作る。Nodeでは ``om2.MFnDependencyNode`` を返す。DagNodeは ``MFnDagNode``、
        Transformは ``MFnTransform`` のように、派生クラスが最も具体的なfunction setを返すよう上書きする。
        内部のキャッシュとは別のものなので、戻り値を持ち続けてもほかの取得に影響しない。

        Returns:
            om2.MFnDependencyNode: このノードの function set。

        Raises:
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        ...
    @overload
    def getType(self, inherited: Literal[True]) -> list[str]: ...
    @overload
    def getType(self, inherited: Literal[False] = ...) -> str: ...
    @overload
    def getType(self, inherited: bool = ...) -> str | list[str]:
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
        ...
    def hasFn(self, fn: int) -> bool:
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
        ...
    def getClassification(self) -> list[str]:
        """ノードの型の分類の文字列を取得する。

        Returns:
            list[str]: ``MNodeClass.classification`` を1つだけ入れたリスト。分類が無ければ ``[""]``。
        """
        ...
    def isClassified(self, classification: str) -> bool:
        """ノードの型が、指定した分類に入るかを調べる。

        ``cmds.getClassification(type, satisfies=classification)`` と同じ判定で、``cmds.listNodeTypes(classification)`` が
        返す型の一覧にこのノードの型が入るかと同じ結果になる。たとえばblinnは ``isClassified("shader")``・
        ``isClassified("shader/surface")`` でTrue、fileは ``isClassified("texture")`` でTrueになる。

        Args:
            classification (str): 分類(``"shader"``・``"texture/2d"``・``"utility"`` など)。

        Returns:
            bool: 分類に入ればTrue。

        Raises:
            TypeError: classificationが文字列でない場合。
            ValueError: classificationが空文字列の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def isType(self, nodeType: str) -> bool:
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
        ...
    def isLocked(self) -> bool:
        """ノードそのものがロックされているか調べる。

        アトリビュートごとのロックはPlug.isLocked()で調べる。

        Returns:
            bool: ロックされていればTrue。

        Raises:
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        ...
    def setLocked(self, state: bool = ..., *, fast: bool = ...) -> None:
        """ノードそのもののロックを設定する。

        アトリビュートごとのロックはPlug.setLocked()を使う。
        通常は ``cmds.lockNode`` で変更し、Undoに記録する。``fast=True`` では
        ``MFnDependencyNode.isLocked`` を直接変更し、Undoに記録しない。

        Args:
            state (bool): Trueならロック、Falseなら解除する。既定はTrue。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateかfastがbool以外の場合。
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合、またはMayaが変更を拒否した場合。
        """
        ...
    def isFromReferencedFile(self) -> bool:
        """ノードがリファレンスしたファイルから読み込まれたものか調べる。

        Returns:
            bool: リファレンスから読み込まれたノードならTrue。

        Raises:
            RuntimeError: ノードが破棄されている(削除後にUndoの記録から消えた)場合。
        """
        ...
    def swapConnections(self, other: Node | str) -> None:
        """同じ型の2つのDGノードの接続をMayaのnodeCastで入れ替える。

        名前・値は交換しない。DAG・参照・追加アトリビュートのあるノードは対象外。
        通常Undoに対応する。fast引数は持たない(1回のnodeCastコマンドを使うため)。

        Args:
            other (Node | str): 接続を交換する同じノード型の相手。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: otherがノードとして解決できない型の場合。
            ValueError: 自身を指定した場合、またはノード型が異なる場合。
            RuntimeError: ノードの無効・ロック、またはMayaが交換を拒否した場合。
            NotImplementedError: DAG・参照・追加アトリビュートのあるノードの場合。
        """
        ...
    def getContainer(self) -> Container | None:
        """このノードが直接所属するコンテナを取得する。

        Returns:
            Container | None: 所属コンテナ。所属していなければNone。

        Raises:
            RuntimeError: ノードが無効、またはMayaが照会を拒否した場合。
        """
        ...
    def getReference(self) -> Reference | None:
        """このノードを読み込んだリファレンスノードを取得する。

        ``cmds.referenceQuery(node, referenceNode=True)`` と同じく、入れ子のリファレンスでは、
        ノードを直接読み込んだ最も内側のリファレンスノードを返す。

        Returns:
            Reference | None: リファレンスノード。リファレンスから読み込まれたノードでなければ ``None``。

        Raises:
            RuntimeError: ノードが削除済み・無効な場合。
        """
        ...
    def hasUniqueName(self) -> bool:
        """階層を含まないノード名がシーン内で一意か調べる。

        名前空間は名前に含む。最短一意名を取得するgetNameとは異なり、改名しない。

        Returns:
            bool: MFnDependencyNodeが一意と判定した場合はTrue。

        Raises:
            RuntimeError: ノードが無効(削除済み)な場合。
        """
        ...
    def getSets(self, *, type: str | None = ...) -> Nodes[ObjectSet]:
        """このノードが入っているセット(objectSetとその派生の型)を取得する。

        ``cmds.listSets(object=node)`` と同じく、ノード自身がメンバーになっているセットを返す。

        - Shapeでは、コンポーネント(``f[0]`` など)だけがメンバーになっているセット(シェーディンググループなど)も含む。
        - Transformでは、Transform自身が入っているセットだけを返す。Shapeのセットは含まない。

        Args:
            type (str | None): セットのノードの型で絞る(``"shadingEngine"`` など)。派生の型も含む。Noneなら絞らない。

        Returns:
            Nodes[ObjectSet]: セットのオブジェクト(``ShadingEngine`` などの派生の型も含む)。名前の順。無ければ空の集まり。

        Raises:
            TypeError: typeが文字列・None以外の場合。
            ValueError: typeが空文字列の場合。
            RuntimeError: ノードが削除済み・無効な場合。
        """
        ...
    def isAncestorOf(self, other: Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug, *, direct: bool = ...) -> bool:
        """otherが、このノードの子孫か調べる。``direct=True`` なら、直接の子かを調べる。

        このオブジェクトが持つDAGパスで判定する。

        Args:
            other (Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug):
                調べる対象か、その名前。Plugはそれを持つノードを、Componentはそれを持つシェイプを指す。
            direct (bool): Trueなら、直接の子だけをTrueにする。既定はFalse(孫より下も含む)。

        Returns:
            bool: 自身を除く子孫ならTrue(direct=Trueでは直接の子ならTrue)。otherがDAGノードでない場合、
                無効なノードの場合、削除済みのアトリビュートの場合はFalse。

        Raises:
            TypeError: otherの型が対応していない場合、またはdirectがboolでない場合。
            RuntimeError: 名前を解決できない場合、MObject・MPlugが空の場合、
                または自身が削除済みか無効な場合(持っているパスのインスタンスが消えた場合も含む)。
        """
        ...
    def getNamespace(self) -> Namespace:
        """ノードが入っているネームスペースを取得する。

        Returns:
            Namespace: ノードが入っているネームスペース。
        """
        ...
    def setNamespace(self, namespace: str | Namespace, *, fast: bool = ...) -> None:
        """ノードを指定したネームスペースへ移す。

        移す先のネームスペースが無ければ作る。

        Args:
            namespace (str | Namespace): 移す先のネームスペースの名前。末尾の ``":"`` は付けても付けなくてもよい。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。ネームスペース付きの名前は ``getName(node=True)`` で取得する。

        Raises:
            ValueError: namespaceが空文字列か、文字列でない場合。
            RuntimeError: ネームスペースへ移せなかった場合。
        """
        ...
    def delete(self, *, skipConnected: bool = ..., fast: bool = ...) -> None:
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
            skipConnected (bool): Trueなら、自身かDAGの子孫にDGの接続がある場合は削除しない。
                入力・出力・message・セットやマテリアルの接続をすべて含む。
                Falseならふつうに削除する。ロックの解除や、例外を抑えることはしない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: skipConnectedがboolでない場合。
            RuntimeError: 対象が無効な場合、ロック・リファレンス・削除できないノードを含む場合、
                またはMayaが削除を拒否した場合。
        """
        ...
    def rename(self, name: str, ignoreShape: bool = ..., *, fast: bool = ...) -> None:
        """ノード名を変更する。

        名前が重なったときの連番など、Mayaが直した後の名前は、戻り値の ``getName(node=True)`` で取得する。

        Args:
            name (str): 新しいノード名。DAGパスの区切りの ``|`` は含められない
                (Mayaが黙って別の文字へ置き換えるため、受け付けない)。
            ignoreShape (bool): ``True`` なら、Shapeの名前は変えない。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合。
            ValueError: nameに ``|`` を含む場合。
            RuntimeError: ノードが無効(削除済み)の場合(``無効な<クラス名>のため、名前の変更はできません``。
                fastも同じ)、このオブジェクトが持つDAGパスのインスタンスが削除された場合、
                またはMayaが名前の変更を拒否した場合。
        """
        ...
    def duplicate(self, name: str | None = ..., *, suffix: str | None = ..., **kwargs: object) -> Self:
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
        ...
    def select(self, **kwargs: object) -> None:
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
        ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[True], index: int) -> tuple[Plug, Node] | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[True], index: None = ...) -> list[tuple[Plug, Node]]: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[False] = ..., index: int) -> tuple[Plug, Plug] | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[False] = ..., index: None = ...) -> list[tuple[Plug, Plug]]: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[True], index: int) -> Node | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[True], index: None = ...) -> Nodes: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[False] = ..., index: int) -> Plug | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[False] = ..., index: None = ...) -> Plugs: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: bool = ..., asNode: bool = ..., index: int | None = ...) -> Plugs | Nodes | list | Plug | Node | tuple | None:
        """接続を取得する。

        結果はPlug・Node・ペアのどれかの形で返す。既定では、直接つながっている相手を返す
        (``cmds.listConnections`` と同じ)。

        ``skipConversionNodes=True`` (または ``scn=True``)では、:meth:`~mlib.plugs.plug.Plug.getConnections`
        と同じく、unitConversionの仲間
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
            Plugs | Nodes | list | Plug | Node | tuple | None: 条件に合う結果。
        """
        ...
    def setKey(self, attributes: str | Iterable[str] | None = ..., *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., **kwargs) -> None:
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
            None: 値を返さない。

        Raises:
            TypeError: attributesが文字列・文字列の並び・None以外の場合、``attribute`` / ``at`` をkwargsに渡した場合、
                単位の型が不正な場合、または ``timeUnit="sec"`` でtimeに数値以外を指定した場合。
            ValueError: attributesが空の並びの場合、単位の名前が不正な場合、またはuiUnits=Trueと単位を同時に指定した場合。
            RuntimeError: ノードが無効な場合、またはMayaがキーの設定を拒否した場合。
        """
        ...
    def removeKey(self, attributes: str | Iterable[str] | None = ..., *, time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> None:
        """複数のアトリビュートのキーを削除する(``cmds.cutKey(node, attribute=[...], clear=True)`` にあたる)。

        キーのクリップボードは変えない。キーをすべて削除すると、Mayaと同じく、空になったカーブも削除される。
        fast引数は持たない(OpenMayaでキーを1つずつ消すほうが、cmds.cutKeyより遅いため)。

        Args:
            attributes (str | Iterable[str] | None): アトリビュート名。Noneなら、キーのあるすべてのアトリビュート。
            time (float | Sequence[float] | None): 削除する時刻、または両端を含む範囲 ``(start, end)``。Noneならすべてのキー。
            timeUnit (str | None): timeの単位。None(既定)と ``"frame"`` は今のUIの時間単位のフレーム、``"sec"`` は秒。

        Returns:
            None: 値を返さない。キーが無ければ何もしない。

        Raises:
            TypeError: attributesが文字列・文字列の並び・None以外の場合、timeが数値・2つの数値の並び・None以外の場合、
                またはtimeUnitが文字列・None以外の場合。
            ValueError: attributesが空の並びの場合、timeが有限でない場合、範囲の始まりが終わりより大きい場合、
                またはtimeUnitが対応していない単位の名前の場合。
            RuntimeError: ノードが無効な場合、またはMayaが削除を拒否した場合。
        """
        ...
    def moveKey(self, attributes: str | Iterable[str] | None = ..., *, time: float | Sequence[float] | None = ..., timeOffset: float = ..., valueOffset: float = ..., unit: str | None = ..., timeUnit: str | None = ...) -> None:
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
            None: 値を返さない。

        Raises:
            TypeError: attributesが文字列・文字列の並び・None以外の場合、またはほかの引数の型が不正な場合。
            ValueError: attributesが空の並びの場合、有限でない値を渡した場合、または単位の名前が対応していない場合。
            RuntimeError: ノードが無効な場合、またはMayaが移動を拒否した場合。
        """
        ...
    def setKeyTangent(self, attributes: str | Iterable[str] | None = ..., *, inTangentType: str | None = ..., outTangentType: str | None = ..., time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> None:
        """複数のアトリビュートのキーの、接線の型をまとめて変える(``cmds.keyTangent(node, attribute=[...], edit=True)`` にあたる)。

        時刻か範囲で選んだキーをまとめて変える。Mayaのコマンドの1回なので、Undoが有効なら1回で戻せる。
        fast引数は持たない(1回のcmdsで全キーを処理するため)。

        Args:
            attributes (str | Iterable[str] | None): アトリビュート名。Noneなら、キーのあるすべてのアトリビュート。
            inTangentType (str | None): 入力側の接線の型(``"auto"``・``"linear"``・``"flat"`` など。``"fixed"`` は使えない)。Noneなら変えない。
            outTangentType (str | None): 出力側の接線の型。Noneなら変えない。
            time (float | Sequence[float] | None): 変えるキーの時刻、または両端を含む範囲 ``(start, end)``。Noneならすべてのキー。
            timeUnit (str | None): timeの単位。None(既定)と ``"frame"`` は今のUIの時間単位のフレーム、``"sec"`` は秒。

        Returns:
            None: 値を返さない。キーが無ければ何もしない。

        Raises:
            TypeError: attributesが文字列・文字列の並び・None以外の場合、timeが数値・2つの数値の並び・None以外の場合、
                またはtimeUnitが文字列・None以外の場合。
            ValueError: attributesが空の並びの場合、接線の型を1つも指定しない場合、対応していない接線の型かfixedを指定した場合、
                timeが有限でない場合、範囲の始まりが終わりより大きい場合、またはtimeUnitが対応していない単位の名前の場合。
            RuntimeError: ノードが無効な場合、またはMayaが変更を拒否した場合。
        """
        ...
    def getHistory(self, *, type: str | None = ..., future: bool = ...) -> Nodes:
        """ヒストリのノードを取得する。

        ``MItDependencyGraph`` でヒストリをたどって探す。

        Args:
            type (str | None): ノードの型で絞る。派生の型も含む。Noneなら絞らない。
            future (bool): Trueなら下流を、Falseなら上流を探す。既定はFalse。

        Returns:
            Nodes: ``cmds.listHistory`` と同じ順(深さ優先)。自身は含まず、同じものは1回だけ含む。
                見つからなければ空リスト。Shapeを持つTransformでは、``listHistory`` と同じく、
                中間オブジェクトでない直下のShapeのヒストリを返す。DAGノードは最初のDAGパスで返す。

        Raises:
            RuntimeError: 無効な(削除済みの)ノードの場合。
        """
        ...
    def findCycles(self) -> list[list[Plug]]:
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
        ...
    def resetAttrs(self, attributes: str | Plug | Iterable[str | Plug] | None = ..., *, fast: bool = ..., check: bool = ...) -> Plugs:
        """アトリビュートを既定値へ戻す。

        指定したアトリビュートを戻す。省略したときは、書き込めてキーを設定できるアトリビュートを戻す。
        Transformでも同じ決まりで、省略時はtranslate・rotate・scale・shearに限らず、キーを設定できるもの
        すべて(visibilityなども含む)を戻す。Jointは、省略時にjointOrientも戻す。

        Args:
            attributes (str | Plug | Iterable[str | Plug] | None): アトリビュート名か、このノードのPlug
                (名前と混ぜてもよい)。Noneなら、キーを設定できる数値・単位付き・enumのアトリビュートを対象にする。
                そのうち、マルチアトリビュート・ロック・入力の接続・書込み禁止・対応していない型のものは除く
                (通常とfastで同じものを選ぶ)。明示したアトリビュートのエラーは、除かずにそのまま例外にする。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            Plugs: 既定値へ戻したアトリビュート。すべての変更を1回のUndoにまとめる。

        Raises:
            AttributeError: 指定したアトリビュートが存在しない場合。
            TypeError: 名前・Plug以外を指定した場合、または明示したアトリビュートが既定値へ戻せない型の場合。
            ValueError: 別のノードのPlugを指定した場合。
            RuntimeError: 明示したアトリビュートが、ロックや接続などで書き込めない場合。
        """
        ...
    def setAttrFlags(self, attributes: str | Plug | Iterable[str | Plug], *, locked: bool | None = ..., keyable: bool | None = ..., channelBox: bool | None = ..., children: bool = ..., fast: bool = ...) -> None:
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
            None: 値を返さない。

        Raises:
            AttributeError: 指定したアトリビュートが存在しない場合。
            TypeError: 必須の引数が足りない場合、fast・childrenや状態の型が不正な場合、
                または名前・Plug以外を指定した場合。
            ValueError: 別のノードのPlugを指定した場合。
            RuntimeError: Mayaが変更を拒否した場合。
        """
        ...
    def getPlugs(self, userDefined: bool = ..., includeChildren: bool = ..., *, writable: bool = ..., animatable: bool = ..., **listAttrFlags) -> Plugs:
        """アトリビュートの一覧を、Plugのオブジェクトで取得する。

        - ``userDefined=True``: ユーザーが追加した(動的な)アトリビュートだけを、Mayaの定義から追加した順に、
          型に合ったPlugで作る。cmdsは使わない。マルチアトリビュートはMultiPlugになり、
          非表示やkeyableでないものも含む。
        - それ以外: ``cmds.listAttr`` の条件(``keyable=True`` など)で取得する。
          フラグ無し・``keyable=True``・``scalar=True`` (組み合わせてもよい)では ``cmds.listAttr`` を呼ばず、
          OpenMayaで定義をたどって同じ順・同じ結果を求める。トップレベルの定義の順に並べ、
          コンパウンドアトリビュートの子は親のすぐ後に置く。マルチアトリビュートであるコンパウンドアトリビュートの子は含めない。
        - ``animatable=True``: Mayaがアニメーションできると判定するアトリビュートを、``cmds.listAnimatable`` の順と範囲で返す。
          Transformでは、Shapeのアトリビュートも含む(ほかのノードのPlugが入る)。重複は除く。
          ロックや入力の接続による、今書き込めるかどうかは保証しない。

        Args:
            userDefined (bool): Trueなら、ユーザー定義のアトリビュートだけを返す。listAttrのフラグとは同時に指定できない。
                既定はFalse。
            includeChildren (bool): Trueなら、コンパウンドアトリビュートの子も含める。Falseならトップレベルだけ。既定はTrue。
            writable (bool): Trueなら、今書き込めるものだけに絞る。書き込めるのは、ロックされておらず、
                animCurve以外からの入力の接続が無いもの(親・子のロックと入力も見る)。
                animCurveが直接つながったものは含める。既定はFalse。
            animatable (bool): Trueなら、``cmds.listAnimatable`` が返すアトリビュートを返す。既定はFalse。
                ほかの引数(userDefined・includeChildren・writable・listAttrのフラグ)とは同時に指定できない。
            **listAttrFlags: ``userDefined=False`` のときに ``cmds.listAttr`` へ渡すフラグ。

        Returns:
            Plugs: 新しいリスト。userDefinedでは追加した順、それ以外はlistAttrの順。
                解決できないパスは省き、見つからなければ空リスト。
                名前が必要なら ``[plug.getAttributeName() for plug in ...]`` を使う。

        Raises:
            TypeError: userDefined・includeChildren・writable・animatableがboolでない場合、
                userDefined=TrueとlistAttrのフラグを同時に指定した場合、
                またはanimatable=Trueとほかの引数を同時に指定した場合。
            RuntimeError: ノードが無効な場合、listAttr・listAnimatableが失敗した場合、
                またはuserDefined=TrueかつincludeChildren=Trueで、マルチアトリビュートである
                コンパウンドアトリビュートの子(番号を指定していないもの)が含まれる場合。
        """
        ...
    def getAttrNames(self, **listAttrFlags) -> list[str]:
        """アトリビュートの名前の一覧を、``cmds.listAttr`` と同じ名前・順で取得する。

        :meth:`getPlugs` はPlugにできない名前(番号を決めていないマルチアトリビュートの子、
        ``instObjGroups.objectGroups.objectGroupId`` など)を省くが、このメソッドは省かない。
        表示・記録のために ``cmds.listAttr`` と同じ一覧が要るときに使う。シーンは変更しない。

        Args:
            **listAttrFlags: ``cmds.listAttr`` へそのまま渡すフラグ(``keyable=True`` など)。

        Returns:
            list[str]: アトリビュートの名前(``cmds.listAttr`` の形)。見つからなければ空リスト。

        Raises:
            TypeError: listAttrが受け付けないフラグを指定した場合。
            RuntimeError: ノードが無効な場合、またはlistAttrが失敗した場合。
        """
        ...
    def getAliases(self) -> list[tuple[str, Plug]]:
        """このノードのアトリビュートのエイリアス(別名)を取得する。

        Returns:
            list[tuple[str, Plug]]: ``(エイリアス名, 対応するPlug)`` のリスト。
                エイリアスが無ければ空リスト。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def addAttr(self, longName: str = ..., type: str | None = ..., subType: str | None = ..., channelBox: bool = ..., childNames: Sequence[str] | None = ..., childShortNames: Sequence[str] | None = ..., childSuffixes: Sequence[str] | None = ..., proxy: Plug | str | None = ..., getPlug: bool = ..., *, skipExisting: bool = ..., fast: bool = ..., unit: str = ..., timeUnit: str = ..., attributeType: str = ..., at: str = ..., binaryTag: str = ..., bt: str = ..., cachedInternally: bool = ..., ci: bool = ..., category: str | Sequence[str] = ..., ct: str | Sequence[str] = ..., dataType: str | Sequence[str] = ..., dt: str | Sequence[str] = ..., defaultValue: object = ..., dv: object = ..., disconnectBehaviour: int = ..., dcb: int = ..., edit: bool = ..., e: bool = ..., enforcingUniqueName: bool = ..., eun: bool = ..., enumName: str = ..., en: str = ..., exists: bool = ..., ex: bool = ..., fromPlugin: bool = ..., fp: bool = ..., hasMaxValue: bool = ..., hxv: bool = ..., hasMinValue: bool = ..., hnv: bool = ..., hasSoftMaxValue: bool = ..., hsx: bool = ..., hasSoftMinValue: bool = ..., hsn: bool = ..., hidden: bool = ..., h: bool = ..., indexMatters: bool = ..., im: bool = ..., internalSet: bool = ..., keyable: bool = ..., k: bool = ..., ln: str = ..., maxValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., max: float | om2.MAngle | om2.MDistance | om2.MTime = ..., minValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., min: float | om2.MAngle | om2.MDistance | om2.MTime = ..., multi: bool = ..., m: bool = ..., niceName: str = ..., nn: str = ..., numberOfChildren: int = ..., nc: int = ..., parent: str = ..., p: str = ..., pxy: Plug | str | None = ..., query: bool = ..., q: bool = ..., readable: bool = ..., r: bool = ..., shortName: str = ..., sn: str = ..., softMaxValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., smx: float | om2.MAngle | om2.MDistance | om2.MTime = ..., softMinValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., smn: float | om2.MAngle | om2.MDistance | om2.MTime = ..., storable: bool = ..., s: bool = ..., usedAsColor: bool = ..., uac: bool = ..., usedAsFilename: bool = ..., uaf: bool = ..., usedAsProxy: bool = ..., uap: bool = ..., worldSpace: bool = ..., ws: bool = ..., writable: bool = ..., w: bool = ..., cb: bool = ..., **kwargs) -> Plug | None:
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
            skipExisting (bool): Trueなら、何度実行しても同じ結果になるようにする。同じ名前のアトリビュートがすでにあれば
                何も変えずに、そのPlug(getPlug=FalseならNone)を返す。既存の既定値・範囲・表示などは変えない。
                ただし、既存のアトリビュートの型(getType()で比べる)や、マルチアトリビュートかどうかが
                指定と違う場合は、skipExistingでもTypeErrorにする。既定のFalseでは、名前が重なるとMayaのエラー
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
            TypeError: ロング名と短縮名を同時に指定した場合、fast・skipExistingがbool以外の場合、
                unitが文字列・None以外の場合、単位のある型の既定値・範囲が数値でも単位付きの値でもない場合、
                またはskipExisting=Trueで、既存のアトリビュートの型やマルチアトリビュートかどうかが指定と違う場合。
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
        ...
    def moveAttrOrder(self, name: str, offset: int) -> None:
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
            None: 値を返さない。すべての変更を1回のUndoにまとめる。

        Raises:
            TypeError: 作り直す範囲に、コンパウンドアトリビュート・マルチアトリビュート・対応していない型の
                アトリビュートが含まれる場合。cmdsで作り直せないnon-connectableの定義も、変更する前に拒否する。
            ValueError: nameが、トップレベルのユーザー定義のアトリビュートの一覧に無い場合。
            RuntimeError: ノードが無効な場合、または安全に元へ戻すために必要なUndoが無効な場合。
        """
        ...
    def getPlug(self, name: str) -> Plug:
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
                ``AttributeError`` の派生で、``mlib.getPlug("node.name")`` と同じ例外。
            AttributeError: 論理番号が上限を超える場合。
        """
        ...
    def hasAttr(self, name: str) -> bool:
        """アトリビュートがあるか調べる。

        :meth:`getPlug` で取得できるかどうかで判定する。

        Args:
            name (str): アトリビュート名か、アトリビュートのパス。

        Returns:
            bool: アトリビュートを取得できれば ``True``。
        """
        ...
    def getExternalContent(self) -> list[dict[str, str | list[str]]]:
        """ノードがMayaへ申告している外部ファイル情報を取得する。

        ファイルの存在や連番・UDIMの全ファイルを独自に調べることはしない。
        未解決のパスや、情報を申告しないノードでは空の値・一覧になる場合がある。

        Returns:
            list[dict[str, str | list[str]]]: Mayaの登録順の独立した辞書。keyは識別名、unresolvedLocationは元のパス、
                resolvedLocationは解決後のパス、contextNodeFullNameは所有ノード名、rolesは用途名のリスト。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def getUuid(self) -> str | None:
        """ノードのMayaのUUIDを取得する。

        Returns:
            str | None: ノードのUUID。ノードが無効なら ``None``。
        """
        ...
    def getName(self, *, full: bool = ..., node: bool = ..., removeNamespace: bool = ...) -> str:
        """最短の一意な名前を取得する。``full=True`` なら完全な名前、``node=True`` ならDAGパスを付けないノード名を取得する。

        既定の名前は、Mayaのコマンドへ渡すと、このオブジェクトが持つインスタンスを指せる名前になる。

        - DAGノード: このオブジェクトが持つDAGパスのpartialPathName。
        - DGノード: ノード名。

        名前は覚えておかず、呼ぶたびにMayaから取得する。
        別の階層に同じ短い名前のノードがあると、一意にするために親を含む部分的なパス(``grp1|ctrl`` など)になる。

        ``node=True`` では、DAGの別の階層に同じ名前のノードがあっても、親のパスは付けない(DGノードにも使える)。
        新しい名前を組み立てる元にするとき(接尾辞の付け替えなど)に使う。Mayaのコマンドへ渡す一意な名前が要るときは、既定のままにする。

        ``full=True`` では、DAGノードはこのオブジェクトが持つインスタンスの完全なDAGパス(``|grp1|ctrl``)、DGノードはノード名を返す。
        ノードそのものが無効なら、例外にせず空文字列を返す。

        Args:
            full (bool): Trueなら、完全な名前を返す。node・removeNamespaceと同時には指定できない。既定はFalse。
            node (bool): Trueなら、DAGパスを付けないノード名(ネームスペースは含む)を返す。既定はFalse。
            removeNamespace (bool): Trueなら、ネームスペースも取り除く。``node=True`` のときだけ指定できる。既定はFalse。

        Returns:
            str: 今の名前。``full=True`` でノードが無効なら空文字列。

        Raises:
            TypeError: full・node・removeNamespaceがboolでない場合、``full=True`` とnode・removeNamespaceを同時に指定した場合、
                または ``node=True`` なしでremoveNamespaceを指定した場合。
            RuntimeError: ノードが削除済みか、Undoで作成が取り消された(無効な)場合(``full=True`` を除く)、
                またはノードは有効だが、このオブジェクトが持つDAGパスのインスタンスが削除された場合(既定の名前と ``full=True`` のとき)。
        """
        ...
    def _full_name(self) -> str:
        """完全な名前(:meth:`getName` の ``full=True``)を、引数の検査なしで取得する。

        maya.cmdsへ名前を渡す内部の処理から、毎回の引数の検査を省いて呼ぶ。

        Returns:
            str: DAGノードではワールドから始まる完全なパス。DGノードではノード名。
                ノードそのものが無効なら空文字列。

        Raises:
            RuntimeError: ノードは有効だが、このオブジェクトが持つDAGパスのインスタンスが削除された場合。
        """
        ...
    def _list_plugs(self, userDefined, includeChildren, listAttrFlags):
        """:meth:`getPlugs` の列挙の本体(writableで絞る前)。"""
        ...
    def _plugs_from(self, attributes: str | Plug | Iterable[str | Plug]) -> list[Plug]:
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
        ...
    @staticmethod
    def _create_node(node_type: str, flags: dict, *, fast: bool = ..., classification: str | None = ...) -> Node:
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
            classification (str | None): ``"asShader"`` など、``cmds.shadingNode`` で作るときの分類のフラグ名。
                Noneなら ``cmds.createNode`` で作る。fastとは組み合わせない(呼出し側で拒否する)。

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
        ...
    @staticmethod
    def _connect_joint_parent(node: Node, parent: str | None, *, fast: bool) -> Node:
        """jointの下へ作ったjointの inverseScale へ、親の scale を接続する(``cmds.joint`` と同じ)。

        Args:
            node (Node): 作成したノード。
            parent (str | None): 作成時に指定した親の完全パス。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            Node: node。jointでない、または親がjointでない場合は何もしない。
        """
        ...
    def _has_delete_connections(self) -> bool:
        """自身とDAG子孫のDG接続をOMで検査する。

        Returns:
            bool: 接続が一つでもあればTrue。DAG階層関係自体は接続に数えない。
        """
        ...
    @staticmethod
    def _selection_owner(selection: om2.MSelectionList, index: int, name: str | None = ..., plug: bool = ...) -> tuple[om2.MObject, om2.MDagPath | None]:
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
        ...
    @staticmethod
    def _unique_node_name(mobject: om2.MObject) -> str:
        """ノードの MObject から maya.cmds で一意に解決できる最短名を返す。

        DAG ノードは最初のインスタンスの最短一意パス(``MDagPath.partialPathName()``)、
        DG ノードはノード名を返す。``Node.getName()`` と同じ規則。

        Args:
            mobject (om2.MObject): 依存ノードの MObject。

        Returns:
            str: 最短一意名。
        """
        ...
    @staticmethod
    def _mobject_name(mobject: om2.MObject) -> str:
        """依存ノードの MObject を完全 DAG パスまたは DG ノード名へ変換する。

        Args:
            mobject (om2.MObject): 変換対象。

        Returns:
            str: 完全 DAG パス(最初のインスタンス)、または DG ノード名。

        Raises:
            TypeError: アトリビュート・コンポーネント・データなど依存ノード以外を指す場合。
            ValueError: 空、または削除済みノードの MObject の場合。
        """
        ...
    @staticmethod
    def _resolve_input(value: Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug) -> Node:
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
                (:class:`DeletedAttributeError`)。
            RuntimeError: 名前を解決できない(存在しない、または複数のノードに一致する)場合、
                または空・削除済みのノードを指す om2 オブジェクトの場合(``Node(value)`` と同じ)。
        """
        ...
    @staticmethod
    def _input_name(value: str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug) -> str:
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
        ...
    def _resolve(self, node: str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug) -> None:
        """ノードを表す入力を内部 API オブジェクトへ変換する。

        Args:
            node (str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug):
                対象ノードを表す入力(_resolve_node と同じ)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対応しないノード入力型の場合。
            ValueError: アトリビュートが ``deleteAttr`` で削除済みの Plug・MPlug の場合
                (``DeletedAttributeError``)。
            RuntimeError: ノード名を解決できない場合。
        """
        ...
    def _alive_fn(self) -> om2.MFnDependencyNode:
        """破棄されていないことを確かめて、保持するノードの MFnDependencyNode を返す。

        Undo の記録から消えて破棄されたノード(削除後の flushUndo 等)へ関数セットを作ると
        Maya が異常終了するため、その前に RuntimeError にする。Undo で戻せる削除済みノード
        (生存中)は従来どおり問い合わせる。

        Returns:
            om2.MFnDependencyNode: このノードの関数セット。

        Raises:
            RuntimeError: ノードが破棄されている場合。
        """
        ...
    def _api1_object(self):
        """API 1.0専用の照会に渡すMObjectを、その都度名前から解決する。"""
        ...
    def _dependency_fn(self) -> om2.MFnDependencyNode:
        """保持するノードの MFnDependencyNode を返す(作成は初回の1回だけ)。

        名前・アトリビュートの問い合わせのたびに関数セットを作り直さないためのキャッシュ。
        ノードが有効(:meth:`isValid`)であることを呼び出し側で確かめてから使う。

        Returns:
            om2.MFnDependencyNode: このノードの関数セット。
        """
        ...
    @staticmethod
    def _wrap_dag_path(dag_path: om2.MDagPath) -> DagNode:
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
        ...
    @staticmethod
    def _wrap_resolved(mobject: om2.MObject, dag_path: om2.MDagPath | None, handle: om2.MObjectHandle | None = ...) -> Node:
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
        ...
    @staticmethod
    def _from_name(value: str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug) -> Node:
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
        ...
    def _require_named(self) -> None:
        """名前の取得の前にノードが有効か確かめる。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが削除済み、またはUndoで作成が取り消された場合。
        """
        ...
    def _require_valid(self, action: str) -> None:
        """操作の前にノードが有効か確かめ、無効なら統一した文言で拒否する。

        Args:
            action (str): 例外メッセージに使う動作の名詞句(``"名前の変更"``・``"削除"`` 等)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが削除済み・無効な場合。文言は
                ``無効な<クラス名>のため、<action>はできません``。
        """
        ...
    def _current_dag_path(self) -> om2.MDagPath | None:
        """このオブジェクトが持つDAGパスを返す。消えたインスタンスを、別のパスへ切り替えない。

        ノードごと削除された場合は、Undoの記録に残る間(MDagPathが有効のまま古いパスを返す間)も
        無効として扱う。

        Returns:
            om2.MDagPath | None: 保持しているパス。非DAGはNone。

        Raises:
            RuntimeError: 保持しているDAGインスタンス、またはノード自体が削除された場合。
        """
        ...
    @staticmethod
    def _prepare_extra_attr_definition(flags: dict, attribute_type: str | None, child_names: Sequence[str] | None, child_short_names: Sequence[str] | None, child_suffixes: Sequence[str] | None, *, sub_type: str | None = ..., angle_unit: str = ..., time_unit: str = ...) -> tuple:
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
        ...
    def _create_extra_attr_definition(self, name: str, flags: dict, numeric: object, count: int, deferred: object, child_names: Sequence[str] | None, child_short_names: Sequence[str] | None, child_suffixes: Sequence[str] | None, sub_type: str | None, *, fast: bool = ..., time_unit: str = ...):
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
        ...
    def _listed_attributes(self, include_children: bool = ..., keyable: bool = ..., scalar: bool = ...) -> list[om2.MObject]:
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
        ...
    def _user_attributes(self, include_children: bool = ...) -> Iterator[om2.MObject]:
        """動的アトリビュートの定義を追加順に列挙する。

        Args:
            include_children (bool): Trueならコンパウンドアトリビュートの子の定義も含める。

        Yields:
            om2.MObject: アトリビュート定義。マルチアトリビュートの要素の取得・作成は行わない。
        """
        ...


_NodeT = TypeVar("_NodeT", bound=Node, default=Node, covariant=True)
class Nodes(_ListMethods, Generic[_NodeT]):
    """複数のノードを、渡した順にまとめて持つクラス。

    要素の型は、まとめるときに確かめる。

    - 同じノードで同じDAGパスのものだけを1つにまとめる。インスタンスのパスが違えば別の要素として持つ。
    - コピーやスライスは、同じNodeのオブジェクトを共有する。シーンのノードは複製しない。
    - ``len``・番号での取り出し(sliceなら同じ型)・``for``・``bool``・``in``・``+``・``==``・:meth:`sort` が使える。
    - 一覧を返す取得系のメソッドや ``mlib.ls`` は、要素がすべてJointならJoints、すべてSkinClusterならSkinClustersで返す。
    - Pythonのlistと同じ名前の ``append``・``extend``・``insert``・``remove``・``pop``・``index``・``count``・``clear``・``reverse`` と、
      番号への代入・``del``・``+=`` も使える。足す値は作るときと同じ決まりで確かめ、すでにある要素は足さない。
      これらの名前は、各要素の同じ名前のメソッドへは転送しない(転送するときは :meth:`callEach` を使う)。
    - そのまま ``maya.cmds`` へ渡せる(cmdsが並びとして、各ノードの名前へ展開する)。
    - ``==`` を定義しているので、listと同じくハッシュできない(dictのキーやsetの要素にできない)。

    ``item_class`` は、派生のクラス(:class:`~mlib.nodes.joint.Joints` など)が受け付ける要素の型を
    宣言するクラス属性。
    """
    def __iter__(self) -> Iterator[_NodeT]: ...
    @overload
    def __getitem__(self, index: int) -> _NodeT: ...
    @overload
    def __getitem__(self, index: slice) -> Nodes[_NodeT]: ...
    item_class: Any
    __hash__: None
    def __init__(self, names: object | Iterable[object] = ...) -> None:
        """入力からノードを解決し、要素の型を確かめてから持つ。

        Args:
            names (object | Iterable[object]): 名前・Node・APIのオブジェクトなど、またはその並び。
                名前を1つだけ渡してもよい。

        Raises:
            TypeError: 解決したノードがitem_classの派生でない場合。
            ValueError: 入力を解決するときに、不正なものが見つかった場合。
            RuntimeError: 名前を解決できない場合、または無効なノードの場合。
        """
        ...
    def __len__(self) -> int:
        """要素の数を返す。

        Returns:
            int: 要素の数。
        """
        ...
    def __repr__(self) -> str:
        """クラス名と要素を表す文字列を返す。

        Returns:
            str: クラス名と、持っている要素を表す文字列。
        """
        ...
    def __eq__(self, other: Nodes | list | tuple) -> bool:
        """同じ並びのノードを持っているか比べる。

        Args:
            other (Nodes | list | tuple): 比べる相手。Nodesの派生の型の違いは問わない。

        Returns:
            bool: 要素の数が同じで、同じ位置のNodeどうしが ``==`` で等しければTrue。
                対応していない型ならNotImplemented。
        """
        ...
    def __getattr__(self, name: str) -> Callable[..., list]:
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
        ...
    def __add__(self, other: Nodes | list | tuple) -> Nodes:
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
        ...
    def __radd__(self, other: list | tuple) -> Nodes:
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
        ...
    def sort(self, key: Callable[[Node], object] | None = ..., reverse: bool = ...) -> None:
        """要素をその場で並べ替える。

        ``key`` を省くと、ノードの完全な名前(``Node.getName(full=True)``)の順にする。
        Nodeは大小を比べられないため、Pythonのlistと違い、要素そのものは比べない。
        並べ替えるのはこのまとまりの要素の順だけ。:meth:`copy`・スライス・``+`` で作った
        別のまとまりの順は変わらない(各要素のNodeのオブジェクトは共有している)。

        Args:
            key (Callable[[Node], object] | None): 各Nodeから、比べるための値を返す関数。Noneなら完全な名前。
            reverse (bool): Trueなら大きい順にする。既定はFalse。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: keyが呼び出せないものの場合、またはreverseがbool以外の場合。
            RuntimeError: keyを省いたときに、無効なノードを含む場合。
        """
        ...
    def resetAttrs(self, attributes: str | Iterable[str] | None = ..., *, fast: bool = ..., check: bool = ...) -> Plugs:
        """各ノードへ、順に :meth:`Node.resetAttrs` を呼ぶ。

        Args:
            attributes (str | Iterable[str] | None): :meth:`Node.resetAttrs` と同じ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            Plugs: すべての要素で既定値へ戻したアトリビュート(要素の順)。通常は1回のUndoにまとめる。

        Raises:
            AttributeError: :meth:`Node.resetAttrs` と同じ。
            TypeError: :meth:`Node.resetAttrs` と同じ。
            RuntimeError: 無効なノードを含む場合、またはアトリビュートを書き込めない場合。
        """
        ...
    def getColor(self, *, outliner: bool = ..., shape: bool = ...) -> list[int | tuple[float, float, float] | None]:
        """各DAGノードの :meth:`~mlib.nodes.dagNode.DagNode.getColor` を、要素の順に取得する。

        Args:
            outliner (bool): :meth:`~mlib.nodes.dagNode.DagNode.getColor` と同じ。既定False。
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.getColor` と同じ。既定False。

        Returns:
            list[int | tuple[float, float, float] | None]: 各ノードの表示色。

        Raises:
            TypeError: DAGノード以外を含む場合。
            RuntimeError: 無効なノードを含む場合。
        """
        ...
    def setColor(self, color: object, *, outliner: bool = ..., shape: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """各DAGノードへ、順に :meth:`~mlib.nodes.dagNode.DagNode.setColor` を呼ぶ。

        Args:
            color (object): :meth:`~mlib.nodes.dagNode.DagNode.setColor` と同じ。
            outliner (bool): :meth:`~mlib.nodes.dagNode.DagNode.setColor` と同じ。既定False。
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.setColor` と同じ。既定False。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。通常は全体を1回のUndoにまとめる。

        Raises:
            TypeError: DAGノード以外を含む、色の指定が不正、またはoutliner・fastがbool以外の場合。
            ValueError: 色の指定が不正な場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        ...
    def setColors(self, colors: Iterable[object], *, outliner: bool = ..., shape: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """各DAGノードへ、それぞれ違う色で :meth:`~mlib.nodes.dagNode.DagNode.setColor` を呼ぶ。

        Args:
            colors (Iterable[object]): ノードと同じ数の色。要素の順に1色ずつ使う。書き込む前に、すべての色を確かめる。
            outliner (bool): :meth:`~mlib.nodes.dagNode.DagNode.setColor` と同じ。既定False。
            shape (bool): :meth:`~mlib.nodes.dagNode.DagNode.setColor` と同じ。既定False。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。通常は全体を1回のUndoにまとめる。

        Raises:
            TypeError: DAGノード以外を含む、色の指定が不正、またはoutliner・shape・fastがbool以外の場合。
            ValueError: 色の数がノードの数と違う、または色の指定が不正な場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        ...
    def setVisibility(self, state: bool = ..., *, fast: bool = ..., check: bool = ...) -> None:
        """各DAGノードへ、順に :meth:`~mlib.nodes.dagNode.DagNode.setVisibility` を呼ぶ。

        Args:
            state (bool): Trueなら表示、Falseなら非表示にする。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: DAGノード以外を含む、またはstate・fastがbool以外の場合。
            RuntimeError: 無効なノードを含む、またはMayaが更新を拒否した場合。
        """
        ...
    def setParent(self, parent: object | None = ..., *, relative: bool = ..., add: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """各Transformへ、順に :meth:`~mlib.nodes.transform.Transform.setParent` を呼ぶ。

        Args:
            parent (object | None): 親。Noneならワールド。
            relative (bool): :meth:`~mlib.nodes.transform.Transform.setParent` と同じ。
            add (bool): :meth:`~mlib.nodes.transform.Transform.setParent` と同じ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。各要素は、親を変えた後のパスを指す。

        Raises:
            TypeError: Transform以外を含む場合。
            ValueError: :meth:`~mlib.nodes.transform.Transform.setParent` と同じ。
            RuntimeError: 無効なノードを含む場合、parentがどれかの要素自身かその子孫の場合、
                またはMayaが親の変更を拒否した場合。parentは、どの要素も変える前に確かめる。
        """
        ...
    def getNames(self, *, full: bool = ...) -> list[str]:
        """各ノードの名前を取得する。

        既定は一意な名前(:meth:`Node.getName` を並べたもの)。``full=True`` なら完全な名前
        (``Node.getName(full=True)`` を並べたもの)。

        Args:
            full (bool): Trueなら、DAGノードではワールドから始まる完全なパス(DGノードではノード名)を返す。既定はFalse。

        Returns:
            list[str]: 要素の順のノード名。

        Raises:
            TypeError: fullがboolでない場合。
            RuntimeError: 無効な(削除済みの)ノードを含む場合。full=Trueでは、文言に要素の番号(0から)を含む。
        """
        ...
    def select(self, **kwargs: object) -> None:
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
        ...
    def callEach(self, method: str, *args: object, **kwargs: object) -> list:
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
        ...
    def copy(self) -> Nodes:
        """同じ型の、別のまとまりを作って返す。

        要素のNodeのオブジェクトは共有する。並べ替えなどは、元のまとまりに影響しない。

        Returns:
            Nodes: 同じNodeを共有する、同じ型の新しいまとまり。
        """
        ...
    @classmethod
    def _wrap(cls, items: Iterable[Node]) -> Nodes:
        """すでに確かめてあるNodeの並びから、解決と検査を省いて作る(取得系のメソッドの戻り値で使う)。

        Args:
            items (Iterable[Node]): 有効で、重なりの無いNodeの並び。同じ型の集まりならその要素を写す。

        Returns:
            Nodes: itemsを持っている順のまま持つ、新しい集まり。Nodesとして作るときに、要素がすべて
                Joint(またはSkinCluster)なら、JointsやSkinClustersにする(要素が無ければNodes)。
                こうして自動で決まった型の集まりは、あとで型の合わない要素を足すとNodesへ戻る
                (:meth:`_resolve_new_items`・``+``)。``Joints([...])`` のように自分で作った集まりは、これまでどおりTypeErrorにする。
        """
        ...
    def _resolve_new_items(self, values: list[object]) -> list[Node]:
        """これから足す値の並びをNodeへ解決して確かめる。自動で決まった型に合わない要素があれば、自身をNodesへ戻す。

        Args:
            values (list[object]): 足す値の並び。

        Returns:
            list[Node]: 解決したノードの並び。

        Raises:
            TypeError: 自分で作った集まり(``Joints([...])`` など)に、型の合わない要素を足そうとした場合。
            RuntimeError: 名前を解決できない場合、または無効なノードの場合。
        """
        ...
    def _resolve_item(self, value: object) -> Node:
        """追加する値をNodeへ解決し、有効か・要素の型が合うかを確かめる。

        Args:
            value (object): 名前・Node・APIのオブジェクトなど。

        Returns:
            Node: 解決したノード。

        Raises:
            TypeError: 解決したノードがitem_classの派生でない場合。
            RuntimeError: 名前を解決できない場合、または無効なノードの場合。
        """
        ...
    def _forward(self, method: str, args: tuple, fast: bool | None, *, writes: Callable[[Node], Iterable[Plug]] | None = ..., **kwargs: object) -> list:
        """保持順の各ノードへ単数のメソッドを適用し、結果の列を返す。

        全要素がメソッドを持ち有効であることを書込みの前に確かめ、通常は1回のUndoにまとめる。

        Args:
            method (str): 単数のノードのメソッド名。
            args (tuple): 位置引数。
            fast (bool | None): メソッドへ渡すfast。Noneはfast引数の無いメソッド。
            writes (Callable[[Node], Iterable[Plug]] | None): ``check=True`` のとき、書く前に全要素で
                確かめる書き込み先を、ノードごとに返す関数。Noneなら前もって確かめない。
            **kwargs (object): メソッドへそのまま渡すキーワード引数。

        Returns:
            list: 要素順の戻り値。

        Raises:
            TypeError: メソッドを持たない要素を含む場合、またはfastがbool以外の場合。
            RuntimeError: 無効な要素を含む場合、またはwritesの書き込み先に書き込めない場合。
        """
        ...
    @staticmethod
    def _require_writable_targets(plugs: Iterable[Plug]) -> None:
        """``check=True`` の書き込みの前に、全要素の書き込み先へ書き込めるかを確かめる。シーンは変えない。

        途中の要素で止まって、手前の要素だけが書き換わるのを防ぐために使う。

        Args:
            plugs (Iterable[Plug]): 書き込むPlug。コンパウンドアトリビュートは子も確かめる。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ロックや入力の接続などで、書き込めないPlugがある場合。
        """
        ...
    @staticmethod
    def _color_plugs(outliner: bool, node: DagNode, color: object, shape: bool) -> list[Plug]:
        """表示色の設定(``setColor``)で、nodeについて書き込むPlugを返す。

        Args:
            outliner (bool): Trueならアウトライナーの文字色、Falseなら描画のオーバーライドの色。
            node (DagNode): 設定するノード。
            color (object): 設定する色。
            shape (bool): 確かめ済みのshape。

        Returns:
            list[Plug]: 書き込むPlug。
        """
        ...
    def _require_method(self, method: str) -> None:
        """全要素が単数のメソッドを持つことを確かめる。

        Args:
            method (str): 単数のノードのメソッド名。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: メソッドを持たない要素を含む場合。
        """
        ...
    @staticmethod
    def _resolve_inputs(values: object) -> list:
        """対象列を一度だけ展開し、名前とNodeの混在を変換前に拒否する。

        Args:
            values (object): 単体、または対象の反復可能列。既存のAPI型も保持する。

        Returns:
            list: 入力順の対象。空列は空のまま返す。

        Raises:
            TypeError: 同じ対象列に文字列とNodeが混在している場合。
        """
        ...
    @staticmethod
    def _items_of(values: Nodes | list | tuple) -> list[Node]:
        """結合の相手を単独で解決し、Node参照のlistを返す。

        Args:
            values (Nodes | list | tuple): 結合の相手。

        Returns:
            list[Node]: 相手の保持順のNode参照。Nodesはそのまま、列はNodesの構築と同じ規則で解決する。
        """
        ...
    @staticmethod
    def _duplicate_key(node: Node) -> tuple[str | None, str]:
        """構築時の重複判定に使うキーを返す。

        Args:
            node (Node): 有効なノード参照。

        Returns:
            tuple[str | None, str]: UUIDと、DAGの完全パスまたはDGのノード名。
        """
        ...
    @staticmethod
    def _validate_inputs(values: list) -> None:
        """展開済み対象列の名前とNodeの混在を拒否する。

        Args:
            values (list): Objectが展開した対象列。値の変換は行わない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 名前とNodeが混在する場合。
        """
        ...
    def getShadingEngines(self) -> list[Nodes[ShadingEngine]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getShadingEngines` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def sameNode(self, other: object) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.sameNode` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isValid(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isValid` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isAlive(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isAlive` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mnode(self) -> list[om2.MObject]:
        """各要素の :meth:`~mlib.nodes.node.Node.mnode` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDgTimer(self, metric: int | None = ..., *, timerType: int = ..., callbacks: bool = ..., state: bool = ...) -> list[float | list[tuple[str, float]] | int]:
        """各要素の :meth:`~mlib.nodes.node.Node.getDgTimer` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setDgTimer(self, state: bool | None = ..., *, reset: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.setDgTimer` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mfn(self) -> list[om2.MFnDependencyNode]:
        """各要素の :meth:`~mlib.nodes.node.Node.mfn` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getType(self, inherited: bool = ...) -> list[str | list[str]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def hasFn(self, fn: int) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.hasFn` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getClassification(self) -> list[list[str]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getClassification` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isClassified(self, classification: str) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isClassified` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isType(self, nodeType: str) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isLocked(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setLocked(self, state: bool = ..., *, fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.setLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isFromReferencedFile(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isFromReferencedFile` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def swapConnections(self, other: Node | str) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.swapConnections` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getContainer(self) -> list[Container | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.getContainer` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getReference(self) -> list[Reference | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.getReference` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def hasUniqueName(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.hasUniqueName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSets(self, *, type: str | None = ...) -> list[Nodes[ObjectSet]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getSets` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isAncestorOf(self, other: Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug, *, direct: bool = ...) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isAncestorOf` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNamespace(self) -> list[Namespace]:
        """各要素の :meth:`~mlib.nodes.node.Node.getNamespace` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setNamespace(self, namespace: str | Namespace, *, fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.setNamespace` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def delete(self, *, skipConnected: bool = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.delete` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def rename(self, name: str, ignoreShape: bool = ..., *, fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.rename` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def duplicate(self, name: str | None = ..., *, suffix: str | None = ..., **kwargs: object) -> list[Node]:
        """各要素の :meth:`~mlib.nodes.node.Node.duplicate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: bool = ..., asNode: bool = ..., index: int | None = ...) -> list[Plugs | Nodes | list | Plug | Node | tuple | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.getConnections` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setKey(self, attributes: str | Iterable[str] | None = ..., *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., **kwargs) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.setKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def removeKey(self, attributes: str | Iterable[str] | None = ..., *, time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.removeKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def moveKey(self, attributes: str | Iterable[str] | None = ..., *, time: float | Sequence[float] | None = ..., timeOffset: float = ..., valueOffset: float = ..., unit: str | None = ..., timeUnit: str | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.moveKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setKeyTangent(self, attributes: str | Iterable[str] | None = ..., *, inTangentType: str | None = ..., outTangentType: str | None = ..., time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.setKeyTangent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getHistory(self, *, type: str | None = ..., future: bool = ...) -> list[Nodes]:
        """各要素の :meth:`~mlib.nodes.node.Node.getHistory` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def findCycles(self) -> list[list[list[Plug]]]:
        """各要素の :meth:`~mlib.nodes.node.Node.findCycles` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setAttrFlags(self, attributes: str | Plug | Iterable[str | Plug], *, locked: bool | None = ..., keyable: bool | None = ..., channelBox: bool | None = ..., children: bool = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.setAttrFlags` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPlugs(self, userDefined: bool = ..., includeChildren: bool = ..., *, writable: bool = ..., animatable: bool = ..., **listAttrFlags) -> list[Plugs]:
        """各要素の :meth:`~mlib.nodes.node.Node.getPlugs` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getAttrNames(self, **listAttrFlags) -> list[list[str]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getAttrNames` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getAliases(self) -> list[list[tuple[str, Plug]]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getAliases` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def addAttr(self, longName: str = ..., type: str | None = ..., subType: str | None = ..., channelBox: bool = ..., childNames: Sequence[str] | None = ..., childShortNames: Sequence[str] | None = ..., childSuffixes: Sequence[str] | None = ..., proxy: Plug | str | None = ..., getPlug: bool = ..., *, skipExisting: bool = ..., fast: bool = ..., unit: str = ..., timeUnit: str = ..., attributeType: str = ..., at: str = ..., binaryTag: str = ..., bt: str = ..., cachedInternally: bool = ..., ci: bool = ..., category: str | Sequence[str] = ..., ct: str | Sequence[str] = ..., dataType: str | Sequence[str] = ..., dt: str | Sequence[str] = ..., defaultValue: object = ..., dv: object = ..., disconnectBehaviour: int = ..., dcb: int = ..., edit: bool = ..., e: bool = ..., enforcingUniqueName: bool = ..., eun: bool = ..., enumName: str = ..., en: str = ..., exists: bool = ..., ex: bool = ..., fromPlugin: bool = ..., fp: bool = ..., hasMaxValue: bool = ..., hxv: bool = ..., hasMinValue: bool = ..., hnv: bool = ..., hasSoftMaxValue: bool = ..., hsx: bool = ..., hasSoftMinValue: bool = ..., hsn: bool = ..., hidden: bool = ..., h: bool = ..., indexMatters: bool = ..., im: bool = ..., internalSet: bool = ..., keyable: bool = ..., k: bool = ..., ln: str = ..., maxValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., max: float | om2.MAngle | om2.MDistance | om2.MTime = ..., minValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., min: float | om2.MAngle | om2.MDistance | om2.MTime = ..., multi: bool = ..., m: bool = ..., niceName: str = ..., nn: str = ..., numberOfChildren: int = ..., nc: int = ..., parent: str = ..., p: str = ..., pxy: Plug | str | None = ..., query: bool = ..., q: bool = ..., readable: bool = ..., r: bool = ..., shortName: str = ..., sn: str = ..., softMaxValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., smx: float | om2.MAngle | om2.MDistance | om2.MTime = ..., softMinValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., smn: float | om2.MAngle | om2.MDistance | om2.MTime = ..., storable: bool = ..., s: bool = ..., usedAsColor: bool = ..., uac: bool = ..., usedAsFilename: bool = ..., uaf: bool = ..., usedAsProxy: bool = ..., uap: bool = ..., worldSpace: bool = ..., ws: bool = ..., writable: bool = ..., w: bool = ..., cb: bool = ..., **kwargs) -> list[Plug | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.addAttr` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def moveAttrOrder(self, name: str, offset: int) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.moveAttrOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPlug(self, name: str) -> list[Plug]:
        """各要素の :meth:`~mlib.nodes.node.Node.getPlug` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def hasAttr(self, name: str) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.hasAttr` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getExternalContent(self) -> list[list[dict[str, str | list[str]]]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getExternalContent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUuid(self) -> list[str | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.getUuid` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getName(self, *, full: bool = ..., node: bool = ..., removeNamespace: bool = ...) -> list[str]:
        """各要素の :meth:`~mlib.nodes.node.Node.getName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSetsAndMembers(self, *, renderableOnly: bool = ...) -> list[list[tuple[ObjectSet, list[Components] | None]]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getSetsAndMembers` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSkinClusters(self) -> list[SkinClusters]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getSkinClusters` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBindPoses(self) -> list[Nodes[DagPose]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getBindPoses` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mpath(self) -> list[om2.MDagPath]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.mpath` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getRoot(self) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getRoot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getCommonAncestor(self, other: DagNode | str | om2.MObject | om2.MDagPath) -> list[DagNode | None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getCommonAncestor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSiblings(self) -> list[Nodes[DagNode]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getSiblings` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getOutlinerOrder(self) -> list[int]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getOutlinerOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def reorder(self, *, index: int | None = ..., front: bool = ..., f: bool = ..., back: bool = ..., b: bool = ..., relative: int = ..., r: int = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.reorder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isInUnderworld(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isInUnderworld` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isInModel(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isInModel` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBoundingBox(self, worldSpace: bool = ..., *, ws: bool = ..., includeInvisible: bool = ..., corners: bool = ...) -> list[om2.MBoundingBox | list[Vector]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getBoundingBox` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isIntermediateObject(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isIntermediateObject` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getInstances(self, noSelf: bool = ...) -> list[Nodes[DagNode]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getInstances` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isInstanced(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isInstanced` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getInstanceIndex(self) -> list[int]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getInstanceIndex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getParent(self, step: int = ..., *, all: bool = ..., instances: bool = ..., indirect: bool = ...) -> list[Transform | Nodes[Transform] | None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getParent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getChildren(self, shapes: bool = ..., intermediates: bool = ..., *, allDescendents: bool = ..., order: str = ..., leaves: bool = ..., includeSelf: bool = ..., underWorld: bool = ..., type: str | Iterable[str] | None = ...) -> list[Nodes[DagNode]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getChildren` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getShape(self, index: int = ..., intermediates: bool = ..., *, all: bool = ...) -> list[DagNode | Nodes[DagNode] | None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getShape` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isTemplated(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isTemplated` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isVisible(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isVisible` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getObjectGroupComponents(self, groupId: int) -> list[list[Components]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getObjectGroupComponents` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDrawColor(self, *, mode: str = ...) -> list[tuple[float, float, float, float] | None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getDrawColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getVisibility(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getVisibility` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDisplayType(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getDisplayType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setDisplayType(self, kind: str, *, fast: bool = ..., check: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.setDisplayType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setShadingOverride(self, state: bool = ..., *, fast: bool = ..., check: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.setShadingOverride` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def deleteHistory(self, keepDeformers: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.deleteHistory` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def addConstraint(self, sources: Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug | Iterable, type: str = ..., maintainOffset: bool = ..., *, typ: str = ..., mo: bool = ..., createCache: Sequence[float] = ..., cc: Sequence[float] = ..., decompRotationToChild: bool = ..., dr: bool = ..., deleteCache: bool = ..., dc: bool = ..., edit: bool = ..., e: bool = ..., layer: str = ..., l: str = ..., name: str = ..., n: str = ..., query: bool = ..., q: bool = ..., remove: bool = ..., rm: bool = ..., skipRotate: str | Sequence[str] = ..., sr: str | Sequence[str] = ..., skipTranslate: str | Sequence[str] = ..., st: str | Sequence[str] = ..., targetList: bool = ..., tl: bool = ..., weight: float = ..., w: float = ..., weightAliasList: bool = ..., wal: bool = ..., offset: Sequence[float] = ..., o: Sequence[float] = ..., skip: str | Sequence[str] = ..., sk: str | Sequence[str] = ..., scaleCompensate: bool = ..., sc: bool = ..., aimVector: Sequence[float] = ..., aim: Sequence[float] = ..., upVector: Sequence[float] = ..., u: Sequence[float] = ..., worldUpObject: Node | Plug | Component | str | om2.MObject | om2.MDagPath | om2.MPlug = ..., wuo: Node | Plug | Component | str | om2.MObject | om2.MDagPath | om2.MPlug = ..., worldUpType: str = ..., wut: str = ..., worldUpVector: Sequence[float] = ..., wu: Sequence[float] = ..., **kwargs) -> list[Constraint]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.addConstraint` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def deleteConstraints(self, *, fast: bool = ...) -> list[list[str]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.deleteConstraints` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def scaleGeometry(self, scale: float | Iterable[float], worldSpace: bool = ..., pivot: Iterable[float] = ..., indices: Iterable[int | tuple[int, int]] | None = ..., *, fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.scaleGeometry` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mirrorGeometry(self, axis: str | int = ..., worldSpace: bool = ..., pivot: Iterable[float] = ..., indices: Iterable[int] | None = ..., *, fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.mirrorGeometry` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPivot(self, worldSpace: bool = ..., *, kind: str = ..., translation: bool = ..., ws: bool = ...) -> list[Translate | Vector]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getPivot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setPivot(self, value: Iterable[float], worldSpace: bool = ..., *, kind: str = ..., translation: bool = ..., preserve: bool = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setPivot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def centerPivot(self, components: str | PointComponents | Iterable[PointComponent] | None = ..., *, fast: bool = ..., check: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.centerPivot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def zeroTransformPivots(self) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.zeroTransformPivots` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def ungroup(self, *, world: bool = ...) -> list[Nodes[Transform]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.ungroup` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUnusedIntermediateShapes(self) -> list[Nodes[Shape]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getUnusedIntermediateShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def deleteUnusedIntermediateShapes(self, *, fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.deleteUnusedIntermediateShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def addShape(self, shape: Shape | str, *, fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.addShape` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def replaceShapes(self, source: Transform | Shape | str, *, keepSource: bool = ..., worldSpace: bool = ..., ws: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.replaceShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getCurveShapesData(self) -> list[dict]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getCurveShapesData` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setCurveShapesData(self, data: dict) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setCurveShapesData` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def exportCurveShapes(self, path: str | os.PathLike) -> list[pathlib.Path]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.exportCurveShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def importCurveShapes(self, path: str | os.PathLike) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.importCurveShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTransform(self) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getTransform` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def matchTransform(self, target: Transform | str | om2.MObject | om2.MDagPath, position: bool = ..., rotation: bool = ..., scale: bool = ..., pivots: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.matchTransform` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mirrorTransform(self, axis: str | int = ..., worldSpace: bool = ..., pivot: Iterable[float] = ..., *, fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.mirrorTransform` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getMatrix(self, worldSpace: bool = ..., p: bool = ..., inv: bool = ..., *, parent: bool = ..., inverse: bool = ..., ws: bool = ...) -> list[Matrix]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getMatrix` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setMatrix(self, matrix: Matrix | Iterable[float], worldSpace: bool = ..., *, safe: bool = ..., get: bool = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[dict[str, Translate | EulerRotate | Scale | Shear] | None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setMatrix` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTransformation(self) -> list[Transformation]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getTransformation` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setTransformation(self, value: Transformation, *, fast: bool = ..., check: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setTransformation` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTranslation(self, worldSpace: bool = ..., at: int = ..., *, ws: bool = ...) -> list[Translate]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getTranslation` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setTranslation(self, value: Iterable[float], worldSpace: bool = ..., at: int = ..., *, relative: bool = ..., safe: bool = ..., get: bool = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[Translate | None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setTranslation` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getRotate(self, worldSpace: bool = ..., *, order: int | str | None = ..., ws: bool = ...) -> list[EulerRotate]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getRotate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setRotate(self, value: Iterable[float] | EulerRotate | Quaternion, worldSpace: bool = ..., *, relative: bool = ..., safe: bool = ..., get: bool = ..., unit: str = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[EulerRotate | None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setRotate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getRotateOrder(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getRotateOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setRotateOrder(self, order: str | int, preserve: bool = ..., *, fast: bool = ..., check: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setRotateOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getScale(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Scale]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getScale` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setScale(self, value: Iterable[float] | float, worldSpace: bool = ..., *, relative: bool = ..., safe: bool = ..., get: bool = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[Scale | None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setScale` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getShear(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Shear]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getShear` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setShear(self, value: Iterable[float], worldSpace: bool = ..., *, relative: bool = ..., safe: bool = ..., get: bool = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> list[Shear | None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setShear` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getQuaternion(self, worldSpace: bool = ..., ra: bool = ..., r: bool = ..., jo: bool = ..., *, rotateAxis: bool = ..., rotate: bool = ..., jointOrient: bool = ..., ws: bool = ...) -> list[Quaternion]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getQuaternion` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setQuaternion(self, value: Quaternion | om2.MQuaternion | Iterable[float], worldSpace: bool = ..., ra: bool = ..., r: bool = ..., jo: bool = ..., *, safe: bool = ..., get: bool = ..., fast: bool = ..., check: bool = ..., rotateAxis: bool = ..., rotate: bool = ..., jointOrient: bool = ..., ws: bool = ..., preserve: bool = ...) -> list[EulerRotate | None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setQuaternion` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def makeIdentity(self, *, apply: bool = ..., a: bool = ..., jointOrient: bool = ..., jo: bool = ..., normal: int = ..., n: int = ..., preserveNormals: bool = ..., pn: bool = ..., rotate: bool = ..., r: bool = ..., scale: bool = ..., s: bool = ..., translate: bool = ..., t: bool = ..., query: bool = ..., q: bool = ..., edit: bool = ..., e: bool = ..., **kwargs: object) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.makeIdentity` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getOffsetParentMatrix(self) -> list[Matrix]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getOffsetParentMatrix` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setOffsetParentMatrix(self, matrix: Matrix | om2.MMatrix | Sequence[float], *, fast: bool = ..., check: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setOffsetParentMatrix` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def freezeToOffsetParent(self) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.freezeToOffsetParent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def eulerFilter(self, *, indirect: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.eulerFilter` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getClosestAxisToVector(self, refVector: Vector | Iterable[float], includeNegative: bool = ...) -> list[str]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getClosestAxisToVector` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getLimits(self, *, unit: str = ...) -> list[dict[str, tuple[float | None, float | None]]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getLimits` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setLimits(self, *, unit: str = ..., **limits: tuple[float | None, float | None] | None) -> list[None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setLimits` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
