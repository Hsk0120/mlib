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

#: GUIのないMayaで使う、Maya標準のカラー番号のRGB。
_DEFAULT_COLOR_PALETTE = (
    (0.4699999988079071, 0.4699999988079071, 0.4699999988079071),
    (0.0, 0.0, 0.0),
    (0.25, 0.25, 0.25),
    (0.6000000238418579, 0.6000000238418579, 0.6000000238418579),
    (0.6079999804496765, 0.0, 0.15700000524520874),
    (0.0, 0.01600000075995922, 0.37599998712539673),
    (0.0, 0.0, 1.0),
    (0.0, 0.2750000059604645, 0.09799999743700027),
    (0.14900000393390656, 0.0, 0.2630000114440918),
    (0.7839999794960022, 0.0, 0.7839999794960022),
    (0.5410000085830688, 0.28200000524520874, 0.20000000298023224),
    (0.24699999392032623, 0.13699999451637268, 0.12200000137090683),
    (0.6000000238418579, 0.14900000393390656, 0.0),
    (1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, 0.2549999952316284, 0.6000000238418579),
    (1.0, 1.0, 1.0),
    (1.0, 1.0, 0.0),
    (0.3919999897480011, 0.8629999756813049, 1.0),
    (0.2630000114440918, 1.0, 0.6389999985694885),
    (1.0, 0.6899999976158142, 0.6899999976158142),
    (0.8939999938011169, 0.675000011920929, 0.4749999940395355),
    (1.0, 1.0, 0.3880000114440918),
    (0.0, 0.6000000238418579, 0.32899999618530273),
    (0.8549000024795532, 0.5686299800872803, 0.4274500012397766),
    (0.8784300088882446, 0.784309983253479, 0.30588001012802124),
    (0.6352900266647339, 0.8117600083351135, 0.2784300148487091),
    (0.2313700020313263, 0.7568600177764893, 0.5803899765014648),
    (0.2549000084400177, 0.8196099996566772, 0.7254899740219116),
    (0.22744999825954437, 0.6156899929046631, 0.8078399896621704),
    (0.6117600202560425, 0.41960999369621277, 0.8078399896621704),
    (0.8078399896621704, 0.34902000427246094, 0.6549000144004822),
)

#: overrideDisplayType の値(番号順)と、setDisplayType で指定する名前。
_DISPLAY_TYPES = ("normal", "template", "reference")


