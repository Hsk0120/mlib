# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""デフォーマー(delta mush・cluster など)による変形を、スキンのウェイトへ焼き込む(``cmds.bakeDeformer`` 相当)。

Mayaの Bake Deformers to Skin Weights と同じく ``cmds.bakeDeformer`` を使う。
ジョイントを動かしたときの変形を元の形状で測り、変形先の形状の skinCluster のウェイトにする。
戻り値はその skinCluster。

変形先を省略すると、元の形状そのものを skinCluster だけで変形する形へ置き換える。
このとき元のデフォーマーは取り除かれる。

.. code-block:: python

    import mlib

    skin = mlib.bakeDeformer("body_geo", "root_JNT", "body_game_geo", maxInfluences=4)
"""

import maya.cmds as cmds
from ..core.object import Object
from ..decorator import _pick_alias, undoChunk
from ..util import _UNSET
from mlib.nodes.joint import Joint
from mlib.nodes.node import Node
from mlib.nodes.skinCluster import SkinCluster

_REJECTED_FLAGS: frozenset

def bakeDeformer(source: Node | str, skeleton: Joint | str, destination: Node | str | None = ..., destinationSkeleton: Joint | str | None = ..., maxInfluences: int = ..., *, mi: int = ..., **kwargs: object) -> SkinCluster:
    """元の形状の変形を、変形先の形状の skinCluster のウェイトへ焼き込む。

    選択状態は使わない。変形先がすでにバインドされていれば、その skinCluster のウェイトを書き換える。
    fast引数は無い(OpenMayaに同じ機能が無いため)。Undoが有効なら1回で戻せる。

    Args:
        source (Node | str): 変形を測る元の形状(またはその transform)。デフォーマーで変形していること。
        skeleton (Joint | str): 元の形状を動かすスケルトンの、ルートの joint。
        destination (Node | str | None): ウェイトを焼き込む形状。Noneならsourceそのものに焼き込む。
            このとき元のデフォーマーを取り除き、skinCluster だけで変形する形にする。
        destinationSkeleton (Joint | str | None): 変形先のスケルトンのルート。Noneならskeletonと同じ。
        maxInfluences (int): 1つの頂点に影響するインフルエンスの最大数。正の整数。既定は4。
        mi (int): maxInfluencesの短縮名。maxInfluencesと同時には指定できない。
        **kwargs (object): ``cmds.bakeDeformer`` のそのほかのフラグ。長い名前・短い名前のどちらでもよい。
            使えるのは ``influences``・``pruneWeights``・``smoothWeights``・``hierarchy``・
            ``customRangeOfMotion``・``bakeRangeOfMotion``・``colorizeSkeleton``。
            ``srcMeshName``・``srcSkeletonName``・``dstMeshName``・``dstSkeletonName`` (と短縮名)は
            専用の引数で指定するため受け付けない。query・editも受け付けない。

    Returns:
        SkinCluster: 変形先の形状の skinCluster。

    Raises:
        TypeError: maxInfluencesと短縮名 ``mi`` を同時に指定した場合、または ``**kwargs`` で受け付けない
            フラグを渡した場合。
        ValueError: maxInfluencesが正の整数でない場合。
        RuntimeError: 名前からノードが見つからない場合、Mayaが焼き込みを拒否した場合、
            または変形先に skinCluster が見つからない場合。
    """
    ...
