"""Maya の objectSet(セット)を扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _require_bool, undoChunk
from .node import Node, Nodes


class ObjectSet(Node):
    """objectSet(セット)を扱うクラス。

    ノード・アトリビュート・コンポーネントが、セットに入っているかどうかを扱う。
    セットへの登録は、DAGの親子付けやContainerへの所属とは別の関係になる。
    取得にはMFnSet、編集にはcmds.setsを使う。
    """

    def getMembers(self, *, flatten=False):
        """セットのメンバーを取得する。

        flatten=Trueでは入れ子セットを再帰的に展開する。コンポーネント範囲の単一要素への分解とは異なる。
        既定では直接のメンバーだけを返す。所属関係と選択は変更しない。

        - ノード: Nodeのオブジェクトにする。
        - アトリビュート: Plugのオブジェクトにする。
        - コンポーネント: ``vtx[0:3]`` のようにまとめられた範囲ごとに、Verticesなどの複数形のオブジェクトにする。

        順番はMaya APIが列挙する順のまま。独自に並べ替えない。

        Args:
            flatten (bool): Trueなら入れ子セットの内容を取得する。既定False。

        Returns:
            list[Node | Plug | Components]: 新しいリスト。空のセットなら空リスト。

        Raises:
            TypeError: flattenがboolでない場合。
            RuntimeError: ノードが無効な場合。
        """
        _require_bool(flatten, "flatten")
        return self._member_names(om2.MFnSet(self.mnode()).getMembers(flatten))

    def getMemberDagNodes(self, *, shadingOnly=False):
        """セットに属するDAGパスをノード参照として取得する。

        コンポーネントは所属先のDAGパスになる。getMembersとは異なり、DGノードやPlugは返さない。
        Maya API2にgetMemberPathsがない版では未対応。

        Args:
            shadingOnly (bool): Trueならマテリアル割当てに影響するDAGパスだけを返す。既定False。

        Returns:
            Nodes[DagNode]: Mayaの順に並ぶパス別のノード参照。

        Raises:
            TypeError: shadingOnlyがbool以外の場合。
            RuntimeError: セットが無効な場合。
            NotImplementedError: 使用中のMayaに対応するAPI2メソッドがない場合。
        """
        _require_bool(shadingOnly, "shadingOnly")
        self._require_valid("セットのDAGパスの取得")
        if not hasattr(om2.MFnSet, "getMemberPaths"):
            raise NotImplementedError("このMayaのAPI2はセットのDAGパス照会に対応していません")
        return Nodes._wrap([Node._wrap_dag_path(path) for path in om2.MFnSet(self.mnode()).getMemberPaths(shadingOnly)])

    def getRestriction(self):
        """セットに登録できるメンバーの種類の制限を取得する。

        Returns:
            int: om2.MFnSetの制限定数。制限なしはkNone。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("所属制限の取得")
        return om2.MFnSet(self.mnode()).restriction()

    def addExclusiveMembers(self, *members):
        """同じpartition内の排他所属を移して、このセットへメンバーを追加する。

        Mayaのsets(forceElement=...)を使う。同じpartitionの別セットから対象が外れる場合がある。
        partitionの作成や、partitionが異なるセットからの除外は行わない。
        fast引数は持たない(排他所属の更新をMayaコマンドに委ねるため)。

        Args:
            members (Node | str): 追加するノードやコンポーネント。省略時は何もしない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 入力の型や組合せが不正な場合。
            ValueError: 対象を解決できない場合。
            RuntimeError: セットが無効、またはMayaが所属変更を拒否した場合。
        """
        self._require_valid("排他所属の変更")
        if members:
            names = Object._input_names(members)
            cmds.sets(names, forceElement=self.getName())

    def addMembers(self, *members):
        """ノードやコンポーネントなどを、このセットへ追加する。

        入力はほかのメソッドと同じ方法で解決し、cmds.setsへ渡す。何も渡さなければ、何も変えずに自身を返す。
        ノードを複製したり、親子付けしたりはしない。
        fast引数は持たない(MFnSetでの更新はcmds.setsより遅いため)。

        Args:
            members (Node | str): 追加するもの。ノードやコンポーネントの表記などを渡す。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対応していない型を渡した場合、または名前とNodeなどのオブジェクトを混ぜて渡した場合。
            ValueError: 名前に一致するものが無い場合。
            RuntimeError: Mayaが追加を拒否した場合。
        """
        with undoChunk("mlibObjectSetAddMembers"):
            if members:
                cmds.sets(Object._input_names(members), add=self.getName())

    def removeMembers(self, *members):
        """指定したメンバーを、このセットから外す。

        外すのはセットへの所属だけで、ノードそのものは削除しない。何も渡さなければ何も変えない。
        入力の解決のしかたは :meth:`addMembers` と同じ。

        Args:
            *members (Node | str): 外すもの。ノードやコンポーネントの表記などを渡す。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: Mayaが外すのを拒否した場合。
        """
        with undoChunk("mlibObjectSetRemoveMembers"):
            if members:
                cmds.sets(Object._input_names(members), remove=self.getName())

    def isMember(self, member):
        """渡したものが、すべてこのセットに直接入っているか調べる。

        入力を選択リストへ解決し、その要素を1つずつhasItem()で調べる。各要素は次の順に試して取り出す。

        1. アトリビュート(MPlug)
        2. DAGノードやコンポーネント(DAGパスとコンポーネント)
        3. DGノード(MObject)

        DGノード・DGノードのアトリビュート・DAGノードのアトリビュートも、
        ``cmds.sets(member, isMember=set)`` と同じ結果になる。
        入れ子になったセットの中身は展開しない。名前の文字列だけで同じものかを判定することもしない。

        Args:
            member (Node | str): 調べる対象。コンポーネントの範囲の表記も指定できる。

        Returns:
            bool: 解決したすべての要素が入っていればTrue。1つでも入っていなければFalse。
        """
        query = om2.MSelectionList()
        query.add(Object._input_name(member))
        members = om2.MFnSet(self.mnode()).getMembers(False)
        for index in range(query.length()):
            # getComponent は DG ノードやアトリビュートの要素で RuntimeError ではなく TypeError を出し、
            # getPlug はノードの要素で空の MPlug を返す。両方を判定して要素の種類を選ぶ。
            try:
                item = query.getPlug(index)
            except (RuntimeError, TypeError):
                item = None
            if item is None or item.isNull:
                try:
                    item = query.getComponent(index)
                except (RuntimeError, TypeError):
                    item = query.getDependNode(index)
            if not members.hasItem(item):
                return False
        return True

    def removeAllMembers(self):
        """セットに直接入っているメンバーを、すべて外す(``cmds.sets(clear=set)``)。

        ノードそのものは削除しない。fast引数は持たない(:meth:`addMembers` と同じ理由)。
        Undoが有効なら、1回のUndoで戻せる。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが無効(削除済み)の場合、またはMayaが処理を拒否した場合。
        """
        self._require_valid("クリア")
        with undoChunk("mlibObjectSetRemoveAllMembers"):
            cmds.sets(clear=self.getName())

    def getUnion(self, other):
        """このセットと別のセットの、少なくとも一方に直接入っているものを取得する(和集合)。

        入れ子になったセットの中身は展開しない。戻り値の形は :meth:`getMembers` と同じ。
        コンポーネントの範囲は、Mayaの選択リストの決まりでまとめる。シーンは変更しない。

        Args:
            other (ObjectSet | str): 比べるobjectSet。

        Returns:
            list[Node | Plug | Components]: 新しいリスト。

        Raises:
            TypeError: otherがobjectSetでない場合。
            RuntimeError: どちらかのノードが無効(削除済み)の場合。
        """
        members = self._member_list()
        members.merge(self._other_member_list(other))
        return self._member_names(members)

    def getIntersection(self, other):
        """このセットと別のセットの、両方に直接入っているものを取得する(共通部分)。

        コンポーネントは1要素ずつ比べる。たとえば ``cube.vtx[0:3]`` と ``cube.vtx[2:5]`` の共通部分は
        ``cube.vtx[2:3]`` になる。入れ子になったセットの中身は展開しない。シーンは変更しない。

        Args:
            other (ObjectSet | str): 比べるobjectSet。

        Returns:
            list[Node | Plug | Components]: 新しいリスト。形は :meth:`getMembers` と同じ。

        Raises:
            TypeError: otherがobjectSetでない場合。
            RuntimeError: どちらかのノードが無効(削除済み)の場合。
        """
        members = self._member_list()
        only_self = om2.MSelectionList(members)
        only_self.merge(self._other_member_list(other), om2.MSelectionList.kRemoveFromList)
        members.merge(only_self, om2.MSelectionList.kRemoveFromList)
        return self._member_names(members)

    def getDifference(self, other):
        """このセットに直接入っているもののうち、別のセットに直接入っていないものを取得する(差集合)。

        コンポーネントは1要素ずつ除く。入れ子になったセットの中身は展開しない。シーンは変更しない。

        Args:
            other (ObjectSet | str): 除くメンバーを持つobjectSet。

        Returns:
            list[Node | Plug | Components]: 新しいリスト。形は :meth:`getMembers` と同じ。

        Raises:
            TypeError: otherがobjectSetでない場合。
            RuntimeError: どちらかのノードが無効(削除済み)の場合。
        """
        members = self._member_list()
        members.merge(self._other_member_list(other), om2.MSelectionList.kRemoveFromList)
        return self._member_names(members)

    def isSubSet(self, other):
        """このセットに直接入っているものが、すべて別のセットにも直接入っているか調べる。

        空のセットは、どのセットに対してもTrueになる。入れ子になったセットの中身は展開しない。

        Args:
            other (ObjectSet | str): 含む側のobjectSet。

        Returns:
            bool: すべて含まれる場合はTrue。

        Raises:
            TypeError: otherがobjectSetでない場合。
            RuntimeError: どちらかのノードが無効(削除済み)の場合。
        """
        members = self._member_list()
        members.merge(self._other_member_list(other), om2.MSelectionList.kRemoveFromList)
        return members.isEmpty()

    def _member_list(self):
        """直接メンバーの選択リストを返す。

        Returns:
            om2.MSelectionList: 新しい選択リスト。

        Raises:
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        self._require_valid("メンバーの取得")
        return om2.MFnSet(self.mnode()).getMembers(False)

    @staticmethod
    def _other_member_list(other):
        """比べる相手のobjectSetを解決し、直接メンバーの選択リストを返す。

        Args:
            other (ObjectSet | str): 比べるobjectSet。

        Returns:
            om2.MSelectionList: 新しい選択リスト。

        Raises:
            TypeError: otherがobjectSetでない場合。
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        node = other if isinstance(other, Node) else Node(Object._input_name(other))
        node._require_valid("メンバーの取得")
        if not node.isType("objectSet"):
            raise TypeError(f"objectSetを指定してください: {node.getType()}: {node.getName()}")
        return om2.MFnSet(node.mnode()).getMembers(False)

    @staticmethod
    def _member_names(members):
        """選択リストを :meth:`getMembers` と同じ形のリストへ変換する。

        Args:
            members (om2.MSelectionList): 変換する選択リスト。

        Returns:
            list[Node | Plug | Components]: ノードはNode、アトリビュートはPlug、コンポーネントは範囲ごとの複数形のオブジェクト。
        """
        # 循環参照の回避: cmds・common・plugsがnodesを参照するため、使う時点で読み込む。
        from ..cmds.ls import _collect
        from ..common.selection import Selection
        from ..components import Component
        from ..plugs.plug import Plug

        result = []
        for name in members.getSelectionStrings():
            if "." not in name:
                result.append(Node(name))
                continue
            resolved = Selection(name).items
            if resolved and isinstance(resolved[0], Component):
                result.append(_collect(resolved))
            else:
                result.append(Plug._resolve_input(name))
        return result
