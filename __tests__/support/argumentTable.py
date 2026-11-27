"""引数を網羅するテスト(``support.argumentSweep``)の、Mayaを使わない部分。

docstring の Args・Raises の読み取り、引数の型の分類、値の候補と「違う型の値」の生成、
2つの引数の組(ペアワイズ)の生成、「正しい呼び方の表」の1行(:class:`Method`)と、
値の作り直し(:func:`resolve`)・可変長の引数を展開した呼び出し(:func:`invoke`)を置く。
Mayaを起動せずに ``noMaya/test_argumentTable.py`` から確かめられるよう、ここでは maya を import しない。
"""

import fnmatch
import inspect
import itertools
import math
import re

SECTION = re.compile(r"^(Args|Returns|Yields|Raises|Examples|Note|Notes|Warning|See Also|Attributes):$")
ARG_LINE = re.compile(r"^\*{0,2}(\w+)\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)\s*:\s*(.*)$")
RAISES_LINE = re.compile(r"^([A-Z]\w*(?:Error|Exception|Exit))\s*:")
CHOICE = re.compile(r'``"([^"`]+)"``')
ALIAS = re.compile(r"^(\w+)の短縮名")

#: 引数の型の分類。docstring の型の文字列を ``|`` で分けた部分ごとに1つを決める。
#: ``any`` は ``object``・``Any``(どの値も受け付ける。説明にノード・Plug と書いた ``object`` は ``node``)。
KINDS = ("bool", "int", "float", "str", "choice", "none", "sequence", "plug", "node", "callable", "any", "other")

#: 数学型・並びとして扱う型の名前(docstring の型の文字列の先頭)。
SEQUENCE_NAMES = (
    "Iterable",
    "Sequence",
    "list",
    "tuple",
    "set",
    "dict",
    "Vector",
    "Translate",
    "Scale",
    "Shear",
    "Point",
    "EulerRotate",
    "Quaternion",
    "Matrix",
    "Transformation",
    "MVector",
    "MPoint",
    "MFloatPoint",
    "MFloatVector",
    "MMatrix",
    "MQuaternion",
    "MEulerRotation",
    "MTransformationMatrix",
)

#: 段1の数の候補。既定値と表の候補に足す(境界: 0・1・負・大きい値)。
INT_VALUES = (0, 1, -1, 100)
FLOAT_VALUES = (0.0, 1.0, -1.5, 1000.0)

#: 段3で1メソッドあたりに作る組の上限の既定。
DEFAULT_LIMIT = 200


class Lazy:
    """呼ぶ直前に作る値(新しく作ったノード・削除済みのノードなど)。

    表の値の候補・違う型の値に置くと、テストの実行時に ``make(case)`` を呼んだ結果に置き換わる。
    並び(list・tuple)・辞書の中に置いてもよい(中の Lazy も作る)。

    Attributes:
        make (callable): テストケースを受け取り、渡す値を返す関数。``args=True`` なら
            ``make(case, kwargs)`` で、ほかの引数(Lazy でない値と ``args=False`` の Lazy を作った値)の辞書も受け取る。
        label (str): subTest と出力に出す名前。
        args (bool): True なら、ほかの引数の辞書も受け取る(3つ以上の引数がそろって決まる値に使う)。
    """

    def __init__(self, make, label, args=False):
        self.make = make
        self.label = label
        self.args = args

    def __repr__(self):
        return self.label


class Known:
    """``Method.known`` の理由に、当てはまる Maya の版を付ける。

    Attributes:
        reason (str): 理由。
        versions (tuple[int, ...] | None): 当てはまる Maya の版(``2022`` など)。None ならすべての版。
    """

    def __init__(self, reason, versions=None):
        self.reason = reason
        self.versions = None if versions is None else tuple(versions)

    def __repr__(self):
        return f"Known({self.reason!r}, versions={self.versions!r})"

    def applies(self, version):
        """版に当てはまるかを返す。

        Args:
            version (int | None): Maya の版。None なら版を問わない。

        Returns:
            bool: 当てはまるなら True。
        """
        return self.versions is None or version is None or version in self.versions


