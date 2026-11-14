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

#: :meth:`Joint.orient` の orientation に指定できる値(``cmds.joint(orientJoint=...)`` と同じ)。
_ORIENTATIONS = ("xyz", "yzx", "zxy", "zyx", "yxz", "xzy", "none")

#: :meth:`Joint.orient` の secondaryAxisOrient に指定できる値(``cmds.joint`` と同じ)。
_SECONDARY_AXES = ("xup", "xdown", "yup", "ydown", "zup", "zdown")


def _orient_flags(orientation, secondaryAxisOrient, children, zeroScaleOrient):
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
    for value, label in ((orientation, "orientation"), (secondaryAxisOrient, "secondaryAxisOrient")):
        if not isinstance(value, str):
            raise TypeError(f"{label}は文字列で指定してください")
    if orientation not in _ORIENTATIONS:
        raise ValueError(f"orientationは{', '.join(_ORIENTATIONS)}のどれかで指定してください: {orientation!r}")
    if secondaryAxisOrient not in _SECONDARY_AXES:
        raise ValueError(f"secondaryAxisOrientは{', '.join(_SECONDARY_AXES)}のどれかで指定してください: {secondaryAxisOrient!r}")
    _require_bool(children, "children")
    _require_bool(zeroScaleOrient, "zeroScaleOrient")
    return {"edit": True, "orientJoint": orientation, "secondaryAxisOrient": secondaryAxisOrient, "children": children, "zeroScaleOrient": zeroScaleOrient}


@contextmanager
def _unlocked_influences(skins, fast=False):
    """skinClusterのウェイトのロックを一時的に外し、抜けるときに元へ戻す。

    Args:
        skins (Iterable[SkinCluster]): ロックを外すskinCluster。
        fast (bool): Trueはロックの切替えをUndoへ記録しない。

    Yields:
        None: 値を渡さない。

    Raises:
        RuntimeError: lockInfluenceWeightsがロック・入力接続されていて切り替えられない場合。何も変更しない。
    """
    locked = {}
    for skin in skins:
        for node in skin.getLockedInfluences():
            locked[node.getUuid()] = node
    for node in locked.values():
        node.getPlug("lockInfluenceWeights")._require_writable()
    for node in locked.values():
        node.getPlug("lockInfluenceWeights").set(False, fast=fast)
    try:
        yield
    finally:
        for node in locked.values():
            # 削除やinfluenceの解除で消えたアトリビュートは戻さない。
            if node.isValid() and node.hasAttr("lockInfluenceWeights"):
                node.getPlug("lockInfluenceWeights").set(True, fast=fast)


def _influences_by_skin(joints):
    """jointを、登録先のskinClusterごとにまとめる。

    Args:
        joints (Iterable[Joint]): 調べるjoint。

    Returns:
        list[tuple[SkinCluster, list[Joint]]]: skinClusterと、そこへ登録されたjoint。
    """
    groups = {}
    for joint in joints:
        for skin in joint.getSkinClusters():
            if skin.hasInfluence(joint.getFullName()):
                groups.setdefault(skin.getUuid(), (skin, []))[1].append(joint)
    return list(groups.values())


def _remove_influences(groups, transfer_to_parent, force, fast=False, deleting=False):
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
    with _unlocked_influences([skin for skin, _ in groups], fast=fast):
        checked = [(skin, skin._influence_removal_plans(joints, transfer_to_parent, force=force)) for skin, joints in groups]
        for skin, (plans, snapshot) in checked:
            skin._apply_influence_removals(plans, snapshot, force=force, fast=fast, deleting=deleting)


