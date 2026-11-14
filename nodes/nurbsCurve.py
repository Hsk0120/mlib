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

#: aimAxis・upAxis の名前と (軸番号, 符号)。
_AXES = {"x": (0, 1.0), "y": (1, 1.0), "z": (2, 1.0), "-x": (0, -1.0), "-y": (1, -1.0), "-z": (2, -1.0)}
#: 方向を定義できないとみなすベクトルの長さ。
_DEGENERATE = 1e-10
#: 平行移動で向きを運ぶときの、全長あたりの最少の分割数。
_TRANSPORT_STEPS = 128
#: :meth:`NurbsCurve.rebuild` の keepRange と ``cmds.rebuildCurve`` の keepRange の値。
_KEEP_RANGES = {"original": 1, "unit": 0, "spans": 2}
#: :meth:`NurbsCurve.rebuild` で指定できる次数(``cmds.rebuildCurve`` の degree)。
_REBUILD_DEGREES = (1, 2, 3, 5, 7)
#: 面積の数値積分に使う5点のガウス・ルジャンドル則の (節点, 重み)。区間は [-1, 1]。
_GAUSS_LEGENDRE = (
    (0.0, 0.5688888888888889),
    (-0.5384693101056831, 0.4786286704993665),
    (0.5384693101056831, 0.4786286704993665),
    (-0.9061798459386640, 0.2369268850561891),
    (0.9061798459386640, 0.2369268850561891),
)
#: 面積の数値積分で、ノットの区間をさらに分ける数(有理カーブの精度のため)。
_AREA_SUBDIVISIONS = 8
#: 平面とみなすCVの外れの大きさ(cm)。``MFnNurbsCurve.isPlanar`` と同じく、0.001以下なら平面とみなす。
_PLANAR_TOLERANCE = 1e-3


def _points_planar(points):
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
    vectors = [om2.MVector(point) for point in points]
    if len(vectors) < 3:
        return False
    origin = vectors[0]
    far = max(vectors, key=lambda vector: (vector - origin).length())
    axis = far - origin
    if axis.length() <= _DEGENERATE:
        return False
    normal = max((axis ^ (vector - origin) for vector in vectors), key=lambda vector: vector.length())
    if normal.length() <= _DEGENERATE * axis.length():
        return False
    normal.normalize()
    return all(abs(normal * (vector - origin)) <= _PLANAR_TOLERANCE for vector in vectors)


class _OwnedCurve(om2.MFnNurbsCurve):
    """メモリ内の形状データ(``data``)を保持する ``om2.MFnNurbsCurve``。"""


def _require_count(value):
    """点の数を検証する。

    Args:
        value (int): 点の数。boolは受け付けない。

    Returns:
        int: 検証済みの点の数。

    Raises:
        TypeError: int以外(boolを含む)の場合。
        ValueError: 1未満の場合。
    """
    if isinstance(value, bool) or not isinstance(value, numbers.Integral):
        raise TypeError("countはintで指定してください")
    value = int(value)
    if value < 1:
        raise ValueError(f"countは正の値で指定してください: {value}")
    return value


def _require_axis(value, name):
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
    if not isinstance(value, str):
        raise TypeError(f"{name}はstrで指定してください")
    try:
        return _AXES[value]
    except KeyError:
        raise ValueError(f"{name}はx・y・z・-x・-y・-zのどれかで指定してください: {value!r}") from None


def _perpendicular(vector, aim):
    """vector から aim 方向の成分を除いて正規化する。

    Args:
        vector (om2.MVector): 元の方向。
        aim (om2.MVector): 正規化済みの基準方向。

    Returns:
        om2.MVector | None: aim に直交する単位ベクトル。平行で定義できない場合は None。
    """
    result = vector - aim * (vector * aim)
    length = result.length()
    if length < _DEGENERATE:
        return None
    return result / length