class ErrorState:
    """状態で決まる例外(削除済み・アンロード中など)を確かめる指定。``Method.errors`` に置く。

    ``test_<メソッド>_errors`` が、作り直した対象を ``prepare`` でその状態にしてから正しい呼び方で呼び、
    ``error`` の例外になり、シーンが変わらないことを確かめる。

    Attributes:
        label (str): subTest と出力に出す名前(``"削除済み"`` など)。
        prepare (callable): テストケースと対象を受け取り、対象をその状態にする。値を返せば、その値を対象として呼ぶ。
        error (type | tuple[type, ...] | str): 期待する例外の型(型の名前でもよい。派生も可)。
        kwargs (dict): 正しい呼び方へ足す・置き換える引数。
    """

    def __init__(self, label, prepare, error, kwargs=None):
        self.label = label
        self.prepare = prepare
        self.error = error
        self.kwargs = dict(kwargs or {})

    def matches(self, error):
        """例外が期待する型かを返す。

        Args:
            error (BaseException): 起きた例外。

        Returns:
            bool: 期待する型(またはその派生)なら True。
        """
        expected = self.error if isinstance(self.error, tuple) else (self.error,)
        names = {item if isinstance(item, str) else item.__name__ for item in expected}
        return isDocumented(error, names)


#: 削除済みのノード(テストケースの ``deletedNode()`` で作る)。
DELETED_NODE = Lazy(lambda case: case.deletedNode(), "<削除済みのノード>")
#: 削除済みのノードのPlug(テストケースの ``deletedPlug()`` で作る)。
DELETED_PLUG = Lazy(lambda case: case.deletedPlug(), "<削除済みのPlug>")
#: 存在しないノードの名前(テストケースの ``name()`` で名前空間付きにする)。
MISSING_NAME = Lazy(lambda case: case.name("argumentSweepMissing"), "'<存在しない名前>'")
#: 選べる値に無い文字列。
INVALID_CHOICE = "__argumentSweepInvalid__"


class RoundTrip:
    """set の後の get が同じ値を返すことを確かめる指定。

    Attributes:
        getter (str): 読み出すメソッドの名前。
        value (str): 書いた値の引数の名前。
        shared (tuple[str, ...]): get にも同じ値で渡す引数の名前(``worldSpace``・``at`` など)。
        skip (callable | None): 引数の辞書を受け取り、Trueなら確かめない(``relative=True`` など、値が書いた値と違うとき)。
        places (int): 比べる小数の桁。
        fixed (dict): get へいつも渡す引数(省けない引数など)。``shared`` で渡す値が優先する。
    """

    def __init__(self, getter, value="value", shared=(), skip=None, places=6, fixed=None):
        self.getter = getter
        self.value = value
        self.shared = tuple(shared)
        self.skip = skip
        self.places = places
        self.fixed = dict(fixed or {})


