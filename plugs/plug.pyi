# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya API 2.0 の MPlug を、アトリビュートを扱うオブジェクトとして包む。"""

import math
import re
from contextlib import contextmanager, nullcontext
from functools import partial
from operator import methodcaller
from typing import TYPE_CHECKING
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
from ..core.attributeType import _convert_angles, _convert_times, _convert_units, _from_seconds, _leaf_unit_kind, _plain_angle_unit, _plain_time_unit, _time_quantity, attributeType, is_internal_data_type, value_reader
from ..core.fastWrite import _ancestor_plugs, require_supported_type, set_attr, set_plug
from ..core.listMethods import _ListMethods
from ..core.nodeEdit import require_editable
from ..core.object import Object, _missing_member_message
from ..decorator import _edit_context, _require_bool, _undo_recording, _validated_flags, undoChunk
from ..util import _UNSET, _angle_unit, _finite, _time_unit
from typing import Any, Callable, Dict, Literal, Optional, Union
from ..nodes.node import Node
from typing import Any, Iterable, Iterator, Literal, Sequence
from mlib._stubtypes import GeneratorContextManager
from mlib.maths.matrix import Matrix
from mlib.nodes.node import Nodes
from mlib.plugs.multiPlug import MultiPlug
from typing import overload
from typing_extensions import Self

_MULTI_SET_MESSAGE: str
_MULTI_RESET_MESSAGE: str
_PLUG_PATH_TOKEN: Any
_PLUG_PATH_INDEX: Any
MAX_LOGICAL_INDEX: int
_SCALAR_ARRAY_TYPES: frozenset
_LENGTH_PREFIXED_ARRAY_TYPES: frozenset
_INVALID_ATTRIBUTE: Any
_NORMAL_ATTRIBUTE: Any
_BOTH_UNIT_KINDS: frozenset

def _require_finite_value(value: object) -> None:
    """set() へ渡した値に、有限でない数値(NaN・無限大)が無いかを確かめる。

    数値、数値の並び(入れ子も含む)、om2 のベクトル・点・オイラー回転・クォータニオン・マトリクスと
    単位付きの値を調べる。文字列・整数・bool・その他の値は調べない。

    Args:
        value (object): 書き込む値。

    Returns:
        None: 値を返さない。

    Raises:
        ValueError: 有限でない数値がある場合(文言にアトリビュート名は含めない)。
    """
    ...

def _instance_count(multi: om2.MPlug) -> int:
    """ワールド空間のマルチアトリビュートなら、持ち主の DAG ノードのインスタンス数を返す。

    ``worldMatrix`` などのワールド空間のアトリビュートでは、インスタンス番号(0～インスタンス数-1)の
    要素を、評価の前でもあるものとして扱う(:class:`MultiPlug` と同じ決まり)。

    Args:
        multi (om2.MPlug): マルチアトリビュートのPlug。

    Returns:
        int: 間接的なインスタンスを含むインスタンス数。ワールド空間のアトリビュートでなければ 0。
    """
    ...

def _is_ramp(mplug: om2.MPlug) -> bool:
    """マルチアトリビュートが、MRampAttribute で扱えるランプのアトリビュートか判定する。

    ランプは、位置・値・補間の3つの子を持つコンパウンドアトリビュートの、マルチアトリビュート。
    その形のものだけを ``om2.MRampAttribute`` で確かめる(ほかのマルチアトリビュートで例外の処理を走らせないため)。

    Args:
        mplug (om2.MPlug): マルチアトリビュート全体のPlug。

    Returns:
        bool: ランプのアトリビュートなら True。
    """
    ...

def _attribute_class(fn: om2.MFnDependencyNode, attribute_handle: om2.MObjectHandle, attribute: om2.MObject) -> int:
    """アトリビュートがノードにあるかと、静的なアトリビュートかを判定する。

    ``addAttr`` で足した動的アトリビュート(``addExtension`` で足した拡張アトリビュートを含む)は削除できる。
    削除したアトリビュートの MPlug で値を読み書きすると、Maya が異常終了する。
    削除しても、Undo のためにアトリビュートの MObject が残っている場合があり、``MObjectHandle.isValid()``
    だけでは判定できない。そのため、ノードの ``MFnDependencyNode.attributeClass()`` で確かめる
    (ノードに無いアトリビュートは ``kInvalidAttr``)。

    - 同じ名前で足し直したアトリビュートは、別のアトリビュートとして扱う。
    - Undo で削除を取り消したアトリビュートと、名前を変えたアトリビュートは、同じアトリビュートのまま。

    Args:
        fn (om2.MFnDependencyNode): ノードの関数セット。ノードが有効(削除されていない)であること。
        attribute_handle (om2.MObjectHandle): アトリビュートの MObject のハンドル。
        attribute (om2.MObject): アトリビュートの MObject。

    Returns:
        int: ``MFnDependencyNode`` の ``kNormalAttr`` (静的アトリビュート)・``kLocalDynamicAttr``・
            ``kExtensionAttr``、またはノードに無いアトリビュートの ``kInvalidAttr``。
    """
    ...

def _key_flags_to_ui(mplug: om2.MPlug, kwargs: dict, unit: str | None, time_unit: str | None, ui_units: bool) -> dict:
    """setKeyframe のフラグの時刻と値を、Mayaが受け取るUIの単位へ換算する。

    Args:
        mplug (om2.MPlug): キーを打つアトリビュート。
        kwargs (dict): setKeyframe のフラグ。
        unit (str | None): 角度の値の単位。
        time_unit (str | None): 時刻と時間の値の単位。
        ui_units (bool): Trueは値をUI単位のまま渡す。

    Returns:
        dict: 換算したフラグ(新しい辞書)。

    Raises:
        TypeError: 単位の型が不正、または秒の時刻に数値以外を指定した場合。
        ValueError: 単位名が不正、またはuiUnitsと単位の同時指定の場合。
    """
    ...

def _move_key_flags(plug: Plug, time: float | Sequence[float] | None, time_offset: float, value_offset: float, unit: str | None, time_unit: str | None) -> dict:
    """キーを動かす ``cmds.keyframe`` のフラグを作る(時刻の範囲・UI単位の移動量)。

    Args:
        plug (Plug): キーを動かすアトリビュート。
        time (float | Sequence[float] | None): 時刻、または両端を含む範囲。Noneは全キー。
        time_offset (float): 時刻の移動量。
        value_offset (float): 値の移動量(角度は度・距離はcm)。
        unit (str | None): 角度の単位。
        time_unit (str | None): 時刻の単位。

    Returns:
        dict: ``time``(指定時)・``timeChange``・``valueChange`` のフラグ。

    Raises:
        TypeError: 型が不正な場合。
        ValueError: 非有限値、または単位名が未対応の場合。
    """
    ...

def _move_plug_keys(name: str, flags: dict):
    """1つのアトリビュートのキーを相対移動する。

    範囲を省くと、キーが1つだけのカーブをMayaが動かさないため、全キーは番号で指定する。

    Args:
        name (str): アトリビュートの完全名。
        flags (dict): :func:`_move_key_flags` のフラグ。
    """
    ...

def _cut_key_flags(time: float | Sequence[float] | None, time_unit: str | None) -> dict:
    """キーの削除範囲を ``cmds.cutKey`` のフラグへ変換する。

    Args:
        time (float | Sequence[float] | None): 時刻、または両端を含む範囲。Noneは全キー。
        time_unit (str | None): timeの単位。Noneと ``"frame"`` は現在のUIの時間単位でのフレーム、``"sec"`` は秒。

    Returns:
        dict: ``{"time": (start, end)}`` (UI時間単位のフレーム)。Noneなら空の辞書。

    Raises:
        TypeError: timeが数値・2つの数値の並び・None以外の場合。
        ValueError: 有限でない、または開始が終了より大きい場合。
    """
    ...

def _key_tangent_flags(in_tangent_type: str | None, out_tangent_type: str | None) -> dict[str, str]:
    """接線の型の指定を確かめ、``cmds.keyTangent`` のフラグへ変換する。

    Args:
        in_tangent_type (str | None): 入力側の接線の型。Noneは変えない。
        out_tangent_type (str | None): 出力側の接線の型。Noneは変えない。

    Returns:
        dict[str, str]: ``inTangentType``・``outTangentType`` のフラグ(小文字)。

    Raises:
        ValueError: どちらもNoneの場合、対応していない接線の型の場合、またはfixedの場合。
    """
    ...

def _frames_from_seconds(value: float | Sequence[float]) -> float | tuple[float, ...] | list[float]:
    """setKeyframeのtimeへ渡す秒の数値(または数値の並び)を、現在のUIの時間単位でのフレームへ換算する。

    Args:
        value (float | Sequence[float]): 秒の時刻。tuple/listは範囲などの並びとして要素ごとに換算する。

    Returns:
        float | tuple[float, ...] | list[float]: フレームの時刻。並びは入力と同じ型で返す。

    Raises:
        TypeError: 数値・数値の並び以外(範囲の文字列など)の場合。
    """
    ...

def _multi_element_exists(mplug: om2.MPlug) -> bool:
    """Plug(と、途中のマルチアトリビュートの要素)がシーンにあるか判定する。

    マルチアトリビュートの要素は、すでにある論理番号(``getExistingArrayAttributeIndices()``。
    値を持つ要素と、接続された要素)に含まれていれば、あるものとする。値を読まないので、
    無い要素を作ってしまうことはない。

    Args:
        mplug (om2.MPlug): 判定するPlug。

    Returns:
        bool: Plugと、途中のすべてのマルチアトリビュートの要素があれば True。
    """
    ...


class DeletedAttributeError(ValueError):
    """``deleteAttr`` で削除したアトリビュートの Plug・MPlug を、ノードを受け取る引数に渡した場合の例外。

    ノードは残っていてアトリビュートだけが削除された Plug・MPlug を、そのノードとして扱うと、
    削除されたものを黙って受け付けてしまう。そのため、``Node._resolve_input``・``Node(...)``/``mlib.getNode``・
    ``Transform.addConstraint()`` のターゲットやコンストレイント先などでも例外にする。

    mlib のコマンド(``Object._input_name``)と同じく、``ValueError`` の派生クラス
    (クラスの親は1つにする決まりのため、``RuntimeError`` の派生ではない)。
    """


class MissingAttributeError(AttributeError):
    """指定した名前のアトリビュートが見つからない場合の例外。

    ``mlib.getPlug("node.nope")`` と ``node.getPlug("nope")`` のどちらもこの例外を送出する(文言は
    ``アトリビュートが見つかりません: <ノード名>.<アトリビュート名>``)。
    ``AttributeError`` の派生クラス(クラスの親は1つにする決まりのため、``RuntimeError`` の派生ではない)。
    ``node.nope`` のように書いた場合は、近い名前の候補を含む ``AttributeError`` を送出し、
    この例外を ``__cause__`` に入れる。
    """


