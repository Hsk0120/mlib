"""MayaのNURBS曲面シェイプを扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..components.surfaceCV import SurfaceCV, SurfaceCVs
from ..core import geometryEdit as geometry_edit
from ..core.fastWrite import require_writable
from ..decorator import _edit_context, _pick_alias, _require_bool
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _finite, _world_space
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

    def getNumSpans(self):
        """U・V方向のスパン数を取得する。

        Returns:
            tuple[int, int]: (U方向のスパン数, V方向のスパン数)。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        fn = self._geometry_fn()
        return fn.numSpansInU, fn.numSpansInV

    def getDegree(self):
        """U・V方向の次数を取得する。

        Returns:
            tuple[int, int]: (U方向の次数, V方向の次数)。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        fn = self._geometry_fn()
        return fn.degreeInU, fn.degreeInV

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

    def setCvPositions(self, points, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
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

        Returns:
            NurbsSurface: 自身。

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
        values = geometry_edit.point_list(points)
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
                self._require_fast_editable()
                fn.setCVPositions(om2.MPointArray(local))
                fn.updateSurface()
            else:
                name = self.getFullName()
                unit = om2.MDistance.uiUnit()
                for index, point in enumerate(local):
                    u, v = divmod(index, count_v)
                    coordinates = [om2.MDistance(c).asUnits(unit) for c in (point.x, point.y, point.z)]
                    cmds.xform(f"{name}.cv[{u}][{v}]", absolute=True, translation=coordinates, objectSpace=True)
        return self

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
        x, y, z = geometry_edit.point_list([point])[0]
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
        for name, value, (start, end) in (("u", u, fn.knotDomainInU), ("v", v, fn.knotDomainInV)):
            value = _finite(value, name)
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
        for tangent in tangents:
            tangent = om2.MVector(tangent)
            if matrix is not None:
                tangent = tangent * matrix
            length = tangent.length()
            result.append(None if length < _DEGENERATE else tangent / length)
        return result[0], result[1]

    def _require_fast_editable(self):
        """fast で直接書き込めることを検証する。

        Raises:
            NotImplementedError: createへの入力(コンストラクションヒストリ)がある場合。
            RuntimeError: シェイプのロック、またはCVのアトリビュートがロック・入力接続されている場合。
        """
        dependency = self._dependency_fn()
        if dependency.findPlug("create", False).isDestination:
            raise NotImplementedError("fastのジオメトリ編集には、入力ヒストリのないシェイプが必要です")
        if dependency.isLocked:
            raise RuntimeError("シェイプノードがロックされています")
        points = dependency.findPlug("controlPoints", False)
        for index in points.getExistingArrayAttributeIndices():
            point = points.elementByLogicalIndex(index)
            require_writable(point)
            for child in range(point.numChildren()):
                require_writable(point.child(child))

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
