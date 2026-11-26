# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の objectSet(セット)を扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.fastWrite import require_unlocked
from ..core.nodeEdit import require_editable
from ..core.object import Object
from ..decorator import _require_bool, undoChunk
from .node import Node, Nodes
from typing import Literal
from mlib.components.component import Components
from mlib.nodes.dagNode import DagNode
from mlib.plugs.plug import Plug
from typing import overload



class ObjectSet(Node):
    """objectSet(セット)を扱うクラス。

    ノード・アトリビュート・コンポーネントが、セットに入っているかどうかを扱う。
    セットへの登録は、DAGの親子付けやContainerへの所属とは別の関係になる。
    取得にはMFnSet、編集にはcmds.setsを使う。
    """
    @overload
    def getMembers(self, *, flatten: bool = ..., dagOnly: Literal[True], shadingOnly: bool = ...) -> Nodes[DagNode]: ...
    @overload
    def getMembers(self, *, flatten: bool = ..., dagOnly: Literal[False] = ..., shadingOnly: Literal[False] = ...) -> list[Node | Plug | Components]: ...
    @overload
    def getMembers(self, *, flatten: bool = ..., dagOnly: bool = ..., shadingOnly: bool = ...) -> list[Node | Plug | Components] | Nodes[DagNode]:
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
        ...
    def getRestriction(self) -> int:
        """セットに登録できるメンバーの種類の制限を取得する。

        Returns:
            int: om2.MFnSetの制限定数。制限なしはkNone。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def addMembers(self, *members: Node | str, forceElement: bool = ...) -> None:
        """ノードやコンポーネントなどを、このセットへ追加する。

        入力はほかのメソッドと同じ方法で解決し、cmds.setsへ渡す。何も渡さなければ、何も変えない。
        ノードを複製したり、親子付けしたりはしない。
        fast引数は持たない(MFnSetでの更新はcmds.setsより遅いため)。

        ``forceElement=True`` は、同じpartitionの中の排他の所属を移して追加する(``cmds.sets(forceElement=...)`` と同じ名前)。
        同じpartitionの別のセットから、対象が外れる場合がある。
        partitionの作成や、partitionが違うセットからの除外はしない。

        Args:
            *members (Node | str): 追加するもの。ノードやコンポーネントの表記などを渡す。
            forceElement (bool): Trueなら、同じpartitionの別のセットから外して追加する。既定はFalse。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対応していない型を渡した場合、名前とNodeなどのオブジェクトを混ぜて渡した場合、
                またはforceElementがboolでない場合。
            ValueError: 名前に一致するものが無い場合。
            RuntimeError: forceElement=Trueでセットが無効な場合、またはMayaが追加を拒否した場合。
        """
        ...
    def removeMembers(self, *members: Node | str, all: bool = ...) -> None:
        """指定したメンバーを、このセットから外す。``all=True`` なら、直接入っているメンバーをすべて外す。

        外すのはセットへの所属だけで、ノードそのものは削除しない。何も渡さなければ何も変えない。
        入力の解決のしかたは :meth:`addMembers` と同じ。``all=True`` は ``cmds.sets(clear=set)`` を使う。
        fast引数は持たない(:meth:`addMembers` と同じ理由)。Undoが有効なら、1回のUndoで戻せる。

        Args:
            *members (Node | str): 外すもの。ノードやコンポーネントの表記などを渡す。all=Trueとは同時に指定できない。
            all (bool): Trueなら、直接入っているメンバーをすべて外す。既定はFalse。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: allがboolでない場合、またはmembersとall=Trueを同時に指定した場合。
            RuntimeError: ノードが無効な場合、セットがロックされているかリファレンスの場合、
                メンバーのアトリビュート(``dagSetMembers``・``dnSetMembers``)がロックされている場合、
                またはMayaが外すのを拒否した場合。

        Note:
            Mayaはセットのロックを見ずにメンバーを外すため、ロックとリファレンスは ``cmds.sets`` を呼ぶ前に確かめる。
        """
        ...
    def isMember(self, member: Node | str) -> bool:
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
        ...
    def combine(self, other: ObjectSet | str, *, mode: str = ...) -> list[Node | Plug | Components]:
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
        ...
    def isSubSet(self, other: ObjectSet | str) -> bool:
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
        ...
    def _require_members_editable(self, action: str) -> None:
        """メンバーを外す前に、セットとメンバーのアトリビュートを編集できるかを確かめる。

        Args:
            action (str): 例外の文に入れる操作の名前。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: ノードが無効な場合、セットがロックされているかリファレンスの場合、
                またはメンバーのアトリビュートかその要素がロックされている場合。
        """
        ...
    def _member_list(self) -> om2.MSelectionList:
        """直接メンバーの選択リストを返す。

        Returns:
            om2.MSelectionList: 新しい選択リスト。

        Raises:
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    @staticmethod
    def _other_member_list(other: ObjectSet | str) -> om2.MSelectionList:
        """比べる相手のobjectSetを解決し、直接メンバーの選択リストを返す。

        Args:
            other (ObjectSet | str): 比べるobjectSet。

        Returns:
            om2.MSelectionList: 新しい選択リスト。

        Raises:
            TypeError: otherがobjectSetでない場合。
            RuntimeError: ノードが無効(削除済み)の場合。
        """
        ...
    @staticmethod
    def _member_names(members: om2.MSelectionList) -> list[Node | Plug | Components]:
        """選択リストを :meth:`getMembers` と同じ形のリストへ変換する。

        Args:
            members (om2.MSelectionList): 変換する選択リスト。

        Returns:
            list[Node | Plug | Components]: ノードはNode、アトリビュートはPlug、コンポーネントは範囲ごとの複数形のオブジェクト。
        """
        ...
