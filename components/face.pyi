# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""メッシュのフェースと、フェースの集まり。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..decorator import _pick_alias, _require_bool
from ..maths.vector import Vector, _vectors_of_points
from ..util import _UNSET, _checked_tolerance, _finite, _world_space
from .component import Component, Components
from .uv import UVs
from .vertex import Vertices
from typing import Any, Iterator, Literal, Sequence
from mlib.components.edge import Edges
from mlib.components.vertexFace import VertexFaces
from mlib.nodes.node import Node
from mlib.nodes.node import Nodes
from mlib.nodes.shadingEngine import ShadingEngine
from typing import overload

_FACE_KIND_QUERIES: dict


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
    def getColor(self, *, colorSet: str | None = ...) -> tuple[float, float, float, float] | None:
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
    def getArea(self, worldSpace: bool = ..., *, uv: bool = ..., uvSet: str | None = ..., ws: bool = ...) -> float:
        """面の面積を取得する。

        既定では、3Dの面積をcm²で返す(``MItMeshPolygon.getArea``)。
        ``uv=True`` なら、UV座標での面積を返す(``MItMeshPolygon.getUVArea``)。UV上の面積は単位が無く、
        3D形状やTransformのスケールには依存しない。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。``uv=True`` とは同時に指定できない。
            uv (bool): TrueならUV上の面積を返す。既定はFalse(3Dの面積)。
            uvSet (str | None): ``uv=True`` のときのUVセット。Noneは現在のセット。``uv=True`` のときだけ指定できる。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            float: 面積(cm²)。ワールド空間では、親のスケールも含む。``uv=True`` ならUV座標での面積。

        Raises:
            TypeError: worldSpaceかuvがboolでない場合、worldSpaceとwsを同時に指定した場合、``uv=True`` と
                worldSpace(ws)を同時に指定した場合、``uv=True`` でないのにuvSetを指定した場合、またはuvSetが文字列でもNoneでもない場合。
            ValueError: 指定したUVセットが無い場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、または ``uv=True`` で、フェースにUVが割り当てられていない場合。
        """
        ...
    @overload
    def getConnected(self, *, type: Literal["face"] = ...) -> Faces: ...
    @overload
    def getConnected(self, *, type: Literal["edge"]) -> Edges: ...
    @overload
    def getConnected(self, *, type: Literal["vertex"]) -> Vertices: ...
    @overload
    def getConnected(self, *, type: str = ...) -> Faces | Edges | Vertices:
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
    def getUVSetNames(self) -> list[str]:
        """このフェースに割り当てられたUVセット名を取得する。

        Returns:
            list[str]: Mayaの列挙順の名前。メッシュ全体のUVセット一覧とは異なる。

        Raises:
            IndexError: フェース番号が範囲外の場合。
            RuntimeError: Shapeが無効な場合。
        """
        ...
    def getPointAtUV(self, u: float, v: float, worldSpace: bool = ..., *, uvSet: str | None = ..., tolerance: float = ..., ws: bool = ...) -> Vector:
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
        ...
    def getUVAtPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, uvSet: str | None = ..., ws: bool = ...) -> tuple[float, float]:
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
    def isKind(self, kind: str, *, uvSet: str | None = ..., tolerance: float | None = ...) -> bool:
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
            uvSet (str | None): UVセット。Noneは現在のセット。``"zeroUVArea"``・``"uvReversed"`` のときだけ指定できる。
            tolerance (float | None): 面積の許容誤差。0以上の有限値。Noneなら1e-10。``"zeroArea"`` (cm²)・``"zeroUVArea"`` のときだけ指定できる。

        Returns:
            bool: その種類に当たればTrue。

        Raises:
            TypeError: kindが文字列でない場合、その種類で使わないuvSet・toleranceを指定した場合、
                またはuvSet・toleranceの型が合わない場合。
            ValueError: kindが決まった名前でない場合、toleranceが負か有限でない場合、またはUVセットが無い場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合、または ``"zeroUVArea"``・``"uvReversed"`` で、フェースにUVが割り当てられていない場合。
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
    def getShadingEngines(self) -> Nodes[ShadingEngine]:
        """各フェースに割り当てられたシェーディンググループを取得する。

        Returns:
            Nodes[ShadingEngine]: シェーディンググループ。重なりは除く。
        """
        ...
    def getMaterials(self) -> Nodes:
        """各フェースに割り当てられたマテリアルを取得する。

        Returns:
            Nodes: マテリアル。重なりは除く。
        """
        ...
    def extrude(self, *, curve: str | Node | None = ..., divisions: int = ..., keepFacesTogether: bool = ...) -> Node:
        """フェースを押し出す(``cmds.polyExtrudeFacet`` を1回実行する)。

        作成履歴を残し、作った polyExtrudeFace ノードを返す(押し出しの量はそのアトリビュートで変える)。
        ``curve`` を指定すると、そのカーブに沿って押し出す。Mayaのコマンドと同じく、終わると押し出したフェースが選ばれる。
        Undoが有効なら1回で戻せる。

        Args:
            curve (str | Node | None): 押し出しに沿わせるNURBSカーブ(Shape、またはShapeを持つTransform)。Noneなら沿わせない。
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
    def getColor(self, *, colorSet: str | None = ...) -> list[tuple[float, float, float, float] | None]:
        """各要素の :meth:`~mlib.components.face.Face.getColor` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getCenter(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.face.Face.getCenter` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getNormal(self, worldSpace: bool = ..., *, ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.face.Face.getNormal` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getArea(self, worldSpace: bool = ..., *, uv: bool = ..., uvSet: str | None = ..., ws: bool = ...) -> list[float]:
        """各要素の :meth:`~mlib.components.face.Face.getArea` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getConnected(self, *, type: str = ...) -> list[Faces | Edges | Vertices]:
        """各要素の :meth:`~mlib.components.face.Face.getConnected` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getVertexFaces(self) -> list[VertexFaces]:
        """各要素の :meth:`~mlib.components.face.Face.getVertexFaces` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUVs(self) -> list[UVs]:
        """各要素の :meth:`~mlib.components.face.Face.getUVs` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUVSetNames(self) -> list[list[str]]:
        """各要素の :meth:`~mlib.components.face.Face.getUVSetNames` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getPointAtUV(self, u: float, v: float, worldSpace: bool = ..., *, uvSet: str | None = ..., tolerance: float = ..., ws: bool = ...) -> list[Vector]:
        """各要素の :meth:`~mlib.components.face.Face.getPointAtUV` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getUVAtPoint(self, point: Sequence[float] | om2.MPoint | om2.MVector, worldSpace: bool = ..., *, uvSet: str | None = ..., ws: bool = ...) -> list[tuple[float, float]]:
        """各要素の :meth:`~mlib.components.face.Face.getUVAtPoint` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isOnBoundary(self) -> list[bool]:
        """各要素の :meth:`~mlib.components.face.Face.isOnBoundary` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def isKind(self, kind: str, *, uvSet: str | None = ..., tolerance: float | None = ...) -> list[bool]:
        """各要素の :meth:`~mlib.components.face.Face.isKind` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getTriangleCount(self) -> list[int]:
        """各要素の :meth:`~mlib.components.face.Face.getTriangleCount` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def getMultiIndex(self) -> list[tuple[int, ...]]:
        """各要素の :meth:`~mlib.components.component.Component.getMultiIndex` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
