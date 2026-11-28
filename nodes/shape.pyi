# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""DAG シェイプの共通操作を提供する。"""

import math
import numbers
import operator
import maya.api.OpenMaya as om2
import maya.cmds as cmds
from ..core import geometryEdit
from ..decorator import _edit_context, _pick_alias, _require_bool
from ..util import _UNSET, _world_space
from .dagNode import DagNode
from .transform import Transform
from typing import Iterable



class Shape(DagNode):
    """MayaのDAGのShapeノードに共通する操作を扱うクラス。"""
    def setParent(self, parent: Transform | str | None = ..., *, relative: bool = ..., add: bool = ..., fast: bool = ..., check: bool = ...) -> None:
        """このシェイプを別のTransformの下へ移す。``add=True`` なら、今の親はそのままにして親を加える(インスタンス)。

        ``cmds.parent(shape, transform, shape=True, relative=True)`` と同じ(``add=True`` は ``add=True`` も付ける)。
        引数は :meth:`Transform.setParent <mlib.nodes.transform.Transform.setParent>` と同じ。
        シェイプは常にローカルの形のまま移る(relativeの値によらない)。そのため、ワールドでの位置は新しい親に合わせて変わる。
        シェイプが無くなっても、元のTransformは削除しない。
        :meth:`~mlib.nodes.transform.Transform.addShape` は、同じ操作を受け取る側から行う。

        Args:
            parent (Transform | str | None): 新しい親のTransform(Jointも指定できる)。シェイプはワールドの直下へ置けないため、
                Noneは指定できない(Transform.setParentと引数を揃えるために既定値を持つ)。
            relative (bool): Transform.setParentと同じ引数。シェイプは常にローカルの形のまま移るため、値によって動きは変わらない。
                既定はFalse。
            add (bool): Trueなら、今の親はそのままにして、新しい親の下にもインスタンスを加える。既定はFalse。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。``MDagModifier.reparentNode`` を使う。
                add=Trueには対応していない(NotImplementedError)。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、シェイプ・元の親・新しい親がロック・リファレンスで編集できないものでないか(fastでは常に確かめる)。

        Returns:
            None: 値を返さない。移した後のパスを指す。add=Trueでは、このオブジェクトは元のパスを指したまま。

        Raises:
            TypeError: parentがTransformでない場合、またはrelative・add・fast・checkがboolでない場合。
            ValueError: parentがNoneの場合。
            RuntimeError: 自身か親が無効な場合、add=Falseでシェイプがインスタンス化されている場合、
                checkかfastで、ロックされたノードやリファレンスのノードを含む場合、
                またはMayaが親の変更を拒否した場合。
            NotImplementedError: fastで、add=Trueを指定した場合、または移す先に同じ名前の子がある場合
                (Mayaが名前を付け直す規則を再現しないため)。
        """
        ...
    def scaleGeometry(self, scale: float | Iterable[float], worldSpace: bool = ..., *, pivot: Iterable[float] = ..., indices: Iterable[int | tuple[int, int]] | None = ..., fast: bool = ..., check: bool = ..., ws: bool = ...) -> None:
        """メッシュの頂点やNURBSのCVを、指定した中心で拡大・縮小する。

        Transformのマトリクスと、フェースの頂点の順は変えない。
        形状を共有しているインスタンスでは、すべてのインスタンスに影響する。
        周期的なカーブ・サーフェスで連動して動くCVも考えに入れて拡大・縮小する。
        途中で失敗しても、それまでに変えた分は戻さない。

        Args:
            scale (float | Iterable[float]): 倍率。1つの数ならXYZに同じ倍率、3つならXYZごとの倍率。
                有限な数で指定する。負の数や0も指定できる。
            worldSpace (bool): Trueならワールド空間、FalseならShapeのオブジェクト空間で拡大・縮小する。既定はFalse。
            ws (bool): worldSpaceの短縮名。worldSpaceと同時には指定できない(TypeError)。
            pivot (Iterable[float]): 拡大・縮小の中心。worldSpaceで選んだ空間での位置で、単位はcm。
                既定は原点。Transformのピボットは使わない。
            indices (Iterable[int | tuple[int, int]] | None): 対象の頂点またはCVの番号。サーフェスでは(U, V)の組。
                Noneならすべてが対象。空なら何も書き込まない。ただし、Shapeの種類の確認と、
                fastでサーフェスを拒否する確認は、その前に行う。既定はNone。
            fast (bool): TrueはUndoなしのOpenMaya更新。既定False。Trueで使えるのは、ヒストリの無いメッシュとカーブだけ。
                Falseなら、Maya標準のコマンドで書き込み、Undoが有効なら1回にまとめる。
            check (bool): Trueなら書き込む前に確かめ、問題があれば何も書かずに例外にする。既定はFalseで、確かめずに書く(Mayaが拒否したときだけ例外になる)。確かめるのは、書き込めるか(ロック・入力の接続が無いか)。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: fast・checkや番号の型が正しくない場合、またはworldSpaceとwsを同時に指定した場合。
            ValueError: 倍率・中心・空間の指定が正しくない場合、ワールドへの変換がほぼ特異(逆に戻せない)な場合、
                またはメッシュ・NURBS以外のShapeの場合。
            IndexError: 番号が範囲外の場合。
            RuntimeError: Mayaが編集を拒否した場合。
            NotImplementedError: fastで、サーフェスやヒストリのある形状を指定した場合。
        """
        ...
    def getTransform(self) -> Transform | None:
        """このShapeの親Transformを取得する。

        Returns:
            Transform | None: 親Transform。存在しない場合は ``None``。
        """
        ...
    def _require_editable_parents(self, target: Transform) -> None:
        """シェイプ・元の親・新しい親が、ロック・リファレンスで編集できないものでないかを確かめる。

        Args:
            target (Transform): 新しい親。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: どれかが、ロックされているかリファレンスのノードの場合。
        """
        ...
    def _set_parent_fast(self, target: Transform) -> None:
        """編集できるかを先に確かめてから、MDagModifierでシェイプの親を変える。

        Args:
            target (Transform): 新しい親。

        Returns:
            None: 値を返さない。

        Raises:
            RuntimeError: シェイプ・元の親・新しい親のどれかが、ロックされているかリファレンスのノードの場合。
            NotImplementedError: 新しい親に同じ名前の子がある場合。
        """
        ...
