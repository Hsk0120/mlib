# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""TransformとShapeに共通するDAG階層へのアクセスを提供する。"""

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds
from ..core.fastWrite import require_writable, set_plug
from ..core.registry import _inherited_node_types, _real_node_type
from ..decorator import _edit_context, _pick_alias, _require_bool, undoChunk, undoTransaction
from ..maths import Vector
from ..util import _UNSET, _color_value, _world_space
from .node import Node
from typing import Iterable, Sequence
from mlib.nodes.dagPose import DagPose
from mlib.nodes.skinCluster import SkinCluster
from mlib.nodes.transform import Transform

_DEFAULT_COLOR_PALETTE: tuple
_DISPLAY_TYPES: tuple

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
    def getSkinClusters(self) -> list[SkinCluster]:
        """このノードのジオメトリを変形しているSkinClusterを取得する。

        Shapeから呼ぶと自身を、Transformから呼ぶと直下のShape(中間オブジェクトを除く)を調べる。
        子のTransformより下は調べない。

        ヒストリを上流へたどり、出力先がそのShapeになっているSkinClusterだけを返す。
        途中でつながっている別の形状のSkinClusterは含まない。
        メッシュ・NURBSなどShapeの種類を問わず使え、シーンとUndoの記録は変更しない。
        Jointの同名メソッドは意味が違い、そのジョイントをインフルエンスに持つSkinClusterを返す。

        Returns:
            list[SkinCluster]: 見つかったSkinCluster。Shapeの順に、Shapeごとに近いものから並ぶ。
                同じものは1回だけ含む。見つからなければ空リスト。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合、またはMayaの検索が失敗した場合。
        """
        ...
    def getBindPoses(self) -> list[DagPose]:
        """このノードに関係するSkinClusterのバインドポーズを取得する。

        対象のSkinClusterはgetSkinClusters()と同じ。ShapeとTransformでは自身を変形しているもの、
        Jointでは自身をインフルエンスに持つものになる。

        SkinClusterの順に並べる。複数のSkinClusterが同じポーズを共有していれば1回だけ含め、
        バインドポーズが接続されていないSkinClusterは飛ばす。

        Returns:
            list[DagPose]: 接続されているバインドポーズ。1つもなければ空リスト。

        Raises:
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
    def getSiblings(self) -> list[DagNode]:
        """同じ親の下にある、同じ種類の兄弟を取得する。

        自身と、自身のほかのインスタンスは含まない。並びはDAGの子の順。

        - Transformなら、親の直下にあるほかのTransformを返す。
        - Shapeなら、親の直下にあるほかのShape(中間オブジェクトを除く)を返す。
        - ワールド直下のTransformなら、ほかのワールド直下のTransformを返す。

        Returns:
            list[DagNode]: 兄弟のオブジェクト。ノードが無効な場合と、兄弟がない場合は空リスト。

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
    def setOutlinerOrder(self, index: int) -> DagNode:
        """アウトライナーでの並び順を、指定した番号へ変える。

        親の直接の子の中での順番を変える。番号の数え方は :meth:`getOutlinerOrder` と同じ。
        ほかの子は、互いの順番を保ったまま詰める。
        変えるのは、このオブジェクトが持つDAGパスの親の下だけ。インスタンスのほかの親の下の順番は変えない。
        OpenMayaには子の順番を変える機能が無いため、fast引数は持たない。Undoが有効なら1回で戻せる。

        Args:
            index (int): 移動先の番号(0 始まり)。負の値は後ろから数える(-1 は最後)。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: index が int でない場合。
            IndexError: index が範囲外の場合。
            RuntimeError: ノードが無効な場合、またはMayaが拒否した場合(ロックされたノードなど)。

        Examples:
            >>> node.setOutlinerOrder(0)     # 先頭へ
            >>> node.setOutlinerOrder(-1)    # 最後へ
        """
        ...
    def reorder(self, *, front: bool = ..., f: bool = ..., back: bool = ..., b: bool = ..., relative: int = ..., r: int = ...) -> DagNode:
        """アウトライナーでの並び順を変える(``cmds.reorder`` 相当)。

        親の直接の子の中での順番を変える。``front``・``back``・``relative`` のどれか1つを指定する。
        ほかの子は、互いの順番を保つ。
        並びの数え方は :meth:`getOutlinerOrder` と同じ。変えるのは、このオブジェクトが持つDAGパスの親の下だけ。
        ``relative`` は端を越えると反対側へ回る(最後の子に 1 を指定すると先頭になる)。
        端で止めたいときや、番号で指定したいときは :meth:`setOutlinerOrder` を使う。
        OpenMayaには子の順番を変える機能が無いため、fast引数は持たない。Undoが有効なら1回で戻せる。

        Args:
            front (bool): Trueなら先頭へ移動する。
            f (bool): frontの別名。frontと同時には指定できない。
            back (bool): Trueなら最後へ移動する。
            b (bool): backの別名。backと同時には指定できない。
            relative (int): 移動する数。正の値は後ろへ、負の値は前へ動かす。
            r (int): relativeの別名。relativeと同時には指定できない。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: 長い名前と短い名前を同時に指定した場合、front・back が bool でない場合、relative が
                int でない場合、または front・back・relative のちょうど1つを指定していない場合。
            RuntimeError: ノードが無効な場合、またはMayaが拒否した場合(ロックされたノードなど)。

        Examples:
            >>> node.reorder(front=True)     # 先頭へ
            >>> node.reorder(back=True)      # 最後へ
            >>> node.reorder(relative=-1)    # 1つ前へ
        """
        ...
    def getBoundingBox(self, worldSpace: bool = ..., *, ws: bool = ...) -> om2.MBoundingBox:
        """バウンディングボックスを取得する。

        既定では ``MFnDagNode.boundingBox`` の値を返す。これは自身のtranslate・rotate・scale
        (Transformの場合)を含むが、親から受け継いだ変換は含まない(``cmds.xform(-boundingBox)`` と同じ)。
        ``worldSpace=True`` なら、そこへこのオブジェクトが持つDAGパスの ``exclusiveMatrix``
        (親までのワールドマトリクス)をかけ、ワールド空間のボックスを返す。
        Shapeでは、自身のローカルの形状から計算する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseなら親の変換を含まない空間。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            om2.MBoundingBox: 軸に沿ったボックス。単位はMaya APIの内部の距離単位。
                子のShapeが無いTransformでは、原点だけを含む、ほぼ空のボックスになる。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: ノードが無効な場合、または保持するDAGパスが無効な場合。
        """
        ...
    def getBoundingBoxCorners(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """バウンディングボックスの8つの隅の点を取得する。

        :meth:`getBoundingBox` が返す、軸に沿ったボックスの隅を返す。
        ワールド空間を指定しても、ワールドの軸に沿ったボックス(``getBoundingBox(worldSpace=True)``)の隅になる。
        ノードの向きに合わせて回したボックスの隅ではない。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseなら親の変換を含まない空間(:meth:`getBoundingBox` と同じ)。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[Vector]: cm単位の8点。X・Y・Zの順に、最小と最大を組み合わせた順に並ぶ
                ((minX, minY, minZ), (minX, minY, maxZ), (minX, maxY, minZ), ..., (maxX, maxY, maxZ))。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: ノードが無効な場合、または保持するDAGパスが無効な場合。

        Examples:
            >>> corners = node.getBoundingBoxCorners(ws=True)
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
    def getInstances(self, noSelf: bool = ...) -> list[DagNode]:
        """同じノードへのDAGパス(インスタンス)をすべて取得する。

        すでにあるパスを調べるだけで、ノードを複製したり、インスタンスを新しく作ったりはしない。
        親がインスタンス化されたことで生じたパス(間接的なインスタンス)も含む。

        Args:
            noSelf (bool): Trueなら、このオブジェクトが持つパスを結果から除く。既定はFalse。

        Returns:
            list[DagNode]: パスごとのオブジェクト。順番はMaya APIが列挙する順。
                このオブジェクトが持つパスには自身を、ほかのパスには新しいオブジェクトを入れる。

        Raises:
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
    def getParents(self, indirect: bool = ...) -> list[Transform]:
        """直接の親をすべて取得する。

        インスタンス化されたノードには親が複数ある。そのすべてを返す。
        親の親など、さらに上の祖先は含まない。

        Args:
            indirect (bool): 親の数え方を選ぶ。既定はFalse。

                - False: 親のノードごとに1つ返す。順番はMaya APIの親の順。
                  このオブジェクトが持つパスの親にはそのパスを使い、ほかの親にはMaya APIが返すパスを1つ使う。
                - True: getInstances()が返すパスごとに、その親を返す。
                  親がインスタンス化されたことで生じたパスの分も含む。

        Returns:
            list[Transform]: 親のオブジェクト。同じ親が重なってもまとめない。
                DAGの親は必ずTransform系(Jointなど)になる。
                このオブジェクトが持つパスがワールド直下なら空リスト。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        ...
    def getParent(self, step: int = ...) -> Transform | None:
        """親を取得する。

        このオブジェクトが持つDAGパスを、上へたどって求める。

        Args:
            step (int): 何階層上の親を取得するか。1は直接の親、2は親の親。既定は1。

        Returns:
            Transform | None: 親の新しいオブジェクト。DAGの親は必ずTransform系(Jointなど)になる。
                stepが0以下の場合と、ワールドまで(それより上へ)たどる場合はNone。

        Raises:
            RuntimeError: stepが正で、保持するDAGパスが無効な場合。
        """
        ...
    def getChildren(self, shapes: bool = ..., intermediates: bool = ..., *, allDescendents: bool = ..., order: str = ..., leaves: bool = ..., includeSelf: bool = ..., underWorld: bool = ..., type: str | Iterable[str] | None = ...) -> list[DagNode]:
        """子、または子孫を取得する。

        このオブジェクトが持つDAGパスから下へたどる。結果のパスは、たどった道筋のまま作り、
        名前から探し直さない。そのため、同じノードが複数のパスで見つかれば、パスごとに結果へ入る。

        Args:
            shapes (bool): TrueならShapeも含める。既定はFalse(Transformだけ)。
            intermediates (bool): Trueなら中間オブジェクトも含める。既定はFalse。
                含めなかった中間オブジェクトの下は調べない。
            allDescendents (bool): Trueなら子孫すべて、Falseなら直接の子だけを取得する。既定はFalse。
            order (str): 並べる順。``"depthFirst"`` (深さ優先。既定)か ``"breadthFirst"`` (幅優先)。
                兄弟どうしはDAGの子の順に並ぶ。
            leaves (bool): Trueなら、末端のTransform(子にTransformを持たないもの)を、下の階層まで
                たどって取得する。Shapeを持っていても末端として扱う。shapes=Trueとは同時に指定できない。
            includeSelf (bool): Trueなら自身も対象にする。shapes・leavesの条件に合えば、
                自身(同じオブジェクト)を結果へ入れる。
            underWorld (bool): Trueなら、Shapeの下のアンダーワールドも調べる。
            type (str | Iterable[str] | None): 結果をMayaのノード型で絞る。``cmds.listRelatives(type=)`` と同じく、
                指定した型から派生した型も含む(:meth:`~mlib.nodes.node.Node.isType` で判定する)。
                絞るのは結果だけで、たどる範囲は変わらない。``allDescendents=True`` では、型の違う子の下も調べる。
                Shapeの型(``"mesh"`` など)を指定した場合は、shapes=FalseでもShapeを含めて調べる。
                ``multDoubleLinear`` と ``multDL`` のように、Mayaの版で名前が変わった型はどちらの名前でも指定できる。

        Returns:
            list[DagNode]: たどった順のオブジェクト。該当するものがない場合と、
                ノードそのものが無効な場合は空リスト。

        Raises:
            TypeError: allDescendents・leaves・includeSelf・underWorldがboolでない場合、
                またはtypeが文字列・文字列の並び・Noneのどれでもない場合。
            ValueError: orderが不正な場合、leavesとshapesを同時に指定した場合、
                またはtypeに空文字列を指定した場合。
            RuntimeError: ノードは有効だが、保持するDAGパスが無効な場合。
        """
        ...
    def getShape(self, index: int = ..., intermediates: bool = ...) -> DagNode | None:
        """Shapeを取得する。

        ノードの種類によって次のように返す。

        - Shapeなら、``index``・``intermediates`` を無視して自身を返す。
        - Transformなら、派生クラス(Transform.getShape)が、直下のShapeのうち ``index`` 番目
          (0 始まり)を返す。範囲外ならNone。
        - それ以外のDAGノードならNone。

        範囲外のindexでもIndexErrorにはしない。

        Args:
            index (int): Transformで、何番目のShapeを選ぶか。Shapeでは無視する。既定は0。
            intermediates (bool): Trueなら、Transformで中間オブジェクトも候補に含める。Shapeでは無視する。

        Returns:
            DagNode | None: Shapeなら自身、Transformなら選んだShape。当てはまるものがなければNone。

        Raises:
            RuntimeError: ノードが破棄されている場合。
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
    def show(self, *, fast: bool = ...) -> DagNode:
        """表示する。

        visibilityをTrueにして自身を返す。``setVisibility(True, fast=fast)`` と同じ。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
        """
        ...
    def hide(self, *, fast: bool = ...) -> DagNode:
        """非表示にする。

        visibilityをFalseにして自身を返す。``setVisibility(False, fast=fast)`` と同じ。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
        """
        ...
    def getOverrideColor(self, *, shape: bool = ...) -> int | tuple[float, float, float] | None:
        """描画のオーバーライドの表示色を取得する。

        既定では、Transformでも直下のShapeは読まず、自身のアトリビュートを読む。

        Args:
            shape (bool): Trueなら、直下のShapeのうち中間オブジェクトでない最初のものを読む
                (Shapeが無ければ自身)。Falseなら自身を読む。既定はFalse。

        Returns:
            int | tuple[float, float, float] | None: ``overrideEnabled`` が無効ならNone。
                ``overrideRGBColors`` が有効なら (r, g, b)。それ以外はカラー番号(0は既定色)。

        Raises:
            TypeError: shapeがbool以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setOverrideColor(self, color: int | Sequence[float] | None, *, shape: bool = ..., fast: bool = ...) -> DagNode:
        """描画のオーバーライドで表示色を設定する。

        ``overrideEnabled`` を有効にしてから、指定に応じて次のように設定し、自身を返す。

        - カラー番号: ``overrideRGBColors`` を無効にして ``overrideColor`` を設定する。
        - RGB: ``overrideRGBColors`` を有効にして ``overrideColorRGB`` を設定する。
        - ``None``: ``overrideEnabled`` を無効にする。表示タイプなど、ほかのオーバーライドも効かなくなる。

        TransformやJointでも、直下のShapeではなく自身へ設定する。Mayaの描画のオーバーライドと同じく、
        Transformへの設定は子の階層全体に効く。``shape=True`` なら、直下のShape(中間オブジェクトを除く)
        すべてへ設定する(Shapeが無ければ自身)。

        通常は ``cmds.setAttr`` で書き込み、1回のUndoにまとめる。途中で失敗したら元に戻す。
        ``fast=True`` なら、対象のアトリビュートすべてに書き込めるかを先に調べてからOpenMayaで書き込み、
        Undoには記録しない。

        Args:
            color (int | Sequence[float] | None): 表示色。カラー番号(0〜31。0は既定色)、
                0〜1の有限な数値3個の (r, g, b)、または無効にするNone。RGBは表示色の値で、色空間の変換はしない。
            shape (bool): Trueなら直下のShape(中間オブジェクトを除く)へ設定する(Shapeが無ければ自身)。
                Falseなら自身へ設定する。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: colorがint・3個の数値の列・Noneのどれでもない場合(boolを含む)、
                またはshape・fastがbool以外の場合。
            ValueError: 番号が0〜31の範囲外の場合、またはRGBの成分が3個でないか、0〜1の範囲外の場合。
            RuntimeError: ノードが無効な場合、またはロックや入力接続のためにMayaが設定を拒否した場合。
        """
        ...
    def getOutlinerColor(self, *, shape: bool = ...) -> tuple[float, float, float] | None:
        """アウトライナーの文字色を取得する。

        Args:
            shape (bool): Trueなら、直下のShapeのうち中間オブジェクトでない最初のものを読む
                (Shapeが無ければ自身)。Falseなら自身を読む。既定はFalse。

        Returns:
            tuple[float, float, float] | None: (r, g, b)。``useOutlinerColor`` が無効ならNone。

        Raises:
            TypeError: shapeがbool以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setOutlinerColor(self, color: int | Sequence[float] | None, *, shape: bool = ..., fast: bool = ...) -> DagNode:
        """アウトライナーの文字色を設定する。

        ``useOutlinerColor`` を有効にして ``outlinerColor`` を設定し、自身を返す。
        ``None`` なら ``useOutlinerColor`` を無効にする。
        既定では、TransformやJointでも直下のShapeではなく自身へ設定する。

        ``outlinerColor`` はRGBしか持たないため、カラー番号は指定した時点のRGBに直して書き込む。
        GUIのないMayaでは現在のパレットを読めないため、Maya標準のパレットを使う。

        Args:
            color (int | Sequence[float] | None): 文字色。カラー番号(0〜31)、0〜1の有限な数値3個の (r, g, b)、
                または無効にするNone。
            shape (bool): Trueなら直下のShape(中間オブジェクトを除く)へ設定する(Shapeが無ければ自身)。
                Falseなら自身へ設定する。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: colorがint・3個の数値の列・Noneのどれでもない場合(boolを含む)、
                またはshape・fastがbool以外の場合。
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
    def setVisibility(self, state: bool, *, fast: bool = ...) -> DagNode:
        """visibilityを設定する。

        自身のvisibilityだけを変える。親や表示レイヤーの表示設定は変えない。

        Args:
            state (bool): visibilityへ設定する値。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: state・fastがbool以外の場合。
            RuntimeError: ノードが無効な場合、またはvisibilityがロックや入力接続のために書き込めない場合。

        Note:
            ``fast=True`` ならOpenMayaで直接書き込み、Undoには記録しない。既定の ``False`` なら通常の処理になる。
            直接書き込んだ値は、あとで自動では戻さない。
        """
        ...
    def getOutlinerVisibility(self) -> bool:
        """アウトライナーに表示する設定になっているかを取得する。

        Returns:
            bool: hiddenInOutlinerがFalseならTrue。画面に実際に見えているかどうかではない。

        Raises:
            RuntimeError: ノードが無効な場合。

        Note:
            エディターのフィルター、親が折り畳まれているか、非表示のノードを表示する設定は調べない。
        """
        ...
    def setOutlinerVisibility(self, state: bool, *, fast: bool = ...) -> DagNode:
        """アウトライナーに表示するかを設定する。

        Args:
            state (bool): Trueなら表示、Falseなら非表示。hiddenInOutlinerには逆の値を書き込む。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。DagNodes・Transforms・Jointsから、まとめて呼ぶこともできる。

        Raises:
            TypeError: stateまたはfastがbool以外の場合。
            AttributeError: 対応するアトリビュートがない場合。
            RuntimeError: ロックや入力接続などのために書き込めない場合。

        Note:
            ビューポートのvisibilityは変えない。実際にアウトライナーに出るかは、
            各アウトライナーのフィルターや、非表示のノードを表示する設定によっても変わる。
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
    def setDisplayType(self, kind: str, *, fast: bool = ...) -> DagNode:
        """描画のオーバーライドで表示の種類を設定する。

        表示の種類は通常・テンプレート・リファレンスの3つ。設定して自身を返す。

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

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: kindが文字列以外の場合、またはfastがbool以外の場合。
            ValueError: kindが対応していない名前の場合。
            RuntimeError: ノードが無効な場合、またはロックや入力接続のためにMayaが設定を拒否した場合。
        """
        ...
    def isShadingOverridden(self) -> bool:
        """描画のオーバーライドで、ワイヤーフレーム表示にしているかを調べる。

        Mayaの ``overrideShading`` は、Trueでシェーディングあり(既定)、Falseでワイヤーフレームを表す。
        このメソッドはその逆向きで、シェーディングを消しているときにTrueを返す。
        自身のアトリビュートを読む(:meth:`setShadingOverride` と同じ対象)。

        Returns:
            bool: ``overrideEnabled`` が有効で ``overrideShading`` がFalseならTrue。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setShadingOverride(self, enabled: bool, *, fast: bool = ...) -> DagNode:
        """描画のオーバーライドで、ワイヤーフレーム表示にするかを設定する。

        設定して自身を返す。

        - ``enabled=True``: ``overrideEnabled`` を有効にして、``overrideShading`` をFalse(ワイヤーフレーム)にする。
        - ``enabled=False``: ``overrideShading`` をTrue(Mayaの既定のシェーディングあり)へ戻すだけで、
          ``overrideEnabled`` は変えない。

        boolの向きはMayaの ``overrideShading`` と逆で、:meth:`isShadingOverridden` の戻り値と同じ向き。
        対象・Undo・fastの扱いは :meth:`setDisplayType` と同じ。

        Args:
            enabled (bool): Trueならシェーディングを消してワイヤーフレーム表示にする。Falseなら元に戻す。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: enabledまたはfastがbool以外の場合。
            RuntimeError: ノードが無効な場合、またはロックや入力接続のためにMayaが設定を拒否した場合。
        """
        ...
    def deleteHistory(self, keepDeformers: bool = ...) -> DagNode:
        """ヒストリを削除する。

        削除して自身を返す。消し方はkeepDeformersで選ぶ。

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
            DagNode: 自身。

        Raises:
            TypeError: keepDeformersがbool以外の場合。
            RuntimeError: ノードが無効な場合、またはMayaが削除を拒否した場合。
        """
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
    def _set_display_values(self, values: list[tuple[str, object]], chunk: str, fast: bool, shape: bool = ...) -> None:
        """表示のアトリビュートへ値を書き込む(:meth:`setOverrideColor`・:meth:`setDisplayType` などの本体)。

        fastでは、一部のアトリビュートだけが変わってしまうのを避けるため、すべてのアトリビュート
        (コンパウンドアトリビュートは子も)に書き込めるかを先に調べてから書き込む。

        Args:
            values (list[tuple[str, object]]): アトリビュート名と値の組を、書き込む順に並べたもの。
            chunk (str): 通常の処理で使うUndoチャンクの名前。
            fast (bool): 確かめ済みのfast。TrueはUndoなしのOpenMaya更新。
            shape (bool): 確かめ済みのshape。Trueなら直下のShapeへ書き込む。

        Returns:
            None: 値を返さない。

        Raises:
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

def _palette_color(index: int) -> tuple[float, float, float]:
    """カラー番号のRGBを返す。

    Args:
        index (int): 0〜31のカラー番号。

    Returns:
        tuple[float, float, float]: RGB。
    """
    ...
