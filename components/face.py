"""メッシュのフェースと、フェースの集まり。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..decorator import _pick_alias, _require_bool
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _checked_tolerance, _finite, _world_space
from .component import Component, Components
from .uv import UVs
from .vertex import Vertices

#: :meth:`Face.isKind` の種類の名前と、``om2.MItMeshPolygon`` の判定メソッド名の対応(引数を取らないもの)。
_FACE_KIND_QUERIES = {
    "planar": "isPlanar",
    "convex": "isConvex",
    "starlike": "isStarlike",
    "lamina": "isLamina",
    "holed": "isHoled",
    "validTriangulation": "hasValidTriangulation",
}


class Face(Component):
    """メッシュのフェース1つを表すクラス。"""

    shape_type = "mesh"
    component_type = "f"
    count_attribute = "getNumPolygons"

    def getShadingEngine(self):
        """このフェースに割り当てられたシェーディンググループを取得する。

        Shapeのオブジェクトが持つDAGパスのインスタンスでの割り当てを調べる。

        Returns:
            ShadingEngine | None: 割り当てられたシェーディンググループ。無ければNone。
        """
        self._require_valid()
        return self.shape.getShadingEngines(perFace=True)[self.index]

    def getMaterial(self):
        """このフェースに割り当てられたサーフェスシェーダーを取得する。

        Returns:
            Node | None: 割り当てられたサーフェスシェーダー。無ければNone。
        """
        group = self.getShadingEngine()
        return group.getShader() if group is not None else None

    def getVertices(self):
        """フェースの頂点を取得する。

        Returns:
            Vertices: 頂点。Mayaが返すつながりの順に並ぶ。
        """
        self._require_valid()
        return Vertices(self.shape, self.shape._geometry_fn().getPolygonVertices(self.index))

    def getEdges(self):
        """この面のエッジを取得する。

        :meth:`Faces.getEdges` と同じ規則。

        Returns:
            Edges: エッジ。番号の小さい順に並び、重なりは無い。
        """
        return Faces(self.shape, [self.index]).getEdges()

    def getColor(self, *, colorSet=None):
        """フェースの平均カラーをMayaの方法で取得する。

        面頂点の未設定カラーを含む平均の扱いはMItMeshPolygon.getColorに従う。
        全コーナーが未設定ならNoneを返す。

        Args:
            colorSet (str | None): カラーセット。Noneは現在のセット。既定はNone。

        Returns:
            tuple[float, float, float, float] | None: RGBAの平均。カラーが無ければNone。

        Raises:
            TypeError: colorSetが文字列・None以外の場合。
            ValueError: 指定したカラーセットが無い場合。
            RuntimeError: フェースが無効な場合。
        """
        self._require_valid()
        fn = self.shape._geometry_fn()
        name = self.shape._resolve_color_set(colorSet, fn)
        if name is None:
            return None
        values = self.shape.getVertexColors(perFace=True, colorSet=name, faceVertices=self.getVertexFaces())
        if all(value is None for value in values):
            return None
        return tuple(self._iterator().getColor(name))

    def getCenter(self, worldSpace=_UNSET, *, ws=_UNSET):
        """面の中心を取得する。

        中心は頂点の位置の平均で、``MItMeshPolygon.center`` で求める。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 中心の位置(cm)。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        self._require_valid()
        it = om2.MItMeshPolygon(self.shape.mpath())
        it.setIndex(self.index)
        return _vectors_of_points([it.center(space)])[0]

    def getNormal(self, worldSpace=_UNSET, *, ws=_UNSET):
        """面の法線を、長さ1で取得する。

        ``MFnMesh.getPolygonNormal`` で求める。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 長さ1の法線。向きは、面の頂点を回る順で決まる。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        self._require_valid()
        return Vector(self.shape._geometry_fn().getPolygonNormal(self.index, space)).normal()

    def getArea(self, worldSpace=_UNSET, *, uv=False, uvSet=None, ws=_UNSET):
        """面の面積を取得する。

        既定では、3Dの面積をcm²で返す(``MItMeshPolygon.getArea``)。
        ``uv=True`` なら、UV座標での面積を返す(``MItMeshPolygon.getUVArea``)。UV上の面積は単位が無く、
        3D形状やTransformのスケールには依存しない。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。``uv=True`` とは同時に指定できない。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            uv (bool): TrueならUV上の面積を返す。既定はFalse(3Dの面積)。
            uvSet (str | None): ``uv=True`` のときのUVセット。Noneは現在のセット。``uv=True`` のときだけ指定できる。既定はNone。

        Returns:
            float: 面積(cm²)。ワールド空間では、親のスケールも含む。``uv=True`` ならUV座標での面積。

        Raises:
            TypeError: worldSpaceかuvがboolでない場合、worldSpaceとwsを同時に指定した場合、``uv=True`` と
                worldSpace(ws)を同時に指定した場合、``uv=True`` でないのにuvSetを指定した場合、またはuvSetが文字列でもNoneでもない場合。
            ValueError: 指定したUVセットが無い場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、または ``uv=True`` で、フェースにUVが割り当てられていない場合。
        """
        _require_bool(uv, "uv")
        if uv:
            if worldSpace is not _UNSET or ws is not _UNSET:
                raise TypeError("uv=TrueとworldSpace(ws)は同時に指定できません")
            name = self.shape._resolve_uv_set(uvSet)
            iterator = self._iterator()
            if not iterator.hasUVs(name):
                raise RuntimeError(f"フェースにUVが割り当てられていません: {self._full_name()}")
            return iterator.getUVArea(name)
        if uvSet is not None:
            raise TypeError("uvSetはuv=Trueのときだけ指定できます")
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        self._require_valid()
        it = om2.MItMeshPolygon(self.shape.mpath())
        it.setIndex(self.index)
        return it.getArea(space)

    def getConnected(self, *, type="face"):
        """このフェースの隣にあるコンポーネントを取得する。

        ``type`` で、取得する種類を選ぶ。どれも自身(このフェースのエッジ・頂点)は含めない。

        - ``"face"``: このフェースとエッジを共有するフェース(``MItMeshPolygon.getConnectedFaces``)。
        - ``"edge"``: このフェースの頂点につながる、フェース外のエッジ。フェース自身のエッジは :meth:`getEdges` で取得する。
        - ``"vertex"``: このフェースとエッジでつながる、フェース外の頂点。フェース自身の頂点は :meth:`getVertices` で取得する。

        Args:
            type (str): 取得する種類。``"face"``・``"edge"``・``"vertex"``。既定は ``"face"``。

        Returns:
            Faces | Edges | Vertices: ``type`` に合う集まり。番号の小さい順に並び、重なりは無い。

        Raises:
            TypeError: typeが文字列でない場合。
            ValueError: typeが ``"face"``・``"edge"``・``"vertex"`` のどれでもない場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        if not isinstance(type, str):
            raise TypeError(f"typeは文字列で指定してください: {type.__class__.__name__}")
        if type == "face":
            return Faces(self.shape, sorted(set(self._iterator().getConnectedFaces())))
        if type == "edge":
            # edge.pyがFaceを参照するため、循環を避けて呼出し時に読む。
            from .edge import Edges

            return Edges(self.shape, sorted(set(self._iterator().getConnectedEdges())))
        if type == "vertex":
            return Vertices(self.shape, sorted(set(self._iterator().getConnectedVertices())))
        raise ValueError(f'typeは"face"・"edge"・"vertex"のどれかで指定してください: {type!r}')

    def getVertexFaces(self):
        """このフェースの頂点フェースを、フェースの頂点の順に取得する。

        Returns:
            VertexFaces: 頂点フェース。フェースの頂点を回る順に並ぶ。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        # vertexFace.py が face.py を import するため、循環を避けて呼出し時に読む。
        from .vertexFace import VertexFaces

        self._require_valid()
        vertices = self.shape._geometry_fn().getPolygonVertices(self.index)
        return VertexFaces(self.shape, [(vertex, self.index) for vertex in vertices])

    def getUVs(self):
        """このフェースの、現在のUVセットのUVを取得する。

        Returns:
            UVs: UV。フェースの頂点を回る順に並び、重なりは無い。UVの無いフェースでは空。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        iterator = self._iterator()
        uv_set = self.shape._geometry_fn().currentUVSetName()
        indices = []
        if iterator.hasUVs(uv_set):
            indices = [iterator.getUVIndex(local, uv_set) for local in range(iterator.polygonVertexCount())]
        return UVs(self.shape, indices)

    def getUVSetNames(self):
        """このフェースに割り当てられたUVセット名を取得する。

        Returns:
            list[str]: Mayaの列挙順の名前。メッシュ全体のUVセット一覧とは異なる。

        Raises:
            IndexError: フェース番号が範囲外の場合。
            RuntimeError: Shapeが無効な場合。
        """
        return list(self._iterator().getUVSetNames())

    def getPointAtUV(self, u, v, worldSpace=_UNSET, *, uvSet=None, tolerance=0.0, ws=_UNSET):
        """このフェース内のUV座標に対応する3D位置を取得する。

        別フェースに重なるUVがあっても探索しない。境界の判定はMayaに従う。

        Args:
            u (float): 有限なU座標。
            v (float): 有限なV座標。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            uvSet (str | None): UVセット。Noneは現在のセット。既定はNone。
            tolerance (float): UV判定の許容誤差。0以上。既定0。

        Returns:
            Vector: 対応する位置(cm)の新しい値。

        Raises:
            TypeError: 数値・UVセット・空間指定の型が不正、または長短名を同時指定した場合。
            ValueError: 数値が有限でない、許容誤差が負、またはUVセットがない場合。
            IndexError: フェース番号が範囲外の場合。
            RuntimeError: Shapeが無効、UV未割り当て、またはフェース内に対応点がない場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        coords = (_finite(u, "u"), _finite(v, "v"))
        limit = _checked_tolerance(tolerance)
        name = self.shape._resolve_uv_set(uvSet)
        point = self._iterator().getPointAtUV(coords, space, name, limit)
        return _vectors_of_points([point])[0]

    def getUVAtPoint(self, point, worldSpace=_UNSET, *, uvSet=None, ws=_UNSET):
        """指定位置に最も近い、このフェース上の点のUV座標を取得する。

        メッシュ全体の最短点ではなく、このフェースだけを調べる。

        Args:
            point (Sequence[float] | om2.MPoint | om2.MVector): 入力位置(cm)。worldSpaceと同じ空間。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            uvSet (str | None): UVセット。Noneは現在のセット。既定はNone。

        Returns:
            tuple[float, float]: (U, V)の新しい値。

        Raises:
            TypeError: 入力・UVセット・空間指定の型が不正、または長短名を同時指定した場合。
            ValueError: 入力が3成分の有限値でない、またはUVセットがない場合。
            IndexError: フェース番号が範囲外の場合。
            RuntimeError: Shapeが無効、UV未割り当て、またはMayaが照会を拒否した場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        value = self.shape._resolve_query_point(point)
        name = self.shape._resolve_uv_set(uvSet)
        return tuple(self._iterator().getUVAtPoint(value, space, name))

    def isOnBoundary(self):
        """メッシュの縁に接するフェースか調べる。

        縁とは、接する面が1つだけのエッジのこと。``MItMeshPolygon.onBoundary`` で調べる。

        Returns:
            bool: 縁のエッジを持てばTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().onBoundary()

    def isKind(self, kind, *, uvSet=None, tolerance=None):
        """フェースが、名前で選んだ種類の形に当たるか調べる。

        ``kind`` で、調べる内容を選ぶ。

        - ``"planar"``: 頂点が同じ平面の上にある(``MItMeshPolygon.isPlanar``)。三角形は常にTrue。
        - ``"convex"``: 凸多角形である(``MItMeshPolygon.isConvex``)。
        - ``"starlike"``: Mayaの星状多角形の条件を満たす(``MItMeshPolygon.isStarlike``)。凸かどうか・三角形分割が有効かとは別の判定。
        - ``"lamina"``: ラミナフェース(別のフェースとすべてのエッジを共有している、重なったフェース)である(``MItMeshPolygon.isLamina``)。
        - ``"holed"``: 穴を持つ(``MItMeshPolygon.isHoled``)。
        - ``"validTriangulation"``: Mayaで有効な三角形分割を持つ(``MItMeshPolygon.hasValidTriangulation``)。
        - ``"zeroArea"``: 面積がtolerance以下である。頂点が1点に集まったり、一直線に並んだりして潰れたフェースを見つけるのに使う。
          Shapeのオブジェクト空間での面積(``MItMeshPolygon.getArea``)で判定する。
          ``MItMeshPolygon.zeroArea`` は、頂点を1点へ集めたフェースでもFalseを返すことがあるので使わない。
        - ``"zeroUVArea"``: UV上の面積(:meth:`getArea` の ``uv=True``)がtolerance以下である。
        - ``"uvReversed"``: UVが時計回りに並ぶ。面の頂点順にUVをたどり、符号付き面積が負ならTrue(面積0ならFalse)。

        メッシュの縁に接するかは :meth:`isOnBoundary` で調べる。

        Args:
            kind (str): 調べる種類。上の名前のどれか。
            uvSet (str | None): UVセット。Noneは現在のセット。``"zeroUVArea"``・``"uvReversed"`` のときだけ指定できる。既定はNone。
            tolerance (float | None): 面積の許容誤差。0以上の有限値。Noneなら1e-10。``"zeroArea"`` (cm²)・``"zeroUVArea"`` のときだけ指定できる。既定はNone。

        Returns:
            bool: その種類に当たればTrue。

        Raises:
            TypeError: kindが文字列でない場合、その種類で使わないuvSet・toleranceを指定した場合、
                またはuvSet・toleranceの型が合わない場合。
            ValueError: kindが決まった名前でない場合、toleranceが負か有限でない場合、またはUVセットが無い場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、または ``"zeroUVArea"``・``"uvReversed"`` で、フェースにUVが割り当てられていない場合。
        """
        if not isinstance(kind, str):
            raise TypeError(f"kindは文字列で指定してください: {type(kind).__name__}")
        uses_uv_set = kind in ("zeroUVArea", "uvReversed")
        uses_tolerance = kind in ("zeroArea", "zeroUVArea")
        if not (kind in _FACE_KIND_QUERIES or uses_uv_set or uses_tolerance):
            names = "・".join(f'"{name}"' for name in (*_FACE_KIND_QUERIES, "zeroArea", "zeroUVArea", "uvReversed"))
            raise ValueError(f"kindは{names}のどれかで指定してください: {kind!r}")
        if uvSet is not None and not uses_uv_set:
            raise TypeError(f'uvSetはkindが"zeroUVArea"・"uvReversed"のときだけ指定できます: {kind!r}')
        if tolerance is not None and not uses_tolerance:
            raise TypeError(f'toleranceはkindが"zeroArea"・"zeroUVArea"のときだけ指定できます: {kind!r}')
        if uses_tolerance:
            limit = _checked_tolerance(1e-10 if tolerance is None else tolerance)
            if kind == "zeroUVArea":
                return self.getArea(uv=True, uvSet=uvSet) <= limit
            return self._iterator().getArea() <= limit
        if kind == "uvReversed":
            name = self.shape._resolve_uv_set(uvSet)
            iterator = self._iterator()
            if not iterator.hasUVs(name):
                raise RuntimeError(f"フェースにUVが割り当てられていません: {self._full_name()}")
            us, vs = iterator.getUVs(name)
            # MItMeshPolygon.isUVReversedはPython API 2.0の引数変換が失敗する版があるため、UVの巻き方向から求める。
            return sum(u * vs[(index + 1) % len(us)] - us[(index + 1) % len(us)] * vs[index] for index, u in enumerate(us)) < 0
        return getattr(self._iterator(), _FACE_KIND_QUERIES[kind])()

    def getTriangleCount(self):
        """フェースを三角形に分けたときの、三角形の数を取得する。

        ``MItMeshPolygon.numTriangles`` で求める。

        Returns:
            int: 三角形の数。``cmds.polyEvaluate(triangle=True)`` を1フェースごとに数えた値と同じ。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().numTriangles()

    def _iterator(self):
        """番号を確かめて、このフェースに合わせた ``om2.MItMeshPolygon`` を返す。

        Returns:
            om2.MItMeshPolygon: このフェースを指す反復子。
        """
        self._require_valid()
        iterator = om2.MItMeshPolygon(self.shape.mpath())
        iterator.setIndex(self.index)
        return iterator


