# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""マテリアル接続と形状への割り当てを扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core.object import Object
from ..decorator import _edit_context, undoChunk
from .node import Node
from .objectSet import ObjectSet
from typing import Iterable
from mlib.components.face import Face
from mlib.components.face import Faces
from mlib.plugs.plug import Plug



class ShadingEngine(ObjectSet):
    """Mayaのレンダー用のセット(shadingEngine)を扱うクラス。

    表面・ボリューム・ディスプレイスメントの3種類のシェーダーを接続して持つ。
    マテリアルを割り当てるには、まず :meth:`setShader` でシェーダーを接続し、
    次に :meth:`assign` で形状やフェースへ割り当てる。

    .. code-block:: python

        import maya.cmds as cmds
        import mlib
        from mlib.nodes import ShadingEngine

        shader = mlib.createNode("lambert", name="red_MAT")
        shader.getPlug("color").set((1, 0, 0))
        engine = ShadingEngine(cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name="red_SG"))
        engine.setShader(shader)        # shader.outColor -> red_SG.surfaceShader
        engine.assign(mlib.getNode("pCube1"))  # 形状全体。フェースは Face/Faces や "pCube1.f[0:3]"
    """
    def getShaderPlug(self, kind: str = ...) -> Plug | None:
        """接続しているシェーダーの出力アトリビュートを取得する。

        Args:
            kind (str): シェーダーの種類。surface・volume・displacementのどれか。既定はsurface。

        Returns:
            Plug | None: 接続元の出力のPlug。接続されていなければNone。

        Raises:
            ValueError: kindがsurface/volume/displacement以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def getShader(self, kind: str = ...) -> Node | None:
        """接続しているシェーダーのノードを取得する。

        Args:
            kind (str): シェーダーの種類。surface・volume・displacementのどれか。既定はsurface。

        Returns:
            Node | None: シェーダーのノード。ノード型に合ったクラスのオブジェクトになる。接続されていなければNone。

        Raises:
            ValueError: kindがsurface/volume/displacement以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        ...
    def setShader(self, shader: Node | Plug | str, kind: str = ..., output: str | None = ..., *, fast: bool = ...) -> ShadingEngine:
        """シェーダーを接続する。

        例えば ``engine.setShader(lambert)`` は、``lambert.outColor`` を ``surfaceShader`` へ接続する。
        すでにある接続は置き換える。同じ接続元がすでに接続されていれば、何も変えない。
        形状への割り当ては :meth:`assign` で行う(クラスの説明の例を参照)。

        Args:
            shader (Node | Plug | str): シェーダーのノード、またはその出力のPlug。
            kind (str): シェーダーの種類。surface・volume・displacementのどれか。既定はsurface。
            output (str | None): shaderにノードを渡したときに使う出力のアトリビュート名。
                Noneならdisplacementではdisplacement、それ以外ではoutColorを使う。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。

        Returns:
            ShadingEngine: 自身。

        Raises:
            ValueError: kindが対応していない値の場合。
            RuntimeError: 接続元と接続先が同じアトリビュートの場合(fastの指定に関係なく)、
                またはMayaが接続を拒否した場合。
        """
        ...
    def assign(self, targets: Node | Face | Faces | str | Iterable) -> ShadingEngine:
        """形状またはフェースへ割り当てる。

        すでにある割り当ては、この割り当てに置き換わる。``cmds.sets(forceElement=...)`` と同じ。
        例えば ``engine.assign(mlib.getNode("pCube1"))`` は形状全体へ、
        ``engine.assign("pCube1.f[0:3]")`` はそのフェースだけへ割り当てる。
        シェーダーの接続は :meth:`setShader` で行う(クラスの説明の例を参照)。
        OpenMayaでの割り当ては ``cmds.sets`` より遅いため、fast引数は持たない。

        Args:
            targets (Node | Face | Faces | str | Iterable): 割り当てる対象。選択されているものには関係しない。

        Returns:
            ShadingEngine: 自身。targetsが空なら何も変えない。

        Raises:
            RuntimeError: Mayaが割り当てを拒否した場合。
        """
        ...
    def getMembers(self) -> list[Node | Face]:
        """割り当てている先を取得する。

        Returns:
            list[Node | Face]: 形状全体に割り当てていればそのノード、フェースに割り当てていれば
                フェース1つずつのオブジェクト。どれもインスタンスのDAGパスを保つ。
        """
        ...
    @staticmethod
    def _shader_attribute(kind: str) -> str:
        """シェーダーの種類を、接続先のアトリビュート名へ変える。

        Args:
            kind (str): surface・volume・displacementのどれか。

        Returns:
            str: 接続先のアトリビュート名。

        Raises:
            ValueError: kindが対応していない値の場合。
        """
        ...
