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


class NurbsSurface(Shape):
    """NURBS曲面のシェイプを扱うクラス。

    アトリビュートや親のTransformの操作はShapeから受け継ぐ。

    CVの番号は ``cv[u][v]`` の (u, v) で表す。:meth:`getCvPositions` などが返すCVの並びは、
    Uを外側・Vを内側にした ``u * numCVsInV + v`` の順になる(``om2.MFnNurbsSurface.cvPositions`` と同じ)。
    距離はMayaの内部単位(cm)。
    """

    def mfn(self):
        """この曲面のOpenMayaのfunction setを取得する。

        呼び出すたびに新しく作る。形状のデータを持たない空のシェイプ
        (``mlib.createNode("nurbsSurface")`` の直後など)では ``om2.MFnNurbsSurface`` が使えない。
        その場合は ``om2.MFnDagNode`` を返す。

        Returns:
            om2.MFnNurbsSurface | om2.MFnDagNode: この曲面の function set。空のシェイプでは MFnDagNode。

        Raises:
            RuntimeError: このオブジェクトが持つDAGパスが無効な場合。
        """
        path = self.mpath()
        try:
            fn = om2.MFnNurbsSurface(path)
            # 版により作成は通り照会で失敗するため、形状データの有無を作成直後に確かめる。
            fn.numCVsInU  # noqa: B018
        except (RuntimeError, ValueError):
            return om2.MFnDagNode(path)
        return fn

    def getNumCVs(self):
        """U・V方向のCVの数を取得する。

        周期曲面では、重なっているCVも数に含む。

        Returns:
            tuple[int, int]: (U方向のCV数, V方向のCV数)。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        fn = self._geometry_fn()
        return fn.numCVsInU, fn.numCVsInV

    def getForm(self):
        """U・V方向の形式(開いているか閉じているか)を取得する。

        Returns:
            tuple[int, int]: U・Vの順の形式。それぞれ ``om2.MFnNurbsSurface`` の kOpen・kClosed・kPeriodic のいずれか。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        fn = self._geometry_fn()
        return fn.formInU, fn.formInV

    def getParamRange(self):
        """U・Vのパラメーターの範囲(``MFnNurbsSurface.knotDomainInU/V``)を取得する。

        Returns:
            tuple[tuple[float, float], tuple[float, float]]: ((U の最小, U の最大), (V の最小, V の最大))。
                ``minMaxRangeU``・``minMaxRangeV`` アトリビュートと同じ値。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        fn = self._geometry_fn()
        u_start, u_end = fn.knotDomainInU
        v_start, v_end = fn.knotDomainInV
        return (u_start, u_end), (v_start, v_end)

    def getKnots(self):
        """U方向・V方向のノット列を取得する。

        Returns:
            tuple[list[float], list[float]]: U・Vの順の独立したリスト。OpenMayaと同じく両端の余分なノットを含めない。

        Raises:
            RuntimeError: 形状が無効な場合。
        """
        fn = self._geometry_fn()
        return list(fn.knotsInU()), list(fn.knotsInV())

    def setKnots(self, uKnots, vKnots):
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
        source = self._geometry_fn()
        self._require_knot_edit()
        u_values = [_finite(value, "uKnots") for value in uKnots]
        v_values = [_finite(value, "vKnots") for value in vKnots]
        for values, count, degree in ((u_values, source.numKnotsInU, source.degreeInU), (v_values, source.numKnotsInV, source.degreeInV)):
            if len(values) != count or any(a > b for a, b in zip(values, values[1:])):
                raise ValueError("ノット列は既存と同じ数の非減少列で指定してください")
            if values[degree - 1] >= values[-degree]:
                raise ValueError("ノットのパラメーター範囲には正の幅が必要です")
        # コピーの所有者を保持し、失敗してもシーン側へ不正なノットを書き込まない。
        data = om2.MFnNurbsSurfaceData().create()
        copied = om2.MFnNurbsSurface(om2.MFnNurbsSurface().copy(source.object(), data))
        copied.setKnotsInU(u_values, 0, len(u_values) - 1)
        copied.setKnotsInV(v_values, 0, len(v_values) - 1)
        self._write_surface_data(copied)

    def removeKnot(self, parameter, direction="u", *, all=False):
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
        _require_bool(all, "all")
        if direction not in ("u", "v"):
            raise ValueError("directionはuまたはvで指定してください")
        parameter = _finite(parameter, "parameter")
        self._require_knot_edit()
        source = self._geometry_fn()
        axis = 0 if direction == "u" else 1
        if self.getForm()[axis] != om2.MFnNurbsSurface.kOpen:
            raise NotImplementedError("ノット削除は指定方向が開いた曲面だけに対応しています")
        low, high = self.getParamRange()[axis]
        if not low < parameter < high or parameter not in self.getKnots()[axis]:
            raise ValueError("parameterはパラメーター範囲の内側のノット値で指定してください")
        # コピーの所有者を編集・書込みが終わるまで保持する。
        data = om2.MFnNurbsSurfaceData().create()
        copied = om2.MFnNurbsSurface(om2.MFnNurbsSurface().copy(source.object(), data))
        if direction == "u":
            if all:
                copied.removeKnotInU(parameter, True)
            else:
                copied.removeOneKnotInU(parameter)
        elif all:
            copied.removeKnotInV(parameter, True)
        else:
            copied.removeOneKnotInV(parameter)
        self._write_surface_data(copied)

    def getPatchShaders(self):
        """保持するインスタンスのパッチごとのシェーディンググループを取得する。

        Returns:
            tuple[Nodes[ShadingEngine], list[int]]: グループ一覧と、パッチごとの一覧内の番号。未割当は-1。

        Raises:
            RuntimeError: 曲面の形状データやDAGパスが無効な場合。
        """
        shaders, indices = self._geometry_fn().getConnectedShaders(self.mpath().instanceNumber())
        return Nodes._wrap([Node(node) for node in shaders]), list(indices)

    def getUVData(self):
        """明示的に設定されたテクスチャUVと、パッチへの割り当てを取得する。

        曲面のパラメーター(u, v)とは別の値。Mayaが既定で使うUVから、明示UVを生成する処理は行わない。

        Returns:
            tuple[list[tuple[float, float]], list[int], list[int]]: UV番号順の(U, V)、パッチ番号順のUV数、
                パッチのコーナー順に連結したUV番号。未割当パッチの数は0。すべて独立した値。

        Raises:
            RuntimeError: 明示的なUVデータが無いか、形状データが無効な場合。
        """
        fn = self._geometry_fn()
        try:
            us, vs = fn.getUVs()
            counts, indices = fn.getAssignedUVs()
        except RuntimeError as error:
            raise RuntimeError(f"明示的なテクスチャUVデータを取得できません: {self.getFullName()}") from error
        return list(zip(us, vs)), list(counts), list(indices)

    def setUVData(self, uvs, counts, indices, *, fast=False):
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
        _require_bool(fast, "fast")
        if not fast:
            raise NotImplementedError("曲面のUV更新はfast=True専用です")
        self._require_uv_edit()
        values = [tuple(_finite(value, "uvs") for value in uv) for uv in uvs]
        counts = list(counts)
        indices = list(indices)
        fn = self._geometry_fn()
        if not values or any(len(uv) != 2 for uv in values):
            raise ValueError("uvsは空でない(U, V)のリストで指定してください")
        if any(type(value) is not int for value in counts + indices):
            raise TypeError("countsとindicesは整数で指定してください")
        if len(counts) != fn.numSpansInU * fn.numSpansInV or any(value not in (0, 4) for value in counts):
            raise ValueError("countsは各パッチに対応する0または4のリストで指定してください")
        if sum(counts) != len(indices) or any(index < 0 or index >= len(values) for index in indices):
            raise ValueError("indicesの長さまたはUV番号が不正です")
        try:
            current_count = fn.numUVs
        except RuntimeError:
            current_count = 0
        if len(values) < current_count:
            raise NotImplementedError("既存UV表の縮小には対応していません")
        # 独立データでMaya側の割当条件も検証してから、実体へ書く。
        data = om2.MFnNurbsSurfaceData().create()
        check_fn = om2.MFnNurbsSurface(om2.MFnNurbsSurface().copy(self.mnode(), data))
        us, vs = zip(*values)
        check_fn.setUVs(us, vs)
        check_fn.assignUVs(counts, indices)
        fn.setUVs(us, vs)
        fn.assignUVs(counts, indices)

    def clearUVData(self):
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
        self._require_uv_edit()
        self._require_fast_editable(check=True)
        if self.mpath().isInstanced():
            raise NotImplementedError("インスタンスの曲面のUV消去には対応していません")
        if len(self.getPlug("uvSet").getIndices()) > 1:
            raise NotImplementedError("複数UVセットを持つ曲面のUV消去には対応していません")
        geometry = om2.MFnGeometryData(self.getPlug("local").mplug().asMObject())
        if geometry.componentTags():
            raise NotImplementedError("コンポーネントタグを持つ曲面のUV消去には対応していません")
        fn = self._geometry_fn()
        try:
            uv_count = fn.numUVs
        except RuntimeError:
            # 明示UVがない曲面では、Mayaは0でなく例外を返す。
            return
        if uv_count:
            self._write_surface_data(fn)

    def getTrimBoundaryInfo(self):
        """トリム領域ごとの境界の種類とエッジ数を取得する。

        境界カーブやシーンのノードは作らない。領域番号・境界番号は編集後も維持されるIDではない。

        Returns:
            list[list[tuple[int, int]]]: 外側の位置が領域番号、内側の位置が境界番号。
                各境界は(種類, エッジ数)。種類はMFnNurbsSurfaceのkOuter・kInner・kSegment・kClosedSegment等。
                未トリム曲面では領域0の境界が空になる。すべて独立した値。

        Raises:
            RuntimeError: 形状データが無いか無効な曲面の場合。
        """
        fn = self._geometry_fn()
        return [
            [(fn.boundaryType(region, boundary), fn.numEdges(region, boundary)) for boundary in range(fn.numBoundaries(region))]
            for region in range(fn.numRegions)
        ]

    def getTrimBoundaryCurveData(self, region, boundary, edge, *, parametric=False):
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
        _require_bool(parametric, "parametric")
        fn = self._geometry_fn()
        self._require_trim_index(region, fn.numRegions, "region")
        self._require_trim_index(boundary, fn.numBoundaries(region), "boundary")
        self._require_trim_index(edge, fn.numEdges(region, boundary), "edge")
        curves = fn.edge(region, boundary, edge, parametric)
        result = []
        for curve in curves:
            curve_fn = om2.MFnNurbsCurve(curve)
            result.append(
                {
                    "degree": curve_fn.degree,
                    "form": curve_fn.form,
                    "knots": list(curve_fn.knots()),
                    "cvs": [(point.x, point.y, point.z, point.w) for point in curve_fn.cvPositions()],
                }
            )
        return result

    def isPointInTrimmedRegion(self, u, v):
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
        fn = self._geometry_fn()
        u, v = self._require_params(fn, u, v)
        # MayaのOM2は、トリム後に残る領域をTrueで返すため、切り落とし領域の判定へ反転する。
        return bool(fn.isTrimmedSurface and not fn.isPointInTrimmedRegion(u, v))

    def getRayIntersection(self, origin, direction, worldSpace=_UNSET, *, tolerance=1e-6, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        start, ray = geometryEdit.point_list([origin, direction])
        ray = om2.MVector(*ray)
        if ray.length() == 0:
            raise ValueError("directionはゼロ以外のベクトルで指定してください")
        result = self._geometry_fn().intersect(om2.MPoint(*start), ray.normal(), tolerance=_checked_tolerance(tolerance, positive=True), space=space)
        if result is None:
            return None
        return _vectors_of_points([result[0]])[0], result[1], result[2]

    def getCV(self, u, v):
        """``(u, v)`` の番号から、CVを1つ取得する。

        Args:
            u (int): U方向のCV番号。
            v (int): V方向のCV番号。

        Returns:
            SurfaceCV: シーン上のCV(``cv[u][v]``)を指すオブジェクト。

        Raises:
            IndexError: CVの番号が範囲外の場合。
        """
        return SurfaceCV(self, (u, v))

    def getCVs(self, indices=None):
        """複数のCVをまとめて取得する。

        Args:
            indices (Iterable[int | tuple[int, int]] | None): CVの番号。1つの通し番号か ``(u, v)`` で指定する。
                Noneなら、今あるすべてのCV。

        Returns:
            SurfaceCVs: CVをまとめたオブジェクト。どのCVも同じShapeを使う。重なった番号は1つにまとめる。
        """
        return SurfaceCVs(self, indices)

    def getCvPositions(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        return _vectors_of_points(self._geometry_fn().cvPositions(space))

    def setCvPositions(self, points, worldSpace=_UNSET, *, fast=False, check=False, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        world = _world_space(worldSpace)
        values = geometryEdit.point_list(points)
        fn = self._geometry_fn()
        count_v = fn.numCVsInV
        count = fn.numCVsInU * count_v
        if len(values) != count:
            raise ValueError(f"点を{count}個指定してください: {len(values)}個")
        path = self.mpath()
        current = fn.cvPositions()
        inverse = om2.MMatrix()
        if world:
            matrix = path.inclusiveMatrix()
            if abs(matrix.det4x4()) < 1e-12:
                raise ValueError("トランスフォームが特異なため、ワールド空間では編集できません")
            inverse = matrix.inverse()
        # cvPositions(kWorld)はCVのwもマトリクスの積に使うため、同じwで逆変換してローカルのXYZにする。
        local = []
        for value, old in zip(values, current):
            point = om2.MPoint(value[0], value[1], value[2], old.w) * inverse
            point.w = old.w
            local.append(point)
        with _edit_context("mlibNurbsSurfaceSetCvPositions", fast, transaction=True):
            if fast:
                self._require_fast_editable(check)
                fn.setCVPositions(om2.MPointArray(local))
                fn.updateSurface()
            else:
                if check:
                    # cmds.xformはCVのロックを見ずに書くので、確かめる指定のときは書く前に確かめる。
                    geometryEdit._require_control_points_writable(self)
                name = self.getFullName()
                unit = om2.MDistance.uiUnit()
                for index, point in enumerate(local):
                    u, v = divmod(index, count_v)
                    coordinates = [om2.MDistance(c).asUnits(unit) for c in (point.x, point.y, point.z)]
                    cmds.xform(f"{name}.cv[{u}][{v}]", absolute=True, translation=coordinates, objectSpace=True)

    def isPointOnSurface(self, point, worldSpace=_UNSET, *, tolerance=1e-7, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        x, y, z = geometryEdit.point_list([point])[0]
        return self._geometry_fn().isPointOnSurface(om2.MPoint(x, y, z), _checked_tolerance(tolerance), space)

    def getClosestPoint(self, point, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        x, y, z = geometryEdit.point_list([point])[0]
        found, u, v = self._geometry_fn().closestPoint(om2.MPoint(x, y, z), tolerance=1e-7, space=space)
        return _vectors_of_points([found])[0], u, v

    def getPointAtParam(self, u, v, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        fn = self._geometry_fn()
        u, v = self._require_params(fn, u, v)
        return _vectors_of_points([fn.getPointAtParam(u, v, space)])[0]

    def getDerivativesAtParam(self, u, v, worldSpace=_UNSET, *, secondOrder=False, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        _require_bool(secondOrder, "secondOrder")
        fn = self._geometry_fn()
        u, v = self._require_params(fn, u, v)
        values = fn.getDerivativesAtParam(u, v, space=space, secondOrder=secondOrder)
        return (_vectors_of_points([values[0]])[0], *(Vector(value) for value in values[1:]))

    def getNormalAtParam(self, u, v, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        fn = self._geometry_fn()
        u, v = self._require_params(fn, u, v)
        normal = Vector(fn.normal(u, v, space))
        if normal.length() < 1e-12:
            raise ValueError(f"({u}, {v})では法線が定義できません: {self.getFullName()}")
        return normal.normal()

    def getTangentsAtParam(self, u, v, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        world = _world_space(worldSpace)
        fn = self._geometry_fn()
        u, v = self._require_params(fn, u, v)
        tangent_u, tangent_v = self._tangents(fn, u, v, world)
        if tangent_u is None or tangent_v is None:
            raise ValueError(f"({u}, {v})ではタンジェントが定義できません: {self.getFullName()}")
        return Vector(tangent_u), Vector(tangent_v)

    def getMatrixAtParam(self, u, v, *, aimAxis="x", upAxis="y", worldSpace=_UNSET, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        world = _world_space(worldSpace)
        aim_axis = _require_axis(aimAxis, "aimAxis")
        up_axis = _require_axis(upAxis, "upAxis")
        if aim_axis[0] == up_axis[0]:
            raise ValueError(f"aimAxisとupAxisは別の軸で指定してください: {aimAxis!r}, {upAxis!r}")
        fn = self._geometry_fn()
        u, v = self._require_params(fn, u, v)
        space = om2.MSpace.kWorld if world else om2.MSpace.kObject
        aim = self._tangents(fn, u, v, world)[0]
        up = None if aim is None else _perpendicular(fn.normal(u, v, space), aim)
        if up is None:
            raise ValueError(f"({u}, {v})ではフレームが定義できません: {self.getFullName()}")
        return _frame_matrix(fn.getPointAtParam(u, v, space), aim, up, aim_axis, up_axis)

    def getArea(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        return self._geometry_fn().area(space)

    def _require_uv_edit(self):
        """UV更新の対応条件とUVアトリビュートの書き込み可否を確認する。"""
        if self.isFromReferencedFile() or self._geometry_fn().isTrimmedSurface:
            raise NotImplementedError("参照・トリム曲面のUV更新には対応していません")
        self._require_fast_editable()
        require_writable(self.getPlug("create").mplug())
        uv_sets = self.getPlug("uvSet").mplug()
        require_writable(uv_sets)
        for index in uv_sets.getExistingArrayAttributeIndices():
            element = uv_sets.elementByLogicalIndex(index)
            require_writable(element)
            for child_index in range(element.numChildren()):
                child = element.child(child_index)
                require_writable(child)
                if child.isArray:
                    for logical_index in child.getExistingArrayAttributeIndices():
                        point = child.elementByLogicalIndex(logical_index)
                        require_writable(point)
                        if point.isCompound:
                            for component_index in range(point.numChildren()):
                                require_writable(point.child(component_index))

    @staticmethod
    def _require_trim_index(index, count, name):
        """Mayaへ渡す前に、トリム構成の0始まりの番号を検査する。"""
        if type(index) is not int:
            raise TypeError(f"{name}はintで指定してください")
        if not 0 <= index < count:
            raise IndexError(f"{name}がトリム構成の範囲外です")

    @staticmethod
    def _require_params(fn, u, v):
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
        result = []
        for name, given, (start, end) in (("u", u, fn.knotDomainInU), ("v", v, fn.knotDomainInV)):
            value = _finite(given, name)
            margin = 1e-9 * max(1.0, end - start)
            if value < start - margin or value > end + margin:
                raise ValueError(f"{name} {value}がサーフェスの範囲[{start}, {end}]の外です")
            result.append(min(max(value, start), end))
        return result[0], result[1]

    def _tangents(self, fn, u, v, world):
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
        tangents = fn.tangents(u, v, om2.MSpace.kObject)
        matrix = self.mpath().inclusiveMatrix() if world else None
        result = []
        for derivative in tangents:
            tangent = om2.MVector(derivative)
            if matrix is not None:
                tangent = tangent * matrix
            length = tangent.length()
            result.append(None if length < _DEGENERATE else tangent / length)
        return result[0], result[1]

    def _require_fast_editable(self, check=False):
        """fast で直接書き込めることを検証する。

        Args:
            check (bool): Trueなら、CVのアトリビュートへ書き込めるか(ロック・入力の接続)も確かめる。

        Raises:
            NotImplementedError: createへの入力(コンストラクションヒストリ)がある場合。
            RuntimeError: シェイプのロック、またはCVのアトリビュートがロック・入力接続されている場合。
        """
        dependency = self._dependency_fn()
        if dependency.findPlug("create", False).isDestination:
            raise NotImplementedError("fastのジオメトリ編集には、入力ヒストリのないシェイプが必要です")
        if dependency.isLocked:
            raise RuntimeError("シェイプノードがロックされています")
        if check:
            geometryEdit._require_control_points_writable(self)

    def _write_surface_data(self, fn):
        """検証済みの独立した曲面データを1回のcmdsで書き込む。

        Args:
            fn (om2.MFnNurbsSurface): 書き込むデータ。
        """
        points = [tuple(point) for point in fn.cvPositions()]
        cmds.setAttr(
            self.getFullName() + ".create",
            fn.degreeInU,
            fn.degreeInV,
            fn.formInU - 1,
            fn.formInV - 1,
            True,
            list(fn.knotsInU()),
            0,
            list(fn.knotsInV()),
            0,
            len(points),
            *points,
            type="nurbsSurface",
        )

    def _require_knot_edit(self):
        """曲面全体の置換で失われる付帯データと編集不可条件を拒否する。"""
        fn = self._geometry_fn()
        if self._dependency_fn().isFromReferencedFile or fn.isTrimmedSurface:
            raise NotImplementedError("参照またはトリム曲面のノット編集には対応していません")
        if self._dependency_fn().isLocked:
            raise RuntimeError("ロックされた曲面のノットは編集できません")
        try:
            uv_count = fn.numUVs
        except RuntimeError:
            uv_count = 0
        if uv_count:
            raise NotImplementedError("明示テクスチャUVを持つ曲面のノット編集には対応していません")
        create = self.getPlug("create")
        if create.getSource() is not None:
            raise NotImplementedError("ヒストリ付き曲面のノット編集には対応していません")
        require_writable(create.mplug())
        for point in self.getPlug("controlPoints").getElements():
            for plug in [point, *point.getChildren()]:
                if plug.isLocked() or plug.getSource() is not None:
                    raise NotImplementedError("CVのロック・接続がある曲面のノット編集には対応していません")

    def _geometry_fn(self):
        """形状データを要する照会用に ``om2.MFnNurbsSurface`` を返す。

        Returns:
            om2.MFnNurbsSurface: この曲面の function set。

        Raises:
            RuntimeError: 保持する DAG パスが無効、または形状データを持たない空のシェイプの場合。
        """
        fn = self.mfn()
        if not isinstance(fn, om2.MFnNurbsSurface):
            raise RuntimeError(f"nurbsSurfaceにジオメトリのデータがありません: {self.getFullName()}")
        return fn
