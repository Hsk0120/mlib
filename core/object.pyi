# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""シーンの中の1つの対象を表す共通の基底クラスと、選択リストで対象の種類を見分ける補助。"""

import maya.api.OpenMaya as om2
from typing import Any, Iterator
from mlib.components.component import Component
from mlib.nodes.node import Node
from mlib.plugs.plug import Plug

_MEMBER_HINTS: dict

def _exists(name: str) -> bool:
    """名前がシーンの対象を指しているかを調べる。

    選択リストへ追加できるかどうかで判定する。
    ほかと区別できる完全名なら、``cmds.objExists`` と同じ結果になる。
    範囲外のコンポーネント番号や、マルチアトリビュートのまだ作られていない要素も True になる。

    Args:
        name (str): 調べる完全名。

    Returns:
        bool: 選択リストへ追加できたら True。
    """
    ...

def _selection_plug(selection: om2.MSelectionList, index: int) -> om2.MPlug | None:
    """選択リストの要素がアトリビュートなら、そのMPlugを取得する。

    ``MSelectionList.getPlug`` は、要素がノードやコンポーネントのとき RuntimeError か
    TypeError になる(どちらになるかはMayaの版で違う)。そのため、どちらもNoneとして扱う。

    Args:
        selection (om2.MSelectionList): 選択リスト。
        index (int): 要素の番号。

    Returns:
        om2.MPlug | None: アトリビュートの要素ならMPlug。それ以外、またはnullのMPlugならNone。
    """
    ...

def _selection_component(selection: om2.MSelectionList, index: int) -> tuple[om2.MDagPath, om2.MObject] | None:
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
    ...

def _missing_member_message(obj: object, name: str, what: str = ...) -> str:
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
    ...


class _ObjectType(type):
    """Objectを呼んだときだけ入力の種類を見分けるメタクラス。派生クラスは通常どおり作る。"""


class Object(metaclass=_ObjectType):
    """Node・Plug・単数のComponentに共通する基底クラス。

    対象を探すときは :func:`~mlib.ls` を使う。

    Objectに対象を1つ渡すと、その種類に合ったオブジェクトを返す。
    アトリビュートやコンポーネントを渡しても、持ち主のノードには置き換えない。
    すでにあるObjectを渡すと、削除されていても同じインスタンスを返す。
    複数の対象は受け付けない。ノードの作成・複製や、選択の変更はしない。
    """
    def asString(self) -> str:
        """今の対象の名前を文字列で返す。

        Node・Plug・Componentそれぞれの ``str()`` と同じ名前を返す。
        名前は保存せず、毎回取得し直すので、名前の変更や親の付け替えにも追いつく。
        対象が無効なときの扱いも、それぞれの型の ``str()`` と同じ。

        Returns:
            str: Mayaのコマンドへ渡せる対象の名前。

        Raises:
            RuntimeError: 対象が無効で、それぞれの型の文字列への変換が止める場合。
        """
        ...
    @staticmethod
    def _resolve_input(value: str | Object | om2.MObject | om2.MDagPath | om2.MPlug | tuple) -> Object:
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
        ...
    @staticmethod
    def _classes() -> tuple[type, type, type, type]:
        """種類の判定に使う mlib のクラスを取得する。

        import が循環しないように、呼んだときに読み込む。

        Returns:
            tuple[type, type, type, type]: Node、Plug、Component、Components。
        """
        ...
    @staticmethod
    def _unsupported(value: object) -> TypeError:
        """対応しない入力型の TypeError を作る。

        Args:
            value (object): 入力値。

        Returns:
            TypeError: 送出する例外。
        """
        ...
    @staticmethod
    def _name(value: object, node_class: type, plug_class: type, component_class: type) -> str:
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
        ...
    @staticmethod
    def _input_name(value: str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug) -> str:
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
        ...
    @staticmethod
    def _flatten_inputs(values: object) -> list:
        """入れ子になった対象の並びを、平らな1つのリストにする。

        どの型どうしを混ぜてよいかは、呼び出し側が確かめる。

        Args:
            values (object): 1つの対象、または入れ子にもなる対象の並び。

        Returns:
            list: 元の順番のままの対象。Componentsは、番号を範囲にまとめるため展開しない。

        Raises:
            TypeError: 対応していない型の場合。
        """
        ...
    @staticmethod
    def _input_names(values: object, allow_plugs: bool = ...) -> list[str]:
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
        ...
    def __getattr__(self, name: str) -> Any: ...