_FACE_GET_VERTICES = Face.getVertices


class Faces(Components):
    """同じメッシュにあるフェースの集まりを表すクラス。"""

    component_class = Face

    def getShadingEngines(self):
        """各フェースに割り当てられたシェーディンググループを取得する。

        Returns:
            Nodes[ShadingEngine]: シェーディンググループ。重なりは除く。
        """
        result = []
        assignments = self.shape.getShadingEngines(perFace=True)
        for face in self:
            face._require_valid()
            group = assignments[face.index]
            if group is not None and group not in result:
                result.append(group)
        # 循環参照の回避: nodesがcomponentsを参照するため、使う時点で読み込む。
        from ..nodes.node import Nodes

        return Nodes._wrap(result)

    def getMaterials(self):
        """各フェースに割り当てられたマテリアルを取得する。

        Returns:
            Nodes: マテリアル。重なりは除く。
        """
        result = []
        for group in self.getShadingEngines():
            material = group.getShader()
            if material is not None and material not in result:
                result.append(material)
        # 循環参照の回避: nodesがcomponentsを参照するため、使う時点で読み込む。
        from ..nodes.node import Nodes

        return Nodes._wrap(result)

    def extrude(self, *, curve=None, divisions=1, keepFacesTogether=True):
        """フェースを押し出す(``cmds.polyExtrudeFacet`` を1回実行する)。

        作成履歴を残し、作った polyExtrudeFace ノードを返す(押し出しの量はそのアトリビュートで変える)。
        ``curve`` を指定すると、そのカーブに沿って押し出す。Mayaのコマンドと同じく、終わると押し出したフェースが選ばれる。
        Undoが有効なら1回で戻せる。

        Args:
            curve (str | Node | None): 押し出しに沿わせるNURBSカーブ(Shape、またはShapeを持つTransform)。Noneなら沿わせない。既定はNone。
            divisions (int): 押し出しの分割数。1以上。既定は1。
            keepFacesTogether (bool): Trueなら、隣り合うフェースを1つにつないだまま押し出す。既定はTrue。

        Returns:
            Node: 作った polyExtrudeFace ノード。

        Raises:
            TypeError: divisionsがintでない場合、keepFacesTogetherがboolでない場合、
                またはcurveがNURBSカーブでない場合。
            ValueError: フェースが空の場合、またはdivisionsが1未満の場合。
            RuntimeError: シェイプが無効な場合、またはMayaが押し出しを拒否した場合。
        """
        # 循環参照の回避: nodesがcomponentsを参照するため、使う時点で読み込む。
        from ..nodes.node import Node

        if isinstance(divisions, bool) or not isinstance(divisions, int):
            raise TypeError(f"divisionsはintで指定してください: {type(divisions).__name__}")
        if divisions < 1:
            raise ValueError(f"divisionsは1以上で指定してください: {divisions}")
        _require_bool(keepFacesTogether, "keepFacesTogether")
        if not len(self):
            raise ValueError("押し出すフェースがありません")
        self._require_valid()
        flags = {"divisions": divisions, "keepFacesTogether": keepFacesTogether, "constructionHistory": True}
        if curve is not None:
            node = curve if isinstance(curve, Node) else Node(curve)
            shapes = (
                [node]
                if node.isType("nurbsCurve")
                else [shape for shape in node.getShape(all=True) if shape.isType("nurbsCurve")]
                if node.isType("transform")
                else []
            )
            if len(shapes) != 1:
                raise TypeError(f"curveはNURBSカーブを1つ指定してください: {node._full_name()}")
            flags["inputCurve"] = shapes[0]._full_name()
        return Node(cmds.polyExtrudeFacet(self.getNames(full=True, compact=True), **flags)[0])

    def getVertices(self):
        """各フェースの頂点を取得する。

        Returns:
            Vertices: 頂点。フェースを持っている順に集め、重なりは除く。
        """
        if not (self._uses_standard_iteration(Face) and self._uses_standard_vertices() and Face.getVertices is _FACE_GET_VERTICES):
            return Vertices(self.shape, (v.index for item in self for v in item.getVertices()))
        indices = self._mesh_vertex_indices("numPolygons", "getPolygonVertices")
        return Vertices(self.shape, indices)

    def getEdges(self):
        """持っている面のエッジを取得する。

        ``cmds.polyListComponentConversion(toEdge=True)`` と同じエッジになる。選択は変えない。

        Returns:
            Edges: エッジ。番号の小さい順に並び、重なりは無い。面が空なら空。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        # edge.py が face.py を import するため、循環を避けて呼出し時に読む。
        from .edge import Edges

        self._require_valid()
        iterator = om2.MItMeshPolygon(self.shape.mpath())
        found = set()
        for index in self._indices:
            iterator.setIndex(index)
            found.update(iterator.getEdges())
        return Edges(self.shape, sorted(found))