class Method:
    """「正しい呼び方の表」の1行。メソッドごとに1つ書く。

    Attributes:
        name (str): メソッドの名前(``"setTranslation"``)。
        setup (callable): テストケースを受け取り、メソッドを呼ぶ対象(ノード・Plug など)を作って返す。
            setUp の後(書き込むメソッドは呼ぶたび)に、テストの名前空間の中で呼ばれる。
        args (tuple): 正しい呼び方の位置引数。引数の名前に結び付けて、キーワードで渡す。
        kwargs (dict): 正しい呼び方のキーワード引数。
        values (dict[str, Iterable]): 引数ごとの値の候補。docstring から作る候補に足す
            (``replace`` に名前を入れた引数は置き換える)。:class:`Lazy` も置ける。
        replace (tuple[str, ...]): values の候補だけを使う引数の名前。
        invalid (dict[str, Iterable]): 段2の「違う型の値」。書いた引数は自動の値を置き換える(空にすると段2を行わない)。
        skip (tuple[str, ...]): 網羅しない引数の名前。
        conflicts (tuple): 同時に指定できない組。引数の名前の組(両方を渡したら TypeError)か、
            引数の辞書を受け取り、同時に指定できない組なら True を返す関数。
        expect (callable | None): 例外にならなかった呼び出しごとに ``expect(case, call)`` を呼ぶ(結果を cmds・om2 で確かめる)。
            ``call`` は :class:`Call`。
        state (callable | None): テストケースと対象を受け取り、比べられるシーンの状態を返す。
            省略時はテストケースの ``STATE``、それも無ければテストの名前空間のノード・アトリビュートの値・接続を読む。
        roundTrip (RoundTrip | None): set の後の get が同じ値を返すことを確かめる。
        plural (callable | None): テストケースを受け取り、(複数形, 単数の並び) を返す。複数形から呼んだ結果が、
            単数を1つずつ呼んだ結果の並びと同じことを確かめる。
        writes (bool | None): シーンを変えるメソッドか。省略時は名前が get・is・has・list・find で始まらなければ True。
        known (dict): 本体との食い違いとして記録した場合と理由。キーは ``"段:引数=値"`` の形の型紙(fnmatch の ``*`` が使える。
            ``[`` はそのままの文字としても比べる)か、``(段, 引数の辞書)`` を受け取り当てはまれば True を返す関数。
            理由は文字列か :class:`Known`(版を限る)。通常の実行からは外し、expectedFailure のテストで、まだ食い違っていることを確かめる。
        limit (int): 段3で作る組の上限。
        function (callable | None): 対象のメソッドの代わりに呼ぶ関数(モジュールの関数・クラスメソッド・静的メソッド)。
            対象(setup の戻り値)は状態・expect にだけ使う。省略時は ``getattr(対象, name)`` を呼ぶ
            (対象がクラス・モジュールなら、そのクラスメソッド・静的メソッド・関数をそのまま呼ぶ)。
        variant (str | None): テストの名前に足す接尾辞(``test_<name>_<variant>_values``)。同じメソッドを別の呼び方で2行置くとき。
            省略して同じ名前が重なった行は ``_2``・``_3`` と番号を付ける。
        undoable (bool): False なら Undo に記録しないメソッド(段3で、Undo の記録が無いことを確かめ、Undo・redo は確かめない)。
        reset (callable | None): 呼び出しごとに、テストケースと対象を受け取って後始末をする(登録を増やすメソッドの解除など)。
        context (bool): True なら、戻り値を with で入って出てから状態を読む(コンテキストマネージャーを返すメソッド)。
        combos (Iterable[dict]): 段3で上限によらず必ず通す組(3つ以上の引数でもよい)。
        errors (Iterable[ErrorState]): 状態で決まる例外を確かめる指定(``test_<name>_errors``)。
        skipCalling (dict[str, str]): 段4(呼び方)で確かめない項目(``"defaults"``・``"positional"``・``"keywordOnly"``)と理由。
            2回呼ぶと結果の名前が変わる・ファイルが残るなど、呼び方を変えた2回の結果を比べられない行に書く。
    """

    def __init__(
        self,
        name,
        setup,
        args=(),
        kwargs=None,
        values=None,
        replace=(),
        invalid=None,
        skip=(),
        conflicts=(),
        expect=None,
        state=None,
        roundTrip=None,
        plural=None,
        writes=None,
        known=None,
        limit=DEFAULT_LIMIT,
        function=None,
        variant=None,
        undoable=True,
        reset=None,
        context=False,
        combos=(),
        errors=(),
        skipCalling=None,
    ):
        self.name = name
        self.setup = setup
        self.args = tuple(args)
        self.kwargs = dict(kwargs or {})
        self.values = dict(values or {})
        self.replace = tuple(replace)
        self.invalid = dict(invalid or {})
        self.skip = tuple(skip)
        self.conflicts = tuple(conflicts)
        self.expect = expect
        self.state = state
        self.roundTrip = roundTrip
        self.plural = plural
        self.writes = (not name.startswith(("get", "is", "has", "list", "find"))) if writes is None else writes
        self.known = dict(known or {})
        self.limit = limit
        self.function = function
        self.variant = variant
        self.undoable = undoable
        self.reset = reset
        self.context = context
        self.combos = tuple(dict(combo) for combo in combos)
        self.errors = tuple(errors)
        self.skipCalling = dict(skipCalling or {})

    @property
    def testName(self):
        """テストの名前に使う名前(``name`` と ``variant``)を返す。

        Returns:
            str: ``setX`` か ``setX_<variant>``。
        """
        return f"{self.name}_{self.variant}" if self.variant else self.name

    def isKnown(self, label, kwargs=None, version=None):
        """食い違いとして記録した場合なら、その理由を返す。

        Args:
            label (str): 場合の名前(``"invalid:relative=1"`` など)。
            kwargs (dict | None): 渡す引数。関数で書いた known に渡す(None なら関数の known は見ない)。
            version (int | None): Maya の版。:class:`Known` の版と比べる(None なら版を問わない)。

        Returns:
            str | None: 理由。記録していなければ None。
        """
        stage = label.split(":", 1)[0]
        for pattern, reason in self.known.items():
            if isinstance(reason, Known):
                if not reason.applies(version):
                    continue
                reason = reason.reason
            if callable(pattern):
                if kwargs is not None and pattern(stage, kwargs):
                    return reason
            elif matchLabel(label, pattern):
                return reason
        return None

    def hasVersionedKnown(self, version):
        """この版に当てはまらない :class:`Known` があるかを返す。

        Args:
            version (int | None): Maya の版。

        Returns:
            bool: 版で外れた known があるなら True。
        """
        return any(isinstance(reason, Known) and not reason.applies(version) for reason in self.known.values())

    def valuesFor(self, param):
        """引数の、表に書いた値の候補を返す(可変長の引数は ``"*"``・``"**"`` のキーでもよい)。

        Args:
            param (Parameter): 引数。

        Returns:
            tuple: 値の候補。
        """
        return tuple(self.values.get(param.name, self.values.get(param.variadic, ()) if param.variadic else ()))

    def invalidFor(self, param):
        """引数の、表に書いた段2の値を返す。書いていなければ None。

        Args:
            param (Parameter): 引数。

        Returns:
            tuple | None: 段2の値。
        """
        for key in (param.name, param.variadic):
            if key and key in self.invalid:
                return tuple(self.invalid[key])
        return None

    def mentions(self, name, star):
        """可変長の引数を、表の values・invalid に書いたかを返す。

        Args:
            name (str): 引数の名前。
            star (str): ``"*"`` か ``"**"``。

        Returns:
            bool: 書いたなら True。
        """
        return any(key in table for key in (name, star) for table in (self.values, self.invalid))

    def conflicting(self, kwargs):
        """引数の辞書が、同時に指定できない組を含むかを返す。

        Args:
            kwargs (dict): 渡す引数。

        Returns:
            bool: 同時に指定できない組を含むなら True。
        """
        for rule in self.conflicts:
            if callable(rule):
                if rule(kwargs):
                    return True
            elif all(name in kwargs for name in rule):
                return True
        return False


