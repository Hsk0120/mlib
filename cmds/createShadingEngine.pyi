# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""描画に使うシェーディンググループを作り、ShadingEngineを返す(``cmds.sets(renderable=True, noSurfaceShader=True, empty=True)`` 相当)。"""

import maya.cmds as cmds
from ..core.shapeBuild import require_name
from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET
from mlib.nodes.node import Node
from mlib.nodes.shadingEngine import ShadingEngine
from mlib.plugs.plug import Plug


def createShadingEngine(shader: Node | Plug | str | None = ..., *, name: str | None = ..., n: str | None = ...) -> ShadingEngine:
    """描画に使う空のシェーディンググループ(shadingEngine)を作り、そのノードを返す。

    Hypershadeでマテリアルを作ったときと同じく、``renderPartition`` へ登録した(描画の対象になる)
    shadingEngineを作る(``lightLinker1``・``materialInfo`` もMayaがつなぐ)。``mlib.createNode("shadingEngine")`` は
    ``renderPartition`` へ登録しないので、描画に使うものはこの関数で作る。
    shaderを渡すと、:meth:`ShadingEngine.setShader <mlib.nodes.ShadingEngine.setShader>` で ``surfaceShader`` へつなぐ。
    形状への割り当ては :meth:`ShadingEngine.assign <mlib.nodes.ShadingEngine.assign>` で行う。
    現在の選択は変えない。fast引数は無い(``cmds.sets`` に当たるOpenMayaの作成が無いため)。
    shaderを渡したときは、作成と接続を1回のUndoにまとめる。
    nameは ``cmds.sets`` と同じ短縮名 ``n`` でも指定できる(長い名前と短縮名は同時に指定できない)。

    Args:
        shader (Node | Plug | str | None): つなぐシェーダーのノードか、その出力のPlug。Noneならつながない。既定はNone。
        name (str | None): 付けたい名前。NoneならMayaの既定の名前(``set1`` など)。既定はNone。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        ShadingEngine: 作ったシェーディンググループ。

    Raises:
        TypeError: nameと短縮名 ``n`` を同時に指定した場合、nameが文字列でもNoneでもない場合、またはshaderが対応していない型の場合。
        ValueError: nameが空文字列か ``|`` を含む場合。
        RuntimeError: shaderが見つからない場合、またはMayaが作成・接続を拒否した場合。

    Examples:
        >>> import mlib
        >>> shader = mlib.createNode("lambert", name="red_MAT", asShader=True)
        >>> engine = mlib.createShadingEngine(shader, name="red_SG")
        >>> engine.assign(mlib.getNode("pCube1"))
    """
    ...
