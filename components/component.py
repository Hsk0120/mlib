"""Mayaのコンポーネント(頂点・エッジ・フェース・CV・UV)と同一シェイプの要素群。"""

import functools
import operator
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple

import maya.api.OpenMaya as om2

from ..core.object import Object, _missing_member_message
from ..decorator import _edit_context, _require_bool

if TYPE_CHECKING:
    from ..nodes.shape import Shape


#: Components の repr に表示する、範囲へまとめた名前の最大数。
_REPR_LIMIT = 4


def _count_name(owner):
    """要素数を返すシェイプのメソッド名(count_attribute)を取り出す。

    Args:
        owner (type | Component): count_attributeを持つ単数のクラス、またはそのインスタンス。

    Returns:
        str: シェイプのメソッド名。

    Raises:
        TypeError: 基底クラスなどで、count_attributeが文字列でない場合。getattrと同じ例外の型にしてある。
    """
    name = owner.count_attribute
    if not isinstance(name, str):
        raise TypeError(f"アトリビュート名は文字列で指定してください: '{type(name).__name__}'")
    return name


def _indexed_component_fn(component):
    """コンポーネントの番号の数(1〜3個)に合う、OpenMayaのfunction setを返す。

    Args:
        component (om2.MObject): コンポーネント。

    Returns:
        om2.MFnSingleIndexedComponent | om2.MFnDoubleIndexedComponent | om2.MFnTripleIndexedComponent | None:
            番号を持たない種類ならNone。
    """
    if component.hasFn(om2.MFn.kSingleIndexedComponent):
        return om2.MFnSingleIndexedComponent(component)
    if component.hasFn(om2.MFn.kDoubleIndexedComponent):
        return om2.MFnDoubleIndexedComponent(component)
    if component.hasFn(om2.MFn.kTripleIndexedComponent):
        return om2.MFnTripleIndexedComponent(component)
    return None


