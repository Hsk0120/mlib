# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ジョイントのクラスと、ジョイントのコレクションを提供する。"""

import math
from contextlib import contextmanager
from typing import Any, Dict, List
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.fastWrite import require_writable, set_attr
from ..core.nodeEdit import check_deletion, delete_nodes
from ..decorator import _edit_context, _pick_alias, _require_bool, undoChunk
from ..maths import EulerRotate, Matrix, Scale, Vector
from ..util import _MIRROR_PLANES, _UNSET, _finite_vector, _mirror_axis, _world_space
from .node import Node, Nodes
from .transform import Transform, _closest_euler
from typing import Any, Iterable, Iterator, Sequence
from mlib._stubtypes import GeneratorContextManager
from mlib.common.namespace import Namespace
from mlib.components.component import Component
from mlib.components.component import Components
from mlib.maths.quaternion import Quaternion
from mlib.maths.shear import Shear
from mlib.maths.translate import Translate
from mlib.nodes.constraint import Constraint
from mlib.nodes.dagNode import DagNode
from mlib.nodes.dagPose import DagPose
from mlib.nodes.ikHandle import IkHandle
from mlib.nodes.objectSet import ObjectSet
from mlib.nodes.reference import Reference
from mlib.nodes.shadingEngine import ShadingEngine
from mlib.nodes.shape import Shape
from mlib.nodes.skinCluster import SkinCluster
from mlib.nodes.skinCluster import SkinClusters
from mlib.plugs.plug import Plug
from typing import overload
import os
import pathlib

_ORIENTATIONS: tuple
_SECONDARY_AXES: tuple

def _orient_flags(orientation: str, secondaryAxisOrient: str, children: bool, zeroScaleOrient: bool) -> dict:
    """Joint.orientの引数を検証し、cmds.jointへ渡すフラグを返す。

    Args:
        orientation (str): 主軸・副軸・第3軸の順の軸名、または ``"none"``。
        secondaryAxisOrient (str): 副軸を向けるワールド軸。
        children (bool): 子孫jointも処理するか。
        zeroScaleOrient (bool): scaleOrientを0にするか。

    Returns:
        dict: ``cmds.joint(edit=True, ...)`` のフラグ。

    Raises:
        TypeError: 文字列・bool以外の場合。
        ValueError: 対応しない軸名の場合。
    """
    ...

def _unlocked_influences(skins: Iterable[SkinCluster], fast: bool = ...) -> GeneratorContextManager[None]:
    """skinClusterのウェイトのロックを一時的に外し、抜けるときに元へ戻す。

    Args:
        skins (Iterable[SkinCluster]): ロックを外すskinCluster。
        fast (bool): Trueはロックの切替えをUndoへ記録しない。

    Yields:
        None: 値を渡さない。

    Raises:
        RuntimeError: lockInfluenceWeightsがロック・入力接続されていて切り替えられない場合。何も変更しない。
    """
    ...

def _influences_by_skin(joints: Iterable[Joint]) -> list[tuple[SkinCluster, list[Joint]]]:
    """jointを、登録先のskinClusterごとにまとめる。

    Args:
        joints (Iterable[Joint]): 調べるjoint。

    Returns:
        list[tuple[SkinCluster, list[Joint]]]: skinClusterと、そこへ登録されたjoint。
    """
    ...

def _remove_influences(groups: list[tuple[SkinCluster, list[Joint]]], transfer_to_parent: bool, force: bool, fast: bool = ..., deleting: bool = ...) -> None:
    """ウェイトのロックを一時的に外し、全skinClusterを検査してから深いinfluenceから順に解除する。

    Args:
        groups (list[tuple[SkinCluster, list[Joint]]]): skinClusterと解除するjoint。
        transfer_to_parent (bool): 祖先influenceへウェイトを移すか。
        force (bool): 不正ウェイトを修復してから解除するか。
        fast (bool): Trueはウェイトの書込みをOpenMayaで行い、Undoへ記録しない。
        deleting (bool): Trueは直後にjointを削除する。

    Returns:
        None: 値を返さない。
    """
    ...

def _delete_joints(joints: Sequence[Joint], safe: bool, fast: bool, remove_influence: bool, transfer_to_parent: bool, force: bool) -> None:
    """jointを、消える階層のinfluenceを解除してから一括で削除する。

    Args:
        joints (Sequence[Joint]): 削除するjoint。
        safe (bool): Trueは自身またはDAG子孫にDG接続があるjointを削除しない。
        fast (bool): TrueはUndoなしのOpenMaya更新。
        remove_influence (bool): 削除の前にinfluenceを解除するか。
        transfer_to_parent (bool): 解除するウェイトを残る祖先influenceへ移すか。
        force (bool): 不正ウェイトを修復してから解除するか。

    Returns:
        None: 値を返さない。

    Raises:
        TypeError: safe・remove_influence・transfer_to_parent・forceがbool以外の場合。
        RuntimeError: 対象が無効、削除できない、またはinfluenceを解除できない場合。
    """
    ...