class Call:
    """1回の呼び出しの記録。``Method.expect`` に渡す。

    Attributes:
        target (object): メソッドを呼んだ対象。
        kwargs (dict): 渡した引数(:class:`Lazy` は作った値)。
        result (object): 戻り値。
        stage (str): ``"values"``・``"pairs"`` のどれか。
        before (object): 呼ぶ前の状態(``Method.state`` などで読んだもの)。
    """

    def __init__(self, target, kwargs, result, stage, before=None):
        self.target = target
        self.kwargs = kwargs
        self.result = result
        self.stage = stage
        self.before = before


def sections(doc):
    """docstring を見出し(``Args:`` など)ごとの行に分ける。

    Args:
        doc (str): docstring。

    Returns:
        dict[str, list[str]]: 見出しと、その下の行(前後の空白を除く)。
    """
    result, current = {}, None
    for line in (doc or "").splitlines():
        stripped = line.strip()
        if SECTION.match(stripped):
            current = stripped[:-1]
            result[current] = []
        elif current is not None:
            result[current].append(stripped)
    return result


def argDocs(doc):
    """docstring の Args を、引数ごとの (型の文字列, 説明) にする。

    Args:
        doc (str): docstring。

    Returns:
        dict[str, tuple[str, str]]: 引数の名前と、型の文字列・説明。
    """
    result, current = {}, None
    for line in sections(doc).get("Args", []):
        match = ARG_LINE.match(line)
        if match:
            current = match.group(1)
            result[current] = [match.group(2), match.group(3)]
        elif current and line:
            result[current][1] += " " + line
    return {name: (type_text, text) for name, (type_text, text) in result.items()}


