# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""メッシュのフェースと、フェースの集まり。"""

import maya.api.OpenMaya as om2
from ..decorator import _pick_alias
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _checked_tolerance, _world_space
from .component import Component, Components
from .uv import UVs
from .vertex import Vertices
from typing import Any, Iterator
from mlib.components.edge import Edges
from mlib.components.vertexFace import VertexFaces
from mlib.nodes.node import Node
from mlib.nodes.shadingEngine import ShadingEngine
from typing import overload



class Face(Component):
    """メッシュのフェース1つを表すクラス。"""
    shape_type: str
    component_type: str
    count_attribute: str
    def getShadingEngine(self) -> ShadingEngine | None:
        """このフェースに割り当てられたシェーディンググループを取得する。

        Shapeのオブジェクトが持つDAGパスのインスタンスでの割り当てを調べる。

        Returns:
            ShadingEngine | None: 割り当てられたシェーディンググループ。無ければNone。
        """
        ...
    def getMaterial(self) -> Node | None:
        """このフェースに割り当てられたサーフェスシェーダーを取得する。

        Returns:
            Node | None: 割り当てられたサーフェスシェーダー。無ければNone。
        """
        ...
    def getVertices(self) -> Vertices:
        """フェースの頂点を取得する。

        Returns:
            Vertices: 頂点。Mayaが返すつながりの順に並ぶ。
        """
        ...
    def getEdges(self) -> Edges:
        """この面のエッジを取得する。

        :meth:`Faces.getEdges` と同じ規則。

        Returns:
            Edges: エッジ。番号の小さい順に並び、重なりは無い。
        """
        ...
    def getCenter(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def getNormal(self, worldSpace: bool = ..., *, ws: bool = ...) -> Vector:
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
        ...
    def getArea(self, worldSpace: bool = ..., *, ws: bool = ...) -> float:
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
        ...
    def getConnectedFaces(self) -> Faces:
        """このフェースとエッジを共有するフェースを取得する。

        自身は含めない。``MItMeshPolygon.getConnectedFaces`` で求める。

        Returns:
            Faces: フェース。番号の小さい順に並び、重なりは無い。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getVertexFaces(self) -> VertexFaces:
        """このフェースの頂点フェースを、フェースの頂点の順に取得する。

        Returns:
            VertexFaces: 頂点フェース。フェースの頂点を回る順に並ぶ。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getUVs(self) -> UVs:
        """このフェースの、現在のUVセットのUVを取得する。

        Returns:
            UVs: UV。フェースの頂点を回る順に並び、重なりは無い。UVの無いフェースでは空。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isOnBoundary(self) -> bool:
        """メッシュの縁に接するフェースか調べる。

        縁とは、接する面が1つだけのエッジのこと。``MItMeshPolygon.onBoundary`` で調べる。

        Returns:
            bool: 縁のエッジを持てばTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isPlanar(self) -> bool:
        """フェースの頂点が、同じ平面の上にあるか調べる。

        ``MItMeshPolygon.isPlanar`` で調べる。

        Returns:
            bool: 平面ならTrue。三角形は常にTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isConvex(self) -> bool:
        """凸多角形のフェースか調べる。

        ``MItMeshPolygon.isConvex`` で調べる。

        Returns:
            bool: 凸ならTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isLamina(self) -> bool:
        """ラミナフェースか調べる。

        ラミナフェースとは、別のフェースとすべてのエッジを共有している、重なったフェースのこと。
        ``MItMeshPolygon.isLamina`` で調べる。

        Returns:
            bool: ラミナフェースならTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isHoled(self) -> bool:
        """穴を持つフェースか調べる。

        ``MItMeshPolygon.isHoled`` で調べる。

        Returns:
            bool: 穴があればTrue。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def isZeroArea(self, tolerance: float = ...) -> bool:
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
        ...
    def getTriangleCount(self) -> int:
        """フェースを三角形に分けたときの、三角形の数を取得する。

        ``MItMeshPolygon.numTriangles`` で求める。

        Returns:
            int: 三角形の数。``cmds.polyEvaluate(triangle=True)`` を1フェースごとに数えた値と同じ。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def _iterator(self) -> om2.MItMeshPolygon:
        """番号を確かめて、このフェースに合わせた ``om2.MItMeshPolygon`` を返す。

        Returns:
            om2.MItMeshPolygon: このフェースを指す反復子。
        """
        ...
_FACE_GET_VERTICES: Any


class Faces(Components):
    """同じメッシュにあるフェースの集まりを表すクラス。"""
    def __iter__(self) -> Iterator[Face]: ...
    @overload
    def __getitem__(self, index: int) -> Face: ...
    @overload
    def __getitem__(self, index: slice) -> Faces: ...
    component_class: Any
    def getShadingEngines(self) -> list[ShadingEngine]:
        """各フェースに割り当てられたシェーディンググループを取得する。

        Returns:
            list[ShadingEngine]: シェーディンググループ。重なりは除く。
        """
        ...
    def getMaterials(self) -> list[Node]:
        """各フェースに割り当てられたマテリアルを取得する。

        Returns:
            list[Node]: マテリアル。重なりは除く。
        """
        ...
    def getVertices(self) -> Vertices:
        """各フェースの頂点を取得する。

        Returns:
            Vertices: 頂点。フェースを持っている順に集め、重なりは除く。
        """
        ...
    def getEdges(self) -> Edges:
        """持っている面のエッジを取得する。

        ``cmds.polyListComponentConversion(toEdge=True)`` と同じエッジになる。選択は変えない。

        Returns:
            Edges: エッジ。番号の小さい順に並び、重なりは無い。面が空なら空。

        Raises:
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getShadingEngine(self) -> list[ShadingEngine | None]:
        """各要素の :meth:`~mlib.components.face.Face.getShadingEngine` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getMaterial(self) -> list[Node | None]:
        """各要素の :meth:`~mlib.components.face.Face.getMaterial` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getCenter(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.face.Face.getCenter` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNormal(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.face.Face.getNormal` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getArea(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[float]:
        """各要素の :meth:`~mlib.components.face.Face.getArea` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getConnectedFaces(self) -> list[Faces]:
        """各要素の :meth:`~mlib.components.face.Face.getConnectedFaces` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getVertexFaces(self) -> list[VertexFaces]:
        """各要素の :meth:`~mlib.components.face.Face.getVertexFaces` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUVs(self) -> list[UVs]:
        """各要素の :meth:`~mlib.components.face.Face.getUVs` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isOnBoundary(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.face.Face.isOnBoundary` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isPlanar(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.face.Face.isPlanar` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isConvex(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.face.Face.isConvex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isLamina(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.face.Face.isLamina` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isHoled(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.face.Face.isHoled` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isZeroArea(self, tolerance: float = ...) -> list[bool]:
        """各要素の :meth:`~mlib.components.face.Face.isZeroArea` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTriangleCount(self) -> list[int]:
        """各要素の :meth:`~mlib.components.face.Face.getTriangleCount` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