class Component(Object):
    """Mayaのコンポーネント1つを表すクラス。

    シェイプと、Mayaでのコンポーネントの番号を持つ。
    頂点・エッジ・フェース・UV・カーブのCVなどの共通の基底クラスで、実際にはVertexなどの具体的なクラスを使う。

    - 渡されたShapeのオブジェクトをそのまま共有する。形状や座標のコピーは持たない。
    - 番号は作るときに確かめる。ただし、トポロジーを変えた後も同じ要素を指し続けるとは限らない。
    - UVの番号の範囲は、現在のUVセットに従う。
    """

    # シェイプ型・cmds用の種類名・要素数を返すシェイプのメソッド名。具体型が定義し、基底ではNone。
    shape_type: Optional[str] = None
    component_type: Optional[str] = None
    count_attribute: Optional[str] = None

    def __init__(self, shape, index):
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
        self._shape = shape
        if isinstance(index, bool):
            raise TypeError("コンポーネントの番号は整数で指定してください(boolは指定できません)")
        self._index = operator.index(index)
        self._require_valid()

    def __getattr__(self, name):
        """存在しない名前を使ったときに、案内付きのAttributeErrorを送出する。

        Args:
            name (str): 使おうとした名前。

        Raises:
            AttributeError: 常に送出する。``'Vertex'にメソッド'<name>'はありません`` の形で、
                近い名前のメソッドと、maya.cmdsやほかのライブラリの名前に当たるmlibの書き方を案内する。
        """
        if name.startswith("_"):
            raise AttributeError(name)
        raise AttributeError(_missing_member_message(self, name))

    def __eq__(self, other):
        """同じコンポーネントを指すか比べる。

        シェイプのインスタンス・コンポーネントの種類・番号がすべて同じなら等しい。

        Args:
            other: 比較・演算の相手。
        """
        if not isinstance(other, Component):
            return NotImplemented
        return self._shape == other._shape and self.component_type == other.component_type and self._index == other._index

    def __hash__(self):
        """シェイプ・種類・番号からハッシュ値を作って返す。座標を変えても値は変わらない。"""
        return hash((self._shape, self.component_type, self._index))

    def __repr__(self):
        """デバッグ用に、型名とコンポーネント名を表す文字列を返す。

        シェイプは、ほかと区別できる一番短い名前で表す。
        ``__str__`` (maya.cmdsへ渡す完全パスの名前)とは別の表示で、名前は毎回取得し直す。

        Returns:
            str: ``Vertex('boxShape.vtx[5]')`` のような文字列。シェイプが削除された場合、
                シェイプの種類が違う場合、番号が範囲の外の場合は ``<Vertex invalid>``。
        """
        cls = type(self).__name__
        if not self.isValid():
            return f"<{cls} invalid>"
        full = self.getFullName()
        return f"{cls}({self._shape.getName() + full[full.rindex('.') :]!r})"

    def __str__(self):
        """コンポーネント名を返す。

        Returns:
            str: 今の完全パスを付けたコンポーネント名。
        """
        return self.getFullName()

    @property
    def shape(self):
        """このコンポーネントを持つシェイプを返す。

        Returns:
            Shape: 作ったときに渡したのと同じオブジェクト。コピーは作らず、まだ有効かも調べ直さない。
        """
        return self._shape

    @property
    def index(self):
        """Mayaでのコンポーネントの番号を返す。

        Returns:
            int: 0から始まる番号。今のトポロジーで範囲の中にあるかは調べ直さない。
                カーブのCVはOpenMayaの番号で、周期カーブの末尾ではcmdsで使う番号と違うことがある。
        """
        return self._index

    def getFullName(self):
        """今のDAGパスを使って、コンポーネント名を取得する。

        Returns:
            str: シェイプの完全パスと、コンポーネントの種類・番号を含む名前。
        """
        self._require_valid()
        return f"{self._shape.getFullName()}.{self.component_type}[{self._index}]"

    def isValid(self):
        """このコンポーネントが今も使えるか調べる。

        シェイプが削除されていないか、種類が合うか、番号が今の範囲の中にあるかを調べる。

        Returns:
            bool: 今のシェイプでこの番号の要素を使えればTrue。

        Note:
            トポロジーを変えた前後で、同じ要素を指すとは限らない。
            UVは、現在のUVセットの番号の範囲を使う。
        """
        try:
            self._require_valid()
        except (RuntimeError, TypeError, ValueError, IndexError):
            return False
        return True

    @staticmethod
    def _from_api(path, component):
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
        # nodes・具体コンポーネント型はこのモジュールを継承・importするため、循環を避けて使う時点で読み込む。
        from ..nodes.node import Node
        from .cv import CV
        from .edge import Edge
        from .face import Face
        from .latticePoint import LatticePoint
        from .surfaceCV import SurfaceCV
        from .uv import UV
        from .vertex import Vertex
        from .vertexFace import VertexFace

        types = {
            om2.MFn.kMeshVertComponent: Vertex,
            om2.MFn.kMeshEdgeComponent: Edge,
            om2.MFn.kMeshPolygonComponent: Face,
            om2.MFn.kMeshMapComponent: UV,
            om2.MFn.kCurveCVComponent: CV,
            om2.MFn.kSurfaceCVComponent: SurfaceCV,
            om2.MFn.kLatticeComponent: LatticePoint,
            om2.MFn.kMeshVtxFaceComponent: VertexFace,
        }
        cls = types.get(component.apiType())
        if cls is None:
            raise TypeError("対応しているのは、メッシュの頂点・エッジ・フェース・UV・頂点フェース、カーブのCV、サーフェスのCV、ラティスの点だけです")
        shape = Node(path)
        fn = _indexed_component_fn(component)
        if fn.isComplete:
            indices = range(cls._element_count(shape))
        else:
            indices = fn.getElements()
        return [cls(shape, index) for index in indices]

    @staticmethod
    def _resolve_input(value):
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
        if isinstance(value, Component):
            return value
        if isinstance(value, str):
            if not value:
                raise ValueError("コンポーネント名は空でない文字列で指定してください")
            selection = om2.MSelectionList()
            selection.add(value)
            if selection.length() != 1:
                raise ValueError("コンポーネントを1つ指定してください")
            value = selection.getComponent(0)
        if not (isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], om2.MDagPath) and isinstance(value[1], om2.MObject)):
            raise TypeError("コンポーネントの参照か、名前か、(MDagPath, MObject)を指定してください")
        # 要素1つを求めるときは、広い範囲を1つずつのオブジェクトへ分ける前に例外にする。
        component_fn = _indexed_component_fn(value[1])
        if component_fn is None:
            raise TypeError("番号付きのコンポーネントを指定してください")
        if component_fn.isComplete:
            count = component_fn.getCompleteData()
            if isinstance(count, tuple):
                # 多次元の番号では、各方向の要素数の積が全体の数。
                count = functools.reduce(operator.mul, count, 1)
        else:
            count = component_fn.elementCount
        if count != 1:
            raise ValueError("コンポーネントを1つ指定してください。範囲にはSelectionを使います")
        items = Component._from_api(*value)
        if len(items) != 1:
            raise ValueError("コンポーネントを1つ指定してください。範囲にはSelectionを使います")
        return items[0]

    def _get_coordinate(self, axis, **space):
        """指定した軸の、今の座標を返す。axisは派生クラスで確かめてある整数。

        Args:
            axis: 座標成分の番号。0=X、1=Y、2=Z。
            **space: 座標空間の指定。worldSpace=Trueでワールド空間。
        """
        return self.getPosition(**space)[axis]

    def _require_valid(self):
        """今のシェイプの型と番号を確かめ直す。

        Returns:
            None: 値を返さない。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: 番号が現在の要素数の範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        self._require_shape(self._shape, self.shape_type)
        if self._index < 0:
            self._require_index_range(self._index, 0)
        self._require_index_range(self._index, self._element_count(self._shape))

    @classmethod
    def _element_count(cls, shape):
        """シェイプが今持っている、この種類の要素の数を返す。

        Args:
            shape (Shape): 型を確かめてあるシェイプ。

        Returns:
            int: 要素の数。基底では ``count_attribute`` のシェイプのメソッドを呼ぶ。
                番号を複数持つ種類は、このメソッドを上書きする。
        """
        return getattr(shape, _count_name(cls))()

    @staticmethod
    def _require_shape(shape, shape_type):
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
        if not callable(getattr(shape, "isValid", None)):
            raise TypeError("shapeはmlibのシェイプのラッパーで指定してください")
        if not shape.isValid():
            raise RuntimeError("コンポーネントのシェイプが無効です")
        if shape.getType() != shape_type:
            raise TypeError(f"{shape_type}のシェイプを指定してください")

    @staticmethod
    def _require_index_range(index, count):
        """番号が要素数の範囲の中にあるか確かめる。

        Args:
            index (int): 整数に直してあるコンポーネントの番号。
            count (int): その呼び出しの中で調べた、今の要素数。

        Returns:
            None: 値を返さない。

        Raises:
            IndexError: 番号が範囲外の場合。
        """
        if not 0 <= index < count:
            raise IndexError(f"コンポーネントの番号が範囲外です: {index}")


_COMPONENT_INIT = Component.__init__
_COMPONENT_REQUIRE_VALID = Component._require_valid
_COMPONENT_INDEX = Component.index
_COMPONENT_SHAPE = Component.shape
_COMPONENT_VALIDATE_SHAPE = Component._require_shape
_COMPONENT_REQUIRE_INDEX_RANGE = Component._require_index_range


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

    component_class = Component
    __hash__ = None  # type: ignore[assignment]
    # __init__で設定する保持値。派生クラス(別モジュール)からも参照する。
    _shape: "Shape"
    _indices: Tuple[int, ...]

    if TYPE_CHECKING:
        # 座標の取得は派生クラス(PointComponents・UVs)が実装する。
        getPosition: Callable[..., List[Any]]

    def __init__(self, shape, indices=None):
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
        self._shape = shape
        Component._require_shape(shape, self.component_class.shape_type)
        selected = range(self.component_class._element_count(shape)) if indices is None else indices
        # 一般の反復入力や独自__index__は従来どおり一件ずつ構築する。
        # これにより入力の副作用・途中例外・利用側constructor/_validateを維持する。
        if (
            self._has_standard_component()
            and self._has_standard_shape()
            and (type(selected) is range or (type(selected) in (list, tuple) and all(type(index) is int for index in selected)))
        ):
            count = len(selected) if indices is None else None
            for index in selected:
                if index < 0:
                    Component._require_index_range(index, 0)
                if count is None:
                    count = self.component_class._element_count(shape)
                Component._require_index_range(index, count)
            self._indices = tuple(dict.fromkeys(selected))
        else:
            self._indices = tuple(dict.fromkeys(self.component_class(shape, index).index for index in selected))

    def __len__(self):
        """持っている番号の数を返す。

        Returns:
            int: 作ったときに決まった数。今のShapeの要素数や、Shapeが削除されていないかは調べない。
        """
        return len(self._indices)

    def __iter__(self):
        """持っている番号の順に、要素1つのコンポーネントを作って返す。

        1つ作るたびに、今のShapeと番号を確かめる。先に全部を確かめるわけではないので、
        途中で失敗しても、それより前の要素はすでに返している。座標は取得しない。

        Yields:
            Component: 同じShapeのオブジェクトを共有する、新しいコンポーネント。
        """
        for index in self._indices:
            yield self.component_class(self._shape, index)

    def __repr__(self):
        """デバッグ用に、型名と、範囲にまとめたコンポーネント名を表す文字列を返す。

        持っている順で1ずつ続く番号は、``[start:end]`` にまとめる。
        シェイプは、ほかと区別できる一番短い名前で表す。
        まとめた名前が ``_REPR_LIMIT`` 個より多い場合は先頭だけを表示し、数を付ける。

        Returns:
            str: ``CVs('curveShape.cv[0:7]')`` や ``Vertices('boxShape.vtx[0:2]', 'boxShape.vtx[5]')`` のような文字列。
                多い場合は ``Vertices('boxShape.vtx[0]', ..., count=120)``、空なら
                ``Vertices('boxShape', count=0)``、無効なら ``<Vertices invalid>``。
        """
        cls = type(self).__name__
        if not self.isValid():
            return f"<{cls} invalid>"
        shape = self._shape.getName()
        if not self._indices:
            return f"{cls}({shape!r}, count=0)"
        prefix = f"{shape}.{self.component_class.component_type}"
        names = []
        start = previous = None
        for index in self._repr_indices():
            if previous is not None and index == previous + 1:
                previous = index
                continue
            if start is not None:
                names.append(self._range_name(prefix, start, previous))
            start = previous = index
        names.append(self._range_name(prefix, start, previous))
        if len(names) > _REPR_LIMIT:
            shown = ", ".join(repr(name) for name in names[:_REPR_LIMIT])
            return f"{cls}({shown}, ..., count={len(self._indices)})"
        return f"{cls}({', '.join(repr(name) for name in names)})"

    def __getitem__(self, index):
        """位置を指定して、要素を取り出す。

        整数を指定すると要素1つのコンポーネントを、sliceを指定すると同じクラスの集まりを返す。
        指定するのはこの集まりの中での位置で、Mayaでの番号ではない。負の数とboolは、tupleと同じ位置として扱う。
        取り出した要素の番号は今の形状で確かめ直し、元と同じShapeのオブジェクトを共有する。

        Args:
            index (int | slice): この集まりの中での位置。

        Returns:
            Component | Components: 新しいコンポーネント、または同じクラスの新しい集まり。

        Raises:
            TypeError: tupleが受け付けない位置を指定した場合、またはShapeの型が合わない場合。
            ValueError: sliceのstepが0の場合。
            IndexError: 位置が範囲の外の場合、またはMayaでの番号が今の範囲の外にある場合。
            RuntimeError: Shapeが無効な場合。
        """
        if isinstance(index, slice):
            return type(self)(self._shape, self._indices[index])
        return self.component_class(self._shape, self._indices[index])

    def __eq__(self, other):
        """同じシェイプ・同じ種類で、番号の並びも同じか比べる。

        list・tupleと比べるときは、同じ位置にあるコンポーネントどうしを ``==`` で比べる。

        Args:
            other (Components | list | tuple): 比べる相手。

        Returns:
            bool: 等しければTrue。対応していない型ならNotImplemented。
        """
        if isinstance(other, Components):
            return (
                self.component_class.component_type == other.component_class.component_type and self._shape == other._shape and self._indices == other._indices
            )
        if not isinstance(other, (list, tuple)):
            return NotImplemented
        if len(self._indices) != len(other):
            return False
        component_type = self.component_class.component_type
        return all(
            isinstance(item, Component) and item.component_type == component_type and item._shape == self._shape and item._index == index
            for item, index in zip(other, self._indices)
        )

    def __getattr__(self, name):
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
        if name.startswith("_") or not callable(getattr(self.component_class, name, None)):
            raise AttributeError(f"{type(self).__name__!r}オブジェクトにアトリビュート{name!r}はありません")

        def forward(*args, **kwargs):
            fast = kwargs.get("fast", False) is True
            with _edit_context(f"mlib{type(self).__name__}{name[:1].upper()}{name[1:]}", fast):
                return [getattr(component, name)(*args, **kwargs) for component in self]

        forward.__name__ = name
        forward.__qualname__ = f"{type(self).__name__}.{name}"
        forward.__doc__ = f"各要素の {name}() を同じ引数で保持順に呼び、戻り値を保持順のリストで返す。"
        return forward

    def __add__(self, other):
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
        if not isinstance(other, (Components, list, tuple)):
            return NotImplemented
        return type(self)(self._shape, self._indices + self._matching_indices(other))

    def __radd__(self, other):
        """左辺がlist・tupleのときに、つないだ新しい集まりを返す。

        Args:
            other (list | tuple): 前へつなぐ、同じシェイプ・同じ種類のコンポーネントの並び。

        Returns:
            Components: 右辺(自身)と同じクラスの新しい集まり。

        Raises:
            TypeError: シェイプまたはコンポーネントの種類が異なる要素を含む場合。
        """
        if not isinstance(other, (list, tuple)):
            return NotImplemented
        return type(self)(self._shape, self._matching_indices(other) + self._indices)

    @property
    def shape(self):
        """この集まりを持つシェイプを返す。

        Returns:
            Shape: 作ったときに渡したのと同じオブジェクト。コピーは作らず、まだ有効かも調べ直さない。
        """
        return self._shape

    @property
    def indices(self):
        """持っているMayaでの番号を、変更できないtupleで返す。

        Returns:
            tuple[int, ...]: 初めて出てきた順に並び、重なりを除いた番号。持っているtupleそのものを返し、
                コピーは作らない。今の範囲の中にあるかも調べ直さない。カーブのCVはOpenMayaの番号で持つ。
        """
        return self._indices

    def sort(self, key=None, reverse=False):
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
        _require_bool(reverse, "reverse")
        if key is not None and not callable(key):
            raise TypeError("keyは呼び出せるオブジェクトかNoneで指定してください")
        if key is None:
            self._indices = tuple(sorted(self._indices, reverse=reverse))
            return self
        pairs = sorted(zip(self, self._indices), key=lambda pair: key(pair[0]), reverse=reverse)
        self._indices = tuple(index for _, index in pairs)
        return self

    def getFullNames(self):
        """持っている順に、完全パスのコンポーネント名を取得する。

        全部の番号を、まとめて1回だけ確かめ直す。

        Returns:
            list[str]: ``|cube|cubeShape.vtx[3]`` のような、要素ごとの名前。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        prefix = self._name_prefix()
        return [f"{prefix}[{index}]" for index in self._indices]

    def getCompactNames(self):
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
        prefix = self._name_prefix()
        names = []
        start = previous = None
        for index in self._indices:
            if previous is not None and index == previous + 1:
                previous = index
                continue
            if start is not None:
                names.append(self._range_name(prefix, start, previous))
            start = previous = index
        if start is not None:
            names.append(self._range_name(prefix, start, previous))
        return names

    def isValid(self):
        """この集まりが今も使えるか調べる。

        シェイプが削除されていないか、種類が合うか、全部の番号が今の範囲の中にあるかを調べる。

        Returns:
            bool: 全部の番号の要素を使えればTrue。空の集まりでも、シェイプが残っていて種類が合えばTrue。

        Note:
            トポロジーを変えた前後で、同じ要素を指すとは限らない。
            UVは、現在のUVセットの番号の範囲を使う。
        """
        try:
            self._require_valid()
        except (RuntimeError, TypeError, ValueError, IndexError):
            return False
        return all(index >= 0 for index in self._indices)

    def isComplete(self):
        """シェイプが今持っている、この種類の要素をすべて持っているか調べる。

        並び順は問わない。``cmds.ls(..., flatten=True)`` で得られる全要素(``vtx[*]`` など)と同じ集まりかを調べる。

        Returns:
            bool: 全要素を持っていればTrue。要素が0個のシェイプで、空の集まりの場合もTrue。

        Raises:
            TypeError: 対応していないシェイプの型の場合。
            IndexError: トポロジーを変えたことで、持っている番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        self._require_valid()
        return len(self._indices) == self.component_class._element_count(self._shape)

    def _matching_indices(self, other):
        """つなぐ相手が同じシェイプ・同じ種類であることを確かめて、その番号の並びを取り出す。

        Args:
            other (Components | list | tuple): つなぐ相手。

        Returns:
            tuple[int, ...]: 相手の番号を、相手が持っている順に並べたもの。

        Raises:
            TypeError: シェイプまたはコンポーネントの種類が異なる場合。
        """
        name = type(self).__name__
        component_type = self.component_class.component_type
        if isinstance(other, Components):
            if other.component_class.component_type != component_type:
                raise TypeError(f"{type(other).__name__}を{name}へ追加できません: コンポーネントの種類が違います")
            if other._shape != self._shape:
                raise TypeError(f"{type(other).__name__}を{name}へ追加できません: シェイプが違います")
            return other._indices
        indices = []
        for item in other:
            if not isinstance(item, Component) or item.component_type != component_type:
                raise TypeError(f"{type(item).__name__}を{name}へ追加できません: {self.component_class.__name__}を指定してください")
            if item._shape != self._shape:
                raise TypeError(f"{type(item).__name__}を{name}へ追加できません: シェイプが違います")
            indices.append(item._index)
        return tuple(indices)

    def _has_standard_component(self, component_class=None):
        """要素1つのクラスが、作成・確認・番号の取得を標準のまま使っているか調べる。

        Args:
            component_class (type | None): 調べる要素1つのクラス。Noneなら自身の要素のクラス。

        Returns:
            bool: 利用側の派生クラスでなく、処理も差し替えられていなければTrue。
        """
        # 具体コンポーネント型はこのモジュールを継承するため、循環を避けて使う時点で読み込む。
        from .cv import CV
        from .edge import Edge
        from .face import Face
        from .uv import UV
        from .vertex import Vertex

        component_class = self.component_class if component_class is None else component_class
        return (
            component_class in (Vertex, Edge, Face, UV, CV)
            and component_class.__init__ is _COMPONENT_INIT
            and component_class._require_valid is _COMPONENT_REQUIRE_VALID
            and component_class.index is _COMPONENT_INDEX
            and component_class.shape is _COMPONENT_SHAPE
            and component_class._require_shape is _COMPONENT_VALIDATE_SHAPE
            and component_class._require_index_range is _COMPONENT_REQUIRE_INDEX_RANGE
        )

    def _has_standard_shape(self, component_class=None):
        """シェイプが標準のクラスのままか調べる。

        利用側がシェイプを派生させて、要素数の取得を変えている場合に、それを保つために使う。

        Args:
            component_class (type | None): 要素数を調べる、要素1つのクラス。Noneなら自身の要素のクラス。

        Returns:
            bool: MeshまたはNurbsCurveそのもので、要素数の取得も差し替えられていなければTrue。
        """
        # nodes → components の循環importを避けるため、使う時点で読み込む。
        from ..nodes.mesh import Mesh
        from ..nodes.nurbsCurve import NurbsCurve

        shape_class = type(self._shape)
        if shape_class not in (Mesh, NurbsCurve):
            return False
        component_class = self.component_class if component_class is None else component_class
        name = _count_name(component_class)
        reader = getattr(self._shape, name, None)
        function = getattr(reader, "__func__", None)
        return (
            function is not None
            and function is getattr(shape_class, name, None)
            and function.__module__ == shape_class.__module__
            and function.__qualname__ == f"{shape_class.__name__}.{name}"
            and not hasattr(function, "__wrapped__")
        )

    def _uses_standard_iteration(self, component_class):
        """まとめての取得を使ってよいか調べる。

        要素1つのクラスや反復が拡張されていない場合だけ、まとめての取得を使う。

        Args:
            component_class (type): その操作の標準の、要素1つのクラス。

        Returns:
            bool: 要素1つのクラス・反復・シェイプがすべて標準の実装ならTrue。
        """
        return (
            self.component_class is component_class
            and type(self).__iter__ is _COMPONENTS_ITER
            and self._has_standard_component()
            and self._has_standard_shape()
        )

    def _uses_standard_vertices(self):
        """途中で作る頂点の集まりについても、作成と反復が標準のままか調べる。

        Returns:
            bool: 利用側がVertices/Vertexを差し替えていなければTrue。
        """
        # vertexはこのモジュールを継承するため、循環を避けて使う時点で読み込む。
        from .vertex import Vertex, Vertices

        return (
            Vertices.component_class is Vertex
            and self._has_standard_component(Vertex)
            and self._has_standard_shape(Vertex)
            and Vertices.__init__ is _COMPONENTS_INIT
            and Vertices.__iter__ is _COMPONENTS_ITER
        )

    def _mesh_vertex_indices(self, count_name, vertices_method):
        """今のメッシュから、各要素につながる頂点の番号を集める。

        Args:
            count_name (str): コンポーネントの数を返す、MFnMeshのプロパティ名。
            vertices_method (str): 要素の頂点番号を返す、MFnMeshのメソッド名。

        Returns:
            list[int]: 頂点の番号。持っている順に、つながりの順を保って並ぶ。重なりは、呼び出し元のVerticesが除く。
        """
        Component._require_shape(self.shape, self.component_class.shape_type)
        indices = []
        if self._indices:
            mesh_fn = self.shape._geometry_fn()
            count = getattr(mesh_fn, count_name)
            for index in self._indices:
                Component._require_index_range(index, count)
                indices.extend(getattr(mesh_fn, vertices_method)(index))
        return indices

    def _name_prefix(self):
        """全部の番号をまとめて確かめ直し、``<シェイプの完全パス>.<種類>`` を返す。

        Returns:
            str: ``|cube|cubeShape.vtx`` のような接頭辞。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が現在の要素数の範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        self._require_valid()
        return f"{self._shape.getFullName()}.{self.component_class.component_type}"

    def _repr_indices(self):
        """reprに表示する番号を、持っている順で返す。カーブのCVは、cmdsで使う番号に直す。

        Returns:
            Sequence[int]: 表示用の番号列。
        """
        return self._indices

    def _require_valid(self):
        """シェイプと、持っている番号をまとめて確かめる。

        名前や、要素1つのオブジェクトは作らない。

        Raises:
            TypeError: シェイプの型が違う場合。
            IndexError: トポロジーを変えたことで、番号が範囲の外になった場合。
            RuntimeError: シェイプが無効な場合。
        """
        component_class = self.component_class
        if not self._shape.isValid():
            raise RuntimeError("コンポーネントのシェイプが無効です")
        if self._shape.getType() != component_class.shape_type:
            raise TypeError(f"{component_class.shape_type}のシェイプを指定してください")
        if self._indices:
            largest = max(self._indices)
            if largest >= component_class._element_count(self._shape):
                raise IndexError(f"コンポーネントの番号が範囲外です: {largest}")

    @staticmethod
    def _range_name(prefix, start, end):
        """範囲指定のコンポーネント名を作る。

        Args:
            prefix (str): ``<シェイプの完全パス>.<種類>``。
            start (int): 先頭の番号。
            end (int): 末尾の番号。先頭と同じなら1つだけの名前にする。

        Returns:
            str: ``prefix[start]`` または ``prefix[start:end]``。
        """
        if start == end:
            return f"{prefix}[{start}]"
        return f"{prefix}[{start}:{end}]"

    def _get_coordinate(self, axis, **space):
        """指定した軸の値を、持っている順に返す。axisは派生クラスが選ぶ。

        Args:
            axis: 座標成分の番号。0=X、1=Y、2=Z。
            **space: 座標空間の指定。worldSpace=Trueでワールド空間。
        """
        return [point[axis] for point in self.getPosition(**space)]