def raisesNames(doc):
    """docstring の Raises に書いた例外の型の名前を集める。

    Args:
        doc (str): docstring。

    Returns:
        set[str]: 例外の型の名前。
    """
    names = set()
    for line in sections(doc).get("Raises", []):
        match = RAISES_LINE.match(line)
        if match:
            names.add(match.group(1))
    return names


def isDocumented(error, names):
    """例外が、docstring の Raises に書いた型(またはその派生)かを返す。

    Args:
        error (BaseException): 起きた例外。
        names (Iterable[str]): Raises の型の名前。

    Returns:
        bool: 書いた型なら True。
    """
    names = set(names)
    return any(cls.__name__ in names for cls in type(error).__mro__)


def splitTypes(type_text):
    """型の文字列を、括弧の外の ``|`` と ``,`` で分ける(``Iterable[float] | None`` → 2つ)。

    Args:
        type_text (str): docstring の型の文字列。

    Returns:
        list[str]: 分けた型の文字列。
    """
    parts, depth, current = [], 0, ""
    for char in type_text:
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
        if depth == 0 and char in "|,":
            parts.append(current.strip())
            current = ""
            continue
        current += char
    parts.append(current.strip())
    return [part for part in parts if part and part != "optional"]


def kindOf(part, text=""):
    """型の文字列の1つの部分を、:data:`KINDS` のどれかに分ける。

    Args:
        part (str): ``|`` で分けた型の文字列の1つ。
        text (str): 引数の説明(選べる値 ``"x"`` を探す)。

    Returns:
        str: 分類の名前。
    """
    head = part.split("[")[0].strip().split(".")[-1]
    if head == "bool":
        return "bool"
    if head == "int":
        return "int"
    if head in ("float", "Number", "MAngle", "MDistance", "MTime"):
        return "float"
    if head == "str" or head.startswith("Literal"):
        return "choice" if CHOICE.search(text) or head.startswith("Literal") else "str"
    if head == "None":
        return "none"
    if head in SEQUENCE_NAMES:
        return "sequence"
    if head in ("Callable", "callable", "function"):
        return "callable"
    if "Plug" in head:
        return "plug"
    if head in ("object", "Any"):
        # 説明にノード・Plug と書いた object はノードとして段2の値を作る。それ以外は、どの値も受け付ける。
        return "node" if head == "object" and re.search(r"Node|Plug|ノード", text or "") else "any"
    if head[:1].isupper() or head == "node":
        return "node"
    return "other"


def kindsOf(type_text, text=""):
    """型の文字列を、分類の名前の並びにする(同じ分類は1つ)。

    Args:
        type_text (str): docstring の型の文字列。
        text (str): 引数の説明。

    Returns:
        list[str]: 分類の名前。docstring の順。
    """
    result = []
    for part in splitTypes(type_text):
        kind = kindOf(part, text)
        if kind not in result:
            result.append(kind)
    return result


def choices(text):
    """説明に書いた選べる値(````"x"````)を集める。

    Args:
        text (str): 引数の説明。

    Returns:
        list[str]: 選べる値。書いた順で重複なし。
    """
    result = []
    for value in CHOICE.findall(text):
        if value not in result:
            result.append(value)
    return result


def aliasOf(text):
    """説明が「Xの短縮名」で始まれば、その長い名前を返す。

    Args:
        text (str): 引数の説明。

    Returns:
        str | None: 長い名前。短縮名でなければ None。
    """
    match = ALIAS.match(text or "")
    return match.group(1) if match else None


