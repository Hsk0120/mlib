"""マテリアル接続と形状への割り当てを扱う。"""

import maya.api.OpenMaya as om2
import maya.cmds as cmds

from ..core.object import Object
from ..decorator import _edit_context, undoChunk
from .node import Node
from .objectSet import ObjectSet


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

    def getShaderPlug(self, kind="surface"):
        """接続しているシェーダーの出力アトリビュートを取得する。

        Args:
            kind (str): シェーダーの種類。surface・volume・displacementのどれか。既定はsurface。

        Returns:
            Plug | None: 接続元の出力のPlug。接続されていなければNone。

        Raises:
            ValueError: kindがsurface/volume/displacement以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        return self.getPlug(self._shader_attribute(kind)).getSource()

    def getShader(self, kind="surface"):
        """接続しているシェーダーのノードを取得する。

        Args:
            kind (str): シェーダーの種類。surface・volume・displacementのどれか。既定はsurface。

        Returns:
            Node | None: シェーダーのノード。ノード型に合ったクラスのオブジェクトになる。接続されていなければNone。

        Raises:
            ValueError: kindがsurface/volume/displacement以外の場合。
            RuntimeError: ノードが無効な場合。
        """
        plug = self.getShaderPlug(kind)
        return None if plug is None else plug.getNode()

    def setShader(self, shader, kind="surface", output=None, *, fast=False):
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
        with _edit_context("mlibShadingEngineSetShader", fast):
            # plugs は nodes を参照するため、循環importを避けて呼出し時に取得する。
            from ..plugs.plug import Plug

            target = self.getPlug(self._shader_attribute(kind))
            if isinstance(shader, Plug) or isinstance(shader, str) and "." in shader:
                source = Plug._resolve_input(shader)
            else:
                source = Node._resolve_input(shader).getPlug(output or ("displacement" if kind == "displacement" else "outColor"))
            if source == target:
                # fastのMDGModifierは自己接続を拒否しないため、cmdsの経路と同じく先に拒否する。
                raise RuntimeError(f"アトリビュート{target.getFullName()}を自分自身へは接続できません")
            # 同じ割り当ての再実行は、既存の同じ接続をそのまま残して成功させる。
            source.connectTo(target, force=True, safe=True, fast=fast)
            return self

    def assign(self, targets):
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
        with undoChunk("mlibShadingEngineAssign"):
            names = Object._input_names(targets)
            if names:
                cmds.sets(names, edit=True, forceElement=self.getFullName())
            return self

    def getMembers(self):
        """割り当てている先を取得する。

        Returns:
            list[Node | Face]: 形状全体に割り当てていればそのノード、フェースに割り当てていれば
                フェース1つずつのオブジェクト。どれもインスタンスのDAGパスを保つ。
        """
        selection = om2.MFnSet(self.mnode()).getMembers(False)
        result = []
        for index in range(selection.length()):
            path, component = selection.getComponent(index)
            # 選択リストから取得したばかりのパスなので、入力の再解決を省いてラッパーにする。
            node = Node._wrap_dag_path(path)
            if component.hasFn(om2.MFn.kMeshPolygonComponent):
                fn = om2.MFnSingleIndexedComponent(component)
                indices = range(om2.MFnMesh(path).numPolygons) if fn.isComplete else fn.getElements()
                result.extend(node.getFace(value) for value in indices)
            else:
                result.append(node)
        return result

    @staticmethod
    def _shader_attribute(kind):
        """シェーダーの種類を、接続先のアトリビュート名へ変える。

        Args:
            kind (str): surface・volume・displacementのどれか。

        Returns:
            str: 接続先のアトリビュート名。

        Raises:
            ValueError: kindが対応していない値の場合。
        """
        if kind not in ("surface", "volume", "displacement"):
            raise ValueError("kindはsurface・volume・displacementのどれかで指定してください")
        return kind + "Shader"