def _delete_joints(joints, safe, fast, remove_influence, transfer_to_parent, force):
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
    _require_bool(safe, "safe")
    _require_bool(remove_influence, "removeInfluence")
    _require_bool(transfer_to_parent, "transferToParent")
    _require_bool(force, "force")
    for joint in joints:
        joint._require_valid("削除")
    if safe:
        joints = [joint for joint in joints if not joint._has_delete_connections()]
    if not joints:
        return
    checked = check_deletion(joints, fast=fast)
    if remove_influence:
        # 親と一緒に消える子孫も解除しないと、消えたjointの列にウェイトが残る。
        doomed = {}
        for joint in joints:
            for node in [joint] + list(joint.getChildren(allDescendents=True, type="joint")):
                doomed[node.getUuid()] = node
        # 全influenceが消えるskinClusterは解除の移送先も再配分先も無いため、Maya標準の削除に任せる。
        groups = [(skin, nodes) for skin, nodes in _influences_by_skin(doomed.values()) if len(nodes) < len(skin.getInfluences())]
        _remove_influences(groups, transfer_to_parent, force, fast=fast, deleting=True)
    delete_nodes(joints, fast=fast, checked=checked)


class Joint(Transform):
    """ジョイントを扱うクラス。回転の移し替えや、スケールの補正の操作を持つ。

    マトリクスや移動・回転・スケールの操作はTransformから受け継ぎ、
    rotateAxis・jointOrient・segmentScaleCompensateも考えて計算する。
    次の3つは、それぞれ別々の操作になっている。

    - segmentScaleCompensate(SSC)の切り替え
    - inverseScaleの接続
    - 姿勢を保ったままの回転の移し替え(jointOrientとrotateの間)
    """

    def getSegmentScaleCompensate(self):
        """segmentScaleCompensateがオンか取得する。

        inverseScaleに親のscaleが接続されているかや、補正が思ったとおりに効くかは確かめない。

        Returns:
            bool: segmentScaleCompensateの今の値。
        """
        return bool(self.getPlug("segmentScaleCompensate").get())

    def setSegmentScaleCompensate(self, state, *, fast=False):
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
        with _edit_context("mlibJointSetSegmentScaleCompensate", fast):
            _require_bool(state, "state")
            self.getPlug("segmentScaleCompensate").set(state, fast=fast)
            return self

    def getJointOrient(self):
        """jointOrientを取得する。

        XYZの回転順・ラジアンの値をEulerRotateで返す。
        ノードのrotateOrderや、UIの角度の単位は使わない。
        rotateやrotateAxis、親の回転は足し合わせない。

        Returns:
            EulerRotate: jointOrientの値の新しいオブジェクト。無効なノードではXYZとも0になる。
                ノードが有効かはisValidで確かめる。
        """
        values = self._compound_values("jointOrient", angle=True)
        return EulerRotate(*(math.radians(value) for value in values))

    def jointOrientToRotate(self):
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
        with undoChunk("mlibJointJointOrientToRotate"):
            self._require_valid("方向の変更")
            self._apply_rotate_transfer(self._joint_rotate_transfer_values())
            return self

    def freezeRotate(self):
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
        with undoChunk("mlibJointFreezeRotate"):
            self._require_valid("回転のフリーズ")
            self._apply_rotate_transfer(self._joint_rotate_transfer_values(to_orient=True), to_orient=True)
            return self

    def orient(self, orientation="xyz", secondaryAxisOrient="yup", children=True, zeroScaleOrient=True):
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
        flags = _orient_flags(orientation, secondaryAxisOrient, children, zeroScaleOrient)
        self._require_valid("方向の設定")
        with undoChunk("mlibJointOrient"):
            self._orient(flags)
            return self

    def mirror(self, axis="YZ", behavior=True, searchReplace=None):
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
        flag = "mirror" + _MIRROR_PLANES[_mirror_axis(axis)]
        _require_bool(behavior, "behavior")
        flags: Dict[str, Any] = {flag: True, "mirrorBehavior": behavior}
        if searchReplace is not None:
            if (
                isinstance(searchReplace, str)
                or not isinstance(searchReplace, (tuple, list))
                or len(searchReplace) != 2
                or not all(isinstance(item, str) for item in searchReplace)
            ):
                raise TypeError("searchReplaceは(search, replace)の文字列の組かNoneで指定してください")
            if not searchReplace[0]:
                raise ValueError("searchReplaceの検索文字列は空にできません")
            flags["searchReplace"] = tuple(searchReplace)
        self._require_valid("ミラー")
        with undoChunk("mlibJointMirror"):
            parent = self.getParent()
            # mirrorJointの選択変更はUndoに記録されないため、前後の選択を明示してUndo/Redoで再現する。
            cmds.select(self.getFullName(), replace=True)
            result = cmds.mirrorJoint(self.getFullName(), **flags)
            if not result:
                raise RuntimeError(f"Mayaが{self.getName()}のミラーしたジョイントを作成しませんでした")
            prefix = parent.getFullName() if parent is not None else ""
            root = Joint(prefix + "|" + result[0])
            cmds.select(root.getFullName(), replace=True)
            return root

    def connectInverseScale(self, source=None, force=False, *, fast=False):
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
        with _edit_context("mlibJointConnectInverseScale", fast):
            _require_bool(force, "force")
            self._require_valid("inverseScaleの接続")
            source = self.getParent() if source is None else Node._resolve_input(source)
            if source is None:
                return self
            if not isinstance(source, Transform):
                raise TypeError("sourceはTransformで指定してください")
            if source == self:
                raise ValueError("inverseScaleの入力元に、そのジョイント自身は指定できません")
            origin = source.getPlug("scale")
            target = self.getPlug("inverseScale")
            if target.getSource() != origin:
                origin.connectTo(target, force=force, fast=fast)
            return self

    def disconnectInverseScale(self, *, fast=False):
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
        with _edit_context("mlibJointDisconnectInverseScale", fast):
            for name in ("inverseScale", "inverseScaleX", "inverseScaleY", "inverseScaleZ"):
                target = self.getPlug(name)
                origin = target.getSource()
                if origin is not None:
                    target.disconnect(origin, fast=fast)
            return self

    def getRadius(self):
        """ジョイントごとの表示の半径を取得する。

        Returns:
            float: radiusアトリビュートの値。Maya全体のjointDisplayScaleとは別の値。
        """
        return float(self.getPlug("radius").get())

    def setRadius(self, value, *, fast=False):
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
        with _edit_context("mlibJointSetRadius", fast):
            # この処理でだけ使うため、mlibの読み込み時間に含めない。
            import numbers

            if isinstance(value, bool) or not isinstance(value, numbers.Real):
                raise TypeError("radiusは数値で指定してください")
            value = float(value)
            if not math.isfinite(value) or value < 0:
                raise ValueError("radiusは0以上の有限な数値で指定してください")
            self.getPlug("radius").set(value, fast=fast)
            return self

    def getPreferredAngle(self, *, unit="deg"):
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
        self._require_valid("優先角度の取得")
        return [float(value) for value in self.getPlug("preferredAngle").get(unit=unit)]

    def setPreferredAngle(self, value=None, *, unit="deg"):
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
        with undoChunk("mlibJointSetPreferredAngle"):
            self._require_valid("優先角度の設定")
            if value is None:
                value, unit = tuple(self.getPlug("rotate").get(unit="rad")), "rad"
            else:
                value = _finite_vector(value, 3, "value")
            self.getPlug("preferredAngle").set(value, unit=unit)
            return self

    def assumePreferredAngles(self, children=True):
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
        _require_bool(children, "children")
        self._require_valid("優先角度の適用")
        with undoChunk("mlibJointAssumePreferredAngles"):
            cmds.joint(self.getFullName(), edit=True, assumePreferredAngles=True, children=children)
        return self

    def getDegreesOfFreedom(self):
        """回転できる軸を取得する。

        jointTypeX・Y・Zがオンになっている軸を返す。

        Returns:
            str: 回転できる軸の名前をXYZの順につなげた文字列(``"xyz"``・``"xz"`` など)。
                すべての軸が固定なら空文字列。

        Raises:
            RuntimeError: ジョイントが無効な場合。
        """
        self._require_valid("自由度の取得")
        return "".join(axis for axis in "xyz" if self.getPlug("jointType" + axis.upper()).get())

    def setDegreesOfFreedom(self, axes):
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
        if not isinstance(axes, str):
            raise TypeError(f"axesは'xyz'のような文字列で指定してください: {axes!r}")
        lowered = axes.lower()
        if set(lowered) - set("xyz") or len(set(lowered)) != len(lowered):
            raise ValueError(f"axesは'x'・'y'・'z'を重複なく組み合わせて指定してください: {axes!r}")
        self._require_valid("自由度の設定")
        plugs = [self.getPlug("jointType" + axis.upper()) for axis in "XYZ"]
        # 一部の軸だけ書き換わるのを避けるため、3軸とも書き込めるか先に確かめる。
        for plug in plugs:
            require_writable(plug.mplug())
        with undoChunk("mlibJointSetDegreesOfFreedom"):
            for axis, plug in zip("xyz", plugs):
                plug.set(axis in lowered)
        return self

    def getInverseScale(self):
        """inverseScaleの値を取得する。

        アトリビュートの値のXYZをそのまま返す。逆数にはせず、segmentScaleCompensateのオン・オフでも値は変えない。

        Returns:
            Scale: inverseScaleの値の新しいオブジェクト。無効なノードではXYZとも0になる。
                補正が実際に効いているかや、ノードが有効かを判断するための値ではない。
        """
        return Scale(*self._compound_values("inverseScale"))

    def getDepth(self):
        """ジョイントの階層の中での深さを取得する。

        Returns:
            int: 階層の深さ。ルートのジョイントを0として数える。
        """
        depth = 0
        parent = self.getParent() if self.isValid() else None
        while isinstance(parent, Joint):
            depth += 1
            parent = parent.getParent()
        return depth

    def getSkinClusters(self):
        """このジョイントに接続しているskinClusterを取得する。

        Returns:
            list[SkinCluster]: skinClusterのオブジェクト。同じものは1回だけ含む。
        """
        # 循環参照の回避: 同じパッケージ内で相互に参照するため、使う時点で読み込む。
        from .skinCluster import SkinCluster

        if not self.isValid():
            return []
        seen = set()
        result = []
        for plug in self.getConnections(type="skinCluster"):
            node = plug.getNode()
            if node.getUuid() in seen:
                continue
            seen.add(node.getUuid())
            mobject = node.mnode()
            assert mobject is not None
            result.append(SkinCluster(mobject))
        return result

    def removeInfluence(self, skinCluster=None, *, transferToParent=True, force=False):
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
        with undoChunk("mlibJointRemoveInfluence"):
            # 循環参照の回避: 同じパッケージ内で相互に参照するため、使う時点で読み込む。
            from .skinCluster import SkinCluster

            self._require_valid("削除")
            _require_bool(transferToParent, "transferToParent")
            _require_bool(force, "force")
            skins = self.getSkinClusters() if skinCluster is None else [skinCluster if isinstance(skinCluster, SkinCluster) else SkinCluster(skinCluster)]
            _remove_influences([(skin, [self]) for skin in skins], transferToParent, force)
            return self

    def delete(self, *, safe=False, fast=False, removeInfluence=True, transferToParent=True, force=False):
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
        with _edit_context("mlibJointDelete", fast):
            _delete_joints([self], safe, fast, removeInfluence, transferToParent, force)

    def isInfluenceLocked(self):
        """スキンのウェイトがロックされているか調べる。

        lockInfluenceWeightsアトリビュートの値を見る。このアトリビュートは、skinClusterへバインドしたときに追加される。

        Returns:
            bool: ロックされていればTrue。アトリビュートが無い(どのskinClusterのインフルエンスでもない)場合はFalse。
        """
        return self.hasAttr("lockInfluenceWeights") and bool(self.getPlug("lockInfluenceWeights").get())

    def setInfluenceLocked(self, state=True):
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
        with undoChunk("mlibJointSetInfluenceLocked"):
            _require_bool(state, "state")
            if not self.hasAttr("lockInfluenceWeights"):
                raise RuntimeError(f"ジョイントはどのskinClusterのインフルエンスでもありません: {self.getFullName()}")
            self.getPlug("lockInfluenceWeights").set(state)
            return self

    def getBoneSegments(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=True)
        ws = _world_space(worldSpace)
        children = self.getChildren(type="joint")
        if ws:
            ends = [child.getTranslation(worldSpace=True) for child in children]
        else:
            # 子の位置は自身の空間で表されるため、自身のマトリクスで親側の空間へ写す。
            matrix = self.getMatrix()
            ends = [matrix.transformPoint(child.getTranslation()) for child in children]
        start = self.getTranslation(worldSpace=ws)
        segments = [(Vector(start.x, start.y, start.z), Vector(end.x, end.y, end.z)) for end in ends]
        return segments or [(Vector(start.x, start.y, start.z), Vector(start.x, start.y, start.z))]

    def getTransferTarget(self, skin):
        """ウェイトを移す先になる、いちばん近い祖先のインフルエンスを探す。

        Args:
            skin (SkinCluster): インフルエンスになっているかを調べるskinCluster。

        Returns:
            str | None: 移す先の祖先のジョイントの名前。見つからない場合は ``None``。
        """
        ancestor = self.getParent() if self.isValid() else None
        while isinstance(ancestor, Joint):
            if skin.hasInfluence(ancestor.getName()):
                return ancestor.getName()
            ancestor = ancestor.getParent()
        return None

    def reparentChildren(self, parentJoint):
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
        with undoChunk("mlibJointReparentChildren"):
            parent_name = Node._input_name(parentJoint)
            for child_joint in self.getChildren(type="joint"):
                cmds.parent(child_joint.getFullName(), parent_name)
            return self

    def getChainFromHere(self, to=None):
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
        self._require_valid("チェーンの作成")
        if to is None:
            chain: List[Joint] = [self]
            current = self
            while True:
                children = current.getChildren(type="joint")
                if len(children) != 1:
                    return chain
                current = children[0]
                chain.append(current)
        target = to if isinstance(to, Joint) else Joint(to)
        if not self.isAncestorOf(target):
            raise ValueError("toはこのジョイントの子孫で指定してください")
        chain = [self]
        current = self
        while current.getUuid() != target.getUuid():
            next_joint = next((child for child in current.getChildren(type="joint") if child.getUuid() == target.getUuid() or child.isAncestorOf(target)), None)
            if next_joint is None:
                raise ValueError("toはこのジョイントの子孫で指定してください")
            chain.append(next_joint)
            current = next_joint
        return chain

    def insertJoints(self, count):
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
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError(f"countはintで指定してください: {type(count).__name__}")
        if count < 1:
            raise ValueError(f"countは1以上で指定してください: {count}")
        self._require_valid("ジョイントの挿入")
        children = self.getChildren(type="joint")
        if len(children) != 1:
            raise ValueError(f"ジョイントには子のジョイントが1つだけ必要です: {len(children)}個: {self.getFullName()}")
        child = children[0]
        start = self.getTranslation(worldSpace=True)
        end = child.getTranslation(worldSpace=True)
        base = self.getName().split("|")[-1] + "_insert#"
        name = self.getFullName()
        unit = om2.MDistance.uiUnit()
        with undoChunk("mlibJointInsertJoints"):
            created = []
            parent = name
            for number in range(1, count + 1):
                joint = cmds.createNode("joint", name=base, parent=parent, skipSelect=True)
                joint = cmds.ls(joint, long=True)[0]
                for attribute in ("rotateOrder", "radius", "segmentScaleCompensate"):
                    cmds.setAttr(joint + "." + attribute, cmds.getAttr(name + "." + attribute))
                cmds.connectAttr(parent + ".scale", joint + ".inverseScale")
                ratio = number / (count + 1.0)
                position = [om2.MDistance(a + (b - a) * ratio).asUnits(unit) for a, b in zip(start, end)]
                cmds.xform(joint, worldSpace=True, translation=position)
                created.append(joint)
                parent = joint
            cmds.parent(child.getFullName(), parent)
            return [Joint(joint) for joint in created]

    def getPolePosition(self, distance=None):
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
        if distance is not None:
            if isinstance(distance, bool) or not isinstance(distance, (int, float)):
                raise TypeError(f"distanceは数値かNoneで指定してください: {type(distance).__name__}")
            if not math.isfinite(distance) or distance <= 0:
                raise ValueError(f"distanceは正の有限な数値で指定してください: {distance}")
        self._require_valid("ポールの位置の取得")
        chain = [self]
        for _ in range(2):
            children = chain[-1].getChildren(type="joint")
            if len(children) != 1:
                raise ValueError(f"ジョイントには子のジョイントが1つだけ必要です: {len(children)}個: {chain[-1].getFullName()}")
            chain.append(children[0])
        start, middle, end = (om2.MVector(joint.getTranslation(worldSpace=True)) for joint in chain)
        length = (middle - start).length() + (end - middle).length()
        line = end - start
        if line.length() <= 1e-9 * max(length, 1.0):
            raise ValueError("3つのジョイントが一直線上にあります")
        foot = start + line * (((middle - start) * line) / (line * line))
        bend = middle - foot
        if bend.length() <= 1e-6 * max(length, 1e-9):
            raise ValueError("3つのジョイントが一直線上にあります")
        result = middle + bend.normal() * (length if distance is None else float(distance))
        return Vector(result.x, result.y, result.z)

    def getIkHandles(self):
        """自身を開始ジョイントにしているIKハンドルを取得する。

        自身がIKチェーンの途中や末端のジョイントの場合は見つからない。
        ジョイントからIKハンドルをたどれるのは、IKハンドルの ``startJoint`` への接続だけのため。

        Returns:
            list[IkHandle]: 自身を開始ジョイントにしているIkHandle。無ければ空リスト。
        """
        # nodes の初期化順に依存しないよう、使う時点で読み込む。
        from .ikHandle import IkHandle

        if not self.isValid():
            return []
        seen = set()
        result = []
        for plug in self.getConnections(type="ikHandle"):
            node = plug.getNode()
            if node.getUuid() in seen:
                continue
            seen.add(node.getUuid())
            mobject = node.mnode()
            assert mobject is not None
            result.append(IkHandle(mobject))
        return result

    def _orient(self, flags):
        """検証済みのフラグで向きを揃え、末端jointのjointOrientを0にする。

        Args:
            flags (dict): :func:`_orient_flags` が返したcmds.jointのフラグ。

        Returns:
            None: 値を返さない。
        """
        name = self.getFullName()
        cmds.joint(name, **flags)
        targets = [name]
        if flags["children"]:
            targets += cmds.listRelatives(name, allDescendents=True, type="joint", fullPath=True) or []
        for target in targets:
            if not cmds.listRelatives(target, children=True, type="joint"):
                cmds.setAttr(target + ".jointOrient", 0.0, 0.0, 0.0)

    def _joint_rotate_order(self):
        """Maya の rotateOrder を API の回転順序へ変換する。

        rotateOrder の番号(0=xyz〜5=zyx)は MEulerRotation.kXYZ〜kZYX と同じ並び。

        Returns:
            int: rotateOrder に対応する Maya API 2.0 の MEulerRotation 定数。
        """
        return self._rotate_order()

    def _joint_rotate_transfer_values(self, to_orient=False):
        """書込み可否を検証し、合成後の回転を現在の角度単位で返す。

        Args:
            to_orient (bool): TrueでjointOrient用XYZ、FalseでrotateOrderのrotate用。

        Returns:
            tuple[float, float, float] | None: 合成値。移送元が0ならNone。

        Raises:
            RuntimeError: 無効joint、ロック、入力接続、書込み不可の場合。
        """
        self._require_valid("方向の変更")
        orient = self._compound_values("jointOrient", angle=True)
        rotate = self._compound_values("rotate", angle=True)
        if not any(rotate if to_orient else orient):
            return None
        name = self.getFullName()
        for attribute in ("rotate", "jointOrient"):
            for suffix in ("", "X", "Y", "Z"):
                plug = name + "." + attribute + suffix
                try:
                    self.getPlug(attribute + suffix)._require_writable()
                except RuntimeError as exc:
                    raise RuntimeError(f"アトリビュートはロックされておらず、入力の接続もない状態にしてください: {plug}") from exc
        rotation = om2.MEulerRotation(*(math.radians(v) for v in rotate), self._joint_rotate_order())
        # jointOrientはrotateOrderに関係なくXYZ。MayaのR * JOを合成する。
        orientation = om2.MEulerRotation(*(math.radians(v) for v in orient))
        combined = om2.MTransformationMatrix(rotation.asMatrix() * orientation.asMatrix())
        result = combined.rotation(asQuaternion=True).asEulerRotation()
        result.reorderIt(om2.MEulerRotation.kXYZ if to_orient else self._joint_rotate_order())
        return tuple(om2.MAngle(v).asUnits(om2.MAngle.uiUnit()) for v in result)

    def _apply_rotate_transfer(self, values, to_orient=False):
        """検証済みの回転移送値をcmdsで適用する。

        Args:
            values (tuple | None): 現在のUI角度単位の3成分。Noneなら更新しない。
            to_orient (bool): TrueならjointOrientへ移しrotateを0にする。

        Returns:
            None: 値を返さない。
        """
        if values is None:
            return
        set_attr(self.getFullName() + ".jointOrient", *(values if to_orient else (0, 0, 0)))
        set_attr(self.getFullName() + ".rotate", *((0, 0, 0) if to_orient else values))

    def _rotate_quaternion(self, attribute):
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
        values = self._compound_values(attribute, angle=True)
        rotation = om2.MEulerRotation(*(math.radians(value) for value in values))
        return rotation.asQuaternion()

    def _remove_segment_scale_compensation(self, matrix):
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
        if not self.getPlug("ssc").get():
            return matrix
        inverse_scale = self._compound_values("inverseScale")
        if any(abs(value) < 1e-12 for value in inverse_scale):
            raise ValueError("segmentScaleCompensateが有効な場合、inverseScaleの各成分に0は指定できません")
        result = matrix * Matrix(scale=inverse_scale)
        result.translate = matrix.translate
        return result

    def _rotate_reference(self, reference):
        """:meth:`getRotate` が Euler の解を選ぶ基準を返す。

        joint の getRotate は jointOrient と rotateAxis を含む回転で rotate チャンネルとは
        別の回転なので、チャンネル値ではなく 0 回転(ノードの rotateOrder)を基準にする。

        Args:
            reference (om2.MEulerRotation): 現在の rotate チャンネル値(順序だけを使う)。

        Returns:
            om2.MEulerRotation: 0 回転。順序はノードの rotateOrder。
        """
        return om2.MEulerRotation(0.0, 0.0, 0.0, reference.order)

    def _channel_rotate(self, quaternion, reference):
        """ローカルマトリクスの回転から jointOrient と rotateAxis を除き、rotate の値へ変換する。

        Maya の joint の回転は rotateAxis、rotate、jointOrient の順に適用されるため、
        rotate = rotateAxis⁻¹ · マトリクスの回転 · jointOrient⁻¹(om2 のクォータニオンの積の順序)。

        Args:
            quaternion (om2.MQuaternion): ローカルマトリクスの回転。
            reference (om2.MEulerRotation): 現在の rotate チャンネル値。

        Returns:
            om2.MEulerRotation: ノードの rotateOrder で表した、reference に最も近い解。
        """
        rotate_axis = self._rotate_quaternion("rotateAxis")
        joint_orient = self._rotate_quaternion("jointOrient")
        return _closest_euler(rotate_axis.conjugate() * quaternion * joint_orient.conjugate(), reference)

    def _apply_local_matrix(self, matrix, scale_reference=None, *, fast=False):
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
        super()._apply_local_matrix(matrix, scale_reference, fast=fast)

    def _compound_values(self, attribute, angle=False):
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
        if not self.isValid():
            return (0.0, 0.0, 0.0)
        plug = self._dependency_fn().findPlug(attribute, False)
        if angle:
            return tuple(plug.child(index).asMAngle().asDegrees() for index in range(3))
        return tuple(plug.child(index).asDouble() for index in range(3))


