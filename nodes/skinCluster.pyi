# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
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
from typing import Any, Iterable, Iterator, Literal, Sequence
from mlib._stubtypes import GeneratorContextManager
from mlib.common.namespace import Namespace
from mlib.components.component import Component
from mlib.components.component import Components
from mlib.components.vertex import Vertex
from mlib.components.vertex import Vertices
from mlib.json.nameMapping import NameMapping
from mlib.json.snapshot import ValidationReport
from mlib.nodes.dagPose import DagPose
from mlib.nodes.mesh import Mesh
from mlib.nodes.objectSet import ObjectSet
from mlib.nodes.reference import Reference
from mlib.nodes.shadingEngine import ShadingEngine
from mlib.plugs.plug import Plug
from pathlib import Path
from types import ModuleType
from typing import overload
import os
import pathlib


def _finite_number(value: object) -> bool:
    """有限の数値かを判定する。boolは数値として扱わない。

    Args:
        value (object): 判定する値。

    Returns:
        bool: int・floatの有限の値ならTrue。
    """
    ...


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
    mesh: None
    mesh_path: None
    def __init__(self, skinCluster: str | om2.MObject | om2.MDagPath) -> None:
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
        ...
    def mfn(self) -> oma2.MFnSkinCluster:
        """このskinClusterのMFnSkinClusterを取得する。

        呼び出すたびに新しく作る。``oma2.MFnSkinCluster`` は ``om2.MFnDependencyNode`` の派生クラス。
        :meth:`Node.mfn` の決まりどおり、内部で使い回しているfunction setとは別のものを返す。

        Returns:
            oma2.MFnSkinCluster: このskinClusterの function set。

        Raises:
            RuntimeError: ノードが破棄されている場合(削除した後、Undoの記録からも消えた場合)。
        """
        ...
    def deforms(self, geometry: str | Node) -> bool:
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
        ...
    def copyWeightsTo(self, target: str | Node) -> SkinCluster:
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
        ...
    def mirrorWeights(self, axis: str | int = ..., positiveToNegative: bool = ..., surfaceAssociation: str = ..., influenceAssociation: str | Sequence[str] = ..., normalize: bool = ...) -> SkinCluster:
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
        ...
    def pruneWeights(self, threshold: float, normalize: bool = ..., *, fast: bool = ...) -> SkinCluster:
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
        ...
    def getInfluences(self) -> list[Node]:
        """登録されているインフルエンスを取得する。

        並びはAPIのinfluenceObjects()の順(物理的な順番)になる。

        Returns:
            list[Node]: influenceObjects()のDAGパスから作った新しいオブジェクトのリスト。
                登録されている型に応じて、Joint以外も返す。リストの中の位置は、weights[]の論理番号と同じとは限らない。
                ノードを複製することはない。
        """
        ...
    def addInfluences(self, joints: Joint | str | Iterable[Joint | str]) -> SkinCluster:
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
        ...
    def removeInfluences(self, joints: str | Node | Iterable, transferToParent: bool = ..., *, force: bool = ...) -> SkinCluster:
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
        ...
    def getBindPose(self) -> DagPose | None:
        """bindPoseアトリビュートに接続している、保存したポーズを取得する。

        Returns:
            DagPose | None: 接続しているポーズ。接続が無ければNone。

        Raises:
            RuntimeError: skinClusterが無効な場合、または接続先がdagPoseでない場合。
        """
        ...
    def resetBindPose(self) -> SkinCluster:
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
        ...
    def restoreBindPose(self, worldSpace: bool = ..., *, ws: bool = ...) -> SkinCluster:
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
        ...
    def recacheBindMatrices(self) -> SkinCluster:
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
        ...
    def unbind(self, keepHistory: bool = ...) -> None:
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
        ...
    def getUnusedInfluences(self) -> list[Node]:
        """ウェイトを持たないインフルエンスを探す。シーンは変えない。

        Returns:
            list[Node]: インフルエンスの順に並べたノードのオブジェクト。ごく小さな値でも使っているものとして扱い、
                しきい値で切り捨てることはしない。すべてのジオメトリについてMFnSkinClusterで判定する。

        Raises:
            RuntimeError: skinClusterが無効な場合、または取得に失敗した場合。
        """
        ...
    def removeUnusedInfluences(self, *, force: bool = ...) -> list[Node]:
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
        ...
    def removeInvalidWeights(self, *, fast: bool = ...) -> SkinCluster:
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
        ...
    def hasInfluence(self, joint: str) -> bool:
        """指定したjointがインフルエンスに含まれるかを判定する。

        Args:
            joint (str): 判定するjointの名前。

        Returns:
            bool: インフルエンスに含まれていれば ``True``。
        """
        ...
    def getInfluenceVertices(self, influence: str | Node, threshold: float = ...) -> Vertices:
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
        ...
    def getLockedInfluences(self) -> list[Node]:
        """ウェイトをロック(lockInfluenceWeights)しているインフルエンスを取得する。

        Returns:
            list[Node]: ロックしているインフルエンス。並びと型は :meth:`getInfluences` と同じ。
        """
        ...
    def setInfluencesLocked(self, joints: str | Node | Iterable, state: bool = ...) -> SkinCluster:
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
        ...
    def unlockedInfluences(self, joints: str | Node | Iterable | None = ...) -> GeneratorContextManager[SkinCluster]:
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
        ...
    @overload
    def getWeights(self, joints: str | Node | Iterable, *, vertices: Vertex | Vertices | int | str | Iterable | None = ..., rows: Literal[True]) -> list[list[float]]: ...
    @overload
    def getWeights(self, joints: str | Node | Iterable, *, vertices: Vertex | Vertices | int | str | Iterable | None = ..., rows: Literal[False] = ...) -> om2.MDoubleArray: ...
    @overload
    def getWeights(self, joints: str | Node | Iterable, *, vertices: Vertex | Vertices | int | str | Iterable | None = ..., rows: bool = ...) -> om2.MDoubleArray | list[list[float]]:
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
        ...
    def setWeights(self, joints: str | Node | Iterable, weights: Iterable[float] | Iterable[Iterable[float]], *, vertices: Vertex | Vertices | int | str | Iterable | None = ..., normalize: bool = ..., broadcast: bool = ..., rows: bool = ..., fast: bool = ...) -> SkinCluster:
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
        ...
    def getVertexWeights(self, vertex: Vertex | int | str, *, nonzero: bool = ...) -> dict[Node, float]:
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
        ...
    def setVertexWeights(self, vertex: Vertex | int | str, weights: Mapping[str | Node, float], normalize: bool = ..., *, fast: bool = ...) -> SkinCluster:
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
        ...
    def getBlendWeights(self, *, vertices: Vertex | Vertices | int | str | Iterable | None = ...) -> list[float]:
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
        ...
    def setBlendWeights(self, weights: Iterable[float], *, vertices: Vertex | Vertices | int | str | Iterable | None = ..., fast: bool = ...) -> SkinCluster:
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
        ...
    def getWeightsData(self) -> dict:
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
        ...
    def setWeightsData(self, data: dict, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., method: str = ..., fast: bool = ...) -> ValidationReport:
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
        ...
    def exportWeights(self, path: str | os.PathLike) -> pathlib.Path:
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
        ...
    def importWeights(self, path: str | os.PathLike, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., method: str = ..., fast: bool = ...) -> ValidationReport:
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
        ...
    def invertShape(self, sculpted: str | Node, name: str | None = ...) -> Mesh:
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
        ...
    def redistributeWeights(self, vertices: Vertex | Vertices | Iterable[int | Vertex], method: str = ...) -> None:
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
        ...
    def transferWeights(self, sourceTargetPairs: Iterable[tuple[Node | str, Node | str]], *, fast: bool = ...) -> None:
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
        ...
    def removeInfluence(self, joint: Joint | str, transferToParent: bool = ..., *, force: bool = ...) -> None:
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
        ...
    def normalizeWeights(self, decimals: int | None = ..., *, fast: bool = ...) -> SkinCluster:
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
        ...
    def getMaxInfluences(self) -> int:
        """maxInfluencesの設定値を取得する。

        Returns:
            int: skinClusterのmaxInfluencesの設定値。実際に0でないウェイトを持つインフルエンスの数ではない。
        """
        ...
    def setMaxInfluences(self, count: int, maintain: bool = ..., prune: bool = ..., *, fast: bool = ...) -> SkinCluster:
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
        ...
    def isMaintainingMaxInfluences(self) -> bool:
        """ペイントなどの編集で、最大インフルエンス数を保つ設定(maintainMaxInfluences)かを判定する。

        Returns:
            bool: maintainMaxInfluencesが有効ならTrue。
        """
        ...
    def getSkinningMethod(self) -> str:
        """スキニングの方法(skinningMethod)を取得する。

        Returns:
            str: ``"classicLinear"``・``"dualQuaternion"``・``"weightBlended"`` のどれか。
        """
        ...
    def setSkinningMethod(self, method: str) -> SkinCluster:
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
        ...
    def getNormalizeMode(self) -> str:
        """ウェイトの正規化の方法(normalizeWeights)を取得する。

        Returns:
            str: ``"none"``・``"interactive"``・``"post"`` のどれか。
        """
        ...
    def setNormalizeMode(self, mode: str) -> SkinCluster:
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
        ...
    def _prepare_weights_data(self, data: dict, mapping: NameMapping, method: str) -> tuple[dict, list[Node | None], ValidationReport]:
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
        ...
    def _apply_weights_data(self, saved: dict, nodes: list[Node | None], method: str, report: ValidationReport, fast: bool) -> None:
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
        ...
    def _weight_sources(self, saved: dict, method: str) -> Sequence[int]:
        """現在の各頂点が値を使う、保存した頂点の番号を返す。

        Args:
            saved (dict): 検査済みのデータ。
            method (str): ``"index"`` は同じ番号、``"position"`` は最も近い保存位置の頂点。

        Returns:
            Sequence[int]: 現在の頂点番号順の、保存した頂点の番号。
        """
        ...
    def _weight_rows(self, saved: dict, columns: list[int | None], width: int, sources: Sequence[int], report: ValidationReport) -> tuple[list[int], list[float]]:
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
        ...
    def _write_blend_weights(self, blend: list[float] | None, sources: Sequence[int], fast: bool) -> None:
        """DQブレンドウェイトを、現在の値と違う場合だけ全頂点へ書く。

        Args:
            blend (list[float] | None): 保存した頂点ごとの値。Noneは書かない。
            sources (Sequence[int]): 現在の頂点ごとの、保存した頂点の番号。
            fast (bool): TrueはMFnSkinCluster.setBlendWeights、Falseは範囲指定の1回のsetAttr。

        Returns:
            None: 値を返さない。
        """
        ...
    def _apply_weight_settings(self, settings: dict, report: ValidationReport, fast: bool) -> None:
        """スキニングの設定を、現在の値と違うものだけ書く。書けない設定はreportへ記録する。

        Args:
            settings (dict): 検査済みの ``settings``。
            report (ValidationReport): 書かなかった設定の記録先。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            None: 値を返さない。
        """
        ...
    def _capture_ngskin_layers(self, paths: om2.MDagPathArray) -> list[dict] | None:
        """ngSkinTools2のレイヤーを、:meth:`getWeightsData` の ``ngSkinLayers`` の形で取得する。

        Args:
            paths (om2.MDagPathArray): influenceObjects()。レイヤーの論理番号を保存の位置へ変換する。

        Returns:
            list[dict] | None: レイヤーごとの辞書。ngSkinTools2を使えない、またはレイヤーが無ければNone。
        """
        ...
    def _apply_ngskin_layers(self, saved_layers: list[dict] | None, columns: list[int | None], logical: list[int], sources: Sequence[int], report: ValidationReport, fast: bool) -> None:
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
        ...
    @staticmethod
    def _ngskin_api() -> ModuleType | None:
        """読み込み済みのngSkinTools2のAPIを返す。

        Returns:
            module | None: ``ngSkinTools2.api``。プラグイン未ロード・APIなしはNone。
        """
        ...
    def _input_points(self) -> om2.MPointArray:
        """skinClusterに入る前の形状の頂点位置(オブジェクト空間、cm)を返す。

        入力の形状を読めない場合は、出力のMeshの位置を返す。

        Returns:
            om2.MPointArray: 頂点番号順の位置。
        """
        ...
    @classmethod
    def _parse_weights_data(cls, data: dict) -> dict:
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
        ...
    @classmethod
    def _parse_weight_settings(cls, settings: dict | None) -> dict:
        """``settings`` の形を確かめる。

        Args:
            settings (dict | None): 保存した設定。Noneは設定を書かない。

        Returns:
            dict: 4つの設定。保存に無い設定はNone。

        Raises:
            ValueError: 形または値が不正な場合。
        """
        ...
    @staticmethod
    def _parse_ngskin_layers(layers: list[dict] | None, width: int, count: int) -> list[dict] | None:
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
        ...
    def _inverted_points(self, sculpted_points: om2.MPointArray) -> list[tuple[float, float, float]]:
        """:meth:`invertShape` の頂点の位置(Origの空間)を計算する。シーンは変更しない。

        Args:
            sculpted_points (om2.MPointArray): 現在のポーズで整えた形のオブジェクト空間の頂点。

        Returns:
            list[tuple[float, float, float]]: 頂点番号順の補正形状の位置(cm)。
        """
        ...
    @staticmethod
    def _plug_matrix(plug: om2.MPlug) -> om2.MMatrix:
        """matrix 型のアトリビュートの値を読む。値の無い要素は単位マトリクスにする。

        Args:
            plug (om2.MPlug): matrix 型のアトリビュートの Plug。

        Returns:
            om2.MMatrix: 値。
        """
        ...
    @staticmethod
    def _geometry_skin_uuids(node: Node) -> list[str]:
        """形状を変形しているskinClusterのUUIDを集める。

        集め方はDagNode.getSkinClustersと同じ。Jointの同じ名前のメソッドは、インフルエンスとしての接続を
        調べる別の意味のものなので、DagNodeの実装を直接呼ぶ。

        Args:
            node (Node): 調べるノード。DAGノードでなければ空になる。

        Returns:
            list[str]: skinClusterのUUIDの文字列。並びはgetSkinClustersと同じ。
        """
        ...
    def _uuid_or_none(self, node: str) -> str | None:
        """ノードの名前からMayaのUUIDを取得する。

        Args:
            node (str): UUIDを調べるノードの名前。

        Returns:
            str | None: ノードのUUID。ノードが無ければNone。
        """
        ...
    @staticmethod
    def _path_uuid(path: om2.MDagPath) -> str | None:
        """インフルエンスのDAGパスから、名前を使わずにMayaのUUIDを取得する。

        ``_uuid_or_none(path.fullPathName())`` と同じ値を、名前から探し直さずに求める。

        Args:
            path (om2.MDagPath): influenceObjects()のパス。

        Returns:
            str | None: ノードのUUID。パスかノードが無効ならNone。
        """
        ...
    def _mesh_node(self) -> om2.MObject:
        """オブジェクトを作ったときの、先頭のジオメトリのMObjectを返す。

        Returns:
            om2.MObject: mesh_pathが指すノード。
        """
        ...
    def _geometry_dag_path(self, name: str) -> om2.MDagPath:
        """ジオメトリの名前から、shapeまでたどったMDagPathを取得する。

        Args:
            name (str): ジオメトリのノードの名前。

        Returns:
            om2.MDagPath: DAGパス。Transformの名前なら、その下のshapeまでたどったパス。
        """
        ...
    def _first_geometry_name(self) -> str:
        """skinClusterが変形している先頭のジオメトリの名前を取得する。

        Returns:
            str: skinClusterに登録されている先頭のジオメトリの名前(フルパス)。

        Raises:
            IndexError: ジオメトリが無い場合。
        """
        ...
    def _influence_index(self, joint: str) -> int | None:
        """登録されているインフルエンスの名前・UUIDと比べて、物理的な番号を取得する。

        Args:
            joint (str): 探すインフルエンスの名前。

        Returns:
            int | None: influenceObjects()のリストの中の位置。UUIDかpartialの名前が一致する候補のうち、
                最初のものの物理的な番号を返し、weights[]の論理番号は返さない。登録されていなければNone。
        """
        ...
    def _all_vertices(self) -> tuple[om2.MObject, int]:
        """meshのすべての頂点のcomponentと、頂点の数を作る。

        Returns:
            tuple[om2.MObject, int]: すべての頂点を含むcomponentと、頂点の数。
        """
        ...
    def _require_influences(self, joints: str | Node | Iterable) -> list[int]:
        """インフルエンスの指定を確かめ、指定した順の物理的な番号へ変える。シーンは変えない。

        Args:
            joints (str | Node | Iterable): インフルエンスの指定。この順で番号を返す。

        Returns:
            list[int]: influenceObjects()の中での物理的な番号。weights[]の論理番号ではない。

        Raises:
            TypeError: 頂点などのコンポーネントやアトリビュートを渡した場合、または入力の型が正しくない場合。
            ValueError: 空・未登録・重複の場合。
        """
        ...
    def _vertex_indices(self, vertices: Vertex | Vertices | int | str | Iterable | None) -> list[int] | None:
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
        ...
    @staticmethod
    def _vertex_name_indices(name: str, mesh: om2.MObject, num_vertices: int) -> list[int]:
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
        ...
    def _single_vertex_index(self, vertex: Vertex | int | str) -> int:
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
        ...
    def _read_rows(self, vertex_indices: Sequence[int], physical_indices: Iterable[int]) -> list[list[float]]:
        """指定頂点・指定influenceのウェイトを、頂点ごとの行として読み取る。

        MFnSkinCluster.getWeightsはcomponentの番号を昇順で返すため、昇順で読んでから指定順へ並べ直す。

        Args:
            vertex_indices (Sequence[int]): 検証済みの頂点番号。重複なし。
            physical_indices (Iterable[int]): influenceObjects()内の物理番号。

        Returns:
            list[list[float]]: vertex_indicesの順の行。各行はphysical_indicesの順。
        """
        ...
    @staticmethod
    def _influence_locked(path: om2.MDagPath) -> bool:
        """influenceのlockInfluenceWeightsが有効か調べる。アトリビュートが無い型はFalse。

        Args:
            path (om2.MDagPath): influenceObjects()のパス。

        Returns:
            bool: ロックされている場合True。
        """
        ...
    @staticmethod
    def _normalize_row(row: list[float], vertex: int, specified: Iterable[int], free: Iterable[int], locked: Iterable[int]) -> None:
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
        ...
    def _normalized_write(self, values: list[float], width: int, vertex_indices: Sequence[int], physical_indices: list[int]) -> tuple[list[float], list[int]]:
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
        ...
    def _copy_destination(self, target: str | Node) -> SkinCluster:
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
        ...
    @staticmethod
    def _has_geometry(path: om2.MDagPath) -> bool:
        """DAGパスが形状、または直下に中間でない形状を持つTransformか調べる。

        Args:
            path (om2.MDagPath): 調べるパス。

        Returns:
            bool: 形状を持つ場合True。
        """
        ...
    @staticmethod
    def _require_choice(value: str, name: str, choices: Sequence[str]) -> str:
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
        ...
    def _flatten_weight_rows(self, joints: str | Node | Iterable, weights: Iterable[Iterable[float]]) -> list[object]:
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
        ...
    def _prepare_weight_values(self, joints: Iterable, weights: Iterable, vertices: object = ..., broadcast: bool = ...) -> tuple:
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
        ...
    def _set_weight_values_fast(self, values: list[float], width: int, vertex_indices: Sequence[int], logical_indices: list[int]) -> None:
        """全対象ウェイトPlugを検査し、頂点・指定列の順にOpenMayaで生値を書き込む。

        writable/check_rangeを全件に適用してからsetDoubleを始める。MFnSkinCluster.setWeightsは
        未指定列を再配分し得るため使わない。liwや正規化設定も変更しない。
        事前検査後のAPI書込み失敗は自動で戻さず、Undo設定を変更しない。

        Args:
            values (list[float]): 検証済みのV*K値または共通K値。
            width (int): 指定列数K。
            vertex_indices (Sequence[int]): 書き込む頂点番号。valuesの行の順。
            logical_indices (list[int]): weights[]の論理番号。指定influence順。

        Returns:
            None: 値を返さない。
        """
        ...
    @staticmethod
    def _plug_chain_blocked(plug: om2.MPlug) -> bool:
        """Plugと、その親・マルチアトリビュート側のどこかに、ロックか入力の接続があるかを調べる。

        :func:`mlib.core.fastWrite.require_writable` が要素から親へたどって行う判定を、
        同じ頂点の要素どうしで使い回すために使う。例外は出さず、書き込めないアトリビュートかどうかも判定しない。

        Args:
            plug (om2.MPlug): 調べ始めるPlug。weightList[v].weights のようなマルチアトリビュートのPlug。

        Returns:
            bool: どこかがロックされているか、入力の接続を持っていればTrue。
        """
        ...
    def _set_weight_values_cmds(self, values: list[float], width: int, vertex_indices: Sequence[int], logical_indices: list[int]) -> None:
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
        ...
    @staticmethod
    def _consecutive_runs(logical_indices: Sequence[int]) -> list[tuple[int, int, int]]:
        """指定順の論理番号を、1ずつ増える連続した区間へ分ける。

        Args:
            logical_indices (Sequence[int]): weights[]の論理番号。指定influence順。

        Returns:
            list[tuple[int, int, int]]: 区間ごとの、指定列での開始位置・先頭の論理番号・要素数。
                例えば[0, 1, 3, 2]は[(0, 0, 2), (2, 3, 1), (3, 2, 1)]。
        """
        ...
    def _influence_indices(self, joints: Iterable[str], influences: om2.MDagPathArray) -> list[int | None]:
        """インフルエンスの名前を物理的な番号へ変える。

        1回の操作の中では、UUIDと名前の検索表を作り直さずに使い回す。

        Args:
            joints (Iterable[str]): インフルエンスの名前。この順で番号を返す。
            influences (om2.MDagPathArray): 操作を始めたときのインフルエンスの並び。

        Returns:
            list[int | None]: 入力の順の物理的な番号。登録されていなければNone。
                同じUUIDに複数のパスがある場合は、1つずつ探していた以前の方法と同じく先頭のものを選ぶ。
        """
        ...
    def _transfer_pair(self, source_joint: str, target_joint: str) -> None:
        """sourceのインフルエンスのウェイトをtargetへ移す。

        sourceが影響している頂点を選択し、skinPercentのtransformMoveWeightsを実行する。
        選択の状態は呼び出し側が戻す。

        Args:
            source_joint (str): 移し元のインフルエンスの名前。
            target_joint (str): 移し先のインフルエンスの名前。

        Returns:
            None: 値を返さない。
        """
        ...
    def _influence_removal_target(self, joint, transfer_to_parent=..., *, force=...):
        """削除可否と祖先移送先を変更前に確認する。

        Args:
            joint: 処理対象のジョイント。
            transfer_to_parent: 削除前にウェイトを親インフルエンスへ移すか。
            force: 不正ウェイトの除去を許可するか。検証中は変更しない。
        """
        ...
    def _influence_removal_plans(self, nodes: list[Node], transfer_to_parent: bool = ..., *, force: bool = ...) -> tuple[list[tuple[Node, str | None]], tuple[list[int], list[float]] | None]:
        """複数のinfluenceの解除を変更前に検査し、深いものから順の解除計画を返す。シーンは変更しない。

        Args:
            nodes (list[Node]): 解除するinfluence。
            transfer_to_parent (bool): 祖先influenceへウェイトを移すか。
            force (bool): 不正ウェイトの修復を許可するか。検証中は変更しない。

        Returns:
            tuple[list[tuple[Node, str | None]], tuple[list[int], list[float]] | None]: 深い順の、解除する
                influenceと移送先のinfluence名の列と、検査で読んだ列と値(未読ならNone)。
        """
        ...
    def _apply_influence_removals(self, plans: list[tuple[Node, str | None]], snapshot: tuple[list[int], list[float]] | None, *, force: bool = ..., fast: bool = ..., deleting: bool = ...) -> None:
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
        ...
    def _without_undo(self, enabled: bool) -> GeneratorContextManager[None]:
        """enabledのとき、処理をUndoへ記録しない。キューは消さない。

        Args:
            enabled (bool): TrueはUndoの記録を止める。Falseは何もしない。

        Yields:
            None: 値を渡さない。
        """
        ...
    def _move_weights(self, moves: dict[int, int], logical: list[int], snapshot: tuple[list[int], list[float]] | None, *, fast: bool = ...) -> None:
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
        ...
    def _write_weight_entries(self, entries: list[tuple[tuple[int, int], float]], *, fast: bool = ...) -> None:
        """頂点と論理番号で指定した要素へ、生のウェイト値を書き込む。

        Args:
            entries (list[tuple[tuple[int, int], float]]): 頂点と論理番号の順に並べた ((頂点, 論理番号), 値) の列。
            fast (bool): Trueは全要素を検査してからOpenMayaで書き込み、Undoへ記録しない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 要素がロック・入力接続されている、またはMayaが設定を拒否した場合。
        """
        ...
    def _remove_weight_elements(self, elements: list[om2.MPlug], *, fast: bool = ...) -> None:
        """検査済みのウェイト要素を除去する。

        Args:
            elements (list[om2.MPlug]): 除去する要素。
            fast (bool): TrueはUndoなしのOpenMaya更新。

        Returns:
            None: 値を返さない。
        """
        ...
    def _require_transferable(self, pairs: list[tuple[Node, str]]) -> tuple[list[int], list[float]]:
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
        ...
    def _editable_weights(self):
        """先頭のmeshのすべてのインフルエンスの値を取得する。ロック・接続・レイヤーがあれば拒否する。"""
        ...
    def _editable_weight_list(self, *, check_layers: bool = ...) -> tuple[list[str], om2.MPlug]:
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
        ...
    def _require_unlocked_influences(self) -> list[Node]:
        """lockInfluenceWeightsが有効なinfluenceを拒否する。

        Returns:
            list[Node]: 物理順のinfluence。

        Raises:
            RuntimeError: ロックされたinfluenceがある場合。
        """
        ...
    def _weight_cleanup_plan(self, *, check_layers: bool = ...) -> tuple[list[om2.MPlug], set[int]]:
        """既存の疎な要素から不正ウェイトの除去計画を作る。シーンは変更しない。

        Args:
            check_layers (bool): Falseはレイヤー推定の接続を拒否しない。

        Returns:
            tuple[list[om2.MPlug], set[int]]: 除去対象と、修復後も正値を持つ
                登録済みinfluenceの論理番号。存在しない要素は作成しない。

        Raises:
            RuntimeError: ウェイトが編集不可、または除去対象に出力接続がある場合。
        """
        ...
    @staticmethod
    def _require_weight_locks(plug: om2.MPlug) -> None:
        """既存の疎なウェイト要素だけを辿りロックを検証する。

        Args:
            plug (om2.MPlug): weightListとその子。未存在要素は作成しない。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: 要素または親のアトリビュートがロックされている場合。
        """
        ...
    def _normalized_weights(self, decimals: int | None = ..., limit: int | None = ...) -> tuple[list[str], list[float]]:
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
        ...
    def _has_layer_plugs(self) -> bool:
        """スキニングのレイヤーに関係するノードがつながっているかを判定する。

        Returns:
            bool: つながっているノードの名前か型名に、レイヤーを見分けるための文字列が含まれていれば True。
                実際にレイヤーのデータがあるかは調べない。
        """
        ...
    def _raise_if_layers(self) -> None:
        """スキニングのレイヤーが見つかったら、安全のために処理を止める。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: _has_layer_plugs() が True の場合。
        """
        ...