_COMPONENTS_INIT = Components.__init__
_COMPONENTS_ITER = Components.__iter__


def _flat_input(cls, shape, items):
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
    result = []
    positions = []
    multis = []
    for item in items:
        if isinstance(item, (tuple, list)):
            if len(item) != cls.index_size:
                raise ValueError(f"{cls.__name__}の番号は{cls.index_size}個の数値で指定してください: {len(item)}個")
            numbers = []
            for number in item:
                if isinstance(number, bool):
                    raise TypeError("コンポーネントの番号は整数で指定してください(boolは指定できません)")
                number = operator.index(number)
                if number < 0:
                    raise IndexError(f"コンポーネントの番号が範囲外です: {tuple(item)}")
                numbers.append(number)
            positions.append(len(result))
            multis.append(tuple(numbers))
            result.append(None)
            continue
        if isinstance(item, bool):
            raise TypeError("コンポーネントの番号は整数で指定してください(boolは指定できません)")
        result.append(operator.index(item))
    if multis:
        for position, flat in zip(positions, cls._flat_indices(shape, multis)):
            result[position] = flat
    return result


def _component_name(prefix, numbers):
    """``<シェイプ>.<種類>`` と複数の番号から、``cv[1][2]`` のようなコンポーネント名を作る。

    Args:
        prefix (str): ``<シェイプの名前>.<種類>``。
        numbers (Sequence[int]): cmds用の番号。

    Returns:
        str: コンポーネント名。
    """
    return prefix + "".join(f"[{number}]" for number in numbers)


