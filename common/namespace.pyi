# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の名前空間を取得・作成・移動・削除する。"""

from contextlib import contextmanager
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _require_bool, undoChunk
from typing import Any, Iterator
from mlib._stubtypes import GeneratorContextManager
from mlib.nodes.node import Node
import types



class Namespace:
    """Mayaの名前空間(namespace)を表すオブジェクト。"""
    def __init__(self, name: str | Namespace = ...) -> None:
        """名前空間の名前を決まった形に揃えて、オブジェクトを作る。

        名前を持つだけで、シーンに名前空間を作ったり、存在するかを確かめたりはしない。

        Args:
            name (str | Namespace): 名前空間の名前、または既存のオブジェクト。既定の : はルート。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 文字列でもNamespaceでもない場合。
            ValueError: 空文字列の場合。
        """
        ...
    def __repr__(self) -> str:
        """デバッグ用の表示を返す。

        Returns:
            str: Namespace と、持っている名前を含む文字列。
        """
        ...
    def __str__(self) -> str:
        """名前空間の絶対名を返す。

        Returns:
            str: 揃えた形の、持っている名前。存在するかは確かめない。
        """
        ...
    def __eq__(self, other: object) -> bool | types.NotImplementedType:
        """名前空間の名前で、同じものか判定する。

        Args:
            other (object): 比べる相手。

        Returns:
            bool | types.NotImplementedType: Namespace どうしなら、持っている名前を比べる。型が違えば NotImplemented。
        """
        ...
    def __hash__(self) -> int:
        """名前空間の名前からハッシュ値を返す。

        Returns:
            int: 今持っている名前のハッシュ。rename/move で変わるため、集合や辞書のキーに入れている間は
                名前を変えないこと。
        """
        ...
    @classmethod
    def getCurrent(cls) -> Namespace:
        """カレントの名前空間を取得する。

        Returns:
            Namespace: 今のカレントの名前空間。
        """
        ...
    @classmethod
    def create(cls, name: str | Namespace, parent: str | Namespace = ...) -> Namespace:
        """指定した名前空間を作る。すでにあれば作らず、そのオブジェクトを返す。

        カレントの名前空間は変えない。/ は : と同じ区切りとして扱う。
        cmds.namespaceを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            name (str | Namespace): 作る名前空間。相対名ならparentの下に作る。
                絶対名とNamespaceのオブジェクトでは、parentを無視する。何階層もある名前も指定できる。
            parent (str | Namespace): 作る場所の親。相対名の文字列は、カレントから数える。
                既定はルート(:)。存在しない親も、上から順に作る。

        Returns:
            Namespace: 作った(またはすでにあった)名前空間の完全名を持つオブジェクト。

        Raises:
            ValueError: nameまたはparentが正しくない場合。
            RuntimeError: Mayaが作成を拒否した場合。

        Note:
            使えない文字(``-``・空白・先頭の数字・``#`` など)は、Mayaの規則で置き換える。
            置き換えた名前がすでにあれば、末尾に番号を付ける。戻り値はMayaが実際に作った名前になる。
        """
        ...
    @property
    def name(self) -> str:
        """揃えた形の、名前空間の絶対名を返す。

        Returns:
            str: 先頭が : の、持っている名前。
        """
        ...
    def exists(self) -> bool:
        """名前空間がシーンに存在するか調べる。

        Returns:
            bool: 持っている名前の名前空間が、今のシーンにあれば True。
        """
        ...
    def getParent(self) -> Namespace | None:
        """親の名前空間を返す。ルートの親は ``None``。

        Returns:
            Namespace | None: 名前から求めた親。ルートでは None。親が存在するかは確かめない。
        """
        ...
    def getShortName(self) -> str:
        """末端の名前(``:a:b`` なら ``b``)を返す。

        Returns:
            str: 区切りの ``:`` を含まない最後の階層名。ルートでは ``":"``。
        """
        ...
    def split(self) -> list[str]:
        """階層ごとの名前のリスト(``:a:b`` なら ``["a", "b"]``)を返す。

        Returns:
            list[str]: 上の階層から順に並べた名前。ルートでは空リスト。
        """
        ...
    def getChildren(self, recurse: bool = ...) -> list[Namespace]:
        """子の名前空間を取得する。

        Args:
            recurse (bool): Trueなら、孫より下の子孫も含める(親が子より先に並ぶ)。既定は直下だけ。

        Returns:
            list[Namespace]: 子(recurse=Trueなら子孫)。自身が存在しない場合は空リスト。

        Raises:
            TypeError: recurse が bool でない場合。
        """
        ...
    def getNodes(self, recurse: bool = ...) -> list[Node]:
        """名前空間の中のノードを、mlibのオブジェクトとして返す。

        Args:
            recurse (bool): Trueなら、子の名前空間の中のノードも含める。

        Returns:
            list[Node]: 名前空間の中のノードのオブジェクト。自身が存在しない場合は空リスト。
        """
        ...
    def getNode(self, name: str) -> Node:
        """名前空間を付けた名前で、ノードを取得する。

        例えば ``Namespace(":char").getNode("root")`` は ``char:root`` を取得する。

        Args:
            name (str): 名前空間を除いたノード名。DAGパスでは階層ごとに名前空間が要るため、
                ``"grp|char:child"`` のように、2階層目からは名前空間を付けて渡す。

        Returns:
            Node: 実際のノード型に合ったオブジェクト。

        Raises:
            TypeError: name が文字列でない場合。
            ValueError: name が空文字列の場合。
            RuntimeError: ノードが存在しない場合、または1つに決まらない場合。
        """
        ...
    def setCurrent(self) -> Namespace:
        """カレントの名前空間を、この名前空間に切り替える。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Returns:
            Namespace: 自身。

        Raises:
            RuntimeError: 自身が存在しない場合。
        """
        ...
    def asCurrent(self) -> GeneratorContextManager[Namespace]:
        """カレントの名前空間を、一時的にこの名前空間に切り替える。

        抜けるときは、例外が起きても起きなくても、元に戻そうとする。
        元の名前空間が削除されていれば戻さない。
        戻すときに失敗するとその例外を送出し、ブロックの中で起きた例外と置き換わることがある。

        Yields:
            Namespace: 自身。

        Raises:
            RuntimeError: 自身が存在しない場合、またはMayaが切り替えや戻しを拒否した場合。
        """
        ...
    def rename(self, name: str | Namespace) -> Namespace:
        """この名前空間の名前を変える。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            name (str | Namespace): 新しい名前。最後の階層の名前だけを使い、今の親はそのままにする。

        Returns:
            Namespace: 持っている名前を新しくした自身。

        Raises:
            ValueError: ルートの名前を変えようとした場合、または名前が正しくない場合。
            RuntimeError: 移動先がすでにある場合、親が存在しない場合、または Maya の操作が失敗した場合。
        """
        ...
    def move(self, parent: str | Namespace = ...) -> Namespace:
        """この名前空間を、指定した親の名前空間の下へ移す。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            parent (str | Namespace): 移動先の、既存の親の名前空間。自身の最後の階層の名前はそのままにする。

        Returns:
            Namespace: 持っている名前を新しくした自身。

        Raises:
            ValueError: ルートを移動しようとした場合、または parent が正しくない場合。
            RuntimeError: 親が存在しない場合、移動先がすでにある場合、または Maya の操作が失敗した場合。
        """
        ...
    def remove(self, destination: str | Namespace = ..., *, deleteContents: bool = ...) -> Namespace | None:
        """中身を別の名前空間へ移してから、この名前空間を削除する。

        ``deleteContents=True`` なら、中身ごと削除する。

        - 移すときに名前が重なるノードは、Mayaの規則(cmdsのforceでの移動)で末尾に番号を付けて名前を変える。
        - ``deleteContents=True`` は ``cmds.namespace(removeNamespace=..., deleteNamespaceContent=True)`` と同じ。
          名前空間の中のノードと子の名前空間を削除する(読み込んだアセットの後片付けに使う)。
          名前空間の外にある子孫も、親のDAGノードと一緒に削除される。

        cmdsを使い、Undoが有効なら1つのチャンクに記録する。fast引数は無い。

        Args:
            destination (str | Namespace): 中身を移す先の、既存の名前空間。既定はルート。
                deleteContents=True では使わない。
            deleteContents (bool): True なら、中身を移さずに削除する。既定は False。

        Returns:
            Namespace | None: 中身を受け取った移動先。deleteContents=True では ``None``。
                自身が持っている名前は、削除する前のまま。

        Raises:
            TypeError: deleteContents が bool でない場合。
            ValueError: ルートを削除しようとした場合、または destination が正しくない場合。
            RuntimeError: 自身か移動先が存在しない場合、または Maya の操作が失敗した場合。
        """
        ...
    @classmethod
    def _create(cls, name: str | Namespace, parent: str | Namespace) -> Namespace:
        """createの中身の処理。Undoチャンクは呼び出す側が管理する。

        Args:
            name (str | Namespace): createのname。
            parent (str | Namespace): createのparent。

        Returns:
            Namespace: 作った名前空間の完全名を持つオブジェクト。
        """
        ...
    @staticmethod
    def _normalize(name: str) -> str:
        """名前空間の名前を、Mayaの絶対表記に揃える。

        Args:
            name (str): 揃える名前。

        Returns:
            str: / を : に置き換え、両端の : を除いてから、先頭に : を付けた名前。区切り文字だけなら :。
        """
        ...
    def _move_contents(self, target: Namespace) -> None:
        """名前空間の中身を別の名前空間へ移し、元の名前空間を削除する。

        移動先を作り、force=True で中身を移してから、元を削除する。
        自身が持っている名前は、ここでは新しくしない。

        Args:
            target (Namespace): 新しく作る移動先。親はすでに存在している必要がある。
                Undoチャンクは呼び出す側が管理する。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 移動先がすでにある場合、親が存在しない場合、または Maya の操作が失敗した場合。
        """
        ...
