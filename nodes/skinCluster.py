"""skinClusterのインフルエンスと、先頭のMeshの頂点ウェイトを調べたり編集したりする。"""

import math
from collections.abc import Mapping
from contextlib import contextmanager
from decimal import ROUND_FLOOR, Decimal, localcontext
from itertools import groupby
from typing import List

import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2
import maya.cmds as cmds

from ..core.fastWrite import require_range, require_writable, set_attr
from ..core.ngSkinLayers import _layer_api, _move_layer_weights
from ..core.object import Object
from ..decorator import _edit_context, _pick_alias, _require_bool, preservedSelection, undoChunk
from ..maths import easing
from ..util import _MIRROR_PLANES, _UNSET, _mirror_axis, _PointGrid, _world_space
from .dagNode import DagNode
from .geometryFilter import GeometryFilter
from .joint import Joint, _unlocked_influences
from .node import Node, Nodes


def _finite_number(value):
    """有限の数値かを判定する。boolは数値として扱わない。

    Args:
        value (object): 判定する値。

    Returns:
        bool: int・floatの有限の値ならTrue。
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class SkinCluster(GeometryFilter):
    """skinClusterを扱うクラス。

    インフルエンスと、先頭に出力しているMeshの頂点ウェイトを調べたり編集したりする。

    このクラスのオブジェクトは、作ったときの先頭のジオメトリの名前・DAGパスと、
    自身のMFnSkinClusterを持つ。頂点の操作では、そのジオメトリがMeshであることを前提とする。
    複数のジオメトリをまとめて編集することはしない。

    インフルエンスの番号は2種類あり、区別して扱う。

    - influenceObjects()が返す並びの順番(物理的な順番)。
    - weights[]へ書き込むときに使う論理番号。
    """

    _LAYER_TOKENS = ("ngskin", "ngst", "ngskintools", "skinlayer", "skinninglayer", "layerdata")
    _SURFACE_ASSOCIATIONS = ("closestPoint", "rayCast", "closestComponent")
    _INFLUENCE_ASSOCIATIONS = ("closestJoint", "closestBone", "label", "name", "oneToOne")
    _SKINNING_METHODS = ("classicLinear", "dualQuaternion", "weightBlended")  #: skinningMethod の値の順の名前。
    _NORMALIZE_MODES = ("none", "interactive", "post")  #: normalizeWeights の値の順の名前。
    _WEIGHTS_FORMAT = "mlib.skinWeights"  #: exportWeights のファイルの形式名。
    _WEIGHTS_VERSION = 1  #: exportWeights のファイルの形式の版。
    mesh = None  #: 初期化時の先頭geometryの名前。クラスで宣言し、Node の代入の規則(Mayaアトリビュートへの書込み)から外す。
    mesh_path = None  #: 初期化時の先頭geometryの MDagPath。

    def __init__(self, skinCluster):
        """skinClusterの名前、またはMayaのオブジェクトからオブジェクトを作る。

        既存のskinClusterを取得するためだけに使う。新しくバインドするときは
        :func:`mlib.bindSkin <mlib.cmds.bindSkin.bindSkin>` を使う。
        先頭のジオメトリだけを持つ。頂点ウェイトの操作では、そのジオメトリがmeshであることを前提とする。

        Args:
            skinCluster (str | om2.MObject | om2.MDagPath): skinClusterの名前、またはAPIのオブジェクト。

        Returns:
            None: 値を返さない。

        Raises:
            IndexError: 対象のジオメトリが無い場合。
            RuntimeError: ジオメトリを特定できない場合。
        """
        super().__init__(skinCluster)
        self.mesh = self._first_geometry_name()
        self.mesh_path = self._geometry_dag_path(self.mesh)
        # 内部の照会で使い回す。公開の取得口は毎回新しく作る mfn()。
        self._skin_fn = oma2.MFnSkinCluster(self.mnode())

    def mfn(self):
        """このskinClusterのMFnSkinClusterを取得する。

        呼び出すたびに新しく作る。``oma2.MFnSkinCluster`` は ``om2.MFnDependencyNode`` の派生クラス。
        :meth:`Node.mfn` の決まりどおり、内部で使い回しているfunction setとは別のものを返す。

        Returns:
            oma2.MFnSkinCluster: このskinClusterの function set。

        Raises:
            RuntimeError: ノードが破棄されている場合(削除した後、Undoの記録からも消えた場合)。
        """
        # 破棄済みノードへ function set を作るとMayaが異常終了するため、先に確かめる。
        self._alive_fn()
        return oma2.MFnSkinCluster(self.mnode())

    def deforms(self, geometry):
        """指定した形状を、このskinClusterが変形しているかを調べる。

        探し方は :meth:`mlib.nodes.DagNode.getSkinClusters` と同じ。Shapeならそれ自身、Transformなら
        直下のShape(中間オブジェクトを除く)のヒストリを上流へたどり、出力先がその形状になっているskinClusterを探す。
        Jointは形状を持たないのでFalseになる。インフルエンスとして登録されているかは :meth:`hasInfluence` で調べる。

        Args:
            geometry (str | Node): 調べる形状、またはそのtransform。

        Returns:
            bool: このskinClusterが形状を変形していればTrue。DAGノードでないものもFalse。

        Raises:
            RuntimeError: その名前のノードが無い場合、またはMayaの検索が失敗した場合。
        """
        return self.getUuid() in self._geometry_skin_uuids(Node(geometry))

    @undoChunk("mlibSkinClusterCopyWeightsTo")
    def copyWeightsTo(self, target):
        """別のskinClusterへ、いちばん近い点を使ってウェイトを転送する。

        転送先には、skinClusterのほか、形状(Shape)やその親のTransformも指定できる。

        - 形状を変形しているskinClusterがあれば、そこへ転送する。
        - 無ければ、自身のすべてのインフルエンスと同じmaxInfluencesで、
          :func:`mlib.bindSkin <mlib.cmds.bindSkin.bindSkin>` でバインドしてから転送する。

        バインドと転送は、1回のUndoで戻せる。OpenMayaにはバインドやコピーのAPIが無いため、fast引数は持たない。

        Args:
            target (str | Node): 転送先のskinCluster、または形状かその親のTransform。

        Returns:
            SkinCluster: ウェイトを書き込んだ転送先。新しくバインドした場合は、そのskinCluster。

        Raises:
            TypeError: 転送先がskinClusterでも形状でもない場合(Joint・形状の無いTransform・DGノードなど)。
            ValueError: 転送先が自身(または自身が変形している形状)の場合、または形状を複数のskinClusterが変形している場合。
            RuntimeError: 転送先の名前のノードが無い場合、またはMayaがバインドや転送を拒否した場合。

        Note:
            頂点はclosestPoint、インフルエンスはname/closestJointで対応付ける、おおよその転送で、転送後に正規化する。
            基準になる姿勢が違う場合の補正や、メッシュの頂点を減らすことはしない。
        """
        destination = self._copy_destination(target)
        if destination.getUuid() == self.getUuid():
            raise ValueError("コピー元とコピー先は別のskinClusterで指定してください")
        cmds.copySkinWeights(
            sourceSkin=self.getFullName(),
            destinationSkin=destination.getFullName(),
            noMirror=True,
            surfaceAssociation="closestPoint",
            influenceAssociation=["name", "closestJoint"],
            normalize=True,
        )
        return destination

    @undoChunk("mlibSkinClusterMirrorWeights")
    def mirrorWeights(self, axis="YZ", positiveToNegative=True, surfaceAssociation="closestPoint", influenceAssociation=("closestJoint",), normalize=True):
        """自身の形状の片側のウェイトを、鏡映面の反対側へ写す。

        ``cmds.copySkinWeights(sourceSkin=自身, destinationSkin=自身, mirrorMode=axis, ...)`` を実行し、
        1回のUndoにまとめる。OpenMayaにはミラーのAPIが無いため、fast引数は持たない。

        Args:
            axis (str | int): 鏡映面の指定。次のどれかで指定する。
                既定の ``"YZ"`` (``"x"`` と同じ)は、X軸方向の左右反転になる。

                - 鏡映面: ``"YZ"``・``"XZ"``・``"XY"``。文字の順番と大文字・小文字は問わない。
                - 反転する軸: ``"x"``・``"y"``・``"z"``。xはYZ、yはXZ、zはXYと同じ。
                - 番号: 0・1・2。
            positiveToNegative (bool): Trueなら、面の正の側(YZならX>0)から負の側へ写す。
                Falseなら、負の側から正の側へ写す(``mirrorInverse=True``)。
            surfaceAssociation (str): 頂点の対応の付け方。``"closestPoint"``・``"rayCast"``・``"closestComponent"`` のどれか。
            influenceAssociation (str | Sequence[str]): インフルエンスの対応の付け方を、優先する順に1〜3個指定する。
                ``"closestJoint"``・``"closestBone"``・``"label"``・``"name"``・``"oneToOne"`` から選ぶ。
                ジョイントのラベル(side/type)を設定してあれば、``("label", "closestJoint")`` が確実。
            normalize (bool): Trueなら、写した後に各頂点を正規化する(copySkinWeightsのnormalize)。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: 引数の型が正しくない場合。
            ValueError: 面や対応の付け方の名前が正しくない場合、またはインフルエンスの対応の付け方が
                0個・4個以上・重複している場合。
            RuntimeError: Mayaがミラーを拒否した場合。
        """
        axis = _MIRROR_PLANES[_mirror_axis(axis)]
        _require_bool(positiveToNegative, "positiveToNegative")
        surfaceAssociation = self._require_choice(surfaceAssociation, "surfaceAssociation", self._SURFACE_ASSOCIATIONS)
        if isinstance(influenceAssociation, str):
            influenceAssociation = (influenceAssociation,)
        try:
            influence_association = list(influenceAssociation)
        except TypeError:
            raise TypeError("influenceAssociationはstrかstrの並びで指定してください") from None
        if not 1 <= len(influence_association) <= 3 or len(set(influence_association)) != len(influence_association):
            raise ValueError("influenceAssociationには、別々の対応付けの方法を1〜3個指定してください")
        for method in influence_association:
            self._require_choice(method, "influenceAssociation", self._INFLUENCE_ASSOCIATIONS)
        _require_bool(normalize, "normalize")
        name = self.getFullName()
        cmds.copySkinWeights(
            sourceSkin=name,
            destinationSkin=name,
            mirrorMode=axis,
            mirrorInverse=not positiveToNegative,
            surfaceAssociation=surfaceAssociation,
            influenceAssociation=influence_association,
            normalize=normalize,
        )
        return self

    def pruneWeights(self, threshold, normalize=True, *, fast=False):
        """先頭のMeshの各頂点で、しきい値より小さなウェイトを0にする。

        ``cmds.skinPercent(skin, mesh, pruneWeights=threshold)`` と同じように動く。

        - 値が ``0 < w < threshold`` のインフルエンスを0にする。しきい値と等しい値は残す。
        - ロックしていないインフルエンスがすべてしきい値より小さくなる頂点は、0にも正規化もしない。
        - lockInfluenceWeightsが有効なインフルエンスは0にせず、正規化でも値を変えない。

        値が変わった頂点・列だけを書き込む。通常はcmds.setAttrで書き込み、1回のUndoで戻せる。
        ``fast=True`` では、:meth:`setWeights` のfastと同じく、すべての対象を書き込めるかを先に調べてから、
        OpenMayaでウェイトのPlugへ直接書き込む。Undoには記録しない。

        Args:
            threshold (float): しきい値。0以上の有限な数で指定する。boolは指定できない。
            normalize (bool): Trueなら、上に書いた0にしない頂点を除くすべての頂点(0にする値が無い頂点も含む)で、
                ロックしていないインフルエンスの比率を保ったまま、合計を1(ロックした分を除いた残り)へ戻す。
                ロックしていないインフルエンスがすべて0の頂点は変えない。
                ロックが無ければ、skinPercentの結果と同じ値になる。Falseなら0にするだけで、ほかの値は変えない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: thresholdが数値でない場合、またはnormalize・fastがboolでない場合。
            ValueError: thresholdが負・有限でない場合、または0にする頂点に、負の値・有限でない値・
                合計が1を超えるロックした値がある場合。
            RuntimeError: ウェイトがロックされている・入力が接続されている場合、またはMayaが書き込みを拒否した場合。
        """
        with _edit_context("mlibSkinClusterPruneWeights", fast):
            if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
                raise TypeError(f"thresholdは数値で指定してください: {type(threshold).__name__}")
            threshold = float(threshold)
            if not math.isfinite(threshold) or threshold < 0.0:
                raise ValueError(f"thresholdは0以上の有限な数値で指定してください: {threshold}")
            _require_bool(normalize, "normalize")
            paths = self._skin_fn.influenceObjects()
            locked = {i for i, path in enumerate(paths) if self._influence_locked(path)}
            free = [i for i in range(len(paths)) if i not in locked]
            _, num_vertices = self._all_vertices()
            vertex_indices = list(range(num_vertices))
            rows = self._read_rows(vertex_indices, range(len(paths)))
            edited_vertices, edited_rows, changed = [], [], set()
            for vertex, row in zip(vertex_indices, rows):
                pruned = [i for i in free if 0.0 < row[i] < threshold]
                if pruned and all(row[i] == 0.0 or i in pruned for i in free):
                    # skinPercentと同じく、全てを刈り込む頂点は刈り込みも正規化もしない。
                    continue
                new = list(row)
                for i in pruned:
                    new[i] = 0.0
                if normalize and any(new[i] > 0.0 for i in free):
                    # skinPercentと同じく、刈り込みの無い頂点も正規化する。ロック以外が全て0の頂点は変更しない。
                    self._normalize_row(new, vertex, (), free, locked)
                # 既に正規化済みの頂点を丸め誤差だけで書き直さない。
                columns = [i for i in range(len(paths)) if abs(new[i] - row[i]) > 1e-12]
                if columns:
                    changed.update(columns)
                    edited_vertices.append(vertex)
                    edited_rows.append(new)
            if edited_vertices:
                columns = sorted(changed)
                values = [row[i] for row in edited_rows for i in columns]
                logical = [self._skin_fn.indexForInfluenceObject(paths[i]) for i in columns]
                if fast:
                    self._set_weight_values_fast(values, len(columns), edited_vertices, logical)
                else:
                    self._set_weight_values_cmds(values, len(columns), edited_vertices, logical)
            return self

    def getInfluences(self):
        """登録されているインフルエンスを取得する。

        並びはAPIのinfluenceObjects()の順(物理的な順番)になる。

        Returns:
            list[Node]: influenceObjects()のDAGパスから作った新しいオブジェクトのリスト。
                登録されている型に応じて、Joint以外も返す。リストの中の位置は、weights[]の論理番号と同じとは限らない。
                ノードを複製することはない。
        """
        # influenceObjects()が返したばかりの有効なパスなので、入力の再解決を省いてラッパーにする。
        return [Node._wrap_dag_path(path) for path in self._skin_fn.influenceObjects()]

    @undoChunk("mlibSkinClusterAddInfluences")
    def addInfluences(self, joints):
        """ジョイントを、ウェイト0のインフルエンスとして登録する。

        すでにインフルエンスになっているものと、重ねて指定したものは無視する。

        Args:
            joints (Joint | str | Iterable[Joint | str]): 追加するジョイント。空なら何もしない。

        Returns:
            SkinCluster: 自身。

        Raises:
            ValueError: Joint以外を指定した場合。編集する前に、すべての対象を確かめる。
            RuntimeError: 対象が無効な場合、またはMayaが追加を拒否した場合。

        Note:
            すでにあるウェイトの配り直しや正規化はしない。すでにあるロックの設定も変えない。
        """

        existing = {om2.MFnDependencyNode(path.node()).uuid().asString() for path in self._skin_fn.influenceObjects()}
        names = []
        for name in Object._input_names(joints):
            node = Node(name)
            if not node.isType("joint"):
                raise ValueError(f"ジョイントを指定してください: {name}")
            if node.getUuid() not in existing:
                existing.add(node.getUuid())
                names.append(node.getFullName())
        if names:
            cmds.skinCluster(self.getFullName(), edit=True, addInfluence=names, weight=0.0)
        return self

    def removeInfluences(self, joints, transferToParent=True, *, force=False):
        """複数のインフルエンスを、階層の深いものから順に外す。ノードそのものは削除しない。

        親子のjointを一緒に渡しても、深いjointから :meth:`removeInfluence` と同じ処理で外す。
        そのため、ウェイトは、外さずに残る最も近い祖先のインフルエンスへ集まる。
        すべての対象の登録と、ウェイトの移し先を先に確かめる。

        - ウェイトのロックは一時的に外してから外し、元の状態へ戻す。
        - ngSkinTools2のレイヤーは、レイヤーごとにウェイトを移す。

        Undoが有効なら1つのチャンクにまとめて記録する。fast引数は持たない。
        途中で失敗しても、それまでに終わった変更は戻さない。

        Args:
            joints (str | Node | Iterable): 外す、登録済みのインフルエンス。名前かNodeのどちらか一方の形で指定する。
            transferToParent (bool): Trueなら、外さずに残る最も近い祖先のインフルエンスへウェイトを足す。
                Falseなら、Maya標準の配り直しに任せる。
            force (bool): Trueなら、正しくないウェイトを直してから処理する。直すときに正規化はしない。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: transferToParent・forceがboolでない場合、またはインフルエンスの入力の型が正しくない場合。
            ValueError: インフルエンスが空・未登録・重複の場合、すべてのインフルエンスを外そうとした場合、または
                transferToParent=Trueで、残る祖先のインフルエンスが無いものがある場合。
            RuntimeError: ウェイトの要素がロックされている・入力が接続されている場合、またはMayaの編集が失敗した場合。
        """
        with undoChunk("mlibSkinClusterRemoveInfluences"):
            _require_bool(transferToParent, "transferToParent")
            _require_bool(force, "force")
            paths = self._skin_fn.influenceObjects()
            targets = [Node._wrap_dag_path(paths[index]) for index in self._require_influences(joints)]
            if len(targets) >= len(paths):
                raise ValueError("すべてのインフルエンスを削除することはできません")
            removing = {node.getUuid() for node in targets}
            if transferToParent:
                for node in targets:
                    ancestor = node.getParent() if isinstance(node, Joint) else None
                    while isinstance(ancestor, Joint) and (ancestor.getUuid() in removing or not self.hasInfluence(ancestor.getFullName())):
                        ancestor = ancestor.getParent()
                    if not isinstance(ancestor, Joint):
                        raise ValueError(f"ウェイトを受け取る祖先のインフルエンスが残っていません: {node.getFullName()}")
            with _unlocked_influences([self]):
                plans, snapshot = self._influence_removal_plans(targets, transferToParent, force=force)
                self._apply_influence_removals(plans, snapshot, force=force)
            return self

    def getBindPose(self):
        """bindPoseアトリビュートに接続している、保存したポーズを取得する。

        Returns:
            DagPose | None: 接続しているポーズ。接続が無ければNone。

        Raises:
            RuntimeError: skinClusterが無効な場合、または接続先がdagPoseでない場合。
        """
        # nodes の初期化順に依存しないよう、使う時点で読み込む。
        from .dagPose import DagPose

        return DagPose.fromSkinCluster(self)

    def resetBindPose(self):
        """このskinClusterのインフルエンスについて、保存した姿勢を今の姿勢へ更新する。

        接続しているバインドポーズのうち、インフルエンスの分だけを ``DagPose.reset`` で更新する。
        同じポーズを使っている別のskinClusterからも、更新した結果が見える。bindPreMatrixとウェイトは変えない。
        ポーズに入っていないインフルエンスは自動で足さず、何かを変える前に例外にする。
        ``cmds.dagPose`` の保存の規則をom2で再現しないため、fast引数は持たない。

        Returns:
            SkinCluster: 自身。

        Raises:
            ValueError: インフルエンスが空の場合、またはポーズに入っていない場合。
            RuntimeError: ポーズが接続されていない場合、ノードが無効な場合、またはMayaが更新を拒否した場合。
        """
        with undoChunk("mlibSkinClusterResetBindPose"):
            pose = self.getBindPose()
            if pose is None:
                raise RuntimeError(f"{self.getFullName()}にバインドポーズが接続されていません")
            pose.reset(self.getInfluences())
            return self

    def restoreBindPose(self, worldSpace=_UNSET, *, ws=_UNSET):
        """接続しているポーズのすべてのメンバーを、保存した姿勢へ戻す。

        同じポーズを使っている別のskinClusterや、インフルエンス以外のメンバーにも影響する。
        ロックや入力の接続は外さない。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間で戻す。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: ポーズが接続されていない場合、ノードが無効な場合、またはMayaが戻すのを拒否した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=True)
        with undoChunk("mlibSkinClusterRestoreBindPose"):
            ws = _world_space(worldSpace)
            pose = self.getBindPose()
            if pose is None:
                raise RuntimeError(f"{self.getFullName()}にバインドポーズが接続されていません")
            pose.restore(worldSpace=ws)
            return self

    def recacheBindMatrices(self):
        """バインド時のマトリクスを読み直させる。

        ``skinCluster -e -recacheBindMatrices`` を実行する。Mayaが内部に持っているバインド時のマトリクスを、
        ``bindPreMatrix`` から読み直させる。``bindPreMatrix`` を書き換えた後や、インフルエンスの姿勢を変えてから
        基準を取り直すときに使う。ウェイトは変えない。
        OpenMayaに同じ機能が無いため、fast引数は持たない。

        Returns:
            SkinCluster: 自身。

        Raises:
            RuntimeError: ノードが無効(削除済み)な場合、またはMayaが処理を拒否した場合。
        """
        self._require_valid("バインドマトリクスの再キャッシュ")
        with undoChunk("mlibSkinClusterRecacheBindMatrices"):
            cmds.skinCluster(self.getFullName(), edit=True, recacheBindMatrices=True)
            return self

    def unbind(self, keepHistory=False):
        """形状からスキンを外す。

        ``skinCluster -e -unbind`` (または ``-unbindKeepHistory``)を実行する。Mayaの Unbind Skin と同じく、
        形状をバインドしたときの形へ戻す。

        - ``keepHistory=False``: skinClusterを削除する。このオブジェクトは無効になる。
        - ``keepHistory=True``: skinClusterとウェイト・接続を形状のヒストリに残す。
          ``nodeState`` を HasNoEffect(1)にして、変形だけを止める。

        どちらでも、バインドポーズは削除される。
        OpenMayaに同じ機能が無いため、fast引数は持たない。Undoが有効なら1回で戻せる。

        Args:
            keepHistory (bool): Trueなら、skinClusterのノードとウェイトをヒストリに残す。既定はFalse。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: keepHistoryがboolでない場合。
            RuntimeError: ノードが無効(削除済み)な場合、またはMayaが処理を拒否した場合。
        """
        _require_bool(keepHistory, "keepHistory")
        self._require_valid("バインドの解除")
        flag = "unbindKeepHistory" if keepHistory else "unbind"
        with undoChunk("mlibSkinClusterUnbind"):
            cmds.skinCluster(self.getFullName(), edit=True, **{flag: True})

    def getUnusedInfluences(self):
        """ウェイトを持たないインフルエンスを探す。シーンは変えない。

        Returns:
            list[Node]: インフルエンスの順に並べたノードのオブジェクト。ごく小さな値でも使っているものとして扱い、
                しきい値で切り捨てることはしない。すべてのジオメトリについてMFnSkinClusterで判定する。

        Raises:
            RuntimeError: skinClusterが無効な場合、または取得に失敗した場合。
        """
        self._require_valid("値の取得")
        result = []
        for path in self._skin_fn.influenceObjects():
            selection, _ = self._skin_fn.getPointsAffectedByInfluence(path)
            if not selection.length():
                result.append(Node._wrap_dag_path(path))
        return result

    def removeUnusedInfluences(self, *, force=False):
        """使っていないインフルエンスの登録を外す。ノードそのものは残す。

        forceを指定したときは、正しくないウェイトを直してから、使っていないものを探す。
        Undoが有効なら1つのチャンクにまとめて記録する。fast引数は持たない。
        途中で失敗しても、先に行った修正や登録の解除は自動では戻さない。

        Args:
            force (bool): Trueなら、ウェイトを直してから使っていないものを調べる。正規化やロックの解除はしない。

        Returns:
            list[Node]: 登録を外したノード。インフルエンスの順に並ぶ。対象が無ければ空リスト。

        Raises:
            TypeError: forceがboolでない場合。
            ValueError: 外すとインフルエンスが1つも残らなくなる場合。
            RuntimeError: レイヤー・ロック・接続のために編集できない場合、またはMayaの編集が失敗した場合。
        """
        with undoChunk("mlibSkinClusterRemoveUnusedInfluences"):
            _require_bool(force, "force")
            if force:
                _, used = self._weight_cleanup_plan()
                if not used:
                    raise ValueError("skinClusterからすべてのインフルエンスを削除することはできません")
                self.removeInvalidWeights()
            unused = self.getUnusedInfluences()
            if unused and len(unused) == len(self.getInfluences()):
                raise ValueError("skinClusterからすべてのインフルエンスを削除することはできません")
            for node in unused:
                self.removeInfluence(node.getFullName(), transferToParent=False)
            return unused

    def removeInvalidWeights(self, *, fast=False):
        """正しくないウェイトの要素を取り除く。

        取り除くのは、負の値・有限でない値・登録されていないインフルエンス番号の要素。
        weightListにすでにある要素だけが対象になる。

        - 負でない有限の値は、1を超えていても残す。
        - 正規化・合計が0の頂点の穴埋め・インフルエンスの削除はしない。
        - 取り除いた要素が登録済みのインフルエンスのものなら、そのウェイトは既定の値の0になる。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            SkinCluster: 自身。正しくない要素が無ければ何もしない。

        Raises:
            TypeError: fastがboolでない場合。
            RuntimeError: レイヤー・インフルエンス・ウェイトがロックされている・接続されている場合、または編集が失敗した場合。

        Note:
            変える前に、すべての要素を確かめる。実行の途中でMayaのエラーが起きても、自動では戻さない。
        """
        with _edit_context("mlibSkinClusterRemoveInvalidWeights", fast):
            self._remove_weight_elements(self._weight_cleanup_plan()[0], fast=fast)
            return self

    def hasInfluence(self, joint):
        """指定したjointがインフルエンスに含まれるかを判定する。

        Args:
            joint (str): 判定するjointの名前。

        Returns:
            bool: インフルエンスに含まれていれば ``True``。
        """
        uuid = self._uuid_or_none(joint)
        if not uuid:
            return False
        return any(self._path_uuid(path) == uuid for path in self._skin_fn.influenceObjects())

    def getInfluenceVertices(self, influence, threshold=0.0):
        """インフルエンスがウェイトを持っている、先頭のMeshの頂点を取得する。

        MayaのSelect Influence Verticesに当たる。``MFnSkinCluster.getPointsAffectedByInfluence`` の結果から、
        ウェイトが ``threshold`` より大きい頂点を、番号の小さい順に返す。シーンと選択は変えない。

        Args:
            influence (str | Node): 登録済みのインフルエンス。1つだけ指定する。
            threshold (float): しきい値。0以上の有限な数で指定する。この値より大きいウェイトを持つ頂点だけを返す。
                既定は0.0(ウェイトが0でない頂点すべて)。boolは指定できない。

        Returns:
            Vertices: 先頭のMeshの頂点。当てはまるものが無ければ空。

        Raises:
            TypeError: thresholdが数値でない場合、またはinfluenceに頂点やアトリビュートを渡した場合。
            ValueError: thresholdが負・有限でない場合、またはinfluenceが未登録・1つでない場合。
            RuntimeError: ノードが無効(削除済み)な場合。
        """
        # componentsはnodesを読み込むため、循環importを避けて使う時点で読み込む。
        from ..components.vertex import Vertices

        self._require_valid("値の取得")
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise TypeError(f"thresholdは数値で指定してください: {type(threshold).__name__}")
        threshold = float(threshold)
        if not math.isfinite(threshold) or threshold < 0.0:
            raise ValueError(f"thresholdは0以上の有限な数値で指定してください: {threshold}")
        physical = self._require_influences(influence)
        if len(physical) != 1:
            raise ValueError(f"インフルエンスを1つ指定してください: {len(physical)}個")
        path = self._skin_fn.influenceObjects()[physical[0]]
        selection, weights = self._skin_fn.getPointsAffectedByInfluence(path)
        mesh = self._mesh_node()
        indices = set()
        position = 0
        for item in range(selection.length()):
            dag_path, component = selection.getComponent(item)
            elements = om2.MFnSingleIndexedComponent(component).getElements() if not component.isNull() else []
            for element in elements:
                # 重みの配列は全形状の要素を選択リストの順に並べたものなので、先頭Mesh以外も位置を進める。
                if dag_path.node() == mesh and weights[position] > threshold:
                    indices.add(element)
                position += 1
        return Vertices(Node._wrap_dag_path(self.mesh_path), sorted(indices))

    def getLockedInfluences(self):
        """ウェイトをロック(lockInfluenceWeights)しているインフルエンスを取得する。

        Returns:
            list[Node]: ロックしているインフルエンス。並びと型は :meth:`getInfluences` と同じ。
        """
        return [node for node in self.getInfluences() if node.hasAttr("lockInfluenceWeights") and node.getPlug("lockInfluenceWeights").get()]

    def setInfluencesLocked(self, joints, state=True):
        """インフルエンスのウェイトのロック(lockInfluenceWeights)を設定する。

        ロックしたインフルエンスの値は、Mayaのペイントや、:meth:`setWeights` の ``normalize=True`` でも変わらない。
        インフルエンスの数だけsetAttrするだけで、OpenMayaで書いても速くならないため、fast引数は持たない。

        Args:
            joints (str | Node | Iterable): 登録済みのインフルエンス。複数指定するときは、名前とオブジェクトを混ぜない。
            state (bool): Trueならロックし、Falseならロックを外す。既定はTrue。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: stateがboolでない場合、またはインフルエンスの入力の型が正しくない場合。
            ValueError: インフルエンスが空・未登録・重複の場合。
            RuntimeError: lockInfluenceWeightsがロックされている・入力が接続されている場合。
        """
        with undoChunk("mlibSkinClusterSetInfluencesLocked"):
            _require_bool(state, "state")
            paths = self._skin_fn.influenceObjects()
            for index in self._require_influences(joints):
                Node._wrap_dag_path(paths[index]).getPlug("lockInfluenceWeights").set(state)
            return self

    @contextmanager
    def unlockedInfluences(self, joints=None):
        """指定したインフルエンスのウェイトのロックを一時的に外し、withを抜けるときに元へ戻す。

        withに入るときにロックしていたインフルエンスだけを外す(:meth:`setInfluencesLocked` と同じ
        lockInfluenceWeights)。抜けるとき(例外で抜けるときも)に、それらをロックした状態へ戻す。

        - 入るときにロックしていなかったインフルエンスは、withの中で変えても戻さない。
        - withの中で削除されたjointや、インフルエンスでなくなったjointは戻さない。

        fast引数は持たない。

        Undoが有効なら、ロックを外す操作・withの中の操作・ロックを戻す操作を、1つのUndoチャンクにまとめる。
        抜けた後に1回Undoすると、withに入る前の状態(ロックしたまま、ウェイトも元の値)へ戻る。

        withの中では ``cmds.undo()`` を呼ばないこと。開いているチャンクの中でUndoすると、Mayaが記録した
        最後の1項目だけが戻る。そのため、:meth:`setWeights` などの1回の操作の途中までしか戻らない。
        操作が無ければ、ロックを外したことが戻る(ロックした状態になる)。抜けるときには、その時の状態に関係なく
        元のロックを設定する。withの中の操作を取り消したいときは、抜けてからUndoする。

        Args:
            joints (str | Node | Iterable | None): 対象の、登録済みのインフルエンス。Noneならすべてのインフルエンス。
                複数指定するときは、名前とオブジェクトを混ぜない(:meth:`setInfluencesLocked` と同じ)。

        Yields:
            SkinCluster: 自身。

        Raises:
            TypeError: インフルエンスの入力の型が正しくない場合。
            ValueError: インフルエンスが空・未登録・重複の場合。
            RuntimeError: lockInfluenceWeightsがロックされている・入力が接続されている場合。

        Examples:
            .. code-block:: python

                with skin.unlockedInfluences():
                    skin.setWeights(["spine_JNT"], [1.0], vertices=[0], normalize=True)
        """
        if joints is None:
            targets = self.getInfluences()
        else:
            paths = self._skin_fn.influenceObjects()
            targets = [Node._wrap_dag_path(paths[index]) for index in self._require_influences(joints)]
        locked = [node for node in targets if node.hasAttr("lockInfluenceWeights") and node.getPlug("lockInfluenceWeights").get()]
        with undoChunk("mlibSkinClusterUnlockedInfluences"):
            for node in locked:
                node.getPlug("lockInfluenceWeights").set(False)
            try:
                yield self
            finally:
                for node in locked:
                    if node.isValid() and node.hasAttr("lockInfluenceWeights"):
                        node.getPlug("lockInfluenceWeights").set(True)

    def getWeights(self, joints, *, vertices=None, rows=False):
        """指定したインフルエンスの頂点ウェイトを、先頭のMeshから取得する。

        APIには、influenceObjects()の中での物理的な番号を渡す。飛び飛びになり得るweights[]の論理番号は渡さない。
        インフルエンスは :meth:`setWeights` と同じく、空・未登録・重複を、何かを変える前に拒否する。

        Args:
            joints (str | Node | Iterable): 登録済みのインフルエンス。複数指定するときは、名前とオブジェクトを混ぜない。
                頂点(Vertex・"mesh.vtx[0]"など)はインフルエンスではないため、TypeErrorになる。
            vertices (Vertex | Vertices | int | str | Iterable | None): 取得する頂点。Noneならすべての頂点。
                Vertex・Verticesは先頭のMeshのものだけを指定できる。文字列は ``"mesh.vtx[0:3]"`` のような頂点の名前。
                指定した順に返す。重複していればValueError。
            rows (bool): Trueなら、頂点ごとの行(``list[list[float]]``)で返す。既定はFalseで、1列に並べたlistを返す。

        Returns:
            om2.MDoubleArray | list[list[float]]: 既定では、頂点の数×指定したインフルエンスの数の値を1列に並べた
                ``om2.MDoubleArray`` (listと同じく番号で読め、``list()`` でlistにできる)。
                頂点は指定した順(Noneなら番号順)、各頂点の中はjointsの順に並ぶ。
                i番目の頂点のj番目のインフルエンスの値は ``weights[i * len(joints) + j]``。
                ``rows=True`` なら、同じ値を頂点ごとの行に分けた ``weights[i][j]`` になる。
                値は単位の無い数で、シーンとは切り離されている。戻り値を変えてもシーンには反映されない。
                1つの頂点のウェイトをインフルエンスごとに読むなら、:meth:`getVertexWeights`
                (インフルエンスからウェイトへの辞書)を使う。

        Raises:
            TypeError: jointsに頂点やアトリビュートを渡した場合、頂点の入力の型が正しくない場合、
                またはrowsがboolでない場合。
            ValueError: インフルエンスが空・未登録(例: ``'arm_R_JNT'はskinCluster1のインフルエンスではありません``)・重複の場合、
                または頂点が重複している・別の形状のものである場合。
            IndexError: 頂点の番号が範囲外の場合。
        """
        _require_bool(rows, "rows")
        physical_indices = self._require_influences(joints)
        vertex_indices = self._vertex_indices(vertices)
        if vertex_indices is None:
            component, _ = self._all_vertices()
            flat = self._skin_fn.getWeights(self.mesh_path, component, om2.MIntArray(physical_indices))
            if not rows:
                return flat
            width = len(physical_indices)
            return [list(flat[start : start + width]) for start in range(0, len(flat), width)]
        values = self._read_rows(vertex_indices, physical_indices)
        if rows:
            return [list(row) for row in values]
        return om2.MDoubleArray([value for row in values for value in row])

    def setWeights(self, joints, weights, *, vertices=None, normalize=False, broadcast=False, rows=False, fast=False):
        """指定したインフルエンスの頂点ウェイトを設定する。

        既定では正規化せず、渡した値をそのまま書き込む。

        入力を確かめた後、通常はcmds.setAttrで、頂点の順・指定した列の順に書き込む。
        指定した順で論理番号が続いている部分は、範囲を指定した1回のsetAttrにまとめる。
        ただし、失敗したときにどこまで書き込まれるか、どのエラーになるかは、要素ごとに書き込む場合と同じ。
        fastでは、対象のすべてのPlugについて、ロック・入力の接続・書き込めるか・アトリビュートの範囲を先に確かめてから、
        MPlug.setDoubleで順に書き込む。
        どちらの場合も、MFnSkinCluster.setWeightsによる、指定しなかった列への配り直しは使わない。

        ``normalize=True`` では、``cmds.skinPercent(transformValue=..., normalize=True)`` にならって、
        書き込む各頂点の合計を1にする。

        - 指定したインフルエンスには、指定した値を書く。
        - 指定しなかったインフルエンスのうち、lockInfluenceWeightsが有効なものは値を保つ。
        - 残りの指定しなかったインフルエンスを、比率を保ったまま ``1 - 指定値の合計 - ロック値の合計`` へ拡大・縮小する。
        - ただし、指定した値の合計がこの残りを超える場合と、拡大・縮小できる指定しなかったインフルエンスが無い
          (値がすべて0の)場合は、指定した値を比率を保ったまま ``1 - ロック値の合計`` へ拡大・縮小し、
          指定しなかったもの(ロックしたものを除く)を0にする。

        値が変わった、指定しなかったインフルエンスの列も書き込む。最後の場合のskinPercentの結果はMayaの版で違う
        (2022は指定した値をそのまま書く)。そのため、mlibは版に関係なくこの規則で合計を1にする。

        Args:
            joints (str | Node | Iterable): 空でない、登録済みのインフルエンス。名前かNodeのどちらか一方の形で指定する。
                同じインフルエンスを重ねて指定すると拒否する。頂点(Vertex・"mesh.vtx[0]"など)はTypeError。
            weights (Iterable[float] | Iterable[Iterable[float]]): 書き込む値。対象の頂点の数をV、指定した列の数をKとすると、V*K個
                (頂点の順で、各頂点の中はjointsの順)。``broadcast=True`` なら、すべての対象の頂点に共通のK個。
                ``rows=True`` なら、K個ずつの行がV個(:meth:`getWeights` に ``rows=True`` を指定した結果と同じ形)。
                値はfloatへ変換できる有限の数。
            vertices (Vertex | Vertices | int | str | Iterable | None): 書き込む頂点。Noneならすべての頂点。
                Vertex・Verticesは先頭のMeshのものだけを指定できる。文字列は ``"mesh.vtx[0:3]"`` のような頂点の名前。
                weightsはこの指定の順に対応する。重複していればValueError、空なら何もしない。
            normalize (bool): Trueなら、書き込んだ頂点を上の規則で合計1へ正規化する。既定はFalse。
                対象の頂点に負の値や有限でない値があればValueError。
            broadcast (bool): Trueなら、K個の値をすべての対象の頂点へ同じように書き込む。既定はFalse。
                2つ以上の頂点へK個だけを渡すときは、この指定が必要。
            rows (bool): Trueなら、weightsを頂点ごとの行として受け取る。既定はFalse。broadcastとは同時に指定できない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: 数値に変換できない型の場合、頂点やインフルエンスの入力の型が正しくない場合、
                またはboolの引数がboolでない場合。
            ValueError: インフルエンスが空・未登録・重複の場合、数が合わない場合(broadcast=Trueを指定せずにK個を
                複数の頂点へ渡した場合や、rows=Trueで行の長さがKでない場合を含む)、rowsとbroadcastを同時に指定した場合、
                有限でない値がある場合、数値の文字列が正しくない場合、頂点が重複している・別の形状のものである場合、
                または正規化できない頂点がある場合。
            IndexError: 頂点の番号が範囲外の場合。
            RuntimeError: Plugが編集できない場合、またはMayaが設定を拒否した場合。

        Note:
            ``normalize=False`` では、指定しなかった列とインフルエンスのロックの設定は変えない。
            ただし、lockInfluenceWeightsを理由に拒否することも、レイヤーを見つけることもしない。
            負でないことや合計が1であることも、独自には確かめない。
            normalizeWeights・maintainMaxInfluencesの設定に合わせて正規化し直すこともしない。
            通常の書き込みは、Undoが有効なら同じチャンクに記録する。後のほうで失敗しても、それまでに終わった変更は
            自動では戻さない。fastで先に確かめていても、書き込みの途中での失敗まで全部か無しかにはならない。
        """
        with _edit_context("mlibSkinClusterSetWeights", fast):
            _require_bool(normalize, "normalize")
            _require_bool(broadcast, "broadcast")
            _require_bool(rows, "rows")
            if rows:
                if broadcast:
                    raise ValueError("rowsとbroadcastは同時に指定できません")
                weights = self._flatten_weight_rows(joints, weights)
            values, width, vertex_indices, physical_indices = self._prepare_weight_values(joints, weights, vertices, broadcast)
            if normalize:
                values, physical_indices = self._normalized_write(values, width, vertex_indices, physical_indices)
                width = len(physical_indices)
            influences = self._skin_fn.influenceObjects()
            # 削除済み influence によるマルチアトリビュートの穴を考慮し、物理番号をアトリビュートの論理番号へ変換する。
            logical_indices = [self._skin_fn.indexForInfluenceObject(influences[i]) for i in physical_indices]
            if fast:
                self._set_weight_values_fast(values, width, vertex_indices, logical_indices)
            else:
                self._set_weight_values_cmds(values, width, vertex_indices, logical_indices)
            return self

    def getVertexWeights(self, vertex, *, nonzero=False):
        """先頭のMeshの1つの頂点について、すべてのインフルエンスのウェイトを辞書で取得する。

        Args:
            vertex (Vertex | int | str): 先頭のMeshの頂点。Vertex、頂点の番号、または ``"mesh.vtx[3]"`` で指定する。
            nonzero (bool): Trueなら、値が0でないインフルエンスだけを返す。既定はFalse。

        Returns:
            dict[Node, float]: インフルエンスのオブジェクト(:meth:`getInfluences` と同じ型)からウェイトへの辞書。
                influenceObjects()の物理的な順番に並ぶ。そのまま :meth:`setVertexWeights` へ渡せる。
                値はシーンと切り離したコピーで、辞書を変えてもシーンには反映されない。

        Raises:
            TypeError: 頂点の入力の型が正しくない場合、またはnonzeroがboolでない場合。
            ValueError: 頂点が1つでない場合、または別の形状の頂点の場合。
            IndexError: 頂点の番号が範囲外の場合。
        """
        _require_bool(nonzero, "nonzero")
        index = self._single_vertex_index(vertex)
        paths = self._skin_fn.influenceObjects()
        row = self._read_rows([index], range(len(paths)))[0]
        return {Node._wrap_dag_path(path): value for path, value in zip(paths, row) if not nonzero or value != 0.0}

    def setVertexWeights(self, vertex, weights, normalize=True, *, fast=False):
        """先頭のMeshの1つの頂点に、インフルエンスごとのウェイトを設定する。

        ``setWeights(list(weights), list(weights.values()), vertices=[vertex], normalize=normalize)`` と同じ。

        - 既定の ``normalize=True`` では、指定したインフルエンスに指定した値を書く。指定しなかったインフルエンスは
          :meth:`setWeights` の正規化の規則で拡大・縮小(または0に)して、合計を1にする。
        - ``normalize=False`` では、指定したインフルエンスだけに値をそのまま書き、ほかは変えない。

        Args:
            vertex (Vertex | int | str): 先頭のMeshの頂点。Vertex、頂点の番号、または ``"mesh.vtx[3]"`` で指定する。
            weights (Mapping[str | Node, float]): 登録済みのインフルエンスからウェイトへの辞書。空にはできない。
                キーは名前かNodeのどちらかに揃える(:meth:`getVertexWeights` の戻り値のキーはNode)。
            normalize (bool): Trueなら、書き込んだ頂点を合計1へ正規化する。既定はTrue。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: weightsが辞書でない場合、頂点や値の型が正しくない場合、またはboolの引数がboolでない場合。
            ValueError: weightsが空の場合、インフルエンスが未登録・重複の場合、値が有限でない場合、
                頂点が1つでない・別の形状のものである場合、または正規化できない場合。
            IndexError: 頂点の番号が範囲外の場合。
            RuntimeError: Plugが編集できない場合、またはMayaが設定を拒否した場合。
        """
        with _edit_context("mlibSkinClusterSetVertexWeights", fast):
            if not isinstance(weights, Mapping):
                raise TypeError(f"weightsはインフルエンスからウェイトへのマッピングで指定してください: {type(weights).__name__}")
            if not weights:
                raise ValueError("weightsにはインフルエンスを1つ以上指定してください")
            index = self._single_vertex_index(vertex)
            self.setWeights(list(weights.keys()), list(weights.values()), vertices=[index], normalize=normalize, fast=fast)
            return self

    def getBlendWeights(self, *, vertices=None):
        """先頭のMeshの、頂点ごとのDQブレンドウェイト(``blendWeights``)を取得する。

        DQブレンドウェイトは、スキニングの方法が ``"weightBlended"`` のときに使う値で、頂点ごとに
        クラシックリニア(0)とデュアルクォータニオン(1)を混ぜる割合を表す。
        値が書かれていない頂点は、Mayaの既定と同じ0.0になる。

        Args:
            vertices (Vertex | Vertices | int | str | Iterable | None): 取得する頂点。Noneならすべての頂点。
                指定のしかたは :meth:`getWeights` と同じ。

        Returns:
            list[float]: 指定した順(Noneなら番号順)の値。変えてもシーンには反映されない。

        Raises:
            TypeError: 頂点の入力の型が正しくない場合。
            ValueError: 頂点が重複している・別の形状のものである場合。
            IndexError: 頂点の番号が範囲外の場合。
            RuntimeError: ノードが無効(削除済み)な場合。
        """
        self._require_valid("値の取得")
        vertex_indices = self._vertex_indices(vertices)
        if vertex_indices is None:
            vertex_indices = list(range(om2.MFnMesh(self.mesh_path).numVertices))
        if not vertex_indices:
            return []
        # 照会は番号の昇順の成分で行い、指定順へ並べ直す。
        ordered = sorted(vertex_indices)
        component_fn = om2.MFnSingleIndexedComponent()
        component = component_fn.create(om2.MFn.kMeshVertComponent)
        component_fn.addElements(ordered)
        values = dict(zip(ordered, self._skin_fn.getBlendWeights(self.mesh_path, component)))
        return [values[index] for index in vertex_indices]

    def setBlendWeights(self, weights, *, vertices=None, fast=False):
        """先頭のMeshの、頂点ごとのDQブレンドウェイト(``blendWeights``)を設定する。

        通常は、続いている頂点番号ごとに、範囲を指定した ``cmds.setAttr`` で書き込む。Undoが有効なら1回で戻せる。
        ``fast=True`` では、すべての対象を書き込めるかを先に調べてから ``MFnSkinCluster.setBlendWeights`` で書き込み、
        Undoには記録しない。スキニングの方法(:meth:`setSkinningMethod`)は変えない。

        Args:
            weights (Iterable[float]): 0以上1以下の値。対象の頂点と同じ数だけ渡し、verticesの指定の順に対応する。
            vertices (Vertex | Vertices | int | str | Iterable | None): 書き込む頂点。Noneならすべての頂点(番号順)。
                指定のしかたは :meth:`setWeights` と同じ。空なら何もしない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: weightsが数値の並びでない場合、頂点の入力の型が正しくない場合、またはfastがboolでない場合。
            ValueError: 値の数が頂点の数と違う場合、値が0〜1の有限の数でない場合、
                または頂点が重複している・別の形状のものである場合。
            IndexError: 頂点の番号が範囲外の場合。
            RuntimeError: ノードが無効な場合、blendWeightsがロックされている・入力が接続されている場合、
                またはMayaが設定を拒否した場合。
        """
        with _edit_context("mlibSkinClusterSetBlendWeights", fast):
            self._require_valid("ブレンドウェイトの設定")
            vertex_indices = self._vertex_indices(vertices)
            if vertex_indices is None:
                vertex_indices = list(range(om2.MFnMesh(self.mesh_path).numVertices))
            if isinstance(weights, (str, bytes)):
                raise TypeError("weightsは数値の並びで指定してください(文字列は指定できません)")
            try:
                values = list(weights)
            except TypeError:
                raise TypeError(f"weightsは数値の並びで指定してください: {type(weights).__name__}") from None
            if len(values) != len(vertex_indices):
                raise ValueError(f"ブレンドウェイトを{len(vertex_indices)}個指定してください: {len(values)}個")
            for value in values:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise TypeError(f"ブレンドウェイトは数値で指定してください: {type(value).__name__}")
                if not (math.isfinite(value) and 0.0 <= value <= 1.0):
                    raise ValueError(f"ブレンドウェイトは0〜1の有限な値で指定してください: {value}")
            if not vertex_indices:
                return self
            if fast:
                array = self._dependency_fn().findPlug("blendWeights", False)
                require_writable(array)
                for index in vertex_indices:
                    require_writable(array.elementByLogicalIndex(index))
                pairs = sorted(zip(vertex_indices, values))
                component_fn = om2.MFnSingleIndexedComponent()
                component = component_fn.create(om2.MFn.kMeshVertComponent)
                component_fn.addElements([index for index, _ in pairs])
                self._skin_fn.setBlendWeights(self.mesh_path, component, om2.MDoubleArray([float(value) for _, value in pairs]))
                return self
            name = self.getFullName()
            for start, first, count in self._consecutive_runs(vertex_indices):
                set_attr(f"{name}.blendWeights[{first}:{first + count - 1}]", *(float(value) for value in values[start : start + count]))
            return self

    def getWeightsData(self):
        """すべての頂点のウェイトとスキニングの設定を、``mlib.skinWeights`` 形式の辞書で取得する。

        :meth:`exportWeights` が書き出すデータそのもので、:meth:`setWeightsData` へ渡せる。
        値は丸めない。シーンは変えない。

        データの形(版1):

        - ``geometry``: 先頭のジオメトリ(Shape)の参照(:class:`mlib.json.NodeRef` の辞書)。
        - ``vertexCount``: 頂点の数。
        - ``influences``: インフルエンスの参照のlist。influenceObjects()の物理的な順番に並ぶ。以下の「influenceの位置」や
          「インフルエンスの位置」は、このlistの中の位置を指す。
        - ``influenceLocks``: インフルエンスごとのウェイトのロック(lockInfluenceWeights)。``influences`` と同じ順。
        - ``weights``: 0でない値だけを持つ形。``{"indices": [[...], ...], "values": [[...], ...]}`` で、
          頂点ごとにインフルエンスの位置と値を並べる(i番目の頂点は ``indices[i]`` と ``values[i]``)。
        - ``blendWeights``: 頂点ごとのDQブレンドウェイト(blendWeights)。
        - ``positions``: 頂点ごとの位置 ``[x, y, z]``。skinClusterに入る前の形状の、オブジェクト空間での位置(cm)。
          ``method="position"`` での対応付けに使う。
        - ``settings``: ``skinningMethod``・``normalizeWeights`` (名前)、``maxInfluences`` (int)、
          ``maintainMaxInfluences`` (bool)。
        - ``ngSkinLayers``: ngSkinTools2のレイヤーのlist。レイヤーが無い場合と、ngSkinTools2を使えない場合はNone。
          各レイヤーは ``name``・``enabled``・``opacity``・``parent`` (親レイヤーのlistの中の位置、またはNone)・
          ``index`` (親の中での順番)・``weights`` (``[[influenceの位置, 頂点ごとの値], ...]``)・
          ``mask``・``dq`` (頂点ごとの値、またはNone)を持つ。

        Returns:
            dict: 上の形の辞書。数値・文字列・list・辞書だけを含み、そのままJSONへ書ける。

        Raises:
            RuntimeError: skinClusterかジオメトリが無効な場合。

        Examples:
            .. code-block:: python

                data = skin.getWeightsData()
                other.setWeightsData(data, namespaceMap={"chrA": "chrB"})
        """
        # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
        from ..json.nodeRef import NodeRef

        self._require_valid("値の取得")
        component, count = self._all_vertices()
        paths = self._skin_fn.influenceObjects()
        width = len(paths)
        flat = list(self._skin_fn.getWeights(self.mesh_path, component)[0]) if count else []
        indices, values = [], []
        for start in range(0, count * width, width):
            row = flat[start : start + width]
            used = [index for index, value in enumerate(row) if value != 0.0]
            indices.append(used)
            values.append([row[index] for index in used])
        blend = list(self._skin_fn.getBlendWeights(self.mesh_path, component)) if count else []
        return {
            "geometry": NodeRef.capture(self.mesh_path).toData(),
            "vertexCount": count,
            "influences": [NodeRef.capture(path).toData() for path in paths],
            "influenceLocks": [self._influence_locked(path) for path in paths],
            "weights": {"indices": indices, "values": values},
            "blendWeights": blend,
            "positions": [[point.x, point.y, point.z] for point in self._input_points()],
            "settings": {
                "skinningMethod": self.getSkinningMethod(),
                "maxInfluences": int(self.getMaxInfluences()),
                "maintainMaxInfluences": self.isMaintainingMaxInfluences(),
                "normalizeWeights": self.getNormalizeMode(),
            },
            "ngSkinLayers": self._capture_ngskin_layers(paths),
        }

    def setWeightsData(self, data, *, nameMap=None, replace=None, namespaceMap=None, method="index", fast=False):
        """:meth:`getWeightsData` の辞書から、ウェイトとスキニングの設定をこのskinClusterへ書き戻す。

        保存したインフルエンスは、名前の対応付け(``nameMap``・``replace``・``namespaceMap``。規則は
        :class:`mlib.json.NameMapping`)で、シーンのノードに対応させる。

        - シーンにはあるが、このskinClusterのインフルエンスではないノードは、ウェイト0で追加してから書く。
        - シーンに無いインフルエンスは、結果の報告の ``missing`` に記録して警告する。その値を除いた残りを、
          比率を保って頂点ごとの元の合計まで拡大する。残りがすべて0の頂点は書き換えず、``skipped`` に記録する。
        - 保存したデータに無いインフルエンス(このskinClusterだけにあるインフルエンス)の値は0にする。
        - DQブレンドウェイトと、スキニングの設定(方法・最大インフルエンス数・それを保つか・正規化)を書く。
          ウェイトのロックは保存した状態にする(保存したデータに無いインフルエンスのロックは変えない)。
          ロックされている・入力が接続されている設定は書かずに、``skipped`` に記録する。
        - ``ngSkinLayers`` があり、ngSkinTools2を使える場合は、すでにあるレイヤーを消して、保存したレイヤーを
          作り直す(合成した結果のウェイトはngSkinTools2が書く)。使えない場合は ``skipped`` に記録して、
          合成した結果のウェイトだけを書く。保存したデータにレイヤーが無く、このskinClusterにレイヤーがある場合は、
          レイヤーを変えずに ``skipped`` に記録する。

        頂点の対応付けは ``method`` で選ぶ。

        - ``method="index"``: 頂点の番号で対応させる。頂点の数が違えば、何も変えずにValueErrorにする。
        - ``method="position"``: 各頂点に、保存した位置(skinClusterに入る前の形状のオブジェクト空間)がいちばん近い
          保存した頂点の値(ウェイト・DQブレンドウェイト・レイヤーの値)を使う。頂点の数が違うメッシュにも使える。

        Args:
            data (dict): :meth:`getWeightsData` の形の辞書。
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。
            method (str): 頂点の対応付けの方法。``"index"`` (既定)か ``"position"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。``MFnSkinCluster.setWeights`` を使う。

        Returns:
            ValidationReport: 見つからなかったインフルエンス(missing)と、書かなかったもの(skipped)。

        Raises:
            TypeError: 引数の型が正しくない場合。
            ValueError: データの形が正しくない場合、methodが正しくない場合、``method="index"`` で頂点の数が違う場合、または
                保存したインフルエンスが1つもシーンに無い場合。どの場合もシーンは変えない。
            RuntimeError: ウェイトが編集できない場合、またはMayaが設定を拒否した場合。通常の書き込みでは、元に戻す。

        Note:
            通常の書き込みは、全体を1回のUndoにまとめ(cmds.setAttr)、途中で失敗したら元に戻す。``fast=True`` はUndoに
            記録しない。ただし、インフルエンスの追加(``cmds.skinCluster``)と、ngSkinTools2のレイヤーの作成は、
            ``fast=True`` でもMayaのコマンドで行う。
        """
        # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
        from ..json.nameMapping import NameMapping

        _require_bool(fast, "fast")
        self._require_choice(method, "method", ("index", "position"))
        saved, nodes, report = self._prepare_weights_data(data, NameMapping(nameMap, replace, namespaceMap), method)
        with _edit_context("mlibSkinClusterSetWeightsData", fast, transaction=True):
            self._apply_weights_data(saved, nodes, method, report, fast)
        report.warn(f"SkinCluster {self.getName()}")
        return report

    def exportWeights(self, path):
        """:meth:`getWeightsData` のデータを、ヘッダー付きのJSONファイルへ書き出す。

        ファイルの形式は ``mlib.skinWeights`` の版1。

        Args:
            path (str | os.PathLike): 書き出し先。フォルダーは作らない。

        Returns:
            pathlib.Path: 書き出したファイルの絶対パス。

        Raises:
            RuntimeError: skinClusterかジオメトリが無効な場合。
            OSError: 書き出しに失敗した場合。

        Examples:
            .. code-block:: python

                skin.exportWeights("body_weights.json")
                skin.importWeights("body_weights.json", method="position")
        """
        # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
        from ..json import file

        return file.dump(self.getWeightsData(), path, self._WEIGHTS_FORMAT, self._WEIGHTS_VERSION)

    def importWeights(self, path, *, nameMap=None, replace=None, namespaceMap=None, method="index", fast=False):
        """:meth:`exportWeights` のファイルを読み込み、書き戻す。

        書き戻す規則は :meth:`setWeightsData` と同じ。

        Args:
            path (str | os.PathLike): ``mlib.skinWeights`` の版1のファイル。
            nameMap (dict[str, str] | None): 名前空間を除いた名前の対応表。
            replace (Iterable[tuple[str, str]] | None): 順に当てる文字列の置き換え。
            namespaceMap (dict[str, str] | None): 名前空間の対応。
            method (str): 頂点の対応付けの方法。``"index"`` (既定)か ``"position"``。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            ValidationReport: 見つからなかったインフルエンスと、書かなかったもの。

        Raises:
            TypeError: 引数の型が正しくない場合。
            ValueError: 形式の名前・版・データの形が正しくない場合、methodが正しくない場合、
                ``method="index"`` で頂点の数が違う場合、または保存したインフルエンスが1つもシーンに無い場合。
            OSError: 読み込みに失敗した場合。
            RuntimeError: ウェイトが編集できない場合、またはMayaが設定を拒否した場合。
        """
        # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
        from ..json import file

        _, data = file.load(path, self._WEIGHTS_FORMAT, self._WEIGHTS_VERSION)
        return self.setWeightsData(data, nameMap=nameMap, replace=replace, namespaceMap=namespaceMap, method=method, fast=fast)

    def invertShape(self, sculpted, name=None):
        """今のポーズで形を整えたメッシュから、スキンの変形を逆にかけた補正の形状を作る。

        考え方はcvShapeInverterと同じ。

        1. 各頂点で、スキンが使うマトリクス(``geomMatrix``・``bindPreMatrix``・``matrix``)をウェイトで
           重み付けして足し合わせる(classicLinearの変形)。envelopeも考えに入れる。
        2. その逆マトリクスをsculptedの頂点に掛けて、skinClusterに入る前の空間での形状を求める。

        結果は、skinClusterが変形している先頭のメッシュを同じ親の下に複製し、頂点を置き換えて作る。
        結果を、このメッシュのblendShapeのターゲットとして(skinClusterより前に)足すと、
        今のポーズでsculptedと同じ形になる。複製と頂点の書き込みは、1回のUndoで戻せる。fast引数は持たない。

        Args:
            sculpted (str | Node): 今のポーズで形を整えたメッシュ(transformか、meshのshape)。
                頂点の番号と数が、先頭のメッシュと同じであること。位置はオブジェクト空間の座標を使うので、
                横へ動かした複製でもよい。
            name (str | None): 作るメッシュのtransformの名前。Noneなら ``<sculptedの名前>_inverted``。

        Returns:
            Mesh: 作ったメッシュのshape。

        Raises:
            TypeError: sculptedがメッシュでない場合、またはnameが文字列でもNoneでもない場合。
            ValueError: 頂点の数が先頭のメッシュと違う場合、またはnameが空文字列の場合。
            RuntimeError: 名前からノードを特定できない場合、またはMayaが複製や書き込みを拒否した場合。

        Note:
            skinClusterより前に別のデフォーマーがある場合は、その出力(skinClusterの入力)と元の形状(Orig)の差を足し戻す。
            そのため、blendShapeのように位置を足すだけのデフォーマーは、今の値のまま正しく扱える。
            これは、ターゲットの形状を削除して差分だけになったblendShapeの場合で、ターゲットの形状を
            つないだままのblendShapeは入力に対する絶対的な位置として働くため、その分ずれる。
            回転・拡大を伴うデフォーマー(cluster・nonLinearなど)の効果は逆にしないため、その分ずれる。
            skinningMethodがdualQuaternion・weightBlendedの場合も、線形の変形として逆にするので、おおよその結果になる。
            スキンのマトリクスの和が特異な(ウェイトがほぼ0の)頂点は、skinClusterの入力の位置をそのまま使う。
            頂点の書き込みには :meth:`Mesh.setPoints <mlib.nodes.mesh.Mesh.setPoints>` を使うので、
            頂点の数に比例して時間がかかる。
        """
        # nodes の初期化順に依存しないよう、使う時点で読み込む。
        from .mesh import Mesh

        if name is not None and not isinstance(name, str):
            raise TypeError("nameは文字列かNoneで指定してください")
        if name == "":
            raise ValueError("nameは空でない文字列かNoneで指定してください")
        target = Node(Object._input_name(sculpted))
        if isinstance(target, DagNode):
            target = target.getShape()
        if not isinstance(target, Mesh):
            raise TypeError(f"sculptedはメッシュで指定してください: {Object._input_name(sculpted)}")
        sculpted_points = om2.MFnMesh(target.mpath()).getPoints(om2.MSpace.kObject)
        count = om2.MFnMesh(self.mesh_path).numVertices
        if len(sculpted_points) != count:
            raise ValueError(f"sculptedの頂点数は{len(sculpted_points)}です。{count}が必要です")
        points = self._inverted_points(sculpted_points)
        if name is None:
            name = target.getParent().getName().split("|")[-1] + "_inverted"
        with undoChunk("mlibSkinClusterInvertShape"):
            transform = om2.MFnDagNode(self.mesh_path.transform()).fullPathName()
            duplicate = cmds.duplicate(transform, name=name, returnRootsOnly=True)[0]
            duplicate_path = cmds.ls(duplicate, long=True)[0]
            shapes = cmds.listRelatives(duplicate_path, shapes=True, fullPath=True) or []
            intermediate = [shape for shape in shapes if cmds.getAttr(shape + ".intermediateObject")]
            if intermediate:
                cmds.delete(intermediate)
            children = [child for child in cmds.listRelatives(duplicate_path, children=True, fullPath=True) or [] if child not in shapes]
            if children:
                cmds.delete(children)
            shape = Node(cmds.listRelatives(duplicate_path, shapes=True, fullPath=True)[0])
            shape.setPoints(points)
            return shape

    def redistributeWeights(self, vertices, method="cubic"):
        """先頭のMeshの頂点ウェイトを正規化し、イージングをかけてから、もう一度正規化する。

        頂点の番号はint()で変換し、重複を除いて小さい順に処理する。
        頂点ごとに読み取り・計算・書き込みを行い、すべての頂点を書き込めるかは先に確かめない。
        0のインフルエンスは0のまま。linearでも合計1へ正規化する。
        処理の大半が頂点ごとの読み取りと計算で、OpenMayaで書いても速くならないため、fast引数は持たない。

        Args:
            vertices (Vertex | Vertices | Iterable[int | Vertex]): 頂点、または番号の並び。
                Vertex・Verticesは先頭のMeshのものだけを指定できる。空なら何も変えない。
            method (str): mlib.maths.easing.CURVESにある曲線の名前。既定はcubic。

        Returns:
            None: 値を返さない。途中で失敗しても、それより前の頂点・列の変更は自動では戻さない。

        Raises:
            TypeError: methodが文字列でない場合、または頂点の入力を変換できない型の場合。
            ValueError: 曲線の名前が正しくない場合、別の形状の頂点の場合、頂点の番号を変換できない場合、
                ウェイトの合計が0以下の場合、またはイージングの計算ができない場合。
            IndexError: 頂点の番号が今の範囲の外の場合。
            RuntimeError: Mayaが読み取りや書き込みを拒否した場合。
        """
        with undoChunk("mlibSkinClusterRedistributeWeights"):
            if not isinstance(method, str):
                raise TypeError(f"イージングの方法はstrで指定してください: {type(method).__name__}")
            curve = method
            if curve not in easing.CURVES:
                raise ValueError(f"対応していないイージングの方法です: {method}")
            num_vertices = om2.MFnMesh(self.mesh_path).numVertices
            # 循環参照の回避: components は nodes を参照するため、使う時点で読み込む。
            from ..components.vertex import Vertex, Vertices

            if isinstance(vertices, Vertices):
                if vertices.shape.mnode() != self._mesh_node():
                    raise ValueError("頂点はこのskinClusterの最初のメッシュのものを指定してください")
                vertices = vertices.indices
            elif isinstance(vertices, Vertex):
                vertices = [vertices]
            vertex_indices = set()
            for vertex in vertices:
                if isinstance(vertex, Vertex):
                    if vertex.shape.mnode() != self._mesh_node():
                        raise ValueError("頂点はこのskinClusterの最初のメッシュのものを指定してください")
                    vertex = vertex.index
                # 既存番号入力のint変換を維持し、新しい頂点参照だけを所有者検証する。
                vertex_indices.add(int(vertex))
            vertex_indices = sorted(vertex_indices)
            for vertex in vertex_indices:
                if not (0 <= vertex < num_vertices):
                    raise IndexError(f"頂点番号が範囲外です: {vertex}")
            if not vertex_indices:
                return
            influence_paths = self._skin_fn.influenceObjects()
            all_indices = om2.MIntArray(range(len(influence_paths)))
            logical_indices = [self._skin_fn.indexForInfluenceObject(path) for path in influence_paths]
            name = self.getFullName()
            for vertex in vertex_indices:
                component_fn = om2.MFnSingleIndexedComponent()
                component = component_fn.create(om2.MFn.kMeshVertComponent)
                component_fn.addElement(vertex)
                row = list(self._skin_fn.getWeights(self.mesh_path, component, all_indices))
                total = sum(row)
                if total <= 0.0:
                    raise ValueError(f"頂点{vertex}に再配分するウェイトがありません")
                normalized = [value / total for value in row]
                eased = [easing.ease(value, curve) for value in normalized]
                eased_total = sum(eased)
                if eased_total <= 0.0:
                    raise ValueError(f"頂点{vertex}でウェイトの合計が0になりました")
                final = [value / eased_total for value in eased]
                for logical_index, value in zip(logical_indices, final):
                    set_attr(f"{name}.weightList[{vertex}].weights[{logical_index}]", value)

    def transferWeights(self, sourceTargetPairs, *, fast=False):
        """sourceとtargetの組ごとに、sourceのウェイトをtargetへ移す。

        組は指定した順に処理し、sourceが影響している頂点だけを変える。

        - すべての組の参照と登録を確かめてから処理する。同じインフルエンスどうしの組は飛ばす。
        - targetへは足し算せず、sourceの値で置き換える。そしてsourceを0にする。sourceが0の頂点は変えない。
        - 通常は、skinPercentとnormalizeWeightsの設定に従う。選択はpreservedSelectionで戻そうとする。
        - fastでは、ジオメトリが1つであることと、編集できるかを確かめ、interactiveの正規化と同じ結果にする。

        途中で失敗しても、それまでに終わった変更は戻さない。

        Args:
            sourceTargetPairs (Iterable[tuple[Node | str, Node | str]]): 登録済みのインフルエンスの組。
                Maya APIのノードの参照も受け付ける。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 組を順に取り出せない場合、対応していない参照の型の場合、またはfastがboolでない場合。
            ValueError: 組が2つの要素でない場合、または未登録のインフルエンスの場合。
            RuntimeError: レイヤー・ロックなどのために編集できない場合、またはMayaの処理が失敗した場合。
            NotImplementedError: fastで、ジオメトリが1つでない場合。
        """
        with _edit_context("mlibSkinClusterTransferWeights", fast):
            self._raise_if_layers()

            pairs = []
            for pair in sourceTargetPairs:
                if isinstance(pair, (str, bytes)):
                    raise ValueError("コピー元とコピー先の組を指定してください(文字列は指定できません)")
                pair = tuple(pair)
                if len(pair) != 2:
                    raise ValueError("1組あたりインフルエンスをちょうど2つ指定してください")
                source, target = (Node._resolve_input(value) for value in pair)
                if any(not node.isValid() or not self.hasInfluence(node.getFullName()) for node in (source, target)):
                    raise ValueError("両方のノードをこのskinClusterのインフルエンスにしてください")
                if source.getUuid() != target.getUuid():
                    pairs.append((source.getFullName(), target.getFullName()))
            if fast:
                # 循環参照の回避: core は nodes を参照するため、使う時点で読み込む。
                from ..core.skinEdit import transfer_weights

                transfer_weights(self, pairs)
            else:
                with preservedSelection():
                    for source_joint, target_joint in pairs:
                        self._transfer_pair(source_joint, target_joint)

    def removeInfluence(self, joint, transferToParent=True, *, force=False):
        """ウェイトを祖先のインフルエンスへ足してから、登録を外す。ノードそのものは削除しない。

        ウェイトの移し先は、同じskinClusterの中で最も近い祖先のインフルエンス。
        元のウェイトをそのまま足してsourceを0にし、登録を外す。

        - 書き込むのは、sourceにウェイトがある頂点の2つの列だけ。ロックや入力の接続も、その要素についてだけ拒否する。
        - 登録の解除と残りの配り直しは、``cmds.skinCluster(edit=True, removeInfluence=...)`` に任せる。
        - ウェイトのロックは一時的に外してから外し、元の状態へ戻す。
        - ngSkinTools2のレイヤーは、レイヤーごとにウェイトを移す。ngSkinTools2を使えない場合のレイヤーは
          拒否せず、skinClusterのウェイトだけを書き換える。

        最後の1つのインフルエンスは外せない。Undoが有効なら1つのチャンクにまとめて記録する。fast引数は持たない。
        修正・移し替え・解除を順に行い、後で失敗しても、それまでに終わった変更は戻さない。

        Args:
            joint (Joint | str): 登録を外すインフルエンス。
            transferToParent (bool): Trueなら、祖先へウェイトを移す。Falseの場合と、祖先が無い場合は、Maya標準の配り直しになる。
            force (bool): Trueなら、正しくないウェイトを直してから処理する。直すときに正規化はしない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: transferToParent・forceがboolでない場合。
            ValueError: 登録されていない場合、または最後の1つのインフルエンスの場合。
            RuntimeError: ウェイトの要素がロックされている・入力が接続されている場合、またはMayaの編集が失敗した場合。
        """
        with undoChunk("mlibSkinClusterRemoveInfluence"):
            with _unlocked_influences([self]):
                plans, snapshot = self._influence_removal_plans([joint], transferToParent, force=force)
                self._apply_influence_removals(plans, snapshot, force=force)

    def normalizeWeights(self, decimals=None, *, fast=False):
        """先頭のMeshの各頂点で、登録されているすべてのインフルエンスのウェイトを合計1へ正規化する。

        すべての頂点を計算して確かめてから、setWeightsへ渡す。次のどれかがあれば拒否する。

        - 負の値・有限でない値・合計が0の頂点
        - インフルエンスのlockInfluenceWeights
        - すでにあるウェイトのロックや入力の接続
        - レイヤーと思われる接続

        normalizeWeightsの設定そのものは変えない。

        Args:
            decimals (int | None): 小数点以下の桁数。0〜15で指定する。boolは指定できない。Noneなら丸めない。
                桁数を指定したときは、最大剰余法で10進数での合計1を保つ。値が並んだときは、influenceObjects()の
                物理的な順番で前にあるものを優先する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            SkinCluster: 自身。インフルエンスの登録数とnormalizeWeightsの設定は変えない。

        Raises:
            TypeError: fastがboolでない場合。
            ValueError: 桁数が正しくない場合、インフルエンスが無い場合、または負の値・有限でない値・合計が0の頂点がある場合。
            RuntimeError: ロック・入力の接続・レイヤーと思われる接続がある場合、またはMayaの編集が失敗した場合。

        Note:
            レイヤーかどうかは、接続している相手の名前や型を決まった文字列と比べて判定する。実際のレイヤーのデータは調べない。
            保存するときにfloatへ戻すため、2進数の浮動小数点で厳密に合計が1になることは保証しない。
            書き込みの途中で失敗しても、それまでに終わった変更は自動では戻さない。
        """
        with _edit_context("mlibSkinClusterNormalizeWeights", fast):
            names, values = self._normalized_weights(decimals)
            self.setWeights(names, values, fast=fast)
            return self

    def getMaxInfluences(self):
        """maxInfluencesの設定値を取得する。

        Returns:
            int: skinClusterのmaxInfluencesの設定値。実際に0でないウェイトを持つインフルエンスの数ではない。
        """
        return self.getPlug("maxInfluences").get()

    def setMaxInfluences(self, count, maintain=True, prune=False, *, fast=False):
        """最大インフルエンス数の設定を変える。必要なら、先頭のMeshの0でない列の数も制限する。

        maxInfluencesとmaintainMaxInfluencesはPlugで設定し、skinClusterの編集コマンドでのバインドし直しは使わない。

        - prune=False: 設定の2つのPlugだけを確かめる。すべてのウェイトやレイヤーは調べない。
        - prune=True: すべてのウェイトが編集できるかと、正規化した結果を先に確かめる。

        Args:
            count (int): 最大インフルエンス数。1〜2147483647で指定する。boolは指定できない。
                登録されているインフルエンスの数より大きい値も受け付ける。
            maintain (bool): maintainMaxInfluencesへ設定する値。
            prune (bool): Trueなら、各頂点で値の大きいcount個の列だけを残し、ほかの列を0にして正規化する。
                値が並んだときは物理的な順番で前にあるものを優先する。インフルエンスの登録は削除しない。
                Falseなら、すでにある値は変えない。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            SkinCluster: 自身。通常の書き込みは、Undoが有効なら同じチャンクに記録する。

        Raises:
            TypeError: maintain・prune・fastがboolでない場合。
            ValueError: countが正しくない場合、またはprune=Trueでウェイトを正規化できない場合。
            RuntimeError: 設定がロックされている・入力が接続されている場合、pruneで編集できない場合、
                またはMayaの設定が失敗した場合。

        Note:
            maxInfluences、maintainMaxInfluences、pruneした値の順に設定する。
            後の書き込みに失敗しても、先に変えた設定や値を自動で戻す処理は持たない。
        """
        with _edit_context("mlibSkinClusterSetMaxInfluences", fast):
            if type(count) is not int or not 1 <= count <= 2147483647:
                raise ValueError("countは正の32ビット整数で指定してください")
            _require_bool(maintain, "maintain")
            _require_bool(prune, "prune")
            settings = [self.getPlug(attr) for attr in ("maxInfluences", "maintainMaxInfluences")]
            for plug in settings:
                if plug.mplug().isFreeToChange() != om2.MPlug.kFreeToChange:
                    attr = plug.getLongName()
                    raise RuntimeError(f"設定がロックされているか、接続されています: {attr}")
            computed = self._normalized_weights(limit=count) if prune else None
            settings[0].set(count, fast=fast)
            settings[1].set(maintain, fast=fast)
            if computed:
                self.setWeights(*computed, fast=fast)
            return self

    def isMaintainingMaxInfluences(self):
        """ペイントなどの編集で、最大インフルエンス数を保つ設定(maintainMaxInfluences)かを判定する。

        Returns:
            bool: maintainMaxInfluencesが有効ならTrue。
        """
        return bool(self.getPlug("maintainMaxInfluences").get())

    def getSkinningMethod(self):
        """スキニングの方法(skinningMethod)を取得する。

        Returns:
            str: ``"classicLinear"``・``"dualQuaternion"``・``"weightBlended"`` のどれか。
        """
        return self._SKINNING_METHODS[int(self.getPlug("skinningMethod").get())]

    def setSkinningMethod(self, method):
        """スキニングの方法(skinningMethod)を設定する。

        fast引数は持たない(1つのsetAttrで、OpenMayaで書いても速くならないため)。

        Args:
            method (str): ``"classicLinear"``・``"dualQuaternion"``・``"weightBlended"`` のどれか。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: methodが文字列でない場合。
            ValueError: methodが上の名前のどれでもない場合。
            RuntimeError: アトリビュートがロック・入力接続されている場合。
        """
        with undoChunk("mlibSkinClusterSetSkinningMethod"):
            self._require_choice(method, "method", self._SKINNING_METHODS)
            self.getPlug("skinningMethod").set(self._SKINNING_METHODS.index(method))
            return self

    def getNormalizeMode(self):
        """ウェイトの正規化の方法(normalizeWeights)を取得する。

        Returns:
            str: ``"none"``・``"interactive"``・``"post"`` のどれか。
        """
        return self._NORMALIZE_MODES[int(self.getPlug("normalizeWeights").get())]

    def setNormalizeMode(self, mode):
        """ウェイトの正規化の方法(normalizeWeights)を設定する。

        既存のウェイトは書き換えない(正規化し直すには :meth:`normalizeWeights` を使う)。
        fast引数は持たない(1つのsetAttrで、OpenMayaで書いても速くならないため)。

        Args:
            mode (str): ``"none"``・``"interactive"``・``"post"`` のどれか。

        Returns:
            SkinCluster: 自身。

        Raises:
            TypeError: modeが文字列でない場合。
            ValueError: modeが上の名前のどれでもない場合。
            RuntimeError: アトリビュートがロック・入力接続されている場合。
        """
        with undoChunk("mlibSkinClusterSetNormalizeMode"):
            self._require_choice(mode, "mode", self._NORMALIZE_MODES)
            self.getPlug("normalizeWeights").set(self._NORMALIZE_MODES.index(mode))
            return self

    def _prepare_weights_data(self, data, mapping, method):
        """:meth:`setWeightsData` の検査を行い、適用に使う値を返す。シーンは変更しない。

        Args:
            data (dict): :meth:`getWeightsData` の形の辞書。
            mapping (NameMapping): 名前の対応付け。
            method (str): ``"index"`` または ``"position"``。

        Returns:
            tuple[dict, list[Node | None], ValidationReport]: 検査済みのデータ、保存した
                influenceごとのシーンのノード(見つからなければNone)、missingを記録した報告。

        Raises:
            ValueError: データの形が不正、``method="index"`` で頂点数が違う、位置が無い、または
                保存したinfluenceが1つもシーンに無い場合。
        """
        # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
        from ..json.snapshot import ValidationReport

        saved = self._parse_weights_data(data)
        report = ValidationReport()
        count = om2.MFnMesh(self.mesh_path).numVertices
        if method == "index" and saved["vertexCount"] != count:
            report.addError(f"保存された頂点数({saved['vertexCount']})が{self.mesh}の頂点数({count})と合っていません。method='position'を使います")
        if method == "position" and not saved["positions"]:
            report.addError("データに頂点の位置がありません")
        if not report.valid:
            raise ValueError(f"スキンウェイトを適用できません: {'; '.join(report.errors)}")
        nodes = [ref.resolve(mapping) for ref in saved["influences"]]
        for ref, node in zip(saved["influences"], nodes):
            if node is None:
                report.addMissing(ref.mappedName(mapping))
        if all(node is None for node in nodes):
            raise ValueError(f"保存されたインフルエンスがシーンに1つもありません: {', '.join(report.missing)}")
        return saved, nodes, report

    def _apply_weights_data(self, saved, nodes, method, report, fast):
        """検査済みのデータを書き戻す(:meth:`setWeightsData` の本体)。Undoの文脈は呼出し側が持つ。

        Args:
            saved (dict): :meth:`_parse_weights_data` の戻り値。
            nodes (list[Node | None]): 保存したinfluenceごとのシーンのノード。
            method (str): ``"index"`` または ``"position"``。
            report (ValidationReport): 書かなかったものの記録先。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            None: 値を返さない。
        """
        registered = {self._path_uuid(path) for path in self._skin_fn.influenceObjects()}
        adding = []
        for node in nodes:
            if node is not None and node.getUuid() not in registered:
                registered.add(node.getUuid())
                adding.append(node.getFullName())
        if adding:
            cmds.skinCluster(self.getFullName(), edit=True, addInfluence=adding, weight=0.0)
        paths = self._skin_fn.influenceObjects()
        physical = {self._path_uuid(path): index for index, path in enumerate(paths)}
        columns = [None if node is None else physical[node.getUuid()] for node in nodes]
        logical = [self._skin_fn.indexForInfluenceObject(path) for path in paths]
        sources = self._weight_sources(saved, method)
        vertices, values = self._weight_rows(saved, columns, len(paths), sources, report)
        original_locks = [self._influence_locked(path) for path in paths]
        locks = list(original_locks)
        for column, state in zip(columns, saved["influenceLocks"]):
            if column is not None:
                locks[column] = state
        # 書込み中はロックを外し、最後に保存したロックへ揃える。
        for path, locked in zip(paths, original_locks):
            if locked:
                Node._wrap_dag_path(path).getPlug("lockInfluenceWeights").set(False, fast=fast)
        if vertices:
            if fast:
                component_fn = om2.MFnSingleIndexedComponent()
                component = component_fn.create(om2.MFn.kMeshVertComponent)
                component_fn.addElements(vertices)
                self._skin_fn.setWeights(self.mesh_path, component, om2.MIntArray(range(len(paths))), om2.MDoubleArray(values), False)
            else:
                self._set_weight_values_cmds(values, len(paths), vertices, logical)
        self._write_blend_weights(saved["blendWeights"], sources, fast)
        self._apply_weight_settings(saved["settings"], report, fast)
        self._apply_ngskin_layers(saved["ngSkinLayers"], columns, logical, sources, report, fast)
        for path, state in zip(paths, locks):
            node = Node._wrap_dag_path(path)
            if state and node.hasAttr("lockInfluenceWeights"):
                node.getPlug("lockInfluenceWeights").set(True, fast=fast)

    def _weight_sources(self, saved, method):
        """現在の各頂点が値を使う、保存した頂点の番号を返す。

        Args:
            saved (dict): 検査済みのデータ。
            method (str): ``"index"`` は同じ番号、``"position"`` は最も近い保存位置の頂点。

        Returns:
            Sequence[int]: 現在の頂点番号順の、保存した頂点の番号。
        """
        if method == "index":
            return range(saved["vertexCount"])
        grid = _PointGrid(saved["positions"])
        return [grid.nearest((point.x, point.y, point.z))[0] for point in self._input_points()]

    def _weight_rows(self, saved, columns, width, sources, report):
        """今の頂点ごとに、すべてのインフルエンス(物理的な順番)のウェイトの行を作る。シーンは変えない。

        見つからないインフルエンスの値は除き、残りを比率を保って元の合計まで拡大する。
        残りがすべて0の頂点は書かずに、reportへ記録する。

        Args:
            saved (dict): 確かめたデータ。
            columns (list[int | None]): 保存したインフルエンスごとの、今の物理的な番号。見つからなければNone。
            width (int): 今のインフルエンスの数。
            sources (Sequence[int]): 今の頂点ごとの、保存した頂点の番号。
            report (ValidationReport): 書かない頂点の記録先。

        Returns:
            tuple[list[int], list[float]]: 書き込む頂点の番号(小さい順)と、頂点の順・物理的な順番で1列に並べた値。
        """
        indices, weights = saved["weights"]
        rows = {}
        vertices, values = [], []
        for vertex, source in enumerate(sources):
            if source not in rows:
                row = [0.0] * width
                dropped = 0.0
                for index, value in zip(indices[source], weights[source]):
                    column = columns[index]
                    if column is None:
                        dropped += value
                    else:
                        row[column] += value
                if dropped:
                    kept = sum(row)
                    row = [value * (kept + dropped) / kept for value in row] if kept > 0.0 else None
                rows[source] = row
            row = rows[source]
            if row is None:
                report.addSkipped(f"{self.mesh}.vtx[{vertex}]", "存在しないインフルエンスだけにウェイトがあります")
                continue
            vertices.append(vertex)
            values.extend(row)
        return vertices, values

    def _write_blend_weights(self, blend, sources, fast):
        """DQブレンドウェイトを、現在の値と違う場合だけ全頂点へ書く。

        Args:
            blend (list[float] | None): 保存した頂点ごとの値。Noneは書かない。
            sources (Sequence[int]): 現在の頂点ごとの、保存した頂点の番号。
            fast (bool): TrueはMFnSkinCluster.setBlendWeights、Falseは範囲指定の1回のsetAttr。

        Returns:
            None: 値を返さない。
        """
        if blend is None or not len(sources):
            return
        values = [blend[source] for source in sources]
        component, count = self._all_vertices()
        if list(self._skin_fn.getBlendWeights(self.mesh_path, component)) == values:
            return
        if fast:
            self._skin_fn.setBlendWeights(self.mesh_path, component, om2.MDoubleArray(values))
        else:
            set_attr(f"{self.getFullName()}.blendWeights[0:{count - 1}]", *values)

    def _apply_weight_settings(self, settings, report, fast):
        """スキニングの設定を、現在の値と違うものだけ書く。書けない設定はreportへ記録する。

        Args:
            settings (dict): 検査済みの ``settings``。
            report (ValidationReport): 書かなかった設定の記録先。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            None: 値を返さない。
        """
        values = {
            "skinningMethod": self._SKINNING_METHODS.index(settings["skinningMethod"]),
            "maxInfluences": settings["maxInfluences"],
            "maintainMaxInfluences": settings["maintainMaxInfluences"],
            "normalizeWeights": self._NORMALIZE_MODES.index(settings["normalizeWeights"]),
        }
        for attr, value in values.items():
            if value is None:
                continue
            plug = self.getPlug(attr)
            if int(plug.get()) == int(value):
                continue
            if plug.mplug().isFreeToChange() != om2.MPlug.kFreeToChange:
                report.addSkipped(f"{self.getName()}.{attr}", "ロックされているか、接続されています")
                continue
            plug.set(value, fast=fast)

    def _capture_ngskin_layers(self, paths):
        """ngSkinTools2のレイヤーを、:meth:`getWeightsData` の ``ngSkinLayers`` の形で取得する。

        Args:
            paths (om2.MDagPathArray): influenceObjects()。レイヤーの論理番号を保存の位置へ変換する。

        Returns:
            list[dict] | None: レイヤーごとの辞書。ngSkinTools2を使えない、またはレイヤーが無ければNone。
        """
        found = _layer_api(self.getFullName())
        if found is None:
            return None
        layers = found[1].list()
        if not layers:
            return None
        positions = {self._skin_fn.indexForInfluenceObject(path): index for index, path in enumerate(paths)}
        ids = [layer.id for layer in layers]
        result = []
        for layer in layers:
            weights = [[positions[index], [float(value) for value in layer.get_weights(index)]] for index in layer.get_used_influences() if index in positions]
            entry = {
                "name": layer.name,
                "enabled": bool(layer.enabled),
                "opacity": float(layer.opacity),
                "parent": ids.index(layer.parent_id) if layer.parent_id in ids else None,
                "index": int(layer.index or 0),
                "weights": weights,
            }
            for target in ("mask", "dq"):
                values = layer.get_weights(target)
                entry[target] = [float(value) for value in values] if values else None
            result.append(entry)
        return result

    def _apply_ngskin_layers(self, saved_layers, columns, logical, sources, report, fast):
        """保存したngSkinTools2のレイヤーで、このskinClusterのレイヤーを作り直す。

        Args:
            saved_layers (list[dict] | None): 検査済みの ``ngSkinLayers``。
            columns (list[int | None]): 保存したinfluenceごとの、現在の物理番号。
            logical (list[int]): 現在の物理番号ごとのweights[]の論理番号(ngSkinTools2のinfluence番号)。
            sources (Sequence[int]): 現在の頂点ごとの、保存した頂点の番号。
            report (ValidationReport): 書かなかったものの記録先。
            fast (bool): TrueはレイヤーのウェイトのUndoを記録しない。

        Returns:
            None: 値を返さない。
        """
        name = self.getFullName()
        if not saved_layers:
            if _layer_api(name) is not None:
                report.addSkipped(f"{self.getName()}のngSkinToolsのレイヤー", "既存のレイヤーを残しました。書き込んだウェイトを上書きする可能性があります")
            return
        api = self._ngskin_api()
        if api is None:
            report.addSkipped(f"{self.getName()}のngSkinToolsのレイヤー", "ngSkinTools2が利用できません")
            return
        layers = api.init_layers(name)
        undo = not fast
        with api.suspend_updates(layers.data_node):
            layers.clear()
            created = {}
            # 親を先に作る。_parse_weights_data で親の循環は拒否済み。
            while len(created) < len(saved_layers):
                for position, entry in enumerate(saved_layers):
                    parent = entry["parent"]
                    if position in created or (parent is not None and parent not in created):
                        continue
                    layer = layers.add(entry["name"], force_empty=True, parent=None if parent is None else created[parent])
                    layer.enabled = entry["enabled"]
                    layer.opacity = entry["opacity"]
                    merged = {}
                    for index, weights in entry["weights"]:
                        if columns[index] is None:
                            continue
                        values = [weights[source] for source in sources]
                        key = logical[columns[index]]
                        merged[key] = [a + b for a, b in zip(merged[key], values)] if key in merged else values
                    for key, values in merged.items():
                        layer.set_weights(key, values, undo_enabled=undo)
                    for target in ("mask", "dq"):
                        if entry[target] is not None:
                            layer.set_weights(target, [entry[target][source] for source in sources], undo_enabled=undo)
                    created[position] = layer
            for position in sorted(created, key=lambda item: saved_layers[item]["index"]):
                created[position].index = saved_layers[position]["index"]

    @staticmethod
    def _ngskin_api():
        """読み込み済みのngSkinTools2のAPIを返す。

        Returns:
            module | None: ``ngSkinTools2.api``。プラグイン未ロード・APIなしはNone。
        """
        if not cmds.pluginInfo("ngSkinTools2", query=True, loaded=True):
            return None
        try:
            # ngSkinTools2は任意の外部ツールのため、使うときにだけimportする。
            from ngSkinTools2 import api
        except ImportError:
            return None
        return api

    def _input_points(self):
        """skinClusterに入る前の形状の頂点位置(オブジェクト空間、cm)を返す。

        入力の形状を読めない場合は、出力のMeshの位置を返す。

        Returns:
            om2.MPointArray: 頂点番号順の位置。
        """
        try:
            index = self._skin_fn.indexForOutputShape(self.mesh_path.node())
            fn = self._dependency_fn()
            element = fn.findPlug("input", False).elementByLogicalIndex(index)
            data = element.child(fn.attribute("inputGeometry")).asMObject()
            if not data.isNull() and data.hasFn(om2.MFn.kMesh):
                points = om2.MFnMesh(data).getPoints(om2.MSpace.kObject)
                if len(points) == om2.MFnMesh(self.mesh_path).numVertices:
                    return points
        except RuntimeError:
            pass
        return om2.MFnMesh(self.mesh_path).getPoints(om2.MSpace.kObject)

    @classmethod
    def _parse_weights_data(cls, data):
        """:meth:`getWeightsData` の辞書の形を確かめ、適用に使う形へ変える。シーンは変更しない。

        Args:
            data (dict): 確かめる辞書。

        Returns:
            dict: ``vertexCount``・``influences`` (NodeRefのlist)・``influenceLocks``・
                ``weights`` (indicesとvaluesの組)・``blendWeights``・``positions``・``settings``・
                ``ngSkinLayers`` を持つ辞書。

        Raises:
            TypeError: dataが辞書でない場合。
            ValueError: 形が不正な場合。
        """
        # 循環参照の回避: mlib.json はnodesを読み込むため、使う時点で読み込む。
        from ..json.nodeRef import NodeRef

        if not isinstance(data, dict):
            raise TypeError(f"dataはdictで指定してください: {type(data).__name__}")
        for key in ("vertexCount", "influences", "weights"):
            if key not in data:
                raise ValueError(f"スキンウェイトのデータに'{key}'がありません")
        count = data["vertexCount"]
        if type(count) is not int or count < 0:
            raise ValueError(f"vertexCountは0以上のintで指定してください: {count!r}")
        if not isinstance(data["influences"], list) or not data["influences"]:
            raise ValueError("influencesは空でないリストで指定してください")
        influences = [NodeRef.fromData(item) for item in data["influences"]]
        width = len(influences)
        locks = data.get("influenceLocks")
        locks = [False] * width if locks is None else locks
        if not isinstance(locks, list) or len(locks) != width or not all(isinstance(lock, bool) for lock in locks):
            raise ValueError(f"influenceLocksは{width}個のboolのリストで指定してください")
        weights = data["weights"]
        if not isinstance(weights, dict) or set(weights) != {"indices", "values"}:
            raise ValueError("weightsは'indices'と'values'を持つdictで指定してください")
        indices, values = weights["indices"], weights["values"]
        if not isinstance(indices, list) or not isinstance(values, list) or len(indices) != count or len(values) != count:
            raise ValueError(f"weightsのindicesとvaluesは{count}行のリストで指定してください")
        for vertex, (row_indices, row_values) in enumerate(zip(indices, values)):
            if not isinstance(row_indices, list) or not isinstance(row_values, list) or len(row_indices) != len(row_values):
                raise ValueError(f"頂点{vertex}のウェイトの行が不正です")
            for index, value in zip(row_indices, row_values):
                if type(index) is not int or not 0 <= index < width:
                    raise ValueError(f"頂点{vertex}のインフルエンスの番号{index!r}が不正です")
                if not _finite_number(value):
                    raise ValueError(f"頂点{vertex}のウェイト{value!r}が不正です")
        blend = data.get("blendWeights")
        if blend is not None and (not isinstance(blend, list) or len(blend) != count or not all(_finite_number(value) for value in blend)):
            raise ValueError(f"blendWeightsは{count}個の数値のリストで指定してください")
        positions = data.get("positions") or None
        if positions is not None and (
            not isinstance(positions, list)
            or len(positions) != count
            or not all(isinstance(point, list) and len(point) == 3 and all(_finite_number(value) for value in point) for point in positions)
        ):
            raise ValueError(f"positionsは{count}個の[x, y, z]の点のリストで指定してください")
        return {
            "vertexCount": count,
            "influences": influences,
            "influenceLocks": locks,
            "weights": (indices, values),
            "blendWeights": blend,
            "positions": positions,
            "settings": cls._parse_weight_settings(data.get("settings")),
            "ngSkinLayers": cls._parse_ngskin_layers(data.get("ngSkinLayers"), width, count),
        }

    @classmethod
    def _parse_weight_settings(cls, settings):
        """``settings`` の形を確かめる。

        Args:
            settings (dict | None): 保存した設定。Noneは設定を書かない。

        Returns:
            dict: 4つの設定。保存に無い設定はNone。

        Raises:
            ValueError: 形または値が不正な場合。
        """
        settings = {} if settings is None else settings
        if not isinstance(settings, dict):
            raise ValueError("settingsはdictで指定してください")
        result = {key: settings.get(key) for key in ("skinningMethod", "maxInfluences", "maintainMaxInfluences", "normalizeWeights")}
        checks = (
            ("skinningMethod", lambda value: value in cls._SKINNING_METHODS),
            ("normalizeWeights", lambda value: value in cls._NORMALIZE_MODES),
            ("maxInfluences", lambda value: type(value) is int and value >= 1),
            ("maintainMaxInfluences", lambda value: isinstance(value, bool)),
        )
        for key, check in checks:
            if result[key] is not None and not check(result[key]):
                raise ValueError(f"settingsの{key}が不正です: {result[key]!r}")
        return result

    @staticmethod
    def _parse_ngskin_layers(layers, width, count):
        """``ngSkinLayers`` の形と、親の対応(循環が無いこと)を確かめる。

        Args:
            layers (list[dict] | None): 保存したレイヤー。
            width (int): 保存したinfluenceの数。
            count (int): 保存した頂点数。

        Returns:
            list[dict] | None: 確かめたレイヤー。無ければNone。

        Raises:
            ValueError: 形が不正、または親が循環する場合。
        """
        if not layers:
            return None
        if not isinstance(layers, list):
            raise ValueError("ngSkinLayersはリストで指定してください")

        def column(values):
            """頂点ごとの値の列か確かめる。"""
            return isinstance(values, list) and len(values) == count and all(_finite_number(v) for v in values)

        for position, entry in enumerate(layers):
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                raise ValueError(f"位置{position}のngSkinToolsのレイヤーが不正です")
            parent = entry.get("parent")
            if parent is not None and (type(parent) is not int or not 0 <= parent < len(layers) or parent == position):
                raise ValueError(f"ngSkinToolsのレイヤー{entry['name']!r}の親が不正です: {parent!r}")
            if not isinstance(entry.get("enabled"), bool) or not _finite_number(entry.get("opacity")) or type(entry.get("index")) is not int:
                raise ValueError(f"ngSkinToolsのレイヤー{entry['name']!r}の設定が不正です")
            weights = entry.get("weights")
            if not isinstance(weights, list) or not all(
                isinstance(item, list) and len(item) == 2 and type(item[0]) is int and 0 <= item[0] < width and column(item[1]) for item in weights
            ):
                raise ValueError(f"ngSkinToolsのレイヤー{entry['name']!r}のウェイトが不正です")
            for target in ("mask", "dq"):
                if entry.get(target) is not None and not column(entry[target]):
                    raise ValueError(f"ngSkinToolsのレイヤー{entry['name']!r}の{target}が不正です")
        for position, entry in enumerate(layers):
            seen = {position}
            parent = entry.get("parent")
            while parent is not None:
                if parent in seen:
                    raise ValueError(f"ngSkinToolsのレイヤーの親が{entry['name']!r}で循環しています")
                seen.add(parent)
                parent = layers[parent].get("parent")
        return [dict(entry, mask=entry.get("mask"), dq=entry.get("dq")) for entry in layers]

    def _inverted_points(self, sculpted_points):
        """:meth:`invertShape` の頂点の位置(Origの空間)を計算する。シーンは変更しない。

        Args:
            sculpted_points (om2.MPointArray): 現在のポーズで整えた形のオブジェクト空間の頂点。

        Returns:
            list[tuple[float, float, float]]: 頂点番号順の補正形状の位置(cm)。
        """
        dependency = self._dependency_fn()
        geometry_index = oma2.MFnGeometryFilter(self.mnode()).indexForOutputShape(self.mesh_path.node())
        input_plug = dependency.findPlug("input", False).elementByLogicalIndex(geometry_index)
        input_plug = input_plug.child(dependency.attribute("inputGeometry"))
        input_points = om2.MFnMesh(input_plug.asMObject()).getPoints()
        original = cmds.deformableShape(self.mesh_path.fullPathName(), originalGeometry=True) or []
        original = original[0].split(".")[0] if original and original[0] else ""
        if original:
            selection = om2.MSelectionList()
            selection.add(original)
            original_points = om2.MFnMesh(selection.getDagPath(0)).getPoints(om2.MSpace.kObject)
        else:
            original_points = input_points
        geometry = self._plug_matrix(dependency.findPlug("geomMatrix", False))
        geometry_inverse = geometry.inverse()
        envelope = dependency.findPlug("envelope", False).asFloat()
        matrices = dependency.findPlug("matrix", False)
        bind_pre = dependency.findPlug("bindPreMatrix", False)
        logical = [self._skin_fn.indexForInfluenceObject(path) for path in self._skin_fn.influenceObjects()]
        skin_matrices = [
            self._plug_matrix(bind_pre.elementByLogicalIndex(index)) * self._plug_matrix(matrices.elementByLogicalIndex(index)) for index in logical
        ]
        components, count = self._all_vertices()
        weights, width = self._skin_fn.getWeights(self.mesh_path, components)
        weights = list(weights)
        identity = om2.MMatrix()
        result = []
        for vertex in range(count):
            row = weights[vertex * width : (vertex + 1) * width]
            total = om2.MMatrix([0.0] * 16)
            for weight, matrix in zip(row, skin_matrices):
                if weight:
                    total += matrix * weight
            # skinCluster は geomMatrix の空間で変形し、出力を元の空間へ戻す。
            deform = geometry * total * geometry_inverse
            deform = identity * (1.0 - envelope) + deform * envelope
            source = input_points[vertex]
            if abs(deform.det4x4()) > 1e-12:
                source = om2.MPoint(sculpted_points[vertex]) * deform.inverse()
            point = original_points[vertex] + (source - input_points[vertex])
            result.append((point.x, point.y, point.z))
        return result

    @staticmethod
    def _plug_matrix(plug):
        """matrix 型のアトリビュートの値を読む。値の無い要素は単位マトリクスにする。

        Args:
            plug (om2.MPlug): matrix 型のアトリビュートの Plug。

        Returns:
            om2.MMatrix: 値。
        """
        try:
            return om2.MFnMatrixData(plug.asMObject()).matrix()
        except RuntimeError:
            return om2.MMatrix()

    @staticmethod
    def _geometry_skin_uuids(node):
        """形状を変形しているskinClusterのUUIDを集める。

        集め方はDagNode.getSkinClustersと同じ。Jointの同じ名前のメソッドは、インフルエンスとしての接続を
        調べる別の意味のものなので、DagNodeの実装を直接呼ぶ。

        Args:
            node (Node): 調べるノード。DAGノードでなければ空になる。

        Returns:
            list[str]: skinClusterのUUIDの文字列。並びはgetSkinClustersと同じ。
        """
        if not isinstance(node, DagNode):
            return []
        return [skin.getUuid() for skin in DagNode.getSkinClusters(node)]

    def _uuid_or_none(self, node):
        """ノードの名前からMayaのUUIDを取得する。

        Args:
            node (str): UUIDを調べるノードの名前。

        Returns:
            str | None: ノードのUUID。ノードが無ければNone。
        """
        # 存在しない名前でNode()がエラー通知を出さないよう、先に存在だけを確かめる。
        if isinstance(node, str) and not cmds.objExists(node):
            return None
        try:
            return Node(node).getUuid()
        except RuntimeError:
            return None

    @staticmethod
    def _path_uuid(path):
        """インフルエンスのDAGパスから、名前を使わずにMayaのUUIDを取得する。

        ``_uuid_or_none(path.fullPathName())`` と同じ値を、名前から探し直さずに求める。

        Args:
            path (om2.MDagPath): influenceObjects()のパス。

        Returns:
            str | None: ノードのUUID。パスかノードが無効ならNone。
        """
        if not path.isValid():
            return None
        node = path.node()
        if not om2.MObjectHandle(node).isValid():
            return None
        return om2.MFnDependencyNode(node).uuid().asString()

    def _mesh_node(self):
        """オブジェクトを作ったときの、先頭のジオメトリのMObjectを返す。

        Returns:
            om2.MObject: mesh_pathが指すノード。
        """
        path = self.mesh_path
        # mesh_pathは__init__で必ず設定する。
        assert path is not None
        return path.node()

    def _geometry_dag_path(self, name):
        """ジオメトリの名前から、shapeまでたどったMDagPathを取得する。

        Args:
            name (str): ジオメトリのノードの名前。

        Returns:
            om2.MDagPath: DAGパス。Transformの名前なら、その下のshapeまでたどったパス。
        """
        # 名前とインスタンスパスの解決は既存Node/DagNodeの経路を共有する。
        path = Node(name).mpath()
        if path.node().hasFn(om2.MFn.kTransform):
            path.extendToShape()
        return path

    def _first_geometry_name(self):
        """skinClusterが変形している先頭のジオメトリの名前を取得する。

        Returns:
            str: skinClusterに登録されている先頭のジオメトリの名前(フルパス)。

        Raises:
            IndexError: ジオメトリが無い場合。
        """
        geometries = oma2.MFnGeometryFilter(self.mnode()).getOutputGeometry()
        if not geometries:
            raise IndexError("このskinClusterに出力ジオメトリがありません")
        return om2.MFnDagNode(geometries[0]).fullPathName()

    def _influence_index(self, joint):
        """登録されているインフルエンスの名前・UUIDと比べて、物理的な番号を取得する。

        Args:
            joint (str): 探すインフルエンスの名前。

        Returns:
            int | None: influenceObjects()のリストの中の位置。UUIDかpartialの名前が一致する候補のうち、
                最初のものの物理的な番号を返し、weights[]の論理番号は返さない。登録されていなければNone。
        """
        return self._influence_indices((joint,), self._skin_fn.influenceObjects())[0]

    def _all_vertices(self):
        """meshのすべての頂点のcomponentと、頂点の数を作る。

        Returns:
            tuple[om2.MObject, int]: すべての頂点を含むcomponentと、頂点の数。
        """
        num_vertices = om2.MFnMesh(self.mesh_path).numVertices
        component_fn = om2.MFnSingleIndexedComponent()
        vertices = component_fn.create(om2.MFn.kMeshVertComponent)
        component_fn.addElements(range(num_vertices))
        return vertices, num_vertices

    def _require_influences(self, joints):
        """インフルエンスの指定を確かめ、指定した順の物理的な番号へ変える。シーンは変えない。

        Args:
            joints (str | Node | Iterable): インフルエンスの指定。この順で番号を返す。

        Returns:
            list[int]: influenceObjects()の中での物理的な番号。weights[]の論理番号ではない。

        Raises:
            TypeError: 頂点などのコンポーネントやアトリビュートを渡した場合、または入力の型が正しくない場合。
            ValueError: 空・未登録・重複の場合。
        """
        # componentsはnodesを読み込むため、循環importを避けて使う時点で読み込む。
        from ..components.component import Component, Components

        hint = "頂点はvertices=で渡すか、getVertexWeights()/setVertexWeights()を使います"
        items = joints if isinstance(joints, (list, tuple, set)) else (joints,)
        for item in items:
            if isinstance(item, (Component, Components)):
                raise TypeError(f"インフルエンスを指定してください: コンポーネント({type(item).__name__})が渡されました。{hint}")
        names = Object._input_names(joints)
        if not names:
            raise ValueError("インフルエンスを1つ以上指定してください")
        for name in names:
            if "." in name:
                raise TypeError(f"インフルエンスを指定してください: コンポーネントかアトリビュートの名前'{name}'が渡されました。{hint}")
        physical_indices: List[int] = []
        seen = set()
        for name, index in zip(names, self._influence_indices(names, self._skin_fn.influenceObjects())):
            if index is None:
                raise ValueError(f"'{name}'は{self.getName()}のインフルエンスではありません")
            if index in seen:
                raise ValueError(f"インフルエンスが複数回指定されています: '{name}'")
            seen.add(index)
            physical_indices.append(index)
        return physical_indices

    def _vertex_indices(self, vertices):
        """頂点の指定を、先頭のMeshの頂点番号のリストへ変える。シーンは変えない。

        Args:
            vertices (Vertex | Vertices | int | str | Iterable | None): 頂点のオブジェクト・番号・名前
                (``"mesh.vtx[0:3]"`` のような範囲も指定できる)、またはそれらを順に取り出せるもの。

        Returns:
            list[int] | None: 指定した順の頂点番号。Noneを渡したときはNone(すべての頂点)。

        Raises:
            TypeError: 頂点ではない入力(bool・float・エッジなど)の場合。
            ValueError: 先頭のMesh以外の頂点の場合、または同じ頂点が重複している場合。
            IndexError: 頂点の番号が範囲外の場合。
        """
        if vertices is None:
            return None
        # componentsはnodesを読み込むため、循環importを避けて使う時点で読み込む。
        from ..components.component import Component, Components
        from ..components.vertex import Vertex, Vertices

        mesh = self._mesh_node()
        num_vertices = om2.MFnMesh(self.mesh_path).numVertices
        result = []

        def collect(value):
            """単数・範囲・入れ子の頂点指定を番号へ展開してresultへ追加する。"""
            if isinstance(value, Vertices):
                if value.shape.mnode() != mesh:
                    raise ValueError("頂点はこのskinClusterの最初のメッシュのものを指定してください")
                result.extend(value.indices)
            elif isinstance(value, Vertex):
                if value.shape.mnode() != mesh:
                    raise ValueError("頂点はこのskinClusterの最初のメッシュのものを指定してください")
                result.append(value.index)
            elif isinstance(value, (Component, Components)):
                raise TypeError(f"メッシュの頂点を指定してください: {type(value).__name__}")
            elif isinstance(value, bool) or isinstance(value, float):
                raise TypeError(f"頂点番号を指定してください: {type(value).__name__}")
            elif isinstance(value, int):
                result.append(value)
            elif isinstance(value, str):
                result.extend(self._vertex_name_indices(value, mesh, num_vertices))
            else:
                try:
                    iterator = iter(value)
                except TypeError:
                    raise TypeError(f"頂点を指定してください: {type(value).__name__}") from None
                for item in iterator:
                    collect(item)

        collect(vertices)
        seen = set()
        for index in result:
            if not 0 <= index < num_vertices:
                raise IndexError(f"頂点番号が範囲外です: {index}")
            if index in seen:
                raise ValueError(f"頂点が複数回指定されています: {index}")
            seen.add(index)
        return result

    @staticmethod
    def _vertex_name_indices(name, mesh, num_vertices):
        """``"mesh.vtx[0:3]"`` のような頂点名を、先頭Meshの頂点番号へ展開する。

        Args:
            name (str): 頂点の名前。範囲・``[*]`` を含んでよい。
            mesh (om2.MObject): 先頭MeshのShape。
            num_vertices (int): 先頭Meshの頂点数。complete指定の展開に使う。

        Returns:
            list[int]: Mayaが返す順の頂点番号。

        Raises:
            TypeError: 頂点以外のコンポーネント、またはノード名だけの場合。
            ValueError: 空文字、または先頭Mesh以外の頂点の場合。
            RuntimeError: 名前を解決できない場合。
        """
        if not name:
            raise ValueError("頂点名は空でない文字列で指定してください")
        selection = om2.MSelectionList()
        selection.add(name)
        indices = []
        for item in range(selection.length()):
            path, component = selection.getComponent(item)
            if component.isNull() or component.apiType() != om2.MFn.kMeshVertComponent:
                raise TypeError(f"'mesh.vtx[0]'のようなメッシュの頂点名を指定してください: '{name}'")
            if path.node().hasFn(om2.MFn.kTransform):
                path.extendToShape()
            if path.node() != mesh:
                raise ValueError(f"頂点はこのskinClusterの最初のメッシュのものを指定してください: '{name}'")
            component_fn = om2.MFnSingleIndexedComponent(component)
            indices.extend(range(num_vertices) if component_fn.isComplete else component_fn.getElements())
        return indices

    def _single_vertex_index(self, vertex):
        """1頂点の指定を頂点番号へ変換する。

        Args:
            vertex (Vertex | int | str): 先頭Meshの1頂点。

        Returns:
            int: 頂点番号。

        Raises:
            TypeError: Noneや頂点以外の型の場合。
            ValueError: 1頂点でない、または先頭Mesh以外の頂点の場合。
            IndexError: 頂点番号が範囲外の場合。
        """
        if vertex is None:
            raise TypeError("頂点を指定してください(Noneは指定できません)")
        indices = self._vertex_indices(vertex)
        # vertexがNoneでなければ頂点番号のlistが返る。
        assert indices is not None
        if len(indices) != 1:
            raise ValueError(f"頂点を1つだけ指定してください: {len(indices)}個")
        return indices[0]

    def _read_rows(self, vertex_indices, physical_indices):
        """指定頂点・指定influenceのウェイトを、頂点ごとの行として読み取る。

        MFnSkinCluster.getWeightsはcomponentの番号を昇順で返すため、昇順で読んでから指定順へ並べ直す。

        Args:
            vertex_indices (Sequence[int]): 検証済みの頂点番号。重複なし。
            physical_indices (Iterable[int]): influenceObjects()内の物理番号。

        Returns:
            list[list[float]]: vertex_indicesの順の行。各行はphysical_indicesの順。
        """
        physical_indices = list(physical_indices)
        if not vertex_indices or not physical_indices:
            return [[] for _ in vertex_indices]
        ordered = sorted(vertex_indices)
        component_fn = om2.MFnSingleIndexedComponent()
        component = component_fn.create(om2.MFn.kMeshVertComponent)
        component_fn.addElements(ordered)
        flat = list(self._skin_fn.getWeights(self.mesh_path, component, om2.MIntArray(physical_indices)))
        width = len(physical_indices)
        position = {vertex: i for i, vertex in enumerate(ordered)}
        return [flat[position[vertex] * width : (position[vertex] + 1) * width] for vertex in vertex_indices]

    @staticmethod
    def _influence_locked(path):
        """influenceのlockInfluenceWeightsが有効か調べる。アトリビュートが無い型はFalse。

        Args:
            path (om2.MDagPath): influenceObjects()のパス。

        Returns:
            bool: ロックされている場合True。
        """
        fn = om2.MFnDependencyNode(path.node())
        if not fn.hasAttribute("lockInfluenceWeights"):
            return False
        return fn.findPlug("lockInfluenceWeights", False).asBool()

    @staticmethod
    def _normalize_row(row, vertex, specified, free, locked):
        """1つの頂点の、すべてのインフルエンスの値を、指定した列を優先して合計1へ正規化する。

        rowをその場で書き換える。

        - ロックした列は値を保つ。
        - 空き(``1 - ロック合計``)から指定した列の合計を引いた残りに、自由な列(指定もロックもしていない列)を
          比率で合わせる。
        - 指定した列の合計が空きを超える場合と、自由な列がすべて0の場合は、指定した列を比率で空きに合わせ、
          自由な列を0にする。

        Args:
            row (list[float]): すべてのインフルエンスの値。物理的な順番に並ぶ。
            vertex (int): エラーの表示に使う頂点の番号。
            specified (Iterable[int]): 値を指定した物理的な番号。
            free (Iterable[int]): 指定もロックもしていない物理的な番号。
            locked (Iterable[int]): 値を保つ、ロックした指定していない物理的な番号。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: 負の値や有限でない値がある場合、ロックした値の合計が1を超える場合、
                または合計が0で正規化できない場合。
        """
        if not all(math.isfinite(value) and value >= 0.0 for value in row):
            raise ValueError(f"頂点{vertex}のウェイトに負の値か有限でない値があるため、正規化できません")
        specified, free = list(specified), list(free)
        budget = 1.0 - sum(row[i] for i in locked)
        if budget < -1e-9:
            raise ValueError(f"頂点{vertex}で、ロックされたインフルエンスのウェイトが1.0を超えています")
        budget = max(budget, 0.0)
        specified_total = sum(row[i] for i in specified)
        free_total = sum(row[i] for i in free)
        if free_total > 0.0 and specified_total <= budget:
            scale = (budget - specified_total) / free_total
            for i in free:
                row[i] *= scale
        elif specified_total > 0.0:
            scale = budget / specified_total
            for i in specified:
                row[i] *= scale
            for i in free:
                row[i] = 0.0
        elif budget > 1e-9:
            raise ValueError(f"頂点{vertex}のウェイトの合計が0のため、正規化できません")

    def _normalized_write(self, values, width, vertex_indices, physical_indices):
        """setWeights(normalize=True)で書き込む値を、対象の頂点の今の値から計算する。シーンは変えない。

        Args:
            values (list[float]): 確かめたV*K個の値、またはすべての頂点に共通のK個の値。
            width (int): 指定した列の数K。
            vertex_indices (Sequence[int]): 書き込む頂点の番号。
            physical_indices (list[int]): 指定したインフルエンスの物理的な番号。

        Returns:
            tuple[list[float], list[int]]: 頂点の順に1列に並べた値と、その列の物理的な番号。
                指定した列の後に、値が変わった指定していない列を、物理的な順番で続ける。
        """
        paths = self._skin_fn.influenceObjects()
        specified = set(physical_indices)
        others = [i for i in range(len(paths)) if i not in specified]
        locked = [i for i in others if self._influence_locked(paths[i])]
        free = [i for i in others if i not in set(locked)]
        rows = self._read_rows(vertex_indices, range(len(paths)))
        shared = len(values) == width
        results, changed = [], set()
        for position, (vertex, row) in enumerate(zip(vertex_indices, rows)):
            offset = 0 if shared else position * width
            new = list(row)
            for column, index in enumerate(physical_indices):
                new[index] = values[offset + column]
            self._normalize_row(new, vertex, physical_indices, free, locked)
            changed.update(i for i in others if new[i] != row[i])
            results.append(new)
        columns = list(physical_indices) + [i for i in others if i in changed]
        return [row[i] for row in results for i in columns], columns

    def _copy_destination(self, target):
        """copyWeightsToの転送先のSkinClusterを決める。すでにあるものを使うか、新しくバインドする。

        Args:
            target (str | Node): skinCluster、または形状かその親のTransform。

        Returns:
            SkinCluster: 転送先。形状にskinClusterが無ければ、自身のインフルエンスでバインドしたもの。

        Raises:
            TypeError: skinClusterでも形状でもない場合。
            ValueError: 形状を複数のskinClusterが変形している場合。
            RuntimeError: その名前のノードが無い場合、またはMayaがバインドを拒否した場合。
        """
        node = target if isinstance(target, Node) else Node(target)
        if isinstance(node, SkinCluster):
            return node
        description = f"{node.getType()} '{node.getName()}'"
        if not isinstance(node, DagNode) or node.isType("joint"):
            raise TypeError(f"copyWeightsToにはskinClusterかジオメトリを指定してください: {description}")
        skins = DagNode.getSkinClusters(node)
        if len(skins) > 1:
            raise ValueError(f"ジオメトリが複数のskinClusterで変形されています: {description}")
        if skins:
            return skins[0]
        if not self._has_geometry(node.mpath()):
            raise TypeError(f"copyWeightsToにはskinClusterかジオメトリを指定してください: シェイプのない{description}")
        # cmds は nodes を参照するため、循環importを避けて関数内で読み込む。
        from ..cmds.bindSkin import bindSkin

        return bindSkin(self.getInfluences(), node, maximumInfluences=self.getMaxInfluences())

    @staticmethod
    def _has_geometry(path):
        """DAGパスが形状、または直下に中間でない形状を持つTransformか調べる。

        Args:
            path (om2.MDagPath): 調べるパス。

        Returns:
            bool: 形状を持つ場合True。
        """
        if path.node().hasFn(om2.MFn.kShape):
            return True
        for index in range(path.childCount()):
            child = path.child(index)
            if child.hasFn(om2.MFn.kShape) and not om2.MFnDagNode(child).isIntermediateObject:
                return True
        return False

    @staticmethod
    def _require_choice(value, name, choices):
        """文字列の選択肢を検証する。

        Args:
            value (str): 検証する値。
            name (str): エラー表示用の引数名。
            choices (Sequence[str]): 受け付ける値。

        Returns:
            str: 検証済みの値。

        Raises:
            TypeError: 文字列でない場合。
            ValueError: 選択肢にない場合。
        """
        if not isinstance(value, str):
            raise TypeError(f"{name}はstrで指定してください: {type(value).__name__}")
        if value not in choices:
            raise ValueError(f"{name}は{', '.join(choices)}のどれかで指定してください: '{value}'")
        return value

    def _flatten_weight_rows(self, joints, weights):
        """頂点ごとの行を、:meth:`setWeights` の平坦な値の並びへ変換する。

        Args:
            joints (str | Node | Iterable): 指定influence。行の長さの基準。
            weights (Iterable[Iterable[float]]): 頂点ごとの行。

        Returns:
            list[object]: 行を順につないだ値。値の検証は呼出し側が行う。

        Raises:
            TypeError: 行が反復できない、または文字列の場合。
            ValueError: 行の長さが指定influenceの数と合わない場合。
        """
        width = len(self._require_influences(joints))
        flat = []
        for row in weights:
            if isinstance(row, (str, bytes)) or not hasattr(row, "__iter__"):
                raise TypeError(f"各行はウェイトの並びで指定してください: {type(row).__name__}")
            row = list(row)
            if len(row) != width:
                raise ValueError(f"1行あたりウェイトを{width}個指定してください: {len(row)}個")
            flat.extend(row)
        return flat

    def _prepare_weight_values(self, joints, weights, vertices=None, broadcast=False):
        """指定influence・頂点と平坦なウェイト入力を検証する。

        値の数・有限性と、対象が空でなく登録済み/重複なしであることを検証する。
        非負・合計1・レイヤー・lockInfluenceWeightsは検査しない。シーンには書き込まない。

        Args:
            joints (Iterable): 指定順のinfluence参照。
            weights (Iterable): 頂点順のV*K値、またはbroadcast時の共通K値。
            vertices (object): :meth:`_vertex_indices` が受け付ける頂点指定。Noneは全頂点。
            broadcast (bool): TrueはK個の値を全対象頂点へ適用する。

        Returns:
            tuple: float値リスト、指定列数K、対象頂点番号の列、指定順の物理番号リスト。

        Raises:
            ValueError: 件数不一致。K個をbroadcastなしで複数頂点へ渡した場合は、broadcast=True・vertices=の
                指定を促す。
        """
        physical_indices = self._require_influences(joints)
        if isinstance(weights, (str, bytes)):
            raise TypeError("weightsは数値の並びで指定してください(文字列は指定できません)")
        values = [float(value) for value in weights]
        vertex_indices = self._vertex_indices(vertices)
        if vertex_indices is None:
            vertex_indices = range(om2.MFnMesh(self.mesh_path).numVertices)
        count, width = len(vertex_indices), len(physical_indices)
        if broadcast:
            if len(values) != width:
                raise ValueError(f"broadcast=Trueにはウェイトをちょうど{width}個(インフルエンスごとに1つ)指定してください: {len(values)}個")
        elif len(values) != count * width:
            if len(values) == width:
                raise ValueError(
                    f"{count}個の頂点 × {width}個のインフルエンスに対して、ウェイトが{width}個渡されました。すべての頂点へ適用するにはbroadcast=True、頂点を選ぶにはvertices=を指定してください"
                )
            raise ValueError(f"ウェイトの数は「頂点数 × インフルエンス数」({count} x {width} = {count * width})で指定してください: {len(values)}個")
        if not all(math.isfinite(value) for value in values):
            raise ValueError("ウェイトは有限な数値で指定してください")
        return values, width, vertex_indices, physical_indices

    def _set_weight_values_fast(self, values, width, vertex_indices, logical_indices):
        """全対象ウェイトPlugを検査し、頂点・指定列の順にOpenMayaで生値を書き込む。

        writable/check_rangeを全件に適用してから書き込む。書き込みは
        ``MFnSkinCluster.setWeights(normalize=False)`` の1回で行い、指定していない列は変えない。
        normalizeWeightsが1(interactive)のときは、書く間だけ0にして元へ戻す(liwは変えない)。
        値が0の要素はMayaが削除する(読み取る値は0のまま)。メッシュ以外の形状・同じ頂点や列の重複・登録の無い列は、
        MPlugへ1値ずつ書き込む。
        事前検査後のAPI書込み失敗は自動で戻さず、Undo設定を変更しない。

        Args:
            values (list[float]): 検証済みのV*K値または共通K値。
            width (int): 指定列数K。
            vertex_indices (Sequence[int]): 書き込む頂点番号。valuesの行の順。
            logical_indices (list[int]): weights[]の論理番号。指定influence順。

        Returns:
            None: 値を返さない。
        """
        weights_plug = self._dependency_fn().findPlug("weightList", False)
        # 全要素が同じweightsアトリビュートなので、書込み可否と範囲の定義を読むfunction setは
        # 1つを共有する。ロック・入力接続は要素ごと、親側(weightList[v].weights より上)は
        # 頂点ごとに毎回調べる。拒否する要素ではrequire_writable()を呼び、従来と同じ例外を送出する。
        attribute_fn = range_fn = None
        attribute_writable = has_limits = True
        shared = len(values) == width
        for position, vertex in enumerate(vertex_indices):
            row = weights_plug.elementByLogicalIndex(vertex).child(0)
            row_blocked = self._plug_chain_blocked(row)
            offset = 0 if shared else position * width
            for column, index in enumerate(logical_indices):
                plug = row.elementByLogicalIndex(index)
                if attribute_fn is None:
                    attribute = plug.attribute()
                    attribute_fn = om2.MFnAttribute(attribute)
                    attribute_writable = attribute_fn.writable
                    if attribute.hasFn(om2.MFn.kNumericAttribute):
                        range_fn = om2.MFnNumericAttribute(attribute)
                        has_limits = range_fn.hasMin() or range_fn.hasMax()
                if row_blocked or plug.isLocked or plug.isDestination or not attribute_writable:
                    require_writable(plug, attribute_fn)
                if has_limits:
                    require_range(plug, values[offset + column], range_fn)
        count = len(vertex_indices)
        if not count or not width:
            return
        skin_fn = self._skin_fn
        physical = {skin_fn.indexForInfluenceObject(path): index for index, path in enumerate(skin_fn.influenceObjects())}
        mesh_path = self.mesh_path
        if (
            mesh_path is not None
            and mesh_path.hasFn(om2.MFn.kMesh)
            and all(index in physical for index in logical_indices)
            and len(set(logical_indices)) == width
            and len(set(vertex_indices)) == count
        ):
            # normalize=Falseなら指定した列の生値だけを書き、ほかの列を再配分しない。
            component_fn = om2.MFnSingleIndexedComponent()
            component = component_fn.create(om2.MFn.kMeshVertComponent)
            component_fn.addElements(om2.MIntArray(list(vertex_indices)))
            # コンポーネントは番号の昇順に並ぶため、値も頂点番号の昇順に並べ替える。
            order = sorted(range(count), key=vertex_indices.__getitem__)
            if shared:
                flat = values * count
            elif order == list(range(count)):
                flat = values
            else:
                flat = [value for position in order for value in values[position * width : (position + 1) * width]]
            # normalizeWeightsが1(interactive)だと、normalize=Falseでも合計が1になるよう書き換えられる。
            # 書く間だけ0(none)にして、生の値のまま書く。変えられないときは1値ずつ書く。
            mode_plug = self._dependency_fn().findPlug("normalizeWeights", False)
            mode = mode_plug.asInt()
            if mode != 1 or not (mode_plug.isLocked or mode_plug.isDestination):
                if mode == 1:
                    mode_plug.setInt(0)
                try:
                    skin_fn.setWeights(mesh_path, component, om2.MIntArray([physical[index] for index in logical_indices]), om2.MDoubleArray(flat), False)
                finally:
                    if mode == 1:
                        mode_plug.setInt(mode)
                return
        for position, vertex in enumerate(vertex_indices):
            row = weights_plug.elementByLogicalIndex(vertex).child(0)
            offset = 0 if shared else position * width
            for column, index in enumerate(logical_indices):
                row.elementByLogicalIndex(index).setDouble(values[offset + column])

    @staticmethod
    def _plug_chain_blocked(plug):
        """Plugと、その親・マルチアトリビュート側のどこかに、ロックか入力の接続があるかを調べる。

        :func:`mlib.core.fastWrite.require_writable` が要素から親へたどって行う判定を、
        同じ頂点の要素どうしで使い回すために使う。例外は出さず、書き込めないアトリビュートかどうかも判定しない。

        Args:
            plug (om2.MPlug): 調べ始めるPlug。weightList[v].weights のようなマルチアトリビュートのPlug。

        Returns:
            bool: どこかがロックされているか、入力の接続を持っていればTrue。
        """
        current = plug
        while True:
            if current.isLocked or current.isDestination:
                return True
            if current.isChild:
                current = current.parent()
            elif current.isElement:
                current = current.array()
            else:
                return False

    def _set_weight_values_cmds(self, values, width, vertex_indices, logical_indices):
        """頂点・指定influence列の順に、cmdsで生のウェイト値を書き込む。

        weights[]には疎な論理番号を使う。指定順で論理番号が1ずつ増える列は
        ``weights[a:b]`` の範囲指定で1回のsetAttrにまとめ、番号の穴や順序の入れ替わりで区切る。
        全Plugの事前検査はせず、途中で拒否された場合も先行する書込みを自動で戻さない。
        Undoチャンクは呼出し側が管理する。

        範囲指定のsetAttrはロック・入力接続などで拒否されると範囲内のどの要素も更新しない。
        その場合だけ同じ範囲を要素ごとのsetAttrで書き直し、従来の要素ごとの書込みと同じく
        拒否された要素の手前まで更新して、その要素のMayaのエラーを送出する。

        Args:
            values (list[float]): 検証済みのV*K値または共通K値。
            width (int): 指定列数K。
            vertex_indices (Sequence[int]): 書き込む頂点番号。valuesの行の順。
            logical_indices (list[int]): weights[]の論理番号。指定influence順。

        Returns:
            None: 値を返さない。
        """
        name = self.getFullName()
        runs = self._consecutive_runs(logical_indices)
        shared = len(values) == width
        for position, vertex in enumerate(vertex_indices):
            offset = 0 if shared else position * width
            prefix = f"{name}.weightList[{vertex}].weights"
            for column, first, count in runs:
                start = offset + column
                if count == 1:
                    set_attr(f"{prefix}[{first}]", values[start])
                    continue
                row = values[start : start + count]
                try:
                    set_attr(f"{prefix}[{first}:{first + count - 1}]", *row)
                except RuntimeError:
                    # 範囲指定は失敗時に何も書かないため、要素ごとに書き直して
                    # 拒否された要素までの部分更新とエラーを従来と揃える。
                    for position, value in enumerate(row):
                        set_attr(f"{prefix}[{first + position}]", value)

    @staticmethod
    def _consecutive_runs(logical_indices):
        """指定順の論理番号を、1ずつ増える連続した区間へ分ける。

        Args:
            logical_indices (Sequence[int]): weights[]の論理番号。指定influence順。

        Returns:
            list[tuple[int, int, int]]: 区間ごとの、指定列での開始位置・先頭の論理番号・要素数。
                例えば[0, 1, 3, 2]は[(0, 0, 2), (2, 3, 1), (3, 2, 1)]。
        """
        runs = []
        for column, index in enumerate(logical_indices):
            if runs:
                start, first, count = runs[-1]
                if index == first + count:
                    runs[-1] = (start, first, count + 1)
                    continue
            runs.append((column, index, 1))
        return runs

    def _influence_indices(self, joints, influences):
        """インフルエンスの名前を物理的な番号へ変える。

        1回の操作の中では、UUIDと名前の検索表を作り直さずに使い回す。

        Args:
            joints (Iterable[str]): インフルエンスの名前。この順で番号を返す。
            influences (om2.MDagPathArray): 操作を始めたときのインフルエンスの並び。

        Returns:
            list[int | None]: 入力の順の物理的な番号。登録されていなければNone。
                同じUUIDに複数のパスがある場合は、1つずつ探していた以前の方法と同じく先頭のものを選ぶ。
        """
        joints = list(joints)
        if not joints:
            return []
        if len(joints) == 1:
            # 単数指定では検索表全体を構築せず、一致した時点で終了する。
            joint = joints[0]
            uuid = self._uuid_or_none(joint)
            for index, path in enumerate(influences):
                if (uuid and self._path_uuid(path) == uuid) or path.partialPathName() == joint:
                    return [index]
            return [None]
        by_uuid, by_name = {}, {}
        for index, path in enumerate(influences):
            uuid = self._path_uuid(path)
            if uuid:
                by_uuid.setdefault(uuid, index)
            by_name.setdefault(path.partialPathName(), index)
        result = []
        for joint in joints:
            candidates = (by_uuid.get(self._uuid_or_none(joint)), by_name.get(joint))
            result.append(min((i for i in candidates if i is not None), default=None))
        return result

    def _transfer_pair(self, source_joint, target_joint):
        """sourceのインフルエンスのウェイトをtargetへ移す。

        sourceが影響している頂点を選択し、skinPercentのtransformMoveWeightsを実行する。
        選択の状態は呼び出し側が戻す。

        Args:
            source_joint (str): 移し元のインフルエンスの名前。
            target_joint (str): 移し先のインフルエンスの名前。

        Returns:
            None: 値を返さない。
        """
        cmds.skinCluster(self.getName(), edit=True, selectInfluenceVerts=source_joint)
        if om2.MGlobal.getActiveSelectionList().length():
            cmds.skinPercent(self.getName(), transformMoveWeights=[source_joint, target_joint])

    def _influence_removal_target(self, joint, transfer_to_parent=True, *, force=False):
        """削除可否と祖先移送先を変更前に確認する。

        Args:
            joint: 処理対象のジョイント。
            transfer_to_parent: 削除前にウェイトを親インフルエンスへ移すか。
            force: 不正ウェイトの除去を許可するか。検証中は変更しない。
        """
        _require_bool(transfer_to_parent, "transferToParent")
        _require_bool(force, "force")
        source = joint if isinstance(joint, Node) else Node(joint)
        if not source.isValid() or not self.hasInfluence(source.getFullName()):
            raise ValueError("ジョイントはこのskinClusterのインフルエンスではありません")
        if len(self.getInfluences()) <= 1:
            raise ValueError("最後のインフルエンスは削除できません")
        target = source.getTransferTarget(self) if transfer_to_parent and isinstance(source, Joint) else None
        if force:
            if target is not None:
                # 既存の祖先移送は先頭mesh専用。未対応形状の拒否を修復より前に行う。
                om2.MFnMesh(self.mesh_path)
            self._weight_cleanup_plan(check_layers=False)
        return source, target

    def _influence_removal_plans(self, nodes, transfer_to_parent=True, *, force=False):
        """複数のinfluenceの解除を変更前に検査し、深いものから順の解除計画を返す。シーンは変更しない。

        Args:
            nodes (list[Node]): 解除するinfluence。
            transfer_to_parent (bool): 祖先influenceへウェイトを移すか。
            force (bool): 不正ウェイトの修復を許可するか。検証中は変更しない。

        Returns:
            tuple[list[tuple[Node, str | None]], tuple[list[int], list[float]] | None]: 深い順の、解除する
                influenceと移送先のinfluence名の列と、検査で読んだ列と値(未読ならNone)。
        """
        plans = [self._influence_removal_target(node, transfer_to_parent, force=force) for node in nodes]
        pairs = [plan for plan in plans if plan[1] is not None]
        snapshot = self._require_transferable(pairs) if pairs and not force else None
        depth = {plan[0].getUuid(): plan[0].getDepth() if isinstance(plan[0], Joint) else 0 for plan in plans}
        return sorted(plans, key=lambda plan: depth[plan[0].getUuid()], reverse=True), snapshot

    def _apply_influence_removals(self, plans, snapshot, *, force=False, fast=False, deleting=False):
        """検査済みのinfluenceのウェイトを1回の読み書きで移送し、登録をまとめて解除する。

        親子を同時に外す場合も、途中の列を経由せず最終の移送先へ直接加算する。ngSkinTools2のレイヤーが
        使えるときはレイヤーごとに移送し、skinClusterのウェイトはレイヤーの再計算に任せる。

        Args:
            plans (list[tuple[Node, str | None]]): 深い順の、解除するinfluenceと移送先のinfluence名。
            snapshot (tuple[list[int], list[float]] | None): 検査時に読んだ列と値。Noneは読み直す。
            force (bool): 不正ウェイトを修復してから処理する。
            fast (bool): Trueはウェイトの書込みをOpenMayaで行い、登録解除もUndoへ記録しない。
            deleting (bool): Trueは直後にノードを削除する。0にした列の登録はMayaの削除処理が解除する。

        Returns:
            None: 値を返さない。
        """
        if force:
            self._remove_weight_elements(self._weight_cleanup_plan(check_layers=False)[0], fast=fast)
            snapshot = None
        paths = self._skin_fn.influenceObjects()
        physical = {self._path_uuid(path): index for index, path in enumerate(paths)}
        logical = [self._skin_fn.indexForInfluenceObject(path) for path in paths]
        follow = {physical[source.getUuid()]: None if target is None else physical[self._uuid_or_none(target)] for source, target in plans}
        moves = {}
        for source, target in follow.items():
            while follow.get(target) is not None:
                target = follow[target]
            if target is not None:
                moves[source] = target
        with self._without_undo(fast):
            layered = _move_layer_weights(
                self.getName(),
                {logical[source]: logical[target] for source, target in moves.items()},
                [logical[source] for source, target in follow.items() if target is None],
                [logical[index] for index in range(len(paths)) if index not in follow],
                self._all_vertices()[1],
                fast=fast,
            )
            if moves and not layered:
                self._move_weights(moves, logical, snapshot, fast=fast)
            # 値が残る列を一括で外すと再配分の結果が変わるため、0にした列だけをまとめる。
            emptied = [source.getFullName() for source, target in plans if target is not None]
            if emptied and not deleting:
                cmds.skinCluster(self.getName(), edit=True, removeInfluence=emptied)
            for source, target in plans:
                if target is None:
                    cmds.skinCluster(self.getName(), edit=True, removeInfluence=source.getFullName())

    @contextmanager
    def _without_undo(self, enabled):
        """enabledのとき、処理をUndoへ記録しない。キューは消さない。

        Args:
            enabled (bool): TrueはUndoの記録を止める。Falseは何もしない。

        Yields:
            None: 値を渡さない。
        """
        if not enabled:
            yield
            return
        state = cmds.undoInfo(query=True, state=True)
        cmds.undoInfo(stateWithoutFlush=False)
        try:
            yield
        finally:
            cmds.undoInfo(stateWithoutFlush=state)

    def _move_weights(self, moves, logical, snapshot, *, fast=False):
        """移送元の値を移送先へ加算し、変わった要素だけを書き込む。

        保存値を明示的に加算する(skinPercentの移送は正規化設定に依存するため)。

        Args:
            moves (dict[int, int]): 移送元と最終の移送先の物理番号。
            logical (list[int]): 物理番号から論理番号への対応。
            snapshot (tuple[list[int], list[float]] | None): 読み済みの列と値。Noneは読む。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            None: 値を返さない。
        """
        if snapshot is None:
            columns = sorted(set(moves).union(moves.values()))
            values = list(self._skin_fn.getWeights(self.mesh_path, self._all_vertices()[0], om2.MIntArray(columns)))
        else:
            columns, values = snapshot
        width = len(columns)
        position = {index: offset for offset, index in enumerate(columns)}
        entries = {}
        for source, target in moves.items():
            offset = position[target]
            for vertex, value in enumerate(values[position[source] :: width]):
                if value != 0.0:
                    entries[(vertex, logical[source])] = 0.0
                    values[vertex * width + offset] += value
                    entries[(vertex, logical[target])] = values[vertex * width + offset]
        self._write_weight_entries(sorted(entries.items()), fast=fast)

    def _write_weight_entries(self, entries, *, fast=False):
        """頂点と論理番号で指定した要素へ、生のウェイト値を書き込む。

        Args:
            entries (list[tuple[tuple[int, int], float]]): 頂点と論理番号の順に並べた ((頂点, 論理番号), 値) の列。
            fast (bool): Trueは全要素を検査してからOpenMayaで書き込み、Undoへ記録しない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 要素がロック・入力接続されている、またはMayaが設定を拒否した場合。
        """
        if not fast:
            for vertex, items in groupby(entries, key=lambda entry: entry[0][0]):
                items = list(items)
                self._set_weight_values_cmds([value for _, value in items], len(items), [vertex], [key[1] for key, _ in items])
            return
        weight_list = self._dependency_fn().findPlug("weightList", False)
        attribute_fn = None
        edits = []
        for vertex, items in groupby(entries, key=lambda entry: entry[0][0]):
            row = weight_list.elementByLogicalIndex(vertex).child(0)
            row_blocked = self._plug_chain_blocked(row)
            for (_, index), value in items:
                plug = row.elementByLogicalIndex(index)
                if attribute_fn is None:
                    attribute_fn = om2.MFnAttribute(plug.attribute())
                if row_blocked or plug.isLocked or plug.isDestination:
                    require_writable(plug, attribute_fn)
                edits.append((plug, value))
        for plug, value in edits:
            plug.setDouble(value)

    def _remove_weight_elements(self, elements, *, fast=False):
        """検査済みのウェイト要素を除去する。

        Args:
            elements (list[om2.MPlug]): 除去する要素。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            None: 値を返さない。
        """
        if fast:
            modifier = om2.MDGModifier()
            for plug in elements:
                modifier.removeMultiInstance(plug, False)
            if elements:
                modifier.doIt()
            return
        names = [plug.name() for plug in elements]
        for name in names:
            cmds.removeMultiInstance(name, b=False)

    def _require_transferable(self, pairs):
        """祖先移送で読み書きする列を、変更前に検査する。シーンは変更しない。

        値は読み書きする列の全頂点を調べ、ロック・入力接続は移送元のいずれかにウェイトがある頂点の
        各列だけを調べる。親子を同時に外すと子のウェイトが親の列を経由するため、頂点は全移送元の和で扱う。

        Args:
            pairs (list[tuple[Node, str]]): 移送元のinfluenceと移送先のinfluence名の組。

        Returns:
            tuple[list[int], list[float]]: 読んだ列の物理番号と、頂点順の値。移送で読み直さずに使う。

        Raises:
            ValueError: 対象の列に負値・非有限値がある場合。
            RuntimeError: 書き込む要素のロック・入力接続がある場合。
        """
        sources = {self._require_influences(source.getFullName())[0] for source, _ in pairs}
        columns = sorted(sources.union(self._require_influences(target)[0] for _, target in pairs))
        component, count = self._all_vertices()
        values = list(self._skin_fn.getWeights(self.mesh_path, component, om2.MIntArray(columns)))
        # 非有限値は総和へ伝わるため、全要素を個別に調べず総和と最小値で判定する。
        if not math.isfinite(sum(values)) or (values and min(values) < 0):
            raise ValueError("ウェイトは0以上の有限な数値で指定してください")
        weight_list = self.getPlug("weightList").mplug()
        if weight_list.isLocked or weight_list.isDestination:
            raise RuntimeError("ウェイトがロックされているか、接続されています")
        influences = self._skin_fn.influenceObjects()
        logical = [self._skin_fn.indexForInfluenceObject(influences[index]) for index in columns]
        width = len(columns)
        touched = set()
        for position, index in enumerate(columns):
            if index in sources:
                touched.update(vertex for vertex, value in enumerate(values[position::width]) if value != 0.0)
        for vertex in touched:
            element = weight_list.elementByLogicalIndex(vertex)
            row = element.child(0)
            existing = set(row.getExistingArrayAttributeIndices())
            for plug in [element, row] + [row.elementByLogicalIndex(index) for index in logical if index in existing]:
                if plug.isLocked or plug.isDestination:
                    raise RuntimeError(f"ウェイトのマルチアトリビュートの要素がロックされているか、接続されています: {plug.name()}")
        return columns, values

    def _editable_weights(self):
        """先頭のmeshのすべてのインフルエンスの値を取得する。ロック・接続・レイヤーがあれば拒否する。"""
        names, _ = self._editable_weight_list()
        weights = list(self.getWeights(names))
        if any(not math.isfinite(v) or v < 0 for v in weights):
            raise ValueError("ウェイトは0以上の有限な数値で指定してください")
        return names, weights

    def _editable_weight_list(self, *, check_layers=True):
        """正規化・整理用に全ウェイトの編集条件を検査し、名前列とweightList参照を返す。

        登録influenceが空、lockInfluenceWeightsが有効、既存weightList配下にロック/入力接続、
        またはレイヤー推定の接続があれば拒否する。値の有限性や符号はここでは検査しない。
        この厳密な編集条件は、setWeightsの直接書込みには適用しない。

        Args:
            check_layers (bool): Falseはレイヤー推定の接続を拒否しない。

        Returns:
            tuple[list[str], om2.MPlug]: 物理順のinfluence名と、シーン内weightListへの参照。
                Plugはコピーした値ではない。ロックの一時解除や設定変更は行わない。
        """
        if check_layers:
            self._raise_if_layers()
        names = [node.getName() for node in self._require_unlocked_influences()]
        if not names:
            raise ValueError("インフルエンスがありません")
        weight_list = self.getPlug("weightList").mplug()
        if weight_list.isLocked or weight_list.isDestination:
            raise RuntimeError("ウェイトがロックされているか、接続されています")
        self._require_weight_locks(weight_list)
        return names, weight_list

    def _require_unlocked_influences(self):
        """lockInfluenceWeightsが有効なinfluenceを拒否する。

        Returns:
            list[Node]: 物理順のinfluence。

        Raises:
            RuntimeError: ロックされたinfluenceがある場合。
        """
        influences = self.getInfluences()
        for node in influences:
            if node.hasAttr("lockInfluenceWeights") and node.getPlug("lockInfluenceWeights").get():
                raise RuntimeError(f"インフルエンスがロックされています: {node.getName()}")
        return influences

    def _weight_cleanup_plan(self, *, check_layers=True):
        """既存の疎な要素から不正ウェイトの除去計画を作る。シーンは変更しない。

        Args:
            check_layers (bool): Falseはレイヤー推定の接続を拒否しない。

        Returns:
            tuple[list[om2.MPlug], set[int]]: 除去対象と、修復後も正値を持つ
                登録済みinfluenceの論理番号。存在しない要素は作成しない。

        Raises:
            RuntimeError: ウェイトが編集不可、または除去対象に出力接続がある場合。
        """
        _, weight_list = self._editable_weight_list(check_layers=check_layers)
        registered = {self._skin_fn.indexForInfluenceObject(path) for path in self._skin_fn.influenceObjects()}
        elements, used = [], set()
        for vertex in weight_list.getExistingArrayAttributeIndices():
            row = weight_list.elementByLogicalIndex(vertex).child(0)
            for index in row.getExistingArrayAttributeIndices():
                plug = row.elementByLogicalIndex(index)
                value = plug.asDouble()
                if index not in registered or not math.isfinite(value) or value < 0:
                    if plug.isConnected:
                        raise RuntimeError(f"不正なウェイトが接続されています: {plug.name()}")
                    elements.append(plug)
                elif value > 0:
                    used.add(index)
        return elements, used

    @staticmethod
    def _require_weight_locks(plug):
        """既存の疎なウェイト要素だけを辿りロックを検証する。

        Args:
            plug (om2.MPlug): weightListとその子。未存在要素は作成しない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 要素または親のアトリビュートがロックされている場合。
        """
        if plug.isLocked or plug.isDestination:
            raise RuntimeError(f"ウェイトのマルチアトリビュートの要素がロックされているか、接続されています: {plug.name()}")
        if plug.isArray:
            for index in plug.getExistingArrayAttributeIndices():
                SkinCluster._require_weight_locks(plug.elementByLogicalIndex(index))
        elif plug.isCompound:
            for index in range(plug.numChildren()):
                SkinCluster._require_weight_locks(plug.child(index))

    def _normalized_weights(self, decimals=None, limit=None):
        """すべての頂点ウェイトの正規化・列の削減・10進数の丸めを、メモリの上で計算する。

        - 編集できるかと、値が負でない有限の数かを確かめる。各頂点の合計が0なら拒否する。
        - limitを指定したときは、値の大きい列を残してほかの列を0にする。
        - 桁数を指定したときは、最大剰余法で配分する。値が並んだときは物理的な順番で前にあるものを優先する。

        結果はfloatへ戻す。シーンには書き込まない。

        Args:
            decimals (int | None): 小数点以下の桁数。0〜15。Noneなら丸めない。boolは指定できない。
            limit (int | None): 残す列の数の上限。呼び出し側で確かめた値を渡す。Noneなら列を減らさない。

        Returns:
            tuple[list[str], list[float]]: 物理的な順番のインフルエンスの名前と、頂点の順×インフルエンスの順で1列に並べた値。
        """
        if decimals is not None and (type(decimals) is not int or not 0 <= decimals <= 15):
            raise ValueError("decimalsは0〜15の整数で指定してください")
        names, weights = self._editable_weights()
        width, result = len(names), []
        with localcontext() as context:
            context.prec = 64
            for start in range(0, len(weights), width):
                row = [Decimal(str(v)) for v in weights[start : start + width]]
                if limit is not None:
                    keep = set(sorted(range(width), key=lambda i: (-row[i], i))[:limit])
                    row = [v if i in keep else Decimal(0) for i, v in enumerate(row)]
                total = sum(row)
                if not total:
                    raise ValueError(f"頂点{start // width}のウェイトの合計が0のため、正規化できません")
                row = [v / total for v in row]
                if decimals is not None:
                    scale = 10**decimals
                    scaled = [v * scale for v in row]
                    ticks = [int(v.to_integral_value(rounding=ROUND_FLOOR)) for v in scaled]
                    remaining = scale - sum(ticks)
                    order = sorted(range(width), key=lambda i: (-(scaled[i] - ticks[i]), i))
                    for i in order[:remaining]:
                        ticks[i] += 1
                    row = [Decimal(v) / scale for v in ticks]
                result.extend(float(v) for v in row)
        return names, result

    def _has_layer_plugs(self):
        """スキニングのレイヤーに関係するノードがつながっているかを判定する。

        Returns:
            bool: つながっているノードの名前か型名に、レイヤーを見分けるための文字列が含まれていれば True。
                実際にレイヤーのデータがあるかは調べない。
        """
        # ノード名・型だけが必要。genericアトリビュートを含む接続のPlug生成は避ける。
        fn = self._dependency_fn()
        connected = {om2.MObjectHandle(other.node()).hashCode(): other.node() for plug in fn.getConnections() for other in plug.connectedTo(True, True)}
        for obj in connected.values():
            other_fn = om2.MFnDependencyNode(obj)
            node_name = other_fn.name().lower()
            node_type = other_fn.typeName.lower()
            if any(token in node_name or token in node_type for token in self._LAYER_TOKENS):
                return True
        return False

    def _raise_if_layers(self):
        """スキニングのレイヤーが見つかったら、安全のために処理を止める。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: _has_layer_plugs() が True の場合。
        """
        if self._has_layer_plugs():
            raise RuntimeError("スキニングのレイヤーがある間は実行できません")


class SkinClusters(Nodes):
    """複数のSkinClusterをまとめて持つクラス。重複を除き、入れた順に持つ。"""

    item_class = SkinCluster
