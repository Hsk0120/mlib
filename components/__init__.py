"""Mayaのコンポーネント(頂点・エッジ・フェース・CV・UV・頂点フェース・曲面のCV・ラティスの点)とその要素群を公開する。

コンポーネントは、シェイプを形作る1つ1つの要素を指すオブジェクト。
頂点・CV・UVは、座標を取得できるほか、座標を書き込める(setPosition・setPositionsなど)。
頂点とCVは反転(mirror)もできる。
曲面のCVとラティスの点も、頂点・CVと同じように座標を取得・書き込みできる。
"""

from .component import Component, Components
from .cv import CV, CVs
from .edge import Edge, Edges
from .face import Face, Faces
from .latticePoint import LatticePoint, LatticePoints
from .pointComponent import PointComponent, PointComponents
from .surfaceCV import SurfaceCV, SurfaceCVs
from .uv import UV, UVs
from .vertex import Vertex, Vertices
from .vertexFace import VertexFace, VertexFaces

__all__ = [
    "CV",
    "UV",
    "CVs",
    "Component",
    "Components",
    "Edge",
    "Edges",
    "Face",
    "Faces",
    "LatticePoint",
    "LatticePoints",
    "PointComponent",
    "PointComponents",
    "SurfaceCV",
    "SurfaceCVs",
    "UVs",
    "Vertex",
    "VertexFace",
    "VertexFaces",
    "Vertices",
]
