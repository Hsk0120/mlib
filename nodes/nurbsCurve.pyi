# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Maya の NURBS カーブシェイプを扱う。"""

import math
import numbers
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..components.cv import CV, CVs
from ..components.pointComponent import _mirror_plan, _write_points
from ..core import geometryEdit as geometry_edit
from ..decorator import _edit_context, _pick_alias, _require_bool, preservedSelection, undoChunk
from ..maths.matrix import Matrix
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _finite, _world_space
from .shape import Shape
from typing import Iterable, Sequence

_AXES: dict
_DEGENERATE: float
_TRANSPORT_STEPS: int
_KEEP_RANGES: dict
_REBUILD_DEGREES: tuple
_GAUSS_LEGENDRE: tuple
_AREA_SUBDIVISIONS: int
_PLANAR_TOLERANCE: float

def _points_planar(points: Iterable[om2.MPoint]) -> bool:
    """CVが1つの平面の上にあるか調べる。

    B-スプラインの基底は互いに独立なので、カーブが平面上にあることと、CVが平面上にあることは同じになる。
    ``MFnNurbsCurve.isPlanar`` は使わない。Maya 2023では、平面でないカーブに対して呼ぶと、
    その後の ``curveInfo`` や ``findLengthFromParam`` の長さがずれる不具合があるため。

    Args:
        points (Iterable[om2.MPoint]): CVの位置。

    Returns:
        bool: CVが1つの平面の上にあればTrue。点が一直線上にあって平面が決まらない場合は、
            ``MFnNurbsCurve.isPlanar`` と同じくFalse。
    """
    ...


class _OwnedCurve(om2.MFnNurbsCurve):
    """メモリ内の形状データ(``data``)を保持する ``om2.MFnNurbsCurve``。"""

def _require_count(value: int) -> int:
    """点の数を検証する。

    Args:
        value (int): 点の数。boolは受け付けない。

    Returns:
        int: 検証済みの点の数。

    Raises:
        TypeError: int以外(boolを含む)の場合。
        ValueError: 1未満の場合。
    """
    ...

def _require_axis(value: str, name: str) -> tuple[int, float]:
    """軸の名前を検証する。

    Args:
        value (str): "x"・"y"・"z"・"-x"・"-y"・"-z" のいずれか。
        name (str): 例外メッセージに使う引数名。

    Returns:
        tuple[int, float]: 軸番号(0〜2)と符号。

    Raises:
        TypeError: str以外の場合。
        ValueError: 未対応の名前の場合。
    """
    ...

def _perpendicular(vector: om2.MVector, aim: om2.MVector) -> om2.MVector | None:
    """vector から aim 方向の成分を除いて正規化する。

    Args:
        vector (om2.MVector): 元の方向。
        aim (om2.MVector): 正規化済みの基準方向。

    Returns:
        om2.MVector | None: aim に直交する単位ベクトル。平行で定義できない場合は None。
    """
    ...

def _initial_up(aim: om2.MVector) -> om2.MVector:
    """平行移動の最初の上方向を、aim に最も直交する主軸から作る。

    Args:
        aim (om2.MVector): 正規化済みの最初の接線。

    Returns:
        om2.MVector: aim に直交する単位ベクトル。同程度なら Y→Z→X の順に選ぶ。
    """
    ...

def _transport(up: om2.MVector, start: om2.MPoint, end: om2.MPoint, start_aim: om2.MVector, end_aim: om2.MVector) -> om2.MVector:
    """二重反射法(rotation minimizing frame)で上方向を次の点へ運ぶ。

    Args:
        up (om2.MVector): start での上方向(start_aim に直交する単位ベクトル)。
        start (om2.MPoint): 現在の点。
        end (om2.MPoint): 次の点。
        start_aim (om2.MVector): 現在の点の単位接線。
        end_aim (om2.MVector): 次の点の単位接線。

    Returns:
        om2.MVector: end_aim に直交する単位ベクトル。
    """
    ...

def _fill_missing(values: list[object | None]) -> list[object] | None:
    """None の要素を直前の値(先頭は最初の有効な値)で埋める。

    Args:
        values (list[object | None]): 埋める並び。

    Returns:
        list[object] | None: 埋めた新しい並び。有効な値が1つも無い場合は None。
    """
    ...

