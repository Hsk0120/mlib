"""引数を網羅するテスト(``support.argumentSweep``)の、Mayaを使わない部分。

docstring の Args・Raises の読み取り、引数の型の分類、値の候補と「違う型の値」の生成、
2つの引数の組(ペアワイズ)の生成、「正しい呼び方の表」の1行(:class:`Method`)を置く。
Mayaを起動せずに ``noMaya/test_argumentTable.py`` から確かめられるよう、ここでは maya を import しない。
"""

import fnmatch
import inspect
import itertools
import math
import re

SECTION = re.compile(r"^(Args|Returns|Yields|Raises|Examples|Note|Notes|Warning|See Also|Attributes):$")
ARG_LINE = re.compile(r"^(\w+)\s*\(([^)]*(?:\([^)]*\)[^)]*)*)\)\s*:\s*(.*)$")
RAISES_LINE = re.compile(r"^([A-Z]\w*(?:Error|Exception|Exit))\s*:")
CHOICE = re.compile(r'``"([^"`]+)"``')
ALIAS = re.compile(r"^(\w+)の短縮名")

#: 引数の型の分類。docstring の型の文字列を ``|`` で分けた部分ごとに1つを決める。
KINDS = ("bool", "int", "float", "str", "choice", "none", "sequence", "plug", "node", "callable", "other")

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

    Attributes:
        make (callable): テストケースを受け取り、渡す値を返す関数。
        label (str): subTest と出力に出す名前。
    """

    def __init__(self, make, label):
        self.make = make
        self.label = label

    def __repr__(self):
        return self.label


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
    """

    def __init__(self, getter, value="value", shared=(), skip=None, places=6):
        self.getter = getter
        self.value = value
        self.shared = tuple(shared)
        self.skip = skip
        self.places = places


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
            省略時はテストの名前空間のノード・アトリビュートの値・接続を読む。
        roundTrip (RoundTrip | None): set の後の get が同じ値を返すことを確かめる。
        plural (callable | None): テストケースを受け取り、(複数形, 単数の並び) を返す。複数形から呼んだ結果が、
            単数を1つずつ呼んだ結果の並びと同じことを確かめる。
        writes (bool | None): シーンを変えるメソッドか。省略時は名前が get・is・has・list・find で始まらなければ True。
        known (dict[str, str]): 本体との食い違いとして記録した場合(``"段:引数=値"`` の形。fnmatch の ``*`` が使える)と理由。
            通常の実行からは外し、expectedFailure のテストで、まだ食い違っていることを確かめる。
        limit (int): 段3で作る組の上限。
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

    def isKnown(self, label):
        """食い違いとして記録した場合なら、その理由を返す。

        Args:
            label (str): 場合の名前(``"invalid:relative=1"`` など)。

        Returns:
            str | None: 理由。記録していなければ None。
        """
        for pattern, reason in self.known.items():
            if fnmatch.fnmatchcase(label, pattern):
                return reason
        return None

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
    """

    def __init__(self, target, kwargs, result, stage):
        self.target = target
        self.kwargs = kwargs
        self.result = result
        self.stage = stage


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
    if head[:1].isupper() or head in ("node", "object"):
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
    """

    def __init__(self, name, default, typeText="", text=""):
        self.name = name
        self.default = default
        self.typeText = typeText
        self.text = text
        self.kinds = kindsOf(typeText, text) if typeText else []
        self.choices = choices(text) if "choice" in self.kinds else []
        self.alias = aliasOf(text)

    def candidates(self, extra=(), replace=False):
        """段1の値の候補を返す。

        Args:
            extra (Iterable): 表に書いた候補。
            replace (bool): True なら表の候補だけを使う。

        Returns:
            list: 値の候補(重複なし)。
        """
        if replace:
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

        Returns:
            list: 違う型の値。
        """
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


def parameters(function, doc=None, skip=()):
    """関数のシグネチャと docstring から、網羅する引数を作る。

    ``self``・``*args``・``**kwargs`` と ``skip`` に書いた引数は除く。

    Args:
        function (callable): 関数・メソッド。
        doc (str | None): docstring。省略時は ``inspect.getdoc(function)``。
        skip (Iterable[str]): 除く引数の名前。

    Returns:
        list[Parameter]: 引数。シグネチャの順。
    """
    doc = inspect.getdoc(function) if doc is None else doc
    docs = argDocs(doc)
    result = []
    for name, parameter in inspect.signature(function).parameters.items():
        if name in ("self", "cls") or name in skip:
            continue
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        type_text, text = docs.get(name, ("", ""))
        result.append(Parameter(name, parameter.default, type_text, text))
    return result


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
