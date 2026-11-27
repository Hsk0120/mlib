"""公開メソッドの引数を、表から網羅して確かめるテストケース基底。

クラスごとに「正しい呼び方の表」(:class:`support.argumentTable.Method` の並び)を ``METHODS`` に書くと、
メソッドごとに次のテストができる。

- ``test_<メソッド>_values`` (段1): 引数ごとに値の候補を1つずつ差し替えて呼び、例外が出ない
  (docstring の Raises の型は許す)・例外のときシーンが変わらない・``expect`` の確かめ方に合うことを確かめる。
  引数の無いメソッドは1回だけ呼ぶ。
- ``test_<メソッド>_invalid`` (段2): 引数ごとに「違う型の値」を差し替え、docstring の Raises の型になり、
  シーン(ノードの数・名前空間のノードの値・接続)が変わらないことを確かめる。
- ``test_<メソッド>_pairs`` (段3): 2つの引数の値の組(上限つき。引数が1つなら候補を1つずつ、無ければ1回。
  ``combos`` の組は必ず通す)で、例外が Raises の型だけ・同時に指定できない組は TypeError・
  通常の書き込みは Undo 1回で戻り redo で同じ・``fast=True`` と通常でシーンが同じ(fast は Undo に残らない)・
  短縮名と長い名前で同じ・set の後の get が同じ・複数形と単数の並びが同じ、のうち当てはまる性質を確かめる。
- ``test_<メソッド>_errors``: ``errors`` に書いた状態(削除済みなど)で、決めた例外になりシーンが変わらないことを確かめる。
- ``test_<メソッド>_known``: 表の ``known`` に書いた本体との食い違いが、まだ食い違っていることを確かめる(expectedFailure)。

各テストはメソッド・段ごとの件数・上限で切った数・秒数を出力する。
"""

import contextlib
import functools
import inspect
import time
import unittest

import maya.cmds as cmds
from support import argumentTable as table
from support.namespaceCase import NamespaceCase

import mlib
import mlib.core.object

#: 表の1行から作る段。
STAGES = ("values", "invalid", "pairs", "calling")
#: 段4(呼び方)で確かめる項目。
CALLING = ("defaults", "positional", "keywordOnly")


def _maya_version():
    """Maya の版(``2022`` など)を返す。"""
    return int(cmds.about(apiVersion=True)) // 10000


def freeze(result):
    """戻り値の mlib のオブジェクト(とその並び)を、呼んだ時点の名前(の並び)にする。

    書き込むメソッドは呼ぶたびに名前空間を作り直すので、前の呼び出しが返したノード・Plug は無効になる。
    名前にしておけば、短縮名と長い名前の戻り値を比べられる。

    Args:
        result (object): 戻り値。

    Returns:
        object: 名前に置き換えた値。mlib のオブジェクトを含まない値はそのまま。
    """
    # mlib.reload() の後でも今の Object と比べるよう、呼ぶたびにモジュールから取る。
    if isinstance(result, mlib.core.object.Object):
        return str(result)
    if type(result) in (list, tuple):
        return [freeze(item) for item in result]
    module = type(result).__module__ or ""
    if module.startswith("mlib.") and not module.startswith("mlib.maths") and hasattr(result, "__iter__") and not isinstance(result, dict):
        return [freeze(item) for item in result]
    return result


