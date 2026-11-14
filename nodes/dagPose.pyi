# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""DAG階層の保存姿勢とバインドポーズを扱う。"""

import math
import shlex
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.nodeEdit import require_editable
from ..core.object import Object
from ..decorator import _pick_alias, _require_bool, undoChunk, undoTransaction
from ..maths import Matrix
from ..util import _UNSET, _world_space
from .node import Node, Nodes
from typing import Iterable
from mlib.nodes.skinCluster import SkinCluster



class DagPose(Node):
    """dagPoseノードを扱うクラス。DAGのメンバーの保存した姿勢と、バインドポーズを扱う。

    membersの接続と、保存したマトリクスや親の情報を、調べたり変えたりできる。
    バインドポーズも同じノード型なので、isBindPose()で見分ける。

    - reset()は、保存した姿勢を今の姿勢で上書きする。
    - restore()は、シーンの姿勢を保存した姿勢へ戻す。
    - merge()は、保存した情報をまとめ、skinCluster.bindPoseをつなぎ直す。

    skinCluster.bindPreMatrixの設定し直しはしない。作成は ``mlib.createDagPose`` で行う。

    保存・復元・メンバーの変更にはMaya標準の ``cmds.dagPose`` を使い、fast引数は無い
    (階層を補ったり姿勢を戻したりするMayaの決まりを、om2で作り直さないため)。
    """
    @classmethod
    def fromSkinCluster(cls, skinCluster: Node | str) -> DagPose | None:
        """skinClusterに接続されているバインドポーズを取得する。

        Args:
            skinCluster (Node | str): 調べるskinCluster。

        Returns:
            DagPose | None: bindPoseアトリビュートに接続されたポーズ。接続されていなければNone。

        Raises:
            ValueError: skinCluster以外を指定した場合。
            RuntimeError: 無効なノードの場合、またはdagPose以外が接続されている場合。
        """
        ...
    def isBindPose(self) -> bool:
        """バインドポーズとして保存されたノードか調べる。

        Returns:
            bool: bindPoseアトリビュートがTrueならTrue。

        Raises:
            RuntimeError: 無効なノードの場合。
        """
        ...
    def getMemberIndices(self) -> list[int]:
        """今も接続されているメンバーの論理番号を取得する。

        membersマルチアトリビュートにある番号のうち、入力が接続されている要素だけを返す。
        接続が外れた空の要素は除く。抜けた番号は詰めないので、worldMatrix・xformMatrixの番号と対応したままになる。

        Returns:
            list[int]: membersの論理番号。小さい順に並ぶ。並びの位置(物理番号)ではない。

        Raises:
            RuntimeError: 無効なノードの場合。
        """
        ...
    def getMembers(self) -> list[Node]:
        """メンバーを取得する。

        membersマルチアトリビュートの論理番号の順に並べる。

        Returns:
            list[Node]: メンバー。getMemberIndices()と同じ順に並ぶ。

        Raises:
            RuntimeError: 無効なノードの場合。
        """
        ...
    def getMemberIndex(self, member: Node | str) -> int:
        """指定したメンバーの論理番号を取得する。

        Args:
            member (Node | str): メンバーのノード。

        Returns:
            int: members・worldMatrix・xformMatrixに共通の論理番号。

        Raises:
            TypeError: 対応しない型を指定した場合。
            ValueError: ノードが無い場合、またはこのポーズのメンバーでない場合。
            RuntimeError: 無効なdagPoseの場合。
        """
        ...
    def getMatrix(self, member: Node | str, worldSpace: bool = ..., *, ws: bool = ...) -> Matrix:
        """指定したメンバーの、保存したマトリクスを取得する。

        membersと同じ論理番号で、worldMatrixかxformMatrixを読む。
        今のTransformのマトリクスを調べたり、姿勢を戻したりはしない。

        Args:
            member (Node | str): このポーズのメンバー。
            worldSpace (bool): Trueなら保存したワールドマトリクス、Falseなら保存したローカルの
                マトリクス(xformMatrix)を取得する。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Matrix: 保存したマトリクスの新しいコピー。変えてもポーズやシーンは変わらない。

        Raises:
            TypeError: worldSpaceがbool以外の場合、memberが使えない型の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: このポーズのメンバーでない場合。
            RuntimeError: 無効なdagPoseの場合。
        """
        ...
    def getNotAtPose(self) -> list[Node]:
        """保存した姿勢から外れているメンバーを取得する。

        ``cmds.dagPose(query=True, atPose=True)`` で調べる(Bind Poseメニューの判定と同じ)。
        どこまでの差を許すかはMayaの判定に従う。

        Returns:
            list[Node]: 保存した姿勢から外れているメンバー。全員が保存した姿勢なら空リスト。

        Raises:
            RuntimeError: 無効なdagPoseの場合。
        """
        ...
    def isAtPose(self) -> bool:
        """すべてのメンバーが保存した姿勢にあるか調べる。

        Returns:
            bool: getNotAtPose()が空ならTrue。

        Raises:
            RuntimeError: 無効なdagPoseの場合。
        """
        ...
    def getSkinClusters(self) -> list[SkinCluster]:
        """このポーズをバインドポーズとして使っているskinClusterを取得する。

        Returns:
            list[SkinCluster]: messageからskinCluster.bindPoseへの接続先。同じものは1回だけ含む。

        Raises:
            RuntimeError: 無効なdagPoseの場合。
        """
        ...
    def restore(self, worldSpace: bool = ..., *, ws: bool = ...) -> DagPose:
        """保存した姿勢へ戻す。

        接続やロックを外すことはしない。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならローカル空間で戻す。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            DagPose: 自身。

        Raises:
            TypeError: worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: 無効なノードの場合、またはMayaが姿勢を戻すのを拒否した場合。
        """
        ...
    def reset(self, members: Node | str | Iterable[Node | str] | None = ...) -> DagPose:
        """保存した姿勢を、シーンの今の姿勢で上書きする。

        ノードを保存した姿勢へ動かすrestore()とは逆に、保存している側だけを変える。
        skinCluster.bindPreMatrixやウェイトは変えない。
        対象をすべて確かめてからMayaの ``dagPose -reset`` を呼び、1回のUndoにまとめる。

        Args:
            members (Node | str | Iterable[Node | str] | None): 上書きするメンバー。Noneなら全メンバー。
                Noneでメンバーが1つも無ければ、何も変えない。

        Returns:
            DagPose: 自身。

        Raises:
            TypeError: 使えない型を指定した場合。
            ValueError: 指定したものが空の場合、またはTransform以外かメンバー以外を含む場合。
            RuntimeError: 無効なノードの場合、またはMayaが上書きを拒否した場合。
        """
        ...
    def addMembers(self, *members: Node | str | Iterable[Node | str]) -> DagPose:
        """TransformやJointを、今の姿勢でポーズへ加える。

        Mayaの ``dagPose -addToPose`` を使う。姿勢を戻すのに要る親の情報も、Mayaの決まりで保存する。
        すでにメンバーのものは飛ばし、その保存した姿勢も変えない(変えるにはreset()を使う)。

        Args:
            *members (Node | str | Iterable[Node | str]): 加えるノード。空にはできない。

        Returns:
            DagPose: 自身。

        Raises:
            TypeError: 使えない型を指定した場合。
            ValueError: 何も指定しなかった場合、またはTransform以外を含む場合。
            RuntimeError: 無効なノードの場合、またはMayaが追加を拒否した場合。
        """
        ...
    def removeMembers(self, *members: Node | str | Iterable[Node | str]) -> DagPose:
        """メンバーをポーズから外す。

        シーンのノードそのものは削除しない。
        残るメンバーの親として必要なノードは、Mayaがポーズに残すことがある。

        Args:
            *members (Node | str | Iterable[Node | str]): 外すメンバー。空にはできない。

        Returns:
            DagPose: 自身。

        Raises:
            TypeError: 使えない型を指定した場合。
            ValueError: 何も指定しなかった場合、またはTransform以外かメンバー以外を含む場合。
            RuntimeError: 無効なノードの場合、またはMayaが外すのを拒否した場合。
        """
        ...
    def merge(self, sources: DagPose | str | Iterable[DagPose | str], *, currentPose: bool = ..., deleteSources: bool = ...) -> DagPose:
        """ほかのポーズをこのポーズへまとめる。

        まとめた後、skinClusterのbindPoseがつながる先を、このポーズへ揃える。

        - currentPose=False: 保存した姿勢・親の情報・xformの内部情報が食い違っていれば、
          何も変える前にエラーにする。
        - currentPose=True: 食い違っていてもかまわない。このポーズのメンバーも含めて、今の姿勢を保存する。

        すでにある論理番号は、間が空いていてもそのまま使う。ジョイントの姿勢・ウェイト・bindPreMatrixは変えない。

        変える前に、入力・食い違い・ロック・リファレンス・削除できるかを確かめ、変更は1回のUndoにまとめる。
        Undoが有効なら、途中で失敗したときにUndoで元に戻す(undoTransaction)。ただし、必ず戻せるとは限らない。

        Args:
            sources (DagPose | str | Iterable[DagPose | str]): まとめる元のdagPose。
                このポーズ自身や、2回以上指定したものは無視する。空にはできない。
            currentPose (bool): Trueなら、保存した姿勢ではなく今の姿勢と階層を保存する。既定はFalse。
            deleteSources (bool): Trueなら、まとめた後に元のポーズを削除する。既定はTrue。
                元のポーズに、メンバー・親の情報・skinCluster.bindPose・joint.bindPoseからの
                保存したマトリクス以外の接続があればエラーにする。

        Returns:
            DagPose: 自身。

        Raises:
            TypeError: currentPose・deleteSourcesがbool以外の場合、またはsourcesが使えない型の場合。
            ValueError: 何も指定しなかった場合、dagPose以外を含む場合、保存した情報が食い違う場合、
                または通常のポーズとバインドポーズが混ざっている場合。
            RuntimeError: ロック・リファレンス・インスタンス・不正な保存情報がある場合、
                またはMayaでの変更が失敗した場合。
        """
        ...
    def _member_sources(self) -> list[tuple[int, om2.MPlug]]:
        """接続されたmembers要素の論理番号と接続元を取得する。

        Returns:
            list[tuple[int, om2.MPlug]]: 論理番号の昇順の(番号, 接続元のPlug)。
        """
        ...
    def _merge_collect_poses(self, sources: object) -> tuple:
        """対象自身と統合元を入力順に解決し、同じポーズを一度だけ扱う。

        Args:
            sources (object): 統合元のポーズ入力。

        Returns:
            tuple: 対象名、対象を先頭とするポーズ辞書、対象自身を除いた統合元のlist。
        """
        ...
    def _merge_collect_rows(self, poses: dict, current_pose: bool, delete_sources: bool) -> tuple:
        """保存行とskinClusterを集め、姿勢の競合と統合元の削除可否を検査する。

        Args:
            poses (dict): 対象を先頭とするポーズ辞書。
            current_pose (bool): 保存姿勢の競合を許容し、現在の姿勢を後で保存するか。
            delete_sources (bool): 統合元の削除可否を検査するか。

        Returns:
            tuple: 統合する保存行、対象の既存保存行、再接続するskinCluster辞書。
        """
        ...
    def _merge_check_targets(self, skins: dict):
        """対象の保存先とskinClusterの再接続先が編集できることを検査する。

        Args:
            skins (dict): 再接続するskinCluster辞書。
        """
        ...
    def _merge_allocate_indices(self, rows: dict, target_rows: dict) -> dict:
        """既存の疎な保存番号を保ち、未登録メンバーへ後続の番号を割り当てる。

        Args:
            rows (dict): 統合する保存行。
            target_rows (dict): 対象の既存保存行。

        Returns:
            dict: メンバー名から保存先の論理番号への対応。
        """
        ...
    def _merge_write_rows(self, name: str, rows: dict, target_rows: dict, indices: dict, current_pose: bool):
        """メンバー・マトリクス・親情報を既存の順序でMayaの保存先へ書き込む。

        Args:
            name (str): 対象ポーズの名前。
            rows (dict): 統合する保存行。
            target_rows (dict): 対象の既存保存行。
            indices (dict): メンバー名から保存先の論理番号への対応。
            current_pose (bool): 既存メンバーも現在姿勢の行で更新するか。
        """
        ...
    @staticmethod
    def _merge_set_matrix(destination: str, values: tuple):
        """完全なxformデータをcmdsの複合引数へ変換してUndo可能に設定する。

        Args:
            destination (str): 設定先のアトリビュート名。
            values (tuple): _merge_matrix_payload()の戻り値。
        """
        ...
    @staticmethod
    def _merge_matrix_payload(plug: om2.MPlug) -> tuple:
        """Mayaの保存表現からcmds.setAttr用の完全なmatrixデータを読む。

        16要素のマトリクスへ変換するとjointOrient・pivot等のxform情報が失われる。
        Maya生成のsetAttrを実行せず、数値・bool・xformマーカーだけを取り出す。

        Args:
            plug (om2.MPlug): worldMatrixまたはxformMatrixの要素。

        Returns:
            tuple: setAttrの引数に変換できる値の並び。
        """
        ...
    def _merge_snapshot(self) -> dict:
        """メンバー・親の対応・完全な保存姿勢を取得し、不正な接続を拒否する。

        Returns:
            dict: メンバーの完全パスから保存行(index・parent・externalParent・
                worldMatrix・xformMatrix・global)への対応。
        """
        ...
    @staticmethod
    def _merge_rows_equal(left: dict, right: dict) -> bool:
        """同じメンバーの親・復元範囲・xformの内部情報まで比較する。

        Args:
            left (dict): 保存行。
            right (dict): 保存行。

        Returns:
            bool: 一致すればTrue。
        """
        ...
    def _merge_check_delete(self):
        """統合元の削除で失われる外部接続とロックを事前に検査する。"""
        ...
    @staticmethod
    def _transform_names(members: object) -> list[str]:
        """対象を有効なTransformの完全パスに揃える。

        Args:
            members (object): 単体または反復可能な対象。

        Returns:
            list[str]: 入力順・重複なしの完全パス。

        Raises:
            TypeError: 対応しない型の場合。
            ValueError: 空入力、または有効なTransform以外を含む場合。
        """
        ...
    def _pose_name(self):
        """有効なdagPoseの名前を返す。削除済みならRuntimeError。"""
        ...
