"""DAG シェイプの共通操作を提供する。"""

import math
import numbers
import operator

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core import geometryEdit
from ..decorator import _edit_context, _pick_alias, _require_bool
from ..util import _UNSET, _world_space
from .dagNode import DagNode
from .transform import Transform


class Shape(DagNode):
    """MayaのDAGのShapeノードに共通する操作を扱うクラス。"""

    def setParent(self, parent=None, *, relative=False, add=False, fast=False, check=False):
        """このシェイプを別のTransformの下へ移す。``add=True`` なら、今の親はそのままにして親を加える(インスタンス)。

        ``cmds.parent(shape, transform, shape=True, relative=True)`` と同じ(``add=True`` は ``add=True`` も付ける)。
        引数は :meth:`Transform.setParent <mlib.nodes.transform.Transform.setParent>` と同じ。
        シェイプは常にローカルの形のまま移る(relativeの値によらない)。そのため、ワールドでの位置は新しい親に合わせて変わる。
        シェイプが無くなっても、元のTransformは削除しない。
        :meth:`~mlib.nodes.transform.Transform.addShape` は、同じ操作を受け取る側から行う。

        Args:
            parent (Transform | str | None): 新しい親のTransform(Jointも指定できる)。シェイプはワールドの直下へ置けないため、
                Noneは指定できない(Transform.setParentと引数を揃えるために既定値を持つ)。
            relative (bool): Transform.setParentと同じ引数。シェイプは常にローカルの形のまま移るため、値によって動きは変わらない。
                既定はFalse。
            add (bool): Trueなら、今の親はそのままにして、新しい親の下にもインスタンスを加える。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。``MDagModifier.reparentNode`` を使う。
                add=Trueには対応していない(NotImplementedError)。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、シェイプ・元の親・新しい親がロック・リファレンスで編集できないものでないか(fastでは常に確かめる)。

        Returns:
            None: 値を返さない。移した後のパスを指す。add=Trueでは、このオブジェクトは元のパスを指したまま。

        Raises:
            TypeError: parentがTransformでない場合、またはrelative・add・fast・checkがboolでない場合。
            ValueError: parentがNoneの場合。
            RuntimeError: 自身か親が無効な場合、add=Falseでシェイプがインスタンス化されている場合、
                checkかfastで、ロックされたノードやリファレンスのノードを含む場合、
                またはMayaが親の変更を拒否した場合。
            NotImplementedError: fastで、add=Trueを指定した場合、または移す先に同じ名前の子がある場合
                (Mayaが名前を付け直す規則を再現しないため)。
        """
        with _edit_context("mlibShapeSetParent", fast):
            _require_bool(relative, "relative")
            _require_bool(add, "add")
            _require_bool(check, "check")
            self._require_valid("親子付け")
            if parent is None:
                raise ValueError("シェイプはワールドの直下へ置けません。parentにTransformを指定してください")
            target = parent if isinstance(parent, DagNode) else DagNode._resolve_input(parent)
            if not target.isValid():
                raise RuntimeError("parentが有効なノードではありません")
            if not isinstance(target, Transform):
                raise TypeError(f"parentはtransformで指定してください: {target._full_name()}")
            if add:
                if fast:
                    raise NotImplementedError("fastのsetParentは、add=True(シェイプのインスタンス)に対応していません")
                if check:
                    self._require_editable_parents(target)
                cmds.parent(self._full_name(), target._full_name(), shape=True, relative=True, add=True)
                return
            if self.mpath().isInstanced():
                raise RuntimeError(f"インスタンスのシェイプは移動できません: {self._full_name()}")
            current = self.getParent()
            if current is not None and current.mpath().fullPathName() == target.mpath().fullPathName():
                return
            if fast:
                self._set_parent_fast(target)
            else:
                if check:
                    self._require_editable_parents(target)
                cmds.parent(self._full_name(), target._full_name(), shape=True, relative=True)

    def scaleGeometry(self, scale, worldSpace=_UNSET, *, pivot=(0.0, 0.0, 0.0), indices=None, fast=False, check=False, ws=_UNSET):
        """メッシュの頂点やNURBSのCVを、指定した中心で拡大・縮小する。

        Transformのマトリクスと、フェースの頂点の順は変えない。
        形状を共有しているインスタンスでは、すべてのインスタンスに影響する。
        周期的なカーブ・サーフェスで連動して動くCVも考えに入れて拡大・縮小する。
        途中で失敗しても、それまでに変えた分は戻さない。

        Args:
            scale (float | Iterable[float]): 倍率。1つの数ならXYZに同じ倍率、3つならXYZごとの倍率。
                有限な数で指定する。負の数や0も指定できる。
            worldSpace (bool): Trueならワールド空間、FalseならShapeのオブジェクト空間で拡大・縮小する。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 拡大・縮小の中心。worldSpaceで選んだ空間での位置で、単位はcm。
                既定は原点。Transformのピボットは使わない。
            indices (Iterable[int | tuple[int, int]] | None): 対象の頂点またはCVの番号。サーフェスでは(U, V)の組。
                Noneならすべてが対象。空なら何も書き込まない。ただし、Shapeの種類の確認と、
                fastでサーフェスを拒否する確認は、その前に行う。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Trueで使えるのは、ヒストリの無いメッシュとカーブだけ。
                Falseなら、Maya標準のコマンドで書き込み、Undoが有効なら1回にまとめる。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fast・checkや番号の型が正しくない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 倍率・中心・空間の指定が正しくない場合、ワールドへの変換がほぼ特異(逆に戻せない)な場合、
                またはメッシュ・NURBS以外のShapeの場合。
            IndexError: 番号が範囲外の場合。
            RuntimeError: Mayaが編集を拒否した場合。
            NotImplementedError: fastで、サーフェスやヒストリのある形状を指定した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        _require_bool(check, "check")
        with _edit_context("mlibShapeScaleGeometry", fast):
            ws = _world_space(worldSpace)
            try:
                factors = (float(scale),) * 3 if isinstance(scale, numbers.Real) else tuple(float(v) for v in scale)
                center = tuple(float(v) for v in pivot)
            except (TypeError, ValueError):
                raise ValueError("scaleとpivotは有限な数値で指定してください") from None
            if len(factors) != 3 or len(center) != 3 or not all(math.isfinite(v) for v in factors + center):
                raise ValueError("scaleとpivotは3つの有限な数値で指定してください")
            path = self.mpath()
            if path.node().hasFn(om2.MFn.kMesh):
                counts = (om2.MFnMesh(path).numVertices,)
                token = "vtx"
            elif path.node().hasFn(om2.MFn.kNurbsCurve):
                fn = om2.MFnNurbsCurve(path)
                counts = (fn.numCVs,)
                token = "cv"
            elif path.node().hasFn(om2.MFn.kNurbsSurface):
                fn = om2.MFnNurbsSurface(path)
                counts = (fn.numCVsInU, fn.numCVsInV)
                token = "cv"
            else:
                raise ValueError("scaleGeometryはメッシュとNURBSのシェイプに対応しています")
            if fast and len(counts) == 2:
                raise NotImplementedError("fastのscaleGeometryはNURBSサーフェスに対応していません")
            selected = []
            if indices is None:
                components = []
                if len(counts) == 2:
                    # cmds.ls("cv[*][*]", flatten=True) と同じく、周期方向は独立CV(数 - 次数)だけを u 優先で並べる。
                    counts_u, counts_v = (
                        count - degree if form == om2.MFnNurbsSurface.kPeriodic else count
                        for count, degree, form in zip(counts, (fn.degreeInU, fn.degreeInV), (fn.formInU, fn.formInV))
                    )
                    components = [(u, v) for u in range(counts_u) for v in range(counts_v)]
                if len(counts) == 1:
                    count = counts[0]
                    if token == "cv" and fn.form == om2.MFnNurbsCurve.kPeriodic:
                        count -= fn.degree
                    selected = list(range(count))
            else:
                components = []
                seen = set()
                for value in indices:
                    row = (value,) if len(counts) == 1 else tuple(value)
                    if len(row) != len(counts) or any(isinstance(v, bool) for v in row):
                        raise TypeError("コンポーネントの番号が不正です")
                    row = tuple(operator.index(v) for v in row)
                    if any(v < 0 or v >= count for v, count in zip(row, counts)):
                        raise IndexError("コンポーネントの番号が範囲外です")
                    if path.node().hasFn(om2.MFn.kNurbsCurve):
                        row = (geometryEdit.command_indices(self, row)[0],)
                    elif path.node().hasFn(om2.MFn.kNurbsSurface):
                        fn = om2.MFnNurbsSurface(path)
                        row = tuple(
                            value % (count - degree) if form == om2.MFnNurbsSurface.kPeriodic else value
                            for value, count, degree, form in zip(row, counts, (fn.degreeInU, fn.degreeInV), (fn.formInU, fn.formInV))
                        )
                    if row in seen:
                        continue
                    seen.add(row)
                    if len(counts) == 1:
                        selected.append(row[0])
                    else:
                        components.append(row)
            if not selected and (len(counts) == 1 or not components):
                return
            if ws:
                matrix = path.inclusiveMatrix()
                magnitude = max(1.0, *(sum(abs(matrix[r * 4 + c]) for c in range(3)) for r in range(3)))
                if abs(matrix.det4x4()) <= 1e-12 * magnitude**3:
                    raise ValueError("トランスフォームが特異に近いため、ワールド空間ではスケールできません")
            if len(counts) == 1:
                # 全座標を先にAPIで読む。周期CVも独立番号にまとめ、二重に拡縮しない。
                positions = geometryEdit.positions(self, selected, ws)
                values = [tuple(center[i] + (point[i] - center[i]) * factors[i] for i in range(3)) for point in positions]
                if not all(math.isfinite(v) for row in values for v in row):
                    raise ValueError("スケールした位置が有限な数値になりません")
                geometryEdit.set_positions(self, selected, values, ws, fast=fast, check=check)
                return
            center = tuple(om2.MDistance(v).asUnits(om2.MDistance.uiUnit()) for v in center)
            # scaleコマンドのpivot解釈に依存せず、同じ空間で読んだ座標を変換する。
            # 全座標を先にMFnNurbsSurfaceで読み(cmds.xform(query=True)と同じUI単位の値)、
            # 周期CVの連動で後続の読取り値が変わるのを防ぐ。書込みはUndoのためcmds.xformを使う。
            space = om2.MSpace.kWorld if ws else om2.MSpace.kObject
            surface = om2.MFnNurbsSurface(path)
            ui_unit = om2.MDistance.uiUnit()
            positions = []
            for u, v in components:
                point = surface.cvPosition(u, v, space)
                positions.append([om2.MDistance(point[i]).asUnits(ui_unit) for i in range(3)])
            name = self._full_name() + "." + token
            for (u, v), position in zip(components, positions):
                values = [center[i] + (position[i] - center[i]) * factors[i] for i in range(3)]
                cmds.xform(f"{name}[{u}][{v}]", translation=values, worldSpace=ws, objectSpace=not ws)

    def getTransform(self):
        """このShapeの親Transformを取得する。

        Returns:
            Transform | None: 親Transform。存在しない場合は ``None``。
        """
        return self.getParent()

    def _require_editable_parents(self, target):
        """シェイプ・元の親・新しい親が、ロック・リファレンスで編集できないものでないかを確かめる。

        Args:
            target (Transform): 新しい親。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: どれかが、ロックされているかリファレンスのノードの場合。
        """
        # core は nodes を参照するため、循環importを避けて関数内で読み込む。
        from ..core.nodeEdit import require_editable

        for node in (self, self.getParent(), target):
            if node is not None:
                require_editable(node.mnode())

    def _set_parent_fast(self, target):
        """編集できるかを先に確かめてから、MDagModifierでシェイプの親を変える。

        Args:
            target (Transform): 新しい親。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: シェイプ・元の親・新しい親のどれかが、ロックされているかリファレンスのノードの場合。
            NotImplementedError: 新しい親に同じ名前の子がある場合。
        """
        self._require_editable_parents(target)
        name = om2.MFnDagNode(self.mnode()).name()
        parent_fn = om2.MFnDagNode(target.mpath())
        if any(om2.MFnDagNode(parent_fn.child(i)).name() == name for i in range(parent_fn.childCount())):
            raise NotImplementedError(f"fastのsetParentはシェイプの名前を変更しません: {target._full_name()}には{name}という名前の子があります")
        modifier = om2.MDagModifier()
        modifier.reparentNode(self.mnode(), target.mnode())
        modifier.doIt()
