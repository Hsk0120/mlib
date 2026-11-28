# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""DAG階層とメンバーの所有を扱うMaya dagContainer。"""

from .container import Container
from .transform import Transform
from typing import Iterable
from mlib.nodes.node import Node
from mlib.nodes.node import Nodes
from mlib.plugs.plug import Plug
from mlib.plugs.plug import Plugs



class DagContainer(Transform):
    """Transformとしての操作と、Containerと同じメンバー・公開の操作を持つコンテナ。

    MayaのdagContainerはtransformの派生なので、Transformだけを親にする(クラスの親は1つにする決まり)。
    メンバー・公開の操作は :class:`~mlib.nodes.container.Container` と同じ名前のメソッドを持ち、
    中身はContainerのメソッドを呼ぶ。``isinstance(x, Container)`` はFalseになるので、
    コンテナかどうかは ``isType("containerBase")`` で調べる。
    DAGの子のメンバー管理も、Maya標準の仕組みに従う。

    - removeMembersは、メンバーから外すと同時に、子を階層からも外す。
    - removeContainerは、メンバーを残したままコンテナを解除する。
      解除してもローカルの値はそのまま残るので、ワールドでの姿勢は変わることがある。
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
            TypeError: 対応していない型(数値など)を渡した場合、または名前とNodeなどのオブジェクトを混ぜて渡した場合。
            RuntimeError: ノードが見つからない場合、またはほかのcontainerに入っているノードを含む場合。
        """
        ...
    def removeMembers(self, *members: Node | str | Iterable[Node], all: bool = ..., force: bool = ...) -> None:
        """ノードをメンバーから外す。``all=True`` なら、直接入っているメンバーをすべて外す。

        変える前に、指定したノードがすべてメンバーかを確かめる。メンバーでないノードがあれば、
        force=Trueでもエラーにする。ノードそのものは削除しない。
        containerが入れ子になっている場合、外したノードはふつう親のcontainerのメンバーになる。

        Args:
            all (bool): Trueなら、直接入っているメンバーをすべて外す。既定はFalse。
            force (bool): Trueなら、すべてのcontainerから外す(``container -removeNode -force``)。ロックを外すという意味ではない。既定はFalse。
            *members (Node | str | Iterable[Node]): 外すメンバー。all=Trueとは同時に指定できない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: all・forceがboolでない場合、membersとall=Trueを同時に指定した場合、対応していない型を渡した場合、
                または名前とNodeなどのオブジェクトを混ぜて渡した場合。
            ValueError: メンバーでないノードが含まれる場合。
            RuntimeError: ノードが見つからない(名前に一致しない・削除された)場合。
        """
        ...
    def createNode(self, type: str, *, name: str | None = ...) -> Node:
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
            TypeError: plugの型が不正な場合、または文字列がアトリビュートを指していない場合。
            ValueError: nameがバインドされていない公開名でない場合、またはplugのノードが直接のメンバーでない場合。
            MissingAttributeError: plugの文字列のアトリビュート(またはノード)が無い場合(AttributeErrorの派生)。
            RuntimeError: コンテナが無効な場合、またはplugの文字列が複数に一致する場合。
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
            TypeError: plugの型が不正な場合、または文字列がアトリビュートを指していない場合。
            ValueError: nameがすでにある公開名の場合、またはplugのノードが直接のメンバーでない場合。
            MissingAttributeError: plugの文字列のアトリビュート(またはノード)が無い場合(AttributeErrorの派生)。
            RuntimeError: コンテナが無効な場合、またはplugの文字列が複数に一致する場合。
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