class Joint(Transform):
    """ジョイントを扱うクラス。回転の移し替えや、スケールの補正の操作を持つ。

    マトリクスや移動・回転・スケールの操作はTransformから受け継ぎ、
    rotateAxis・jointOrient・segmentScaleCompensateも考えて計算する。
    次の3つは、それぞれ別々の操作になっている。

    - segmentScaleCompensate(SSC)の切り替え
    - inverseScaleの接続
    - 姿勢を保ったままの回転の移し替え(jointOrientとrotateの間)
    """
    def getSegmentScaleCompensate(self) -> bool:
        """segmentScaleCompensateがオンか取得する。

        inverseScaleに親のscaleが接続されているかや、補正が思ったとおりに効くかは確かめない。

        Returns:
            bool: segmentScaleCompensateの今の値。
        """
        ...
    def setSegmentScaleCompensate(self, state: bool, *, fast: bool = ...) -> Joint:
        """segmentScaleCompensateのオン・オフを切り替える。

        segmentScaleCompensateだけを変える。inverseScaleの接続やバインドの情報は変えないので、
        親のスケールによっては、姿勢やスキンの見た目が変わる。

        Args:
            state (bool): Trueなら補正をオン、Falseならオフにする。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Joint: 自身。

        Raises:
            TypeError: stateまたはfastがbool以外の場合。
            RuntimeError: ロックされている、または入力が接続されているなどで変更できない場合。
        """
        ...
    def getJointOrient(self) -> EulerRotate:
        """jointOrientを取得する。

        XYZの回転順・ラジアンの値をEulerRotateで返す。
        ノードのrotateOrderや、UIの角度の単位は使わない。
        rotateやrotateAxis、親の回転は足し合わせない。

        Returns:
            EulerRotate: jointOrientの値の新しいオブジェクト。無効なノードではXYZとも0になる。
                ノードが有効かはisValidで確かめる。
        """
        ...
    def jointOrientToRotate(self) -> Joint:
        """jointOrientをrotateへ移して0にする。

        見た目の姿勢は変わらない。XYZの数値をそのまま足すのではなく、回転として合成する。
        rotateAxis・rotateOrder・移動・スケールは変えず、今のフレームだけを処理する。
        jointOrientがXYZとも0なら、書き込めるかの確認も書き込みもしない。
        fast引数は無い(処理のほとんどが値の確認と計算で、OpenMayaで書いても速くならないため)。

        Returns:
            Joint: 自身。

        Raises:
            RuntimeError: ジョイントが無効な場合、rotateかjointOrientがロック・入力の接続などで書き込めない場合、
                または変更に失敗した場合。

        Note:
            Undoが有効なら、1回のUndoで戻せる。途中で失敗しても、それまでに済んだ変更は自動では戻さない。
        """
        ...
    def freezeRotate(self) -> Joint:
        """rotateをjointOrientへ移して0にする。

        見た目の姿勢は変わらない。rotateAxis・rotateOrder・移動・スケールはそのまま残る。
        今のフレームだけを処理し、アニメーションはベイクしない。ウェイト・bindPreMatrix・バインドポーズは変えない。
        rotateがXYZとも0なら、書き込めるかの確認も書き込みもしない。
        fast引数は無い(:meth:`jointOrientToRotate` と同じ理由)。

        Returns:
            Joint: 自身。

        Raises:
            RuntimeError: ジョイントが無効な場合、rotateかjointOrientがロック・入力の接続などで書き込めない場合、
                または変更に失敗した場合。

        Note:
            Undoが有効なら、1回のUndoで戻せる。途中で失敗しても、それまでに済んだ変更は自動では戻さない。
        """
        ...
    def orient(self, orientation: str = ..., secondaryAxisOrient: str = ..., children: bool = ..., zeroScaleOrient: bool = ...) -> Joint:
        """ジョイントの向きを、子のジョイントの方へ向けて揃える。

        次のコマンドを実行する(``cmds.joint(edit=True, orientJoint=...)`` と同じ)。

        ``cmds.joint(edit=True, orientJoint=orientation, secondaryAxisOrient=secondaryAxisOrient,
        children=children, zeroScaleOrient=zeroScaleOrient)``

        そのうえで、処理したジョイントのうち子のジョイントを持たない末端のものは、jointOrientを0にする
        (親のジョイントと同じ向きになる。rotateは変えない)。

        - 子のジョイントの位置は変わらない。
        - 末端のジョイントの子にある、ジョイント以外のノードは、jointOrientの変更に合わせて動く。

        fast引数は無い(向きの計算はMaya標準のcmds.jointに任せるため)。Undoが有効なら、1回のUndoで戻せる。

        Args:
            orientation (str): 子のジョイントへ向ける主軸・副軸・第3軸の順。既定は ``"xyz"``。
                ``"xyz"``・``"yzx"``・``"zxy"``・``"zyx"``・``"yxz"``・``"xzy"`` のどれか。
                ``"none"`` ならjointOrientを0にする。
            secondaryAxisOrient (str): 副軸を向けるワールドの軸。既定は ``"yup"``。
                ``"xup"``・``"xdown"``・``"yup"``・``"ydown"``・``"zup"``・``"zdown"`` のどれか。
            children (bool): Trueなら子孫のジョイントも同じやり方で処理する。Falseなら自身だけ。既定はTrue。
            zeroScaleOrient (bool): TrueならscaleOrientを0にする。既定はTrue。

        Returns:
            Joint: 自身。

        Raises:
            TypeError: orientation・secondaryAxisOrientが文字列でない場合、
                またはchildren・zeroScaleOrientがboolでない場合。
            ValueError: 使えない軸名を指定した場合。
            RuntimeError: ジョイントが無効な場合、またはロック・入力の接続などでMayaが変更を拒否した場合。
        """
        ...
    def mirror(self, axis: str | int = ..., behavior: bool = ..., searchReplace: tuple[str, str] | None = ...) -> Joint:
        """ジョイントのチェーンをミラーした、新しいチェーンを作る。

        自身と子孫のジョイント(と、子のikEffectorなど)を、Maya標準の ``cmds.mirrorJoint`` で複製してミラーする。
        新しいルートは自身と同じ親の下に作られ、Mayaの決まりどおり選択される。元のチェーンは変えない。
        Transformの :meth:`~mlib.nodes.Transform.mirrorTransform` (自身の値をミラーする)とは別の操作。
        fast引数は無い(OpenMayaに同じ機能が無いため)。Undoが有効なら、1回のUndoで戻せる。

        Args:
            axis (str | int): ミラーの面か、反転する軸。既定は ``"YZ"``。

                - 面: ``"YZ"`` (X方向に左右反転)・``"XZ"``・``"XY"``
                - 軸: ``"x"``・``"y"``・``"z"`` (xはYZ、yはXZ、zはXYと同じ。文字の順や大文字・小文字は問わない)
                - 番号: 0・1・2

            behavior (bool): Trueなら ``mirrorBehavior`` でミラーする。既定はTrue。
                回転の向きが反転し、同じ回転の値で逆向きに動く(リグの左右対称でよく使う)。
                Falseなら向き(orientation)をミラーする。
            searchReplace (tuple[str, str] | None): 新しいジョイントの名前の置き換え ``(検索, 置換)``。
                例: ``("L_", "R_")``。NoneならMayaが自動で名前を付ける。

        Returns:
            Joint: 新しいチェーンのルートのジョイント。チェーン全体は ``getChildren(allDescendents=True)``
                や :meth:`getChainFromHere` で取得する。

        Raises:
            TypeError: axisが文字列・int以外の場合、behaviorがbool以外の場合、
                またはsearchReplaceが2つの文字列の組・None以外の場合。
            ValueError: axisに使えない値を指定した場合、またはsearchReplaceの検索文字列が空の場合。
            RuntimeError: ジョイントが無効な場合、またはMayaがミラーを拒否した場合。

        Note:
            Mayaの ``mirrorJoint`` は、新しいジョイントを今の名前空間へ置く。
            別の名前空間へ置くには、searchReplaceで名前空間ごと置き換える。
        """
        ...
    def connectInverseScale(self, source: object | None = ..., force: bool = ..., *, fast: bool = ...) -> Joint:
        """Transformのscaleを、自身のinverseScaleへ接続する。

        segmentScaleCompensateは変えず、姿勢が変わらないようにする補正もしない。
        接続すると、今の姿勢が変わることがある。

        Args:
            source (object | None): 接続元のノード。Transformとして扱えるものを渡す。Noneなら直接の親を使う。
                親が無ければ何も変えない。
            force (bool): Trueなら、すでにある入力を置き換え、接続先のロックを一時的に外す。既定はFalse。
                ロックを戻すやり方は :meth:`~mlib.plugs.plug.Plug.connect` と同じ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Joint: 自身。同じ接続がすでに直接あれば、何も変えない。

        Raises:
            TypeError: sourceがTransformとして扱えない場合、またはforce・fastがbool以外の場合。
            ValueError: 自身を接続元にした場合、または入力の指定が不正な場合。
            RuntimeError: 対象が無効な場合、または名前の解決・接続・ロックの戻しに失敗した場合。

        Note:
            Jointsから呼んでも、source=Noneならそれぞれのジョイントの親を使う。
            Undoが有効なら、1回のUndoで戻せる。
        """
        ...
    def disconnectInverseScale(self, *, fast: bool = ...) -> Joint:
        """inverseScaleへの入力の接続を外す。

        inverseScale、inverseScaleX・Y・Zの順に、直接の入力の接続を外す。接続が無いところは何もしない。
        出力の接続・segmentScaleCompensate・値を戻すこと・姿勢の補正は扱わない。
        外した後の値は、Mayaの動きに従う。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Joint: 自身。Jointsからもまとめて実行できる。

        Raises:
            TypeError: fastがbool以外の場合。
            RuntimeError: 対象が無効な場合、ロックされている場合、またはMayaが接続を外せなかった場合。

        Note:
            Undoが有効なら、1つのUndoチャンクに記録する。途中で失敗しても、先に外した接続は自動では戻さない。
        """
        ...
    def getRadius(self) -> float:
        """ジョイントごとの表示の半径を取得する。

        Returns:
            float: radiusアトリビュートの値。Maya全体のjointDisplayScaleとは別の値。
        """
        ...
    def setRadius(self, value: float, *, fast: bool = ...) -> Joint:
        """ジョイントごとの表示の半径を設定する。

        骨の長さやscaleは変えない。

        Args:
            value (float): 0以上の有限な数値。実際の表示の大きさは、Maya全体の表示倍率でも変わる。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Joint: 自身。Jointsから呼ぶと、どのジョイントにも同じ値を設定する。

        Raises:
            TypeError: valueが数値でない場合、またはfastがbool以外の場合。
            ValueError: valueが負の数、または有限でない場合。
            RuntimeError: Mayaが変更を拒否した場合。
        """
        ...
    def getPreferredAngle(self, *, unit: str = ...) -> list[float]:
        """preferredAngleを取得する。

        preferredAngleは、IKがジョイントを曲げる向きの基準になる角度。

        Args:
            unit (str): 戻り値の角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。

        Returns:
            list[float]: XYZの角度。

        Raises:
            TypeError: unitが文字列・None以外の場合。
            ValueError: unitに使えない単位名を指定した場合。
            RuntimeError: ジョイントが無効な場合。
        """
        ...
    def setPreferredAngle(self, value: Sequence[float] | None = ..., *, unit: str = ...) -> Joint:
        """preferredAngleを設定する。

        preferredAngleは、IKがジョイントを曲げる向きの基準になる角度。
        valueを省略すると、今のrotateをpreferredAngleにする。これはSkeleton > Set Preferred Angleや
        ``cmds.joint(edit=True, setPreferredAngles=True)`` と同じ。子孫のジョイントには反映しない。

        Args:
            value (Sequence[float] | None): XYZの角度。Noneなら今のrotateを使う。
            unit (str): valueの角度の単位。``"deg"`` は度、``"rad"`` はラジアン。既定は ``"deg"``。

        Returns:
            Joint: 自身。

        Raises:
            TypeError: valueが3つの数値の並び・None以外の場合、またはunitが文字列・None以外の場合。
            ValueError: valueの要素が3つでない場合、有限でない値がある場合、またはunitに使えない単位名を指定した場合。
            RuntimeError: ジョイントが無効な場合、またはpreferredAngleがロック・入力の接続で書き込めない場合。
        """
        ...
    def assumePreferredAngles(self, children: bool = ...) -> Joint:
        """rotateをpreferredAngleの値へ戻す。

        Skeleton > Assume Preferred Angleや ``cmds.joint(edit=True, assumePreferredAngles=True)`` と同じ。

        Args:
            children (bool): Trueなら子孫のジョイントにも行う。Falseなら自身だけ。既定はTrue。

        Returns:
            Joint: 自身。

        Raises:
            TypeError: childrenがbool以外の場合。
            RuntimeError: ジョイントが無効な場合、またはMayaが書き込みを拒否した場合。

        Note:
            Undoが有効なら、1回のUndoで戻せる。rotateがロックされている、または入力が接続されている
            ジョイントをどう扱うかはMayaに従う。
        """
        ...
    def getDegreesOfFreedom(self) -> str:
        """回転できる軸を取得する。

        jointTypeX・Y・Zがオンになっている軸を返す。

        Returns:
            str: 回転できる軸の名前をXYZの順につなげた文字列(``"xyz"``・``"xz"`` など)。
                すべての軸が固定なら空文字列。

        Raises:
            RuntimeError: ジョイントが無効な場合。
        """
        ...
    def setDegreesOfFreedom(self, axes: str) -> Joint:
        """回転できる軸を設定する。

        jointTypeX・Y・Zを書き換える。指定しなかった軸は固定する。

        Args:
            axes (str): ``"xyz"``・``"xz"`` などの軸名の並び。順番や大文字・小文字は問わない。
                空文字列ならすべての軸を固定する。

        Returns:
            Joint: 自身。

        Raises:
            TypeError: axesが文字列でない場合。
            ValueError: x・y・z以外の文字を含む場合、または同じ軸を2回以上含む場合。
            RuntimeError: ジョイントが無効な場合、またはjointTypeがロック・入力の接続で書き込めない場合。

        Note:
            Undoが有効なら、1回のUndoで戻せる。fast引数は無い。
        """
        ...
    def getInverseScale(self) -> Scale:
        """inverseScaleの値を取得する。

        アトリビュートの値のXYZをそのまま返す。逆数にはせず、segmentScaleCompensateのオン・オフでも値は変えない。

        Returns:
            Scale: inverseScaleの値の新しいオブジェクト。無効なノードではXYZとも0になる。
                補正が実際に効いているかや、ノードが有効かを判断するための値ではない。
        """
        ...
    def getDepth(self) -> int:
        """ジョイントの階層の中での深さを取得する。

        Returns:
            int: 階層の深さ。ルートのジョイントを0として数える。
        """
        ...
    def getSkinClusters(self) -> list[SkinCluster]:
        """このジョイントに接続しているskinClusterを取得する。

        Returns:
            list[SkinCluster]: skinClusterのオブジェクト。同じものは1回だけ含む。
        """
        ...
    def removeInfluence(self, skinCluster: SkinCluster | str | None = ..., *, transferToParent: bool = ..., force: bool = ...) -> Joint:
        """skinClusterのインフルエンスから自身を外す。

        ジョイントのノードは残す。外す前に、すべての対象でインフルエンスになっているかと、
        ウェイトを移せるかを確かめる。そのあと、取得した順に、SkinCluster.removeInfluenceと同じ処理で外す。

        - ウェイトのロックは一時的に外し、終わったら元に戻す。
        - ngSkinTools2のレイヤーは、レイヤーごとにウェイトを移す。

        Undoが有効なら、1つのUndoチャンクに記録する。fast引数は無い。
        途中で失敗しても、それまでに済んだ処理は戻さない。

        Args:
            skinCluster (SkinCluster | str | None): 対象のskinCluster。Noneなら接続しているすべてのskinCluster。
            transferToParent (bool): Trueなら、ウェイトをいちばん近い祖先のインフルエンスへ足す。既定はTrue。
                Falseの場合や、移す先が無い場合は、Maya標準の配り直しに任せる。
            force (bool): Trueなら、不正なウェイトを直してから外す。直すときに正規化はしない。既定はFalse。

        Returns:
            Joint: 自身。skinClusterを省略し、どこにもバインドされていなければ何も変えない。

        Raises:
            TypeError: transferToParent・forceがbool以外の場合。
            ValueError: インフルエンスになっていない場合、または最後のインフルエンスを外そうとした場合。
            RuntimeError: ジョイントが無効な場合、ウェイトの要素がロック・入力の接続で書き込めない場合、
                または変更に失敗した場合。
        """
        ...
    def delete(self, *, safe: bool = ..., fast: bool = ..., removeInfluence: bool = ..., transferToParent: bool = ..., force: bool = ...) -> None:
        """インフルエンスから外してから、自身と子孫を削除する。

        Maya標準の削除では、消えたジョイントの列にウェイトが残ってしまう。
        このメソッドは、自身とDAGの子孫のジョイントを、:meth:`removeInfluence` と同じ処理で各skinClusterから外す。
        ウェイトは、残るジョイントのうちいちばん近い祖先のインフルエンスへ移してから削除する。

        - 残る祖先が無ければ、Maya標準の配り直しに任せる。
        - すべてのインフルエンスが消えるskinClusterは外さず、Maya標準の削除に任せる。
        - ウェイトのロックは一時的に外し、終わったら元に戻す。
        - ngSkinTools2のレイヤーは、レイヤーごとにウェイトを移す。ngSkinTools2を使えない場合も
          エラーにはせず、skinClusterのウェイトだけを書き換える。

        変える前にすべての対象を確かめる。Undoが有効なら、1回のUndoで戻せる。
        ``mlib.delete`` はインフルエンスから外す処理をせず、Maya標準の削除のままになる。

        Args:
            safe (bool): Trueなら、自身かDAGの子孫にDGの接続(skinClusterとの接続も含む)がある場合は何もしない。
                既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。ウェイトの書き込みと削除はOpenMayaで行う。
                OpenMayaに無い、インフルエンスから外す処理だけは、Undoに記録しないcmdsで行う。結果は通常と同じ。
            removeInfluence (bool): Falseなら、インフルエンスから外さず、Maya標準の削除だけを行う。既定はTrue。
            transferToParent (bool): Falseなら、ウェイトを祖先へ移さず、Maya標準の配り直しに任せる。既定はTrue。
            force (bool): Trueなら、不正なウェイトを直してから外す。直すときに正規化はしない。既定はFalse。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: safe・fast・removeInfluence・transferToParent・forceがbool以外の場合。
            ValueError: 移すウェイトに負の値か有限でない値がある場合。このときは何も変えない。
            RuntimeError: 対象が無効な場合、ロックされたノードやリファレンスのノードを含む場合(このときは何も変えない)、
                ウェイトの要素がロック・入力の接続で書き込めない場合、またはMayaが変更を拒否した場合。
        """
        ...
    def isInfluenceLocked(self) -> bool:
        """スキンのウェイトがロックされているか調べる。

        lockInfluenceWeightsアトリビュートの値を見る。このアトリビュートは、skinClusterへバインドしたときに追加される。

        Returns:
            bool: ロックされていればTrue。アトリビュートが無い(どのskinClusterのインフルエンスでもない)場合はFalse。
        """
        ...
    def setInfluenceLocked(self, state: bool = ...) -> Joint:
        """スキンのウェイトをロックする、またはロックを外す。

        lockInfluenceWeightsアトリビュートを書き換える。これはジョイント側のアトリビュートなので、
        どのskinClusterでも同じ値になる。
        いくつものジョイントをまとめて設定するなら、:meth:`SkinCluster.setInfluencesLocked
        <mlib.nodes.skinCluster.SkinCluster.setInfluencesLocked>` を使う。fast引数は無い。

        Args:
            state (bool): Trueならロックし、Falseならロックを外す。既定はTrue。

        Returns:
            Joint: 自身。

        Raises:
            TypeError: stateがbool以外の場合。
            RuntimeError: lockInfluenceWeightsが無い(インフルエンスになっていない)場合、
                またはそのアトリビュートがロックされているか入力が接続されている場合。
        """
        ...
    def getBoneSegments(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[tuple[Vector, Vector]]:
        """自身から子のジョイントまでの、ボーンの線分を取得する。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間(親の空間)で取得する。既定はTrue。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[tuple[Vector, Vector]]: 子のジョイントごとの (始点, 終点)。始点は自身の位置(回転ピボット)。
                子のジョイントが無い場合は、始点と同じ点を終点にした1組だけを返す。位置はcm。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
        """
        ...
    def getTransferTarget(self, skin: SkinCluster) -> str | None:
        """ウェイトを移す先になる、いちばん近い祖先のインフルエンスを探す。

        Args:
            skin (SkinCluster): インフルエンスになっているかを調べるskinCluster。

        Returns:
            str | None: 移す先の祖先のジョイントの名前。見つからない場合は ``None``。
        """
        ...
    def reparentChildren(self, parentJoint: str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug) -> Joint:
        """子のジョイントを、指定したジョイントの子へ付け替える。

        fast引数は無い(ワールドの位置を保ったままの付け替えは、cmds.parentのほうが速いため)。

        Args:
            parentJoint (str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug):
                直接の子のジョイントを付け替える先の親ノード。``Node._input_name`` と同じやり方でノードを決める
                (Plug・MPlugなら、それを持つノード)。

        Returns:
            Joint: 自身。

        Raises:
            TypeError: parentJointが使えない型の場合。
            ValueError: parentJointが空文字列の場合、または無効な対象の場合。
            RuntimeError: parentJointのノードが見つからない場合、またはMayaが親の変更を拒否した場合。
        """
        ...
    def getChainFromHere(self, to: Joint | str | None = ...) -> list[Joint]:
        """自身から始まるジョイントのチェーンを、順に取得する。

        Args:
            to (Joint | str | None): チェーンの終わりのジョイント。指定すると、自身からそのジョイントまでの道筋をたどる
                (自身の子孫でなければならない)。
                省略すると、子のジョイントがちょうど1つのあいだだけたどり、
                枝分かれ(子が0個か2つ以上)に着いたところで止める。

        Returns:
            list[Joint]: 自身からtoまで、または最初の枝分かれまでのジョイント。自身を含む。

        Raises:
            ValueError: toが自身の子孫でない場合。
            RuntimeError: 自身が無効な場合。
        """
        ...
    def insertJoints(self, count: int) -> list[Joint]:
        """自身とただ1つの子ジョイントの間に、ジョイントを等間隔に挿入する。

        - 新しいジョイントは、自身から子へ向かう順に親子につなぐ。
        - 元の子ジョイントは、最後の新しいジョイントの子へ付け替える(子のワールドの位置と向きは変わらない)。
        - 新しいジョイントのワールドの向きは、自身と同じにする。jointOrientとrotateは0にし、
          rotateOrder・radius・segmentScaleCompensateは自身の値を写す。
        - inverseScaleは、親のジョイントのscaleへ接続する。
        - 名前は ``<自身の名前>_insert#`` になる(``#`` はMayaの連番)。

        fast引数は無い。Undoが有効なら、1回のUndoで戻せる。

        Args:
            count (int): 挿入する数。1以上。

        Returns:
            list[Joint]: 挿入したジョイント。自身に近い順に並ぶ。

        Raises:
            TypeError: countがintでない場合。
            ValueError: countが1未満の場合、または子ジョイントが無いか2つ以上ある場合。
            RuntimeError: 自身が無効な場合、またはMayaが作成や親の変更を拒否した場合。
        """
        ...
    def getPolePosition(self, distance: float | None = ...) -> Vector:
        """ポールベクターのコントローラーを置く位置を求める。

        自身・子・孫のジョイントの3点を通る平面の上で、チェーンが曲がる側へ離した位置を返す。
        自身から孫への線分へ、子の位置から垂線を下ろす。その垂線の向き(曲がる側)へ、子の位置からdistanceだけ離した点になる。
        IKのpoleVectorのコントローラーを置く位置に使う。シーンは変えない。

        Args:
            distance (float | None): 子の位置から離す距離(cm)。正の有限な数。
                Noneならチェーンの長さ(自身から子までと、子から孫までの長さの和)を使う。

        Returns:
            Vector: ワールド空間の位置(cm)。

        Raises:
            TypeError: distanceが数値・None以外の場合。
            ValueError: distanceが正の有限な数でない場合、子・孫のジョイントがちょうど1つずつでない場合、
                または3点がほぼ一直線に並んでいて曲がる向きが決まらない場合。
            RuntimeError: 自身が無効な場合。
        """
        ...
    def getIkHandles(self) -> list[IkHandle]:
        """自身を開始ジョイントにしているIKハンドルを取得する。

        自身がIKチェーンの途中や末端のジョイントの場合は見つからない。
        ジョイントからIKハンドルをたどれるのは、IKハンドルの ``startJoint`` への接続だけのため。

        Returns:
            list[IkHandle]: 自身を開始ジョイントにしているIkHandle。無ければ空リスト。
        """
        ...
    def _orient(self, flags: dict) -> None:
        """検証済みのフラグで向きを揃え、末端jointのjointOrientを0にする。

        Args:
            flags (dict): :func:`_orient_flags` が返したcmds.jointのフラグ。

        Returns:
            None: 値を返さない。
        """
        ...
    def _joint_rotate_order(self) -> int:
        """Maya の rotateOrder を API の回転順序へ変換する。

        rotateOrder の番号(0=xyz〜5=zyx)は MEulerRotation.kXYZ〜kZYX と同じ並び。

        Returns:
            int: rotateOrder に対応する Maya API 2.0 の MEulerRotation 定数。
        """
        ...
    def _joint_rotate_transfer_values(self, to_orient: bool = ...) -> tuple[float, float, float] | None:
        """書込み可否を検証し、合成後の回転を現在の角度単位で返す。

        Args:
            to_orient (bool): TrueでjointOrient用XYZ、FalseでrotateOrderのrotate用。

        Returns:
            tuple[float, float, float] | None: 合成値。移送元が0ならNone。

        Raises:
            RuntimeError: 無効joint、ロック、入力接続、書込み不可の場合。
        """
        ...
    def _apply_rotate_transfer(self, values: tuple | None, to_orient: bool = ...) -> None:
        """検証済みの回転移送値をcmdsで適用する。

        Args:
            values (tuple | None): 現在のUI角度単位の3成分。Noneなら更新しない。
            to_orient (bool): TrueならjointOrientへ移しrotateを0にする。

        Returns:
            None: 値を返さない。
        """
        ...
    def _rotate_quaternion(self, attribute: str) -> om2.MQuaternion:
        """jointOrient / rotateAxis を API quaternion へ変換する。

        MAngle から明示的に度数法で取得し、ラジアンへ変換する。現在の UI 角度単位に依存しない。
        Maya の jointOrient と
        rotateAxis は rotateOrder にかかわらず常に XYZ 順序で評価されるため、
        XYZ として解釈する。

        Args:
            attribute (str): 度の3成分として読み取る回転アトリビュート名(jointOrient / rotateAxis)。

        Returns:
            om2.MQuaternion: XYZ 順序で解釈した回転。
        """
        ...
    def _remove_segment_scale_compensation(self, matrix: Matrix) -> Matrix:
        """ssc と inverseScale が適用された後のマトリクスから補正前の値を戻す。

        Maya の joint のマトリクスは S · RA · R · JO · IS · T(IS は inverseScale の逆数の
        対角マトリクス)なので、3x3 部分へ inverseScale の対角マトリクスを右から掛けて IS を打ち消す。
        平行移動は IS の後に適用されるため変えない。

        Args:
            matrix (Matrix): スケール補正を取り除く対象マトリクス。

        Returns:
            Matrix: ssc が無効なら入力そのもの。有効なら IS を打ち消した新しいマトリクス。

        Raises:
            ValueError: ssc が有効で inverseScale の成分の絶対値が 1e-12 未満の場合。
        """
        ...
    def _rotate_reference(self, reference: om2.MEulerRotation) -> om2.MEulerRotation:
        """:meth:`getRotate` が Euler の解を選ぶ基準を返す。

        joint の getRotate は jointOrient と rotateAxis を含む回転で rotate チャンネルとは
        別の回転なので、チャンネル値ではなく 0 回転(ノードの rotateOrder)を基準にする。

        Args:
            reference (om2.MEulerRotation): 現在の rotate チャンネル値(順序だけを使う)。

        Returns:
            om2.MEulerRotation: 0 回転。順序はノードの rotateOrder。
        """
        ...
    def _channel_rotate(self, quaternion: om2.MQuaternion, reference: om2.MEulerRotation) -> om2.MEulerRotation:
        """ローカルマトリクスの回転から jointOrient と rotateAxis を除き、rotate の値へ変換する。

        Maya の joint の回転は rotateAxis、rotate、jointOrient の順に適用されるため、
        rotate = rotateAxis⁻¹ · マトリクスの回転 · jointOrient⁻¹(om2 のクォータニオンの積の順序)。

        Args:
            quaternion (om2.MQuaternion): ローカルマトリクスの回転。
            reference (om2.MEulerRotation): 現在の rotate チャンネル値。

        Returns:
            om2.MEulerRotation: ノードの rotateOrder で表した、reference に最も近い解。
        """
        ...
    def _apply_local_matrix(self, matrix: Matrix, scale_reference: Iterable[float] | None = ..., *, fast: bool = ...) -> None:
        """jointOrient と rotateAxis を保持して local マトリクスを適用する。

        Transformの共通処理へ委譲し、Jointの回転分離とSSC補償を反映した
        translate・rotate・scale・shearの設定値のうち、現在値と完全に一致しないものだけを書き込む。
        計算値は距離cm・角度radで、UI角度単位が度であることは前提にしない。

        Args:
            matrix (Matrix): 適用するローカルマトリクス。
            scale_reference (Iterable[float] | None): 最優先で符号を合わせるスケール
                (``setScale`` で要求した値)。None なら現在の scale チャンネル値に合わせる。
            fast (bool): Trueなら各チャンネルをOpenMayaで更新する。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: inverseScale がゼロに近い、またはマトリクスを分解できない場合。
            RuntimeError: Maya がアトリビュートの書き込みを拒否した場合。
        """
        ...
    def _compound_values(self, attribute: str, angle: bool = ...) -> tuple[float, float, float]:
        """コンパウンドアトリビュートを 3 要素の tuple として取得する。

        Args:
            attribute (str): 読み取るコンパウンドアトリビュート名。
            angle (bool): True の場合、各子を角度アトリビュートとして度数法の値で取得する。
                現在の UI 角度単位に関係なく、MAngle.asDegrees() を使用する。
                False の場合は単位変換のない生の double として取得する。

        Returns:
            tuple[float, float, float]: 最初の子 3 要素の値。無効なノードでは (0.0, 0.0, 0.0)。
                有効時は子の数を事前検査せず、3 要素を読み取る。
        """
        ...


class Joints(Nodes[Joint]):
    """Jointのオブジェクトをまとめて持つコレクション。型や重なりの扱いはNodesと同じ。"""
    def __iter__(self) -> Iterator[Joint]: ...
    @overload
    def __getitem__(self, index: int) -> Joint: ...
    @overload
    def __getitem__(self, index: slice) -> Joints: ...
    item_class: Any
    _items: List[Joint]
    def sortedByDepth(self) -> Joints:
        """深いジョイントから順に並べた、新しいコレクションを返す。

        Returns:
            Joints: 深さの順に並べたコレクション。子のジョイントを先に処理したいときに使う。
        """
        ...
    def orient(self, orientation: str = ..., secondaryAxisOrient: str = ..., children: bool = ..., zeroScaleOrient: bool = ...) -> Joints:
        """各ジョイントに、並んでいる順に :meth:`Joint.orient` を行う。

        全体を1つのUndoチャンクに記録する。引数は、処理を始める前に1回だけ確かめる。

        Args:
            orientation (str): :meth:`Joint.orient` と同じ。
            secondaryAxisOrient (str): :meth:`Joint.orient` と同じ。
            children (bool): :meth:`Joint.orient` と同じ。
            zeroScaleOrient (bool): :meth:`Joint.orient` と同じ。

        Returns:
            Joints: 自身。

        Raises:
            TypeError: :meth:`Joint.orient` と同じ。
            ValueError: :meth:`Joint.orient` と同じ。
            RuntimeError: 無効なジョイントを含む場合、またはMayaが変更を拒否した場合。
                先に済んだジョイントの変更は、自動では戻さない。
        """
        ...
    def removeInfluence(self, skinCluster: SkinCluster | str | None = ..., *, transferToParent: bool = ..., force: bool = ...) -> Joints:
        """すべてのジョイントをインフルエンスから外す。

        ジョイントのノードは残す。:meth:`Joint.removeInfluence` と同じやり方で、深いジョイントから順に外す。
        親子を一緒に外すと、ウェイトは外さずに残る、いちばん近い祖先のインフルエンスへ集まる。
        ウェイトは最後の移し先へ1回で書き込み、インフルエンスからもまとめて外す。

        - ウェイトのロックは一時的に外し、終わったら元に戻す。
        - ngSkinTools2のレイヤーは、レイヤーごとにウェイトを移す。

        変える前にすべての対象を確かめる。Undoが有効なら、1回のUndoで戻せる。

        Args:
            skinCluster (SkinCluster | str | None): 対象のskinCluster。Noneなら、各ジョイントがインフルエンスになっているすべてのskinCluster。
            transferToParent (bool): :meth:`Joint.removeInfluence` と同じ。
            force (bool): :meth:`Joint.removeInfluence` と同じ。

        Returns:
            Joints: 自身。skinClusterを省略した場合、どこにもバインドされていないジョイントは変えない。

        Raises:
            TypeError: transferToParent・forceがbool以外の場合。
            ValueError: インフルエンスになっていないジョイントを含む場合、
                またはskinClusterのすべてのインフルエンスを外そうとした場合。このときは何も変えない。
            RuntimeError: 無効なジョイントを含む場合、ウェイトの要素がロック・入力の接続で書き込めない場合、
                またはMayaでの変更が失敗した場合。
        """
        ...
    def delete(self, *, safe: bool = ..., fast: bool = ..., removeInfluence: bool = ..., transferToParent: bool = ..., force: bool = ...) -> None:
        """すべてのジョイントをインフルエンスから外してから、ジョイントと子孫をまとめて削除する。

        外し方は :meth:`Joint.delete` と同じ。一緒に消える親子はまとめて外すので、
        ウェイトは残る中でいちばん近い祖先のインフルエンスへ集まる。
        変える前にすべての対象を確かめる。Undoが有効なら、1回のUndoで戻せる。
        インフルエンスから外す必要がなく、ノードの種類を問わずまとめて削除したいときは ``mlib.delete`` を使う。

        Args:
            safe (bool): Trueなら、自身かDAGの子孫にDGの接続があるジョイントだけを除いて削除する。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。詳細は :meth:`Joint.delete` と同じ。
            removeInfluence (bool): :meth:`Joint.delete` と同じ。
            transferToParent (bool): :meth:`Joint.delete` と同じ。
            force (bool): :meth:`Joint.delete` と同じ。

        Returns:
            None: 値を返さない。コレクションが空なら何もしない。

        Raises:
            TypeError: :meth:`Joint.delete` と同じ。
            ValueError: :meth:`Joint.delete` と同じ。
            RuntimeError: :meth:`Joint.delete` と同じ。
        """
        ...
    def setRadius(self, value: float, *, fast: bool = ...) -> Joints:
        """各ジョイントに、並んでいる順に :meth:`Joint.setRadius` を行う。

        Args:
            value (float): :meth:`Joint.setRadius` と同じ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Joints: 自身。通常は1回のUndoにまとめる。

        Raises:
            TypeError: :meth:`Joint.setRadius` と同じ。
            ValueError: :meth:`Joint.setRadius` と同じ。
            RuntimeError: 無効なジョイントを含む場合、またはMayaが変更を拒否した場合。
        """
        ...
    def setSegmentScaleCompensate(self, state: bool, *, fast: bool = ...) -> Joints:
        """各ジョイントに、並んでいる順に :meth:`Joint.setSegmentScaleCompensate` を行う。

        Args:
            state (bool): :meth:`Joint.setSegmentScaleCompensate` と同じ。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            Joints: 自身。通常は1回のUndoにまとめる。

        Raises:
            TypeError: :meth:`Joint.setSegmentScaleCompensate` と同じ。
            RuntimeError: 無効なジョイントを含む場合、またはMayaが変更を拒否した場合。
        """
        ...
    def getSkinClusters(self) -> SkinClusters:
        """すべてのジョイントに接続しているskinClusterを取得する。

        Returns:
            SkinClusters: skinClusterのコレクション。同じものは1回だけ含む。
        """
        ...
    def getSegmentScaleCompensate(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getSegmentScaleCompensate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getJointOrient(self) -> list[EulerRotate]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getJointOrient` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def jointOrientToRotate(self) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.jointOrientToRotate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def freezeRotate(self) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.freezeRotate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mirror(self, axis: str | int = ..., behavior: bool = ..., searchReplace: tuple[str, str] | None = ...) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.mirror` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def connectInverseScale(self, source: object | None = ..., force: bool = ..., *, fast: bool = ...) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.connectInverseScale` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def disconnectInverseScale(self, *, fast: bool = ...) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.disconnectInverseScale` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getRadius(self) -> list[float]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getRadius` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPreferredAngle(self, *, unit: str = ...) -> list[list[float]]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getPreferredAngle` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setPreferredAngle(self, value: Sequence[float] | None = ..., *, unit: str = ...) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.setPreferredAngle` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def assumePreferredAngles(self, children: bool = ...) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.assumePreferredAngles` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDegreesOfFreedom(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getDegreesOfFreedom` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setDegreesOfFreedom(self, axes: str) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.setDegreesOfFreedom` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getInverseScale(self) -> list[Scale]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getInverseScale` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDepth(self) -> list[int]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getDepth` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isInfluenceLocked(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.isInfluenceLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setInfluenceLocked(self, state: bool = ...) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.setInfluenceLocked` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBoneSegments(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[list[tuple[Vector, Vector]]]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getBoneSegments` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTransferTarget(self, skin: SkinCluster) -> list[str | None]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getTransferTarget` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def reparentChildren(self, parentJoint: str | Node | Plug | Component | om2.MObject | om2.MDagPath | om2.MPlug) -> list[Joint]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.reparentChildren` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getChainFromHere(self, to: Joint | str | None = ...) -> list[list[Joint]]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getChainFromHere` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def insertJoints(self, count: int) -> list[list[Joint]]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.insertJoints` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPolePosition(self, distance: float | None = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getPolePosition` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getIkHandles(self) -> list[list[IkHandle]]:
        """各要素の :meth:`~mlib.nodes.joint.Joint.getIkHandles` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def addConstraint(self, sources: Node | str | Plug | Component | Components | om2.MObject | om2.MDagPath | om2.MPlug | Iterable, type: str = ..., maintainOffset: bool = ..., *, typ: str = ..., mo: bool = ..., createCache: Sequence[float] = ..., cc: Sequence[float] = ..., decompRotationToChild: bool = ..., dr: bool = ..., deleteCache: bool = ..., dc: bool = ..., edit: bool = ..., e: bool = ..., layer: str = ..., l: str = ..., name: str = ..., n: str = ..., query: bool = ..., q: bool = ..., remove: bool = ..., rm: bool = ..., skipRotate: str | Sequence[str] = ..., sr: str | Sequence[str] = ..., skipTranslate: str | Sequence[str] = ..., st: str | Sequence[str] = ..., targetList: bool = ..., tl: bool = ..., weight: float = ..., w: float = ..., weightAliasList: bool = ..., wal: bool = ..., offset: Sequence[float] = ..., o: Sequence[float] = ..., skip: str | Sequence[str] = ..., sk: str | Sequence[str] = ..., scaleCompensate: bool = ..., sc: bool = ..., aimVector: Sequence[float] = ..., aim: Sequence[float] = ..., upVector: Sequence[float] = ..., u: Sequence[float] = ..., worldUpObject: Node | Plug | Component | str | om2.MObject | om2.MDagPath | om2.MPlug = ..., wuo: Node | Plug | Component | str | om2.MObject | om2.MDagPath | om2.MPlug = ..., worldUpType: str = ..., wut: str = ..., worldUpVector: Sequence[float] = ..., wu: Sequence[float] = ..., **kwargs) -> list[Constraint]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.addConstraint` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def deleteConstraints(self, *, fast: bool = ...) -> list[list[str]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.deleteConstraints` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mfn(self) -> list[om2.MFnTransform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.mfn` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def scaleGeometry(self, scale: float | Iterable[float], worldSpace: bool = ..., pivot: Iterable[float] = ..., indices: Iterable[int | tuple[int, int]] | None = ..., *, fast: bool = ..., ws: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.scaleGeometry` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mirrorGeometry(self, axis: str | int = ..., worldSpace: bool = ..., pivot: Iterable[float] = ..., indices: Iterable[int] | None = ..., *, fast: bool = ..., ws: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.mirrorGeometry` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPivot(self, worldSpace: bool = ..., *, kind: str = ..., ws: bool = ...) -> list[Translate]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getPivot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setPivot(self, value: Iterable[float], worldSpace: bool = ..., *, kind: str = ..., preserve: bool = ..., fast: bool = ..., ws: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setPivot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def centerPivot(self, *, fast: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.centerPivot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def zeroTransformPivots(self) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.zeroTransformPivots` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def ungroup(self, *, world: bool = ...) -> list[list[Transform]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.ungroup` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getChildren(self, shapes: bool = ..., intermediates: bool = ..., *, allDescendents: bool = ..., order: str = ..., leaves: bool = ..., includeSelf: bool = ..., underWorld: bool = ..., type: str | Iterable[str] | None = ...) -> list[list[DagNode]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getChildren` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUnusedIntermediateShapes(self) -> list[list[Shape]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getUnusedIntermediateShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def deleteUnusedIntermediateShapes(self, *, fast: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.deleteUnusedIntermediateShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def addShape(self, shape: Shape | str, *, fast: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.addShape` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getShapes(self, intermediates: bool = ...) -> list[list[Shape]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def replaceShapes(self, source: Transform | Shape | str, *, keepSource: bool = ..., worldSpace: bool = ..., ws: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.replaceShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getCurveShapesData(self) -> list[dict]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getCurveShapesData` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setCurveShapesData(self, data: dict) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setCurveShapesData` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def exportCurveShapes(self, path: str | os.PathLike) -> list[pathlib.Path]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.exportCurveShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def importCurveShapes(self, path: str | os.PathLike) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.importCurveShapes` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getShape(self, index: int = ..., intermediates: bool = ...) -> list[Shape | None]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getShape` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTransform(self) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getTransform` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def matchTransform(self, target: Transform | str | om2.MObject | om2.MDagPath, position: bool = ..., rotation: bool = ..., scale: bool = ..., pivots: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.matchTransform` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mirrorTransform(self, axis: str | int = ..., worldSpace: bool = ..., pivot: Iterable[float] = ..., *, fast: bool = ..., ws: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.mirrorTransform` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getShadingEngines(self) -> list[list[ShadingEngine]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getShadingEngines` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getMatrix(self, worldSpace: bool = ..., p: bool = ..., inv: bool = ..., *, parent: bool = ..., inverse: bool = ..., ws: bool = ...) -> list[Matrix]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getMatrix` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setMatrix(self, matrix: Matrix | Iterable[float], worldSpace: bool = ..., safe: bool = ..., get: bool = ..., *, fast: bool = ..., ws: bool = ...) -> list[Transform | dict[str, Translate | EulerRotate | Scale | Shear]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setMatrix` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTranslation(self, worldSpace: bool = ..., at: int = ..., *, ws: bool = ...) -> list[Translate]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getTranslation` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setTranslation(self, value: Iterable[float], worldSpace: bool = ..., at: int = ..., safe: bool = ..., get: bool = ..., *, fast: bool = ..., ws: bool = ...) -> list[Transform | list[float]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setTranslation` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def translateBy(self, value: Iterable[float], worldSpace: bool = ..., *, ws: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.translateBy` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getRotate(self, worldSpace: bool = ..., *, order: int | str | None = ..., ws: bool = ...) -> list[EulerRotate]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getRotate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setRotate(self, value: Iterable[float] | EulerRotate | Quaternion, worldSpace: bool = ..., safe: bool = ..., get: bool = ..., *, unit: str = ..., fast: bool = ..., ws: bool = ...) -> list[Transform | list[float]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setRotate` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def rotateBy(self, value: Iterable[float] | EulerRotate | Quaternion, worldSpace: bool = ..., *, unit: str = ..., ws: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.rotateBy` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getRotateOrder(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getRotateOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setRotateOrder(self, order: str | int, preserve: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setRotateOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getScale(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Scale]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getScale` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setScale(self, value: Iterable[float], worldSpace: bool = ..., safe: bool = ..., get: bool = ..., *, fast: bool = ..., ws: bool = ...) -> list[Transform | list[float]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setScale` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def scaleBy(self, value: float | Iterable[float]) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.scaleBy` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getShear(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Shear]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getShear` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setShear(self, value: Iterable[float], worldSpace: bool = ..., safe: bool = ..., get: bool = ..., *, fast: bool = ..., ws: bool = ...) -> list[Transform | list[float]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setShear` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getQuaternion(self, worldSpace: bool = ..., ra: bool = ..., r: bool = ..., jo: bool = ..., *, rotateAxis: bool = ..., rotate: bool = ..., jointOrient: bool = ..., ws: bool = ...) -> list[Quaternion]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getQuaternion` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setQuaternion(self, value: Quaternion | om2.MQuaternion | Iterable[float], worldSpace: bool = ..., ra: bool = ..., r: bool = ..., jo: bool = ..., safe: bool = ..., get: bool = ..., *, unit: str = ..., fast: bool = ..., rotateAxis: bool = ..., rotate: bool = ..., jointOrient: bool = ..., ws: bool = ...) -> list[Transform | list[float]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setQuaternion` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def makeIdentity(self, *, apply: bool = ..., a: bool = ..., jointOrient: bool = ..., jo: bool = ..., normal: int = ..., n: int = ..., preserveNormals: bool = ..., pn: bool = ..., rotate: bool = ..., r: bool = ..., scale: bool = ..., s: bool = ..., translate: bool = ..., t: bool = ..., query: bool = ..., q: bool = ..., edit: bool = ..., e: bool = ..., **kwargs: object) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.makeIdentity` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getOffsetParentMatrix(self) -> list[Matrix]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getOffsetParentMatrix` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setOffsetParentMatrix(self, matrix: Matrix | om2.MMatrix | Sequence[float], *, fast: bool = ...) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setOffsetParentMatrix` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def freezeToOffsetParent(self) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.freezeToOffsetParent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def eulerFilter(self) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.eulerFilter` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getClosestAxisToVector(self, refVector: Vector | Iterable[float], includeNegative: bool = ...) -> list[str]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getClosestAxisToVector` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getLimits(self, *, unit: str = ...) -> list[dict[str, tuple[float | None, float | None]]]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.getLimits` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setLimits(self, *, unit: str = ..., **limits: tuple[float | None, float | None] | None) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.transform.Transform.setLimits` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBindPoses(self) -> list[list[DagPose]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getBindPoses` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def mpath(self) -> list[om2.MDagPath]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.mpath` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getRoot(self) -> list[Transform]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getRoot` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getCommonAncestor(self, other: DagNode | str | om2.MObject | om2.MDagPath) -> list[DagNode | None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getCommonAncestor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getSiblings(self) -> list[list[DagNode]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getSiblings` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getOutlinerOrder(self) -> list[int]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getOutlinerOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setOutlinerOrder(self, index: int) -> list[DagNode]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.setOutlinerOrder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def reorder(self, *, front: bool = ..., f: bool = ..., back: bool = ..., b: bool = ..., relative: int = ..., r: int = ...) -> list[DagNode]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.reorder` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBoundingBox(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[om2.MBoundingBox]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getBoundingBox` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getBoundingBoxCorners(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[list[Vector]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getBoundingBoxCorners` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isIntermediateObject(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isIntermediateObject` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getInstances(self, noSelf: bool = ...) -> list[list[DagNode]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getInstances` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isInstanced(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isInstanced` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getInstanceIndex(self) -> list[int]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getInstanceIndex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getParents(self, indirect: bool = ...) -> list[list[Transform]]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getParents` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getParent(self, step: int = ...) -> list[Transform | None]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getParent` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isVisible(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isVisible` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getVisibility(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getVisibility` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getOutlinerVisibility(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getOutlinerVisibility` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setOutlinerVisibility(self, state: bool, *, fast: bool = ...) -> list[DagNode]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.setOutlinerVisibility` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getDisplayType(self) -> list[str]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.getDisplayType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setDisplayType(self, kind: str, *, fast: bool = ...) -> list[DagNode]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.setDisplayType` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isShadingOverridden(self) -> list[bool]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.isShadingOverridden` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def setShadingOverride(self, enabled: bool, *, fast: bool = ...) -> list[DagNode]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.setShadingOverride` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def deleteHistory(self, keepDeformers: bool = ...) -> list[DagNode]:
        """各要素の :meth:`~mlib.nodes.dagNode.DagNode.deleteHistory` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
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
