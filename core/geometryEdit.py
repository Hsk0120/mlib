"""形状の座標を取得・設定する処理。通常はcmdsを使い、fastはヒストリの無い形状へ直接書き込む。"""

from collections import namedtuple

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..maths.vector import _vectors_of_points
from ..util import _finite_vector
from .fastWrite import require_writable

#: 点として受け付ける、wを持つom2の型。XYZだけを使い、wでは割らない。
_OM2_POINTS = (om2.MPoint, om2.MFloatPoint)

#: :func:`geometry` の戻り値。オブジェクトが持つDAGパス・関数セット・Meshかどうか。
_Geometry = namedtuple("_Geometry", ("path", "fn", "is_mesh"))


def geometry(shape, indices, edit=False):
    """ShapeのDAGパスと関数セットを取得する。

    edit=Trueなら、直接書き込めるかどうかも調べる。
    Shapeの型と番号の範囲は、呼び出し側で確かめてあるものとする。

    edit=Trueで調べる内容は次のとおり。

    - inMesh・createへの入力と、Shapeノードのロック。
    - 指定した点のpnts・controlPointsとその子について、上の階層を含むロックと入力接続、
      それぞれのアトリビュートへ書き込めるかどうか。
    - 周期カーブでは、指定した独立CVに重なる末尾の重複CVも調べる。
    - indicesが空のUV更新では、点のPlugごとの検査はしない。

    Args:
        shape (Mesh | NurbsCurve): 型が決まっているShapeのオブジェクト。
        indices (Iterable[int]): 範囲を確かめてあるAPIの点番号。UVの番号ではない。
        edit (bool): Trueなら直接書き込むときの制限を調べる。Falseは取得だけに使う。

    Returns:
        _Geometry: ``path`` (このオブジェクトが持つDAGパス)・``fn`` (MFnMeshまたはMFnNurbsCurve)・``is_mesh`` (MeshならTrue)
            のnamedtuple。tupleとして展開できる。関数セットを取得するだけでは座標を書き換えない。

    Raises:
        RuntimeError: 直接書き込むときにロック・入力接続・書き込み禁止がある場合、またはShapeを参照できない場合。
        NotImplementedError: edit=Trueで、inMesh・createへの入力がある場合。
    """
    path = shape.mpath()
    mesh = path.node().hasFn(om2.MFn.kMesh)
    fn = om2.MFnMesh(path) if mesh else om2.MFnNurbsCurve(path)
    if edit:
        indices = list(indices)
        if not mesh and fn.form == om2.MFnNurbsCurve.kPeriodic:
            # 周期カーブは末尾の重複CVも先頭の独立CVと同じ位置に書くので、重複側の書込み可否も調べる。
            independent = fn.numCVs - fn.degree
            indices += [index % independent + independent for index in indices if index % independent < fn.degree]
        dependency = om2.MFnDependencyNode(path.node())
        source = dependency.findPlug("inMesh" if mesh else "create", False)
        if source.isDestination:
            raise NotImplementedError("fastのジオメトリ編集には、入力ヒストリのないシェイプが必要です")
        if dependency.isLocked:
            raise RuntimeError("シェイプノードがロックされています")
        points = dependency.findPlug("pnts" if mesh else "controlPoints", False)
        for index in indices:
            point = points.elementByLogicalIndex(index)
            require_writable(point)
            for child in range(point.numChildren()):
                require_writable(point.child(child))
    return _Geometry(path, fn, mesh)


def _points(shape, indices, ws=False):
    """指定した点をom2.MPointで取得する。

    点は指定した順に並ぶ。1点だけのときは、すべての点を取得しない。

    Args:
        shape (Shape): 有効なMeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある点番号。
        ws (bool): Trueならワールド空間へ変換する。

    Returns:
        Iterable[om2.MPoint]: 指定順の点。距離はcm。
    """
    path, fn, mesh = geometry(shape, indices)
    space = om2.MSpace.kWorld if ws else om2.MSpace.kObject
    if len(indices) == 1:
        if mesh:
            return [fn.getPoint(indices[0], space)]
        return [fn.cvPosition(indices[0], space)]
    all_points = fn.getPoints(space) if mesh else fn.cvPositions(space)
    return (all_points[i] for i in indices)


