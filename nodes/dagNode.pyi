# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""TransformとShapeに共通するDAG階層へのアクセスを提供する。"""

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
import maya.OpenMaya as om1
from ..core.fastWrite import require_writable, set_plug
from ..core.registry import _inherited_node_types, _real_node_type
from ..decorator import _edit_context, _pick_alias, _require_bool, undoChunk, undoTransaction
from ..maths import Vector
from ..util import _UNSET, _color_value, _world_space
from .node import Node, Nodes
from typing import Iterable, Literal, Sequence
from mlib.components.component import Components
from mlib.nodes.dagPose import DagPose
from mlib.nodes.objectSet import ObjectSet
from mlib.nodes.skinCluster import SkinClusters
from mlib.nodes.transform import Transform
from typing import overload

_INFLUENCE_ATTRIBUTES: tuple
_DEFAULT_COLOR_PALETTE: tuple
_DISPLAY_TYPES: tuple
_DRAW_COLOR_MODES: dict

def _type_filter(value: str | Iterable[str] | None) -> tuple[str, ...]:
    """getChildren(type=) の指定を、型名のtupleにそろえる。

    Args:
        value (str | Iterable[str] | None): ノード型名、その並び、またはNone。

    Returns:
        tuple[str, ...]: 型名。Noneなら空。

    Raises:
        TypeError: 文字列・文字列の並び・Noneのどれでもない場合。
        ValueError: 空文字列を含む場合。
    """
    ...

def _require_index(index: object) -> None:
    """getShapeのindexがint(boolを除く)かを確かめる。

    Args:
        index (object): 確かめる値。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: intでない場合。
    """
    ...


