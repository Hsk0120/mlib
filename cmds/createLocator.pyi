# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""ロケーターを作り、シェイプを返す(``cmds.spaceLocator`` 相当)。

localPosition・localScale はシェイプのアトリビュートの値で、単位はMaya APIの内部単位(cm)。
作成と親子付けは1回のUndoにまとめ、現在の選択は変えない。

.. code-block:: python

    import mlib

    shape = mlib.createLocator(name="pole", localScale=(2, 2, 2))
    shape.getTransform().setTranslation((0, 5, -10))
"""

import maya.cmds as cmds
from ..core.shapeBuild import finish_shape, require_name, resolve_parent
from ..decorator import _pick_alias, preservedSelection, undoTransaction
from ..util import _UNSET, _finite_vector
from typing import Sequence
from mlib.nodes.locator import Locator
from mlib.nodes.node import Node


def createLocator(name: str | None = ..., parent: Node | str | None = ..., localPosition: Sequence[float] = ..., localScale: Sequence[float] = ..., *, n: str | None = ...) -> Locator:
    """Transformとlocatorのシェイプを作り、シェイプを返す。

    位置はTransformで動かす。localPosition はシェイプの表示だけをずらす(``spaceLocator`` の
    ``position`` と同じアトリビュート)。fast引数は無い(OpenMayaで作っても約1.2倍にしかならず、効果がほぼ無いため)。
    nameは ``cmds.spaceLocator`` と同じ短縮名 ``n`` でも指定できる(長い名前と短縮名は同時に指定できない)。
    parentの短縮名は無い(``cmds.spaceLocator`` の ``p`` はpositionのため)。

    Args:
        name (str | None): Transformに付けたい名前。シェイプは ``<名前>Shape`` になる。
            NoneならMayaの既定の名前(``locator1`` など)。既定はNone。
        parent (Node | str | None): Transformの親。Noneならワールド直下。
            親のローカル空間に、単位マトリクスで置く。
        localPosition (Sequence[float]): シェイプの localPosition(cm)。既定は(0, 0, 0)。
        localScale (Sequence[float]): シェイプの localScale。既定は(1, 1, 1)。
        n (str | None): nameの短縮名。nameと同時には指定できない。

    Returns:
        Locator: 作ったロケーターのシェイプ。Transformは ``getTransform()`` で取得する。

    Raises:
        TypeError: nameと短縮名 ``n`` を同時に指定した場合、または引数の型が正しくない場合。
        ValueError: localPosition・localScaleの成分が3つでない場合、または有限でない場合。
        RuntimeError: 親が無効な場合、またはMayaが作成を拒否した場合。
    """
    ...