def positions(shape, indices, ws=False):
    """指定した点の座標をtupleで取得する。

    内部の座標計算に使う。単位はcmで、指定した順に並ぶ。

    Args:
        shape (Shape): 有効なMeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある点番号。
        ws (bool): Trueならワールド空間へ変換する。

    Returns:
        list[tuple[float, float, float]]: 指定した順の座標。1点だけのときは、すべての点を取得しない。
    """
    return [(point.x, point.y, point.z) for point in _points(shape, indices, ws)]


def vectors(shape, indices, ws=False):
    """指定した点の座標を :class:`~mlib.maths.vector.Vector` で取得する。

    単位はcmで、指定した順に並ぶ。

    Args:
        shape (Shape): 有効なMeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある点番号。
        ws (bool): Trueならワールド空間へ変換する。

    Returns:
        list[Vector]: 指定した順の新しい座標。CVのwでは割らない。
    """
    return _vectors_of_points(_points(shape, indices, ws))


def command_indices(shape, indices):
    """APIの点番号を、cmdsで使う番号へ置き換える。

    番号の順番と重複はそのまま保つ。

    Args:
        shape (Shape): MeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてあるAPIの番号。

    Returns:
        list[int]: cmds用の番号。周期カーブでは、末尾の重複CVを先頭の独立CVの番号に置き換える。
    """
    _, fn, mesh = geometry(shape, indices)
    if not mesh and fn.form == om2.MFnNurbsCurve.kPeriodic:
        return [index % (fn.numCVs - fn.degree) for index in indices]
    return list(indices)


def set_positions(shape, indices, values, ws=False, *, fast=False):
    """点の座標を書き込む。

    座標はcmで、確かめてあるものを渡す。Undoのまとまりは呼び出し元が管理する。

    Args:
        shape (Shape): MeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてあるAPIの番号。同じ番号が重なれば、後の値が残る。
        values (Sequence[Sequence[float]]): 番号と同じ数の、有限なXYZ。
        ws (bool): Trueならワールド座標として扱う。
        fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

    Returns:
        None: 値を返さない。

    Raises:
        RuntimeError: Mayaが書き込みを拒否した場合。すでに済んだ変更は元に戻さない。
        NotImplementedError: fastで、対応していない形状の場合。
    """
    if not indices:
        return
    if fast:
        _set_positions_fast(shape, indices, values, ws)
        return
    _, _, mesh = geometry(shape, indices)
    if ws and not mesh:
        values = object_positions(shape, indices, values)
        ws = False
    numbers = command_indices(shape, indices)
    name, token = shape.getFullName(), "vtx" if mesh else "cv"
    unit = om2.MDistance.uiUnit()
    for index, value in zip(numbers, values):
        coordinates = [om2.MDistance(v).asUnits(unit) for v in value]
        cmds.xform(f"{name}.{token}[{index}]", absolute=True, translation=coordinates, worldSpace=ws, objectSpace=not ws)