class Joints(Nodes):
    """Jointのオブジェクトをまとめて持つコレクション。型や重なりの扱いはNodesと同じ。"""

    item_class = Joint
    _items: List[Joint]

    def sortedByDepth(self):
        """深いジョイントから順に並べた、新しいコレクションを返す。

        Returns:
            Joints: 深さの順に並べたコレクション。子のジョイントを先に処理したいときに使う。
        """
        return Joints(sorted(self._items, key=lambda joint: joint.getDepth(), reverse=True))

    def orient(self, orientation="xyz", secondaryAxisOrient="yup", children=True, zeroScaleOrient=True):
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
        flags = _orient_flags(orientation, secondaryAxisOrient, children, zeroScaleOrient)
        for joint in self._items:
            joint._require_valid("方向の設定")
        with undoChunk("mlibJointsOrient"):
            for joint in self._items:
                joint._orient(flags)
            return self

    def removeInfluence(self, skinCluster=None, *, transferToParent=True, force=False):
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
        # 循環参照の回避: 同じパッケージ内で相互に参照するため、使う時点で読み込む。
        from .skinCluster import SkinCluster  # skinClusterがjointをimportするため循環を避ける

        with undoChunk("mlibJointsRemoveInfluence"):
            _require_bool(transferToParent, "transferToParent")
            _require_bool(force, "force")
            for joint in self._items:
                joint._require_valid("削除")
            if skinCluster is None:
                groups = _influences_by_skin(self._items)
            else:
                groups = [(skinCluster if isinstance(skinCluster, SkinCluster) else SkinCluster(skinCluster), list(self._items))]
            for skin, joints in groups:
                if joints and len(joints) >= len(skin.getInfluences()):
                    raise ValueError("すべてのインフルエンスを削除することはできません")
            _remove_influences(groups, transferToParent, force)
            return self

    def delete(self, *, safe=False, fast=False, removeInfluence=True, transferToParent=True, force=False):
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
        with _edit_context("mlibJointsDelete", fast):
            _delete_joints(list(self._items), safe, fast, removeInfluence, transferToParent, force)

    def setRadius(self, value, *, fast=False):
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
        self._forward("setRadius", (value,), fast)
        return self

    def setSegmentScaleCompensate(self, state, *, fast=False):
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
        self._forward("setSegmentScaleCompensate", (state,), fast)
        return self

    def getSkinClusters(self):
        """すべてのジョイントに接続しているskinClusterを取得する。

        Returns:
            SkinClusters: skinClusterのコレクション。同じものは1回だけ含む。
        """
        # 循環参照の回避: 同じパッケージ内で相互に参照するため、使う時点で読み込む。
        from .skinCluster import SkinClusters

        skin_clusters = []
        seen = set()
        for joint in self._items:
            for skin in joint.getSkinClusters():
                if skin.getUuid() in seen:
                    continue
                seen.add(skin.getUuid())
                skin_clusters.append(skin)
        return SkinClusters(skin_clusters)
