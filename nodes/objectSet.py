"""Maya の objectSet(セット)を扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.fastWrite import require_unlocked
from ..core.nodeEdit import require_editable
from ..core.object import Object
from ..decorator import _require_bool, undoChunk
from .node import Node, Nodes


class ObjectSet(Node):
    """objectSet(セット)を扱うクラス。

    ノード・アトリビュート・コンポーネントが、セットに入っているかどうかを扱う。
    セットへの登録は、DAGの親子付けやContainerへの所属とは別の関係になる。
    取得にはMFnSet、編集にはcmds.setsを使う。
    """

    def getMembers(self, *, flatten=False, dagOnly=False, shadingOnly=False):
        """セットのメンバーを取得する。

        flatten=Trueでは入れ子セットを再帰的に展開する。コンポーネント範囲の単一要素への分解とは異なる。
        既定では直接のメンバーだけを返す。所属関係と選択は変更しない。

        - ノード: Nodeのオブジェクトにする。
        - アトリビュート: Plugのオブジェクトにする。
        - コンポーネント: ``vtx[0:3]`` のようにまとめられた範囲ごとに、Verticesなどの複数形のオブジェクトにする。

        順番はMaya APIが列挙する順のまま。独自に並べ替えない。

        ``dagOnly=True`` なら、セットに属するDAGパスだけを、ノードの集まりで返す。
        コンポーネントはそれを持つDAGパスになり、DGノードやPlugは返さない。
        Maya API 2.0にgetMemberPathsが無い版では対応していない。

        Args:
            flatten (bool): Trueなら入れ子セットの内容を取得する。既定False。dagOnly=Trueとは同時に指定できない。
            dagOnly (bool): Trueなら、DAGパスだけをNodesで返す。既定False。
            shadingOnly (bool): dagOnly=Trueのときに、Trueならマテリアルの割り当てに関係するDAGパスだけを返す。既定False。

        Returns:
            list[Node | Plug | Components] | Nodes[DagNode]: 新しいリスト。空のセットなら空リスト。
                dagOnly=Trueなら、Mayaの順に並ぶパスごとのノードの集まり。

        Raises:
            TypeError: flatten・dagOnly・shadingOnlyがboolでない場合、flattenとdagOnlyを同時に指定した場合、
                またはdagOnly=TrueなしでshadingOnlyを指定した場合。
            RuntimeError: ノードが無効な場合。
            NotImplementedError: dagOnly=Trueで、使っているMayaに対応するAPI 2.0のメソッドが無い場合。
        """
        _require_bool(flatten, "flatten")
        _require_bool(dagOnly, "dagOnly")
        _require_bool(shadingOnly, "shadingOnly")
        if not dagOnly:
            if shadingOnly:
                raise TypeError("shadingOnlyはdagOnly=Trueのときだけ指定できます")
            return self._member_names(om2.MFnSet(self.mnode()).getMembers(flatten))
        if flatten:
            raise TypeError("flattenとdagOnlyは同時に指定できません")
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

    def addMembers(self, *members, forceElement=False):
        """ノードやコンポーネントなどを、このセットへ追加する。

        入力はほかのメソッドと同じ方法で解決し、cmds.setsへ渡す。何も渡さなければ、何も変えない。
        ノードを複製したり、親子付けしたりはしない。
        fast引数は持たない(MFnSetでの更新はcmds.setsより遅いため)。

        ``forceElement=True`` は、同じpartitionの中の排他の所属を移して追加する(``cmds.sets(forceElement=...)`` と同じ名前)。
        同じpartitionの別のセットから、対象が外れる場合がある。
        partitionの作成や、partitionが違うセットからの除外はしない。

        Args:
            forceElement (bool): Trueなら、同じpartitionの別のセットから外して追加する。既定はFalse。
            *members (Node | str): 追加するもの。ノードやコンポーネントの表記などを渡す。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対応していない型を渡した場合、名前とNodeなどのオブジェクトを混ぜて渡した場合、
                またはforceElementがboolでない場合。
            ValueError: 名前に一致するものが無い場合。
            RuntimeError: forceElement=Trueでセットが無効な場合、またはMayaが追加を拒否した場合。
        """
        _require_bool(forceElement, "forceElement")
        if forceElement:
            self._require_valid("排他所属の変更")
        with undoChunk("mlibObjectSetAddMembers"):
            if members:
                names = Object._input_names(members)
                if forceElement:
                    cmds.sets(names, forceElement=self.getName())
                else:
                    cmds.sets(names, add=self.getName())

    def removeMembers(self, *members, all=False):
        """指定したメンバーを、このセットから外す。``all=True`` なら、直接入っているメンバーをすべて外す。

        外すのはセットへの所属だけで、ノードそのものは削除しない。何も渡さなければ何も変えない。
        入力の解決のしかたは :meth:`addMembers` と同じ。``all=True`` は ``cmds.sets(clear=set)`` を使う。
        fast引数は持たない(:meth:`addMembers` と同じ理由)。Undoが有効なら、1回のUndoで戻せる。

        Args:
            all (bool): Trueなら、直接入っているメンバーをすべて外す。既定はFalse。
            *members (Node | str): 外すもの。ノードやコンポーネントの表記などを渡す。all=Trueとは同時に指定できない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: allがboolでない場合、membersとall=Trueを同時に指定した場合、対応していない型を渡した場合、
                または名前とNodeなどのオブジェクトを混ぜて渡した場合。
            ValueError: 名前に一致するものが無い場合、または渡したものが無効な(削除された)場合。
            RuntimeError: ノードが無効な場合、セットがロックされているかリファレンスの場合、
                メンバーのアトリビュート(``dagSetMembers``・``dnSetMembers``)がロックされている場合、
                またはMayaが外すのを拒否した場合。

        Note:
            Mayaはセットのロックを見ずにメンバーを外すため、ロックとリファレンスは ``cmds.sets`` を呼ぶ前に確かめる。
        """
        _require_bool(all, "all")
        if all:
            if members:
                raise TypeError("membersとall=Trueは同時に指定できません")
            self._require_members_editable("クリア")
            with undoChunk("mlibObjectSetRemoveMembers"):
                cmds.sets(clear=self.getName())
            return
        if not members:
            return
        self._require_members_editable("メンバーの削除")
        with undoChunk("mlibObjectSetRemoveMembers"):
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

        Raises:
            TypeError: 対応していない型を渡した場合。
            ValueError: 名前に一致するものが無い場合、または渡したものが無効な(削除された)場合。
        """
        name = Object._input_name(member)
        query = om2.MSelectionList()
        try:
            query.add(name)
        except RuntimeError:
            raise ValueError(f"名前に一致するものがありません: {name}") from None
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

    def combine(self, other, *, mode="union"):
        """このセットと別のセットのメンバーを、集合の演算で組み合わせて取得する。セットは書き換えない。

        どちらも、直接入っているものだけを使う(入れ子になったセットの中身は展開しない)。
        戻り値の形は :meth:`getMembers` と同じ。コンポーネントは1要素ずつ比べ、範囲はMayaの選択リストの決まりでまとめる。
        たとえば ``cube.vtx[0:3]`` と ``cube.vtx[2:5]`` の共通部分は ``cube.vtx[2:3]`` になる。

        Args:
            other (ObjectSet | str): 比べるobjectSet。
            mode (str): 演算の種類。既定は ``"union"``。

                - ``"union"``: 少なくとも一方に入っているもの(和集合)。
                - ``"intersection"``: 両方に入っているもの(共通部分)。
                - ``"difference"``: このセットに入っていて、otherに入っていないもの(差集合)。

        Returns:
            list[Node | Plug | Components]: 新しいリスト。

        Raises:
            TypeError: otherがobjectSetでない場合、またはmodeがstrでない場合。
            ValueError: modeが対応していない名前の場合。
            RuntimeError: どちらかのノードが無効(削除済み)の場合。
        """
        if not isinstance(mode, str):
            raise TypeError(f"modeはstrで指定してください: {type(mode).__name__}")
        if mode not in ("union", "intersection", "difference"):
            raise ValueError(f"modeは'union'・'intersection'・'difference'のどれかで指定してください: {mode!r}")
        members = self._member_list()
        others = self._other_member_list(other)
        if mode == "union":
            members.merge(others)
        elif mode == "difference":
            members.merge(others, om2.MSelectionList.kRemoveFromList)
        else:
            only_self = om2.MSelectionList(members)
            only_self.merge(others, om2.MSelectionList.kRemoveFromList)
            members.merge(only_self, om2.MSelectionList.kRemoveFromList)
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

    def _require_members_editable(self, action):
        """メンバーを外す前に、セットとメンバーのアトリビュートを編集できるかを確かめる。

        Args:
            action (str): 例外の文に入れる操作の名前。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが無効な場合、セットがロックされているかリファレンスの場合、
                またはメンバーのアトリビュートかその要素がロックされている場合。
        """
        self._require_valid(action)
        require_editable(self.mnode())
        dependency = self._dependency_fn()
        for name in ("dagSetMembers", "dnSetMembers"):
            require_unlocked(dependency.findPlug(name, False))

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
            resolved = Selection(name).getItems()
            if resolved and isinstance(resolved[0], Component):
                result.append(_collect(resolved))
            else:
                result.append(Plug._resolve_input(name))
        return result