class SkinClusters(Nodes[SkinCluster]):
    """複数のSkinClusterをまとめて持つクラス。重複を除き、入れた順に持つ。"""
    def __iter__(self) -> Iterator[SkinCluster]: ...
    @overload
    def __getitem__(self, index: int) -> SkinCluster: ...
    @overload
    def __getitem__(self, index: slice) -> SkinClusters: ...
    item_class: Any
    def mfn(self) -> list[oma2.MFnSkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.mfn` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def deforms(self, geometry: str | Node) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.deforms` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def copyWeightsTo(self, target: str | Node) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.copyWeightsTo` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mirrorWeights(self, axis: str | int = ..., positiveToNegative: bool = ..., surfaceAssociation: str = ..., influenceAssociation: str | Sequence[str] = ..., normalize: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.mirrorWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def pruneWeights(self, threshold: float, normalize: bool = ..., *, fast: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.pruneWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getInfluences(self) -> list[list[Node]]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def addInfluences(self, joints: Joint | str | Iterable[Joint | str]) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.addInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def removeInfluences(self, joints: str | Node | Iterable, transferToParent: bool = ..., *, force: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.removeInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBindPose(self) -> list[DagPose | None]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getBindPose` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def resetBindPose(self) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.resetBindPose` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def restoreBindPose(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.restoreBindPose` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def recacheBindMatrices(self) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.recacheBindMatrices` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def unbind(self, keepHistory: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.unbind` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUnusedInfluences(self) -> list[list[Node]]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getUnusedInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def removeUnusedInfluences(self, *, force: bool = ...) -> list[list[Node]]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.removeUnusedInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def removeInvalidWeights(self, *, fast: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.removeInvalidWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def hasInfluence(self, joint: str) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.hasInfluence` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getInfluenceVertices(self, influence: str | Node, threshold: float = ...) -> list[Vertices]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getInfluenceVertices` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getLockedInfluences(self) -> list[list[Node]]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getLockedInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setInfluencesLocked(self, joints: str | Node | Iterable, state: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.setInfluencesLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getWeights(self, joints: str | Node | Iterable, *, vertices: Vertex | Vertices | int | str | Iterable | None = ..., rows: bool = ...) -> list[om2.MDoubleArray | list[list[float]]]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setWeights(self, joints: str | Node | Iterable, weights: Iterable[float] | Iterable[Iterable[float]], *, vertices: Vertex | Vertices | int | str | Iterable | None = ..., normalize: bool = ..., broadcast: bool = ..., rows: bool = ..., fast: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.setWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getVertexWeights(self, vertex: Vertex | int | str, *, nonzero: bool = ...) -> list[dict[Node, float]]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getVertexWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setVertexWeights(self, vertex: Vertex | int | str, weights: Mapping[str | Node, float], normalize: bool = ..., *, fast: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.setVertexWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBlendWeights(self, *, vertices: Vertex | Vertices | int | str | Iterable | None = ...) -> list[list[float]]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getBlendWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setBlendWeights(self, weights: Iterable[float], *, vertices: Vertex | Vertices | int | str | Iterable | None = ..., fast: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.setBlendWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getWeightsData(self) -> list[dict]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getWeightsData` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setWeightsData(self, data: dict, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., method: str = ..., fast: bool = ...) -> list[ValidationReport]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.setWeightsData` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def exportWeights(self, path: str | os.PathLike) -> list[pathlib.Path]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.exportWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def importWeights(self, path: str | os.PathLike, *, nameMap: dict[str, str] | None = ..., replace: Iterable[tuple[str, str]] | None = ..., namespaceMap: dict[str, str] | None = ..., method: str = ..., fast: bool = ...) -> list[ValidationReport]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.importWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def invertShape(self, sculpted: str | Node, name: str | None = ...) -> list[Mesh]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.invertShape` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def redistributeWeights(self, vertices: Vertex | Vertices | Iterable[int | Vertex], method: str = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.redistributeWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def transferWeights(self, sourceTargetPairs: Iterable[tuple[Node | str, Node | str]], *, fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.transferWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def removeInfluence(self, joint: Joint | str, transferToParent: bool = ..., *, force: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.removeInfluence` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def normalizeWeights(self, decimals: int | None = ..., *, fast: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.normalizeWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getMaxInfluences(self) -> list[int]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getMaxInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setMaxInfluences(self, count: int, maintain: bool = ..., prune: bool = ..., *, fast: bool = ...) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.setMaxInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isMaintainingMaxInfluences(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.isMaintainingMaxInfluences` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSkinningMethod(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getSkinningMethod` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setSkinningMethod(self, method: str) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.setSkinningMethod` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNormalizeMode(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.getNormalizeMode` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setNormalizeMode(self, mode: str) -> list[SkinCluster]:
        """各要素の :meth:`~mlib.nodes.skinCluster.SkinCluster.setNormalizeMode` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getGeometry(self) -> list[list[Node]]:
        """各要素の :meth:`~mlib.nodes.geometryFilter.GeometryFilter.getGeometry` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getInputGeometry(self) -> list[list[Node]]:
        """各要素の :meth:`~mlib.nodes.geometryFilter.GeometryFilter.getInputGeometry` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDeformerWeights(self, geometryIndex: int = ...) -> list[list[float]]:
        """各要素の :meth:`~mlib.nodes.geometryFilter.GeometryFilter.getDeformerWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setDeformerWeights(self, weights: Iterable[float], *, vertices: Component | Components | Iterable[int] | None = ..., geometryIndex: int = ..., fast: bool = ...) -> list[GeometryFilter]:
        """各要素の :meth:`~mlib.nodes.geometryFilter.GeometryFilter.setDeformerWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def dumpDeformerWeights(self, path: str | Path, geometryIndex: int | None = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.geometryFilter.GeometryFilter.dumpDeformerWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def loadDeformerWeights(self, path: str | Path, *, fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.geometryFilter.GeometryFilter.loadDeformerWeights` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def copyDeformerWeightsTo(self, other: GeometryFilter | str, *, geometryIndex: int = ..., otherGeometryIndex: int = ..., fast: bool = ...) -> list[GeometryFilter]:
        """各要素の :meth:`~mlib.nodes.geometryFilter.GeometryFilter.copyDeformerWeightsTo` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getShadingEngines(self) -> list[list[ShadingEngine]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getShadingEngines` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def sameNode(self, other: object) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.sameNode` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isValid(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isValid` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isAlive(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isAlive` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mnode(self) -> list[om2.MObject]:
        """各要素の :meth:`~mlib.nodes.node.Node.mnode` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getType(self, inherited: bool = ...) -> list[str | list[str]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def hasFn(self, fn: int) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.hasFn` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTypeId(self) -> list[int]:
        """各要素の :meth:`~mlib.nodes.node.Node.getTypeId` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPluginName(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.node.Node.getPluginName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getClassification(self) -> list[list[str]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getClassification` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isType(self, nodeType: str) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isLocked(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isFromReferencedFile(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isFromReferencedFile` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getReference(self) -> list[Reference | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.getReference` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isDefaultNode(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isDefaultNode` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSets(self, type: str | None = ...) -> list[list[ObjectSet]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getSets` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isAncestorOf(self, other: Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isAncestorOf` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isParentOf(self, other: Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isParentOf` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isRoot(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.isRoot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNodeName(self, removeNamespace: bool = ...) -> list[str]:
        """各要素の :meth:`~mlib.nodes.node.Node.getNodeName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNamespace(self) -> list[Namespace]:
        """各要素の :meth:`~mlib.nodes.node.Node.getNamespace` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setNamespace(self, namespace: str | Namespace, *, fast: bool = ...) -> list[Node]:
        """各要素の :meth:`~mlib.nodes.node.Node.setNamespace` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def delete(self, *, safe: bool = ..., fast: bool = ...) -> list[None]:
        """各要素の :meth:`~mlib.nodes.node.Node.delete` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def rename(self, name: str, ignoreShape: bool = ..., *, fast: bool = ...) -> list[Node]:
        """各要素の :meth:`~mlib.nodes.node.Node.rename` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def duplicate(self, name: str | None = ..., *, suffix: str | None = ..., **kwargs: object) -> list[Node]:
        """各要素の :meth:`~mlib.nodes.node.Node.duplicate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getConnections(self, s: bool = ..., d: bool = ..., c: bool = ..., t: str | None = ..., et: bool = ..., scn: bool = ..., source: bool = ..., destination: bool = ..., connections: bool = ..., type: str | None = ..., exactType: bool = ..., skipConversionNodes: bool = ..., asPair: bool = ..., asNode: bool = ..., index: int | None = ...) -> list[list | Plug | Node | tuple | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.getConnections` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setKey(self, attributes: str | Iterable[str] | None = ..., *, unit: str | None = ..., timeUnit: str | None = ..., uiUnits: bool = ..., **kwargs) -> list[Node]:
        """各要素の :meth:`~mlib.nodes.node.Node.setKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def removeKey(self, attributes: str | Iterable[str] | None = ..., *, time: float | Sequence[float] | None = ..., timeUnit: str | None = ...) -> list[Node]:
        """各要素の :meth:`~mlib.nodes.node.Node.removeKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def moveKey(self, attributes: str | Iterable[str] | None = ..., *, time: float | Sequence[float] | None = ..., timeOffset: float = ..., valueOffset: float = ..., unit: str | None = ..., timeUnit: str | None = ...) -> list[Node]:
        """各要素の :meth:`~mlib.nodes.node.Node.moveKey` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getHistory(self, type: str | None = ..., future: bool = ...) -> list[list[Node]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getHistory` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def findCycles(self) -> list[list[list[Plug]]]:
        """各要素の :meth:`~mlib.nodes.node.Node.findCycles` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPlugs(self, userDefined: bool = ..., includeChildren: bool = ..., *, writable: bool = ..., **listAttrFlags) -> list[list[Plug]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getPlugs` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getAliases(self) -> list[list[tuple[str, Plug]]]:
        """各要素の :meth:`~mlib.nodes.node.Node.getAliases` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def addAttr(self, longName: str = ..., type: str | None = ..., subType: str | None = ..., channelBox: bool = ..., childNames: Sequence[str] | None = ..., childShortNames: Sequence[str] | None = ..., childSuffixes: Sequence[str] | None = ..., proxy: Plug | str | None = ..., getPlug: bool = ..., *, safe: bool = ..., fast: bool = ..., unit: str = ..., timeUnit: str = ..., attributeType: str = ..., at: str = ..., binaryTag: str = ..., bt: str = ..., cachedInternally: bool = ..., ci: bool = ..., category: str | Sequence[str] = ..., ct: str | Sequence[str] = ..., dataType: str | Sequence[str] = ..., dt: str | Sequence[str] = ..., defaultValue: object = ..., dv: object = ..., disconnectBehaviour: int = ..., dcb: int = ..., edit: bool = ..., e: bool = ..., enforcingUniqueName: bool = ..., eun: bool = ..., enumName: str = ..., en: str = ..., exists: bool = ..., ex: bool = ..., fromPlugin: bool = ..., fp: bool = ..., hasMaxValue: bool = ..., hxv: bool = ..., hasMinValue: bool = ..., hnv: bool = ..., hasSoftMaxValue: bool = ..., hsx: bool = ..., hasSoftMinValue: bool = ..., hsn: bool = ..., hidden: bool = ..., h: bool = ..., indexMatters: bool = ..., im: bool = ..., internalSet: bool = ..., keyable: bool = ..., k: bool = ..., ln: str = ..., maxValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., max: float | om2.MAngle | om2.MDistance | om2.MTime = ..., minValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., min: float | om2.MAngle | om2.MDistance | om2.MTime = ..., multi: bool = ..., m: bool = ..., niceName: str = ..., nn: str = ..., numberOfChildren: int = ..., nc: int = ..., parent: str = ..., p: str = ..., pxy: Plug | str | None = ..., query: bool = ..., q: bool = ..., readable: bool = ..., r: bool = ..., shortName: str = ..., sn: str = ..., softMaxValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., smx: float | om2.MAngle | om2.MDistance | om2.MTime = ..., softMinValue: float | om2.MAngle | om2.MDistance | om2.MTime = ..., smn: float | om2.MAngle | om2.MDistance | om2.MTime = ..., storable: bool = ..., s: bool = ..., usedAsColor: bool = ..., uac: bool = ..., usedAsFilename: bool = ..., uaf: bool = ..., usedAsProxy: bool = ..., uap: bool = ..., worldSpace: bool = ..., ws: bool = ..., writable: bool = ..., w: bool = ..., cb: bool = ..., **kwargs) -> list[Plug | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.addAttr` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def moveAttrOrder(self, name: str, offset: int) -> list[Node]:
        """各要素の :meth:`~mlib.nodes.node.Node.moveAttrOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPlug(self, name: str) -> list[Plug]:
        """各要素の :meth:`~mlib.nodes.node.Node.getPlug` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def hasAttr(self, name: str) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.node.Node.hasAttr` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUuid(self) -> list[str | None]:
        """各要素の :meth:`~mlib.nodes.node.Node.getUuid` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getName(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.node.Node.getName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.node.Node.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