def _initial_up(aim):
    """平行移動の最初の上方向を、aim に最も直交する主軸から作る。

    Args:
        aim (om2.MVector): 正規化済みの最初の接線。

    Returns:
        om2.MVector: aim に直交する単位ベクトル。同程度なら Y→Z→X の順に選ぶ。
    """
    candidates = (om2.MVector(0, 1, 0), om2.MVector(0, 0, 1), om2.MVector(1, 0, 0))
    best = min(candidates, key=lambda axis: abs(axis * aim))
    return _perpendicular(best, aim)


def _transport(up, start, end, start_aim, end_aim):
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
    step = om2.MVector(end - start)
    squared = step * step
    reflected_up = up
    reflected_aim = start_aim
    if squared > _DEGENERATE:
        reflected_up = up - step * (2.0 / squared * (step * up))
        reflected_aim = start_aim - step * (2.0 / squared * (step * start_aim))
    second = end_aim - reflected_aim
    squared = second * second
    if squared > _DEGENERATE:
        reflected_up = reflected_up - second * (2.0 / squared * (second * reflected_up))
    result = _perpendicular(reflected_up, end_aim)
    if result is None:
        return _initial_up(end_aim)
    return result


def _fill_missing(values):
    """None の要素を直前の値(先頭は最初の有効な値)で埋める。

    Args:
        values (list[object | None]): 埋める並び。

    Returns:
        list[object] | None: 埋めた新しい並び。有効な値が1つも無い場合は None。
    """
    valid = [value for value in values if value is not None]
    if not valid:
        return None
    previous = valid[0]
    result = []
    for value in values:
        if value is not None:
            previous = value
        result.append(previous)
    return result


def _frame_matrix(position, aim, up, aim_axis, up_axis):
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
    axes = [None, None, None]
    axes[aim_axis[0]] = aim * aim_axis[1]
    axes[up_axis[0]] = up * up_axis[1]
    other = 3 - aim_axis[0] - up_axis[0]
    axes[other] = axes[(other + 1) % 3] ^ axes[(other + 2) % 3]
    values = []
    for axis in axes:
        values.extend((axis.x, axis.y, axis.z, 0.0))
    values.extend((position.x, position.y, position.z, 1.0))
    return Matrix(values)