class _MultiIndexComponent:
    """番号を複数持つコンポーネント1つに共通の処理。

    ``cv[u][v]``・``pt[s][t][u]``・``vtxFace[v][f]`` のように、番号を複数持つ要素に使う。
    :class:`Component` の具体的なクラスと組み合わせて使う(``class SurfaceCV(_MultiIndexComponent, PointComponent)``)。

    持っている :attr:`~Component.index` は、要素を一列に並べたときの通し番号になる。
    ``==``・ハッシュ・:attr:`Components.indices` は、この通し番号を使う。
    複数の番号は :meth:`getMultiIndex` で取得する。
    具体的なクラスは ``index_size`` と、``_element_count``・``_multi_indices``・``_flat_indices`` を定義する。
    """

    #: 番号の数。具体的なクラスが定義する。
    index_size = 0

    if TYPE_CHECKING:
        _shape: "Shape"
        _index: int
        shape_type: Optional[str]
        component_type: Optional[str]
        _require_shape: Callable[..., None]
        _require_valid: Callable[[], None]
        _multi_indices: Callable[..., List[Tuple[int, ...]]]
        _flat_indices: Callable[..., List[int]]

    def __init__(self, shape, index):
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
        self._shape = shape
        self._require_shape(shape, self.shape_type)
        self._index = _flat_input(type(self), shape, [index])[0]
        self._require_valid()

    def getFullName(self):
        """今のDAGパスと複数の番号を使って、コンポーネント名を取得する。

        Returns:
            str: ``|plane|planeShape.cv[1][2]`` のような名前。周期曲面で重なっているCVは、先頭側の番号で表す。
        """
        self._require_valid()
        numbers = self._multi_indices(self._shape, [self._index], command=True)[0]
        return _component_name(f"{self._shape.getFullName()}.{self.component_type}", numbers)

    def getMultiIndex(self):
        """この要素の複数の番号を、今の形状から取得する。

        Returns:
            tuple[int, ...]: ``(u, v)``・``(s, t, u)``・``(頂点, フェース)`` のような番号。

        Raises:
            TypeError: 対応していないシェイプの型の場合。
            IndexError: 番号が今の範囲の外にある場合。
            RuntimeError: シェイプが無効な場合。
        """
        self._require_valid()
        return self._multi_indices(self._shape, [self._index])[0]