def _set_positions_fast(shape, indices, values, ws=False):
    """点の座標をOpenMayaでまとめて設定する。

    座標はcmで、確かめてあるものを渡す。CVのwは変えない。

    Args:
        shape (Shape): ヒストリの無いMeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある番号。
        values (Sequence[Sequence[float]]): 設定するXYZ。
        ws (bool): TrueならAPIのワールド座標、Falseならローカル座標として扱う。

    Returns:
        None: 値を返さない。

    Raises:
        ValueError: ワールド空間で、変換マトリクスが特異な(逆マトリクスを持たない)場合。
        RuntimeError: ロック・入力接続・書き込み禁止がある場合。
        NotImplementedError: 入力ヒストリのある形状の場合。
    """
    if not indices:
        return
    path, fn, mesh = geometry(shape, indices, edit=True)
    points = fn.getPoints() if mesh else fn.cvPositions()
    transform = path.inclusiveMatrix()
    if ws and abs(transform.det4x4()) < 1e-12:
        raise ValueError("トランスフォームが特異なため、ワールド空間では編集できません")
    inverse = transform.inverse() if ws else om2.MMatrix()
    independent = len(points) if mesh or fn.form != om2.MFnNurbsCurve.kPeriodic else fn.numCVs - fn.degree
    for index, value in zip(indices, values):
        # 周期カーブの重複CVの番号は、対応する先頭の独立CVへ写して書く。
        index %= independent
        # cvPositions(kWorld)はCVのwもマトリクスの積に使う。同じwで逆変換して往復を保つ。
        point = om2.MPoint(value[0], value[1], value[2], points[index].w) * inverse
        point.w = points[index].w
        points[index] = point
    # 周期カーブの末尾の重複CVを、先頭の独立CVと同じ位置に揃える(cmds.xformのcv指定と同じ結果)。
    for index in range(independent, len(points)):
        points[index] = om2.MPoint(points[index - independent])
    if mesh:
        fn.setPoints(points)
        fn.updateSurface()
    else:
        fn.setCVPositions(points)
        fn.updateCurve()


def object_positions(shape, indices, values):
    """APIのワールド座標を、ローカルのXYZへ変換する。

    CVのウェイト(w)はそのまま保つ。

    Args:
        shape (Shape): MeshまたはNurbsCurve。
        indices (Sequence[int]): 確かめてある番号。
        values (Sequence[Sequence[float]]): APIのワールドXYZ。距離はcm。

    Returns:
        list[tuple[float, float, float]]: cmdsのobjectSpaceへ渡すcmの座標。

    Raises:
        ValueError: ワールドマトリクスが特異な(逆マトリクスを持たない)場合。
    """
    path, fn, mesh = geometry(shape, indices)
    matrix = path.inclusiveMatrix()
    if abs(matrix.det4x4()) < 1e-12:
        raise ValueError("トランスフォームが特異なため、ワールド空間では編集できません")
    inverse = matrix.inverse()
    if mesh:
        weights = [1.0] * len(indices)
    elif len(indices) == 1:
        weights = [fn.cvPosition(indices[0]).w]
    else:
        cvs = fn.cvPositions()
        weights = [cvs[i].w for i in indices]
    points = [om2.MPoint(row[0], row[1], row[2], weight) * inverse for row, weight in zip(values, weights)]
    return [(point.x, point.y, point.z) for point in points]


def point_list(points):
    """点の並びを、XYZのfloatのtupleのリストへ変換する。

    変換する前に、点の並びとして正しいかを確かめる。

    Args:
        points (Iterable[Sequence[float] | om2.MPoint | om2.MVector]): 点の並び。

    Returns:
        list[tuple[float, float, float]]: 変換済みの点。

    Raises:
        TypeError: 点の並びを順に取り出せない場合、または点や成分の型が正しくない場合。
        ValueError: 成分の数が3でない場合、または有限の値でない場合。
    """
    if isinstance(points, (str, bytes)) or isinstance(points, _OM2_POINTS + (om2.MVector,)):
        raise TypeError("pointsは点の並びで指定してください")
    try:
        items = list(points)
    except TypeError:
        raise TypeError("pointsは点の並びで指定してください") from None
    result = []
    for item in items:
        if isinstance(item, _OM2_POINTS):
            item = (item.x, item.y, item.z)
        elif isinstance(item, (str, bytes)):
            raise TypeError("各点は3つの数値の並びで指定してください")
        result.append(_finite_vector(item, 3, "point"))
    return result