class Plug(Object):
    """アトリビュートを扱うクラス。値・接続・状態(ロックなど)を扱う。

    このクラスのオブジェクトは、持ち主のノード(Node)と、MPlugを1つずつ持つ。

    名前を返すメソッドの規則(``pCube1.translateX``・``wm[0]`` の例):

    .. list-table::
       :header-rows: 1

       * - メソッド
         - 内容
         - 例
       * - :meth:`getName`
         - ``<ノードの最短名>.<ショート名のパス>``。論理番号を含む。表示・ログ向け
         - ``pCube1.tx``・``pCube1.wm[0]``
       * - ``getName(full=True)`` / ``str(plug)``
         - ``<ノードの一意名>.<ロング名のパス>``。エイリアスがあれば使う。Mayaコマンドへ渡す名前
         - ``pCube1.translateX``・``pCube1.worldMatrix[0]``
       * - :meth:`getAttributeName`
         - アトリビュート自身のロング名。ノード名・親・論理番号を含まない
         - ``translateX``・``worldMatrix``
       * - ``getAttributeName("short")``
         - アトリビュート自身のショート名。ノード名・親・論理番号を含まない
         - ``tx``・``wm``
       * - ``getAttributeName("nice")``
         - UI表示用の名前
         - ``Translate X``・``World Matrix``

    ノード名を除いたパスが必要な場合は ``plug.getName().partition(".")[2]`` (ショート名)、
    同じノードの別インスタンスへ移す場合は ``other.getPlug(plug.getName().partition(".")[2])`` とする
    (Mayaのノード名は ``.`` を含まない)。

    作られるオブジェクトのクラスは、マルチアトリビュート、登録した型、コンパウンドアトリビュートの順に選ぶ。
    取得するときに値は評価しない。generic/kAnyは基底のPlugのままにし、getのときに値を読み解く。
    通常の編集はUndoが有効なら記録する。fastがある操作では、fast=TrueならUndoなしで直接更新する。

    Mayaのコマンドへは、getName(full=True)で文字列にして渡す。名前は、名前の変更や親の変更に追従する。
    特にMultiPlugとコンパウンドアトリビュートのPlugは、cmdsが並びとして展開してしまうので、文字列にする必要がある。

    ノードや動的アトリビュートを削除すると、isValidはFalse、名前は空文字列になる。
    値の読み書き・接続の取得・子の取得はRuntimeErrorになる。削除をUndoすれば、再び有効になる。
    """
    _registry: None
    _reader: 'Optional[Union[Callable[..., Any], Literal[False]]]' = ...
    _node: 'Node'
    _mplug: 'om2.MPlug'
    _attribute: 'om2.MObject'
    def __new__(cls, node: Node, mplug: om2.MPlug) -> Self:
        """作るオブジェクトのクラスを選ぶ。

        マルチアトリビュート・登録したアトリビュートの型・コンパウンドアトリビュートの順に調べる。

        - 登録した型との照合には、``cmds.getAttr(type=True)`` と同じ型名を使う。型名はアトリビュートの
          定義から求め(:func:`mlib.core.attributeType.attributeType`)、maya.cmds へは問い合わせない。
          そのため、まだ無いマルチアトリビュートの要素の Plug を作っても、要素は作られない。
        - generic/kAnyは今の値を読まず、基底のPlugにする。
        - マトリクスなどの値の型は、get()を呼んだときに読み解く。そのため、Plugを作るときや接続を調べるときに、
          クラスを選ぶためのDGの評価は起きない。値の型が変わっても、同じPlugを使い続けられる。

        Args:
            node (Node): Plugの持ち主のノード。
            mplug (om2.MPlug): 包む Maya API 2.0 のPlug。

        Returns:
            Plug: 合った派生クラスのインスタンス。派生クラスから直接呼んだ場合は、そのクラスにする。

        Raises:
            RuntimeError: 次のどれかの場合。

                - ノードかアトリビュートが削除されている。削除されたPlug から要素・子・親の Plug を
                  取得した場合も含む(``Node.getPlug()`` と同じ決まり)。
                - 決まっていない(-1)論理番号を途中に含む(``cmp[-1].child`` や
                  ``inputTarget[-1].inputTargetGroup`` のような、maya.cmds で扱えないPlug)。
                - MPlug の持ち主のノードが node と違う(静的アトリビュート・動的アトリビュートとも。
                  持ち主でないノードを渡した誤り)。
        """
        ...
    def __init__(self, node: Node, mplug: om2.MPlug) -> None:
        """持ち主のノードを共有し、MPlugのコピーと、アトリビュートが有効か調べるためのハンドルを持つ。

        MPlugをコピーしても、指す先はシーンの同じアトリビュートで、値を別に複製するわけではない。

        Args:
            node (Node): Plugの持ち主のノード。
            mplug (om2.MPlug): 包む Maya API 2.0 のPlug。

        Returns:
            None: 値を返さない。
        """
        ...
    def __eq__(self, other):
        """同じアトリビュートを指しているか比べる。削除されたものには問い合わせず、Falseにする。

        Args:
            other: 比較・演算の相手。
        """
        ...
    def __hash__(self):
        """作ったときのノードとアトリビュートのパスから求めた、変わらないハッシュ値を返す。"""
        ...
    def __repr__(self) -> str:
        """デバッグ用の表示を返す。クラス名と、ノード名を含むPlugの名前を表示する。

        クラス名は ``Plug``, ``MultiPlug``, ``CompoundPlug`` などの実際の型になる。そのため、
        マルチアトリビュート全体か、コンパウンドアトリビュートかを表示で見分けられる。

        Returns:
            str: ``MultiPlug('pma.input1D')`` のような文字列。ノードかアトリビュートが削除されていれば、
                ``<Plug invalid>`` のように、クラス名と無効であることを表示する。
        """
        ...
    def __rshift__(self, dst: Plug | om2.MPlug | str) -> Plug:
        """``self >> dst`` で、自身から dst へ接続する。

        :meth:`connectTo` の通常の処理と同じ。``a >> b.x`` は ``a >> (b.x)`` として評価される
        (属性の参照が演算子より先に行われる)。Undo に記録する通常の処理だけで、fast は無い。
        演算の結果として、接続先の Plug を返す。

        Args:
            dst (Plug | om2.MPlug | str): 接続先。マルチアトリビュート全体は受け付けない(空いている要素を選ぶには
                ``self.connectTo(multi, nextAvailable=True)`` を使う)。

        Returns:
            Plug: 実際の接続先(dst から求めた Plug)。

        Raises:
            TypeError: dst が対応していない型の場合。
            AttributeError: 文字列で渡した名前のアトリビュート(またはノード)が見つからない場合(``MissingAttributeError``)。
            RuntimeError: すでに同じ接続がある・すでに入力がある・ロックされている・Plugが無効な場合、
                またはマルチアトリビュート全体へ接続しようとした場合(:meth:`connect` と同じ)。
        """
        ...
    def __lshift__(self, src: Plug | om2.MPlug | str) -> Plug:
        """``self << src`` で、src から自身へ接続する。

        :meth:`connect` の通常の処理と同じ。自身を返す。

        Args:
            src (Plug | om2.MPlug | str): 接続元。

        Returns:
            Plug: 自身。

        Raises:
            TypeError: src が対応していない型の場合。
            AttributeError: 文字列で渡した名前のアトリビュート(またはノード)が見つからない場合(``MissingAttributeError``)。
            RuntimeError: すでに同じ接続がある・すでに入力がある・ロックされている・Plugが無効な場合
                (:meth:`connect` と同じ)。
        """
        ...
    def __floordiv__(self, dst: Plug | om2.MPlug | str) -> Plug:
        """``self // dst`` で、自身から dst への直接の接続を切る。

        :meth:`disconnect` の通常の処理と同じ。dst を返す。

        Args:
            dst (Plug | om2.MPlug | str): 接続先。

        Returns:
            Plug: dst から求めた接続先の Plug。

        Raises:
            TypeError: dst が対応していない型の場合。
            AttributeError: 文字列で渡した名前のアトリビュート(またはノード)が見つからない場合(``MissingAttributeError``)。
            RuntimeError: 自身から dst への接続が無い場合、または Plug が無効な場合。
        """
        ...
    def __getattr__(self, name: str):
        """無いメソッドやアトリビュートを参照したとき、近い名前を案内するAttributeErrorにする。

        Args:
            name (str): 参照した名前。

        Raises:
            AttributeError: 常に送出する。``'Plug'にメソッド'<name>'はありません`` の形で、近い名前の
                メソッドと、maya.cmdsやほかのライブラリの名前に当たるmlibの書き方を案内する。
        """
        ...
    def getNode(self) -> Node:
        """この Plug の持ち主のノードを取得する。

        Returns:
            Node: このオブジェクトが持っているノードそのもの。新しいオブジェクトは作らない。
        """
        ...
    def isValid(self, *, elements: bool = ...) -> bool:
        """ノードとアトリビュートが有効か判定する。

        ロック・接続・アトリビュートの定義によって読み書きできるかどうかは判定しない。
        既定では、まだ作られていないマルチアトリビュートの要素(``multi[5]`` で取得しただけの要素)も
        ``True`` になる。``elements=True`` なら、自身と、上にあるマルチアトリビュートの要素が
        すべて実際にあることも確かめる。値の評価や要素の作成は行わない。

        Args:
            elements (bool): Trueなら、通るマルチアトリビュートの要素がすべて実在することも確かめる。既定はFalse。

        Returns:
            bool: ノードが有効で、アトリビュートがあれば ``True``
                (動的アトリビュートは ``deleteAttr`` で削除されることがある)。
                Undo でノードやアトリビュートが戻れば、再び ``True`` になる。
                ``elements=True`` では、まだ無い要素を通る場合に ``False``。
        """
        ...
    def isInstancedAttribute(self) -> bool:
        """DAGノードのインスタンス別アトリビュート定義か調べる。

        接続の有無や、現在インスタンス化されているかの判定ではない。

        Returns:
            bool: MFnDagNodeがインスタンス別の定義と判定すればTrue。非DAGノードはFalse。
        """
        ...
    def isExactlyEqual(self, other: Plug) -> bool:
        """同じアトリビュートと同じネットワーク上のPlugか調べる。

        通常の==による参照先の比較に加え、MPlug.isExactlyEqualのネットワーク識別も比較する。
        API 2.0にこの照会がないMayaではNotImplementedError。

        Args:
            other (Plug): 比較するPlug。

        Returns:
            bool: Mayaが両者を完全に同じPlugと判定した場合はTrue。

        Raises:
            TypeError: otherがPlugでない場合。
            RuntimeError: どちらかのアトリビュートが無効な場合。
            NotImplementedError: このMayaのAPI 2.0が照会を提供しない場合。
        """
        ...
    def getNumConnectedChildren(self) -> int:
        """接続を持つ直接の子アトリビュート数を取得する。

        コンパウンドアトリビュートでないPlug(子を持たないPlug)では0を返す。

        Returns:
            int: MPlug.numConnectedChildrenによる数。子孫の総数ではない。コンパウンドでなければ0。

        Raises:
            RuntimeError: アトリビュートが無効、またはMayaが照会を拒否した場合。
        """
        ...
    def getSetAttrCmds(self, *, valueSelector: str = ..., useLongNames: bool = ...) -> list[str]:
        """このPlugと子孫の値を設定するMELのsetAttr文を取得する。

        文は実行しない。Mayaが出力する単位・表記を保持するため、別のシーンへ適用する際は
        名前や単位を確認する。値の取得に伴ってDGが評価される場合がある。

        Args:
            valueSelector (str): all(全値)、nonDefault(非既定値)、changed(Mayaが変更ありと判定した値)。既定all。
            useLongNames (bool): Trueならアトリビュートの長名を使う。既定False。

        Returns:
            list[str]: Mayaが生成したMEL文。出力対象がなければ空リスト。

        Raises:
            TypeError: 引数の型が不正な場合。
            ValueError: valueSelectorが未対応の場合。
            RuntimeError: Plugが無効、またはMayaが値の出力を拒否した場合。
        """
        ...
    def getAttributeClass(self) -> int:
        """アトリビュート定義が標準・ローカル・拡張のどれに属するか取得する。

        Returns:
            int: MFnDependencyNodeのkNormalAttr・kLocalDynamicAttr・kGlobalDynamicAttr定数。

        Raises:
            RuntimeError: Plugが無効な場合。
        """
        ...
    def isNewAttribute(self) -> bool:
        """現在のシーンで追加されたアトリビュートか調べる。

        リファレンス元で定義された追加アトリビュートと、読込後に追加されたものを区別する。

        Returns:
            bool: 現在のシーンで追加された定義ならTrue。

        Raises:
            RuntimeError: Plugが無効な場合。
        """
        ...
    def mplug(self) -> om2.MPlug:
        """内部で持っているMPlugを、そのまま取得する。

        コピーは作らず、有効かどうかも確かめ直さない。

        Returns:
            om2.MPlug: 内部で持っているMPlug。アトリビュートの値を別に複製したものではない。
        """
        ...
    def getName(self, *, full: bool = ...) -> str:
        """Plugの名前を取得する。既定は短い名前、``full=True`` ならmaya.cmdsで1つに決まる名前。

        既定は ``<Node.getName()>.<ショート名のパス>`` の形で、ノード名は重ならない範囲で最も短い名前になる。
        要素の論理番号は常に含む(``tt.wm[0]``・``bs.it[0].itg[3].tw[2]``)。エイリアスは使わない。
        表示やログ向けの短い書き方なので、Mayaのコマンドへ渡す名前には ``full=True`` を使う。
        ``node.getPlug(plug.getName().partition(".")[2])`` で同じPlugを取得し直せる。

        ``full=True`` では ``<Node.getName()の名前>.<アトリビュートのパス>`` の形で、アトリビュートの部分は
        ロング名と必要な論理番号を含み、エイリアスがあればそれを使う(``str(plug)`` と同じ)。
        ほかの名前のメソッドとの違いは :class:`Plug` の表を参照する。

        Args:
            full (bool): Trueなら、maya.cmdsで1つに決まる名前を返す。既定はFalse。

        Returns:
            str: Plugの名前。ノードかアトリビュートが削除されている場合は空文字列。

        Raises:
            TypeError: fullがboolでない場合。
        """
        ...
    def getAttributeName(self, kind: str = ...) -> str:
        """アトリビュート自身の名前を取得する(``translateX``・``tx``・``Translate X``)。

        :meth:`getName` (``full=True`` を含む)と違い、ノード名・親のコンパウンドアトリビュート・要素の論理番号は
        含まない(アトリビュートの定義の名前)。``bs.it[0].itg[3].tw[2]`` なら ``targetWeights``。
        Plugのパスが必要なら :meth:`getName` (既定はショート名のパス、``full=True`` ならロング名のパス)を使う。
        無効なときは、空文字列を返す :meth:`getName` と違って例外にする。

        Args:
            kind (str): 名前の種類。``"long"``(既定。ロング名)・``"short"``(ショート名)・
                ``"nice"``(Attribute Editor などに表示する名前。``translateX`` なら ``"Translate X"``)。

        Returns:
            str: アトリビュートの名前。要素の番号や階層は含まない。

        Raises:
            ValueError: kindが ``"long"``・``"short"``・``"nice"`` のどれでもない場合。
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def setNiceName(self, name: str) -> None:
        """ローカルの追加アトリビュートにUI表示名を設定する。

        ロング名・ショート名・値・接続は変更しない。定義全体の変更なのでマルチ要素からは呼べない。
        cmds.addAttrでUndo可能に編集する。高速化する用途がないためfast引数は持たない。

        Args:
            name (str): 表示名。空文字列なら上書きを解除し、Mayaの既定の表示名へ戻す。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: nameが文字列以外、標準アトリビュート・マルチ要素・プロキシの場合。
            ValueError: nameにNUL文字を含む場合。
            RuntimeError: 対象が無効・ロック・参照ノードの場合、またはMayaが変更を拒否した場合。
        """
        ...
    def getCategories(self) -> list[str]:
        """アトリビュート定義に登録されたカテゴリ名を取得する。

        Returns:
            list[str]: Mayaの返す順のカテゴリ名。未登録なら空リスト。
                マルチ要素でも要素共通の定義を調べ、値の評価や要素の作成は行わない。

        Raises:
            RuntimeError: ノードかアトリビュートが無効な場合。
        """
        ...
    def getType(self) -> str | None:
        """アトリビュートのMayaでの型名を取得する。

        アトリビュートの定義から求め、値は評価しない。``cmds.getAttr(<Plugの名前>, type=True)`` と同じ型名
        (``doubleLinear``・``double3``・``matrix``・``string`` など)を返す。
        :meth:`Node.getType` が Maya の nodeType 名を返すのと同じ考え方で、
        Python のクラスを調べるときは ``type(plug)`` を使う。

        Returns:
            str | None: 定義上のMayaの型名。マルチアトリビュート全体では、要素の型名。
                generic/kAnyなど、値によって型が決まるアトリビュートでは、値を評価せずにNoneを返す。
                値を取得したあとでもNoneのまま。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def isMulti(self, *, element: bool = ...) -> bool:
        """マルチアトリビュートか(``element=True`` なら、マルチアトリビュートの要素か)判定する。

        ``isMulti``/``isCompound`` はPlugの構造を見るだけなので、
        無効な Plug(:meth:`isValid` が ``False``)でも例外にしない。

        Args:
            element (bool): Trueなら、マルチアトリビュート全体かではなく、その要素(``multi[2]``)かを判定する。既定はFalse。

        Returns:
            bool: マルチアトリビュート全体のPlugなら ``True``。``element=True`` では、要素のPlugなら ``True``。
        """
        ...
    def isCompound(self, *, child: bool = ...) -> bool:
        """コンパウンドアトリビュートか(``child=True`` なら、コンパウンドアトリビュートの子か)判定する。

        Args:
            child (bool): Trueなら、子を持つかではなく、コンパウンドアトリビュートの子(``translate`` の ``tx``)かを
                判定する。既定はFalse。

        Returns:
            bool: 子のPlugを持つなら ``True``。``child=True`` では、子のPlugなら ``True``。
        """
        ...
    @overload
    def getParent(self, *, all: Literal[True], includeMulti: bool = ...) -> Plugs: ...
    @overload
    def getParent(self, *, all: Literal[False] = ..., includeMulti: bool = ...) -> Plug | None: ...
    @overload
    def getParent(self, *, all: bool = ..., includeMulti: bool = ...) -> Plug | Plugs | None:
        """コンパウンドアトリビュートの子なら、親のPlugを取得する。

        ``all=True`` なら、上にあるコンパウンドアトリビュートを近い順にすべて取得する。
        このときは、マルチアトリビュートの要素も通って上へたどる(``bs.it[0].itg[3].tw[2]`` なら
        ``bs.it[0].itg[3]``・``bs.it[0]``)。``all=False`` を繰り返した結果とは同じにならない
        (``bs.it[0].itg[3]`` はマルチアトリビュートの要素で、コンパウンドアトリビュートの子ではないので、
        ``getParent()`` は ``None``、``getParent(all=True)`` は ``bs.it[0]`` を返す)。

        Args:
            all (bool): Trueなら、上にあるコンパウンドアトリビュートをすべて返す。既定はFalseで、すぐ上の親だけ。
            includeMulti (bool): Trueなら、途中のマルチアトリビュート全体のPlugも含める。``all=True`` のときだけ指定できる。
                上の例では ``bs.it[0].itg[3].tw``・``bs.it[0].itg[3]``・``bs.it[0].itg``・``bs.it[0]``・``bs.it`` になる。

        Returns:
            Plug | Plugs | None: 親のPlug。子でない場合は ``None``。
                ``all=True`` では、上にあるPlugを近い順に並べたPlugs(いちばん上のアトリビュートでは空)。

        Raises:
            TypeError: all・includeMultiがboolでない場合、または ``all=False`` で ``includeMulti=True`` を指定した場合。
            RuntimeError: ノードかアトリビュートが削除されている場合。子かどうかにかかわらず例外にする
                (削除された MPlug は、子かどうかを正しく返さないため)。
        """
        ...
    def getMulti(self) -> MultiPlug | None:
        """マルチアトリビュートの要素なら、マルチアトリビュート全体のPlugを取得する。

        Returns:
            MultiPlug | None: マルチアトリビュート全体のPlug。要素でない場合は ``None``。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def getIndex(self) -> int:
        """マルチアトリビュートの要素の、論理番号を取得する。

        Returns:
            int: 要素の論理番号(``multi[index]`` の index)。並びの上での位置ではない。

        Raises:
            TypeError: マルチアトリビュートの要素でない場合。
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def getSiblings(self) -> Plugs:
        """コンパウンドアトリビュートの子であれば、同じ親を持つ他の子を取得する(``tx`` なら ``ty``・``tz``)。

        Returns:
            Plugs: 自身を除く兄弟の子を定義順に並べたリスト。子プラグでない場合は空の集まり。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def getDescendants(self, *, levels: int | None = ..., leavesOnly: bool = ...) -> Plugs:
        """子アトリビュートと既存のマルチ要素を再帰的に取得する。

        自身を含めず、深さ優先で返す。子は定義順、要素は論理番号順。
        値を評価せず、未作成要素も作らない。空のマルチアトリビュートは末端に含めない。

        Args:
            levels (int | None): たどる深さ。1は直接の子と要素、0は空。Noneは制限なし。
            leavesOnly (bool): Trueなら子も要素も持たない定義のPlugだけを返す。
                深さの上限で打ち切った親は含めない。既定False。

        Returns:
            Plugs: 保持順の新しい参照。値は読み取らない。

        Raises:
            TypeError: levelsが整数・None以外(boolを含む)、またはleavesOnlyがboolでない場合。
            ValueError: levelsが負の場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def isDirty(self) -> bool:
        """アトリビュートのデータがdirtyか調べる。

        cmds.isDirtyのデータの状態を返す。値の評価は要求しない。

        Returns:
            bool: データが再評価を必要とする場合はTrue。

        Raises:
            RuntimeError: アトリビュートが無効な場合、またはMayaが照会を拒否した場合。
        """
        ...
    def setDirty(self) -> None:
        """アトリビュートと依存先をdirtyにして再評価を要求する。

        cmds.dgdirtyを使う。値や接続を設定する操作ではなく、Undo対象ではない。
        fast引数は持たない(評価状態の変更をMayaのコマンドへ委譲するため)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: アトリビュートが無効な場合、またはMayaが要求を拒否した場合。
        """
        ...
    def evaluate(self) -> None:
        """アトリビュートのDG評価を要求する。

        cmds.dgevalを使い、値は返さない。値も必要な場合はgetを使う。
        シミュレーションの順次再生を代替しない。Undo対象ではない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: アトリビュートが無効な場合、またはMayaが評価を拒否した場合。
        """
        ...
    def getFlags(self) -> dict[str, bool]:
        """アトリビュートの状態(ロック・keyable・Channel Box表示・Channel Boxに出ていないか)をまとめて取得する。

        :meth:`setFlags` と対になる。``plug.getFlags()["keyable"]`` のように1つだけ取り出して使える。

        - ``"locked"``: ロックされているか(:meth:`isLocked` と同じ)。
        - ``"keyable"``: キーを打てるか。``setAttr(keyable=...)`` でPlugごとに変えた設定を反映する
          (アトリビュートの定義の既定値だけを見る ``MFnAttribute.keyable`` とは違う)。
        - ``"channelBox"``: Channel Boxに表示するフラグ。keyableだから表示されている、という分は含まない。
        - ``"hidden"``: Channel Boxに出ていないか。keyableでもChannel Box表示でもなければ、出ていないとみなす。
          コンパウンドアトリビュート(``t`` など)は、Channel Boxに子(``tx`` など)が並ぶので、
          下の末端の子がすべて隠れている場合にTrueになる。
          ``addAttr(hidden=True)`` で付ける、アトリビュートの定義の hidden フラグ(``cmds.attributeQuery(hidden=True)``)とは別のもの。

        Returns:
            dict[str, bool]: ``"locked"``・``"keyable"``・``"channelBox"``・``"hidden"`` をキーにした新しい辞書。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def setFlags(self, *, locked: bool | None = ..., keyable: bool | None = ..., channelBox: bool | None = ..., children: bool = ..., leaf: bool = ..., fast: bool = ...) -> None:
        """アトリビュートの状態(ロック・keyable・Channel Box表示)をまとめて変える。

        指定しなかった状態は変えない。今の状態は :meth:`getFlags` で取得する。
        Mayaの ``setAttr(keyable=..., channelBox=...)`` は、コンパウンドアトリビュートの親にだけ効く。
        子のkeyableやChannel Box表示は変わらない(ロックだけは、親のロックが子へ引き継がれる)。
        ``children=True`` なら、自身に続けて、コンパウンドアトリビュートの子(孫より下も)へ同じ状態を設定する。
        ``leaf=True`` なら、自身は変えずに、コンパウンドアトリビュートの末端の子だけへ設定する。
        どちらも、マルチアトリビュートの要素へは広げない。

        Mayaでは、keyableとChannel Box表示のフラグは同時にTrueにならない。``keyable=True`` はChannel Box表示のフラグを外し、
        ``channelBox=True`` はkeyableを外す(``channelBox=True`` だけを指定したときは ``keyable=False`` も指定したものとして扱う)。
        どちらの場合も、1回のUndoで元の2つの状態へ戻る。

        .. list-table::
           :header-rows: 1

           * - やりたいこと
             - 書き方
             - ``getFlags()["hidden"]``
           * - キーを打てる状態でChannel Boxに出す
             - ``setFlags(keyable=True)``
             - False
           * - キーを打てない状態でChannel Boxに出す
             - ``setFlags(channelBox=True)``
             - False
           * - Channel Boxから隠す
             - ``setFlags(keyable=False, channelBox=False)``
             - True

        ``translate`` のようなコンパウンドアトリビュートを子ごと出す・隠すときは ``children=True`` を足す。

        Args:
            locked (bool | None): ロックするかどうか。
            keyable (bool | None): キーを打てるかどうか。
            channelBox (bool | None): Channel Boxに表示するかどうか。キーを打てるアトリビュートは、Falseでも表示される。
            children (bool): Trueなら、コンパウンドアトリビュートの下の子にも同じ状態を設定する。
                既定はFalseで、自身だけを変える。leafとは同時に指定できない。
            leaf (bool): Trueなら、コンパウンドアトリビュートの末端の子だけを設定し、自身(親)は変えない。
                コンパウンドアトリビュートでなければ自身を変える。既定はFalse。childrenとは同時に指定できない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 状態がboolでもNoneでもない場合、children・leaf・fastがboolでない場合、
                またはchildrenとleafを同時にTrueにした場合。
            RuntimeError: アトリビュートが無効な場合、またはMayaが更新を拒否した場合。
        """
        ...
    def isConnected(self, other: Plug | om2.MPlug | str | None = ..., *, source: bool = ..., destination: bool = ...) -> bool:
        """指定した向きの、直接の接続があるか判定する。

        ``other`` を渡すと、そのPlugとつながっているかを判定する。
        子やマルチアトリビュートの要素に別々につながっている接続や、変換ノードの先の接続までは調べない。

        引数の名前は :meth:`getConnections` と同じで、調べる相手の側を表す
        (``source`` は入力元、``destination`` は出力先)。向きを取り違えやすいので注意する。

        - 入力がある(自身が接続先になっている)か: ``isConnected(destination=False)``
        - 出力がある(自身が接続元になっている)か: ``isConnected(source=False)``

        Args:
            other (Plug | om2.MPlug | str | None): 相手のPlug。文字列なら ``"node.attribute"`` の形のアトリビュート名。
                既定はNoneで、相手を決めずに接続があるかだけを調べる。
            source (bool): Trueなら、入力(接続元から入ってくる接続。otherを渡したときはotherから自身への接続)を調べる。既定はTrue。
            destination (bool): Trueなら、出力(接続先へ出ていく接続。otherを渡したときは自身からotherへの接続)を調べる。既定はTrue。

        Returns:
            bool: 指定した向きに接続があれば ``True``。両方Falseなら ``False``。

        Raises:
            TypeError: sourceかdestinationがboolでない場合。other が Plug・MPlug・アトリビュート名・None のどれでもない場合、
                または文字列がアトリビュートを指していない場合。
            ValueError: other が空文字列の場合、または空の MPlug の場合。
            AttributeError: 文字列で渡した名前のアトリビュート(またはノード)が見つからない場合(``MissingAttributeError``)。
            RuntimeError: ノードかアトリビュートが削除されている場合。
                other の文字列が複数のアトリビュートに一致する場合や、
                other のPlug・MPlugのノードかアトリビュートが削除されている場合も含む。
        """
        ...
    def isFromReferencedFile(self) -> bool:
        """このPlugの接続が、リファレンスしたファイルの中で作られたものか判定する。

        ``MPlug.isFromReferencedFile`` と同じ。リファレンスのノードのアトリビュートでも、接続が無い場合や、
        読み込んだ側のシーンで作った接続ならFalseになる。
        ノードがリファレンスから来たものかは、:meth:`Node.isFromReferencedFile` で調べる。

        Returns:
            bool: リファレンスしたファイルで作られた接続の一部なら ``True``。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def isProxy(self) -> bool:
        """プロキシアトリビュートか判定する。

        プロキシアトリビュートは、``addAttr(proxy=...)`` で作る、別のノードのアトリビュートの代わりになるもの。

        Returns:
            bool: プロキシアトリビュートなら ``True``。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def getProxyMaster(self) -> Plug | None:
        """プロキシアトリビュートの元のアトリビュートを取得する。

        元は、``addAttr(proxy=...)`` で指定したアトリビュート。Mayaはプロキシを元からの入力の接続として
        持っているので、その接続元を返す。プロキシのプロキシでは、すぐ上の元(1段上のプロキシ)を返し、
        いちばん元まではたどらない(繰り返し呼べば、いちばん元に着く)。

        Returns:
            Plug | None: 元のアトリビュートのPlug。プロキシでない場合や、元との接続が切れている場合は ``None``。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def isSettable(self) -> bool:
        """今、値を設定できるか判定する。

        Mayaの settable の判定と同じ基準で、``maya.cmds.getAttr(settable=True)`` と同じ値を
        ``MPlug.isFreeToChange()`` で求める。自身・親・子のロックと、入力の接続を反映する。
        定義の writable は判定に含めない(cmds と同じく、``worldMatrix`` などの出力のアトリビュートも True になる)。
        値の型や範囲、実行時のエラーまで含めて、set()が成功することを保証するものではない。

        Returns:
            bool: 自身・親・子に、ロックも入力の接続も無ければ ``True``。

        Raises:
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    def getRange(self, *, soft: bool = ..., unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ...) -> tuple[float | tuple[float, ...] | None, float | tuple[float, ...] | None]:
        """アトリビュートの定義の最小値と最大値を取得する。数値は :meth:`get` と同じ決まりで返す。

        角度は度(``unit="rad"`` でラジアン)、距離はcm、時間は現在のUIの時間単位でのフレーム(``timeUnit="sec"`` で秒)、
        数値は ``float`` を返す(角度・距離・時間を ``MAngle``/``MDistance``/``MTime`` のまま返さない)。
        対象は、数値・角度・距離・時間のアトリビュートだけ。それ以外は ``(None, None)``。
        制限があるかどうかは、``None`` かどうかで判定する(``plug.getRange()[0] is not None``)。

        Args:
            soft (bool): Trueなら、ソフト最小値・ソフト最大値(UIスライダーの下限・上限)を返す。
                入力できる値そのものは制限しない値。既定はFalse。
            unit (str | None): 角度の単位。None(既定)と ``"deg"`` は度、``"rad"`` はラジアン(``"degree"`` などの別名も使える)。
                角度以外では使わない。uiUnits=Trueとは同時に指定できない。
            timeUnit (str | None): 時間の単位。None(既定)と ``"frame"`` は現在のUIの時間単位でのフレーム、
                ``"sec"`` は秒(``"frames"`` / ``"seconds"`` などの別名も使える)。時間以外では使わない。
                uiUnits=Trueとは同時に指定できない。
            uiUnits (bool): Trueなら、現在のUIの単位(UIの角度・距離の単位)の数値で返す。既定はFalse。

        Returns:
            tuple[float | tuple[float, ...] | None, float | tuple[float, ...] | None]: ``(最小値, 最大値)``。
                制限が無い側と、対応しないアトリビュート型では ``None``。数値のコンパウンドアトリビュートは子ごとのtuple。

        Raises:
            TypeError: soft・uiUnitsがboolでない場合、またはunit・timeUnitが文字列でもNoneでもない場合。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合。
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def setRange(self, minimum: float | om2.MAngle | om2.MDistance | om2.MTime | None = ..., maximum: float | om2.MAngle | om2.MDistance | om2.MTime | None = ..., *, soft: bool = ..., unit: str | None = ..., timeUnit: str | None = ...) -> None:
        """動的アトリビュートの定義の最小値・最大値を設定する。

        ``cmds.addAttr(edit=True, minValue=..., maxValue=...)`` と同じ。現在の値そのものは変えない。
        **省略した側は変えず、None を渡した側は制限を外す**
        (``setRange(0)`` は最小値だけを0にし、``setRange(0, None)`` は最小値を0にして最大値の制限を外す。
        最大値だけなら ``setRange(maximum=10)``)。
        値の単位は :meth:`Node.addAttr` の ``minValue`` と同じ。

        - 角度は ``unit`` の単位で、既定は度。
        - 距離はcm。
        - 時間は ``timeUnit`` の単位で、既定は現在のUIの時間単位でのフレーム。
        - ``om2.MAngle`` などの単位付きの値は、そのまま使う。

        アトリビュートの定義を変えるので、マルチアトリビュートの要素では全要素に効く。
        1回の ``cmds.addAttr`` で更新し、Undoが有効なら1回のUndoで戻せる
        (Noneで制限を外した側だけは、MayaのUndoでは制限が戻らない)。
        fast引数は無い(addAttr -e は1回が十数µsで、OpenMayaにしても差が小さいため)。

        Args:
            minimum (float | om2.MAngle | om2.MDistance | om2.MTime | None): 最小値。Noneは制限を外す。省略すると変えない。
            maximum (float | om2.MAngle | om2.MDistance | om2.MTime | None): 最大値。Noneは制限を外す。省略すると変えない。
            soft (bool): Trueなら、ソフト最小値・ソフト最大値(UIスライダーの下限・上限)を設定する。既定はFalse。
                Mayaにはソフトリミットを消す手段が無いので、Noneは渡せない。
            unit (str | None): 角度の数値の単位。既定はNoneで度、``"rad"`` はラジアン。
            timeUnit (str | None): 時間の数値の単位。既定はNoneで現在のUIの時間単位でのフレーム、
                ``"sec"`` は秒。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 次のどれかの場合。minimumとmaximumの両方を省略した。softがboolでない。
                静的な(ノードの型に組み込みの)アトリビュート。数値・単位の型でないアトリビュート。
                両方を指定したときのコンパウンドアトリビュート・マルチアトリビュート全体。
                値が数値・単位付きの値・Noneのどれでもない。unit・timeUnitが文字列でもNoneでもない。
            ValueError: unit・timeUnitが対応していない単位名の場合、値が有限でない場合、最小値が最大値より大きい場合、
                または片側だけを指定して、設定済みの反対側と矛盾する場合
                (Mayaは逆になった範囲を警告だけで無視するので、何も変えずに例外にする。ソフトリミットの片側は確かめない)。
            RuntimeError: ノードまたはアトリビュートが無効な場合、またはMayaが変更を拒否した場合。
            NotImplementedError: ``soft=True`` でNoneを渡した場合。変更前に拒否する。
        """
        ...
    def getDefault(self, *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ...) -> Any:
        """アトリビュートの既定値を取得する。数値は :meth:`get` と同じ決まりで返す。

        角度は度(``unit="rad"`` でラジアン)、距離はcm、時間は現在のUIの時間単位でのフレーム(``timeUnit="sec"`` で秒)、
        数値は ``float``/``bool``/``int``、enum は ``int`` を返す。
        scale・double3・float3のような数値のコンパウンドアトリビュートは、子の既定値の ``tuple``
        (例 ``(1.0, 1.0, 1.0)``)を返す。

        Args:
            unit (str | None): 角度の単位。None(既定)と ``"deg"`` は度、``"rad"`` はラジアン(``"degree"`` などの別名も使える)。
                角度以外では使わない。uiUnits=Trueとは同時に指定できない。
            timeUnit (str | None): 時間の単位。None(既定)と ``"frame"`` は現在のUIの時間単位でのフレーム、
                ``"sec"`` は秒(``"frames"`` / ``"seconds"`` などの別名も使える)。時間以外では使わない。
                uiUnits=Trueとは同時に指定できない。
            uiUnits (bool): Trueは現在のUI単位(UIの角度・距離の単位)の数値で返す
                (コンパウンドアトリビュートは子ごとに換算したtuple)。

        Returns:
            object | None: 既定値。対応しないアトリビュート型(文字列・message・マトリクス・
                数値以外の汎用のコンパウンドアトリビュートなど)では ``None``。

        Raises:
            TypeError: uiUnitsがboolでない場合、またはunit・timeUnitが文字列でもNoneでもない場合。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合。
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def setDefault(self, value: bool | int | float | om2.MAngle | om2.MDistance, *, fast: bool = ..., unit: str | None = ..., uiUnits: bool = ...) -> None:
        """追加アトリビュートの既定値を変更する。現在値と接続は変更しない。

        非参照ノードの単一の数値・bool・enum・角度・距離に対応する。
        未取得の現在値が新しい既定値へ追従しないよう、変更前にget()で値を評価する。
        通常はcmds.addAttrを使うが、Maya 2022～2027ではUndoすると変更前の既定値ではなく0になる。
        Redoは指定値へ戻す。元の既定値を復元するUndoは保証しない。

        Args:
            value (bool | int | float | om2.MAngle | om2.MDistance): 新しい既定値。
                角度は度、距離はcm。単位付きの値は自身の単位を使う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Undo設定は変更しない。
            unit (str | None): 角度の数値の単位(deg/rad)。uiUnitsより優先する。
            uiUnits (bool): Trueなら角度・距離の数値を現在のUI単位として扱う。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対象が未対応の型・マルチ・コンパウンド・子・プロキシ、または入力の型が不正な場合。
            ValueError: 数値が有限でない、範囲外、enumの欠番、または単位が不正な場合。
            RuntimeError: 対象が無効・ロック・参照ノードの場合、またはMayaが変更を拒否した場合。
        """
        ...
    def isDefaultValue(self) -> bool:
        """今の値が、アトリビュートの定義の既定値と同じか判定する(``MPlug.isDefaultValue``)。

        値を評価して比べる。入力の接続があるアトリビュートは、接続元から評価した値で判定する。
        コンパウンドアトリビュートは、子がすべて既定値なら True。

        Returns:
            bool: 既定値なら ``True``。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def getAlias(self) -> str | None:
        """このPlugに設定されているエイリアス名を取得する。

        Returns:
            str | None: エイリアス名。設定されていない場合は ``None``。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def setAlias(self, name: str | None = ..., *, skipExisting: bool = ..., fast: bool = ...) -> None:
        """エイリアス(別名)を設定する。解除もできる。

        Args:
            name (str | None): エイリアス名。Noneか空文字列なら解除する。
            skipExisting (bool): Trueなら、何度実行してもよいようにする。自身がすでに同じエイリアスを持っていれば、
                何も変えずに自身を返す。ほかのアトリビュートが使っているエイリアスは、既定と同じく例外にする。
                既定はFalseで、同じエイリアスを設定し直してもMayaのエラー(RuntimeError)になる。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。対応していない操作は、更新する前に拒否する。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: skipExisting・fastがboolでない場合。
            RuntimeError: アトリビュートが無効な場合、またはMayaがエイリアスを拒否した場合。
        """
        ...
    def setKey(self, *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., **kwargs) -> None:
        """このアトリビュートにキーを打つ。

        ``value`` / ``v`` は、:meth:`get` と同じ決まりの数値(角度は度、距離はcm、時間はフレーム)で受け取る。
        fast引数は無い。時間の大半はキーの確認とカーブの取得にかかり、OpenMayaで書いても速くならないため。
        カーブへ直接キーを打つときは、:meth:`AnimCurve.setKey` の ``fast`` を使う。

        Args:
            unit (str | None): 角度のvalueの単位。None(既定)と ``"deg"`` は度、``"rad"`` はラジアン。
                角度以外のアトリビュートでは使わない。uiUnits=Trueとは同時に指定できない。
            timeUnit (str | None): ``time`` / ``t`` と、時間のアトリビュートのvalueの単位。None(既定)と ``"frame"`` は
                現在のUIの時間単位でのフレーム(setKeyframeと同じ)、``"sec"`` / ``"second"`` / ``"seconds"`` は秒。
                ``"sec"`` では、time に数値か数値の並びだけを受け付け、setKeyframeへ渡す前にフレームへ換算する。
            uiUnits (bool): Trueなら、value を現在のUIの単位(UIの角度・距離の単位)の数値で受け取る。既定はFalse。
            **kwargs: MayaのsetKeyframeのフラグ(``time``・``value``・``inTangentType`` など)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: unit・timeUnitが文字列でもNoneでもない場合、uiUnitsがboolでない場合、
                または ``timeUnit="sec"`` で、time/tに数値でも数値の並びでもないもの
                (``"1:10"`` のような範囲の文字列など)を指定した場合。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合。
        """
        ...
    def removeKey(self, *, time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> None:
        """このアトリビュートのキーを削除する。

        ``cmds.cutKey(plug, time=..., clear=True)`` と同じ。キーのクリップボードは変えない。
        すべてのキーを削除すると、Mayaと同じく、空になったカーブも削除される(アトリビュートは最後の値のまま)。
        カーブを直接操作するときは :meth:`AnimCurve.removeKey` を使う。
        fast引数は無い(OpenMayaでキーを1つずつ消す方が、cmds.cutKeyより遅いため)。

        Args:
            time (float | Sequence[float] | None): 削除する時刻、または両端を含む範囲 ``(start, end)``。
                Noneは全キー。
            timeUnit (str | None): timeの単位。None(既定)と ``"frame"`` は現在のUIの時間単位でのフレーム、
                ``"sec"`` は秒。

        Returns:
            None: 値を返さない。キーが無ければ何もしない。

        Raises:
            TypeError: timeが数値・2つの数値の並び・Noneのどれでもない場合、またはtimeUnitが文字列でもNoneでもない場合。
            ValueError: timeが有限でない場合、範囲の開始が終了より大きい場合、またはtimeUnitが対応していない単位名の場合。
            RuntimeError: アトリビュートが無効な場合、またはMayaが削除を拒否した場合。
        """
        ...
    def moveKey(self, *, time: float | Sequence[float] | None = ..., timeOffset: float = ..., valueOffset: float = ..., unit: str | None = ..., timeUnit: str | None = ...) -> None:
        """このアトリビュートのキーの、時刻と値をずらす。

        ``cmds.keyframe(plug, edit=True, relative=True)`` と同じ。Mayaと同じく、時刻をずらしたキーは、
        動かさない隣のキーを越えない。カーブを直接操作するときは
        :meth:`AnimCurve.moveKey <mlib.nodes.animCurve.AnimCurve.moveKey>` を使う。fast引数は無い。

        Args:
            time (float | Sequence[float] | None): 動かすキーの時刻、または両端を含む範囲 ``(start, end)``。
                Noneならすべてのキー。
            timeOffset (float): 時刻をずらす量。
            valueOffset (float): 値をずらす量。:meth:`get` と同じ決まりの数値(角度は度、距離はcm)。
            unit (str | None): 角度のvalueOffsetの単位。None(既定)と ``"deg"`` は度、``"rad"`` はラジアン。
            timeUnit (str | None): time・timeOffsetの単位。None(既定)と ``"frame"`` は現在のUIの時間単位でのフレーム、
                ``"sec"`` は秒。

        Returns:
            None: 値を返さない。キーが無ければ何もしない。

        Raises:
            TypeError: timeが数値・2つの数値の並び・Noneのどれでもない場合、ずらす量が数値でない場合、
                または単位の型が不正な場合。
            ValueError: 有限でない値がある場合、範囲の開始が終了より大きい場合、または単位名が対応していない場合。
            RuntimeError: アトリビュートが無効な場合、またはMayaが移動を拒否した場合。
        """
        ...
    def setKeyTangent(self, *, inTangentType: str | None = ..., outTangentType: str | None = ..., time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> None:
        """このアトリビュートのキーの、接線の型をまとめて変える。

        ``cmds.keyTangent(plug, edit=True, time=..., inTangentType=..., outTangentType=...)`` と同じ。
        時刻か範囲で選んだキーをまとめて変える。カーブの1つのキーの角度・ウェイトまで変えるときは
        :meth:`AnimCurve.setTangent <mlib.nodes.animCurve.AnimCurve.setTangent>` を使う。
        Mayaのコマンドの1回なので、Undoが有効なら1回で戻せる。fast引数は持たない(1回のcmdsで全キーを処理するため)。

        Args:
            inTangentType (str | None): 入力側の接線の型(``"auto"``・``"linear"``・``"flat"`` など。``"fixed"`` は使えない)。Noneなら変えない。
            outTangentType (str | None): 出力側の接線の型。Noneなら変えない。
            time (float | Sequence[float] | None): 変えるキーの時刻、または両端を含む範囲 ``(start, end)``。Noneならすべてのキー。
            timeUnit (str | None): timeの単位。None(既定)と ``"frame"`` は現在のUIの時間単位でのフレーム、``"sec"`` は秒。

        Returns:
            None: 値を返さない。範囲にキーが無ければ何もしない。

        Raises:
            TypeError: timeが数値・2つの数値の並び・Noneのどれでもない場合、またはtimeUnitが文字列でもNoneでもない場合。
            ValueError: 接線の型を1つも指定しない場合、対応していない接線の型かfixedを指定した場合、timeが有限でない場合、
                範囲の開始が終了より大きい場合、またはtimeUnitが対応していない単位名の場合。
            RuntimeError: アトリビュートが無効な場合、またはMayaが変更を拒否した場合。
        """
        ...
    def getAnimLayers(self, selected: bool = ..., exact: bool = ...) -> Nodes:
        """このアトリビュートへの入力をさかのぼって、アニメーションレイヤーを取得する。

        上のレイヤーから順に並べる。

        Args:
            selected (bool): Trueなら、選択しているレイヤーだけにする。既定はFalse。
            exact (bool): Trueなら、selected=Trueのときにベースレイヤーも選択されているかで絞る。既定はFalse。

        Returns:
            Nodes: animLayerのノード。条件に合えば、最後にベースレイヤーを含む。名前は ``getAnimLayers().getNames()`` で取得する。
        """
        ...
    @overload
    def getEnumNames(self, *, value: int, name: None = ..., current: Literal[False] = ...) -> str: ...
    @overload
    def getEnumNames(self, *, value: None = ..., name: str, current: Literal[False] = ...) -> int: ...
    @overload
    def getEnumNames(self, *, value: None = ..., name: None = ..., current: Literal[True]) -> str: ...
    @overload
    def getEnumNames(self, *, value: None = ..., name: None = ..., current: Literal[False] = ...) -> list[tuple[str, int]]: ...
    @overload
    def getEnumNames(self, *, value: int | None = ..., name: str | None = ..., current: bool = ...) -> list[tuple[str, int]] | str | int:
        """enum アトリビュートのフィールドを取得する。名前と値を相互に変換する指定もここにある。

        - 引数なし: すべてのフィールドを ``(名前, 値)`` の組で返す。値の小さい順に並べ、``a=1:b=5`` のように
          値が飛んでいる定義では、フィールドのある値だけを含む。
        - ``current=True``: 今の値(``get()``)のフィールド名を返す。
        - ``value=3``: その値のフィールド名を返す。
        - ``name="b"``: その名前のフィールドの値を返す(大文字・小文字を区別して、完全に一致するものを探す)。

        Args:
            value (int | None): 名前を調べる enum の値。bool は受け付けない。
            name (str | None): 値を調べるフィールド名。
            current (bool): Trueなら、今の値のフィールド名を返す。既定はFalse。

        Returns:
            list[tuple[str, int]] | str | int: 引数なしは ``(フィールド名, enum の値)`` の新しい list。
                ``current=True``・``value`` はフィールド名、``name`` は enum の値。

        Raises:
            TypeError: enum アトリビュートでない場合、value が整数でない場合、current が bool でない場合、
                または value・name・current のうち2つ以上を同時に指定した場合。
            ValueError: 値に対応するフィールドが無い場合(``a=1:b=5`` で3を指定した場合など、欠けている値)、
                または name に一致するフィールドが無い場合(文言には、使えるフィールド名を並べる)。
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def setEnumNames(self, names: Iterable[str]) -> None:
        """enumアトリビュートのフィールド名を、渡した順に設定し直す。

        fast引数は無い(API 2.0には、すでにあるenumのフィールドを削除する手段が無いため)。

        Args:
            names (Iterable[str]): フィールド名の並び。値0から順に割り当てる。空の名前は使えない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: enumアトリビュートでない場合、または名前が文字列でない場合。
            ValueError: 並びが空の場合、空の名前がある場合、または区切り文字(``:``・``=``)を含む名前がある場合。
            RuntimeError: アトリビュートが無効な場合、またはMayaが変更を拒否した場合。
        """
        ...
    def isLocked(self) -> bool:
        """Plugがロックされているか判定する。

        Returns:
            bool: ロックされている場合は ``True``。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def setLocked(self, state: bool = ..., *, leaf: bool = ..., fast: bool = ...) -> None:
        """ロックを設定する。

        Args:
            state (bool): Trueならロックする。既定はTrue。
            leaf (bool): Trueなら、コンパウンドアトリビュートの末端の子だけを設定し、自身(親)は変えない。
                自身と、その下の子の両方へ設定するには、:meth:`setFlags` の ``children=True`` を使う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。対応していない操作は、更新する前に拒否する。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでもNoneでもない場合、またはfastがboolでない場合。
            RuntimeError: アトリビュートが無効な場合、またはMayaが更新を拒否した場合。
        """
        ...
    def isMuted(self) -> bool:
        """アトリビュートがミュートされているか判定する。

        Returns:
            bool: ミュートされている場合は ``True``。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def setMuted(self, state: bool = ...) -> None:
        """ミュートを設定する。

        Trueなら今の値で止め、Falseなら解除する。

        - アニメーションの無いチャンネルにTrueを指定しても、Mayaが警告を出すだけで何もしない
          (muteノードは作られず、:meth:`isMuted` はFalseのまま)。例外にはせず、自身を返す。
        - コンパウンドアトリビュートでは、入力の接続がある子だけが対象になる(``cmds.mute`` と同じ)。

        ``cmds.mute`` を使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            state (bool): Trueならミュートする。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: stateがboolでない場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合、またはMayaが更新を拒否した場合。
        """
        ...
    def delete(self, *, force: bool = ..., fast: bool = ...) -> None:
        """このアトリビュートをノードから削除する。

        使えるのは、あとから足したアトリビュート(addAttr で足したカスタムアトリビュート)だけ。
        ノードの型に組み込みの静的なアトリビュートを削除しようとすると、Maya が拒否する。
        接続があれば、force にかかわらず、Maya が自動で接続を切ってから削除する。

        Args:
            force (bool): True なら、ロックされていても一時的に解除してから削除する。既定はFalse。
                False のときにロックされたアトリビュートを削除しようとすると、RuntimeError になる。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。対応していない操作は、更新する前に拒否する。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがboolでない場合。
            RuntimeError: ノードかアトリビュートが削除されている場合。または、force=False でロックされている場合や、
                静的なアトリビュートを削除しようとした場合など、Maya が削除を拒否した場合。
        """
        ...
    def get(self, *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., time: float | om2.MTime | None = ...) -> Any:
        """今の値を評価して取得する。

        値はキャッシュしない。単位は次のとおり。

        - 角度のアトリビュート(doubleAngleなど。rotateX・jointOrientの子など)の数値は、既定で度。
        - 距離はcm。
        - 時間のアトリビュート(``time1.outTime`` など)は、既定で現在のUIの時間単位でのフレーム。

        角度・時間のコンパウンドアトリビュートは、子ごとに換算する。
        rotateのEulerRotateのように、自分の単位を持つ値は換算しない(中身はrad)。

        Args:
            time (float | om2.MTime | None): 評価する時刻。数値はUI時間単位のフレーム。Noneは現在の評価コンテキスト。
                現在フレームは動かさない。timeUnitは返す値の換算用で、評価時刻には適用しない。
                シミュレーションの順次再生と同じ結果は保証しない。
            unit (str | None): 数値の角度の単位。None(既定)と ``"deg"`` / ``"degree"`` /
                ``"degrees"`` は度、``"rad"`` / ``"radian"`` / ``"radians"`` はラジアン。
                角度以外のアトリビュートでは使わない。uiUnits=Trueとは同時に指定できない。
            timeUnit (str | None): 数値の時間の単位。None(既定)と ``"frame"`` / ``"frames"`` は
                現在のUIの時間単位(``currentUnit -time``)でのフレーム、``"sec"`` / ``"second"`` /
                ``"seconds"`` は秒。時間以外のアトリビュートでは使わない。uiUnits=Trueとは同時に指定できない。
            uiUnits (bool): Trueなら、単位付きの数値を現在のUIの単位へ換算する。既定はFalseで、
                角度は度(unitの指定に従う)、距離はcm、時間はフレーム(timeUnitの指定に従う)。

        Returns:
            object: 型に合った値。

                - CompoundPlug.getは、子の値を定義順に並べたtuple。
                - MultiPlug.getは、論理番号をキーにしたdict。
                - APIで読む ``doubleArray`` などのデータ型はlist。各要素は、vectorArrayならXYZ、
                  pointArrayならXYZW、matrixArrayなら16成分のtuple。
                - 一度も値を入れていないデータはNone、空のデータは空のlist。
                - generic/kAnyは、今の値に合わせてMatrix・数値・tupleなどを返す。

                マトリクスや ``doubleArray`` などのデータ型の成分と、単位の無い値は換算しない。

        Raises:
            TypeError: uiUnitsがboolでない場合、またはunit・timeUnitが文字列でもNoneでもない場合。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合。
            RuntimeError: アトリビュートが無効な場合、または値を読み取れない場合。
            NotImplementedError: 指定時刻の取得に対応しない型(cmdsで読むgeneric・messageなど)の場合。

        Note:
            まだ作られていないマルチアトリビュートの要素(``multi[9]`` のように取得しただけの要素)を読むと、
            ``cmds.getAttr`` と同じく、Mayaがその要素を作る(以後は ``getIndices()`` に現れる)。
            取得しただけでは要素は作られない。
        """
        ...
    def set(self, value: object, *, safe: bool = ..., unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., fast: bool = ..., check: bool = ...) -> int | None:
        """値を設定する。

        ロックの解除や接続の切断、失敗したときの自動の巻き戻しはしない。
        通常はcmds.setAttrで更新し、Undoが有効なら記録する。

        safe=Trueなら、本体で起きたRuntimeError・TypeError・ValueErrorを、例外にせず失敗の数に変える。
        コンパウンドアトリビュートの値で失敗したときは、子ごとにやり直す。成功した子の変更は残る。

        Args:
            value (object): 設定する値。角度の数値は既定で度(unitで変えられる)、距離はcm、
                時間は既定で現在のUIの時間単位でのフレーム(timeUnitで変えられる)。
                EulerRotate・Quaternion・MAngle・MTimeのように、自分の単位を持つ値は換算しない。
            safe (bool): Trueなら、失敗を例外にせず数える(数える失敗の種類はRaisesを参照)。既定はFalseで、例外を送出する。
            unit (str | None): 数値の角度の単位。None(既定)と ``"deg"`` / ``"degree"`` /
                ``"degrees"`` は度、``"rad"`` / ``"radian"`` / ``"radians"`` はラジアン。
                角度以外のアトリビュートでは使わない。uiUnits=Trueとは同時に指定できない。
            timeUnit (str | None): 数値の時間の単位。None(既定)と ``"frame"`` / ``"frames"`` は
                現在のUIの時間単位でのフレーム、``"sec"`` / ``"second"`` / ``"seconds"`` は秒。
                時間以外のアトリビュートでは使わない。uiUnits=Trueとは同時に指定できない。
            uiUnits (bool): Trueなら、現在のUIの単位の数値として受け取る。既定はFalseで、
                角度は度(unitの指定に従う)、距離はcm、時間はフレーム(timeUnitの指定に従う)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。対応している型だけを直接更新し、Undoの設定は変えない。
                値の意味と確かめ方は通常と同じ(整数型・enum・boolへの小数は四捨五入する。
                数値型への文字列や、文字列型への数値はRuntimeError)。
            check (bool): Trueなら、書き込む前に、値が有限か(NaN・無限大でないか)と、書き込めるか
                (ロック・入力の接続・書き込めない定義が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずにMayaへ渡す(Mayaが拒否したときだけ例外になる)。

        Returns:
            int | None: 通常は値を返さない。safe=Trueなら、成功は0、子ごとにやり直したときは失敗数の合計。
                アトリビュートが無効な場合、値を成分に分けられない場合、やり直しを終えられない失敗は1。
                変更されなかった成分の正確な数は保証しない。

        Raises:
            TypeError: fastがboolでない場合、またはマルチアトリビュート全体に設定しようとした場合。
                safe=Trueでも例外にする。safe=Falseなら、unit・timeUnitが文字列でもNoneでもない場合や、
                値が不正な場合にも送出する。
            ValueError: unit・timeUnitが対応していない単位名の場合、またはuiUnits=Trueと同時に指定した場合
                (safe=Trueでは1を返す)。safe=Falseなら、値の変換などに失敗した場合にも送出する。
            RuntimeError: safe=Falseで、アトリビュートが無効な場合や、ロック・入力の接続などで書き込めない場合。
            NotImplementedError: fastに対応していない型(messageなど)の場合。ロックなど書き込めるかどうかより先に調べ、
                safe=Trueでも、途中まで書き込む前に拒否する。

        Note:
            fastでは、値や書き込めるかどうかより先に、すべての子の型が対応しているか確かめる。
            呼び出し方の誤りや、上に書いた以外の例外は、safe=Trueでもまとめて抑えることはしない。
        """
        ...
    def setIfChanged(self, value: bool | int | float | str, *, unlock: bool = ..., fast: bool = ..., check: bool = ...) -> bool:
        """今の値と違うときだけ書き込む。

        1つの値(スカラー)だけを扱う。getで今の値を取得し、Pythonの ``==`` で比べる。

        - 同じなら、書き込めるかどうかの確認もロックの変更もせず、Falseを返す。
        - 違えばsetで書き込む。失敗したら例外にする。

        Args:
            value (bool | int | float | str): 比べて設定する値。数値は誤差を許さずに比べる。
                単位は :meth:`get` / :meth:`set` の既定(角度は度、距離はcm、時間は現在のUIの時間単位でのフレーム)。
            unlock (bool): Trueなら、このアトリビュート自身のロックを一時的に外す。書き込みが成功しても
                失敗しても、あとでロックし直す。親のロックや入力の接続は外さない。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。中で呼ぶsetや状態の更新にも同じ値を渡す。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            bool: 書き込んだらTrue。値が同じで書き込まなかったらFalse。

        Raises:
            TypeError: fastがboolでない場合、またはスカラーでない値を指定した場合。
            ValueError: check=Trueで、値が有限でない(NaN・無限大の)場合。
            RuntimeError: アトリビュートが無効な場合、check=Trueでロック・入力の接続がある場合、
                またはMayaがアトリビュートの更新を拒否した場合。

        Note:
            通常は、値とロックの変更を、Undoが有効なら同じチャンクに記録する。
            fastではUndoの設定を変えない。途中まで書いた値を自動で戻すこともしない。
        """
        ...
    def reset(self, *, fast: bool = ..., check: bool = ...) -> None:
        """数値・単位付き・enumのアトリビュートを、定義の既定値へ戻す。

        - 単位付きのアトリビュートは、既定値を内部単位(cm・rad・秒)に換算し、``unit="rad"``・``timeUnit="sec"`` でsetへ渡す。
        - コンパウンドアトリビュートは、定義順に子を戻す。途中で失敗したら例外を送出する。
          ``check=True`` なら、書く前にすべての子を確かめる。成功した子を自動で元に戻すことはしない。

        接続の切断やロックの解除はしない。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。通常は、Undoが有効なら子の変更を同じチャンクに記録する。
                fastは子にもそのまま渡し、Undoには記録しない。

        Raises:
            TypeError: マルチアトリビュート全体・文字列・messageなど、既定値を扱えないアトリビュートの場合。
            RuntimeError: ロックや入力の接続などで変更できない場合。enumの既定値がフィールドの
                最小〜最大の外にある場合(``a=1:b=5`` の既定値0など)も、Mayaの設定どおり
                書き込みを拒否してRuntimeErrorになる(値は変えない)。

        Note:
            ``fast=True`` はOpenMayaで直接更新する(Undoなし)。既定の ``False`` は通常の処理。
            fastがboolでなければTypeError。fastで書き終えた変更は、自動では戻さない。
        """
        ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[True], outputs: Literal[False] = ...) -> tuple[Plug, Node] | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[True], outputs: Literal[False] = ...) -> tuple[Plug, Plug] | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[True], outputs: Literal[False] = ...) -> Node | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[True], outputs: Literal[False] = ...) -> Plug | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: int, input: Literal[False] = ..., outputs: Literal[True]) -> tuple[Plug, Node] | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[False] = ..., outputs: Literal[True]) -> list[tuple[Plug, Node]]: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: int, input: Literal[False] = ..., outputs: Literal[True]) -> tuple[Plug, Plug] | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[False] = ..., outputs: Literal[True]) -> list[tuple[Plug, Plug]]: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: int, input: Literal[False] = ..., outputs: Literal[True]) -> Node | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[False] = ..., outputs: Literal[True]) -> Nodes: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: int, input: Literal[False] = ..., outputs: Literal[True]) -> Plug | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[False] = ..., outputs: Literal[True]) -> Plugs: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: int, input: Literal[False] = ..., outputs: Literal[False] = ...) -> tuple[Plug, Node] | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[False] = ..., outputs: Literal[False] = ...) -> list[tuple[Plug, Node]]: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: int, input: Literal[False] = ..., outputs: Literal[False] = ...) -> tuple[Plug, Plug] | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[True], asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[False] = ..., outputs: Literal[False] = ...) -> list[tuple[Plug, Plug]]: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: int, input: Literal[False] = ..., outputs: Literal[False] = ...) -> Node | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[True], checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[False] = ..., outputs: Literal[False] = ...) -> Nodes: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: int, input: Literal[False] = ..., outputs: Literal[False] = ...) -> Plug | None: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: Literal[False] = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: Literal[False] = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: Literal[False] = ..., asNode: Literal[False] = ..., checkChildren: bool = ..., checkElements: bool = ..., index: None = ..., input: Literal[False] = ..., outputs: Literal[False] = ...) -> Plugs: ...
    @overload
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: bool = ..., asNode: bool = ..., checkChildren: bool = ..., checkElements: bool = ..., index: int | None = ..., input: bool = ..., outputs: bool = ...) -> Plugs | Nodes | list | Plug | Node | tuple | None:
        """接続している相手を取得する。

        既定では、直接つながっているPlugを返す(``cmds.listConnections`` と同じ)。
        ``skipConversionNodes=True`` (または ``scn=True``)なら、
        unitConversion系(unitConversion・unitToTimeConversion・timeToUnitConversion)のノードを飛ばして、
        その先のPlugを返す。

        まず自身の入力・出力を調べ、続けてマルチアトリビュートのすでにある要素か、子を順に下へたどる。
        型で絞り、最初に出てきた順で重複を除いてから、indexを当てはめる。

        このPlug自身の入力元・出力先だけが要るときは、``input=True``・``outputs=True`` を使う
        (子やマルチアトリビュートの要素に別々につながっている接続までは調べない)。

        - ``getConnections(input=True)``: 自身の入力元を1つ返す。無ければ ``None``
          (``source=True, destination=False, checkChildren=False, checkElements=False, index=0`` と同じ)。
          接続が無いかどうかは ``plug.getConnections(input=True) is None`` で判定できる。
        - ``getConnections(outputs=True)``: 自身の出力先をPlugsで返す。無ければ空
          (``source=False, destination=True, checkChildren=False, checkElements=False`` と同じ)。

        ``getConnections(destination=False)`` は、これらとは違う。子・要素の接続も集めたPlugsを返すので、
        ``is None`` の判定には使えない。

        Args:
            s (bool): 入力を調べるか。sourceとの両方がTrueのときだけ調べる(AND)。
            d (bool): 出力を調べるか。destinationとの両方がTrueのときだけ調べる(AND)。
            c (bool): connections・asPairのどれかがTrueならペアで返す(OR)。
            t (str | None): 型の条件。typeを指定していない(または偽の)ときに使う。
            et (bool): exactTypeの短縮名。どちらかがTrueなら有効(OR)。
            scn (bool): skipConversionNodesの短縮名。どちらかがTrueなら、変換ノードを飛ばす(OR)。
            source (bool): 入力を含めるか。sとの両方がTrueのときだけ調べる(AND)。
            destination (bool): 出力を含めるか。dとの両方がTrueのときだけ調べる(AND)。
            connections (bool): c・asPairのどれかがTrueならペアで返す(OR)。
            type (str | None): 相手のNodeの型。tより優先する。
            exactType (bool): Trueなら型名が完全に一致するものだけ。Falseなら派生した型も含む。
            skipConversionNodes (bool): 既定はFalseで、直接つながっているPlugを返す(``cmds.listConnections`` と同じ)。
                Trueなら、unitConversion系のノードを飛ばす。
            asPair (bool): Trueなら(自身側のPlug, 相手側)の組で返す。入力の向きでも同じ順番。
            asNode (bool): Trueなら、相手側をNodeで返す。ペアの自身側はPlugのまま。
            checkChildren (bool): Trueなら、コンパウンドアトリビュートの子も調べる。
            checkElements (bool): Trueなら、マルチアトリビュートのすでにある要素も調べる。
            index (int | None): 絞り込んだ結果の、Pythonでの位置の番号。負の数も使える。範囲外ならNone。
            input (bool): Trueなら、このPlug自身の入力元を1件(無ければNone)で返す。既定はFalse。
                outputs・index、向き(s・d・source・destination)とたどり方(checkChildren・checkElements)の指定とは
                同時に指定できない。型・ペア・Nodeで返す指定・変換ノードを飛ばす指定は使える。
            outputs (bool): Trueなら、このPlug自身の出力先を返す。既定はFalse。
                input、向きとたどり方の指定とは同時に指定できない。indexは使える。

        Returns:
            Plugs | Nodes | list | Plug | Node | tuple | None: 既定は相手のPlugs。indexを指定したら1件かNone。
                ``input=True`` は入力元のPlugかNone(接続が無い場合や、型の条件に合わない場合)。
                ``outputs=True`` は出力先のPlugs(接続が無ければ空)。
                asPairなら(自身側のPlug, 相手側)、asNodeなら相手のNode。
                重複は、通常は相手のPlugごと、asNodeでは相手のNodeごと、asPairでは自身側も含めた組ごとにまとめる。
                値やノードは複製しない。

        Raises:
            TypeError: input・outputsがboolでない場合、または同時に指定できない引数と一緒に指定した場合。
            RuntimeError: ノードまたはアトリビュートが無効な場合。
        """
        ...
    @overload
    def getAnimCurve(self, layer: Node | str | None = ..., *, indirect: bool = ..., suitableType: Literal[True], timeInput: bool | None = ...) -> str | None: ...
    @overload
    def getAnimCurve(self, layer: Node | str | None = ..., *, indirect: bool = ..., suitableType: Literal[False] = ..., timeInput: bool | None = ...) -> Node | None: ...
    @overload
    def getAnimCurve(self, layer: Node | str | None = ..., *, indirect: bool = ..., suitableType: bool = ..., timeInput: bool | None = ...) -> Node | str | None:
        """このPlugのアニメーションカーブ(animCurve ノード)を取得する。

        - ``layer`` を指定しなければ、直接つながっている animCurve だけを探す。pairBlend や
          アニメーションレイヤーを通した、間接的な animCurve は探さない。
        - ``indirect=True`` なら、直接つながっている animCurve が無いときに、``cmds.setKeyframe`` がキーを打つ先の
          カーブ(選んでいる・優先するアニメーションレイヤーのカーブや、pairBlend の先のカーブ)を
          ``cmds.keyframe(plug, q=True, name=True)`` の先頭で取得する。
        - ``layer`` を指定すると、そのアニメーションレイヤーでこのPlugの値を持つカーブを、
          ``cmds.animLayer(layer, q=True, findCurveForPlug=...)`` で取得する。
        - ベースレイヤー(``cmds.animLayer(q=True, root=True)``)を指定し、Plugがどのレイヤーにも
          入っていない場合は、直接つながっている animCurve を返す。
        - ``suitableType=True`` なら、カーブではなく、**このPlugの値の型に合うアニメーションカーブのノード型の名前**
          (``animCurveTA`` など)を返す。**つながっているカーブの型ではない**。カーブがつながっていなくても答え、
          カーブや接続は作らない(これからカーブを作るときに、どの型で作るかを調べるためのもの)。
          つながっているカーブの型は ``plug.getAnimCurve().getType()`` で取得する。

        Args:
            layer (Node | str | None): アニメーションレイヤー(animLayer ノード)か、その名前。既定は None。
            indirect (bool): Trueなら、直接のカーブが無いときに、レイヤーや pairBlend の先のカーブも探す。
                layer とは同時に指定できない。既定は False。
            suitableType (bool): Trueなら、このPlugに合うアニメーションカーブのノード型の名前を返す。既定は False。
                layer・indirect とは同時に指定できない。
            timeInput (bool | None): ``suitableType=True`` のときだけ指定できる。True(省略したときも同じ)なら
                時間入力のカーブ(``animCurveT*``)、Falseなら単位なし入力のカーブ(``animCurveU*``。ドリブンキー用)の型。

        Returns:
            Node | str | None: animCurve ノード。無ければ ``None``。
                ``suitableType=True`` では ``animCurveTA`` などの型名。Mayaが適切な型を決められない場合は ``None``。

        Raises:
            TypeError: layer が animLayer ノード・名前・None のどれでもない場合、indirect・suitableType が bool でない場合、
                timeInput が bool でも None でもない場合。suitableType=True と layer・indirect=True を同時に指定した場合、
                または suitableType=False で timeInput を指定した場合。
            ValueError: layer と indirect=True を同時に指定した場合。
            RuntimeError: ノードかアトリビュートが削除されている場合、layer の名前に当たる
                レイヤーが見つからない場合、またはMayaが型の照会を拒否した場合。
        """
        ...
    def getLayeredPlug(self, layer: Node | str | None = ...) -> Plug | None:
        """アニメーションレイヤーで、このPlugの値を受け持つ入力のPlugを取得する。

        返すのは、レイヤーごとのブレンドノード(``animBlendNodeAdditive`` など)の入力(``inputB``)。
        ここにそのレイヤーのキーの animCurve がつながる(キーを打つときや、カーブを調べるときの対象)。
        :meth:`getAnimLayers` と同じく、プロキシ・mute・pairBlend を通ってブレンドのつながりをたどる。

        Args:
            layer (Node | str | None): アニメーションレイヤー(animLayer ノード)か、その名前。

                - None(既定)なら、Plugが入っているいちばん上のレイヤー(どのレイヤーにも入っていなければ自身)。
                - ベースレイヤー(``cmds.animLayer(q=True, root=True)``)なら、ブレンドのつながりのいちばん手前の入力
                  (どのレイヤーにも入っていなければ自身)。

        Returns:
            Plug | None: レイヤーの入力のPlug。指定したレイヤーにPlugが入っていなければ ``None``。

        Raises:
            TypeError: layer が animLayer ノード・名前・None のどれでもない場合。
            RuntimeError: ノードかアトリビュートが削除されている場合、または layer の名前に当たる
                レイヤーが見つからない場合。
        """
        ...
    def connect(self, source: Plug | om2.MPlug | str, *, force: bool = ..., f: bool = ..., lock: bool = ..., l: bool = ..., nextAvailable: bool = ..., na: bool = ..., unlock: bool = ..., skipExisting: bool = ..., fast: bool = ...) -> Plug:
        """sourceから自身へ接続する。

        接続先を返す。既定では、すでに同じ接続があっても例外にする。
        通常はcmds.connectAttrを使い、Undoが有効なら記録する。fastではMDGModifierを使う。
        一時的に外したロックは逆の順に戻す。ただし戻すのに失敗したら例外になり、残りは戻さない。
        接続し終えた変更は、そのあとの失敗だけでは自動で戻さない。

        Args:
            source (Plug | om2.MPlug | str): 接続元。
            force (bool): Trueなら、すでにある入力を置き換える。unlock=Trueなら、接続先と、その上の
                コンパウンドアトリビュート・マルチアトリビュートのロックを一時的に外す。接続元のロックは変えない。
            f (bool): forceの短縮名。どちらかがTrueなら有効(OR)。
            lock (bool): Trueなら、接続したあとにロックする。Falseでも、もとのロックは戻す。
            l (bool): lockの短縮名。どちらかがTrueなら有効(OR)。
            nextAvailable (bool): Trueなら、マルチアトリビュート全体に対して、``cmds.connectAttr(nextAvailable=True)`` と
                同じ決まりで要素を選ぶ(:meth:`MultiPlug.getNextAvailable` の既定と同じ)。接続のある最後の要素の次から、
                入力の接続・ロック・子の入力の接続が無い要素を探す。値を持つだけの要素も候補になり、途中の空きは使わない。
            na (bool): nextAvailableの短縮名。どちらかがTrueなら有効(OR)。
            unlock (bool): Falseなら、forceでもロックを外さない。既定はTrue。
            skipExisting (bool): Trueなら、何度実行してもよいようにする。接続元から接続先への同じ接続
                (unitConversionなどの変換ノードを通したものを含む)がすでにあれば、何も変えず
                (ロックもlockの指定も変えない)、成功したときと同じく接続先を返す。
                nextAvailableでは、接続元がすでにつながっている要素があれば、その要素を返す。
                ほかの入力がある・ロックされているなどの失敗は、既定と同じく例外にする。
                既定はFalseで、同じ接続があってもRuntimeErrorになる。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Plug: 実際の接続先。nextAvailableでは選んだ要素。取得し直すことがあるので、selfと同じオブジェクトとは限らない。

        Raises:
            TypeError: 接続元が指定されていない場合や対応していない型の場合、またはfast・skipExistingがboolでない場合。
            AttributeError: 文字列で渡した名前のアトリビュート(またはノード)が見つからない場合(``MissingAttributeError``)。
            RuntimeError: 次のどれかの場合。同じ接続がすでにある(skipExisting=Falseのとき)。自分自身へ接続しようとした。
                forceなしで入力を置き換えようとした。ロックされている。接続やロックの復元に失敗した。
                接続元・接続先のノードかアトリビュートが削除されている場合も、何も変えずに送出する
                (接続元については、削除前のアトリビュートのパスを文言に入れる)。
        """
        ...
    def disconnect(self, source: Plug | om2.MPlug | str | None = ..., *, force: bool = ..., f: bool = ..., nextAvailable: bool = ..., na: bool = ..., fast: bool = ...) -> Plug | list[Plug]:
        """指定した入力元との、直接の接続を切る。

        子の接続まではたどらず、変換ノードも飛ばさない。変換ノードは削除しない。
        通常はcmds.disconnectAttrを使い、Undoが有効なら記録する。fastではMDGModifierを使う。
        ロックを戻すのに失敗したら、例外にしてそこで止める。切断し終えたものは戻さない。

        Args:
            source (Plug | om2.MPlug | str | None): 入力元。省略するかNoneなら、今の直接の入力。
            force (bool): Trueなら、接続先とその上のロックを一時的に外し、逆の順にロックし直す。入力元のロックは変えない。
            f (bool): forceの短縮名。どちらかがTrueなら有効(OR)。
            nextAvailable (bool): Trueなら、マルチアトリビュートの中で、sourceへ直接つながっている要素の接続をすべて切る。
                sourceを指定したときだけ効く。
            na (bool): nextAvailableの短縮名。どちらかがTrueなら有効(OR)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Plug | list[Plug]: 1つだけ切ったときは、切った入力元のPlug(自身ではない)。

                - sourceを渡した場合は、そのPlug(Plugならそのオブジェクト、MPlug・名前なら、それから求めたPlug)。
                - 省略した場合は、切る前に今の直接の入力として取得したPlug。名前から取得し直さない。

                接続から得た(networkedの)MPlugを持っている場合は、切る前に、同じアトリビュートを指す
                networkedでないMPlugへ持ち替える(自身も同じ。切ったあとも安全に比べたり使ったりできる)。
                マルチアトリビュートの中を探した場合は、接続先の要素のlist。

        Raises:
            TypeError: sourceがboolなど対応していない型の場合、またはfastがboolでない場合。
            AttributeError: 文字列で渡した名前のアトリビュート(またはノード)が見つからない場合(``MissingAttributeError``)。
            RuntimeError: 入力や指定した接続が無い場合、または切断やロックの復元に失敗した場合。

        Note:
            マルチアトリビュートの中を探した場合は、すでにある順に切る。途中で失敗しても、それまでに切った接続は戻さない。
            接続が無いときに何もしない入力の切断には ``disconnectAll(destination=False)`` を使う。
        """
        ...
    def disconnectAll(self, *, source: bool = ..., destination: bool = ..., fast: bool = ...) -> None:
        """直接の接続を、入力、出力の順にすべて切る。

        ロックは外さない。子やマルチアトリビュートの要素に別々につながっている接続までは調べず、変換ノードも削除しない。
        通常は、Undoが有効なら同じチャンクに記録する。途中で失敗しても、それまでに切った接続は戻さない。

        入力だけを切るときは ``disconnectAll(destination=False)`` と書く。:meth:`disconnect` と違い、
        入力が無ければ何もしない(例外にしない)。変換ノードを飛ばさずに今の入力を調べて切る。

        Args:
            source (bool): Trueなら入力の接続を切る。既定はTrue。
            destination (bool): Trueなら出力の接続をすべて切る。既定はTrue。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。接続が無い場合や、両方Falseの場合は何も変えない。
                disconnectが1件のときに返す入力元は返さない。

        Raises:
            TypeError: source・destination・fastがboolでない場合。
            RuntimeError: アトリビュートが無効な場合、またはロックなどで切断できない場合。
        """
        ...
    def connectTo(self, destination: Plug | om2.MPlug | str, *, skipExisting: bool = ..., fast: bool = ..., **kwargs) -> Plug:
        """自身からdestinationへ接続する。

        接続先のPlugを返す。destinationをPlugにしてから、``destination.connect(self, **kwargs)`` で接続する。
        Undoの扱い、force時のロックの復元、マルチアトリビュートの空き番号の選び方(``nextAvailable=True`` は
        ``cmds.connectAttr(nextAvailable=True)`` と同じ決まり)はconnectと同じ。
        fast・skipExistingの指定は、そのままconnectへ渡す。``>>`` 演算子にはskipExistingが無く、同じ接続があると例外にする。

        Args:
            destination (Plug | om2.MPlug | str): 接続先。
            skipExisting (bool): Trueなら、同じ接続がすでにあれば何もせず接続先を返す(:meth:`connect` のskipExisting)。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。対応していない操作は、更新する前に拒否する。
            **kwargs: connectのforce/f・lock/l・nextAvailable/na・unlock。

        Returns:
            Plug: 実際の接続先。skipExistingですでにある接続を見つけた場合も、その接続先。

        Raises:
            TypeError: 接続先が指定されていない場合や対応していない型の場合、またはfast・skipExistingがboolでない場合
                (:meth:`connect` と同じ)。
            AttributeError: 文字列で渡した名前のアトリビュート(またはノード)が見つからない場合(``MissingAttributeError``)。
            RuntimeError: 同じ接続がすでにある(skipExisting=Falseのとき)・forceなしで入力を置き換えようとした・
                ロックされている・接続に失敗した場合、または接続元・接続先が削除されている場合(:meth:`connect` と同じ)。
        """
        ...
    def insertInput(self, node: str | Node, inputAttribute: str, outputAttribute: str) -> None:
        """今の入力の接続の間に、ノードを挟む。

        ``入力元 → node.inputAttribute`` と ``node.outputAttribute → 自身`` の2つの接続にする。

        - 入力元は、unitConversion 系を飛ばした先のPlug(``getConnections(input=True, skipConversionNodes=True)``)。
          挟んだあとに変換ノードが要るかどうかは、Mayaが決める。
        - 入力の接続が無い場合は、``node.outputAttribute → 自身`` だけを接続する。
        - 自身がロックされていれば、:meth:`connect` と同じく一時的に外して接続する。

        cmdsで接続し、1回のUndoで戻せる。

        Args:
            node (str | Node): 挟むノード。
            inputAttribute (str): もとの入力元をつなぐ、node のアトリビュート名。
            outputAttribute (str): 自身へつなぐ、node のアトリビュート名。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: node が対応していない型の場合、または inputAttribute・outputAttribute が文字列でない場合。
            ValueError: inputAttribute・outputAttribute が空文字列の場合。
            AttributeError: node にその名前のアトリビュートが無い場合(``MissingAttributeError``)。
            RuntimeError: 自身か node が無効な場合、
                node の入力側にすでに入力の接続がある場合、または Maya が接続を拒否した場合。
        """
        ...
    def _full_name(self) -> str:
        """maya.cmdsで1つに決まるPlugの名前(:meth:`getName` の ``full=True``)を、引数の検査なしで取得する。

        ``<Node.getName()の名前>.<アトリビュートのパス>`` の形で、名前の変更や親の付け替えに追従する。
        アトリビュートの部分はロング名と必要な論理番号を含み、エイリアスがあればそれを使う。

        Returns:
            str: 1つに決まるPlugの名前。ノードやアトリビュートが削除されていれば空文字列。
        """
        ...
    __str__: Any
    def _anim_layer_names(self, selected: bool = ..., exact: bool = ...) -> list[str]:
        """このアトリビュートへの入力をさかのぼって、アニメーションレイヤーの名前を取得する。

        上のレイヤーから順に並べる。

        Args:
            selected (bool): Trueなら、選択しているレイヤーだけにする。既定はFalse。
            exact (bool): Trueなら、selected=Trueのときにベースレイヤーも選択されているかで絞る。既定はFalse。

        Returns:
            list[str]: レイヤーの名前。条件に合えば、最後にベースレイヤーを含む。
        """
        ...
    def _anim_layer_name(self, layer: Node | str) -> str:
        """animLayer ノードまたはその名前を検証し、一意な名前を返す。

        Args:
            layer (Node | str): animLayer ノードまたはその名前。

        Returns:
            str: animLayer ノードの名前。

        Raises:
            TypeError: layer が animLayer ノード・名前以外の場合。
            RuntimeError: layer の名前を解決できない場合。
        """
        ...
    def _layer_inputs(self) -> tuple[list[tuple[str, Plug]], Plug]:
        """アニメーションレイヤーのブレンドのつながりを上からたどり、各レイヤーの入力を集める。

        :meth:`getAnimLayers` と同じ決まり(プロキシの元・mute の input・pairBlend で使っている入力)でたどる。

        Returns:
            tuple[list[tuple[str, Plug]], Plug]: 上から順の (レイヤー名, ブレンドノードの inputB) の組と、
                つながりのいちばん手前の入力(最後のブレンドノードの inputA。レイヤーが無ければ自身)。
        """
        ...
    def _attribute_plugs(self, attributes: om2.MObjectArray) -> list[Plug]:
        """同じノードのアトリビュートの定義の並びを、重複の無い Plug のリストにする。

        getAffected などで共通に使う。マルチアトリビュートの中の子(要素の番号が決まらないもの)は、
        いちばん外側のマルチアトリビュートにまとめる。

        Args:
            attributes (om2.MObjectArray): アトリビュート定義の MObject。

        Returns:
            list[Plug]: 定義の順の Plug。
        """
        ...
    def _raw_default(self) -> Any:
        """アトリビュートの定義の既定値を、単位付きのom2の値のまま返す。

        アトリビュートの複製やリセットで使う。

        Returns:
            object | None: 既定値(MAngle・MDistance・MTime・数値・tuple・enumのint)。対応していない型ならNone。

        Raises:
            RuntimeError: ノードが無効な場合、またはアトリビュートが削除されている場合。
        """
        ...
    def _layer_anim_curve(self, layer: Node | str) -> Node | None:
        """アニメーションレイヤーで、このPlugの値を持つ animCurve を取得する。

        getAnimCurve で layer を指定したときに使う。

        Args:
            layer (Node | str): animLayer ノードか、その名前。

        Returns:
            Node | None: animCurve ノード。無ければ None。

        Raises:
            TypeError: layer が animLayer ノードでも名前でもない場合。
            RuntimeError: layer の名前に当たるレイヤーが見つからない場合。
        """
        ...
    def _source_plug(self, skipConversionNodes: bool = ...) -> Plug | None:
        """このPlug自身の入力元のPlugを返す(``getConnections(input=True)`` の絞り込みなしの本体)。

        有効かどうかは呼び出し側が確かめておく。子・マルチアトリビュートの要素の接続は調べない。

        Args:
            skipConversionNodes (bool): Trueなら、unitConversion系のノードを飛ばした先のPlugを返す。

        Returns:
            Plug | None: 入力元の Plug。未接続ならNone。
        """
        ...
    def _destination_plugs(self, skipConversionNodes: bool = ...) -> list[Plug]:
        """このPlug自身の出力先のPlugを返す(``getConnections(outputs=True)`` の絞り込みなしの本体)。

        有効かどうかは呼び出し側が確かめておく。子・マルチアトリビュートの要素の接続は調べない。

        Args:
            skipConversionNodes (bool): Trueなら、unitConversion系のノードを飛ばした先のPlugを返す。

        Returns:
            list[Plug]: 出力先の Plug。未接続なら空リスト。
        """
        ...
    def _set_template(self, value: object, safe: bool, *, fast: bool, check: bool = ..., unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., _writer: Callable[..., Any] | None = ..., **options) -> int | None:
        """set()の共通の流れを受け持つ。

        受け持つのは、safeでのUndoのまとめ・マルチアトリビュート全体の拒否・fastに対応していない型の事前の確認・
        safeでの例外の吸収。派生クラスが上書きするのは、値を書き込む :meth:`_set_value` と、
        safeでやり直す :meth:`_set_children_safely` だけ。Undoチャンクの名前は ``mlib<クラス名>Set``。

        Args:
            value (object): 書き込む値。
            safe (bool): Trueなら、失敗を例外にせず数える。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に値が有限かを確かめ、書き込めるかの確認を書き込み側へ指示する。
            unit (str | None): 数値の角度の単位。Noneは度。ここで一度だけラジアンへ換算し、
                書き込みとsafeのやり直しには内部単位の値を渡す。
            timeUnit (str | None): 数値の時間の単位。Noneはフレーム。unitと同じく、ここで一度だけ秒へ換算する。
            uiUnits (bool): Trueなら、UIの単位の数値。unit・timeUnitとは同時に指定できない。
            _writer (callable | None): 内部専用。値の書き込みに使う関数(既定は自身の ``_set_value``)。
                Transform が、Double3 の回転の変換を通さずに基底の書き込みを使うときに ``Plug._set_value`` を渡す。
            **options: ``_set_value`` と ``_set_children_safely`` へ渡す追加の指定。

        Returns:
            int | None: safe=Falseなら値を返さない。safe=Trueなら、成功は0、失敗は失敗の数。

        Raises:
            TypeError: fastがboolでない場合、またはマルチアトリビュート全体に設定しようとした場合。
                safe=Trueでも例外にする。safe=Falseなら、unit・timeUnitが文字列でもNoneでもない場合にも送出する。
            ValueError: safe=Falseで、unit・timeUnitが対応していない場合、またはuiUnits=Trueと同時に指定した場合。
                safe=Trueでは、どちらも書き込む前の失敗として1を返す。
            NotImplementedError: fastに対応していない型の場合。safe=Trueでも例外にする。
        """
        ...
    def _set_value(self, value: object, *, uiUnits: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """値の型と単位を揃えて、指定した方法(cmdsかOpenMaya)で書き込む。

        safeのやり直しとUndoチャンクは、呼び出し元で扱う。

        Args:
            value (object): 書き込む値。
            uiUnits (bool): TrueならUI単位から内部単位へ変換する。
            fast (bool): TrueならOpenMayaで直接更新する。
            check (bool): Trueなら、書き込む前に、書き込めるかを確かめる。

        Returns:
            None: 値を返さない。
        """
        ...
    def _set_children_safely(self, value: object, *, uiUnits: bool = ..., fast: bool = ...) -> int:
        """失敗したコンパウンドアトリビュートの値を、子の定義順に1つずつやり直し、失敗の数を返す。

        子の値に分けられない場合や、やり直しを終えられない失敗は1とする。書き込めた子は戻さない。

        Args:
            value (object): 最初の設定へ渡した値。
            uiUnits (bool): 子のsetへ渡す単位の指定。
            fast (bool): 子のsetへ渡す、更新の方法。

        Returns:
            int: 子の失敗の数。子の値に分けられない失敗は1。
        """
        ...
    def _get_value(self) -> Any:
        """アトリビュートの値を評価して取得する。

        最初に呼んだときに読み取り関数を選んで覚えておき、値そのものは毎回読み直す。
        generic/kAnyがマトリクスかどうかも値を読むときに調べ、Pythonのクラスは変えない。

        - bool/int/float 系の数値、角度・距離・時間の単位付き、enum、文字列と、対応している型付きの並びは、
          Maya API 2.0で直接読む。MEL コマンドを往復しないので速い。角度はrad、距離はcm、時間は秒(内部単位)で返す。
        - message アトリビュートや、mesh・カーブなどの複雑な typed data アトリビュートのように、
          対応する読み方が無いものは ``cmds.getAttr`` で読む。

        Returns:
            object: アトリビュートの値。文字列・数値・並び・None など、実際のアトリビュートの型による。
                ``cmds.getAttr`` で読んだ結果が、tupleを1つだけ入れたリストなら、そのtupleを返す。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合
                (:meth:`isValid` が ``False``。削除前の古い値は返さない)。
                Maya 内部のデータ型(nurbsSurface の ``patchUVIds`` など)の、まだ無い
                マルチアトリビュートの要素の場合も含む(値を読むと Maya が異常終了することがあるため。
                :func:`mlib.core.attributeType.is_internal_data_type`)。
        """
        ...
    @staticmethod
    def _under_multi_element(mplug: om2.MPlug) -> bool:
        """Plugが、マルチアトリビュート・その要素・要素の下のアトリビュートのどれかかを判定する。

        Args:
            mplug (om2.MPlug): 調べるPlug。

        Returns:
            bool: 自身がマルチアトリビュートか、自身か親のどれかがマルチアトリビュートの要素ならTrue。
        """
        ...
    def _record_connection_value(self):
        """今の(接続されていない)値をUndoに記録し、接続をUndoしたときに元の値へ戻せるようにする。

        対象は、マルチアトリビュートの要素とその下のアトリビュートだけ。それ以外は、接続のUndoで
        Mayaが元の値へ戻す(``blendWeighted.input[n]`` のような要素は、Undoで値が0になる)。
        まだ無いマルチアトリビュートの要素は作らない。対象は、数値・単位付き・enumなど、
        共通の数値の操作で扱えるものだけ。Undoが無効なら記録されないので、同じ値の書き込みそのものを省く。
        """
        ...
    def _compound_descendants(self) -> list[om2.MPlug]:
        """コンパウンドアトリビュートの子孫のMPlugを、親から定義順に返す。

        Returns:
            list[om2.MPlug]: 子孫のMPlug。コンパウンドアトリビュートでなければ空。マルチアトリビュートの要素は含めない。
        """
        ...
    def _has_input_from(self, source: Plug) -> bool:
        """sourceからの入力があるか判定する。直接の入力と、unitConversionなどの変換ノードを通した入力の両方を見る。

        Args:
            source (Plug): 接続元。

        Returns:
            bool: Mayaが同じ接続とみなす入力がある場合はTrue。
        """
        ...
    def _existing_connection_target(self, source: Plug, next_available: bool) -> Plug | None:
        """safe=Trueの接続で、既にある同じ接続の接続先を返す。

        Args:
            source (Plug): 接続元。
            next_available (bool): マルチアトリビュートの要素から探すか。

        Returns:
            Plug | None: 同じ接続の接続先。無ければNone。
        """
        ...
    def _get_at_time(self, time: float | om2.MTime, unit: str | None, time_unit: str | None, ui_units: bool) -> Any:
        """現在時刻を動かさず、指定の評価コンテキストでgetを呼ぶ。

        Args:
            time (float | om2.MTime): UI時間単位のフレームか、単位を持つ時刻。
            unit (str | None): 返す角度の単位。
            time_unit (str | None): 返す時間の値の単位。
            ui_units (bool): Trueなら返す数値をUI単位へ換算する。

        Returns:
            object: 通常のgetと同じ型の値。

        Raises:
            TypeError: timeの型が不正な場合。
            ValueError: timeが有限でない場合。
            NotImplementedError: cmds.getAttrでの読み取りが必要な型の場合。
        """
        ...
    def _require_range_order(self, fn: om2.MFnNumericAttribute | om2.MFnUnitAttribute, numbers: dict[str, float], angle_unit: str, time_unit: str):
        """片側だけを設定するときに、設定済みの反対側と矛盾しないことを確かめる。

        Mayaは、最小と最大が逆になる値を、警告を出すだけで無視するため。

        Args:
            fn (om2.MFnNumericAttribute | om2.MFnUnitAttribute): 対象の定義。
            numbers (dict[str, float]): ``"Min"`` か ``"Max"`` をキーにした、``cmds.addAttr`` の単位へ換算した設定値。
            angle_unit (str): 角度の数値の単位。
            time_unit (str): 時間の数値の単位。

        Raises:
            ValueError: 最小値が既存の最大値より大きい、または最大値が既存の最小値より小さい場合。
        """
        ...
    def _range_input(self, fn: om2.MFnNumericAttribute | om2.MFnUnitAttribute, value: object, angle_unit: str, method: str, time_unit: str = ...) -> float:
        """setRangeの値を、``cmds.addAttr`` が受け取る単位の数値へ換算する。

        ``cmds.addAttr`` は角度をrad、距離をcm、時間を現在の時間単位で受け取る(:meth:`Node.addAttr` と同じ換算)。

        Args:
            fn (om2.MFnNumericAttribute | om2.MFnUnitAttribute): 対象の定義。
            value (object): 数値または単位付きの値。
            angle_unit (str): 角度の数値の単位(``"deg"`` / ``"rad"``)。
            method (str): 例外メッセージに使うメソッド名。
            time_unit (str): 時間の数値の単位(``"frame"`` / ``"sec"``)。

        Returns:
            float: 換算した値。

        Raises:
            TypeError: 数値・対応する単位付きの値以外の場合。
        """
        ...
    def _set_generic_matrix(self, matrix: Matrix, fast: bool):
        """generic/kAnyのアトリビュートへ定数のマトリクスを書き込む。

        通常は ``cmds.setAttr(type="matrix")`` を使い、fastではマトリクスのデータをMPlugへ直接設定する。
        Mayaの ``setAttr`` がマトリクスのデータを受け付けないアトリビュート(``choice.input`` などの組み込みの
        generic)では、保存したシーンをMayaが読み込めなくなる(``setAttr`` の行がエラーになり、値が失われる)。
        そのため、fastでも書き込まずにTypeErrorにする。

        Args:
            matrix (Matrix): 書き込む値。
            fast (bool): TrueならOpenMayaで直接更新する。

        Raises:
            TypeError: アトリビュートがマトリクスのデータを受け付けない場合。
            RuntimeError: ロック・入力接続・書込み禁止の場合。
        """
        ...
    @staticmethod
    def _connection_results(pairs: Iterable[tuple[Plug, Plug]], node_type: str | None, exact: bool, as_pair: bool, as_node: bool, index: int | None) -> Plugs | Nodes | list | Plug | Node | tuple | None:
        """接続の組を相手のノードの型で絞り、最初に出てきた順のPlug・Nodeの一覧にする。

        重複を除いたあとでindexを当てはめる。組で返すときは、入力の向きでも自身側を先にする。

        Args:
            pairs (Iterable[tuple[Plug, Plug]]): (自身側, 相手側)の並び。
            node_type (str | None): 相手のMayaのノード型。Noneなら型で絞らない。
            exact (bool): Trueならノード型名が完全に一致するものだけ。Falseなら派生した型も含める。
            as_pair (bool): Trueなら、自身側と相手側の組で返す。
            as_node (bool): Trueなら、相手側だけをNodeにする。
            index (int | None): 結果の、Pythonでの位置の番号。負の数も使える。

        Returns:
            Plugs | Nodes | list | Plug | Node | tuple | None: 一覧(PlugならPlugs、NodeならNodes、組ならlist)、
                またはindexで選んだ1件。範囲外ならNone。
        """
        ...
    def _temporarily_unlocked_connection_path(self, enabled: bool, *, fast: bool = ...) -> GeneratorContextManager[None]:
        """接続先とその上のロックを一時的に外し、外した逆の順にロックし直す。

        もとからロックされていたPlugだけを戻す。接続を変えたことでnetworkedのMPlugが
        使えなくなる場合に備え、戻すときは覚えておいたアトリビュートのパスからPlugを取得し直す。

        Args:
            enabled (bool): Trueなら自身と上位のロックを一時解除する。
            fast (bool): ロックの解除と復元へ同じ更新経路を渡す。

        Yields:
            None: 接続の編集を行う区間。

        Note:
            解除途中の失敗は解除処理が復元を試みる。編集後の復元失敗はその例外を送出し、
            残りの復元を行わない。編集も失敗していれば、その例外を ``__context__`` に残す。
            接続の変更や値をロールバックするコンテキストではない。
        """
        ...
    def _unlock_connection_path(self, *, fast: bool = ...) -> list[Plug]:
        """自身とその上のロックを一時的に外し、あとでロックし直すPlugを返す。

        Args:
            fast (bool): ロックを外すときと、途中で失敗してロックし直すときに渡す、更新の方法。

        Returns:
            list[Plug]: 実際にロックを外したPlug。上から自身への順に並ぶ。
        """
        ...
    @staticmethod
    def _plug_path(mplug: om2.MPlug) -> str:
        """ノード名を除いた、maya.cmds で解決できるアトリビュートパスを返す。

        ロング名と、必要な論理番号(``worldMatrix[0]``、``pnts[2].pntx`` 等)・
        インスタンス番号を含み、エイリアスがあればエイリアス名を使う
        (``MPlug.name()`` のアトリビュート部分と同じ表記)。

        Args:
            mplug (om2.MPlug): 対象のプラグ。

        Returns:
            str: ``translateX`` や ``worldMatrix[0]`` のようなアトリビュートパス。
        """
        ...
    @staticmethod
    def _mplug_attribute_exists(mplug: om2.MPlug, node: om2.MObject | None = ...) -> bool:
        """MPlug のアトリビュートが、持ち主のノードにあるか判定する(ノードは有効であること)。

        ``deleteAttr`` で削除した動的アトリビュートの MPlug は、Undo のためにアトリビュートの MObject が
        残っている場合があり、``MObjectHandle.isValid()`` だけでは判定できない。そのため、ノードの
        ``MFnDependencyNode.attributeClass()`` で確かめる(ノードに無いアトリビュートは ``kInvalidAttr``)。

        Args:
            mplug (om2.MPlug): 判定するPlug。
            node (om2.MObject | None): 持ち主のノード。分かっているときに指定する。

        Returns:
            bool: アトリビュートが存在する場合は True。
        """
        ...
    @staticmethod
    def _mplug_name(mplug: om2.MPlug) -> str:
        """MPlug を、``Plug._full_name()`` と同じ形の、1つに決まるPlugの名前にする。

        持ち主のノードが、Undo で戻せない形で削除された(``flushUndo`` のあと・Undo が無効・シーンの
        切り替え)MPlug では、``MPlug.node()`` を呼んだ時点で Maya が異常終了し、API では見分けられない。
        削除をまたいで持ち続けるなら、mlibのPlugを使う。

        Args:
            mplug (om2.MPlug): 変換するMPlug。

        Returns:
            str: ``<ノードの最短一意名>.<アトリビュートパス>``。

        Raises:
            ValueError: 空の MPlug の場合、ノードが削除されている場合、またはアトリビュートが削除されている(``deleteAttr``)場合。
        """
        ...
    @staticmethod
    def _deleted_attribute_error(plug: Plug) -> DeletedAttributeError | None:
        """ノードは残っていてアトリビュートだけが削除された Plug なら、送出する例外を返す。

        当てはまらなければ None を返す。

        Args:
            plug (Plug): 判定する mlib の Plug。

        Returns:
            DeletedAttributeError | None: アトリビュートが ``deleteAttr`` で削除されていれば、送出する例外。
                ノードが削除されている場合(無効なノードとして扱う)と、有効な Plug では None。
        """
        ...
    @staticmethod
    def _find_plug(mobject: om2.MObject, name: str) -> om2.MPlug | None:
        """ノードのアトリビュート名(ロング名・ショート名・エイリアス)から MPlug を求める。

        ``MFnDependencyNode.findPlug()`` はエイリアスを扱わない。そのため、見つからなければ
        エイリアスの一覧(``bs.smile`` → ``weight[0]`` など)からアトリビュートのパスを求めて探す。

        Args:
            mobject (om2.MObject): 持ち主のノード。
            name (str): アトリビュート名。

        Returns:
            om2.MPlug | None: 見つかったPlug。アトリビュートが無ければ None。
        """
        ...
    @staticmethod
    def _has_out_of_range_index(attribute_path: str) -> bool:
        """アトリビュートパスが :data:`MAX_LOGICAL_INDEX` を超える論理番号を含むか判定する。

        Args:
            attribute_path (str): ノード名を含まないアトリビュートパス(``input1D[4294967296]`` など)。

        Returns:
            bool: 範囲外の番号を含む場合は True。
        """
        ...
    @staticmethod
    def _has_unresolved_index(mplug: om2.MPlug) -> bool:
        """論理番号が決まっていない(-1の)マルチアトリビュートの要素を途中に含むPlugか判定する。

        コンパウンドアトリビュートでもあるマルチアトリビュートの子を、``findPlug("input3Dx")`` のように
        要素を指定せずに取得すると、``input3D[-1].input3Dx`` のようなPlugになり、maya.cmds では扱えない。

        Args:
            mplug (om2.MPlug): 判定するPlug。

        Returns:
            bool: 決まっていない番号を含めば True。
        """
        ...
    @staticmethod
    def _attribute_path_plug(mobject: om2.MObject, attribute_path: str, first: om2.MPlug | None = ...) -> om2.MPlug | None:
        """ノードとアトリビュートのパス(``input1D[3]``、``pnts[2].pntx`` など)から MPlug を求める。

        ``.`` で区切った各部分のアトリビュート名(ロング名・ショート名。先頭はエイリアスも使える)と、
        ``[i]`` の論理番号を順にたどる。まだ無いマルチアトリビュートの要素もPlugとして返すが、
        要素は作らない(シーンを変えない)。

        Args:
            mobject (om2.MObject): 持ち主のノード。
            attribute_path (str): ノード名を含まないアトリビュートのパス。
            first (om2.MPlug | None): 先頭の部分のアトリビュート名に当たるPlugがすでに分かっているときに指定する
                (transform からシェイプへ広げて探した場合など)。

        Returns:
            om2.MPlug | None: 見つかったPlug。アトリビュートとして扱えない場合は None。たとえば、無いアトリビュート、
                範囲の指定、マルチアトリビュートでないアトリビュートへの番号、:data:`MAX_LOGICAL_INDEX` を超える番号、
                マルチアトリビュートの要素の番号を指定していない子のアトリビュートなど。
        """
        ...
    @staticmethod
    def _plug_from_path(text: str) -> tuple[om2.MObject | om2.MDagPath, om2.MPlug] | None:
        """``"node.attr[i].child"`` の形の文字列から、ノードの部分とアトリビュートのパスをたどって MPlug を求める。

        mesh の ``pnts[i]``、nurbsCurve・nurbsSurface・lattice の ``controlPoints[i]`` のように、
        コンポーネントの名前としても読めるアトリビュートは、MSelectionList が頂点・CV として登録してしまい、
        Plugとして取り出せない。そのため、Plug の入力を求めるときは、この関数で求め直す
        (maya.cmds の ``connectAttr``/``setAttr`` などと同じく、アトリビュートとして扱う)。
        transform の名前でシェイプのアトリビュートを指す場合(``pCube1.pnts[3]``)は、
        ただ1つのシェイプ(中間オブジェクトを除く)へ広げて探す。

        Args:
            text (str): アトリビュートを指す名前。

        Returns:
            tuple[om2.MObject | om2.MDagPath, om2.MPlug] | None: 持ち主のノード(DAG ノードなら、
                名前が指すインスタンスの MDagPath)とPlug。アトリビュートとして扱えない場合
                (無いアトリビュート、範囲の指定、マルチアトリビュートでないアトリビュートへの番号など)は None。
        """
        ...
    @staticmethod
    def _unnetworked(mplug: om2.MPlug) -> om2.MPlug:
        """接続から得た(networkedの)MPlugを、同じアトリビュートを指す、networkedでないMPlugにする。

        networkedのMPlugは、接続を切ると破棄される。切断したあとも使うものは、これで持ち替える。

        Args:
            mplug (om2.MPlug): 変換するMPlug。

        Returns:
            om2.MPlug: networkedでなければそのまま。networkedなら、マルチアトリビュートの要素・子をたどって作り直したMPlug。
        """
        ...
    @staticmethod
    def _resolve_input(value: Plug | om2.MPlug | str) -> Plug:
        """渡されたものを mlib の Plug にする。

        文字列は、maya.cmds と同じ決まりで探す。``str(plug)``・``plug._full_name()`` が返す形
        (``grp1|dup.translateX``、``bs.weight[0]``、エイリアス名、``cubeShape.pnts[2].pntx`` など)も使える。

        - インスタンス化された DAG ノードのアトリビュートでは、名前が指すインスタンスのノードを持ち主にする。
        - コンポーネントの名前としても読めるアトリビュート(mesh の ``pnts[i]``、nurbsCurve・lattice の
          ``controlPoints[i]`` など)は、``connectAttr`` などと同じく、アトリビュートとして扱う。

        Args:
            value (Plug | om2.MPlug | str): Plug、MPlug、または ``"node.attribute"`` の形のアトリビュート名。

        Returns:
            Plug: value が Plug ならそのまま返す(削除されていても例外にしない。``Plug.isValid()`` で
                確かめる)。それ以外は、アトリビュートの型に合った Plug。

        Raises:
            TypeError: 対応していない型の場合、または文字列がアトリビュートを指していない場合。
            ValueError: 空文字列の場合、または空の MPlug の場合。
            MissingAttributeError: 文字列のアトリビュート(またはノード)が無い場合。
                ``AttributeError`` の派生クラス。
            RuntimeError: 文字列が複数のものに一致する場合。
                MPlug のノードが削除されている場合や、アトリビュートが ``deleteAttr`` で削除されている場合も含む
                (``Node(...)``・``Plug(...)`` を作るときと同じ。Undo で戻せない形で削除された
                ノードの MPlug は見分けられず、Maya が異常終了する)。
        """
        ...
    def _enum_attribute(self, caller: str) -> om2.MObject:
        """有効性を確かめ済みの前提で、enumアトリビュートの定義を返す。

        Args:
            caller (str): エラー表示に使うメソッド名。

        Returns:
            om2.MObject: enumアトリビュートの定義。

        Raises:
            TypeError: enumアトリビュートでない場合。
        """
        ...
    def _enum_field_name(self, attr: om2.MObject, value: int) -> str:
        """enumの値に対応するフィールド名を返す。

        Args:
            attr (om2.MObject): enumアトリビュートの定義。
            value (int): enum値。

        Returns:
            str: フィールド名。

        Raises:
            ValueError: 対応するフィールドが無い場合(MayaのRuntimeErrorを読み替える)。
        """
        ...
    def _label(self) -> str:
        """エラーの表示に使う名前を返す。削除されていても、作ったときのアトリビュートのパスで示す。

        Returns:
            str: 有効なら ``getName(full=True)`` と同じ名前。無効なら、ノード名(削除されていれば
                ``<削除されたノード>``)と、作ったときのアトリビュートのパス。
        """
        ...
    def _attribute_exists(self) -> bool:
        """アトリビュートが、まだノードにあるか判定する(ノードは有効であること)。

        よく呼ばれる :meth:`_require_valid`・:meth:`_full_name` は、呼び出しの負荷を
        避けるため、同じ判定を直接書いている(変えるときは両方を揃えること)。

        Returns:
            bool: 静的アトリビュート、または削除されていない動的アトリビュートの場合は True。
        """
        ...
    def _require_valid(self, action: str = ...) -> None:
        """ノードとアトリビュートが有効か確かめる。

        削除した動的アトリビュートの MPlug で値を読み書きすると、Maya が異常終了する。削除したノードの
        MPlug は古い値を返す(Undo で戻せない形の削除では、問い合わせただけで異常終了することもある)。
        そのため、MPlug やアトリビュートを扱う前に必ず確かめる。

        - 静的アトリビュートは、ノードが有効な間は必ずあるので、ノードを確かめるだけで済む。
        - 動的アトリビュートは、ノードの ``MFnDependencyNode.attributeClass()`` で、あるかどうかを確かめる
          (:meth:`_attribute_exists`)。

        Args:
            action (str): 例外メッセージに使う動作の名詞句(``無効なPlugのため、{action}はできません``)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードかアトリビュートが削除されている場合。
        """
        ...
    def _range_value(self, value: object, angle_unit: str | None, ui_units: bool, time_unit: str | None = ...) -> Any:
        """getRange等の戻り値を、uiUnits・unit・timeUnitの指定に従って換算する。

        Args:
            value (object): 定義から読んだ値(単位付きオブジェクト・数値・tuple)。
            angle_unit (str | None): ``"deg"`` / ``"rad"``。Noneは角度を換算しない。
            ui_units (bool): Trueは現在のUI単位の数値へ換算する。
            time_unit (str | None): ``"frame"`` / ``"sec"``。Noneは時間を換算しない。

        Returns:
            object: 換算した値。
        """
        ...
    def _plain_range_value(self, value: object, angle_unit: str, ui_units: bool, time_unit: str) -> Any:
        """定義から読んだ値を、get() と同じ規則の数値(角度・時間は指定の単位、距離はcm)へ換算する。

        Args:
            value (object): 定義から読んだ値(単位付きオブジェクト・数値・tuple)。
            angle_unit (str): ``"deg"`` / ``"rad"``。
            ui_units (bool): Trueは現在のUI単位の数値へ換算する。
            time_unit (str): ``"frame"`` / ``"sec"``。

        Returns:
            object: 換算した値。
        """
        ...
    def _range_attribute_fn(self) -> om2.MFnNumericAttribute | om2.MFnUnitAttribute | None:
        """有効なことを確かめてから、範囲(最小・最大)を調べられる型のFunction Setを返す。

        Returns:
            om2.MFnNumericAttribute | om2.MFnUnitAttribute | None: 数値・単位付きの型のFunction Set。
                対応していないアトリビュートの型ならNone。
        """
        ...
    @staticmethod
    def _target_class(mplug: om2.MPlug) -> type:
        """MPlugに合ったPlugのクラスを選ぶ。

        マルチアトリビュート・登録したアトリビュートの型・コンパウンドアトリビュートの順に調べる
        (規則は :meth:`__new__` の説明を参照)。

        Args:
            mplug (om2.MPlug): 包む Maya API 2.0 のPlug。

        Returns:
            type: Plug、またはその派生クラス。
        """
        ...
    @staticmethod
    def _wrap_owned(node: Node, mplug: om2.MPlug) -> Plug:
        """持ち主が分かっているMPlugから、``Plug(node, mplug)`` と同じPlugを作る。

        有効なノードから今取得したMPlugに使う。ノードが有効か、MPlugの持ち主がnodeかは確かめない
        (呼び出し元が保証する)。アトリビュートの有無と、決まっていない論理番号は確かめる。

        Args:
            node (Node): Plugの持ち主のノード。有効であること。
            mplug (om2.MPlug): nodeから取得したMPlug。

        Returns:
            Plug: 型に合ったクラスの新しいオブジェクト。

        Raises:
            RuntimeError: アトリビュートが削除されている場合、または決まっていない(-1)論理番号を含む場合。
        """
        ...
    def _unit_kinds(self) -> frozenset[str]:
        """このPlugとその下に、数値を換算する単位(角度・時間)の成分があるかを返す。

        単位は定義で決まるので、Plugごとに一度だけ調べる。孫を持つPlugとマルチアトリビュートは、
        たどらずに両方あるものとして扱う(換算する側が成分ごとに調べる)。

        Returns:
            frozenset[str]: ``"angle"`` と ``"time"`` のうち、成分があるもの。
        """
        ...
    def _static_entry(self) -> tuple:
        """静的アトリビュートのPlugを作り直すための情報を返す。持ち主のノードが名前ごとに覚える。

        静的アトリビュートは削除も改名もできないので、ノードが有効な間は同じ情報からPlugを作れる。
        登録した型のクラスは覚えず、型名から毎回選ぶ(型の登録を後から変えても、新しい登録が使われる)。

        Returns:
            tuple: :meth:`_from_static_entry` へ渡す情報。
        """
        ...
    @staticmethod
    def _from_static_entry(node: Node, entry: tuple) -> Plug:
        """ノードが覚えた静的アトリビュートの情報から、新しいPlugを作る。

        ``Plug(node, mplug)`` と同じクラスと中身になる。持ち主・未解決の論理番号・アトリビュートの
        有無は、覚えたときに確かめてあるので調べ直さない。ノードが有効なことは呼び出し元が確かめる。

        Args:
            node (Node): Plugの持ち主のノード。情報を覚えたノードと同じオブジェクト。
            entry (tuple): :meth:`_static_entry` が返した情報。

        Returns:
            Plug: 型に合ったクラスの新しいオブジェクト。
        """
        ...
    def _require_writable(self):
        """このPlugと、コンパウンドアトリビュートのすべての子に書き込めるか確かめる。シーンは変えない。

        Raises:
            RuntimeError: アトリビュートが無効な場合、ロックや入力の接続がある場合、または書き込めない定義の場合。
        """
        ...
    @staticmethod
    def _node_from_mplug(mplug: om2.MPlug) -> Node:
        """MPlug の持ち主のノードから、登録した型に合った Node を作る。

        Args:
            mplug (om2.MPlug): 持ち主のノードを取得するPlug。

        Returns:
            Node: 持ち主のノードの型に合ったオブジェクト。
        """
        ...
    def __getitem__(self, key: int | str) -> Plug: ...
    def __iter__(self) -> Iterator[Plug]: ...


class Plugs(_ListMethods):
    """アトリビュート(Plug)を、渡した順に重複を除いて持つコレクション。

    :class:`~mlib.nodes.node.Nodes` と同じく、同じアトリビュート(``Plug`` の ``==`` が等しいもの)は
    先に出てきた方だけを残し、渡した順を保つ。

    - ``len``・番号での取得(sliceならPlugs)・``for``・``bool``・``in``・``+``・``==``・:meth:`sort` が使える。
    - 自分に無い公開メソッドの名前(``get``・``set`` など)は、各要素の同じ名前のメソッドへ転送し、戻り値を同じ順のリストで返す。
    - Pythonのlistと同じ名前の ``append``・``extend``・``insert``・``remove``・``pop``・``index``・``count``・``clear``・``reverse`` と、
      番号への代入・``del``・``+=`` も使える。足す値は作るときと同じ決まりで確かめ、すでにある要素は足さない。
    - コピーやスライスは同じPlugを共有する。値は持たない。
    - ``maya.cmds`` へ渡すと、cmdsが並びとして各Plugの名前に展開する(マルチアトリビュート全体や
      コンパウンドアトリビュートのPlugも、要素としては名前になる)。
    - ``==`` を定義しているので、listと同じくハッシュ値を持たない。

    .. code-block:: python

        import mlib

        plugs = mlib.ls("pCube1.tx", "pCube1.ty")
        for plug in plugs:
            print(plug._full_name())
    """
    def __iter__(self) -> Iterator[Plug]: ...
    @overload
    def __getitem__(self, index: int) -> Plug: ...
    @overload
    def __getitem__(self, index: slice) -> Plugs: ...
    __hash__: None
    def __init__(self, plugs: Plug | om2.MPlug | str | Iterable[Plug | om2.MPlug | str] = ...) -> None:
        """渡されたものをPlugにして、重複を除いて持つ。

        Args:
            plugs (Plug | om2.MPlug | str | Iterable[Plug | om2.MPlug | str]): アトリビュート、
                または ``"node.attribute"`` の形の名前。その並び(入れ子でもよい)。名前1つでも受け付ける。

        Raises:
            TypeError: アトリビュートを指さない値や、対応していない型を含む場合。
            ValueError: 空文字列や空のMPlugを含む場合。
            AttributeError: 名前に当たるアトリビュートが見つからない場合(``MissingAttributeError``)。
            RuntimeError: 無効な(削除された)アトリビュートを含む場合。
        """
        ...
    def __getattr__(self, name: str) -> Callable[..., list]:
        """1つのPlugのメソッドを、すべての要素へ呼ぶ関数として取得する。

        このクラスに無い公開メソッドの名前(``get``・``set`` など)を取得すると、関数が返る。
        その関数は、各要素の同じ名前のメソッドを同じ引数で順に呼び、戻り値を同じ順のリストで返す
        (:class:`~mlib.nodes.node.Nodes` と同じ)。

        - 呼ぶ前に、すべての要素がそのメソッドを持つことを確かめる。
        - 通常は1回のUndoにまとめる。``fast=True`` は、そのまま各メソッドへ渡す。
        - 要素が無いときは :class:`Plug` のメソッドの名前を受け付け、空のリストを返す。

        Args:
            name (str): 1つのPlugの公開メソッドの名前。

        Returns:
            Callable[..., list]: 各要素のメソッドを呼び、戻り値を要素の順のリストで返す関数。

        Raises:
            AttributeError: ``_`` で始まる名前の場合、またはどの要素(空なら :class:`Plug`)も持たないメソッドの名前の場合。
        """
        ...
    def __len__(self) -> int:
        """持っている要素の数を返す。

        Returns:
            int: 要素の数。
        """
        ...
    def __repr__(self) -> str:
        """コレクションの名前と、持っているPlugを表示する。

        Returns:
            str: ``Plugs([Plug('pCube1.translateX'), ...])`` のような文字列。
        """
        ...
    def __eq__(self, other: Plugs | list | tuple) -> bool:
        """同じPlugを同じ順に持っているか比べる。

        Args:
            other (Plugs | list | tuple): 比べる相手。

        Returns:
            bool: 要素の数が同じで、各位置のPlugが ``==`` で等しければTrue。対応していない型にはNotImplemented。
        """
        ...
    def __add__(self, other: Plugs | list | tuple) -> Plugs:
        """ほかのPlugs・list・tupleを後ろへつないだ、新しいコレクションを返す。

        作るときと同じ決まりでPlugにし、重複は先に出てきた方を残す。

        Args:
            other (Plugs | list | tuple): 後ろへつなぐPlug・名前の並び。

        Returns:
            Plugs: 左辺と同じ型の新しいコレクション。自身と相手は変えない。

        Raises:
            TypeError: 相手が対応していない型の場合、またはアトリビュートでないものを含む場合。
            AttributeError: 見つからないアトリビュートを含む場合(``MissingAttributeError``)。
            RuntimeError: 無効なアトリビュートを含む場合。
        """
        ...
    def __radd__(self, other: list | tuple) -> Plugs:
        """左辺がlist・tupleのときの ``+`` で、新しいコレクションを返す。

        Args:
            other (list | tuple): 前へつなぐPlug・名前の並び。

        Returns:
            Plugs: 右辺(自身)と同じ型の新しいコレクション。

        Raises:
            TypeError: 相手が対応していない型の場合、またはアトリビュートでないものを含む場合。
            AttributeError: 見つからないアトリビュートを含む場合(``MissingAttributeError``)。
            RuntimeError: 無効なアトリビュートを含む場合。
        """
        ...
    def sort(self, key: Callable[[Plug], object] | None = ..., reverse: bool = ...) -> None:
        """持っている並びを、その場で並べ替える。

        並べ替えた自身を返す。``key`` を省略したら、アトリビュートの完全な名前(``Plug.getName(full=True)``)の順にする。
        並べ替わるのはこのコレクションだけで、スライスや ``+`` で作った別のコレクションの順番は変わらない
        (各要素のPlugは共有している)。

        Args:
            key (Callable[[Plug], object] | None): 各Plugから、比べるための値を返す関数。Noneなら完全な名前で比べる。
            reverse (bool): Trueなら大きい順。既定はFalse。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: keyが呼び出せない場合、またはreverseがboolでない場合。
        """
        ...
    def getNames(self, *, full: bool = ...) -> list[str]:
        """持っている順に、アトリビュートの名前を返す。

        既定は :meth:`Plug.getName` を並べたもの。``full=True`` なら完全なアトリビュート名
        (``Plug.getName(full=True)`` を並べたもの。``maya.cmds`` へ渡すときに使う)。

        Args:
            full (bool): Trueなら、完全なアトリビュート名を返す。既定はFalse。

        Returns:
            list[str]: 各Plugの名前。無効なPlugは空文字列。

        Raises:
            TypeError: fullがboolでない場合。
        """
        ...
    @classmethod
    def _from_plugs(cls, plugs: Iterable[Plug]) -> Plugs:
        """すでにPlugになっている並びから、重複を除いて作る。Plugにし直す処理は省く(lsの結果で使う)。

        Args:
            plugs (Iterable[Plug]): 解決済みで有効なPlug。

        Returns:
            Plugs: 新しいコレクション。
        """
        ...
    def _resolve_item(self, value: Plug | om2.MPlug | str) -> Plug:
        """追加する値をPlugへ解決し、有効かを確かめる。

        Args:
            value (Plug | om2.MPlug | str): アトリビュート、または ``"node.attribute"`` の形の名前。

        Returns:
            Plug: 解決したアトリビュート。

        Raises:
            TypeError: アトリビュートを指さない値や、対応していない型の場合。
            AttributeError: 名前に当たるアトリビュートが見つからない場合(``MissingAttributeError``)。
            RuntimeError: 無効なアトリビュートの場合。
        """
        ...
    def getNode(self) -> list[Node]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getNode` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isValid(self, *, elements: bool = ...) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isValid` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isInstancedAttribute(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isInstancedAttribute` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isExactlyEqual(self, other: Plug) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isExactlyEqual` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNumConnectedChildren(self) -> list[int]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getNumConnectedChildren` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSetAttrCmds(self, *, valueSelector: str = ..., useLongNames: bool = ...) -> list[list[str]]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getSetAttrCmds` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getAttributeClass(self) -> list[int]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getAttributeClass` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isNewAttribute(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isNewAttribute` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mplug(self) -> list[om2.MPlug]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.mplug` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getName(self, *, full: bool = ...) -> list[str]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getAttributeName(self, kind: str = ...) -> list[str]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getAttributeName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setNiceName(self, name: str) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setNiceName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getCategories(self) -> list[list[str]]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getCategories` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getType(self) -> list[str | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isMulti(self, *, element: bool = ...) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isMulti` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isCompound(self, *, child: bool = ...) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isCompound` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getParent(self, *, all: bool = ..., includeMulti: bool = ...) -> list[Plug | Plugs | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getParent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getMulti(self) -> list[MultiPlug | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getMulti` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getIndex(self) -> list[int]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getIndex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSiblings(self) -> list[Plugs]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getSiblings` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDescendants(self, *, levels: int | None = ..., leavesOnly: bool = ...) -> list[Plugs]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getDescendants` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isDirty(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isDirty` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setDirty(self) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setDirty` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def evaluate(self) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.evaluate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFlags(self) -> list[dict[str, bool]]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getFlags` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setFlags(self, *, locked: bool | None = ..., keyable: bool | None = ..., channelBox: bool | None = ..., children: bool = ..., leaf: bool = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setFlags` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isConnected(self, other: Plug | om2.MPlug | str | None = ..., *, source: bool = ..., destination: bool = ...) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isConnected` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isFromReferencedFile(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isFromReferencedFile` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isProxy(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isProxy` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getProxyMaster(self) -> list[Plug | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getProxyMaster` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isSettable(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isSettable` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getRange(self, *, soft: bool = ..., unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ...) -> list[tuple[float | tuple[float, ...] | None, float | tuple[float, ...] | None]]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getRange` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setRange(self, minimum: float | om2.MAngle | om2.MDistance | om2.MTime | None = ..., maximum: float | om2.MAngle | om2.MDistance | om2.MTime | None = ..., *, soft: bool = ..., unit: str | None = ..., timeUnit: str | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setRange` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDefault(self, *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ...) -> list[Any]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getDefault` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setDefault(self, value: bool | int | float | om2.MAngle | om2.MDistance, *, fast: bool = ..., unit: str | None = ..., uiUnits: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setDefault` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isDefaultValue(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isDefaultValue` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getAlias(self) -> list[str | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getAlias` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setAlias(self, name: str | None = ..., *, skipExisting: bool = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setAlias` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setKey(self, *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., **kwargs) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def removeKey(self, *, time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.removeKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def moveKey(self, *, time: float | Sequence[float] | None = ..., timeOffset: float = ..., valueOffset: float = ..., unit: str | None = ..., timeUnit: str | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.moveKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setKeyTangent(self, *, inTangentType: str | None = ..., outTangentType: str | None = ..., time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setKeyTangent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getAnimLayers(self, selected: bool = ..., exact: bool = ...) -> list[Nodes]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getAnimLayers` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getEnumNames(self, *, value: int | None = ..., name: str | None = ..., current: bool = ...) -> list[list[tuple[str, int]] | str | int]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getEnumNames` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setEnumNames(self, names: Iterable[str]) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setEnumNames` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isLocked(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setLocked(self, state: bool = ..., *, leaf: bool = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isMuted(self) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.isMuted` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setMuted(self, state: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setMuted` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def delete(self, *, force: bool = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.delete` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def get(self, *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., time: float | om2.MTime | None = ...) -> list[Any]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.get` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def set(self, value: object, *, safe: bool = ..., unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., fast: bool = ..., check: bool = ...) -> list[int | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.set` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setIfChanged(self, value: bool | int | float | str, *, unlock: bool = ..., fast: bool = ..., check: bool = ...) -> list[bool]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.setIfChanged` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def reset(self, *, fast: bool = ..., check: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.reset` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getConnections(self, *, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: bool = ..., asNode: bool = ..., checkChildren: bool = ..., checkElements: bool = ..., index: int | None = ..., input: bool = ..., outputs: bool = ...) -> list[Plugs | Nodes | list | Plug | Node | tuple | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getConnections` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getAnimCurve(self, layer: Node | str | None = ..., *, indirect: bool = ..., suitableType: bool = ..., timeInput: bool | None = ...) -> list[Node | str | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getAnimCurve` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getLayeredPlug(self, layer: Node | str | None = ...) -> list[Plug | None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.getLayeredPlug` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def connect(self, source: Plug | om2.MPlug | str, *, force: bool = ..., f: bool = ..., lock: bool = ..., l: bool = ..., nextAvailable: bool = ..., na: bool = ..., unlock: bool = ..., skipExisting: bool = ..., fast: bool = ...) -> list[Plug]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.connect` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def disconnect(self, source: Plug | om2.MPlug | str | None = ..., *, force: bool = ..., f: bool = ..., nextAvailable: bool = ..., na: bool = ..., fast: bool = ...) -> list[Plug | list[Plug]]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.disconnect` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def disconnectAll(self, *, source: bool = ..., destination: bool = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.disconnectAll` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def connectTo(self, destination: Plug | om2.MPlug | str, *, skipExisting: bool = ..., fast: bool = ..., **kwargs) -> list[Plug]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.connectTo` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def insertInput(self, node: str | Node, inputAttribute: str, outputAttribute: str) -> list[None]:
        """各要素の :meth:`~mlib.plugs.plug.Plug.insertInput` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
