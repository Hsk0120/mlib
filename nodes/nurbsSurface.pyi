# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""MayaのNURBS曲面シェイプを扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..components.surfaceCV import SurfaceCV, SurfaceCVs
from ..core import geometryEdit
from ..core.fastWrite import require_writable
from ..decorator import _edit_context, _pick_alias, _require_bool
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _checked_tolerance, _finite, _world_space
from .node import Node, Nodes
from .nurbsCurve import _DEGENERATE, _frame_matrix, _perpendicular, _require_axis
from .shape import Shape
from typing import Iterable, Sequence
from mlib.maths.matrix import Matrix
from mlib.nodes.shadingEngine import ShadingEngine



class NurbsSurface(Shape):
    """NURBS曲面のシェイプを扱うクラス。

    アトリビュートや親のTransformの操作はShapeから受け継ぐ。

    CVの番号は ``cv[u][v]`` の (u, v) で表す。:meth:`getCvPositions` などが返すCVの並びは、
    Uを外側・Vを内側にした ``u * numCVsInV + v`` の順になる(``om2.MFnNurbsSurface.cvPositions`` と同じ)。
    距離はMayaの内部単位(cm)。
    """
    def isBezier(self) -> bool:
        """曲面のノット配置がBezier形式か調べる。

        Returns:
            bool: Bezier形式ならTrue。

        Raises:
            RuntimeError: 曲面が無効、または形状データがない場合。
        """
        ...
    def isUniform(self) -> bool:
        """曲面のノット間隔が一様か調べる。

        Returns:
            bool: 一様ならTrue。

        Raises:
            RuntimeError: 曲面が無効、または形状データがない場合。
        """
        ...
    def isFoldedOnBispan(self) -> bool:
        """曲面のパッチ境界に折返しや折れ目があるか調べる。

        MFnNurbsSurfaceの判定を返す。トリムされた領域も含む。

        Returns:
            bool: 折返しや折れ目があればTrue。

        Raises:
            RuntimeError: 曲面が無効、または形状データがない場合。
        """
        ...
    def mfn(self) -> om2.MFnNurbsSurface | om2.MFnDagNode:
        """この曲面のOpenMayaのfunction setを取得する。

        呼び出すたびに新しく作る。形状のデータを持たない空のシェイプ
        (``mlib.createNode("nurbsSurface")`` の直後など)では ``om2.MFnNurbsSurface`` が使えない。
        その場合は ``om2.MFnDagNode`` を返す。

        Returns:
            om2.MFnNurbsSurface | om2.MFnDagNode: この曲面の function set。空のシェイプでは MFnDagNode。

        Raises:
            RuntimeError: このオブジェクトが持つDAGパスが無効な場合。
        """
        ...
    def getNumCVs(self) -> tuple[int, int]:
        """U・V方向のCVの数を取得する。

        周期曲面では、重なっているCVも数に含む。

        Returns:
            tuple[int, int]: (U方向のCV数, V方向のCV数)。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getNumSpans(self) -> tuple[int, int]:
        """U・V方向のスパン数を取得する。

        Returns:
            tuple[int, int]: (U方向のスパン数, V方向のスパン数)。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getNumPatches(self) -> tuple[int, int]:
        """U・V方向の幅が0でないパッチ数を取得する。

        重複ノットによる幅0のスパンを除く。全パッチ数は返された2値の積で求める。

        Returns:
            tuple[int, int]: U方向・V方向のパッチ数。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getDegree(self) -> tuple[int, int]:
        """U・V方向の次数を取得する。

        Returns:
            tuple[int, int]: (U方向の次数, V方向の次数)。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getForm(self) -> tuple[int, int]:
        """U・V方向の形式(開いているか閉じているか)を取得する。

        Returns:
            tuple[int, int]: U・Vの順の形式。それぞれ ``om2.MFnNurbsSurface`` の kOpen・kClosed・kPeriodic のいずれか。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getParamRange(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """U・Vのパラメーターの範囲(``MFnNurbsSurface.knotDomainInU/V``)を取得する。

        Returns:
            tuple[tuple[float, float], tuple[float, float]]: ((U の最小, U の最大), (V の最小, V の最大))。
                ``minMaxRangeU``・``minMaxRangeV`` アトリビュートと同じ値。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getKnots(self) -> tuple[list[float], list[float]]:
        """U方向・V方向のノット列を取得する。

        Returns:
            tuple[list[float], list[float]]: U・Vの順の独立したリスト。OpenMayaと同じく両端の余分なノットを含めない。

        Raises:
            RuntimeError: 形状が無効な場合。
        """
        ...
    def setKnots(self, uKnots: Iterable[float], vKnots: Iterable[float]) -> None:
        """曲面のU・Vのノット値を変更する。

        ノット数・次数・CVは変えない。ヒストリ、トリム、明示テクスチャUV、参照、CVのロック・接続がある曲面は拒否する。
        独立したデータで検証してから、cmds.setAttrで曲面データを更新する。
        fast引数は持たない(1回のcmdsで両方向を更新するため)。

        Args:
            uKnots (Iterable[float]): U方向のノット列。既存と同じ数の非減少列。
            vKnots (Iterable[float]): V方向のノット列。既存と同じ数の非減少列。

        Returns:
            None: 値を返さない。

        Raises:
            ValueError: 値が有限値でない、数や順序が不正、またはパラメーター範囲が潰れる場合。
            RuntimeError: 曲面が無効、ロックされている、またはMayaが編集を拒否した場合。
            NotImplementedError: ヒストリ・トリム・明示UV・参照・CVロックや接続がある場合。
        """
        ...
    def removeKnot(self, parameter: float, direction: str = ..., *, all: bool = ...) -> None:
        """曲面の内側のノットを削除する。

        指定方向が開いた曲面だけを扱う。形状とCV数が変わる場合がある。
        setKnotsと同じくヒストリ・トリム・明示UV・参照・CVのロックや接続は拒否する。
        fast引数は持たない(独立コピーで編集し、1回のcmdsで更新するため)。

        Args:
            parameter (float): 削除する内側のノットのパラメーター値。
            direction (str): "u"または"v"。既定"u"。
            all (bool): Trueなら同じ値のノットをすべて、Falseなら1つ削除する。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: allがbool以外の場合。
            ValueError: 方向が不正、値が非有限、内側のノットでない場合。
            RuntimeError: 曲面が無効、ロックされている、またはMayaが編集を拒否した場合。
            NotImplementedError: 指定方向が閉じている、またはsetKnotsの未対応条件に当たる場合。
        """
        ...
    def getPatchShaders(self) -> tuple[Nodes[ShadingEngine], list[int]]:
        """保持するインスタンスのパッチごとのシェーディンググループを取得する。

        Returns:
            tuple[Nodes[ShadingEngine], list[int]]: グループ一覧と、パッチごとの一覧内の番号。未割当は-1。

        Raises:
            RuntimeError: 曲面の形状データやDAGパスが無効な場合。
        """
        ...
    def getUVData(self) -> tuple[list[tuple[float, float]], list[int], list[int]]:
        """明示的に設定されたテクスチャUVと、パッチへの割り当てを取得する。

        曲面のパラメーター(u, v)とは別の値。Mayaが既定で使うUVから、明示UVを生成する処理は行わない。

        Returns:
            tuple[list[tuple[float, float]], list[int], list[int]]: UV番号順の(U, V)、パッチ番号順のUV数、
                パッチのコーナー順に連結したUV番号。未割当パッチの数は0。すべて独立した値。

        Raises:
            RuntimeError: 明示的なUVデータが無いか、形状データが無効な場合。
        """
        ...
    def setUVData(self, uvs: Iterable[Iterable[float]], counts: Iterable[int], indices: Iterable[int], *, fast: bool = ...) -> None:
        """曲面の明示テクスチャUVとパッチへの割り当てを置き換える。

        getUVDataと同じ並び順。曲面パラメーターとは別のUVを設定する。既存UV数の縮小には対応しない。
        fast=True専用でUndoには記録しない。ヒストリ・参照・トリム曲面は拒否する。
        事前検査後にUV表と割当表を順に書くため、Mayaの更新失敗時の原子性は保証しない。

        Args:
            uvs (Iterable[Iterable[float]]): UV番号順の(U, V)。空の表と既存UV表の縮小は未対応。
            counts (Iterable[int]): パッチ番号順の割当数。各値は0または4。
            indices (Iterable[int]): コーナー順のUV番号。長さはcountsの合計。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 型が不正な場合。
            ValueError: リストの長さ・UV番号・UV座標が不正な場合。
            RuntimeError: 曲面が無効、ロック、またはUVアトリビュートが編集不可の場合。
            NotImplementedError: fast=False、ヒストリ・参照・トリム曲面、または既存UV表の縮小の場合。
        """
        ...
    def clearUVData(self) -> None:
        """曲面の明示テクスチャUV表とパッチへの割り当てを消去する。

        同じShapeへCV・ノット・次数・形式を書き戻し、Mayaの既定UVを使う状態へ戻す。
        消去後のgetUVDataはRuntimeErrorになる。Shapeの削除・再作成は行わない。
        ヒストリ・参照・トリム・インスタンス・コンポーネントタグ・複数UVセットを持つ曲面や、
        CV/UVアトリビュートが編集できない曲面は拒否する。
        通常Undoに対応する。fast引数は持たない(形状データを1回のcmds.setAttrで書くため)。

        Returns:
            None: 値を返さない。明示UVがない場合は何も変更しない。

        Raises:
            RuntimeError: 曲面が無効、ロック、またはCV/UVアトリビュートが編集不可の場合。
            NotImplementedError: 曲面の編集状態が対応条件を満たさない場合。
        """
        ...
    def getTrimBoundaryInfo(self) -> list[list[tuple[int, int]]]:
        """トリム領域ごとの境界の種類とエッジ数を取得する。

        境界カーブやシーンのノードは作らない。領域番号・境界番号は編集後も維持されるIDではない。

        Returns:
            list[list[tuple[int, int]]]: 外側の位置が領域番号、内側の位置が境界番号。
                各境界は(種類, エッジ数)。種類はMFnNurbsSurfaceのkOuter・kInner・kSegment・kClosedSegment等。
                未トリム曲面では領域0の境界が空になる。すべて独立した値。

        Raises:
            RuntimeError: 形状データが無いか無効な曲面の場合。
        """
        ...
    def getTrimBoundaryCurveData(self, region: int, boundary: int, edge: int, *, parametric: bool = ...) -> list[dict]:
        """トリム境界の1エッジを構成するカーブのデータを取得する。

        シーンにカーブを作らず、値の独立コピーを返す。境界エッジが複数カーブからなる場合は
        Mayaの順に並ぶ。閉じた曲面の極など、3Dエッジが長さ0なら空になる場合がある。

        Args:
            region (int): トリム領域番号。
            boundary (int): 領域内の境界番号。
            edge (int): 境界内のエッジ番号。
            parametric (bool): Trueなら曲面パラメーター上の2Dカーブ、Falseなら3Dカーブ。既定False。

        Returns:
            list[dict]: 各カーブのdegree(int)、form(MFnNurbsCurveの定数)、knots(list[float])、
                cvs(list[tuple[float, float, float, float]])。CVはMPointの(x, y, z, w)成分。
                3Dカーブは曲面のオブジェクト空間(cm)、2Dカーブは曲面パラメーター空間。

        Raises:
            TypeError: 番号が整数でない、またはparametricがboolでない場合。
            IndexError: 領域・境界・エッジ番号が範囲外の場合。
            RuntimeError: 曲面が無効、またはMayaが境界の取得を拒否した場合。
        """
        ...
    def isTrimNormalFlipped(self, region: int) -> bool:
        """指定したトリム領域の法線方向が反転しているか調べる。

        Args:
            region (int): トリム領域番号。

        Returns:
            bool: Mayaが反転ありと判定した場合はTrue。

        Raises:
            TypeError: regionが整数でない場合。
            ValueError: 未トリムの曲面の場合。
            IndexError: regionが範囲外の場合。
            RuntimeError: 曲面が無効な場合。
        """
        ...
    def isTrimmed(self) -> bool:
        """トリム境界を持つ曲面か判定する。

        Returns:
            bool: トリムされた曲面ならTrue。

        Raises:
            RuntimeError: 形状が無効な場合。
        """
        ...
    def isPointInTrimmedRegion(self, u: float, v: float) -> bool:
        """指定パラメーターがトリムで切り落とされた領域か判定する。

        Args:
            u (float): U方向のパラメーター。
            v (float): V方向のパラメーター。

        Returns:
            bool: 切り落とされた領域ならTrue。残る領域はFalse。

        Raises:
            TypeError: u・vが数値以外の場合。
            ValueError: u・vが有限でないか範囲外の場合。
            RuntimeError: 形状が無効な場合。
        """
        ...
    def getRayIntersection(self, origin: Sequence[float], direction: Sequence[float], worldSpace: bool = ..., *, tolerance: float = ..., ws: bool = ...) -> tuple[Vector, float, float] | None:
        """レイと曲面の最も近い交点を取得する。

        トリムの扱いと許容誤差はMFnNurbsSurface.intersectに従う。

        Args:
            origin (Sequence[float]): レイの始点(cm)。worldSpaceと同じ空間。
            direction (Sequence[float]): レイの方向。ゼロ以外のベクトル。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            tolerance (float): 正の距離許容誤差(cm)。既定1e-6。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            tuple[Vector, float, float] | None: (交点(cm), u, v)。交差しなければNone。

        Raises:
            TypeError: 引数の型が不正か、worldSpaceとwsを同時に指定した場合。
            ValueError: 成分が有限でない、方向がゼロ、またはtoleranceが正でない場合。
            RuntimeError: 形状が無効な場合。
        """
        ...
    def getCV(self, u: int, v: int) -> SurfaceCV:
        """``(u, v)`` の番号から、CVを1つ取得する。

        Args:
            u (int): U方向のCV番号。
            v (int): V方向のCV番号。

        Returns:
            SurfaceCV: シーン上のCV(``cv[u][v]``)を指すオブジェクト。

        Raises:
            IndexError: CVの番号が範囲外の場合。
        """
        ...
    def getCVs(self, indices: Iterable[int | tuple[int, int]] | None = ...) -> SurfaceCVs:
        """複数のCVをまとめて取得する。

        Args:
            indices (Iterable[int | tuple[int, int]] | None): CVの番号。1つの通し番号か ``(u, v)`` で指定する。
                Noneなら、今あるすべてのCV。

        Returns:
            SurfaceCVs: CVをまとめたオブジェクト。どのCVも同じShapeを使う。重なった番号は1つにまとめる。
        """
        ...
    def getCvPositions(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """全CVの位置を取得する。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            list[Vector]: ``u * numCVsInV + v`` の順に並べた位置(cm)。有理曲面のウェイト(w)では割らない。
                そのまま :meth:`setCvPositions` へ渡せる。

        Raises:
            TypeError: worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def setCvPositions(self, points: Iterable[Sequence[float] | om2.MPoint | om2.MVector], worldSpace: bool = ..., *, fast: bool = ..., check: bool = ..., ws: bool = ...) -> None:
        """全CVの位置をまとめて設定する。

        :meth:`getCvPositions` と同じ並び・単位(cm)の点を受け付ける。

        - 通常: ``cmds.xform`` で書き込み、1回のUndoにまとめる。
        - ``fast=True``: ``MFnNurbsSurface.setCVPositions`` で一度に書き込む。Undoには記録しない。

        CVの数・次数・ノット・ウェイトは変更しない。周期曲面で重なっているCVには、対応する先頭のCVと
        同じ位置を渡す(違う位置を渡すと、後に書いた値になる)。

        Args:
            points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): CVの順の位置。各点は有限な数値3つ。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら、書き込む前に、書き込めるか(ロック・入力の接続が無いか)を確かめて、問題があれば何も書かずに例外にする。
                既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: worldSpace・fastがbool以外の場合、点の型や成分が不正な場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: 点の数がCVの数と合わない場合、成分が有限でない場合、
                またはworldSpace=Trueでトランスフォームのマトリクスが特異(逆マトリクスが無い)な場合。
            RuntimeError: 形状のデータが無いか無効なシェイプの場合、またはロックなどでMayaが書込みを拒否した場合。
            NotImplementedError: fast=Trueで、createへの入力(コンストラクションヒストリ)がある場合。
        """
        ...
    def isPointOnSurface(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, tolerance: float = ..., ws: bool = ...) -> bool:
        """指定点が許容誤差内でNURBS曲面上にあるか調べる。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 指定空間での位置(cm)。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            ws (bool): worldSpaceの短縮名。長名と同時指定できない。
            tolerance (float): 距離の許容誤差(cm)。0以上の有限値。

        Returns:
            bool: MFnNurbsSurface.isPointOnSurfaceの結果。

        Raises:
            TypeError: 点・空間・許容誤差の型が不正、または長短名を同時指定した場合。
            ValueError: 点が有限の3成分でない、または許容誤差が負か有限でない場合。
            RuntimeError: 形状が無効な場合。
        """
        ...
    def getClosestPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, ws: bool = ...) -> tuple[Vector, float, float]:
        """指定した位置に最も近い、曲面上の点とパラメーター (u, v) を取得する。

        ``closestPointOnSurface`` ノードの ``result.position``・``parameterU``・``parameterV`` にあたる。
        計算用のノードをシーンに作らない。follicleやuvPinの配置に使える。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 位置(cm)。worldSpaceと同じ空間で指定する。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            tuple[Vector, float, float]: 最も近い点(cm)と u・v のパラメーター。

        Raises:
            TypeError: 点の型や成分が不正な場合、worldSpaceがbool以外の場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 成分が有限でない場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getPointAtParam(self, u: float, v: float, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
        """パラメーター (u, v) の位置を取得する。

        Args:
            u (float): :meth:`getParamRange` の U の範囲内のパラメーター。
            v (float): :meth:`getParamRange` の V の範囲内のパラメーター。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 位置(cm)。``pointOnSurfaceInfo`` の ``position`` と同じ。

        Raises:
            TypeError: u・vが数値でない、worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            ValueError: u・vが有限でない、または範囲外の場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getDerivativesAtParam(self, u: float, v: float, worldSpace: bool = ..., *, secondOrder: bool = ..., ws: bool = ...) -> tuple[Vector, ...]:
        """曲面上の位置と、正規化前のU・V方向の微分を取得する。

        縮退点のゼロベクトルもそのまま返す。微分はパラメーターに対する変化量。

        Args:
            u (float): U方向のパラメーター。
            v (float): V方向のパラメーター。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            secondOrder (bool): Trueなら二次微分も返す。既定False。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            tuple[Vector, ...]: (位置, dU, dV)、または(位置, dU, dV, dUU, dVV, dUV)。位置はcm。

        Raises:
            TypeError: 引数の型が不正か、worldSpaceとwsを同時に指定した場合。
            ValueError: u・vが有限でないか範囲外の場合。
            RuntimeError: 形状が無効な場合。
        """
        ...
    def getNormalAtParam(self, u: float, v: float, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
        """パラメーター (u, v) の位置の法線を、長さ1にして取得する。

        Args:
            u (float): :meth:`getParamRange` の U の範囲内のパラメーター。
            v (float): :meth:`getParamRange` の V の範囲内のパラメーター。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 長さ1の法線。``pointOnSurfaceInfo`` の ``normalizedNormal`` と同じ向き。

        Raises:
            TypeError: u・vが数値でない、worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            ValueError: u・vが有限でないか範囲外の場合、または形がつぶれた位置で法線が0になる場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getTangentsAtParam(self, u: float, v: float, worldSpace: bool = ..., *, ws: bool = ...) -> tuple[Vector, Vector]:
        """パラメーター (u, v) の位置の、U方向とV方向の接線を長さ1にして取得する。

        Args:
            u (float): :meth:`getParamRange` の U の範囲内のパラメーター。
            v (float): :meth:`getParamRange` の V の範囲内のパラメーター。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            tuple[Vector, Vector]: U・Vのパラメーターが増える向きの、長さ1のベクトル。
                ``pointOnSurfaceInfo`` の ``normalizedTangentU``・``normalizedTangentV`` と同じ向き。
                互いに直交するとは限らない。

        Raises:
            TypeError: u・vが数値でない、worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            ValueError: u・vが有限でないか範囲外の場合、または重なったCVなどで接線が0になる位置の場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getMatrixAtParam(self, u: float, v: float, *, aimAxis: str = ..., upAxis: str = ..., worldSpace: bool = ..., ws: bool = ...) -> Matrix:
        """パラメーター (u, v) の位置の向きを、マトリクスで取得する。

        aimAxisの軸をU方向の接線へ、upAxisの軸を法線へ向けたマトリクスを返す。
        リボンの上にジョイントなどを並べるときに使う。

        - マトリクスは正規直交の右手系(スケール1)。移動は曲面上の位置(cm)。
        - upAxisは、法線から接線方向の成分を除いた向きになる。
        - 残りの軸は、aimAxisとupAxisから右手系で決まる。既定のx・yでは、zはおおむねV方向と同じ向きか逆向きになる。

        軸の指定のしかたは :meth:`NurbsCurve.getMatricesAlong <mlib.nodes.nurbsCurve.NurbsCurve.getMatricesAlong>` と同じ。

        Args:
            u (float): :meth:`getParamRange` の U の範囲内のパラメーター。
            v (float): :meth:`getParamRange` の V の範囲内のパラメーター。
            aimAxis (str): U方向の接線へ向ける軸。"x"・"y"・"z"・"-x"・"-y"・"-z"。
            upAxis (str): 法線へ向ける軸。aimAxisとは別の軸を指定する。
            worldSpace (bool): Trueはワールド空間、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Matrix: 行ベクトルの決まりのマトリクス(各行が軸、4行目が位置)。

        Raises:
            TypeError: u・vが数値でない場合、aimAxis・upAxisがstr以外の場合、worldSpaceがbool以外の場合、
                またはworldSpaceとwsを同時に指定した場合。
            ValueError: u・vが有限でないか範囲外の場合、軸の名前が対応していないかaimAxisとupAxisが同じ軸の場合、
                またはU方向の接線や法線が0か、互いに平行で向きを決められない場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def getArea(self, worldSpace: bool = ..., *, ws: bool = ...) -> float:
        """曲面の面積を取得する(``MFnNurbsSurface.area``)。

        計算用のノードをシーンに作らない。

        Args:
            worldSpace (bool): Trueはワールド空間(親のスケールを含む)、Falseはローカル(オブジェクト)空間。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 面積(cm²)。トリムされた曲面では、トリムした後の面積。

        Raises:
            TypeError: worldSpaceがbool以外、またはworldSpaceとwsを同時に指定した場合。
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        ...
    def _require_uv_edit(self):
        """UV更新の対応条件とUVアトリビュートの書き込み可否を確認する。"""
        ...
    @staticmethod
    def _require_trim_index(index, count, name):
        """Mayaへ渡す前に、トリム構成の0始まりの番号を検査する。"""
        ...
    @staticmethod
    def _require_params(fn: om2.MFnNurbsSurface, u: float, v: float) -> tuple[float, float]:
        """パラメーターを検証し、範囲の端へ丸め込んだ (u, v) を返す。

        Args:
            fn (om2.MFnNurbsSurface): 照会する曲面。
            u (float): Uのパラメーター。範囲外は端からの相対1e-9までを許す。
            v (float): Vのパラメーター。

        Returns:
            tuple[float, float]: 検証済みのパラメーター。

        Raises:
            TypeError: 数値でない場合。
            ValueError: 有限でない、または範囲外の場合。
        """
        ...
    def _tangents(self, fn: om2.MFnNurbsSurface, u: float, v: float, world: bool) -> tuple[om2.MVector | None, om2.MVector | None]:
        """U・V方向の正規化した接線を返す。

        ``MFnNurbsSurface.tangents`` はローカル空間では正規化せず、ワールド空間では版により正規化して返すため、
        ローカル空間の微分ベクトルをマトリクスで変換してから正規化する(非均等スケールでも向きが正しい)。

        Args:
            fn (om2.MFnNurbsSurface): 照会する曲面。
            u (float): 検証済みのUのパラメーター。
            v (float): 検証済みのVのパラメーター。
            world (bool): Trueならワールド空間。

        Returns:
            tuple[om2.MVector | None, om2.MVector | None]: U・Vの単位接線。0になる向きは None。
        """
        ...
    def _require_fast_editable(self, check: bool = ...):
        """fast で直接書き込めることを検証する。

        Args:
            check (bool): Trueなら、CVのアトリビュートへ書き込めるか(ロック・入力の接続)も確かめる。

        Raises:
            NotImplementedError: createへの入力(コンストラクションヒストリ)がある場合。
            RuntimeError: シェイプのロック、またはCVのアトリビュートがロック・入力接続されている場合。
        """
        ...
    def _write_surface_data(self, fn: om2.MFnNurbsSurface):
        """検証済みの独立した曲面データを1回のcmdsで書き込む。

        Args:
            fn (om2.MFnNurbsSurface): 書き込むデータ。
        """
        ...
    def _require_knot_edit(self):
        """曲面全体の置換で失われる付帯データと編集不可条件を拒否する。"""
        ...
    def _geometry_fn(self) -> om2.MFnNurbsSurface:
        """形状データを要する照会用に ``om2.MFnNurbsSurface`` を返す。

        Returns:
            om2.MFnNurbsSurface: この曲面の function set。

        Raises:
            RuntimeError: 保持する DAG パスが無効、または形状データを持たない空のシェイプの場合。
        """
        ...
