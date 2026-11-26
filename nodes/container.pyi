# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya containerによる計算ノードの所有管理。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _require_bool, undoTransaction
from ..plugs.plug import Plug, Plugs
from .node import Node, Nodes, _resolve_node
from typing import Iterable
from mlib.nodes.dagContainer import DagContainer



class Container(Node):
    """containerノードを扱うクラス。直接のメンバーと、公開名と内部のアトリビュートの対応を管理する。

    つながっているノードを自動で集めるクラスではない。Mayaのcontainerのメンバーと、
    公開名のバインド(内部のアトリビュートとの対応付け)を扱う。
    メンバーや公開したPlugを調べるにはOpenMayaを、メンバーや公開名を変えるにはcmdsを使う。

    変更はundoTransactionでまとめる(Undoが有効であることが前提)。失敗したときはUndoで元に戻そうとするが、
    その戻す処理まで失敗しないとは限らない。fast引数は無い。
    createNodeでノードを作るときも、通常のUndoできる変更を使う。

    :class:`~mlib.nodes.dagContainer.DagContainer` は同じ名前のメソッドを持ち、このクラスのメソッドを呼ぶ
    (クラスの親は1つにする決まりのため、DagContainerはTransformだけを親にする)。
    """
    def getExternalConnections(self) -> Plugs:
        """コンテナ内部から外部へつながる、外部側のPlugを取得する。

        Mayaのcontainer(connectionList=True)の順を保持する。接続を変更しない。

        Returns:
            Plugs: 外部側のアトリビュート。接続がなければ空。

        Raises:
            RuntimeError: コンテナが無効、またはMayaが照会を拒否した場合。
        """
        ...
    def publishConnections(self) -> None:
        """内部ノードから外部への接続を、Mayaの方法でコンテナへ公開する。

        公開名とバインドを追加する。既存名との衝突や公開する親アトリビュートの選択はMayaに従う。
        通常Undoに対応する。fast引数は持たない(1回のcontainerコマンドを使うため)。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: コンテナが無効な場合、またはコンテナのロック等でMayaが公開を拒否した場合。
        """
        ...
    def getMembers(self) -> Nodes:
        """containerに直接入っているメンバーを取得する。

        MFnContainerNode.getMembers()が返すものをそのまま使う。
        つながっているノードや、入れ子のcontainerの中身はたどらない。DAG階層の子孫を集めるものでもない。

        Returns:
            Nodes: メンバーの新しいオブジェクト。ノードは複製しない。
                並びはMayaが返す順のままで、並べ替えない。
        """
        ...
    def addMembers(self, *members: str | Node | Iterable[Node | str]) -> None:
        """ノードをメンバーに加える。

        別のcontainerに入っているノードを、無理に移すことはしない。すでにこのcontainerのメンバーなら、何もしない。
        変える前に、すべてのノードがあり、ほかのcontainerに入っていないかを確かめる。

        Args:
            *members (str | Node | Iterable[Node | str]): メンバーに加えるノード。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが見つからない場合、またはほかのcontainerに入っているノードを含む場合。
        """
        ...
    def removeMembers(self, *members: Node | str | Iterable[Node], all: bool = ..., force: bool = ...) -> None:
        """ノードをメンバーから外す。``all=True`` なら、直接入っているメンバーをすべて外す。

        変える前に、指定したノードがすべてメンバーかを確かめる。メンバーでないノードがあれば、
        force=Trueでもエラーにする。ノードそのものは削除しない。
        containerが入れ子になっている場合、外したノードはふつう親のcontainerのメンバーになる。

        Args:
            *members (Node | str | Iterable[Node]): 外すメンバー。all=Trueとは同時に指定できない。
            all (bool): Trueなら、直接入っているメンバーをすべて外す。既定はFalse。
            force (bool): Trueなら、すべてのcontainerから外す(``container -removeNode -force``)。ロックを外すという意味ではない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: all・forceがboolでない場合、またはmembersとall=Trueを同時に指定した場合。
            ValueError: メンバーでないノードが含まれる場合。
        """
        ...
    def createNode(self, type: str, name: str | None = ...) -> Node:
        """ノードを作り、このcontainerのメンバーにする。

        Args:
            type (str): Mayaのノード型。
            name (str | None): 付けたい名前。省略すると、container名の後ろに ``_`` と型名を付けた名前になる。

        Returns:
            Node: 作ったノード。実際のノード型に合ったクラスのオブジェクトになる。

        Raises:
            ValueError: typeが空文字列、または文字列でない場合。
            RuntimeError: Mayaが知らないtypeの場合。unknownノードは残さない。
        """
        ...
    def removeContainer(self) -> None:
        """containerを解除する。

        直接のメンバーを先に外してから、container自身を取り除く。
        先に外すのは、MayaのremoveContainerがメンバーまで削除してしまうのを防ぐため。

        - container自身のアトリビュートの接続は失われる。出力をつなぎ替えたり、設定を移したりはしない。
        - 通常のdeleteとは、削除される範囲が違う。
        - 成功すると、このオブジェクトは無効になる。

        Returns:
            None: メンバーノードを返す操作ではない。
        """
        ...
    def publishName(self, name: str) -> str:
        """公開名を作る。

        作った公開名は、まだどのアトリビュートにもバインドされていない。

        Args:
            name (str): 作りたい公開名。

        Returns:
            str: 作成した公開名。

        Raises:
            ValueError: 同じ公開名がすでにある場合。
            RuntimeError: ノードが無効な場合、またはMayaが公開名の作成を拒否した場合。
        """
        ...
    def getPublishedAttrs(self) -> dict[str, Plug | None]:
        """公開名と、バインドされている内部のアトリビュートを取得する。

        バインドされていない公開名の値はNoneになる。
        公開ノードのアンカーは扱わない。Plugの値を取得したり、転送用のアトリビュートを作ったりもしない。

        Returns:
            dict[str, Plug | None]: 公開名からPlugへの新しい辞書。Plugは内部のアトリビュートを指す。
                辞書を変えても、公開名やバインドは変わらない。
        """
        ...
    def bindAttr(self, name: str, plug: Plug | str) -> Plug:
        """公開名へ内部のアトリビュートをバインドする。

        Args:
            name (str): すでにある、バインドされていない公開名。
            plug (Plug | str): このcontainerの直接のメンバーが持つアトリビュート。

        Returns:
            Plug: 対応付けた内部アトリビュート。

        Raises:
            ValueError: nameがバインドされていない公開名でない場合、またはplugのノードが直接のメンバーでない場合。
        """
        ...
    def publishAndBind(self, name: str, plug: Plug | str) -> Plug:
        """公開名を作り、内部のアトリビュートへバインドする。

        Args:
            name (str): 新しい公開名。
            plug (Plug | str): このcontainerの直接のメンバーが持つアトリビュート。

        Returns:
            Plug: 対応付けた内部アトリビュート。

        Raises:
            ValueError: nameがすでにある公開名の場合、またはplugのノードが直接のメンバーでない場合。
        """
        ...
    def unbindAttr(self, name: str) -> None:
        """公開名のバインドを外す。

        公開名そのものは残す。

        Args:
            name (str): バインドされている公開名。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: nameが公開名でない場合、またはバインドされていない場合。このときは何も変えない。
        """
        ...
    def unpublishName(self, name: str) -> None:
        """バインドされていない公開名を削除する。

        Args:
            name (str): バインドされていない公開名。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: nameが公開名でない場合、またはバインドされている場合。このときは何も変えない。
        """
        ...
    @staticmethod
    def _resolve_new_members(members: tuple, owner: Container | DagContainer | None = ...) -> list[str]:
        """containerへ加えるノードを確かめ、完全な名前の並びにする。

        containerを作る前に呼べるよう、staticmethodにしている(作ってから失敗してUndoで戻すと、
        今の名前空間がルート以外のときにMayaが壊れることがあるため、作る前に確かめる)。

        Args:
            members (tuple): ``addMembers`` が受けた値の並び。
            owner (Container | DagContainer | None): 加える先のcontainer。そのメンバーはほかのcontainerに入っているとみなさない。

        Returns:
            list[str]: 加えるノードの完全な名前。

        Raises:
            RuntimeError: ノードが見つからない場合、またはほかのcontainerに入っているノードを含む場合。
        """
        ...