class NurbsCurve(Shape):
    """NURBSカーブのシェイプを扱うクラス。

    - 点を並べてカーブを作るときは :func:`mlib.createCurve <mlib.cmds.createCurve.createCurve>` を使う。
    - CVの位置をまとめて設定するときは :meth:`setCvPositions` を使う。
    - CV(:class:`~mlib.components.cv.CV`)のオブジェクトからも、座標を取得・編集できる。
    - 形を反転するときは :meth:`mirror` を使う。
    """

    def getCV(self, index):
        """CVの番号から、CVを1つ取得する。

        Args:
            index (int): 0から始まるCVの番号。

        Returns:
            CV: シーン上のCVを指すオブジェクト。

        Raises:
            IndexError: CVの番号が範囲外の場合。
        """
        return CV(self, index)

    def getCVs(self, indices=None):
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
        return CVs(self, indices)

    def mfn(self):
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
        path = self.mpath()
        try:
            fn = om2.MFnNurbsCurve(path)
            # 版により作成は通り照会で失敗するため、形状データの有無を作成直後に確かめる。
            fn.typeId  # noqa: B018
        except (RuntimeError, ValueError):
            return om2.MFnDagNode(path)
        return fn

    def getNumCVs(self):
        """CV 数を取得する。

        Returns:
            int: カーブの CV 数。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        return self._geometry_fn().numCVs

    def getNumSpans(self):
        """スパン数を取得する。

        Returns:
            int: カーブのスパン数。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        return self._geometry_fn().numSpans

    def getDegree(self):
        """カーブの次数を取得する。

        Returns:
            int: NURBS カーブの次数。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        return self._geometry_fn().degree

    def getForm(self):
        """カーブの形式(開いているか閉じているか)を取得する。

        Returns:
            int: MFnNurbsCurve の kOpen、kClosed、kPeriodic のいずれか。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        return self._geometry_fn().form

    def getKnots(self):
        """ノットの並びを取得する(``MFnNurbsCurve.knots``)。

        Returns:
            list[float]: Mayaの形式のノットの並び。長さは ``getNumCVs() + getDegree() - 1`` になる。
                両端の2つを省いた形で、``cmds.curve(knot=...)`` へそのまま渡せる。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        return list(self._geometry_fn().knots())

    def isPlanar(self):
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
        return _points_planar(self._geometry_fn().cvPositions())

    def getLength(self, tolerance=1e-6, *, worldSpace=_UNSET, unit="cm", ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        # 循環importを避けるため、単位の照会時に読み込む。
        from ..common import units

        # 単位は毎回照会する。係数を使うためシーンの単位設定は変更しない。
        factor = units.convertDistance(1.0, fromUnit="cm", toUnit=unit)
        tolerance = float(tolerance)
        if not math.isfinite(tolerance) or tolerance <= 0:
            raise ValueError("toleranceは正の有限な数値で指定してください")
        return self._space_curve(ws).length(tolerance) * factor

    def getArea(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        curve = self._space_curve(worldSpace)
        start, end = curve.knotDomain
        if curve.form == om2.MFnNurbsCurve.kOpen:
            first = curve.getPointAtParam(start)
            last = curve.getPointAtParam(end)
            if first.distanceTo(last) > 1e-6 * max(1.0, curve.length(1e-6)):
                raise ValueError(f"カーブが閉じていません: {self.getFullName()}")
        if not _points_planar(curve.cvPositions()):
            raise ValueError(f"カーブが平面上にありません: {self.getFullName()}")
        breaks = sorted({knot for knot in curve.knots() if start <= knot <= end} | {start, end})
        total = om2.MVector()
        for low, high in zip(breaks, breaks[1:]):
            step = (high - low) / _AREA_SUBDIVISIONS
            for index in range(_AREA_SUBDIVISIONS):
                center = low + step * (index + 0.5)
                for node, weight in _GAUSS_LEGENDRE:
                    param = center + step * 0.5 * node
                    # tangentは正規化しない微分ベクトル(dP/dt)を返す。
                    total += (om2.MVector(curve.getPointAtParam(param)) ^ curve.tangent(param)) * (weight * step * 0.5)
        return total.length() * 0.5

    def getCvPositions(self, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        space = om2.MSpace.kWorld if ws else om2.MSpace.kObject
        return _vectors_of_points(self._geometry_fn().cvPositions(space))

    def setCvPositions(self, points, worldSpace=_UNSET, *, fast=False, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        values = geometry_edit.point_list(points)
        fn = self._geometry_fn()
        count = fn.numCVs
        independent = count
        if fn.form == om2.MFnNurbsCurve.kPeriodic:
            independent = count - fn.degree
            if len(values) == count:
                for index in range(independent, count):
                    if values[index] != values[index - independent]:
                        raise ValueError("周期カーブの重なるCVは、先頭のCVと一致させてください")
                values = values[:independent]
        if len(values) != independent:
            if independent != count:
                raise ValueError(f"点を{independent}個か{count}個指定してください: {len(values)}個")
            raise ValueError(f"点を{count}個指定してください: {len(values)}個")
        with _edit_context("mlibNurbsCurveSetCvPositions", fast, transaction=True):
            geometry_edit.set_positions(self, list(range(independent)), values, ws, fast=fast)
        return self

    def mirror(self, axis="x", worldSpace=_UNSET, pivot=(0.0, 0.0, 0.0), indices=None, *, fast=False, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(fast, "fast")
        ws = _world_space(worldSpace)
        _write_points([self._mirror_plan(axis, ws, pivot, indices, fast)], fast, "mlibNurbsCurveMirror")
        return self

    def rebuild(self, spans=None, degree=None, *, keepRange="original"):
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
        fn = self._geometry_fn()
        if spans is None:
            spans = fn.numSpans
        elif isinstance(spans, bool) or not isinstance(spans, numbers.Integral):
            raise TypeError("spansはintかNoneで指定してください")
        elif spans < 1:
            raise ValueError(f"spansは正の値で指定してください: {spans}")
        if degree is None:
            degree = fn.degree
        elif isinstance(degree, bool) or not isinstance(degree, numbers.Integral):
            raise TypeError("degreeはintかNoneで指定してください")
        elif degree not in _REBUILD_DEGREES:
            raise ValueError(f"degreeは1・2・3・5・7のどれかで指定してください: {degree}")
        if not isinstance(keepRange, str):
            raise TypeError("keepRangeはstrで指定してください")
        if keepRange not in _KEEP_RANGES:
            raise ValueError(f"keepRangeはoriginal・unit・spansのどれかで指定してください: {keepRange!r}")
        with undoChunk("mlibNurbsCurveRebuild"), preservedSelection():
            cmds.rebuildCurve(
                self.getFullName(),
                spans=int(spans),
                degree=int(degree),
                keepRange=_KEEP_RANGES[keepRange],
                rebuildType=0,
                keepEndPoints=True,
                keepControlPoints=False,
                keepTangents=False,
                constructionHistory=False,
                replaceOriginal=True,
            )
        return self

    def reverse(self):
        """カーブの向き(パラメーターが増える向き)を反転する(``cmds.reverseCurve``)。

        ``cmds.reverseCurve(constructionHistory=False, replaceOriginal=True)`` で、このシェイプの形状を
        置き換える。1回のUndoで戻せる。形の位置は変わらず、CVの並びだけが逆になる。
        シェイプのノードと選択は変わらない。

        Returns:
            NurbsCurve: 自身。

        Raises:
            RuntimeError: 形状のデータを持たない空のシェイプの場合、またはロックなどでMayaが書込みを拒否した場合。
        """
        self._geometry_fn()
        with undoChunk("mlibNurbsCurveReverse"), preservedSelection():
            cmds.reverseCurve(self.getFullName(), constructionHistory=False, replaceOriginal=True)
        return self

    def getCollocatedCVGroups(self, tolerance=1e-6, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        ws = _world_space(worldSpace)
        if not tolerance > 0:
            raise ValueError("toleranceは正の値で指定してください")
        # 距離の計算には MPoint.distanceTo を使うため、Vector へ変換せずに om2 の点列を読む。
        positions = self._geometry_fn().cvPositions(om2.MSpace.kWorld if ws else om2.MSpace.kObject)
        assigned = [False] * len(positions)
        groups = []
        for i in range(len(positions)):
            if assigned[i]:
                continue
            group = [i]
            for j in range(i + 1, len(positions)):
                if not assigned[j] and positions[i].distanceTo(positions[j]) <= tolerance:
                    group.append(j)
                    assigned[j] = True
            if len(group) > 1:
                assigned[i] = True
                groups.append(group)
        return groups

    def getParamRange(self):
        """パラメーターの範囲(``MFnNurbsCurve.knotDomain``)を取得する。

        Returns:
            tuple[float, float]: 最小と最大のパラメーター。``minValue``・``maxValue`` アトリビュートと同じ値。

        Raises:
            RuntimeError: 形状データを持たない空のシェイプの場合。
        """
        start, end = self._geometry_fn().knotDomain
        return start, end

    def getClosestPoint(self, point, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        x, y, z = geometry_edit.point_list([point])[0]
        curve = self._space_curve(worldSpace)
        found, param = curve.closestPoint(om2.MPoint(x, y, z), tolerance=1e-7)
        return _vectors_of_points([found])[0], param

    def getPointAtParam(self, param, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        curve = self._space_curve(worldSpace)
        return _vectors_of_points([curve.getPointAtParam(self._require_param(curve, param))])[0]

    def getTangentAtParam(self, param, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        curve = self._space_curve(worldSpace)
        tangent = self._tangent(curve, self._require_param(curve, param))
        if tangent is None:
            raise ValueError(f"パラメータ{param}ではタンジェントが定義できません: {self.getFullName()}")
        return Vector(tangent)

    def getNormalAtParam(self, param, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        curve = self._space_curve(worldSpace)
        value = self._require_param(curve, param)
        if curve.degree == 1:
            # 次数1の直線にもMayaは任意の直交方向を返すため、CVの一直線を先に拒否する。
            points = curve.cvPositions()
            first = om2.MVector(points[0])
            span = max((om2.MVector(item) - first for item in points), key=lambda item: item.length())
            if span.length() < _DEGENERATE or all((span ^ (om2.MVector(item) - first)).length() <= 1e-9 * span.length() ** 2 for item in points):
                raise ValueError(f"直線のカーブでは法線が定義できません: {self.getFullName()}")
        try:
            normal = curve.normal(value)
        except RuntimeError:
            # 曲率が0の位置ではMayaがkInvalidParameterで拒否する。
            normal = om2.MVector()
        length = normal.length()
        if length < _DEGENERATE:
            raise ValueError(f"パラメータ{param}では法線が定義できません: {self.getFullName()}")
        return Vector(normal / length)

    def getLengthAtParam(self, param, worldSpace=_UNSET, *, unit="cm", ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        curve = self._space_curve(worldSpace)
        factor = self._unit_factor(unit)
        value = self._require_param(curve, param)
        if value <= curve.knotDomain[0]:
            return 0.0
        return curve.findLengthFromParam(value) * factor

    def getParamAtLength(self, length, worldSpace=_UNSET, *, unit="cm", ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        curve = self._space_curve(worldSpace)
        factor = self._unit_factor(unit)
        value = _finite(length, "length") / factor
        return self._param_at_length(curve, value, curve.length(1e-6))

    def getParamsAlong(self, count, worldSpace=_UNSET, *, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        count = _require_count(count)
        curve = self._space_curve(worldSpace)
        return self._params_along(curve, count)

    def getMatricesAlong(self, count, up=None, *, aimAxis="x", upAxis="y", worldSpace=_UNSET, ws=_UNSET):
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
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        count = _require_count(count)
        aim_axis = _require_axis(aimAxis, "aimAxis")
        up_axis = _require_axis(upAxis, "upAxis")
        if aim_axis[0] == up_axis[0]:
            raise ValueError(f"aimAxisとupAxisは別の軸で指定してください: {aimAxis!r}, {upAxis!r}")
        up_vector = None
        if up is not None:
            x, y, z = geometry_edit.point_list([up])[0]
            up_vector = om2.MVector(x, y, z)
            if up_vector.length() < _DEGENERATE:
                raise ValueError("upに0のベクトルは指定できません")
            up_vector.normalize()
        curve = self._space_curve(worldSpace)
        params = self._params_along(curve, count)
        aims = _fill_missing([self._tangent(curve, param) for param in params])
        if aims is None:
            raise ValueError(f"カーブ全体でタンジェントが定義できません: {self.getFullName()}")
        positions = [curve.getPointAtParam(param) for param in params]
        if up_vector is not None:
            ups = _fill_missing([_perpendicular(up_vector, aim) for aim in aims])
            if ups is None:
                raise ValueError("upが、すべての点でカーブのタンジェントと平行です")
        else:
            ups = self._transported_ups(curve, params, aims)
        return [_frame_matrix(position, aim, value, aim_axis, up_axis) for position, aim, value in zip(positions, aims, ups)]

    def _space_curve(self, worldSpace):
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
        ws = _world_space(worldSpace)
        source = self._geometry_fn()
        if not ws:
            return source
        data = om2.MFnNurbsCurveData().create()
        curve = _OwnedCurve(om2.MFnNurbsCurve().copy(source.object(), data))
        # 形状データのMObjectが解放されるとfunction setが無効になるため、照会を終えるまで保持する。
        curve.data = data
        curve.setCVPositions(source.cvPositions(om2.MSpace.kWorld))
        curve.updateCurve()
        return curve

    @staticmethod
    def _unit_factor(unit):
        """cmから指定した距離単位への係数を返す。

        Args:
            unit (str | None): 距離単位。Noneは現在の距離UI単位。

        Returns:
            float: 1cmを指定単位で表した値。

        Raises:
            TypeError: 単位の型が不正な場合。
            ValueError: 単位名が未対応の場合。
        """
        # 循環importを避けるため、単位の照会時に読み込む。
        from ..common import units

        return units.convertDistance(1.0, fromUnit="cm", toUnit=unit)

    @staticmethod
    def _require_param(curve, param):
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
        value = _finite(param, "param")
        start, end = curve.knotDomain
        margin = 1e-9 * max(1.0, end - start)
        if value < start - margin or value > end + margin:
            raise ValueError(f"パラメータ{value}がカーブの範囲[{start}, {end}]の外です")
        return min(max(value, start), end)

    @staticmethod
    def _tangent(curve, param):
        """正規化した接線を返す。

        Args:
            curve (om2.MFnNurbsCurve): 照会するカーブ。
            param (float): 検証済みのパラメーター。

        Returns:
            om2.MVector | None: 単位ベクトル。接線が0の位置は None。
        """
        # MFnNurbsCurve.tangentは文書と異なり正規化しない微分ベクトルを返す。
        tangent = curve.tangent(param)
        length = tangent.length()
        if length < _DEGENERATE:
            return None
        return tangent / length

    @staticmethod
    def _param_at_length(curve, length, total):
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
        margin = 1e-6 * max(1.0, total)
        if length < -margin or length > total + margin:
            raise ValueError(f"長さ{length}がカーブの長さ[0, {total}]の外です")
        start, end = curve.knotDomain
        if length <= 0.0:
            return start
        if length >= total:
            return end
        return min(max(curve.findParamFromLength(length), start), end)

    def _params_along(self, curve, count):
        """弧長で等間隔のパラメーターを返す(:meth:`getParamsAlong` の本体)。

        Args:
            curve (om2.MFnNurbsCurve): 照会するカーブ。
            count (int): 検証済みの点の数。

        Returns:
            list[float]: 始点から順のパラメーター。
        """
        start, end = curve.knotDomain
        if count == 1:
            return [start]
        total = curve.length(1e-6)
        closed = curve.form != om2.MFnNurbsCurve.kOpen
        intervals = count if closed else count - 1
        params = [start]
        for index in range(1, count):
            params.append(self._param_at_length(curve, total * index / intervals, total))
        if not closed:
            params[-1] = end
        return params

    def _transported_ups(self, curve, params, aims):
        """平行移動で運んだ各点の上方向を返す。

        Args:
            curve (om2.MFnNurbsCurve): 照会するカーブ。
            params (list[float]): 出力する点のパラメーター。
            aims (list[om2.MVector]): 各点の単位接線。

        Returns:
            list[om2.MVector]: 各点の、接線に直交する単位ベクトル。
        """
        up = _initial_up(aims[0])
        ups = [up]
        if len(params) == 1:
            return ups
        total_length = curve.length(1e-6)
        steps = max(1, -(-_TRANSPORT_STEPS // (len(params) - 1)))
        point = curve.getPointAtParam(params[0])
        aim = aims[0]
        for index in range(1, len(params)):
            begin = curve.findLengthFromParam(params[index - 1]) if params[index - 1] > params[0] else 0.0
            finish = curve.findLengthFromParam(params[index])
            for step in range(1, steps + 1):
                if step == steps:
                    param = params[index]
                    next_aim = aims[index]
                else:
                    length = begin + (finish - begin) * step / steps
                    param = self._param_at_length(curve, length, total_length)
                    tangent = self._tangent(curve, param)
                    next_aim = aim if tangent is None else tangent
                next_point = curve.getPointAtParam(param)
                up = _transport(up, point, next_point, aim, next_aim)
                point = next_point
                aim = next_aim
            ups.append(up)
        return ups

    def _mirror_plan(self, axis, ws, pivot, indices, fast):
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
        self._geometry_fn()
        return _mirror_plan(self.getCVs(indices), axis, ws, pivot, fast)

    def _geometry_fn(self):
        """形状データを要する照会用に ``om2.MFnNurbsCurve`` を返す。

        Returns:
            om2.MFnNurbsCurve: このカーブの function set。

        Raises:
            RuntimeError: 保持する DAG パスが無効、または形状データを持たない空のシェイプの場合。
        """
        fn = self.mfn()
        if not isinstance(fn, om2.MFnNurbsCurve):
            raise RuntimeError(f"nurbsCurveにジオメトリのデータがありません: {self.getFullName()}")
        return fn
