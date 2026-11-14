# _tools/generate_mlib_stubs.py が mlib の docstring から生成した型スタブ。直接編集しない。
"""Mayaのコンポーネント(頂点・エッジ・フェース・CV・UV)と同一シェイプの要素群。"""

import functools
import operator
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple
import maya.api.OpenMaya as om2
from ..core.object import Object, _missing_member_message
from ..decorator import _edit_context, _require_bool
from ..nodes.shape import Shape
from typing import Any, Iterable, Iterator, Sequence
from typing import overload
from typing_extensions import Self

_REPR_LIMIT: int

def _count_name(owner: type | Component) -> str:
    """要素数を返すシェイプのメソッド名(count_attribute)を取り出す。

    Args:
        owner (type | Component): count_attributeを持つ単数のクラス、またはそのインスタンス。

    Returns:
        str: シェイプのメソッド名。

    Raises:
        TypeError: 基底クラスなどで、count_attributeが文字列でない場合。getattrと同じ例外の型にしてある。
    """
    ...

def _indexed_component_fn(component: om2.MObject) -> om2.MFnSingleIndexedComponent | om2.MFnDoubleIndexedComponent | om2.MFnTripleIndexedComponent | None:
    """コンポーネントの番号の数(1〜3個)に合う、OpenMayaのfunction setを返す。

    Args:
        component (om2.MObject): コンポーネント。

    Returns:
        om2.MFnSingleIndexedComponent | om2.MFnDoubleIndexedComponent | om2.MFnTripleIndexedComponent | None:
            番号を持たない種類ならNone。
    """
    ...