class DagNode(Node):
    """TransformとShapeに共通する、DAGの階層を扱うクラス。

    このクラスのオブジェクトは、ノードへのDAGパスを1つ持つ。インスタンス化されたノードには
    パスが複数あるが、getParentやgetChildrenは、このオブジェクトが持つパスをたどる。
    ほかのパスを含めて全部を調べるときはgetInstancesを使う。

    各メソッドの説明にある「保持するDAGパスが無効」は、次のどちらかを指す。

    - このオブジェクトが持つパスのインスタンスだけが取り除かれた。
    - ノードそのものが削除された(Undoで戻せる間も含む)。

    どちらの場合もMayaのMDagPathは古いパスを返し続ける。そのため、パスを使う取得は
    空文字列や削除前の名前を返さず、RuntimeErrorにする。
    """
    def getSetsAndMembers(self, *, renderableOnly: bool = ...) -> list[tuple[ObjectSet, list[Components] | None]]:
        """保持するDAGパスについて、所属セットと対象コンポーネントを取得する。

        MFnDagNodeのインスタンス別の照会を使う。TransformからShapeへは移動しない。
        セットへの所属やマテリアルの割り当ては変更しない。

        Args:
            renderableOnly (bool): Trueならレンダー可能なセットだけを返す。既定False。

        Returns:
            list[tuple[ObjectSet, list[Components] | None]]: Mayaが列挙する順の組。
                コンポーネントは範囲ごとの集まり、オブジェクト全体の所属はNone。

        Raises:
            TypeError: renderableOnlyがboolでない場合。
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def getSkinClusters(self, *, influence: bool = ...) -> SkinClusters:
        """このノードに関係するSkinClusterを取得する。``influence=True`` なら、このノードをインフルエンスに持つものを取得する。

        既定(``influence=False``)では、このノードのジオメトリを変形しているSkinClusterを返す。
        Shapeから呼ぶと自身を、Transform(Jointを含む)から呼ぶと直下のShape(中間オブジェクトを除く)を調べる。
        子のTransformより下は調べない。ヒストリを上流へたどり、出力先がそのShapeになっているSkinClusterだけを返す。
        途中でつながっている別の形状のSkinClusterは含まない。メッシュ・NURBSなどShapeの種類を問わず使える。

        ``influence=True`` では、このノードからインフルエンスの入力(``matrix``・``lockWeights``・``influenceColor``・
        ``driverPoints``・``basePoints`` の要素)へ直接つながっているSkinClusterを返す。
        ジョイントのほか、インフルエンスにしたTransformやShapeにも使える。

        どちらもシーンとUndoの記録は変更しない。

        Args:
            influence (bool): Trueなら、このノードをインフルエンスに持つSkinClusterを返す。既定はFalse。

        Returns:
            SkinClusters: 見つかったSkinCluster。同じものは1回だけ含む。見つからなければ空リスト。
                ``influence=False`` ではShapeの順に、Shapeごとに近いものから並ぶ。
                ``influence=True`` では接続の順に並び、無効なノードでは空リスト。

        Raises:
            TypeError: influenceがboolでない場合。
            RuntimeError: 保持するDAGパスが無効な場合(``influence=False`` のとき)、またはMayaの検索が失敗した場合。
        """
        ...
    def getBindPoses(self, *, influence: bool = ...) -> Nodes[DagPose]:
        """このノードに関係するSkinClusterのバインドポーズを取得する。

        対象のSkinClusterは、同じ引数の :meth:`getSkinClusters` と同じ。既定では自身(のShape)を変形しているもの、
        ``influence=True`` では自身をインフルエンスに持つものになる。

        SkinClusterの順に並べる。複数のSkinClusterが同じポーズを共有していれば1回だけ含め、
        バインドポーズが接続されていないSkinClusterは飛ばす。

        Args:
            influence (bool): Trueなら、自身をインフルエンスに持つSkinClusterのバインドポーズを返す。既定はFalse。

        Returns:
            Nodes[DagPose]: 接続されているバインドポーズ。1つもなければ空の集まり。

        Raises:
            TypeError: influenceがboolでない場合。
            RuntimeError: 対象が無効な場合、またはバインドポーズの接続が不正な場合。
        """
        ...
    def mpath(self) -> om2.MDagPath:
        """このオブジェクトが持つDAGパスを、OpenMayaのMDagPathとして取得する。

        コピーではなく、内部で持っているMDagPathそのものを返す。pushやpopで書き換えると
        このオブジェクトのパスも変わってしまうので、書き換える前に
        ``om2.MDagPath(node.mpath())`` でコピーを作る。

        Returns:
            om2.MDagPath: 内部で持っているパスと同じオブジェクト。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。ほかのインスタンスのパスへは切り替えない。
        """
        ...
    def mfn(self) -> om2.MFnDagNode:
        """このオブジェクトが持つDAGパスのfunction setを作る。

        呼ぶたびに新しく作って返す。TransformやMeshなどの派生クラスでは、
        それぞれに合った、より具体的なfunction setを返す。

        Returns:
            om2.MFnDagNode: このオブジェクトのfunction set。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def getRoot(self) -> Transform:
        """いちばん上(ワールド直下)の祖先を取得する。

        このオブジェクトが持つDAGパスを、ワールド直下まで上へたどる。
        DAGの親は必ずTransformなので、Shapeから呼んでもTransformが返る。
        自身がワールド直下にあれば自身を返す。

        Returns:
            Transform: ワールド直下の祖先、または自身(ワールド直下に置けるのはTransform系だけ)。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def getCommonAncestor(self, other: DagNode | str | om2.MObject | om2.MDagPath) -> DagNode | None:
        """自身とotherに共通する、いちばん近い祖先を取得する。

        それぞれのオブジェクトが持つDAGパスどうしで比べる。インスタンス化されていても、
        ほかのパスでの共通の祖先は探さない。
        一方がもう一方の祖先(または同じパス)なら、その祖先自身を返す。

        Args:
            other (DagNode | str | om2.MObject | om2.MDagPath): 比べるDAGノード。

        Returns:
            DagNode | None: 共通の祖先。自身が当てはまれば自身、otherが当てはまればotherそのもの、
                それ以外は新しいオブジェクト。ワールド直下の別々の階層にあればNone。

        Raises:
            TypeError: otherがDAGノードでない、または対応していない型の場合。
            RuntimeError: 自身またはotherのノード、または保持するDAGパスが無効な場合。

        Examples:
            >>> hand.getCommonAncestor(foot)    # 腰など、両方を含む最も近い親
        """
        ...
    def getSiblings(self) -> Nodes[DagNode]:
        """同じ親の下にある、同じ種類の兄弟を取得する。

        自身と、自身のほかのインスタンスは含まない。並びはDAGの子の順。

        - Transformなら、親の直下にあるほかのTransformを返す。
        - Shapeなら、親の直下にあるほかのShape(中間オブジェクトを除く)を返す。
        - ワールド直下のTransformなら、ほかのワールド直下のTransformを返す。

        Returns:
            Nodes[DagNode]: 兄弟のオブジェクト。ノードが無効な場合と、兄弟がない場合は空の集まり。

        Raises:
            RuntimeError: ノードは有効だが、保持するDAGパスが無効な場合。
        """
        ...
    def getOutlinerOrder(self) -> int:
        """アウトライナーでの並び順を取得する。

        このオブジェクトが持つDAGパスが、親の直接の子の中で何番目にあるかを返す。
        Transform・Shape・中間オブジェクトを区別せず、親の直接の子すべてをDAGの子の順で数える。
        同じ種類だけを返す :meth:`getSiblings` とは数え方が違う。
        ワールド直下のノードは、``cmds.ls(assemblies=True)`` の並び(既定のカメラを含む)の中で数える。

        Returns:
            int: 0 始まりの番号。

        Raises:
            RuntimeError: ノードが無効な場合、または並びの中にこのオブジェクトのパスが見つからない場合。

        Examples:
            >>> node.getOutlinerOrder()    # 親の最初の子なら 0
        """
        ...
    def reorder(self, *, index: int | None = ..., front: bool = ..., f: bool = ..., back: bool = ..., b: bool = ..., relative: int | None = ..., r: int = ...) -> None:
        """アウトライナーでの並び順を変える(``cmds.reorder`` 相当)。

        親の直接の子の中での順番を変える。``index``・``front``・``back``・``relative`` のどれか1つを指定する。
        ほかの子は、互いの順番を保ったまま詰める。
        並びの数え方は :meth:`getOutlinerOrder` と同じ。変えるのは、このオブジェクトが持つDAGパスの親の下だけで、
        インスタンスのほかの親の下の順番は変えない。
        ``relative`` は端を越えると反対側へ回る(最後の子に 1 を指定すると先頭になる)。
        ``index`` は移動先の番号で、端を越えない(範囲外はIndexError)。
        OpenMayaには子の順番を変える機能が無いため、fast引数は持たない。Undoが有効なら1回で戻せる。

        Args:
            index (int | None): 移動先の番号(0 始まり。:meth:`getOutlinerOrder` と同じ数え方)。負の値は後ろから数える(-1 は最後)。既定はNone。
            front (bool): Trueなら先頭へ移動する。既定はFalse。
            f (bool): frontの別名。frontと同時には指定できない。
            back (bool): Trueなら最後へ移動する。既定はFalse。
            b (bool): backの別名。backと同時には指定できない。
            relative (int | None): 移動する数。正の値は後ろへ、負の値は前へ動かす。既定はNone。
            r (int): relativeの別名。relativeと同時には指定できない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 長い名前と短い名前を同時に指定した場合、front・back が bool でない場合、index・relative が
                int でない場合、または index・front・back・relative のちょうど1つを指定していない場合。
            IndexError: index が範囲外の場合。
            RuntimeError: ノードが無効な場合、またはMayaが拒否した場合(ロックされたノードなど)。

        Examples:
            >>> node.reorder(front=True)     # 先頭へ
            >>> node.reorder(back=True)      # 最後へ
            >>> node.reorder(relative=-1)    # 1つ前へ
            >>> node.reorder(index=0)        # 番号で指定して先頭へ
            >>> node.reorder(index=-1)       # 番号で指定して最後へ
        """
        ...
    def isInUnderworld(self) -> bool:
        """このDAGノードがShape内部のunderworldにあるか調べる。

        Returns:
            bool: サーフェス上のカーブ等のunderworldノードならTrue。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def isInModel(self) -> bool:
        """DAGノードがMayaのモデルに属しているか調べる。

        Returns:
            bool: MFnDagNode.inModelの値。表示・選択可能性の判定ではない。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    @overload
    def getBoundingBox(self, worldSpace: bool = ..., *, includeInvisible: bool = ..., corners: Literal[True], ws: bool = ...) -> list[Vector]: ...
    @overload
    def getBoundingBox(self, worldSpace: bool = ..., *, includeInvisible: bool = ..., corners: Literal[False] = ..., ws: bool = ...) -> om2.MBoundingBox: ...
    @overload
    def getBoundingBox(self, worldSpace: bool = ..., *, includeInvisible: bool = ..., corners: bool = ..., ws: bool = ...) -> om2.MBoundingBox | list[Vector]:
        """バウンディングボックスを取得する。

        既定では ``MFnDagNode.boundingBox`` の値を返す。これは自身のtranslate・rotate・scale
        (Transformの場合)を含むが、親から受け継いだ変換は含まない(``cmds.xform(-boundingBox)`` と同じ)。
        ``worldSpace=True`` なら、そこへこのオブジェクトが持つDAGパスの ``exclusiveMatrix``
        (親までのワールドマトリクス)をかけ、ワールド空間のボックスを返す。
        Shapeでは、自身のローカルの形状から計算する。
        TransformのincludeInvisible=Trueではcmds.xformの非表示を含むボックスを問い合わせる。
        Shapeはこの指定によらず自身の形状のボックスを返す。

        ``corners=True`` なら、ボックスの代わりに8つの隅の点を返す。ワールド空間を指定しても、
        ワールドの軸に沿ったボックスの隅になる(ノードの向きに合わせて回したボックスの隅ではない)。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseなら親の変換を含まない空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            includeInvisible (bool): Trueなら非表示の子の形状も含む。既定False。
            corners (bool): Trueなら、8つの隅の点を返す。既定はFalse。

        Returns:
            om2.MBoundingBox | list[Vector]: 軸に沿ったボックス。単位はMaya APIの内部の距離単位。
                子のShapeが無いTransformでは、原点だけを含む、ほぼ空のボックスになる。
                corners=Trueなら、cm単位の8点。X・Y・Zの順に、最小と最大を組み合わせた順に並ぶ
                ((minX, minY, minZ), (minX, minY, maxZ), (minX, maxY, minZ), ..., (maxX, maxY, maxZ))。

        Raises:
            TypeError: worldSpace・includeInvisible・cornersがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: ノードが無効な場合、または保持するDAGパスが無効な場合。

        Examples:
            >>> corners = node.getBoundingBox(ws=True, corners=True)
        """
        ...
    def isIntermediateObject(self) -> bool:
        """中間オブジェクトかどうかを調べる。

        中間オブジェクトは、ヒストリのために残している非表示のShapeのこと。Transformでは常にFalse。

        Returns:
            bool: 中間オブジェクトならTrue。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def getInstances(self, *, includeSelf: bool = ...) -> Nodes[DagNode]:
        """同じノードへのDAGパス(インスタンス)をすべて取得する。

        すでにあるパスを調べるだけで、ノードを複製したり、インスタンスを新しく作ったりはしない。
        親がインスタンス化されたことで生じたパス(間接的なインスタンス)も含む。

        Args:
            includeSelf (bool): Falseなら、このオブジェクトが持つパスを結果から除く。既定はTrue。

        Returns:
            Nodes[DagNode]: パスごとのオブジェクト。順番はMaya APIが列挙する順。
                このオブジェクトが持つパスには自身を、ほかのパスには新しいオブジェクトを入れる。

        Raises:
            TypeError: includeSelfがboolでない場合。
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def isInstanced(self) -> bool:
        """インスタンス化されているか(DAGパスが複数あるか)を調べる。

        親がインスタンス化されたことで生じたパス(間接的なインスタンス)も数える。
        ``len(getInstances()) > 1`` と同じ結果になる。

        Returns:
            bool: パスが2つ以上ならTrue。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def getInstanceIndex(self) -> int:
        """インスタンス番号を取得する。

        このオブジェクトが持つDAGパスの ``MDagPath.instanceNumber`` を返す。
        インスタンス化されていないノードでは0。:meth:`getInstances` の結果の並び順と一致するとは限らない。

        Returns:
            int: 0以上のインスタンス番号。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    @overload
    def getParent(self, step: int = ..., *, all: bool = ..., instances: Literal[True], indirect: bool = ...) -> Nodes[Transform]: ...
    @overload
    def getParent(self, step: int = ..., *, all: bool = ..., instances: Literal[False] = ..., indirect: Literal[False] = ...) -> Transform | None: ...
    @overload
    def getParent(self, step: int = ..., *, all: bool = ..., instances: bool = ..., indirect: bool = ...) -> Transform | Nodes[Transform] | None:
        """親を取得する。

        このオブジェクトが持つDAGパスを、上へたどって求める。

        ``all=True`` なら、祖先(親・親の親…ワールド直下まで)を近い順にすべて返す
        (:meth:`Plug.getParent(all=True) <mlib.plugs.plug.Plug.getParent>` と同じ考え方)。

        ``instances=True`` なら、直接の親をすべて返す。インスタンス化されたノードには親が複数あり、そのすべてを返す
        (親の親など、さらに上の祖先は含まない)。

        Args:
            step (int): 何階層上の親を取得するか。1は直接の親、2は親の親。既定は1。all=True・instances=Trueとは同時に指定できない。
            all (bool): Trueなら、祖先を近い順にすべて取得する。既定はFalse。instances=Trueとは同時に指定できない。
            instances (bool): Trueなら、インスタンスの直接の親をすべて取得する。既定はFalse。
            indirect (bool): instances=Trueのときの、親の数え方を選ぶ。既定はFalse。

                - False: 親のノードごとに1つ返す。順番はMaya APIの親の順。
                  このオブジェクトが持つパスの親にはそのパスを使い、ほかの親にはMaya APIが返すパスを1つ使う。
                - True: getInstances()が返すパスごとに、その親を返す。
                  親がインスタンス化されたことで生じたパスの分も含む。

        Returns:
            Transform | Nodes[Transform] | None: 親の新しいオブジェクト。DAGの親は必ずTransform系(Jointなど)になる。
                stepが0以下の場合と、ワールドまで(それより上へ)たどる場合はNone。
                all=Trueなら祖先を近い順に並べた集まり(すべてJointなら ``Joints``)。
                instances=Trueなら親の集まり。同じ親が重なってもまとめない。
                このオブジェクトが持つパスがワールド直下なら、all=True・instances=Trueとも空の集まり。

        Raises:
            TypeError: all・instances・indirectがboolでない場合、allかinstancesとstepを同時に指定した場合、
                allとinstancesを同時に指定した場合、またはinstances=Falseでindirect=Trueを指定した場合。
            RuntimeError: stepが正で、保持するDAGパスが無効な場合。
        """
        ...
    def getChildren(self, *, shapes: bool = ..., intermediates: bool = ..., allDescendents: bool = ..., sortBy: str = ..., leaves: bool = ..., includeSelf: bool = ..., underWorld: bool = ..., type: str | Iterable[str] | None = ...) -> Nodes[DagNode]:
        """子、または子孫を取得する。

        このオブジェクトが持つDAGパスから下へたどる。結果のパスは、たどった道筋のまま作り、
        名前から探し直さない。そのため、同じノードが複数のパスで見つかれば、パスごとに結果へ入る。

        Args:
            shapes (bool): TrueならShapeも含める。既定はFalse(Transformだけ)。
            intermediates (bool): Trueなら中間オブジェクトも含める。既定はFalse。
                含めなかった中間オブジェクトの下は調べない。
            allDescendents (bool): Trueなら子孫すべて、Falseなら直接の子だけを取得する。既定はFalse。
            sortBy (str): 並べる順。``"depthFirst"`` (深さ優先。既定)か ``"breadthFirst"`` (幅優先)。
                兄弟どうしはDAGの子の順に並ぶ。
            leaves (bool): Trueなら、末端のTransform(子にTransformを持たないもの)を、下の階層まで
                たどって取得する。Shapeを持っていても末端として扱う。shapes=Trueとは同時に指定できない。既定はFalse。
            includeSelf (bool): Trueなら自身も対象にする。shapes・leavesの条件に合えば、
                自身(同じオブジェクト)を結果へ入れる。既定はFalse。
            underWorld (bool): Trueなら、Shapeの下のアンダーワールドも調べる。既定はFalse。
            type (str | Iterable[str] | None): 結果をMayaのノード型で絞る。``cmds.listRelatives(type=)`` と同じく、
                指定した型から派生した型も含む(:meth:`~mlib.nodes.node.Node.isType` で判定する)。
                絞るのは結果だけで、たどる範囲は変わらない。``allDescendents=True`` では、型の違う子の下も調べる。
                Shapeの型(``"mesh"`` など)を指定した場合は、shapes=FalseでもShapeを含めて調べる。
                ``multDoubleLinear`` と ``multDL`` のように、Mayaの版で名前が変わった型はどちらの名前でも指定できる。既定はNone。

        Returns:
            Nodes[DagNode]: たどった順のオブジェクト。該当するものがない場合と、
                ノードそのものが無効な場合は空リスト。

        Raises:
            TypeError: shapes・intermediates・allDescendents・leaves・includeSelf・underWorldがboolでない場合、
                またはtypeが文字列・文字列の並び・Noneのどれでもない場合。
            ValueError: sortByが不正な場合、leavesとshapesを同時に指定した場合、
                またはtypeに空文字列を指定した場合。
            RuntimeError: ノードは有効だが、保持するDAGパスが無効な場合。
        """
        ...
    @overload
    def getShape(self, *, index: int = ..., intermediates: bool = ..., all: Literal[True]) -> Nodes[DagNode]: ...
    @overload
    def getShape(self, *, index: int = ..., intermediates: bool = ..., all: Literal[False] = ...) -> DagNode | None: ...
    @overload
    def getShape(self, *, index: int = ..., intermediates: bool = ..., all: bool = ...) -> DagNode | Nodes[DagNode] | None:
        """Shapeを取得する。

        ノードの種類によって次のように返す。

        - Shapeなら、``index``・``intermediates`` を使わずに自身を返す(型だけは確かめる)。
        - Transformなら、派生クラス(Transform.getShape)が、直下のShapeのうち ``index`` 番目
          (0 始まり)を返す。範囲外(負の数を含む)ならNone。
        - それ以外のDAGノードならNone。

        範囲外のindexでもIndexErrorにはしない。
        ``all=True`` なら、1つではなく当てはまるShapeすべてを集まりで返す(Shapeなら自身だけ、Transformなら直下のShapeすべて)。

        Args:
            index (int): Transformで、何番目のShapeを選ぶか。Shapeでは無視する。既定は0。
            intermediates (bool): Trueなら、Transformで中間オブジェクトも候補に含める。Shapeでは無視する。既定はFalse。
            all (bool): Trueなら、Shapeすべてを集まりで返す。既定はFalse。indexとは同時に指定できない。

        Returns:
            DagNode | Nodes[DagNode] | None: Shapeなら自身、Transformなら選んだShape。当てはまるものがなければNone。
                all=Trueなら集まり(当てはまるものがなければ空)。

        Raises:
            TypeError: indexがintでない場合、intermediates・allがboolでない場合、またはall=Trueとindexを同時に指定した場合。
            RuntimeError: ノードが破棄されている場合。
        """
        ...
    def isTemplated(self) -> bool:
        """保持するDAGパスの親階層を含めてテンプレート表示の状態を調べる。

        MDagPath.isTemplatedの結果を返す。templateと描画オーバーライドによる
        テンプレート表示を含む。非表示・参照表示など、選択できない原因すべての判定ではない。

        Returns:
            bool: 保持するパスがテンプレート表示ならTrue。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def isVisible(self) -> bool:
        """親の階層まで含めて、表示されているかを調べる。

        このオブジェクトが持つDAGパスで調べ、親のどれかが非表示なら自身も非表示として扱う。

        Returns:
            bool: 親の階層まで含めて表示されていればTrue。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合(削除済みのノードを含む)。
        """
        ...
    def getObjectGroupComponents(self, groupId: int) -> list[Components]:
        """groupIdが示す、このDAGパス上の所属コンポーネントを取得する。

        Mayaのobject groupの番号で、セット一覧内の位置とは異なる。API 1.0の照会を使い、
        返された要素名を保持中の完全パスへ解決する。所属や現在の選択は変更しない。

        Args:
            groupId (int): groupIdノードのgroupIdアトリビュート値。非負の整数。

        Returns:
            list[Components]: 要素の種類ごとにまとめたコンポーネント。

        Raises:
            TypeError: groupIdが整数でない場合。
            ValueError: groupIdが負の場合。
            RuntimeError: この形状に番号が無い、またはMayaが照会できない場合。
        """
        ...
    def getDrawColor(self, *, kind: str = ...) -> tuple[float, float, float, float] | None:
        """DAGノードの描画色を、選択の状態ごとに取得する。

        API 1.0のMFnDagNodeが返す色。ビューポートや表示状態によって値が変わり、
        GUIのない環境では黒を返す場合がある。描画更新を強制せず、表示設定は変更しない。

        Args:
            kind (str): どの状態の色か。既定は ``"dormant"``。

                - ``"dormant"``: 選択していないときの色。
                - ``"active"``: 選択しているときの色。
                - ``"hilite"``: ハイライトのときの色。
                - ``"override"``: このDAGパスに適用される描画オーバーライドの色。自身のoverrideColorを直接読む
                  :meth:`getColor` とは違い、MFnDagNodeの描画の照会を使う。

        Returns:
            tuple[float, float, float, float] | None: RGBAの独立した値。
                ``kind="override"`` で色のオーバーライドが無い場合だけNone。

        Raises:
            TypeError: kindがstrでない場合。
            ValueError: kindが対応していない名前の場合。
        """
        ...
    def getColor(self, *, outliner: bool = ..., toShape: bool = ...) -> int | tuple[float, float, float] | None:
        """表示色(描画のオーバーライドの色、またはアウトライナーの文字色)を取得する。

        既定では、Transformでも直下のShapeは読まず、自身のアトリビュートを読む。

        Args:
            outliner (bool): Trueならアウトライナーの文字色、既定のFalseなら描画のオーバーライドの表示色。
            toShape (bool): Trueなら、直下のShapeのうち中間オブジェクトでない最初のものを読む
                (Shapeが無ければ自身)。Falseなら自身を読む。既定はFalse。

        Returns:
            int | tuple[float, float, float] | None: 描画のオーバーライドでは、``overrideEnabled`` が無効ならNone、
                ``overrideRGBColors`` が有効なら (r, g, b)、それ以外はカラー番号(0は既定色)。
                アウトライナーでは (r, g, b)、``useOutlinerColor`` が無効ならNone。

        Raises:
            TypeError: outliner・toShapeがbool以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setColor(self, color: int | Sequence[float] | None, *, outliner: bool = ..., toShape: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """表示色(描画のオーバーライドの色、またはアウトライナーの文字色)を設定する。

        既定(``outliner=False``)は描画のオーバーライドの表示色で、``overrideEnabled`` を有効にしてから、
        指定に応じて次のように設定する。

        - カラー番号: ``overrideRGBColors`` を無効にして ``overrideColor`` を設定する。
        - RGB: ``overrideRGBColors`` を有効にして ``overrideColorRGB`` を設定する。
        - ``None``: ``overrideEnabled`` を無効にする。表示タイプなど、ほかのオーバーライドも効かなくなる。

        ``outliner=True`` はアウトライナーの文字色で、``useOutlinerColor`` を有効にして ``outlinerColor`` を設定する
        (``None`` なら ``useOutlinerColor`` を無効にする)。``outlinerColor`` はRGBしか持たないため、
        カラー番号は指定した時点のRGBに直して書き込む。GUIのないMayaでは現在のパレットを読めないため、Maya標準のパレットを使う。

        TransformやJointでも、直下のShapeではなく自身へ設定する。Mayaの描画のオーバーライドと同じく、
        Transformへの設定は子の階層全体に効く。``toShape=True`` なら、直下のShape(中間オブジェクトを除く)
        すべてへ設定する(Shapeが無ければ自身)。

        通常は ``cmds.setAttr`` で書き込み、1回のUndoにまとめる。途中で失敗したら元に戻す。
        ``fast=True`` なら、対象のアトリビュートすべてに書き込めるかを先に調べてからOpenMayaで書き込み、
        Undoには記録しない。

        Args:
            color (int | Sequence[float] | None): 表示色。カラー番号(0〜31。0は既定色)、
                0〜1の有限な数値3個の (r, g, b)、または無効にするNone。RGBは表示色の値で、色空間の変換はしない。
            outliner (bool): Trueならアウトライナーの文字色、既定のFalseなら描画のオーバーライドの表示色を設定する。
            toShape (bool): Trueなら直下のShape(中間オブジェクトを除く)へ設定する(Shapeが無ければ自身)。
                Falseなら自身へ設定する。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: colorがint・3個の数値の列・Noneのどれでもない場合(boolを含む)、
                またはoutliner・toShape・fast・checkがbool以外の場合。
            ValueError: 番号が0〜31の範囲外の場合、またはRGBの成分が3個でないか、0〜1の範囲外の場合。
            RuntimeError: ノードが無効な場合、またはロックや入力接続のためにMayaが設定を拒否した場合。
        """
        ...
    def getVisibility(self) -> bool:
        """自身のvisibilityアトリビュートの値を取得する。

        親や表示レイヤーの設定は含めない。実際に表示されているかは :meth:`isVisible` で調べる。

        Returns:
            bool: 自身のvisibilityアトリビュートの値。
        """
        ...
    def setVisibility(self, state: bool = ..., *, fast: bool = ..., check: bool = ...) -> None:
        """visibilityを設定する。

        自身のvisibilityだけを変える。親や表示レイヤーの表示設定は変えない。

        Args:
            state (bool): visibilityへ設定する値。既定はTrue。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: state・fastがbool以外の場合。
            RuntimeError: ノードが無効な場合、またはvisibilityがロックや入力接続のために書き込めない場合。

        Note:
            ``fast=True`` ならOpenMayaで直接書き込み、Undoには記録しない。既定の ``False`` なら通常の処理になる。
            直接書き込んだ値は、あとで自動では戻さない。
        """
        ...
    def getDisplayType(self) -> str:
        """描画のオーバーライドの表示の種類を取得する。

        自身の ``overrideEnabled``・``overrideDisplayType`` を読む。Transformでも直下のShapeは読まない
        (:meth:`setDisplayType` と同じ対象)。表示レイヤーの設定は含めない。

        Returns:
            str: ``"normal"``・``"template"``・``"reference"``。``overrideEnabled`` が無効なら ``"normal"``。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setDisplayType(self, kind: str, *, fast: bool = ..., check: bool = ...) -> None:
        """描画のオーバーライドで表示の種類を設定する。

        表示の種類は通常・テンプレート・リファレンスの3つ。

        - ``"template"``・``"reference"``: ``overrideEnabled`` を有効にして ``overrideDisplayType`` を設定する。
        - ``"normal"``: ``overrideDisplayType`` を0へ戻すだけで、``overrideEnabled`` は変えない。
          表示色など、ほかのオーバーライドを残すため。

        Transformでも、直下のShapeではなく自身へ設定する。Mayaの描画のオーバーライドと同じく、
        Transformへの設定は子の階層全体に効く。

        通常は ``cmds.setAttr`` で書き込み、1回のUndoにまとめる。途中で失敗したら元に戻す。
        ``fast=True`` なら、対象のアトリビュートすべてに書き込めるかを先に調べてからOpenMayaで書き込み、
        Undoには記録しない。

        Args:
            kind (str): ``"normal"``・``"template"``・``"reference"`` のどれか。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: kindが文字列以外の場合、またはfast・checkがbool以外の場合。
            ValueError: kindが対応していない名前の場合。
            RuntimeError: ノードが無効な場合、またはロックや入力接続のためにMayaが設定を拒否した場合。
        """
        ...
    def setShadingOverride(self, state: bool = ..., *, fast: bool = ..., check: bool = ...) -> None:
        """描画のオーバーライドで、ワイヤーフレーム表示にするかを設定する。

        - ``state=True``: ``overrideEnabled`` を有効にして、``overrideShading`` をFalse(ワイヤーフレーム)にする。
        - ``state=False``: ``overrideShading`` をTrue(Mayaの既定のシェーディングあり)へ戻すだけで、
          ``overrideEnabled`` は変えない。

        boolの向きはMayaの ``overrideShading`` と逆(Trueでシェーディングを上書きする)。
        対象・Undo・fastの扱いは :meth:`setDisplayType` と同じ。

        Args:
            state (bool): Trueならシェーディングを消してワイヤーフレーム表示にする。Falseなら元に戻す。既定はTrue。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: state・fast・checkがbool以外の場合。
            RuntimeError: ノードが無効な場合、またはロックや入力接続のためにMayaが設定を拒否した場合。
        """
        ...
    def deleteHistory(self, *, keepDeformers: bool = ...) -> None:
        """ヒストリを削除する。

        消し方はkeepDeformersで選ぶ。

        - ``keepDeformers=True``: ``cmds.bakePartialHistory(prePostDeformers=True)`` を使う。
          デフォーマー(skinCluster・blendShape・clusterなど)は残し、それ以外のヒストリ
          (polySmoothなどのモデリングのヒストリ)だけを形状へ焼き込んで消す。
        - ``keepDeformers=False``: ``cmds.delete(constructionHistory=True)`` を使う。
          デフォーマーを含むすべてのヒストリを消す。形状は、いまの変形結果のまま残る。

        Mayaのコマンドと同じく、Transformから呼ぶと直下のShapeのヒストリが対象になる。
        Shapeを持たないTransform(グループなど)で ``keepDeformers=True`` なら、消すヒストリが無いため何もしない。
        OpenMayaには同じ機能が無いため、fast引数は持たない。Undoが有効なら1回で戻せる。

        Args:
            keepDeformers (bool): Trueならデフォーマーを残す。既定はTrue。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: keepDeformersがbool以外の場合。
            RuntimeError: ノードが無効な場合、またはMayaが削除を拒否した場合。
        """
        ...
    def _instance_parents(self, indirect: bool) -> Nodes[Transform]:
        """インスタンスの直接の親をすべて返す(``getParent(instances=True)`` の本体)。

        Args:
            indirect (bool): Trueなら、getInstances()が返すパスごとに、その親を返す。

        Returns:
            Nodes[Transform]: 親のオブジェクト。ワールド直下なら空の集まり。
        """
        ...
    def _api1_path(self):
        """保持するインスタンスの完全パスをAPI 1.0のMDagPathとして解決する。"""
        ...
    def _collect_children(self, shapes: bool, intermediates: bool, all_descendents: bool, order: str, leaves: bool, include_self: bool, under_world: bool) -> list[DagNode]:
        """子や子孫をたどって集める(:meth:`getChildren` の本体)。

        引数は確かめ済みのものを受け取る。

        Args:
            shapes (bool): TrueならShapeも含める。
            intermediates (bool): Trueなら中間オブジェクトも含める。
            all_descendents (bool): Trueなら子孫すべてを調べる。
            order (str): たどる順。depthFirstまたはbreadthFirst。
            leaves (bool): Trueなら、子にTransformを持たないTransformだけを返す。
            include_self (bool): Trueなら自身も対象にする。
            under_world (bool): Trueならアンダーワールドも調べる。

        Returns:
            list[DagNode]: たどった順のオブジェクト。
        """
        ...
    def _set_display_values(self, values: list[tuple[str, object]], chunk: str, fast: bool, shape: bool = ..., *, check: bool = ...) -> None:
        """表示のアトリビュートへ値を書き込む(:meth:`setColor`・:meth:`setDisplayType` などの本体)。

        fastでcheck=Trueなら、一部のアトリビュートだけが変わってしまうのを避けるため、すべてのアトリビュート
        (コンパウンドアトリビュートは子も)に書き込めるかを先に調べてから書き込む。

        Args:
            values (list[tuple[str, object]]): アトリビュート名と値の組を、書き込む順に並べたもの。
            chunk (str): 通常の処理で使うUndoチャンクの名前。
            fast (bool): 確かめ済みのfast。TrueはUndoなしのOpenMaya更新。
            shape (bool): 確かめ済みのshape。Trueなら直下のShapeへ書き込む。
            check (bool): Trueなら、fastで書き込む前に、書き込めるかを確かめる。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: checkがboolでない場合。
            RuntimeError: ノードが無効な場合、またはロックや入力接続のために書き込めない場合。
        """
        ...
    def _color_targets(self, shape: bool) -> list[DagNode]:
        """表示色を読み書きするノードを返す。

        DagNodeでは ``shape`` にかかわらず自身だけを返す。

        Args:
            shape (bool): 確かめ済みのshape。

        Returns:
            list[DagNode]: 対象のノード。
        """
        ...
    def _require_mnode(self) -> om2.MObject:
        """このオブジェクトが持つMObjectを返す。

        :meth:`mnode` と同じ値を返し、Noneでないことを確かめる。
        作るときにノードが見つからなければ例外になるので、作られたオブジェクトは必ずMObjectを持っている。

        Returns:
            om2.MObject: 持っているMObjectそのもの(コピーではない)。
        """
        ...
    @staticmethod
    def _world_assemblies() -> list[DagNode]:
        """ワールド直下のTransformをすべて取得する。

        Returns:
            list[DagNode]: ワールド直下(DAGパスの長さが1)のTransformのオブジェクト。
        """
        ...
    def _sibling_position(self) -> tuple[int, int]:
        """親の直接の子の中での順番と、子の数を返す。

        このオブジェクトが持つDAGパスが、親の直接の子の何番目にあるかを調べる。

        Returns:
            tuple[int, int]: (0 始まりの番号, 子の数)。

        Raises:
            RuntimeError: 並びの中にこのオブジェクトのパスが見つからない場合(アンダーワールドのノードなど)。
        """
        ...
    def _direct_children(self, shapes: bool, intermediates: bool, shapes_only: bool = ...) -> list[DagNode]:
        """直接の子をOpenMayaで取得する。

        子のパスは、このオブジェクトが持つDAGパスの下へつなげて作る。そのため、インスタンスの
        どの親の下をたどったかが保たれる。

        Args:
            shapes (bool): TrueならShapeも含める。
            intermediates (bool): Trueなら中間オブジェクトも含める。
            shapes_only (bool): TrueならShapeだけを返す(Transformなどはオブジェクトを作らずに除く)。

        Returns:
            list[DagNode]: 条件に合う直接の子。Transformでなければ空リスト。
        """
        ...
    def _traversal_children(self, shapes, intermediates, under_world):
        """次にたどる子のパスを取得する。

        Args:
            shapes: TrueならShapeも含める。
            intermediates: Trueなら中間オブジェクトも含める。
            under_world: Trueなら、Shapeの下のアンダーワールドも調べる。
        """
        ...

