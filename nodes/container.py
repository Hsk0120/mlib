"""Maya containerによる計算ノードの所有管理。"""

from typing import TYPE_CHECKING

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import undoTransaction
from ..plugs.plug import Plug
from .node import Node, Nodes, _resolve_node


# 実行時は Node を継承しない混ぜ込みとし、型検査では Node のメソッドを参照できるようにする。
class _ContainerMixin(Node if TYPE_CHECKING else object):
    """containerBase系のノードが共有する、メンバーと公開名の操作。

    :class:`Container` と :class:`~mlib.nodes.dagContainer.DagContainer` が使う。
    Nodeを継承しない、混ぜ込み用のクラスで、単独では使わない。
    Containerは ``_ContainerMixin`` とNodeを、DagContainerはTransformとContainerを基底に持つ。
    そのため、``isinstance(x, Container)`` はcontainerでもdagContainerでもTrueになる。

    つながっているノードを自動で集めるクラスではない。Mayaのcontainerのメンバーと、
    公開名のバインド(内部のアトリビュートとの対応付け)を扱う。
    メンバーや公開したPlugを調べるにはOpenMayaを、メンバーや公開名を変えるにはcmdsを使う。

    変更はundoTransactionでまとめる(Undoが有効であることが前提)。失敗したときはUndoで元に戻そうとするが、
    その戻す処理まで失敗しないとは限らない。fast引数は無い。
    createNodeでノードを作るときも、通常のUndoできる変更を使う。
    """

    def getMembers(self):
        """containerに直接入っているメンバーを取得する。

        MFnContainerNode.getMembers()が返すものをそのまま使う。
        つながっているノードや、入れ子のcontainerの中身はたどらない。DAG階層の子孫を集めるものでもない。

        Returns:
            list[Node]: メンバーの新しいオブジェクトのリスト。ノードは複製しない。
                並びはMayaが返す順のままで、並べ替えない。
        """
        # Node(obj)と同じ解決(DAGは最初のパス)・型選択を、生成の入口の再判定なしで行う。
        return [Node._wrap_resolved(*_resolve_node(obj)) for obj in om2.MFnContainerNode(self.mnode()).getMembers()]

    @undoTransaction("mlibContainerAddMembers")
    def addMembers(self, *members):
        """ノードをメンバーに加える。

        別のcontainerに入っているノードを、無理に移すことはしない。

        Args:
            *members (str | Node | Iterable[Node | str]): メンバーに加えるノード。

        Returns:
            Container: 自身。
        """
        nodes = Nodes._resolve_inputs(members)
        if nodes:
            cmds.container(self.getFullName(), edit=True, addNode=[Node._resolve_input(n).getFullName() for n in nodes])
        return self

    def removeMembers(self, *members, force=False):
        """ノードをメンバーから外す。

        変える前に、指定したノードがすべてメンバーかを確かめる。メンバーでないノードがあれば、
        force=Trueでもエラーにする。ノードそのものは削除しない。
        containerが入れ子になっている場合、外したノードはふつう親のcontainerのメンバーになる。

        Args:
            *members (Node | str | Iterable[Node]): 外すメンバー。
            force (bool): Trueなら、すべてのcontainerから外す。ロックを外すという意味ではない。

        Returns:
            Container: 自身。

        Raises:
            ValueError: メンバーでないノードが含まれる場合。
        """
        with undoTransaction("mlibContainerRemoveMembers"):
            nodes = [Node._resolve_input(node) for node in Nodes._resolve_inputs(members)]
            # Nodeの等価なら__hash__も等しいため、集合での所属判定はリストの`in`と同じ結果になる。
            current = set(self.getMembers())
            if any(node not in current for node in nodes):
                raise ValueError("nodesはすべてこのコンテナのメンバーで指定してください")
            if nodes:
                cmds.container(self.getFullName(), edit=True, removeNode=[node.getFullName() for node in nodes], force=force)
            return self

    @undoTransaction("mlibContainerCreateNode")
    def createNode(self, type, name=None):
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
        node = Node._create_node(type, {"name": name or self.getName() + "_" + type, "skipSelect": True})
        self.addMembers(node)
        return node

    @undoTransaction("mlibContainerRemoveContainer")
    def removeContainer(self):
        """containerを解除する。

        直接のメンバーを先に外してから、container自身を取り除く。
        先に外すのは、MayaのremoveContainerがメンバーまで削除してしまうのを防ぐため。

        - container自身のアトリビュートの接続は失われる。出力をつなぎ替えたり、設定を移したりはしない。
        - 通常のdeleteとは、削除される範囲が違う。
        - 成功すると、このオブジェクトは無効になる。

        Returns:
            None: メンバーノードを返す操作ではない。
        """
        # removeContainer単独では未接続のDGメンバーも削除される版がある。
        # 所属を先に外し、メンバーの生存を保証してから空の箱を除去する。
        members = self.getMembers()
        if members:
            cmds.container(self.getFullName(), edit=True, removeNode=[node.getFullName() for node in members])
        cmds.container(self.getFullName(), edit=True, removeContainer=True)

    @undoTransaction("mlibContainerPublishName")
    def publishName(self, name):
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
        if name in self.getPublishedAttrs():
            raise ValueError(f"パブリッシュ名はすでに存在します: {name}")
        result = cmds.container(self.getFullName(), edit=True, publishName=name)
        return result[0] if isinstance(result, (list, tuple)) else result

    def getPublishedAttrs(self):
        """公開名と、バインドされている内部のアトリビュートを取得する。

        バインドされていない公開名の値はNoneになる。
        公開ノードのアンカーは扱わない。Plugの値を取得したり、転送用のアトリビュートを作ったりもしない。

        Returns:
            dict[str, Plug | None]: 公開名からPlugへの新しい辞書。Plugは内部のアトリビュートを指す。
                辞書を変えても、公開名やバインドは変わらない。
        """
        fn = om2.MFnContainerNode(self.mnode())
        result = dict.fromkeys(fn.getPublishedNames(False))
        plugs, names = fn.getPublishedPlugs()
        for plug, name in zip(plugs, names):
            result[name] = Plug._resolve_input(plug)
        return result

    @undoTransaction("mlibContainerBindAttr")
    def bindAttr(self, name, plug):
        """公開名へ内部のアトリビュートをバインドする。

        Args:
            name (str): すでにある、バインドされていない公開名。
            plug (Plug | str): このcontainerの直接のメンバーが持つアトリビュート。

        Returns:
            Plug: 対応付けた内部アトリビュート。

        Raises:
            ValueError: nameがバインドされていない公開名でない場合、またはplugのノードが直接のメンバーでない場合。
        """
        published = self.getPublishedAttrs()
        if name not in published or published[name] is not None:
            raise ValueError(f"バインドされていないパブリッシュ名を指定してください: {name}")
        plug = Plug._resolve_input(plug)
        if plug.getNode() not in self.getMembers():
            raise ValueError("plugはメンバーのノードのものを指定してください")
        cmds.container(self.getFullName(), edit=True, bindAttr=(plug.getFullName(), name))
        return plug

    @undoTransaction("mlibContainerPublishAndBind")
    def publishAndBind(self, name, plug):
        """公開名を作り、内部のアトリビュートへバインドする。

        Args:
            name (str): 新しい公開名。
            plug (Plug | str): このcontainerの直接のメンバーが持つアトリビュート。

        Returns:
            Plug: 対応付けた内部アトリビュート。

        Raises:
            ValueError: nameがすでにある公開名の場合、またはplugのノードが直接のメンバーでない場合。
        """
        if name in self.getPublishedAttrs():
            raise ValueError(f"パブリッシュ名はすでに存在します: {name}")
        plug = Plug._resolve_input(plug)
        if plug.getNode() not in self.getMembers():
            raise ValueError("plugはメンバーのノードのものを指定してください")
        cmds.container(self.getFullName(), edit=True, publishAndBind=(plug.getFullName(), name))
        return plug

    @undoTransaction("mlibContainerUnbindAttr")
    def unbindAttr(self, name):
        """公開名のバインドを外す。

        公開名そのものは残す。

        Args:
            name (str): バインドされている公開名。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: nameが公開名でない場合、またはバインドされていない場合。このときは何も変えない。
        """
        plug = self.getPublishedAttrs().get(name)
        if plug is None:
            raise ValueError(f"バインドされたパブリッシュ名を指定してください: {name}")
        cmds.container(self.getFullName(), edit=True, unbindAttr=(plug.getFullName(), name))

    @undoTransaction("mlibContainerUnpublishName")
    def unpublishName(self, name):
        """バインドされていない公開名を削除する。

        Args:
            name (str): バインドされていない公開名。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: nameが公開名でない場合、またはバインドされている場合。このときは何も変えない。
        """
        published = self.getPublishedAttrs()
        if name not in published or published[name] is not None:
            raise ValueError(f"バインドされていないパブリッシュ名を指定してください: {name}")
        cmds.container(self.getFullName(), edit=True, unpublishName=name)


class Container(_ContainerMixin, Node):
    """containerノードを扱うクラス。直接のメンバーと、公開名と内部のアトリビュートの対応を管理する。

    メンバーと公開名の操作(create・getMembers・addMembers・removeMembers・createNode・removeContainer・
    publishName・getPublishedAttrs・bindAttr・publishAndBind・unbindAttr・unpublishName)は、
    非公開の ``_ContainerMixin`` に書いてあり、:class:`~mlib.nodes.dagContainer.DagContainer` と共有する。
    """