class Component(Object):
    """Mayaのコンポーネント1つを表すクラス。

    シェイプと、Mayaでのコンポーネントの番号を持つ。
    頂点・エッジ・フェース・UV・カーブのCVなどの共通の基底クラスで、実際にはVertexなどの具体的なクラスを使う。

    - 渡されたShapeのオブジェクトをそのまま共有する。形状や座標のコピーは持たない。
    - 番号は作るときに確かめる。ただし、トポロジーを変えた後も同じ要素を指し続けるとは限らない。
    - UVの番号の範囲は、現在のUVセットに従う。
    """
    shape_type: Optional[str] = ...
    component_type: Optional[str] = ...
    count_attribute: Optional[str] = ...
    def __init__(self, shape: Shape, index: int) -> None:
        """シェイプとコンポーネントの番号を確かめて、コンポーネントを作る。

        名前やTransformからShapeを探すことはしない。渡されたShapeのオブジェクトをそのまま持つ。

        Args:
            shape (Shape): このクラスに対応するShape(MeshやNurbsCurveなど)のオブジェクト。
            index (int): Mayaでの番号。0から始まる。__index__を持つ値も使えるが、boolは受け付けない。
                負の数を、末尾から数えた位置としては扱わない。

        Raises:
            TypeError: シェイプの型が合わない場合、またはindexがboolか、整数として扱えない場合。
            IndexError: 番号が、今の要素数の範囲の外にある場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def __getattr__(self, name: str):
        """存在しない名前を使ったときに、案内付きのAttributeErrorを送出する。

        Args:
            name (str): 使おうとした名前。

        Raises:
            AttributeError: 常に送出する。``'Vertex'にメソッド'<name>'はありません`` の形で、
                近い名前のメソッドと、maya.cmdsやほかのライブラリの名前に当たるmlibの書き方を案内する。
        """
        ...
    def __eq__(self, other):
        """同じコンポーネントを指すか比べる。

        シェイプのインスタンス・コンポーネントの種類・番号がすべて同じなら等しい。

        Args:
            other: 比較・演算の相手。
        """
        ...
    def __hash__(self):
        """シェイプ・種類・番号からハッシュ値を作って返す。座標を変えても値は変わらない。"""
        ...
    def __repr__(self) -> str:
        """デバッグ用に、型名とコンポーネント名を表す文字列を返す。

        シェイプは、ほかと区別できる一番短い名前で表す。
        ``__str__`` (maya.cmdsへ渡す完全パスの名前)とは別の表示で、名前は毎回取得し直す。

        Returns:
            str: ``Vertex('boxShape.vtx[5]')`` のような文字列。シェイプが削除された場合、
                シェイプの種類が違う場合、番号が範囲の外の場合は ``<Vertex invalid>``。
        """
        ...
    def __str__(self) -> str:
        """コンポーネント名を返す。

        Returns:
            str: 今の完全パスを付けたコンポーネント名。
        """
        ...
    @property
    def shape(self) -> Shape:
        """このコンポーネントを持つシェイプを返す。

        Returns:
            Shape: 作ったときに渡したのと同じオブジェクト。コピーは作らず、まだ有効かも調べ直さない。
        """
        ...
    @property
    def index(self) -> int:
        """Mayaでのコンポーネントの番号を返す。

        Returns:
            int: 0から始まる番号。今のトポロジーで範囲の中にあるかは調べ直さない。
                カーブのCVはOpenMayaの番号で、周期カーブの末尾ではcmdsで使う番号と違うことがある。
        """
        ...
    def getFullName(self) -> str:
        """今のDAGパスを使って、コンポーネント名を取得する。

        Returns:
            str: シェイプの完全パスと、コンポーネントの種類・番号を含む名前。
        """
        ...
    def isValid(self) -> bool:
        """このコンポーネントが今も使えるか調べる。

        シェイプが削除されていないか、種類が合うか、番号が今の範囲の中にあるかを調べる。

        Returns:
            bool: 今のシェイプでこの番号の要素を使えればTrue。

        Note:
            トポロジーを変えた前後で、同じ要素を指すとは限らない。
            UVは、現在のUVセットの番号の範囲を使う。
        """
        ...
    @staticmethod
    def _from_api(path: om2.MDagPath, component: om2.MObject) -> list[Component]:
        """OpenMayaのコンポーネントを、要素1つずつのオブジェクトに分ける。

        番号を個別に指定したコンポーネントは、getElements()の順に並べる。
        全要素を指す(complete)コンポーネントは、今のShapeの全番号を使う。
        どのオブジェクトも同じShapeのオブジェクトを共有し、座標は取得しない。

        Args:
            path (MDagPath): コンポーネントを持つShapeの、インスタンスのパス。
            component (MObject): Meshの頂点/エッジ/フェース/UV/頂点フェース、NurbsCurveのCV、
                NurbsSurfaceのCV、またはLatticeの点。

        Returns:
            list[Component]: 新しく作った、要素1つずつのオブジェクトのリスト。completeの場合は番号0から順に並ぶ。

        Raises:
            TypeError: 対応していないコンポーネントの種類、またはShapeの型の場合。
            IndexError: 個別に指定した番号が、今のShapeの範囲の外にある場合。
            RuntimeError: コンポーネントを持つShapeを見つけられない、または使えない場合。
        """
        ...
    @staticmethod
    def _resolve_input(value: str | Component | tuple) -> Component:
        """コンポーネント名・Componentのオブジェクト・APIの組から、要素1つのオブジェクトを得る。

        - Componentのオブジェクトは、確かめ直さずにそのまま返す。
        - 文字列は、MSelectionListで探す。
        - APIの組は、番号が1つのコンポーネントかと、要素の数を確かめてから分ける。

        要素が1つでないと分かった入力は、分ける前に例外にする。分けた後も、1つであることを確かめる。

        Args:
            value (str | Component | tuple): コンポーネント名、Componentのオブジェクト、または
                (MDagPath, MObject)。:meth:`_from_api` が分けられる種類を扱う。

        Returns:
            Component: 具体的なクラスのオブジェクト。Componentを渡した場合以外は、新しく作ったオブジェクト。

        Raises:
            TypeError: 入力の型、またはコンポーネントの種類に対応していない場合。
            ValueError: 空文字列を指定した場合、または指す要素が1つでない場合。
            IndexError: 個別に指定した番号が、今のShapeの範囲の外にある場合。
            RuntimeError: 名前やコンポーネントを持つShapeを見つけられない場合。
        """
        ...
    def _get_coordinate(self, axis, **space):
        """指定した軸の、今の座標を返す。axisは派生クラスで確かめてある整数。

        Args:
            axis: 座標成分の番号。0=X、1=Y、2=Z。
            **space: 座標空間の指定。worldSpace=Trueでワールド空間。
        """
        ...
    def _require_valid(self) -> None:
        """今のシェイプの型と番号を確かめ直す。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: 番号が現在の要素数の範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    @classmethod
    def _element_count(cls, shape: Shape) -> int:
        """シェイプが今持っている、この種類の要素の数を返す。

        Args:
            shape (Shape): 型を確かめてあるシェイプ。

        Returns:
            int: 要素の数。基底では ``count_attribute`` のシェイプのメソッドを呼ぶ。
                番号を複数持つ種類は、このメソッドを上書きする。
        """
        ...
    @staticmethod
    def _require_shape(shape: Shape, shape_type: str | None) -> None:
        """シェイプが削除されていないかと、型を確かめる。

        要素の数は、必要になったときに呼び出し側で調べる。

        Args:
            shape (Shape): 確かめるシェイプ。
            shape_type (str | None): 必要なMayaのシェイプの型。基底クラスのNoneは、どのシェイプとも一致しない。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: shapeがシェイプのオブジェクトでない場合、または型が違う場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    @staticmethod
    def _require_index_range(index: int, count: int) -> None:
        """番号が要素数の範囲の中にあるか確かめる。

        Args:
            index (int): 整数に直してあるコンポーネントの番号。
            count (int): その呼び出しの中で調べた、今の要素数。

        Returns:
            None: 値を返さない。

        Raises:
            IndexError: 番号が範囲外の場合。
        """
        ...
_COMPONENT_INIT: Any
_COMPONENT_REQUIRE_VALID: Any
_COMPONENT_INDEX: Any
_COMPONENT_SHAPE: Any
_COMPONENT_VALIDATE_SHAPE: Any
_COMPONENT_REQUIRE_INDEX_RANGE: Any


class Components:
    """同じシェイプにある、同じ種類のコンポーネントの集まりを表すクラス。

    Mayaでの番号を、初めて出てきた順に、重なりを除いたtupleで持つ。
    Verticesなどの具体的なクラスが、1つずつの取り出しとまとめての操作を受け持つ。

    - Shapeのオブジェクトを共有し、番号の並びは作ったときに決まる。
    - 形状を編集して要素が増えたり減ったりしても、自動ではついていかない。
      トポロジーを変えた後に同じ要素を指すとも限らない。
    - ``[]`` で指定するのは、この集まりの中での位置で、Mayaでの番号ではない。
    - ``+`` (同じシェイプ・同じ種類どうし)・``==``・:meth:`sort` が使える。
      ``==`` を定義しているので、listと同じくハッシュ値を持たない(dictのキーやsetの要素にできない)。
    """
    def __iter__(self) -> Iterator[Component]: ...
    @overload
    def __getitem__(self, index: int) -> Component: ...
    @overload
    def __getitem__(self, index: slice) -> Components: ...
    component_class: Any
    __hash__: None
    _shape: 'Shape'
    _indices: Tuple[int, ...]
    def __init__(self, shape: Shape, indices: Iterable[int] | None = ...) -> None:
        """指定した番号を確かめて、コンポーネントの集まりを作る。

        番号は並べ替えず、初めて出てきた順のまま、重なりを除いて変更できないtupleに入れる。
        list・tuple・range以外の反復可能な入力や、独自の__index__を持つ番号は、
        要素1つのオブジェクトを1つずつ作って確かめる。拡張側の検査や途中の例外を省かないためである。

        Args:
            shape (Shape): このクラスに対応するShapeのオブジェクト。同じオブジェクトをそのまま持つ。
            indices (Iterable[int] | None): Mayaでの番号。Noneなら、作った時点の全要素を番号の小さい順に持つ。
                空の並びなら空の集まりになる。各番号は__index__を持つ値で、boolと負の数は受け付けない。

        Raises:
            TypeError: シェイプの型、または番号の型が合わない場合。
            IndexError: どれかの番号が、今の要素数の範囲の外にある場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def __len__(self) -> int:
        """持っている番号の数を返す。

        Returns:
            int: 作ったときに決まった数。今のShapeの要素数や、Shapeが削除されていないかは調べない。
        """
        ...
    def __repr__(self) -> str:
        """デバッグ用に、型名と、範囲にまとめたコンポーネント名を表す文字列を返す。

        持っている順で1ずつ続く番号は、``[start:end]`` にまとめる。
        シェイプは、ほかと区別できる一番短い名前で表す。
        まとめた名前が ``_REPR_LIMIT`` 個より多い場合は先頭だけを表示し、数を付ける。

        Returns:
            str: ``CVs('curveShape.cv[0:7]')`` や ``Vertices('boxShape.vtx[0:2]', 'boxShape.vtx[5]')`` のような文字列。
                多い場合は ``Vertices('boxShape.vtx[0]', ..., count=120)``、空なら
                ``Vertices('boxShape', count=0)``、無効なら ``<Vertices invalid>``。
        """
        ...
    def __eq__(self, other: Components | list | tuple) -> bool:
        """同じシェイプ・同じ種類で、番号の並びも同じか比べる。

        list・tupleと比べるときは、同じ位置にあるコンポーネントどうしを ``==`` で比べる。

        Args:
            other (Components | list | tuple): 比べる相手。

        Returns:
            bool: 等しければTrue。対応していない型ならNotImplemented。
        """
        ...
    def __getattr__(self, name: str) -> Callable[..., list]:
        """要素1つのコンポーネントのメソッドを、全要素に対して呼ぶ関数として取得する。

        この集まりに無い公開メソッドの名前を使うと、次のような関数を返す。

        - 持っている順に、各要素(``component_class``)の同じ名前のメソッドを同じ引数で呼ぶ。
        - 戻り値を、持っている順のリストにして返す。
        - ふだんは1回のUndoで戻せるようにまとめる。``fast=True`` はそのまま各メソッドへ渡し、Undoはまとめない。
        - 途中の要素で失敗しても、それまでの変更は自動では元に戻さない。

        Args:
            name (str): 要素1つのコンポーネントの公開メソッドの名前。

        Returns:
            Callable[..., list]: 各要素のメソッドを呼び、戻り値を持っている順のリストで返す関数。

        Raises:
            AttributeError: 名前が ``_`` で始まる場合、または ``component_class`` に無いメソッドの名前の場合。
        """
        ...
    def __add__(self, other: Components | list | tuple) -> Components:
        """同じシェイプ・同じ種類の要素を後ろへつないだ、新しい集まりを返す。

        作るときと同じく、初めて出てきた順を保ち、重なった番号は除く。

        Args:
            other (Components | list | tuple): 同じシェイプ・同じ種類の集まり、または
                要素1つのコンポーネントの並び。

        Returns:
            Components: 左辺と同じクラスの新しい集まり。自身と相手は変更しない。

        Raises:
            TypeError: シェイプまたはコンポーネントの種類が異なる要素を含む場合。
            IndexError: 番号が現在の要素数の範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def __radd__(self, other: list | tuple) -> Components:
        """左辺がlist・tupleのときに、つないだ新しい集まりを返す。

        Args:
            other (list | tuple): 前へつなぐ、同じシェイプ・同じ種類のコンポーネントの並び。

        Returns:
            Components: 右辺(自身)と同じクラスの新しい集まり。

        Raises:
            TypeError: シェイプまたはコンポーネントの種類が異なる要素を含む場合。
        """
        ...
    @property
    def shape(self) -> Shape:
        """この集まりを持つシェイプを返す。

        Returns:
            Shape: 作ったときに渡したのと同じオブジェクト。コピーは作らず、まだ有効かも調べ直さない。
        """
        ...
    @property
    def indices(self) -> tuple[int, ...]:
        """持っているMayaでの番号を、変更できないtupleで返す。

        Returns:
            tuple[int, ...]: 初めて出てきた順に並び、重なりを除いた番号。持っているtupleそのものを返し、
                コピーは作らない。今の範囲の中にあるかも調べ直さない。カーブのCVはOpenMayaの番号で持つ。
        """
        ...
    def sort(self, key: Callable[[Component], object] | None = ..., reverse: bool = ...) -> Self:
        """番号の並びをその場で並べ替える。

        ``key`` を省略すると、Mayaでの番号の順にする。
        ``key`` を渡すと、要素1つのコンポーネント(``__iter__`` と同じく新しく作ったもの)を引数にして呼ぶ。
        並べ替えるのはこの集まりの番号の並びだけで、スライスや ``+`` で作った別の集まりの順は変わらない
        (シェイプのオブジェクトは共有している)。

        Args:
            key (Callable[[Component], object] | None): 各要素から、比べるための値を返す関数。
                NoneならMayaでの番号で比べる。既定はNone。
            reverse (bool): Trueなら大きい順にする。既定はFalse。

        Returns:
            Components: 並べ替えた自身。新しい集まりは作らない。派生クラスでは自身のクラスになる。

        Raises:
            TypeError: keyが呼び出せない、またはreverseがbool以外の場合。
        """
        ...
    def getFullNames(self) -> list[str]:
        """持っている順に、完全パスのコンポーネント名を取得する。

        全部の番号を、まとめて1回だけ確かめ直す。

        Returns:
            list[str]: ``|cube|cubeShape.vtx[3]`` のような、要素ごとの名前。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getCompactNames(self) -> list[str]:
        """続いている番号を範囲にまとめた名前を取得する。

        たくさんの要素を ``maya.cmds`` へ渡すときに使う(``mlib.select`` などが使っている)。
        番号は並べ替えず、持っている順で1ずつ続く区間だけをまとめる。
        たとえば番号 ``[0, 1, 2, 5, 3]`` は ``vtx[0:2]``・``vtx[5]``・``vtx[3]`` になる。
        全部の番号を、まとめて1回だけ確かめ直す。

        Returns:
            list[str]: ``|cube|cubeShape.vtx[0:2]`` のような名前。空の集まりなら空リスト。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def isValid(self) -> bool:
        """この集まりが今も使えるか調べる。

        シェイプが削除されていないか、種類が合うか、全部の番号が今の範囲の中にあるかを調べる。

        Returns:
            bool: 全部の番号の要素を使えればTrue。空の集まりでも、シェイプが残っていて種類が合えばTrue。

        Note:
            トポロジーを変えた前後で、同じ要素を指すとは限らない。
            UVは、現在のUVセットの番号の範囲を使う。
        """
        ...
    def isComplete(self) -> bool:
        """シェイプが今持っている、この種類の要素をすべて持っているか調べる。

        並び順は問わない。``cmds.ls(..., flatten=True)`` で得られる全要素(``vtx[*]`` など)と同じ集まりかを調べる。

        Returns:
            bool: 全要素を持っていればTrue。要素が0個のシェイプで、空の集まりの場合もTrue。

        Raises:
            TypeError: 対応していないシェイプの型の場合。
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def _matching_indices(self, other: Components | list | tuple) -> tuple[int, ...]:
        """つなぐ相手が同じシェイプ・同じ種類であることを確かめて、その番号の並びを取り出す。

        Args:
            other (Components | list | tuple): つなぐ相手。

        Returns:
            tuple[int, ...]: 相手の番号を、相手が持っている順に並べたもの。

        Raises:
            TypeError: シェイプまたはコンポーネントの種類が異なる場合。
        """
        ...
    def _has_standard_component(self, component_class: type | None = ...) -> bool:
        """要素1つのクラスが、作成・確認・番号の取得を標準のまま使っているか調べる。

        Args:
            component_class (type | None): 調べる要素1つのクラス。Noneなら自身の要素のクラス。

        Returns:
            bool: 利用側の派生クラスでなく、処理も差し替えられていなければTrue。
        """
        ...
    def _has_standard_shape(self, component_class: type | None = ...) -> bool:
        """シェイプが標準のクラスのままか調べる。

        利用側がシェイプを派生させて、要素数の取得を変えている場合に、それを保つために使う。

        Args:
            component_class (type | None): 要素数を調べる、要素1つのクラス。Noneなら自身の要素のクラス。

        Returns:
            bool: MeshまたはNurbsCurveそのもので、要素数の取得も差し替えられていなければTrue。
        """
        ...
    def _uses_standard_iteration(self, component_class: type) -> bool:
        """まとめての取得を使ってよいか調べる。

        要素1つのクラスや反復が拡張されていない場合だけ、まとめての取得を使う。

        Args:
            component_class (type): その操作の標準の、要素1つのクラス。

        Returns:
            bool: 要素1つのクラス・反復・シェイプがすべて標準の実装ならTrue。
        """
        ...
    def _uses_standard_vertices(self) -> bool:
        """途中で作る頂点の集まりについても、作成と反復が標準のままか調べる。

        Returns:
            bool: 利用側がVertices/Vertexを差し替えていなければTrue。
        """
        ...
    def _mesh_vertex_indices(self, count_name: str, vertices_method: str) -> list[int]:
        """今のメッシュから、各要素につながる頂点の番号を集める。

        Args:
            count_name (str): コンポーネントの数を返す、MFnMeshのプロパティ名。
            vertices_method (str): 要素の頂点番号を返す、MFnMeshのメソッド名。

        Returns:
            list[int]: 頂点の番号。持っている順に、つながりの順を保って並ぶ。重なりは、呼び出し元のVerticesが除く。
        """
        ...
    def _name_prefix(self) -> str:
        """全部の番号をまとめて確かめ直し、``<シェイプの完全パス>.<種類>`` を返す。

        Returns:
            str: ``|cube|cubeShape.vtx`` のような接頭辞。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が現在の要素数の範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def _repr_indices(self) -> Sequence[int]:
        """reprに表示する番号を、持っている順で返す。カーブのCVは、cmdsで使う番号に直す。

        Returns:
            Sequence[int]: 表示用の番号列。
        """
        ...
    def _require_valid(self):
        """シェイプと、持っている番号をまとめて確かめる。

        名前や、要素1つのオブジェクトは作らない。

        Raises:
            TypeError: シェイプの型が違う場合。
            IndexError: トポロジーを変えたことで、番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    @staticmethod
    def _range_name(prefix: str, start: int, end: int) -> str:
        """範囲指定のコンポーネント名を作る。

        Args:
            prefix (str): ``<シェイプの完全パス>.<種類>``。
            start (int): 先頭の番号。
            end (int): 末尾の番号。先頭と同じなら1つだけの名前にする。

        Returns:
            str: ``prefix[start]`` または ``prefix[start:end]``。
        """
        ...
    def _get_coordinate(self, axis, **space):
        """指定した軸の値を、持っている順に返す。axisは派生クラスが選ぶ。

        Args:
            axis: 座標成分の番号。0=X、1=Y、2=Z。
            **space: 座標空間の指定。worldSpace=Trueでワールド空間。
        """
        ...
    def getFullName(self) -> list[str]:
        """各要素の :meth:`~mlib.components.component.Component.getFullName` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
    def asString(self) -> list[str]:
        """各要素の :meth:`~mlib.core.object.Object.asString` を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"""
        ...
_COMPONENTS_INIT: Any
_COMPONENTS_ITER: Any

def _flat_input(cls, shape: Shape, items: list[int | Sequence[int]]) -> list[int]:
    """番号の指定を、通し番号のリストへ変換する。

    番号は、要素を一列に並べたときの通し番号か、複数の番号のtuple(``(u, v)`` など)で指定する。
    複数の番号は今の形状で通し番号へ変換し、範囲の外ならIndexErrorにする。
    通し番号の範囲は、呼び出し側が確かめる。

    Args:
        cls (type): ``index_size`` と ``_flat_indices`` を持つ、番号を複数持つ要素1つのクラス。
        shape (Shape): 型を確かめてあるシェイプ。
        items (list[int | Sequence[int]]): 番号の指定。

    Returns:
        list[int]: 通し番号。指定した順に並ぶ。

    Raises:
        TypeError: 番号が整数として扱えない場合、またはboolの場合。
        ValueError: 複数の番号の数が ``index_size`` と違う場合。
        IndexError: 複数の番号が範囲の外の場合。
    """
    ...

def _component_name(prefix: str, numbers: Sequence[int]) -> str:
    """``<シェイプ>.<種類>`` と複数の番号から、``cv[1][2]`` のようなコンポーネント名を作る。

    Args:
        prefix (str): ``<シェイプの名前>.<種類>``。
        numbers (Sequence[int]): cmds用の番号。

    Returns:
        str: コンポーネント名。
    """
    ...


class _MultiIndexComponent:
    """番号を複数持つコンポーネント1つに共通の処理。

    ``cv[u][v]``・``pt[s][t][u]``・``vtxFace[v][f]`` のように、番号を複数持つ要素に使う。
    :class:`Component` の具体的なクラスと組み合わせて使う(``class SurfaceCV(_MultiIndexComponent, PointComponent)``)。

    持っている :attr:`~Component.index` は、要素を一列に並べたときの通し番号になる。
    ``==``・ハッシュ・:attr:`Components.indices` は、この通し番号を使う。
    複数の番号は :meth:`getMultiIndex` で取得する。
    具体的なクラスは ``index_size`` と、``_element_count``・``_multi_indices``・``_flat_indices`` を定義する。
    """
    index_size: int
    def __init__(self, shape: Shape, index: int | Sequence[int]) -> None:
        """シェイプと番号を確かめて、コンポーネントを作る。

        Args:
            shape (Shape): このクラスに対応するシェイプのオブジェクト。
            index (int | Sequence[int]): 通し番号、または複数の番号(``(u, v)`` など)。
                boolと負の数は受け付けない。

        Raises:
            TypeError: シェイプの型が合わない場合、または番号が整数として扱えないかboolの場合。
            ValueError: 複数の番号の数が違う場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getFullName(self) -> str:
        """今のDAGパスと複数の番号を使って、コンポーネント名を取得する。

        Returns:
            str: ``|plane|planeShape.cv[1][2]`` のような名前。周期曲面で重なっているCVは、先頭側の番号で表す。
        """
        ...
    def getMultiIndex(self) -> tuple[int, ...]:
        """この要素の複数の番号を、今の形状から取得する。

        Returns:
            tuple[int, ...]: ``(u, v)``・``(s, t, u)``・``(頂点, フェース)`` のような番号。

        Raises:
            TypeError: 対応していないシェイプの型の場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...


class _MultiIndexComponents:
    """番号を複数持つコンポーネントの集まりに共通の処理。

    :class:`Components` の具体的なクラスと組み合わせて使う。
    番号の指定には、通し番号と複数の番号を混ぜて使える。持つのは通し番号にする。
    名前は範囲にまとめない。
    """
    def __init__(self, shape: Shape, indices: Iterable[int | Sequence[int]] | None = ...) -> None:
        """指定した番号を確かめて、コンポーネントの集まりを作る。

        初めて出てきた順を保ち、重なりを除いて持つ。

        Args:
            shape (Shape): このクラスに対応するシェイプのオブジェクト。
            indices (Iterable[int | Sequence[int]] | None): 通し番号、または複数の番号の並び。
                Noneなら、作った時点の全要素を通し番号の小さい順に持つ。

        Raises:
            TypeError: シェイプの型、または番号の型が合わない場合。
            ValueError: 複数の番号の数が違う場合。
            IndexError: どれかの番号が今の範囲の外にある場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def __repr__(self) -> str:
        """デバッグ用に、型名と先頭の要素の名前を表す文字列を返す。

        Returns:
            str: ``SurfaceCVs('planeShape.cv[0][0]', 'planeShape.cv[0][1]')`` のような文字列。多い場合は数を付ける。
                空なら ``SurfaceCVs('planeShape', count=0)``、無効なら ``<SurfaceCVs invalid>``。
        """
        ...
    def getFullNames(self) -> list[str]:
        """持っている順に、完全パスのコンポーネント名を取得する。

        Returns:
            list[str]: ``|plane|planeShape.cv[1][2]`` のような、要素ごとの名前。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
    def getCompactNames(self) -> list[str]:
        """cmdsへ渡す名前を返す。

        番号を複数持つ要素は範囲にまとめないので、:meth:`getFullNames` と同じ名前を返す。

        Returns:
            list[str]: 持っている順のコンポーネント名。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        ...