def _type_filter(value):
    """getChildren(type=) の指定を、型名のtupleにそろえる。

    Args:
        value (str | Iterable[str] | None): ノード型名、その並び、またはNone。

    Returns:
        tuple[str, ...]: 型名。Noneなら空。

    Raises:
        TypeError: 文字列・文字列の並び・Noneのどれでもない場合。
        ValueError: 空文字列を含む場合。
    """
    if value is None:
        return ()
    names = (value,) if isinstance(value, str) else tuple(value) if isinstance(value, (list, tuple)) else None
    if names is None or not all(isinstance(name, str) for name in names):
        raise TypeError("typeはノード型名か、名前の並びか、Noneで指定してください")
    if not all(names):
        raise ValueError("typeに空のノード型名は指定できません")
    return names


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

    def getSkinClusters(self):
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
        path = self.mpath()
        obj = path.node()
        if obj.hasFn(om2.MFn.kTransform):
            fn = om2.MFnDagNode(path)
            shapes = [fn.child(i) for i in range(fn.childCount()) if fn.child(i).hasFn(om2.MFn.kShape) and not om2.MFnDagNode(fn.child(i)).isIntermediateObject]
        else:
            shapes = [obj] if obj.hasFn(om2.MFn.kShape) else []
        result, seen = [], set()
        for shape in shapes:
            iterator = om2.MItDependencyGraph(
                shape, om2.MFn.kSkinClusterFilter, om2.MItDependencyGraph.kUpstream, om2.MItDependencyGraph.kBreadthFirst, om2.MItDependencyGraph.kNodeLevel
            )
            iterator.pruningOnFilter = False
            while not iterator.isDone():
                skin = iterator.currentNode()
                key = om2.MFnDependencyNode(skin).uuid().asString()
                if key not in seen and any(output == shape for output in oma2.MFnGeometryFilter(skin).getOutputGeometry()):
                    seen.add(key)
                    result.append(Node(skin))
                iterator.next()
        return result

    def getBindPoses(self):
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
        result, seen = [], set()
        for skin in self.getSkinClusters():
            pose = skin.getBindPose()
            if pose is not None:
                key = pose.getUuid()
                if key not in seen:
                    seen.add(key)
                    result.append(pose)
        return result

    def mpath(self):
        """このオブジェクトが持つDAGパスを、OpenMayaのMDagPathとして取得する。

        コピーではなく、内部で持っているMDagPathそのものを返す。pushやpopで書き換えると
        このオブジェクトのパスも変わってしまうので、書き換える前に
        ``om2.MDagPath(node.mpath())`` でコピーを作る。

        Returns:
            om2.MDagPath: 内部で持っているパスと同じオブジェクト。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。ほかのインスタンスのパスへは切り替えない。
        """
        dag_path = self._current_dag_path()
        # DagNode は初期化時に必ず DAG パスを解決して保持する(None は非DAGの Node だけ)。
        assert dag_path is not None
        return dag_path

    def mfn(self):
        """このオブジェクトが持つDAGパスのfunction setを作る。

        呼ぶたびに新しく作って返す。TransformやMeshなどの派生クラスでは、
        それぞれに合った、より具体的なfunction setを返す。

        Returns:
            om2.MFnDagNode: このオブジェクトのfunction set。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        return om2.MFnDagNode(self.mpath())

    def getRoot(self):
        """いちばん上(ワールド直下)の祖先を取得する。

        このオブジェクトが持つDAGパスを、ワールド直下まで上へたどる。
        DAGの親は必ずTransformなので、Shapeから呼んでもTransformが返る。
        自身がワールド直下にあれば自身を返す。

        Returns:
            Transform: ワールド直下の祖先、または自身(ワールド直下に置けるのはTransform系だけ)。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        node = self
        parent = node.getParent()
        while parent is not None:
            node = parent
            parent = node.getParent()
        return node

    def getCommonAncestor(self, other):
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
        other_node = Node._resolve_input(other)
        if not isinstance(other_node, DagNode):
            raise TypeError(f"otherはDAGノードで指定してください: {other_node.getFullName()}")
        self._require_valid("共通の祖先の検索")
        other_node._require_valid("共通の祖先の検索")
        self_path = self.mpath().fullPathName()
        other_path = other_node.mpath().fullPathName()
        other_ancestors = {other_path}
        path = om2.MDagPath(other_node.mpath())
        while path.length() > 1:
            path.pop()
            other_ancestors.add(path.fullPathName())
        if self_path in other_ancestors:
            return self
        path = om2.MDagPath(self.mpath())
        while path.length() > 1:
            path.pop()
            name = path.fullPathName()
            if name == other_path:
                return other_node
            if name in other_ancestors:
                # 有効なDAGパスを上へたどったパスなので、Node(path) の入力解決を省いて同じ型で包む。
                return Node._wrap_dag_path(path)
        return None

    def getSiblings(self):
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
        if not self.isValid():
            return []
        is_shape = self._require_mnode().hasFn(om2.MFn.kShape)
        parent = self.getParent()
        if parent is not None:
            candidates = parent._direct_children(is_shape, False, shapes_only=is_shape)
        elif is_shape:
            candidates = []
        else:
            candidates = DagNode._world_assemblies()
        self_uuid = self.getUuid()
        return [candidate for candidate in candidates if candidate.getUuid() != self_uuid]

    def getOutlinerOrder(self):
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
        self._require_valid("アウトライナーの並び順の取得")
        return self._sibling_position()[0]

    def setOutlinerOrder(self, index):
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
        if isinstance(index, bool) or not isinstance(index, int):
            raise TypeError(f"indexはintで指定してください: {type(index).__name__}")
        with undoChunk("mlibDagNodeSetOutlinerOrder"):
            self._require_valid("並べ替え")
            current, count = self._sibling_position()
            target = index + count if index < 0 else index
            if not 0 <= target < count:
                raise IndexError(f"アウトライナーの並び順が範囲外です: {index}")
            if target != current:
                # 範囲内の relative は循環せず、その数だけ前後へ動く。
                cmds.reorder(self.getFullName(), relative=target - current)
            return self

    def reorder(self, *, front=_UNSET, f=_UNSET, back=_UNSET, b=_UNSET, relative=_UNSET, r=_UNSET):
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
        front = _require_bool(_pick_alias(front, f, "front", "f", default=False), "front")
        back = _require_bool(_pick_alias(back, b, "back", "b", default=False), "back")
        relative = _pick_alias(relative, r, "relative", "r", default=None)
        if relative is not None and (isinstance(relative, bool) or not isinstance(relative, int)):
            raise TypeError(f"relativeはintで指定してください: {type(relative).__name__}")
        if front + back + (relative is not None) != 1:
            raise TypeError("front・back・relativeのどれか1つだけを指定してください")
        if front:
            flags = {"front": True}
        elif back:
            flags = {"back": True}
        else:
            flags = {"relative": relative}
        with undoChunk("mlibDagNodeReorder"):
            self._require_valid("並べ替え")
            cmds.reorder(self.getFullName(), **flags)
            return self

    def getBoundingBox(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        world = _world_space(worldSpace)
        self._require_valid("バウンディングボックスの計算")
        path = self.mpath()
        box = om2.MFnDagNode(path).boundingBox
        if not world:
            return box
        parent_matrix = path.exclusiveMatrix()
        world_box = om2.MBoundingBox()
        for x in (box.min.x, box.max.x):
            for y in (box.min.y, box.max.y):
                for z in (box.min.z, box.max.z):
                    world_box.expand(om2.MPoint(x, y, z) * parent_matrix)
        return world_box

    def getBoundingBoxCorners(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        box = self.getBoundingBox(worldSpace=worldSpace)
        return [Vector(x, y, z) for x in (box.min.x, box.max.x) for y in (box.min.y, box.max.y) for z in (box.min.z, box.max.z)]

    def isIntermediateObject(self):
        """中間オブジェクトかどうかを調べる。

        中間オブジェクトは、ヒストリのために残している非表示のShapeのこと。Transformでは常にFalse。

        Returns:
            bool: 中間オブジェクトならTrue。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        return self.mfn().isIntermediateObject

    def getInstances(self, noSelf=False):
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
        original = self.mpath().fullPathName()
        # APIが列挙した有効なパスの複製なので、Node(...) の入力解決を省いて同じ型で包む。
        return [
            self if path.fullPathName() == original else Node._wrap_dag_path(om2.MDagPath(path))
            for path in om2.MDagPath.getAllPathsTo(self.mnode())
            if not noSelf or path.fullPathName() != original
        ]

    def isInstanced(self):
        """インスタンス化されているか(DAGパスが複数あるか)を調べる。

        親がインスタンス化されたことで生じたパス(間接的なインスタンス)も数える。
        ``len(getInstances()) > 1`` と同じ結果になる。

        Returns:
            bool: パスが2つ以上ならTrue。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        return self.mfn().isInstanced(True)

    def getInstanceIndex(self):
        """インスタンス番号を取得する。

        このオブジェクトが持つDAGパスの ``MDagPath.instanceNumber`` を返す。
        インスタンス化されていないノードでは0。:meth:`getInstances` の結果の並び順と一致するとは限らない。

        Returns:
            int: 0以上のインスタンス番号。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合。
        """
        return self.mpath().instanceNumber()

    def getParents(self, indirect=False):
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
        parent = self.getParent()
        if parent is None:
            return []
        if indirect:
            return [instance.getParent() for instance in self.getInstances() if instance.getParent() is not None]
        fn = self.mfn()
        return [
            parent if fn.parent(index) == parent.mnode() else Node._wrap_dag_path(om2.MDagPath.getAPathTo(fn.parent(index)))
            for index in range(fn.parentCount())
            if not fn.parent(index).hasFn(om2.MFn.kWorld)
        ]

    def getParent(self, step=1):
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
        if step <= 0:
            return None
        path = om2.MDagPath(self.mpath())
        if step >= path.length():
            return None
        path.pop(step)
        # 有効なDAGパスのコピーを上へたどったパスなので、Node(path) の入力解決を省いて同じ型で包む。
        return Node._wrap_dag_path(path)

    def getChildren(
        self, shapes=False, intermediates=False, *, allDescendents=False, order="depthFirst", leaves=False, includeSelf=False, underWorld=False, type=None
    ):
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
        for value, name in ((allDescendents, "allDescendents"), (leaves, "leaves"), (includeSelf, "includeSelf"), (underWorld, "underWorld")):
            _require_bool(value, name)
        if order not in ("depthFirst", "breadthFirst"):
            raise ValueError("orderは'depthFirst'か'breadthFirst'で指定してください")
        if leaves and shapes:
            raise ValueError("leavesはトランスフォームを選ぶ指定のため、shapesと同時に指定できません")
        types = _type_filter(type)
        if types and not leaves and not shapes:
            # Shapeの型で絞る場合は、既定のTransformだけの探索では必ず空になるためShapeも探す。
            shapes = any("shape" in _inherited_node_types(_real_node_type(name)) for name in types)
        if not self.isValid():
            return []
        result = self._collect_children(shapes, intermediates, allDescendents, order, leaves, includeSelf, underWorld)
        if types:
            result = [node for node in result if any(node.isType(name) for name in types)]
        return result

    def getShape(self, index=0, intermediates=False):  # noqa: ARG002  # Shapeでは無視する契約。派生(Transform)が使う。
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
        return self if self._require_mnode().hasFn(om2.MFn.kShape) else None

    def isVisible(self):
        """親の階層まで含めて、表示されているかを調べる。

        このオブジェクトが持つDAGパスで調べ、親のどれかが非表示なら自身も非表示として扱う。

        Returns:
            bool: 親の階層まで含めて表示されていればTrue。

        Raises:
            RuntimeError: 保持するDAGパスが無効な場合(削除済みのノードを含む)。
        """
        return self.mpath().isVisible()

    def show(self, *, fast=False):
        """表示する。

        visibilityをTrueにして自身を返す。``setVisibility(True, fast=fast)`` と同じ。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
        """
        return self.setVisibility(True, fast=fast)

    def hide(self, *, fast=False):
        """非表示にする。

        visibilityをFalseにして自身を返す。``setVisibility(False, fast=fast)`` と同じ。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            DagNode: 自身。

        Raises:
            TypeError: fastがbool以外の場合。
        """
        return self.setVisibility(False, fast=fast)

    def getOverrideColor(self, *, shape=False):
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
        _require_bool(shape, "shape")
        fn = self._color_targets(shape)[0]._dependency_fn()
        if not fn.findPlug("overrideEnabled", False).asBool():
            return None
        if fn.findPlug("overrideRGBColors", False).asBool():
            plug = fn.findPlug("overrideColorRGB", False)
            return tuple(plug.child(index).asFloat() for index in range(3))
        return fn.findPlug("overrideColor", False).asInt()

    def setOverrideColor(self, color, *, shape=False, fast=False):
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
        _require_bool(shape, "shape")
        _require_bool(fast, "fast")
        index, rgb = _color_value(color)
        if index is None and rgb is None:
            values = [("overrideEnabled", False)]
        elif rgb is None:
            values = [("overrideEnabled", True), ("overrideRGBColors", False), ("overrideColor", index)]
        else:
            values = [("overrideEnabled", True), ("overrideRGBColors", True), ("overrideColorRGB", rgb)]
        self._set_display_values(values, "mlibDagNodeSetOverrideColor", fast, shape)
        return self

    def getOutlinerColor(self, *, shape=False):
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
        _require_bool(shape, "shape")
        fn = self._color_targets(shape)[0]._dependency_fn()
        if not fn.findPlug("useOutlinerColor", False).asBool():
            return None
        plug = fn.findPlug("outlinerColor", False)
        return tuple(plug.child(index).asFloat() for index in range(3))

    def setOutlinerColor(self, color, *, shape=False, fast=False):
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
        _require_bool(shape, "shape")
        _require_bool(fast, "fast")
        index, rgb = _color_value(color)
        if index is not None:
            rgb = _palette_color(index)
        values = [("useOutlinerColor", False)] if rgb is None else [("useOutlinerColor", True), ("outlinerColor", rgb)]
        self._set_display_values(values, "mlibDagNodeSetOutlinerColor", fast, shape)
        return self

    def getVisibility(self):
        """自身のvisibilityアトリビュートの値を取得する。

        親や表示レイヤーの設定は含めない。実際に表示されているかは :meth:`isVisible` で調べる。

        Returns:
            bool: 自身のvisibilityアトリビュートの値。
        """
        return bool(self.getPlug("visibility").get())

    def setVisibility(self, state, *, fast=False):
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
        with _edit_context("mlibDagNodeSetVisibility", fast):
            _require_bool(state, "state")
            self.getPlug("visibility").set(state, fast=fast)
            return self

    def getOutlinerVisibility(self):
        """アウトライナーに表示する設定になっているかを取得する。

        Returns:
            bool: hiddenInOutlinerがFalseならTrue。画面に実際に見えているかどうかではない。

        Raises:
            RuntimeError: ノードが無効な場合。

        Note:
            エディターのフィルター、親が折り畳まれているか、非表示のノードを表示する設定は調べない。
        """
        return not bool(self.getPlug("hiddenInOutliner").get())

    def setOutlinerVisibility(self, state, *, fast=False):
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
        with _edit_context("mlibDagNodeSetOutlinerVisibility", fast):
            _require_bool(state, "state")
            self.getPlug("hiddenInOutliner").set(not state, fast=fast)
            return self

    def getDisplayType(self):
        """描画のオーバーライドの表示の種類を取得する。

        自身の ``overrideEnabled``・``overrideDisplayType`` を読む。Transformでも直下のShapeは読まない
        (:meth:`setDisplayType` と同じ対象)。表示レイヤーの設定は含めない。

        Returns:
            str: ``"normal"``・``"template"``・``"reference"``。``overrideEnabled`` が無効なら ``"normal"``。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("表示タイプの取得")
        fn = self._dependency_fn()
        if not fn.findPlug("overrideEnabled", False).asBool():
            return "normal"
        return _DISPLAY_TYPES[fn.findPlug("overrideDisplayType", False).asInt()]

    def setDisplayType(self, kind, *, fast=False):
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
        _require_bool(fast, "fast")
        if not isinstance(kind, str):
            raise TypeError("kindは'normal'・'template'・'reference'のどれかで指定してください")
        if kind not in _DISPLAY_TYPES:
            raise ValueError(f"kindは{', '.join(map(repr, _DISPLAY_TYPES))}のどれかで指定してください: {kind!r}")
        index = _DISPLAY_TYPES.index(kind)
        values = [("overrideDisplayType", index)] if index == 0 else [("overrideEnabled", True), ("overrideDisplayType", index)]
        self._set_display_values(values, "mlibDagNodeSetDisplayType", fast)
        return self

    def isShadingOverridden(self):
        """描画のオーバーライドで、ワイヤーフレーム表示にしているかを調べる。

        Mayaの ``overrideShading`` は、Trueでシェーディングあり(既定)、Falseでワイヤーフレームを表す。
        このメソッドはその逆向きで、シェーディングを消しているときにTrueを返す。
        自身のアトリビュートを読む(:meth:`setShadingOverride` と同じ対象)。

        Returns:
            bool: ``overrideEnabled`` が有効で ``overrideShading`` がFalseならTrue。

        Raises:
            RuntimeError: ノードが無効な場合。
        """
        self._require_valid("シェーディングのオーバーライドの取得")
        fn = self._dependency_fn()
        return fn.findPlug("overrideEnabled", False).asBool() and not fn.findPlug("overrideShading", False).asBool()

    def setShadingOverride(self, enabled, *, fast=False):
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
        _require_bool(fast, "fast")
        _require_bool(enabled, "enabled")
        values = [("overrideEnabled", True), ("overrideShading", False)] if enabled else [("overrideShading", True)]
        self._set_display_values(values, "mlibDagNodeSetShadingOverride", fast)
        return self

    def deleteHistory(self, keepDeformers=True):
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
        _require_bool(keepDeformers, "keepDeformers")
        self._require_valid("ヒストリの削除")
        name = self.getFullName()
        if keepDeformers and not self._require_mnode().hasFn(om2.MFn.kShape):
            # bakePartialHistory は Shape の無い Transform を「Shapeを選択」のエラーにするため、Shapeを渡す。
            targets = [shape.getFullName() for shape in self.getChildren(shapes=True) if shape.mnode().hasFn(om2.MFn.kShape)]
            if not targets:
                return self
        else:
            targets = [name]
        with undoChunk("mlibDagNodeDeleteHistory"):
            if keepDeformers:
                cmds.bakePartialHistory(targets, prePostDeformers=True)
            else:
                cmds.delete(targets, constructionHistory=True)
        return self

    def _collect_children(self, shapes, intermediates, all_descendents, order, leaves, include_self, under_world):
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
        recursive = all_descendents or leaves
        # この処理でだけ使うため、mlibの読み込み時間に含めない。
        from collections import deque

        pending = deque([(self, 0)])
        result = []
        while pending:
            node, depth = pending.popleft() if order == "breadthFirst" else pending.pop()
            is_shape = node._require_mnode().hasFn(om2.MFn.kShape)
            children = node._traversal_children(shapes, intermediates, under_world) if recursive or depth == 0 else []
            selected = (include_self or depth > 0) and (shapes or not is_shape)
            if selected and (not leaves or not any(child.mnode().hasFn(om2.MFn.kTransform) for child in children)):
                result.append(node)
            if recursive or depth == 0:
                rows = [(child, depth + 1) for child in children]
                pending.extend(rows if order == "breadthFirst" else reversed(rows))
        return result

    def _set_display_values(self, values, chunk, fast, shape=False):
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
        targets = self._color_targets(shape)
        if fast:
            writes = []
            for target in targets:
                # Plugのオブジェクトを作らず、組み込みアトリビュートのMPlugを直接取る。
                fn = target._dependency_fn()
                writes += [(fn.findPlug(attribute, False), value) for attribute, value in values]
            for plug, _ in writes:
                require_writable(plug)
                for child in range(plug.numChildren() if plug.isCompound else 0):
                    require_writable(plug.child(child))
            for plug, value in writes:
                set_plug(plug, value, _writable_checked=True)
            return
        names = [target.getFullName() for target in targets]
        with undoTransaction(chunk):
            for name in names:
                for attribute, value in values:
                    if isinstance(value, tuple):
                        cmds.setAttr(name + "." + attribute, *value)
                    else:
                        cmds.setAttr(name + "." + attribute, value)

    def _color_targets(self, shape):  # noqa: ARG002  # 派生が使う契約の引数。DagNodeは自身を返す。
        """表示色を読み書きするノードを返す。

        DagNodeでは ``shape`` にかかわらず自身だけを返す。

        Args:
            shape (bool): 確かめ済みのshape。

        Returns:
            list[DagNode]: 対象のノード。
        """
        self._require_valid("表示アトリビュートの取得")
        return [self]

    def _require_mnode(self):
        """このオブジェクトが持つMObjectを返す。

        :meth:`mnode` と同じ値を返し、Noneでないことを確かめる。
        作るときにノードが見つからなければ例外になるので、作られたオブジェクトは必ずMObjectを持っている。

        Returns:
            om2.MObject: 持っているMObjectそのもの(コピーではない)。
        """
        mobject = self.mnode()
        assert mobject is not None
        return mobject

    @staticmethod
    def _world_assemblies():
        """ワールド直下のTransformをすべて取得する。

        Returns:
            list[DagNode]: ワールド直下(DAGパスの長さが1)のTransformのオブジェクト。
        """
        iterator = om2.MItDag(om2.MItDag.kBreadthFirst, om2.MFn.kTransform)
        assemblies = []
        while not iterator.isDone():
            path = iterator.getPath()
            if path.length() == 1:
                # MItDag が返した有効なパスなので、Node(path) の入力解決を省いて同じ型で包む。
                assemblies.append(Node._wrap_dag_path(path))
            iterator.next()
        return assemblies

    def _sibling_position(self):
        """親の直接の子の中での順番と、子の数を返す。

        このオブジェクトが持つDAGパスが、親の直接の子の何番目にあるかを調べる。

        Returns:
            tuple[int, int]: (0 始まりの番号, 子の数)。

        Raises:
            RuntimeError: 並びの中にこのオブジェクトのパスが見つからない場合(アンダーワールドのノードなど)。
        """
        path = self.mpath()
        node = path.node()
        position = None
        if path.length() > 1:
            parent = om2.MDagPath(path)
            parent.pop()
            count = parent.childCount()
            for index in range(count):
                if parent.child(index) == node:
                    position = index
                    break
        else:
            # ワールド直下は cmds.reorder が数える並び(ls -assemblies と同じ順。非表示の既定ノードを
            # 含まない)を幅優先でたどる。深さ1を読み終えたら打ち切る。
            iterator = om2.MItDag(om2.MItDag.kBreadthFirst)
            count = 0
            while not iterator.isDone():
                depth = iterator.depth()
                if depth > 1:
                    break
                if depth == 1:
                    if position is None and iterator.currentItem() == node:
                        position = count
                    count += 1
                iterator.next()
        if position is None:
            raise RuntimeError(f"{type(self).__name__}のアウトライナーの並び順が見つかりません: {self.getFullName()}")
        return position, count

    def _direct_children(self, shapes, intermediates, shapes_only=False):
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
        path = self.mpath()
        if not path.node().hasFn(om2.MFn.kTransform):
            return []
        # 子の数と子は、このオブジェクトが持つDAGパスから直接読む(MFnDagNode(path) と同じ子の順。関数セットの作成を省く)。
        result = []
        for index in range(path.childCount()):
            obj = path.child(index)
            if not shapes and not obj.hasFn(om2.MFn.kTransform):
                continue
            if shapes_only and not obj.hasFn(om2.MFn.kShape):
                continue
            if not intermediates and om2.MFnDagNode(obj).isIntermediateObject:
                continue
            child = om2.MDagPath(path)
            child.push(obj)
            # 直前に延長した有効なパスなので、Node(child)の入力解決を省いて同じ型で包む。
            result.append(Node._wrap_dag_path(child))
        return result

    def _traversal_children(self, shapes, intermediates, under_world):
        """次にたどる子のパスを取得する。

        Args:
            shapes: TrueならShapeも含める。
            intermediates: Trueなら中間オブジェクトも含める。
            under_world: Trueなら、Shapeの下のアンダーワールドも調べる。
        """
        result = []
        is_shape = self._require_mnode().hasFn(om2.MFn.kShape)
        if under_world and (is_shape or not shapes):
            shape = self if is_shape else self.getShape()
            if shape is not None:
                iterator = om2.MItDag()
                iterator.reset(shape.mpath())
                iterator.traverseUnderWorld = True
                iterator.next()
                if not iterator.isDone():
                    root = iterator.getPath()
                    # アンダーワールドの非表示ルート自体は公開せず、その子を探索する。
                    if not om2.MFnDagNode(root).inModel:
                        for index in range(root.childCount()):
                            path = om2.MDagPath(root)
                            path.push(root.child(index))
                            if intermediates or not om2.MFnDagNode(path).isIntermediateObject:
                                result.append(Node._wrap_dag_path(path))
        result.extend(self._direct_children(shapes, intermediates))
        return result


def _palette_color(index):
    """カラー番号のRGBを返す。

    Args:
        index (int): 0〜31のカラー番号。

    Returns:
        tuple[float, float, float]: RGB。
    """
    # 0は既定色で取得できず、GUIのないMayaはcolorIndexがNoneを返すため標準のパレットを使う。
    if index == 0 or cmds.about(batch=True):
        return _DEFAULT_COLOR_PALETTE[index]
    return tuple(cmds.colorIndex(index, query=True))