class ArgumentSweepCase(NamespaceCase):
    """``METHODS`` の表から、引数を網羅するテストを作る基底。

    Attributes:
        METHODS (tuple[Method, ...]): 正しい呼び方の表。
        PREFIX (str): 名前空間の先頭。
        STATE (callable | None): 表の ``state`` を省いた行で使う、比べるシーンの状態(テストケースと対象を受け取る関数)。
            None なら :meth:`sceneState`。
    """

    METHODS = ()
    PREFIX = "mlibSweep_"
    STATE = None

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        used = set()
        for method in cls.METHODS:
            name, number = method.testName, 1
            while name in used:
                number += 1
                name = f"{method.testName}_{number}"
            used.add(name)
            for stage in STAGES:
                setattr(cls, f"test_{name}_{stage}", _stage_test(method, stage))
            if method.errors:
                setattr(cls, f"test_{name}_errors", _errors_test(method))
            if method.known:
                setattr(cls, f"test_{name}_known", unittest.expectedFailure(_known_test(method)))

    # ------------------------------------------------------------------
    # 表から使う補助

    def fresh(self, method):
        """名前空間の中身を作り直し、表の setup で対象を作って返す。

        Args:
            method (Method): 表の1行。

        Returns:
            object: メソッドを呼ぶ対象。
        """
        if cmds.namespace(exists=self.ns):
            cmds.namespace(removeNamespace=self.ns, deleteNamespaceContent=True)
        cmds.namespace(add=self.ns)
        return method.setup(self)

    def deletedNode(self):
        """削除済みのノードを返す(段2の値)。

        Returns:
            Node: 削除したノード。
        """
        node = mlib.createNode("transform", name=self.name("sweepDeleted#"))
        cmds.delete(str(node))
        return node

    def deletedPlug(self):
        """削除済みのノードの Plug を返す(段2の値)。

        Returns:
            Plug: 削除したノードの translateX。
        """
        node = mlib.createNode("transform", name=self.name("sweepDeleted#"))
        plug = node.getPlug("translateX")
        cmds.delete(str(node))
        return plug

    @contextlib.contextmanager
    def inNamespace(self):
        """テストの名前空間を今の名前空間にする(``cmds.polyCube`` などが作るシェイプも名前空間の中にできる)。

        Yields:
            str: テストの名前空間。
        """
        current = cmds.namespaceInfo(currentNamespace=True, absoluteName=True)
        cmds.namespace(setNamespace=":" + self.ns)
        try:
            yield self.ns
        finally:
            cmds.namespace(setNamespace=current)

    def sceneState(self):
        """比べるシーンの状態(全体のノードの数、名前空間のノード・keyable の値・ワールドのマトリクス・接続)を返す。

        値はノード・アトリビュートの名前の順に並べる(アトリビュートを消して Undo すると ``listAttr`` の順が変わるため)。
        読めないアトリビュート(blendShape の ``.weight`` など)は None として読む。

        Returns:
            list: 状態。
        """
        nodes = sorted(cmds.ls(self.ns + ":*", long=True) or [])
        values = []
        for node in nodes:
            for attr in cmds.listAttr(node, keyable=True, scalar=True) or []:
                try:
                    values.append((node, attr, cmds.getAttr(node + "." + attr)))
                except (RuntimeError, ValueError, TypeError):
                    values.append((node, attr, None))
            if cmds.objectType(node, isAType="transform"):
                values.append((node, "worldMatrix", cmds.getAttr(node + ".worldMatrix[0]")))
        values.sort(key=lambda item: (item[0], item[1]))
        connections = sorted(cmds.listConnections(nodes, connections=True, plugs=True) or []) if nodes else []
        return [len(cmds.ls()), nodes, values, connections]

    # ------------------------------------------------------------------
    # 実行

    def _state(self, method, target):
        if method.state:
            return method.state(self, target)
        state = type(self).STATE
        return state(self, target) if state else self.sceneState()

    def _function(self, method, target):
        """呼ぶ関数(表の function か、対象のメソッド)を返す。"""
        return method.function if method.function is not None else getattr(target, method.name)

    def _invoke(self, method, target, kwargs):
        """表の1行のメソッドを、作った値の引数で呼ぶ(可変長の引数は展開し、context なら with で入って出る)。"""
        result = table.invoke(self._function(method, target), kwargs)
        if method.context:
            with result:
                pass
        return result

    def _prepare(self, method):
        """表の1行から、対象・引数・Raises・正しい呼び方を作る。"""
        target = self.fresh(method)
        function = self._function(method, target)
        doc = inspect.getdoc(function) or ""
        signature = inspect.signature(function)
        bound = signature.bind_partial(*method.args, **method.kwargs).arguments
        base = {name: value for name, value in bound.items() if name not in ("self", "cls")}
        include = [
            name
            for name, param in signature.parameters.items()
            if (param.kind is param.VAR_POSITIONAL and method.mentions(name, "*")) or (param.kind is param.VAR_KEYWORD and method.mentions(name, "**"))
        ]
        params = table.parameters(function, doc, skip=method.skip, include=include)
        return target, base, params, table.raisesNames(doc)

    def _resolve(self, kwargs):
        return table.resolve(kwargs, self)

    def _call(self, method, target, kwargs, raises, stage, undo=False):
        """1回呼び、例外と状態を確かめる。

        Returns:
            tuple: (成功したか, 戻り値, 呼ぶ前の状態, 呼んだ後の状態, 渡した値)。
            書き込むメソッドの戻り値は :func:`freeze` で名前にする。
        """
        resolved = self._resolve(kwargs)
        if undo:
            cmds.flushUndo()
        before = self._state(method, target)
        conflict = method.conflicting(kwargs)
        try:
            try:
                result = self._invoke(method, target, resolved)
            except Exception as error:
                if conflict:
                    self.assertIsInstance(error, TypeError, f"同時に指定できない組の例外が TypeError でない: {error!r}")
                else:
                    self.assertTrue(table.isDocumented(error, raises), f"docstring の Raises {sorted(raises)} に無い例外: {error!r}")
                self.assertTrue(table.same(self._state(method, target), before), f"例外({type(error).__name__})のあとシーンが変わった")
                return False, error, before, before, resolved
            if conflict:
                self.fail(f"同時に指定できない組なのに例外にならない(戻り値 {result!r})")
            after = self._state(method, target)
            if method.expect:
                method.expect(self, table.Call(target, resolved, result, stage, before))
            return True, (freeze(result) if method.writes else result), before, after, resolved
        finally:
            if method.reset:
                method.reset(self, target)

    def _cases(self, method, stage, params, base):
        """段ごとの (名前, 引数) の並びと、上限で切った数を返す。"""
        if stage == "values":
            if not params:
                return [("values:(引数なし)", dict(base))], 0
            cases = [
                (f"values:{param.name}={value!r}", dict(base, **{param.name: value}))
                for param in params
                for value in param.candidates(method.valuesFor(param), param.name in method.replace)
            ]
            return cases, 0
        if stage == "calling":
            return [(f"calling:{kind}", dict(base)) for kind in CALLING if kind not in method.skipCalling], 0
        if stage == "invalid":
            cases = []
            for param in params:
                values = method.invalidFor(param)
                for value in param.invalidValues() if values is None else values:
                    cases.append((f"invalid:{param.name}={value!r}", dict(base, **{param.name: value})))
            return cases, 0
        candidates = {param.name: param.candidates(method.valuesFor(param), param.name in method.replace) for param in params}
        cut = 0
        if not params:
            cases = [("pairs:(引数なし)", dict(base))]
        elif len(params) == 1:
            name = params[0].name
            cases = [(f"pairs:{name}={value!r}", dict(base, **{name: value})) for value in candidates[name]]
        else:
            combos, cut = table.pairs(candidates, method.limit)
            cases = [("pairs:" + table.label(combo), dict(base, **combo)) for combo in combos]
        fixed = [("pairs:" + table.label(combo), dict(base, **combo)) for combo in method.combos]
        names = {name for name, _ in fixed}
        return fixed + [case for case in cases if case[0] not in names], cut

    def _run_case(self, method, stage, kwargs, params, raises, target, name=""):
        """1件を確かめる。"""
        if stage == "calling":
            self._check_calling(method, name.split(":", 1)[1], kwargs, params, raises, target)
            return
        if stage == "invalid":
            if method.writes:
                target = self.fresh(method)
            resolved = self._resolve(kwargs)
            before = self._state(method, target)
            try:
                result = self._invoke(method, target, resolved)
            except Exception as error:
                self.assertTrue(table.isDocumented(error, raises), f"docstring の Raises {sorted(raises)} に無い例外: {error!r}")
            else:
                self.fail(f"違う型の値を受け付けた(戻り値 {result!r})")
            finally:
                if method.reset:
                    method.reset(self, target)
            self.assertTrue(table.same(self._state(method, target), before), "例外のあとシーンが変わった")
            return
        if stage == "values":
            if method.writes:
                target = self.fresh(method)
            self._call(method, target, kwargs, raises, stage)
            return
        self._check_pair(method, kwargs, params, raises, target)

    def _check_pair(self, method, kwargs, params, raises, target):
        """段3の1件: 性質を確かめる。"""
        names = {param.name for param in params}
        if method.writes:
            target = self.fresh(method)
        ok, result, before, after, resolved = self._call(method, target, kwargs, raises, "pairs", undo=method.writes)
        if not ok:
            return
        if method.writes:
            if kwargs.get("fast") is True:
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True), "fast=True なのに Undo に記録した")
            elif not method.undoable:
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True), "Undo に記録しないメソッド(undoable=False)が Undo に記録した")
            elif cmds.undoInfo(query=True, undoQueueEmpty=True):
                self.assertTrue(table.same(after, before), "Undo に記録せずにシーンを変えた")
            else:
                cmds.undo()
                self.assertTrue(table.same(self._state(method, target), before), "Undo 1回で元に戻らない")
                self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True), "Undo 1回で戻したあと、まだ Undo の記録が残る")
                cmds.redo()
                self.assertTrue(table.same(self._state(method, target), after), "redo で同じ結果にならない")
            if self._compares_fast(method, kwargs, names):
                fast_target = self.fresh(method)
                fast_ok, fast_result, _, fast_after, _ = self._call(method, fast_target, dict(kwargs, fast=True), raises, "pairs")
                # docstring で fast と同時に使えないと決めた組(Raises の NotImplementedError)は比べない。
                if fast_ok or not isinstance(fast_result, NotImplementedError):
                    self.assertTrue(fast_ok, f"fast=True だけ例外になった: {fast_result!r}")
                    self.assertTrue(table.same(fast_after, after), "fast=True と通常でシーンの結果が違う")
        for param in params:
            if param.alias and param.alias in kwargs and param.name not in kwargs and param.alias in names:
                renamed = {(param.name if name == param.alias else name): value for name, value in kwargs.items()}
                alias_target = self.fresh(method) if method.writes else target
                alias_ok, alias_result, _, alias_after, _ = self._call(method, alias_target, renamed, raises, "pairs")
                self.assertTrue(alias_ok, f"短縮名 {param.name} だけ例外になった: {alias_result!r}")
                self.assertTrue(table.same(alias_result, result), f"短縮名 {param.name} と {param.alias} で戻り値が違う")
                if method.writes:
                    self.assertTrue(table.same(alias_after, after), f"短縮名 {param.name} と {param.alias} でシーンの結果が違う")
        self._assert_round_trip(method, kwargs, params, raises, target, resolved)
        if method.plural:
            self._check_plural(method, kwargs, raises, result, after)

    def _check_calling(self, method, kind, kwargs, params, raises, target):
        """段4の1件: 正しい呼び方を、渡し方だけ変えて呼んでも同じ結果になることを確かめる。

        - ``defaults``: 省いた引数へ既定値を明示しても、省いたときと同じ(docstring と署名の既定値が、実際の動きと同じ)。
        - ``positional``: 位置で渡せる引数を位置で渡しても、名前で渡したときと同じ。
        - ``keywordOnly``: キーワード専用の引数を位置で渡すと TypeError になり、シーンは変わらない。
        """
        if method.writes:
            target = self.fresh(method)
        ok, result, _before, after, _resolved = self._call(method, target, kwargs, raises, "calling", undo=method.writes)
        if not ok:
            return
        signature = inspect.signature(self._function(method, target))
        parameters = list(signature.parameters.values())
        # 関数をメソッドに見せる補助(``variadic`` の印を持つ)は、署名から ``*args`` を外してある。
        variadic = any(param.kind is param.VAR_POSITIONAL for param in parameters) or getattr(self._function(method, target), "variadic", False)
        positional = [param for param in parameters if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD)]
        if kind == "defaults":
            explicit = {
                param.name: param.default
                for param in params
                if param.name not in kwargs and not param.variadic and not param.alias and not _is_omitted(param.default)
            }
            if not explicit or method.conflicting(dict(kwargs, **explicit)):
                return
            other = self.fresh(method) if method.writes else target
            other_ok, other_result, _, other_after, _ = self._call(method, other, dict(kwargs, **explicit), raises, "calling")
            self.assertTrue(other_ok, f"既定値を明示すると例外になった({explicit!r}): {other_result!r}")
            self.assertTrue(table.same(other_result, result), f"既定値を明示すると戻り値が違う({explicit!r}): {other_result!r} と {result!r}")
            if method.writes:
                self.assertTrue(table.same(other_after, after), f"既定値を明示するとシーンの結果が違う({explicit!r})")
            return
        if variadic:
            return
        other = self.fresh(method) if method.writes else target
        function = self._function(method, other)
        resolved = self._resolve(kwargs)
        if kind == "positional":
            args = []
            for param in positional:
                if param.name not in resolved:
                    break
                args.append(resolved.pop(param.name))
            if not args:
                return
            try:
                other_result = table.invoke(functools.partial(function, *args), resolved)
                if method.context:
                    with other_result:
                        pass
                other_after = self._state(method, other)
            finally:
                if method.reset:
                    method.reset(self, other)
            other_result = freeze(other_result) if method.writes else other_result
            self.assertTrue(table.same(other_result, result), f"位置で渡すと戻り値が違う: {other_result!r} と {result!r}")
            if method.writes:
                self.assertTrue(table.same(other_after, after), "位置で渡すとシーンの結果が違う")
            return
        keyword = [param for param in parameters if param.kind is param.KEYWORD_ONLY]
        if not keyword or any(param.name not in resolved and param.default is param.empty for param in positional):
            return
        args = [resolved.pop(param.name, param.default) for param in positional]
        extra = resolved.pop(keyword[0].name, keyword[0].default)
        before = self._state(method, other)
        try:
            with self.assertRaises(TypeError, msg=f"キーワード専用の {keyword[0].name} を位置で渡せた"):
                function(*args, None if _is_omitted(extra) else extra, **{name: value for name, value in resolved.items() if name in signature.parameters})
        finally:
            if method.reset:
                method.reset(self, other)
        self.assertTrue(table.same(self._state(method, other), before), "TypeError のあとシーンが変わった")

    def _compares_fast(self, method, kwargs, names):
        """段3で fast=True と通常を比べるかを返す。

        fast を指定した組・get=True・safe=True(失敗を数えるので、fast だけが拒否する値で数が変わる)・
        fast と同時に指定できない組(``conflicts``)は比べない。
        """
        if "fast" not in names or "fast" in kwargs or kwargs.get("get") or kwargs.get("safe"):
            return False
        return not method.conflicting(dict(kwargs, fast=True))

    def _assert_round_trip(self, method, kwargs, params, raises, target, resolved):
        """set の後の get が、書いた値(省いたなら既定値)と同じことを確かめる。"""
        trip = method.roundTrip
        if not trip or (trip.skip and trip.skip(kwargs)):
            return
        if method.writes:
            target = self.fresh(method)
            ok, _, _, _, resolved = self._call(method, target, kwargs, raises, "pairs")
            if not ok:
                return
        if trip.value in resolved:
            expected = resolved[trip.value]
        else:
            defaults = [param.default for param in params if param.name == trip.value and param.default is not inspect.Parameter.empty]
            if not defaults:
                return
            expected = defaults[0]
        shared = dict(trip.fixed, **{name: resolved[name] for name in trip.shared if name in resolved})
        # 短縮名で書いた値は、長い名前の固定値の代わりに渡す(同時に渡すと TypeError になる)。
        if "ws" in shared and "worldSpace" in shared and "worldSpace" not in resolved:
            del shared["worldSpace"]
        value = getattr(target, trip.getter)(**shared)
        self.assertTrue(table.same(value, expected, trip.places), f"{trip.getter} が書いた値と違う: {value!r}")

    def _check_plural(self, method, kwargs, raises, result, after):
        """複数形から呼んだ結果が、単数を1つずつ呼んだ結果の並びと同じことを確かめる。

        書き込むメソッドは、作り直した後のノードから値(Lazy)を作り直し、表の ``state`` で比べる。
        """
        if method.writes:
            target = self.fresh(method)
            plural, _singles = method.plural(self)
            table.invoke(getattr(plural, method.name), self._resolve(kwargs))
            plural_after = self._state(method, target)
            target = self.fresh(method)
            _plural, singles = method.plural(self)
            resolved = self._resolve(kwargs)
            for single in singles:
                table.invoke(getattr(single, method.name), resolved)
            self.assertTrue(table.same(plural_after, self._state(method, target)), "複数形と単数の並びでシーンの結果が違う")
            return
        # 読むだけのメソッドは、組ごとにノードを作り足さないよう、段の最初に作った複数形を使い回す。
        if self._plural is None:
            self._plural = method.plural(self)
        plural, singles = self._plural
        resolved = self._resolve(kwargs)
        plural_result = table.invoke(getattr(plural, method.name), resolved)
        single_result = [table.invoke(getattr(single, method.name), resolved) for single in singles]
        self.assertTrue(table.same(freeze(list(plural_result)), freeze(single_result)), "複数形の結果が単数の並びと違う")

    def _run_errors(self, method):
        """``errors`` に書いた状態ごとに、決めた例外になりシーンが変わらないことを確かめる。"""
        start = time.perf_counter()
        _target, base, _params, _raises = self._prepare(method)
        for state in method.errors:
            with self.subTest(stage="errors", state=state.label):
                target = self.fresh(method)
                prepared = state.prepare(self, target)
                if prepared is not None:
                    target = prepared
                resolved = self._resolve(dict(base, **state.kwargs))
                before = self.sceneState()
                try:
                    result = self._invoke(method, target, resolved)
                except Exception as error:
                    self.assertTrue(state.matches(error), f"{state.label}: 期待する例外 {state.error!r} でない: {error!r}")
                else:
                    self.fail(f"{state.label}: 例外にならない(戻り値 {result!r})")
                self.assertTrue(table.same(self.sceneState(), before), f"{state.label}: 例外のあとシーンが変わった")
        seconds = time.perf_counter() - start
        print(f"[argumentSweep] {method.name} errors: {len(method.errors)}件 {seconds:.2f}秒")

    def _sweep(self, method, stage, knownOnly=False):
        """段を実行し、件数と秒数を出力する。knownOnly なら known の場合だけを実行して、食い違いの数を返す。"""
        start = time.perf_counter()
        self._plural = None
        version = _maya_version()
        target, base, params, raises = self._prepare(method)
        cases, cut = self._cases(method, stage, params, base)
        run = skipped = 0
        failures = []
        for name, kwargs in cases:
            reason = method.isKnown(name, kwargs, version)
            if bool(reason) != knownOnly:
                skipped += 1
                continue
            run += 1
            if knownOnly:
                try:
                    self._run_case(method, stage, kwargs, params, raises, target, name)
                except Exception as error:
                    failures.append(f"{name}: {error}")
                else:
                    print(f"[argumentSweep] 食い違いが直った可能性(known から外す): {method.name} {name}")
                continue
            with self.subTest(stage=stage, args=name[len(stage) + 1 :]):
                self._run_case(method, stage, kwargs, params, raises, target, name)
        seconds = time.perf_counter() - start
        self._known_run = getattr(self, "_known_run", 0) + (run if knownOnly else 0)
        if knownOnly:
            if run:
                print(f"[argumentSweep] {type(target).__name__}.{method.name} {stage} known: {run}件 {seconds:.2f}秒 食い違い{len(failures)}件")
            return failures
        note = f" 上限{method.limit}で{cut}件を省略" if cut else ""
        known = f" known{skipped}件は別" if skipped else ""
        print(f"[argumentSweep] {type(target).__name__}.{method.name} {stage}: {run}件 {seconds:.2f}秒{note}{known}")
        uncovered = [param.name for param in params if param.name not in base and not param.candidates(method.valuesFor(param))]
        if stage == "values" and uncovered:
            print(f"[argumentSweep] {method.name}: 候補が無い引数(表の values に書く): {', '.join(uncovered)}")
        return failures


def _is_omitted(default):
    """既定値が無い(必須)か、省略を見分ける番兵(``...``・``object()``)かを返す。"""
    return default is inspect.Parameter.empty or default is Ellipsis or type(default) is object


def _stage_test(method, stage):
    def test(self):
        self._sweep(method, stage)

    test.__doc__ = f"{method.name} の引数を網羅する({stage})。"
    return test


def _errors_test(method):
    def test(self):
        self._run_errors(method)

    test.__doc__ = f"{method.name} の、状態で決まる例外を確かめる。"
    return test


def _known_test(method):
    def test(self):
        self._known_run = 0
        failures = []
        for stage in STAGES:
            failures += self._sweep(method, stage, knownOnly=True)
        if failures:
            raise AssertionError("本体との食い違い(known):\n" + "\n".join(failures))
        if not self._known_run and method.hasVersionedKnown(_maya_version()):
            raise unittest.SkipTest("この版に当てはまる known が無い")

    test.__doc__ = f"{method.name} の、表に記録した本体との食い違いがまだあることを確かめる。"
    return test