def _override_color_writes(color: int | Sequence[float] | None) -> list[tuple[str, object]]:
    """``DagNode.setColor()`` で書き込むアトリビュートと値を返す。

    Args:
        color (int | Sequence[float] | None): :meth:`DagNode.setColor` と同じ。

    Returns:
        list[tuple[str, object]]: アトリビュート名と値の組を、書き込む順に並べたもの。

    Raises:
        TypeError: colorがint・3個の数値の列・Noneのどれでもない場合。
        ValueError: 番号やRGBの成分が範囲外の場合。
    """
    ...

def _outliner_color_writes(color: int | Sequence[float] | None) -> list[tuple[str, object]]:
    """``DagNode.setColor(outliner=True)`` で書き込むアトリビュートと値を返す。

    Args:
        color (int | Sequence[float] | None): :meth:`DagNode.setColor` と同じ。

    Returns:
        list[tuple[str, object]]: アトリビュート名と値の組を、書き込む順に並べたもの。

    Raises:
        TypeError: colorがint・3個の数値の列・Noneのどれでもない場合。
        ValueError: 番号やRGBの成分が範囲外の場合。
    """
    ...

def _palette_color(index: int) -> tuple[float, float, float]:
    """カラー番号のRGBを返す。

    Args:
        index (int): 0〜31のカラー番号。

    Returns:
        tuple[float, float, float]: RGB。
    """
    ...
