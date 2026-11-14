"""メッシュの頂点フェース(フェースごとの頂点)と、頂点フェースの集まり。"""

import bisect

import maya.api.OpenMaya as om2

from ..decorator import _pick_alias
from ..maths.vector import Vector
from ..util import _UNSET, _world_space
from .component import Component, Components, _MultiIndexComponent, _MultiIndexComponents
from .face import Face
from .vertex import Vertex


def _face_vertex_layout(shape):
    """フェースごとの頂点の並びを取得する。

    Args:
        shape (Mesh): 型を確かめてあるメッシュ。

    Returns:
        tuple[list[int], list[int], list[int]]: (各フェースの先頭の通し番号, 各フェースの頂点数,
            通し番号の順に並べた頂点番号)。通し番号は、フェース番号の順、同じフェースの中では頂点の順に数える。
    """
    counts, vertices = shape._geometry_fn().getVertices()
    offsets = []
    total = 0
    for count in counts:
        offsets.append(total)
        total += count
    return offsets, list(counts), list(vertices)


class VertexFace(_MultiIndexComponent, Component):
    """メッシュの頂点フェース(``vtxFace[頂点][フェース]``)1つを表すクラス。

    頂点フェースは、フェースごとに法線や色を持たせるときの単位。

    持っている :attr:`index` は通し番号。フェース番号の順、同じフェースの中では頂点の順に数える
    (``om2.MFnMesh.getVertices`` の頂点の並び、``MItMeshFaceVertex`` の順と同じ)。
    ``(頂点, フェース)`` は :meth:`getMultiIndex` で取得する。
    """

    shape_type = "mesh"
    component_type = "vtxFace"
    index_size = 2

    def getVertex(self):
        """この頂点フェースの頂点を取得する。

        Returns:
            Vertex: 頂点。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return Vertex(self.shape, self.getMultiIndex()[0])

    def getFace(self):
        """この頂点フェースのフェースを取得する。

        Returns:
            Face: フェース。

        Raises:
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        return Face(self.shape, self.getMultiIndex()[1])

    def getNormal(self, worldSpace=_UNSET, *, ws=_UNSET):
        """頂点フェースの法線を、長さ1で取得する。

        ``MFnMesh.getFaceVertexNormal`` で求める。ハードエッジやロックした法線を反映した、表示に使う法線になる
        (``polyNormalPerVertex`` で取得した値と同じ)。

        Args:
            worldSpace (bool): Trueならワールド空間、Falseならオブジェクト空間。既定はFalse。
                ワールド空間は、Shapeのオブジェクトが持つDAGパスで求める。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。

        Returns:
            Vector: 長さ1の法線。

        Raises:
            TypeError: worldSpaceがboolでない場合、またはworldSpaceとwsを同時に指定した場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        space = om2.MSpace.kWorld if _world_space(worldSpace) else om2.MSpace.kObject
        vertex, face = self.getMultiIndex()
        return Vector(self.shape._geometry_fn().getFaceVertexNormal(face, vertex, space)).normal()

    @classmethod
    def _element_count(cls, shape):
        """頂点フェースの数(全フェースの頂点数の合計)を返す。

        Args:
            shape (Mesh): 型を確かめてあるメッシュ。

        Returns:
            int: 頂点フェースの数。
        """
        return shape._geometry_fn().numFaceVertices

    @classmethod
    def _multi_indices(cls, shape, indices, command=False):  # noqa: ARG003  # 基底が command= で呼ぶ契約の引数。
        """通し番号を ``(頂点, フェース)`` へ変換する。

        Args:
            shape (Mesh): 型を確かめてあるメッシュ。
            indices (Iterable[int]): 範囲を確かめてある通し番号。
            command (bool): Trueならcmdsで使う番号にする。頂点フェースではどちらも同じ番号になる。

        Returns:
            list[tuple[int, int]]: ``(頂点, フェース)``。指定した順に並ぶ。
        """
        offsets, _, vertices = _face_vertex_layout(shape)
        return [(vertices[index], bisect.bisect_right(offsets, index) - 1) for index in indices]

    @classmethod
    def _flat_indices(cls, shape, numbers):
        """``(頂点, フェース)`` を通し番号へ変換する。

        Args:
            shape (Mesh): 型を確かめてあるメッシュ。
            numbers (Iterable[tuple[int, int]]): 0以上の ``(頂点, フェース)``。

        Returns:
            list[int]: 通し番号。指定した順に並ぶ。

        Raises:
            IndexError: フェース番号が範囲の外にある場合、または頂点がそのフェースに無い場合。
        """
        offsets, counts, vertices = _face_vertex_layout(shape)
        result = []
        for vertex, face in numbers:
            if face >= len(offsets):
                raise IndexError(f"コンポーネントの番号が範囲外です: {(vertex, face)}")
            start = offsets[face]
            local = vertices[start : start + counts[face]]
            if vertex not in local:
                raise IndexError(f"頂点{vertex}はフェース{face}にありません")
            result.append(start + local.index(vertex))
        return result


class VertexFaces(_MultiIndexComponents, Components):
    """同じメッシュにある頂点フェースの集まりを表すクラス。

    番号の指定には、通し番号と ``(頂点, フェース)`` を混ぜて使える。名前は範囲にまとめない。
    """

    component_class = VertexFace