def isPlain(value):
    """既定値として候補に入れてよい値(引数の未指定を表す目印でない値)かを返す。

    Args:
        value (object): 既定値。

    Returns:
        bool: None・bool・数・文字列・それらのタプルなら True。
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return True
    return isinstance(value, tuple) and all(isPlain(item) for item in value)


def same(left, right, places=6):
    """2つの値が同じかを返す。数は小数 ``places`` 桁まで、並びは要素ごと、それ以外は ``str`` が同じなら同じ。

    om2 の点(4成分で w=1)と3成分の並びは、w を除いて比べる。

    mlib の Node・Plug は ``str`` が名前なので、同じ対象なら同じになる。

    Args:
        left (object): 値。
        right (object): 値。
        places (int): 比べる小数の桁。

    Returns:
        bool: 同じなら True。
    """
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        if math.isnan(left) or math.isnan(right):
            return math.isnan(left) and math.isnan(right)
        return abs(left - right) <= 0.5 * 10 ** (-places) * max(1.0, abs(left), abs(right))
    if isinstance(left, (str, bytes)) or isinstance(right, (str, bytes)):
        return str(left) == str(right)
    try:
        left_items, right_items = list(left), list(right)
    except TypeError:
        return left == right or str(left) == str(right)
    # om2 の点(MPoint)は w=1 の4成分なので、3成分の値とは w を除いて比べる。
    if len(left_items) == 4 and len(right_items) == 3 and same(left_items[3], 1.0):
        left_items = left_items[:3]
    elif len(right_items) == 4 and len(left_items) == 3 and same(right_items[3], 1.0):
        right_items = right_items[:3]
    if len(left_items) != len(right_items):
        return False
    return all(same(a, b, places) for a, b in zip(left_items, right_items))


def _unique(values):
    """順を保って重複を除く(True と 1 は別の値として扱う)。"""
    result, seen = [], []
    for value in values:
        key = (type(value), repr(value))
        if key not in seen:
            seen.append(key)
            result.append(value)
    return result


class Parameter:
    """網羅する1つの引数。シグネチャと docstring から作る。

    Attributes:
        name (str): 引数の名前。
        default (object): 既定値(``inspect.Parameter.empty`` なら必須)。
        typeText (str): docstring の型の文字列。
        text (str): docstring の説明。
        kinds (list[str]): 分類の名前。
        choices (list[str]): 選べる値。
        alias (str | None): 短縮名なら、その長い名前。
        variadic (str | None): 可変長の引数なら ``"*"``(位置。値は並び)か ``"**"``(キーワード。値は辞書)。
    """

    def __init__(self, name, default, typeText="", text="", variadic=None):
        self.name = name
        self.default = default
        self.typeText = typeText
        self.text = text
        self.kinds = kindsOf(typeText, text) if typeText else []
        self.choices = choices(text) if "choice" in self.kinds else []
        self.alias = aliasOf(text)
        self.variadic = variadic

    def candidates(self, extra=(), replace=False):
        """段1の値の候補を返す。

        可変長の引数は、表に書いた候補(``*`` は並び、``**`` は辞書)だけを使う。

        Args:
            extra (Iterable): 表に書いた候補。
            replace (bool): True なら表の候補だけを使う。

        Returns:
            list: 値の候補(重複なし)。
        """
        if replace or self.variadic:
            return _unique(extra)
        values = list(extra)
        if isPlain(self.default) and self.default is not inspect.Parameter.empty:
            values.insert(0, self.default)
        for kind in self.kinds:
            if kind == "bool":
                values += [True, False]
            elif kind == "int":
                values += list(INT_VALUES)
            elif kind == "float" and "int" not in self.kinds:
                values += list(FLOAT_VALUES)
            elif kind == "choice":
                values += self.choices
            elif kind == "none":
                values.append(None)
        return _unique(values)

    def invalidValues(self):
        """段2の「違う型の値」を返す(どの分類でも受け付けない値だけ)。

        可変長の位置引数(``*``)は、要素の型で作った値を1つだけの並びにする。``**`` は作らない。

        Returns:
            list: 違う型の値。
        """
        if self.variadic == "**":
            return []
        if self.variadic == "*":
            return [(value,) for value in Parameter(self.name, inspect.Parameter.empty, self.typeText, self.text).invalidValues()]
        kinds = set(self.kinds)
        values = []
        if "bool" in kinds:
            values += [1, "yes"]
        if kinds & {"int", "float"}:
            values += ["a", float("nan"), float("inf")]
        if "str" in kinds or "choice" in kinds:
            values.append(1.5)
        if "choice" in kinds and "str" not in kinds:
            values.append(INVALID_CHOICE)
        if "node" in kinds:
            values += [DELETED_NODE, MISSING_NAME]
        if "plug" in kinds:
            values += [DELETED_PLUG, MISSING_NAME]
        if "sequence" in kinds:
            values.append(object())
        return [value for value in _unique(values) if not self.accepts(value)]

    def accepts(self, value):
        """値が、どれかの分類で受け付けられる型かを返す(段2の値を絞るための目安)。

        Args:
            value (object): 値。

        Returns:
            bool: 受け付けられる型なら True。
        """
        kinds = set(self.kinds)
        if "any" in kinds:
            return True
        if isinstance(value, Lazy):
            return False
        if isinstance(value, bool):
            return "bool" in kinds
        if isinstance(value, int):
            return bool(kinds & {"int", "float"})
        if isinstance(value, float):
            return "float" in kinds and math.isfinite(value)
        if isinstance(value, str):
            if "str" in kinds:
                return True
            if "choice" in kinds:
                return value in self.choices
            return bool(kinds & {"node", "plug"}) and value != INVALID_CHOICE
        if value is None:
            return "none" in kinds
        return "other" in kinds or ("callable" in kinds and callable(value))


def parameters(function, doc=None, skip=(), include=()):
    """関数のシグネチャと docstring から、網羅する引数を作る。

    ``self``・``cls`` と ``skip`` に書いた引数は除く。``*args``・``**kwargs`` は ``include`` に名前
    (または ``"*"``・``"**"``)を書いたときだけ入れる。

    Args:
        function (callable): 関数・メソッド。
        doc (str | None): docstring。省略時は ``inspect.getdoc(function)``。
        skip (Iterable[str]): 除く引数の名前。
        include (Iterable[str]): 入れる可変長の引数の名前(``"*"``・``"**"`` でもよい)。

    Returns:
        list[Parameter]: 引数。シグネチャの順。
    """
    doc = inspect.getdoc(function) if doc is None else doc
    docs = argDocs(doc)
    include = set(include)
    result = []
    for name, parameter in inspect.signature(function).parameters.items():
        if name in ("self", "cls") or name in skip:
            continue
        variadic = {parameter.VAR_POSITIONAL: "*", parameter.VAR_KEYWORD: "**"}.get(parameter.kind)
        if variadic and name not in include and variadic not in include:
            continue
        type_text, text = docs.get(name, ("", ""))
        result.append(Parameter(name, parameter.default, type_text, text, variadic))
    return result


def matchLabel(label, pattern):
    """場合の名前が known の型紙に合うかを返す。

    fnmatch の型紙として比べる。ただし ``[`` はそのままの文字とする(値の repr の ``[0, 1]`` を ``[[]`` と書かなくてよい)。
    文字の集まりとして読むのは ``[[]``・``[]]``(以前の書き方)と ``[!...]``(否定)だけ。

    Args:
        label (str): 場合の名前。
        pattern (str): 型紙。

    Returns:
        bool: 合うなら True。
    """
    if label == pattern:
        return True
    parts = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "[" and pattern[index : index + 3] not in ("[[]", "[]]") and pattern[index + 1 : index + 2] != "!":
            parts.append("[[]")
        elif char == "[":
            # 文字の集まりは閉じ括弧までそのまま写す。
            end = pattern.find("]", index + 2)
            end = len(pattern) - 1 if end < 0 else end
            parts.append(pattern[index : end + 1])
            index = end
        else:
            parts.append(char)
        index += 1
    return fnmatch.fnmatchcase(label, "".join(parts))


def _has_args_lazy(value):
    """値(並び・辞書の中を含む)に、ほかの引数を受け取る Lazy があるかを返す。"""
    if isinstance(value, Lazy):
        return value.args
    if type(value) in (list, tuple):
        return any(_has_args_lazy(item) for item in value)
    if type(value) is dict:
        return any(_has_args_lazy(item) for item in value.values())
    return False


def _has_lazy(value):
    """値(並び・辞書の中を含む)に Lazy があるかを返す。"""
    if isinstance(value, Lazy):
        return True
    if type(value) in (list, tuple):
        return any(_has_lazy(item) for item in value)
    if type(value) is dict:
        return any(_has_lazy(item) for item in value.values())
    return False


def _make(value, case, others):
    """値の中の Lazy を作る(並び・辞書の中も作る。Lazy の無い値は同じオブジェクトのまま返す)。"""
    if isinstance(value, Lazy):
        return value.make(case, others) if value.args else value.make(case)
    if not _has_lazy(value):
        return value
    if type(value) in (list, tuple):
        return type(value)(_make(item, case, others) for item in value)
    if type(value) is dict:
        return {key: _make(item, case, others) for key, item in value.items()}
    return value


def resolve(kwargs, case):
    """引数の辞書の中の :class:`Lazy` を作った値にする(並び・辞書の中も作る)。

    ``args=True`` の Lazy は、ほかの引数を作った後に、その辞書を受け取って作る。

    Args:
        kwargs (dict): 引数。
        case (object): Lazy に渡すテストケース。

    Returns:
        dict: 作った値の引数(同じ順)。
    """
    first = {name: _make(value, case, None) for name, value in kwargs.items() if not _has_args_lazy(value)}
    return {name: first[name] if name in first else _make(value, case, dict(first)) for name, value in kwargs.items()}


def invoke(function, kwargs):
    """引数の辞書で関数を呼ぶ。可変長の引数の値は展開して渡す。

    ``*args`` の名前の値(並び)は位置引数として、その前の引数も位置で渡す。``**kwargs`` の名前の値(辞書)は
    キーワードとして展開する。

    Args:
        function (callable): 呼ぶ関数・メソッド。
        kwargs (dict): 引数の名前と値。

    Returns:
        object: 戻り値。
    """
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return function(**kwargs)
    params = list(signature.parameters.values())
    var_positional = next((param for param in params if param.kind is param.VAR_POSITIONAL), None)
    var_keyword = next((param for param in params if param.kind is param.VAR_KEYWORD), None)
    kwargs = dict(kwargs)
    args = []
    if var_positional is not None and var_positional.name in kwargs:
        extra = kwargs.pop(var_positional.name)
        for param in params:
            if param.kind not in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
                break
            if param.name in kwargs:
                args.append(kwargs.pop(param.name))
            elif param.default is not param.empty:
                args.append(param.default)
            else:
                break
        args.extend(extra if isinstance(extra, (list, tuple)) else (extra,))
    if var_keyword is not None and isinstance(kwargs.get(var_keyword.name), dict):
        kwargs.update(kwargs.pop(var_keyword.name))
    return function(*args, **kwargs)


def label(kwargs, names=None):
    """subTest と出力に出す、引数の並びの文字列を返す。

    Args:
        kwargs (dict): 引数。
        names (Iterable[str] | None): 出す引数の名前。省略時はすべて。

    Returns:
        str: ``a=1,b=True`` の形。
    """
    names = list(kwargs) if names is None else list(names)
    return ",".join(f"{name}={kwargs[name]!r}" for name in names if name in kwargs)


def _combos(first, second, candidates):
    """2つの引数の候補の全部×全部を、辞書で順に返す。"""
    for a, b in itertools.product(candidates[first], candidates[second]):
        yield {first: a, second: b}


def pairs(candidates, limit=DEFAULT_LIMIT):
    """2つの引数の値の組を、上限まで作る。

    すべての2つの引数の組について、候補の全部×全部を作る。上限で切るときは、引数の組ごとに1つずつ順に取り、
    後ろの組が欠けないようにする。

    Args:
        candidates (dict[str, list]): 引数の名前と値の候補(並びは引数の順)。
        limit (int): 作る組の上限。

    Returns:
        tuple[list[dict], int]: 組(引数の名前と値の辞書)の並びと、上限で切った数。
    """
    names = [name for name, values in candidates.items() if values]
    generators = [_combos(first, second, candidates) for first, second in itertools.combinations(names, 2)]
    total = sum(len(candidates[first]) * len(candidates[second]) for first, second in itertools.combinations(names, 2))
    result = []
    while generators and len(result) < limit:
        alive = []
        for generator in generators:
            if len(result) >= limit:
                break
            item = next(generator, None)
            if item is not None:
                result.append(item)
                alive.append(generator)
        generators = alive
    return result, total - len(result)
