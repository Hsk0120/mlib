"""メッシュのフェースと、フェースの集まり。"""

import maya.api.OpenMaya as om2

from ..decorator import _pick_alias
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _checked_tolerance, _finite, _world_space
from .component import Component, Components
from .uv import UVs
from .vertex import Vertices


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
        return self.shape.getFaceShadingEngines()[self.index]

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
            colorSet (str | None): カラーセット。Noneは現在のセット。

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
        values = self.shape.getFaceVertexColors(colorSet=name, faceVertices=self.getVertexFaces())
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

    def getArea(self, worldSpace=_UNSET, *, ws=_UNSET):
        """面の面積を、cm²で取得する。

        ``MItMeshPolygon.getArea`` で求める。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 面積(cm²)。ワールド空間では、親のスケールも含む。

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
        return it.getArea(space)

    def getConnectedFaces(self):
        """このフェースとエッジを共有するフェースを取得する。

        自身は含めない。``MItMeshPolygon.getConnectedFaces`` で求める。

        Returns:
            Faces: フェース。番号の小さい順に並び、重なりは無い。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return Faces(self.shape, sorted(set(self._iterator().getConnectedFaces())))

    def getConnectedEdges(self):
        """このフェースの頂点につながる、フェース外のエッジを取得する。

        フェース自身のエッジは含めない。getEdgesとは取得対象が異なる。

        Returns:
            Edges: 番号の小さい順に並ぶ、重複のないエッジ。

        Raises:
            IndexError: フェース番号が範囲外の場合。
            RuntimeError: Shapeが無効な場合。
        """
        # edge.pyがFaceを参照するため、循環を避けて呼出し時に読む。
        from .edge import Edges

        return Edges(self.shape, sorted(set(self._iterator().getConnectedEdges())))

    def getConnectedVertices(self):
        """このフェースとエッジでつながる、フェース外の頂点を取得する。

        フェース自身の頂点は含めない。getVerticesとは取得対象が異なる。

        Returns:
            Vertices: 番号の小さい順に並ぶ、重複のない頂点。

        Raises:
            IndexError: フェース番号が範囲外の場合。
            RuntimeError: Shapeが無効な場合。
        """
        return Vertices(self.shape, sorted(set(self._iterator().getConnectedVertices())))

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
            uvSet (str | None): UVセット。Noneは現在のセット。
            tolerance (float): UV判定の許容誤差。0以上。既定0。
            ws (bool): worldSpaceの短縮名。同時指定は不可。

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
            uvSet (str | None): UVセット。Noneは現在のセット。
            ws (bool): worldSpaceの短縮名。同時指定は不可。

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

    def getUVArea(self, *, uvSet=None):
        """フェースのUV上の面積を取得する。

        Args:
            uvSet (str | None): UVセット。Noneは現在のセット。

        Returns:
            float: UV座標での面積。3D形状やTransformのスケールには依存しない。

        Raises:
            TypeError: uvSetが文字列・None以外の場合。
            ValueError: UVセットが無い場合。
            RuntimeError: フェースにUVが割り当てられていない場合。
        """
        name = self.shape._resolve_uv_set(uvSet)
        iterator = self._iterator()
        if not iterator.hasUVs(name):
            raise RuntimeError(f"フェースにUVが割り当てられていません: {self.getFullName()}")
        return iterator.getUVArea(name)

    def isUVReversed(self, *, uvSet=None):
        """フェースのUVが時計回りに並ぶか調べる。

        Args:
            uvSet (str | None): UVセット。Noneは現在のセット。

        Returns:
            bool: 面の頂点順にUVをたどり、符号付き面積が負ならTrue。面積0ならFalse。

        Raises:
            TypeError: uvSetが文字列・None以外の場合。
            ValueError: UVセットが無い場合。
            RuntimeError: フェースにUVが割り当てられていない場合。
        """
        name = self.shape._resolve_uv_set(uvSet)
        iterator = self._iterator()
        if not iterator.hasUVs(name):
            raise RuntimeError(f"フェースにUVが割り当てられていません: {self.getFullName()}")
        us, vs = iterator.getUVs(name)
        # MItMeshPolygon.isUVReversedはPython API 2.0の引数変換が失敗する版があるため、UVの巻き方向から求める。
        return sum(u * vs[(index + 1) % len(us)] - us[(index + 1) % len(us)] * vs[index] for index, u in enumerate(us)) < 0

    def isZeroUVArea(self, *, uvSet=None, tolerance=1e-10):
        """フェースのUV上の面積が許容誤差以下か調べる。

        Args:
            uvSet (str | None): UVセット。Noneは現在のセット。
            tolerance (float): UV面積の許容誤差。0以上の有限値。

        Returns:
            bool: UV面積がtolerance以下ならTrue。

        Raises:
            TypeError: uvSet・toleranceの型が不正な場合。
            ValueError: UVセットが無いか、許容誤差が不正な場合。
            RuntimeError: フェースにUVが割り当てられていない場合。
        """
        tolerance = _checked_tolerance(tolerance)
        return self.getUVArea(uvSet=uvSet) <= tolerance

    def hasValidTriangulation(self):
        """フェースがMayaで有効な三角形分割を持つか調べる。

        Returns:
            bool: MItMeshPolygon.hasValidTriangulationの判定。
        """
        return self._iterator().hasValidTriangulation()

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

    def isPlanar(self):
        """フェースの頂点が、同じ平面の上にあるか調べる。

        ``MItMeshPolygon.isPlanar`` で調べる。

        Returns:
            bool: 平面ならTrue。三角形は常にTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().isPlanar()

    def isConvex(self):
        """凸多角形のフェースか調べる。

        ``MItMeshPolygon.isConvex`` で調べる。

        Returns:
            bool: 凸ならTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().isConvex()

    def isStarlike(self):
        """フェースがMayaの星状多角形の条件を満たすか調べる。

        MItMeshPolygon.isStarlikeの判定を返す。凸性や三角形分割の有効性とは別の照会。

        Returns:
            bool: 星状多角形ならTrue。

        Raises:
            IndexError: フェース番号が範囲外の場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().isStarlike()

    def isLamina(self):
        """ラミナフェースか調べる。

        ラミナフェースとは、別のフェースとすべてのエッジを共有している、重なったフェースのこと。
        ``MItMeshPolygon.isLamina`` で調べる。

        Returns:
            bool: ラミナフェースならTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().isLamina()

    def isHoled(self):
        """穴を持つフェースか調べる。

        ``MItMeshPolygon.isHoled`` で調べる。

        Returns:
            bool: 穴があればTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return self._iterator().isHoled()

    def isZeroArea(self, *, tolerance=1e-10):
        """面積がほぼ0のフェースか調べる。

        頂点が1点に集まったり、一直線に並んだりして潰れたフェースを見つけるのに使う。
        Shapeのオブジェクト空間での面積(``MItMeshPolygon.getArea``)で判定する。
        ``MItMeshPolygon.zeroArea`` は、頂点を1点へ集めたフェースでもFalseを返すことがあるので使わない。

        Args:
            tolerance (float): 面積の許容誤差(cm²)。0以上。既定は1e-10。

        Returns:
            bool: 面積がtolerance以下ならTrue。

        Raises:
            TypeError: toleranceが数値でない場合。
            ValueError: toleranceが負の場合、または有限でない場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        limit = _checked_tolerance(tolerance)
        return self._iterator().getArea() <= limit

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
        assignments = self.shape.getFaceShadingEngines()
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