def _frame_matrix(position: om2.MPoint, aim: om2.MVector, up: om2.MVector, aim_axis: tuple[int, float], up_axis: tuple[int, float]) -> Matrix:
    """位置と直交する2方向からマトリクスを組む。

    Args:
        position (om2.MPoint): 平行移動。
        aim (om2.MVector): aim_axis へ向ける単位ベクトル。
        up (om2.MVector): up_axis へ向ける、aim に直交する単位ベクトル。
        aim_axis (tuple[int, float]): aim の軸番号と符号。
        up_axis (tuple[int, float]): up の軸番号と符号。

    Returns:
        Matrix: 行ベクトルの規約(各行が軸、4行目が位置)の右手系マトリクス。
    """
    ...


class NurbsCurve(Shape):
    """NURBSカーブのシェイプを扱うクラス。

    - 点を並べてカーブを作るときは :func:`mlib.createCurve <mlib.cmds.createCurve.createCurve>` を使う。
    - CVの位置をまとめて設定するときは :meth:`setCvPositions` を使う。
    - CV(:class:`~mlib.components.cv.CV`)のオブジェクトからも、座標を取得・編集できる。
    - 形を反転するときは :meth:`mirror` を使う。
    """
    def getCV(self, index: int) -> CV:
        """CVの番号から、CVを1つ取得する。

        Args:
            index (int): 0から始まるCVの番号。

        Returns:
            CV: シーン上のCVを指すオブジェクト。

        Raises:
            IndexError: CVの番号が範囲外の場合。
        """
        ...
    def getCVs(self, indices: Iterable[int] | None = ...) -> CVs:
        """複数のCVをまとめて取得する。

        番号は、渡した中で最初に出てきた順に並べる。

        Args:
            indices (Iterable[int] | None): OpenMayaのCVの番号。Noneなら、今あるすべてのCVを小さい順に取得する。
                空の並びを渡すと、空のまとまりになる。負の数とboolは受け付けない。

        Returns:
            CVs: CVをまとめた新しいオブジェクト。どのCVも同じShapeを使い、重なった番号は1つにまとめる。
                周期カーブの末尾で重なっているCVもOpenMayaの番号のまま持つ。ただしcmdsへ渡す名前では、
                対応する先頭側のCVの名前にする。
        """
        ...
    def mfn(self) -> om2.MFnNurbsCurve | om2.MFnDagNode:
        """このカーブに使えるOpenMayaのfunction setのうち、最も具体的なものを取得する。

        呼び出すたびに新しく作る。形状のデータを持っていれば ``om2.MFnNurbsCurve`` を返す。

        ``mlib.createNode("nurbsCurve")`` の直後のように、形状のデータを持たない空のシェイプでは
        ``om2.MFnNurbsCurve`` が使えない(Maya 2027では作るときにValueErrorになり、版によっては作った後の
        取得でRuntimeErrorになる)。その場合は ``om2.MFnDagNode`` を返す。
        DagNodeに共通の取得(中間オブジェクトかどうか・親の一覧など)は、空のシェイプでも使える。

        Returns:
            om2.MFnNurbsCurve | om2.MFnDagNode: このカーブの function set。空のシェイプでは MFnDagNode。

        Raises:
            RuntimeError: このオブジェクトが持つDAGパスが無効な場合。
        """
        ...
    def getNumCVs(self) -> int:
        """CV 数を取得する。

        Returns:
            int: カーブの CV 数。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getNumSpans(self) -> int:
        """スパン数を取得する。

        Returns:
            int: カーブのスパン数。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getDegree(self) -> int:
        """カーブの次数を取得する。

        Returns:
            int: NURBS カーブの次数。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getForm(self) -> int:
        """カーブの形式(開いているか閉じているか)を取得する。

        Returns:
            int: MFnNurbsCurve の kOpen、kClosed、kPeriodic のいずれか。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getKnots(self) -> list[float]:
        """ノットの並びを取得する(``MFnNurbsCurve.knots``)。

        Returns:
            list[float]: Mayaの形式のノットの並び。長さは ``getNumCVs() + getDegree() - 1`` になる。
                両端の2つを省いた形で、``cmds.curve(knot=...)`` へそのまま渡せる。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def isPlanar(self) -> bool:
        """カーブが1つの平面の上にあるか調べる。

        平面かどうかはトランスフォームで変わらないため、空間は指定しない。
        判定は ``MFnNurbsCurve.isPlanar`` と同じく、CVの外れが0.001cm以下なら平面とみなす。
        点が一直線上にあるカーブは、平面が決まらないためFalseになる。
        ``MFnNurbsCurve.isPlanar`` そのものは呼ばない(Maya 2023で、その後の長さの計算がずれる不具合があるため)。

        Returns:
            bool: 平面上にあればTrue。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getLength(self, tolerance: float = ..., *, worldSpace: bool = ..., unit: str | None = ..., ws: bool = ...) -> float:
        """カーブの長さを取得する。

        計算用のノードをシーンに作らない。

        Args:
            tolerance (float): 長さを計算するときの許容誤差。内部の距離単位で、正の有限な値を指定する。
            worldSpace (bool): Trueはワールド空間、Falseはローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            unit (str | None): 返す値の単位。既定はcm。Noneなら、今のUIの距離単位。
                mm/cm/m/km/in/ft/yd/mi、またはMayaのロング名で指定する。

        Returns:
            float: 指定した単位での長さ。単位を省いたときはcm。
                worldSpace=Trueでは、親の非均等スケール・シアーと、インスタンスのトランスフォームも反映する。

        Raises:
            TypeError: 単位の型が不正な場合、worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: toleranceが正の有限な値でない場合、または単位の名前が対応していない場合。
            RuntimeError: カーブが無効な場合、またはMayaが評価を拒否した場合。
        """
        ...
    def getArea(self, worldSpace: bool = ..., *, ws: bool = ...) -> float:
        """閉じた平面カーブが囲む面積を取得する。

        計算用のノードをシーンに作らない。``MFnNurbsCurve.area`` は版によって値を返さないため、
        カーブに沿った線積分(``1/2 ∮ P × dP`` の長さ)を、ノットの区間ごとにガウス・ルジャンドル則で求める。
        自分自身と交差するカーブでは、向きの付いた面積を足し合わせた値になる。

        Args:
            worldSpace (bool): Trueはワールド空間(親のスケールを含む)、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 面積(cm²)。

        Raises:
            TypeError: worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            ValueError: カーブが閉じていない場合(開いた形式で、始点と終点が離れている)、
                またはカーブが平面の上に無い場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getCvPositions(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """CVの位置を取得する。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[Vector]: CVの順の位置(:class:`~mlib.maths.vector.Vector`)。距離はMaya APIの
                内部単位(cm)。有理カーブのウェイト(w)は含まず、wで割らないXYZを返す。
                そのまま :meth:`setCvPositions` へ渡せる。

        Raises:
            TypeError: worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def setCvPositions(self, points: Iterable[Sequence[float] | om2.MPoint | om2.MVector], worldSpace: bool = ..., *, fast: bool = ..., ws: bool = ...) -> NurbsCurve:
        """全CVの位置をまとめて設定する。

        :meth:`getCvPositions` と同じ並び・単位(内部単位のcm)の点を受け付ける。

        - 通常: ``cmds.xform`` で書き込み、1回のUndoにまとめる。
        - ``fast=True``: ``MFnNurbsCurve.setCVPositions`` で全CVを一度に書き込む。Undoには記録しない。

        CVの数・次数・ノット・ウェイトは変更しない。周期カーブでは、次のどちらかの数の点を受け付ける。

        - 重なっていないCVの数(``getNumCVs() - getDegree()``)。
        - 末尾の重なったCVも含む ``getNumCVs()`` 個。重なったCVには、対応する先頭のCVと同じ位置を渡す。

        Args:
            points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): CVの順の位置。各点は
                有限な数値3つ。MPointはwで割らずにXYZを使う。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            NurbsCurve: 自身。

        Raises:
            TypeError: worldSpace・fastがbool以外の場合、点の型や成分が不正な場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: 点の数がCVの数と合わない場合、成分が有限でない場合、周期カーブの重なったCVが
                先頭のCVと一致しない場合、またはworldSpace=Trueでトランスフォームのマトリクスが特異な場合。
            RuntimeError: 形状のデータが無いか無効なシェイプの場合、またはロックなどでMayaが書込みを拒否した場合。
            NotImplementedError: fast=Trueで、createへの入力(コンストラクションヒストリ)がある場合。
        """
        ...
    def mirror(self, axis: str | int = ..., worldSpace: bool = ..., pivot: Iterable[float] = ..., indices: Iterable[int] | None = ..., *, fast: bool = ..., ws: bool = ...) -> NurbsCurve:
        """CVの座標を、中心pivotに対して反転する。

        反転後の座標は ``2 * pivot - 今の座標`` になる。

        - Transform・次数・ノット・CVの順番とウェイト(w)は変更しない。
        - Shapeを共有しているインスタンスすべてに反映される。複製や、パラメーターの向きの反転はしない。
        - 全CVの座標を先に読んでから書くので、周期カーブの末尾の重なったCVを二重に反転しない
          (重なったCVは、先頭側の対応するCVと同じ位置にそろう)。
        - 入力をすべて確かめてから書き込む。通常は ``cmds.xform`` をCVごとに呼び、1回のUndoにまとめる。
          ``fast=True`` では ``MFnNurbsCurve.setCVPositions`` で全CVを一度に書く。

        Args:
            axis (str | int): 反転する軸 ``"x"``・``"y"``・``"z"``、またはミラー面 ``"YZ"``・``"XZ"``・``"XY"``
                (x⇔YZ、y⇔XZ、z⇔XY。文字の順序・大文字小文字は問わない)、または0/1/2。
            worldSpace (bool): Trueなら、このオブジェクトが持つDAGパスのワールド空間で反転する。
                FalseならShapeのオブジェクト空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 反転の中心のXYZ(cm)。worldSpaceで選んだ空間で指定する。
                既定は原点で、Transformのピボットとは関係しない。
            indices (Iterable[int] | None): OpenMayaのCVの番号。Noneなら全CV。空の並びなら何も変えない。
                同じ番号は1回だけ処理する。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            NurbsCurve: 自身。

        Raises:
            TypeError: worldSpace・fastがbool以外の場合、axisが文字列・int以外の場合、番号の型が不正な場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: axisやpivotが不正な場合、またはworldSpace=Trueでトランスフォームのマトリクスがほぼ特異な場合。
            IndexError: CVの番号が負か範囲外の場合。
            RuntimeError: 形状のデータが無いか無効なシェイプの場合、またはロックなどでMayaが書込みを拒否した場合。
            NotImplementedError: fast=Trueで、createへの入力(コンストラクションヒストリ)がある場合。
        """
        ...
    def rebuild(self, spans: int | None = ..., degree: int | None = ..., *, keepRange: str = ...) -> NurbsCurve:
        """カーブを均等なスパンで作り直す(``cmds.rebuildCurve`` のuniform)。

        ``cmds.rebuildCurve(constructionHistory=False, replaceOriginal=True)`` で、このシェイプの形状を
        置き換える。1回のUndoで戻せる。シェイプのノードと選択は変わらない。両端の位置は保つ。

        - コンストラクションヒストリのあるカーブでは、上流が再評価されて形状が元に戻ることがある。
        - スパンの数と次数は ``cmds.rebuildCurve`` の結果のとおりになる。指定と違うことがある
          (Maya 2027では、次数1・spans=2で4スパンになるなど)。

        Args:
            spans (int | None): 新しいスパンの数。1以上。Noneなら今のスパンの数。
            degree (int | None): 新しい次数。1・2・3・5・7のいずれか。Noneなら今の次数。
            keepRange (str): パラメーターの範囲。``"original"`` は元の範囲(既定)、``"unit"`` は0〜1、
                ``"spans"`` は0〜スパンの数。

        Returns:
            NurbsCurve: 自身。

        Raises:
            TypeError: spans・degreeがint・None以外(boolを含む)の場合、またはkeepRangeがstr以外の場合。
            ValueError: spansが1未満の場合、degreeが対応していない値の場合、またはkeepRangeが対応していない名前の場合。
            RuntimeError: 形状のデータを持たない空のシェイプの場合、またはロックなどでMayaが書込みを拒否した場合。
        """
        ...
    def reverse(self) -> NurbsCurve:
        """カーブの向き(パラメーターが増える向き)を反転する(``cmds.reverseCurve``)。

        ``cmds.reverseCurve(constructionHistory=False, replaceOriginal=True)`` で、このシェイプの形状を
        置き換える。1回のUndoで戻せる。形の位置は変わらず、CVの並びだけが逆になる。
        シェイプのノードと選択は変わらない。

        Returns:
            NurbsCurve: 自身。

        Raises:
            RuntimeError: 形状のデータを持たない空のシェイプの場合、またはロックなどでMayaが書込みを拒否した場合。
        """
        ...
    def getCollocatedCVGroups(self, tolerance: float = ..., worldSpace: bool = ..., *, ws: bool = ...) -> list[list[int]]:
        """ほぼ同じ位置にあるCVを、グループに分けて取得する。

        周期カーブで重なっているCVを調べるときや、整理する前のカーブを確かめるときなどに使う。

        Args:
            tolerance (float): 同じ位置とみなす距離の許容誤差(Maya APIの内部の距離単位)。正の値を指定する。
            worldSpace (bool): Trueはワールド空間、Falseはローカル空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[list[int]]: 2個以上のCVが重なっているグループだけを返す。グループの中は番号の小さい順、
                グループどうしは先頭の番号の小さい順に並ぶ。ほかと重なっていないCVは含まない。

        Raises:
            TypeError: worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            ValueError: toleranceが正の値でない場合。
        """
        ...
    def getParamRange(self) -> tuple[float, float]:
        """パラメーターの範囲(``MFnNurbsCurve.knotDomain``)を取得する。

        Returns:
            tuple[float, float]: 最小と最大のパラメーター。``minValue``・``maxValue`` アトリビュートと同じ値。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getClosestPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, ws: bool = ...) -> tuple[Vector, float]:
        """指定した位置に最も近い、カーブ上の点とパラメーターを取得する。

        ``nearestPointOnCurve`` ノードの ``result.position``・``result.parameter`` にあたる。
        計算用のノードをシーンに作らない。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 位置(cm)。worldSpaceと同じ空間で指定する。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            tuple[Vector, float]: 最も近い点(cm)とパラメーター。

        Raises:
            TypeError: 点の型や成分が不正な場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 成分の数が3でない場合、または有限でない場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getPointAtParam(self, param: float, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
        """パラメーターの位置を取得する。

        Args:
            param (float): :meth:`getParamRange` の範囲内のパラメーター。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 位置(cm)。``pointOnCurveInfo`` の ``position`` と同じ。

        Raises:
            TypeError: paramが数値でない、worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            ValueError: paramが有限でない、または範囲外の場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getTangentAtParam(self, param: float, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
        """パラメーターの位置の接線を、長さ1にして取得する。

        Args:
            param (float): :meth:`getParamRange` の範囲内のパラメーター。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: パラメーターが増える向きの、長さ1のベクトル。``pointOnCurveInfo`` の ``normalizedTangent`` と同じ。

        Raises:
            TypeError: paramが数値でない、worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            ValueError: paramが有限でないか範囲外の場合、または重なったCVで接線が0になる位置の場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getNormalAtParam(self, param: float, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
        """パラメーターの位置の法線を、長さ1にして取得する(``MFnNurbsCurve.normal``)。

        - 次数2以上: 曲がっていく向き(主法線)。
        - 次数1: CVの平均の平面の中で、接線に直交する向き。

        ``pointOnCurveInfo`` の ``normalizedNormal`` と同じ。

        Args:
            param (float): :meth:`getParamRange` の範囲内のパラメーター。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 長さ1のベクトル。

        Raises:
            TypeError: paramが数値でない、worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            ValueError: paramが有限でないか範囲外の場合、または法線を決められない場合。
                法線を決められないのは、次数2以上で曲率が0の位置(まっすぐな部分・変曲点)と、
                次数1でCVがすべて一直線上にある場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getLengthAtParam(self, param: float, worldSpace: bool = ..., *, unit: str | None = ..., ws: bool = ...) -> float:
        """カーブの始点から、パラメーターの位置までの長さを取得する。

        ``arcLengthDimension`` の ``arcLength`` にあたる。計算用のノードをシーンに作らない。

        Args:
            param (float): :meth:`getParamRange` の範囲内のパラメーター。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            unit (str | None): 返す値の単位。既定はcm。Noneなら、今のUIの距離単位。指定のしかたは :meth:`getLength` と同じ。

        Returns:
            float: 指定した単位での長さ。

        Raises:
            TypeError: paramが数値でない場合、worldSpaceがbool以外の場合、単位の型が不正な場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: paramが有限でないか範囲外の場合、または単位の名前が対応していない場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getParamAtLength(self, length: float, worldSpace: bool = ..., *, unit: str | None = ..., ws: bool = ...) -> float:
        """カーブの始点からの長さにあたる、パラメーターを取得する。

        Args:
            length (float): 始点からの長さ。0から全長(:meth:`getLength`)までで、単位はunit。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
                ワールド空間の長さには、親の非均等スケールも反映する。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            unit (str | None): lengthの単位。既定はcm。Noneなら、今のUIの距離単位。指定のしかたは :meth:`getLength` と同じ。

        Returns:
            float: パラメーター。0は始点、全長は終点のパラメーター。

        Raises:
            TypeError: lengthが数値でない場合、worldSpaceがbool以外の場合、単位の型が不正な場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: lengthが有限でないか、0未満か、全長を超える場合、または単位の名前が対応していない場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getParamsAlong(self, count: int, worldSpace: bool = ..., *, ws: bool = ...) -> list[float]:
        """カーブに沿った長さで、等間隔に並ぶパラメーターを取得する。

        - 開いたカーブ(``getForm()`` がkOpen): 両端を含む。間隔は 全長/(count-1)。
        - 閉じたカーブ・周期カーブ(kClosed・kPeriodic): 終点は始点と重なるので含めない。
          始点から 全長/count の間隔で、count個の別々の点を返す。
        - count=1: 始点だけ。

        Args:
            count (int): 点の数。1以上。
            worldSpace (bool): Trueならワールド空間での長さで、Falseならローカル(オブジェクト)空間での長さで等分する。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[float]: 始点から順のパラメーター。

        Raises:
            TypeError: countがint以外(boolを含む)の場合、worldSpaceがbool以外の場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: countが1未満の場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getMatricesAlong(self, count: int, up: Sequence[float] | om2.MVector | None = ..., *, aimAxis: str = ..., upAxis: str = ..., worldSpace: bool = ..., ws: bool = ...) -> list[Matrix]:
        """カーブに沿って等間隔に並ぶ点の向きを、マトリクスで取得する。

        各点で、aimAxisの軸を接線へ向けたマトリクスを返す。点の並びは :meth:`getParamsAlong` と同じ。
        マトリクスは正規直交の右手系(スケール1)で、移動はカーブ上の位置(cm)。
        upAxisの向きは、upの指定によって次のように決まる。

        - ``up`` を指定した場合: 各点で、upから接線方向の成分を除いた向きへupAxisを向ける。
          接線と平行で向きを決められない点では、直前の点の向きを使う(先頭なら、最初に向きを決められた点の向き)。
        - ``None`` の場合: 最初の点の向きを、ねじれを加えずにカーブに沿って運ぶ
          (二重反射法によるrotation minimizing frame)。最初の点のupAxisは、最初の接線に最も直交する
          主軸(同じくらいならY→Z→Xの順)を、接線に直交させた向きになる。点の間を細かく分けて運ぶので、
          countが少なくても向きは変わらない。閉じたカーブでは、一周した後の向きが最初と一致するとは
          限らない(ねじれをならす処理はしない)。

        重なったCVで接線が0になる点では、直前の点の接線を使う(先頭なら次の点の接線)。

        Args:
            count (int): 点の数。1以上。
            up (Sequence[float] | om2.MVector | None): upAxisを向ける方向。worldSpaceと同じ空間で指定する。
            aimAxis (str): 接線へ向ける軸。"x"・"y"・"z"・"-x"・"-y"・"-z"。
            upAxis (str): upへ向ける軸。aimAxisとは別の軸を指定する。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[Matrix]: 始点から順のマトリクス。

        Raises:
            TypeError: countがint以外(boolを含む)の場合、upの型や成分が不正な場合、aimAxis・upAxisがstr以外の場合、
                worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: countが1未満の場合、upの成分が有限でないか長さが0の場合、
                軸の名前が対応していないかaimAxisとupAxisが同じ軸の場合、upがすべての点で接線と平行な場合、
                またはすべての点で接線が0の場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def _space_curve(self, worldSpace: bool) -> om2.MFnNurbsCurve:
        """指定空間の形状をオブジェクト空間で照会できる ``om2.MFnNurbsCurve`` を返す。

        ワールド空間はメモリ内のコピーのCVだけをワールド座標へ変換する。弧長などオブジェクト空間でしか
        計算できない照会や、非均等スケール下の法線も、変換後の形状として一貫して求められる。
        元のCV・履歴・Undoキューは変更しない。copyにより次数・ノット・有理カーブのウェイトも維持する。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはローカル空間。

        Returns:
            om2.MFnNurbsCurve: kObject で照会する function set。

        Raises:
            TypeError: worldSpaceがbool以外の場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    @staticmethod
    def _unit_factor(unit: str | None) -> float:
        """cmから指定した距離単位への係数を返す。

        Args:
            unit (str | None): 距離単位。Noneは現在の距離UI単位。

        Returns:
            float: 1cmを指定単位で表した値。

        Raises:
            TypeError: 単位の型が不正な場合。
            ValueError: 単位名が未対応の場合。
        """
        ...
    @staticmethod
    def _require_param(curve: om2.MFnNurbsCurve, param: float) -> float:
        """パラメーターを検証し、範囲の端へ丸め込んだfloatを返す。

        Args:
            curve (om2.MFnNurbsCurve): 照会するカーブ。
            param (float): パラメーター。範囲外は端からの相対1e-9までを許す。

        Returns:
            float: 検証済みのパラメーター。

        Raises:
            TypeError: 数値でない場合。
            ValueError: 有限でない、または範囲外の場合。
        """
        ...
    @staticmethod
    def _tangent(curve: om2.MFnNurbsCurve, param: float) -> om2.MVector | None:
        """正規化した接線を返す。

        Args:
            curve (om2.MFnNurbsCurve): 照会するカーブ。
            param (float): 検証済みのパラメーター。

        Returns:
            om2.MVector | None: 単位ベクトル。接線が0の位置は None。
        """
        ...
    @staticmethod
    def _param_at_length(curve: om2.MFnNurbsCurve, length: float, total: float) -> float:
        """弧長を検証し、対応するパラメーターを返す。

        Args:
            curve (om2.MFnNurbsCurve): 照会するカーブ。
            length (float): cmの弧長。
            total (float): カーブの全長(cm)。

        Returns:
            float: パラメーター。

        Raises:
            ValueError: 0未満、または全長を超える場合(相対1e-6までは端へ丸める)。
        """
        ...
    def _params_along(self, curve: om2.MFnNurbsCurve, count: int) -> list[float]:
        """弧長で等間隔のパラメーターを返す(:meth:`getParamsAlong` の本体)。

        Args:
            curve (om2.MFnNurbsCurve): 照会するカーブ。
            count (int): 検証済みの点の数。

        Returns:
            list[float]: 始点から順のパラメーター。
        """
        ...
    def _transported_ups(self, curve: om2.MFnNurbsCurve, params: list[float], aims: list[om2.MVector]) -> list[om2.MVector]:
        """平行移動で運んだ各点の上方向を返す。

        Args:
            curve (om2.MFnNurbsCurve): 照会するカーブ。
            params (list[float]): 出力する点のパラメーター。
            aims (list[om2.MVector]): 各点の単位接線。

        Returns:
            list[om2.MVector]: 各点の、接線に直交する単位ベクトル。
        """
        ...
    def _mirror_plan(self, axis: str | int, ws: bool, pivot: Iterable[float], indices: Iterable[int] | None, fast: bool) -> tuple | None:
        """CVを反転した座標を求め、書込みの計画を返す。シーンは変更しない。

        :meth:`Transform.mirrorGeometry <mlib.nodes.transform.Transform.mirrorGeometry>` が
        全Shapeを検証してから書き込むために使う。

        Args:
            axis (str | int): 反転する軸またはミラー面。
            ws (bool): Trueならワールド空間。検証済み。
            pivot (Iterable[float]): 指定空間の反転中心XYZ(cm)。
            indices (Iterable[int] | None): CV番号。Noneは全CV。
            fast (bool): TrueならOpenMayaで直接書けるかも確かめる。

        Returns:
            tuple | None: ``(shape, indices, rows, ws)``。対象が無ければNone。
        """
        ...
    def _geometry_fn(self) -> om2.MFnNurbsCurve:
        """形状データを要する照会用に ``om2.MFnNurbsCurve`` を返す。

        Returns:
            om2.MFnNurbsCurve: このカーブの function set。

        Raises:
            RuntimeError: 保持する DAG パスが無効、または形状データを持たない空のシェイプの場合。
        """
        ...