class _MultiIndexComponents:
    """番号を複数持つコンポーネントの集まりに共通の処理。

    :class:`Components` の具体的なクラスと組み合わせて使う。
    番号の指定には、通し番号と複数の番号を混ぜて使える。持つのは通し番号にする。
    名前は範囲にまとめない。
    """

    if TYPE_CHECKING:
        _shape: "Shape"
        _indices: Tuple[int, ...]
        component_class: Any
        isValid: Callable[[], bool]
        _require_valid: Callable[[], None]

    def __init__(self, shape, indices=None):
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
        self._shape = shape
        component_class = self.component_class
        Component._require_shape(shape, component_class.shape_type)
        count = component_class._element_count(shape)
        if indices is None:
            self._indices = tuple(range(count))
            return
        if isinstance(indices, (str, bytes)):
            raise TypeError("indicesはコンポーネントの番号の並びで指定してください")
        flats = _flat_input(component_class, shape, list(indices))
        for index in flats:
            Component._require_index_range(index, count)
        self._indices = tuple(dict.fromkeys(flats))

    def __repr__(self):
        """デバッグ用に、型名と先頭の要素の名前を表す文字列を返す。

        Returns:
            str: ``SurfaceCVs('planeShape.cv[0][0]', 'planeShape.cv[0][1]')`` のような文字列。多い場合は数を付ける。
                空なら ``SurfaceCVs('planeShape', count=0)``、無効なら ``<SurfaceCVs invalid>``。
        """
        cls = type(self).__name__
        if not self.isValid():
            return f"<{cls} invalid>"
        shape = self._shape.getName()
        if not self._indices:
            return f"{cls}({shape!r}, count=0)"
        prefix = f"{shape}.{self.component_class.component_type}"
        shown = self.component_class._multi_indices(self._shape, self._indices[:_REPR_LIMIT], command=True)
        text = ", ".join(repr(_component_name(prefix, numbers)) for numbers in shown)
        if len(self._indices) > _REPR_LIMIT:
            return f"{cls}({text}, ..., count={len(self._indices)})"
        return f"{cls}({text})"

    def getFullNames(self):
        """持っている順に、完全パスのコンポーネント名を取得する。

        Returns:
            list[str]: ``|plane|planeShape.cv[1][2]`` のような、要素ごとの名前。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        self._require_valid()
        prefix = f"{self._shape.getFullName()}.{self.component_class.component_type}"
        return [_component_name(prefix, numbers) for numbers in self.component_class._multi_indices(self._shape, self._indices, command=True)]

    def getCompactNames(self):
        """cmdsへ渡す名前を返す。

        番号を複数持つ要素は範囲にまとめないので、:meth:`getFullNames` と同じ名前を返す。

        Returns:
            list[str]: 持っている順のコンポーネント名。

        Raises:
            TypeError: 対応しないシェイプ型の場合。
            IndexError: いずれかの番号が範囲外の場合。
            RuntimeError: シェイプが無効な場合。
        """
        return self.getFullNames()
