"""メッシュの頂点フェース(フェースごとの頂点)と、頂点フェースの集まり。"""

import bisect

import maya.api.OpenMaya as om2

from ..decorator import _pick_alias, _require_bool
from ..maths.vector import Vector
from ..util import _UNSET, _world_space
from .component import Component, Components
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


class VertexFace(Component):
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

    def setNormal(self, normal, worldSpace=_UNSET, *, fast=False, check=False, ws=_UNSET):
        """この面頂点の法線を設定し、ロックする。

        通常はpolyNormalPerVertexでUndoに記録する。fastは入力ヒストリの無いメッシュに限る。

        Args:
            normal (Sequence[float] | Vector): 長さが0でないXYZ。正規化して設定する。
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            check (bool): Trueなら有限な数値か書き込み前に確認する。既定FalseはMayaの受理に任せる。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fast・check・空間指定・法線の型が不正な場合。
            ValueError: 法線の成分が不正、長さ0、またはワールド変換が特異な場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        _require_bool(fast, "fast")
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        self.shape.setFaceVertexNormals([normal], worldSpace, fast=fast, check=check, faceVertices=self)

    def isNormalLocked(self):
        """この面頂点の法線がロックされているか調べる。

        Returns:
            bool: 法線がロックされていればTrue。
        """
        return self.shape.getFaceVertexNormalLocks(faceVertices=self)[0]

    def setNormalLocked(self, state=True, *, fast=False):
        """この面頂点の法線をロック、またはロック解除する。

        Args:
            state (bool): Trueはロック、Falseは解除。既定True。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。入力ヒストリの無いメッシュに限る。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: state・fastがbool以外の場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        _require_bool(fast, "fast")
        self.shape.setFaceVertexNormalsLocked(state, fast=fast, faceVertices=self)

    def getTangent(self, worldSpace=_UNSET, *, uvSet=None, ws=_UNSET):
        """この面頂点のUVのU方向に沿う接線を取得する。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            uvSet (str | None): UVセット。Noneは現在のセット。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            Vector: 独立した正規化済み接線。

        Raises:
            RuntimeError: UVが未割当・縮退しているか、接線を求められない場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self.shape.getFaceVertexTangents(worldSpace, uvSet=uvSet, faceVertices=self)[0]

    def getBinormal(self, worldSpace=_UNSET, *, uvSet=None, ws=_UNSET):
        """この面頂点のUVに基づく従法線を取得する。

        Args:
            worldSpace (bool): Trueはワールド空間、Falseはオブジェクト空間。既定False。
            uvSet (str | None): UVセット。Noneは現在のセット。
            ws (bool): worldSpaceの別名。同時指定は不可。

        Returns:
            Vector: 独立した正規化済み従法線。

        Raises:
            RuntimeError: UVが未割当・縮退しているか、従法線を求められない場合。
        """
        worldSpace = _pick_alias(worldSpace, ws, "worldSpace", "ws", default=False)
        return self.shape.getFaceVertexBinormals(worldSpace, uvSet=uvSet, faceVertices=self)[0]

    def getColor(self, *, colorSet=None):
        """この面頂点の色を取得する。

        Args:
            colorSet (str | None): カラーセット。Noneは現在のセット。

        Returns:
            tuple[float, float, float, float] | None: RGBA。色が未設定ならNone。
        """
        return self.shape.getFaceVertexColors(colorSet=colorSet, faceVertices=self)[0]

    def setColor(self, color, *, fast=False, colorSet=None):
        """この面頂点の色を設定する。

        通常はpolyColorPerVertexでUndoに記録する。fastは入力ヒストリの無いメッシュに限る。

        Args:
            color (Sequence[float] | om2.MColor): RGBまたはRGBAの有限値。RGBのAは1。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            colorSet (str | None): 既存のカラーセット。Noneは現在のセット(無ければcolorSet1を作る)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合、または色・セットの型が不正な場合。
            ValueError: 色の成分が不正、またはセットが無い場合。
            RuntimeError: メッシュがロックされているか、Mayaが編集を拒否した場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        _require_bool(fast, "fast")
        self.shape.setFaceVertexColors([color], fast=fast, colorSet=colorSet, faceVertices=self)

    def removeColor(self, *, fast=False, colorSet=None):
        """この面頂点のカラー割り当てを解除する。

        カラーセットは残し、getColorでNoneになる状態へ戻す。
        ヒストリの制限はMesh.removeFaceVertexColorsと同じ。通常はUndoに記録する。

        Args:
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。
            colorSet (str | None): 既存のカラーセット。Noneは現在のセット。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fastがbool以外の場合、またはcolorSetの型が不正な場合。
            ValueError: 指定したカラーセットが無い場合。
            RuntimeError: メッシュが編集不可か、通常経路で未対応のヒストリがある場合。
            NotImplementedError: fastで入力ヒストリのあるメッシュを編集する場合。
        """
        _require_bool(fast, "fast")
        self.shape.removeFaceVertexColors(fast=fast, colorSet=colorSet, faceVertices=self)

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


class VertexFaces(Components):
    """同じメッシュにある頂点フェースの集まりを表すクラス。

    番号の指定には、通し番号と ``(頂点, フェース)`` を混ぜて使える。名前は範囲にまとめない。
    """

    component_class = VertexFace
