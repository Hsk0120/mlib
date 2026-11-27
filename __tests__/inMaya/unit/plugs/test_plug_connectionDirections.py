"""Plugの接続照会・判定・全切断に共通する方向指定をMaya内で検証する。"""

import inspect
import sys
import unittest

import maya.cmds as cmds

import mlib


class ConnectionDirectionsTest(unittest.TestCase):
    """入力・出力の意味、既存照会仕様、参照検査とUndo契約を検証する。"""

    def setUp(self):
        """各テストに独立した空シーンと有効なUndoキューを用意する。"""
        cmds.file(new=True, force=True)
        cmds.undoInfo(state=True)

    def test_queries_share_direction_aliases_and_keep_legacy_and_rules(self):
        """sourceは入力、destinationは出力。短縮名s/dは、値に関係なく長い名前と同時に指定できない。"""
        source, center, destinations = self._chain("query")
        for method_name in ("getConnections",):
            query = getattr(center, method_name)
            for src, dst in ((True, True), (True, False), (False, True), (False, False)):
                expected = ([source] if src else []) + (destinations if dst else [])
                with self.subTest(method=method_name, src=src, dst=dst):
                    self.assertCountEqual(query(source=src, destination=dst), expected)
            self.assertCountEqual(query(s=False), destinations)
            self.assertEqual(query(d=False), [source])
            for kwargs in ({"s": True, "source": False}, {"d": False, "destination": False}, {"t": "network", "type": "network"}):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        query(**kwargs)
            # 長い名前と短縮名は、値に関係なく同時に指定できない。
            for kwargs in ({"s": True, "source": True}, {"d": True, "destination": True}, {"et": False, "exactType": False}):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        query(**kwargs)
            # bool の引数は、bool 以外の値を受け付けない。
            for kwargs in ({"source": 1}, {"destination": "enabled"}, {"asPair": 1}, {"checkChildren": None}):
                with self.subTest(kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        query(**kwargs)

    def test_query_removed_aliases_reject_without_changing_connections(self):
        """廃止した短縮名src/dst/idxと位置・名前の重複を拒否し、既存接続を変更しない。"""
        source, center, destinations = self._chain("queryConflicts")
        for method_name in ("getConnections",):
            query = getattr(center, method_name)
            for kwargs in ({"src": True}, {"dst": False}, {"idx": 0}):
                with self.subTest(method=method_name, kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        query(**kwargs)
            with self.assertRaises(TypeError):
                query(True, False, False, None, False, False, True, source=True)
        self._assert_chain(source, center, destinations)

    def test_query_filters_return_forms_and_index_keep_their_contract(self):
        """方向指定に型・ペア・ノード・単一結果・明示Plug型を併用できる。"""
        source, center, destinations = self._chain("filters")

        self.assertEqual(center.getConnections(source=True, destination=False, index=0, skipConversionNodes=True), source)
        self.assertIsNone(center.getConnections(source=False, destination=False, index=0, skipConversionNodes=True))
        self.assertIsNone(center.getConnections(source=True, destination=False, index=99, skipConversionNodes=True))
        self.assertEqual(center.getConnections(source=True, destination=False, asPair=True, skipConversionNodes=True), [(center, source)])
        self.assertCountEqual(
            center.getConnections(source=False, destination=True, asNode=True, skipConversionNodes=True), [plug.getNode() for plug in destinations]
        )
        self.assertEqual(center.getConnections(source=True, destination=False, type="network", exactType=True, skipConversionNodes=True), [source])
        self.assertEqual(center.getConnections(source=True, destination=True, t="transform", et=True, skipConversionNodes=True), [])
        # pcls は廃止。ペアの両側は型登録に従う Plug で、位置はそのまま。
        pair = center.getConnections(source=True, destination=False, asPair=True, index=0, skipConversionNodes=True)
        self.assertIsInstance(pair[0], mlib.Plug)
        self.assertIsInstance(pair[1], mlib.Plug)
        self.assertEqual(pair, (center, source))

    def test_query_original_positional_signature_is_preserved(self):
        """従来の位置引数を保ち、短縮名の別名を持たない。"""
        names = (
            "self",
            "source",
            "s",
            "destination",
            "d",
            "type",
            "t",
            "exactType",
            "et",
            "skipConversionNodes",
            "scn",
            "asPair",
            "asNode",
            "checkChildren",
            "checkElements",
            "index",
            "input",
            "output",
        )
        # 短縮名と、短縮名を持つ長い名前の既定は_UNSET(同時に指定したかを見分ける。意味の既定はdocstringのとおり)。
        unset = mlib.util._UNSET
        defaults = (unset,) * 10 + (False, False, True, True, None, False, False)
        signature = inspect.signature(mlib.Plug.getConnections)
        self.assertEqual(tuple(signature.parameters), names)
        self.assertEqual(tuple(parameter.default for parameter in list(signature.parameters.values())[1 : len(names)]), defaults)
        # cmds.listConnectionsと同じく、フラグはすべてキーワードで渡す。
        for parameter in list(signature.parameters.values())[1 : len(names)]:
            self.assertEqual(parameter.kind, inspect.Parameter.KEYWORD_ONLY)
        source, center, destinations = self._chain("positional")
        with self.assertRaises(TypeError):
            center.getConnections(True, False)
        self.assertEqual(center.getConnections(source=True, destination=False, index=0), source)
        self.assertCountEqual(center.getConnections(source=False, destination=True, skipConversionNodes=True), destinations)
        self.assertEqual(
            inspect.signature(center.getConnections),
            inspect.signature(mlib.Plug.getConnections).replace(parameters=list(inspect.signature(mlib.Plug.getConnections).parameters.values())[1:]),
        )

    def test_query_child_and_multi_expansion_does_not_change_direct_operations(self):
        """照会は子・マルチアトリビュートを展開し、接続判定と全切断は元のMPlugの範囲を保つ。"""
        owner = mlib.createNode("network", name="hierarchyOwner")
        cmds.addAttr(str(owner), longName="payload", attributeType="compound", numberOfChildren=1)
        cmds.addAttr(str(owner), longName="childValue", attributeType="double", parent="payload")
        parent = owner.getPlug("payload")
        child = owner.getPlug("childValue")
        array = owner.addAttr("values", attributeType="double", multi=True)
        source = self._value("hierarchySource")
        destination = self._value("hierarchyDestination")
        multi_destination = self._value("hierarchyArrayDestination")
        child.connect(source)
        destination.connect(child)
        element = array[7]
        element.connect(source)
        multi_destination.connect(element)
        for target, local, output in ((parent, child, destination), (array, element, multi_destination)):
            with self.subTest(target=str(target)):
                self.assertEqual(target.getConnections(source=True, destination=False, asPair=True, skipConversionNodes=True), [(local, source)])
                self.assertEqual(target.getConnections(source=False, destination=True, skipConversionNodes=True), [output])
                self.assertEqual(target.getConnections(source=True, destination=True, checkChildren=False, checkElements=False, skipConversionNodes=True), [])
                self.assertEqual(target.isConnected(), target.mplug().isConnected)
                self.assertEqual(target.isConnected(source=True, destination=False), target.mplug().isDestination)
                self.assertEqual(target.isConnected(source=False, destination=True), target.mplug().isSource)
                self.assertFalse(target.isConnected(source))
                self.assertIsNone(target.disconnectAll())
                self.assertTrue(cmds.isConnected(str(source), str(local)))
                self.assertTrue(cmds.isConnected(str(local), str(output)))

    def test_is_connected_matches_mplug_flags_in_each_direction(self):
        """単独入力・単独出力・両方向・未接続で入力と出力の判定を揃える。"""
        source, center, destinations = self._chain("flags")
        empty = self._value("flagsEmpty")
        for target in [source, center, destinations[0], empty]:
            with self.subTest(target=str(target)):
                mp = target.mplug()
                self.assertEqual(target.isConnected(), mp.isConnected)
                self.assertEqual(target.isConnected(source=True, destination=False), mp.isDestination)
                self.assertEqual(target.isConnected(source=False, destination=True), mp.isSource)
                self.assertFalse(target.isConnected(source=False, destination=False))

    def test_is_connected_with_other_checks_direction_and_all_supported_inputs(self):
        """Plug・MPlug・文字列を受け付け、自身から見た入力と出力を判定する。"""
        source, center, destinations = self._chain("peers")
        unrelated = self._value("peersUnrelated")
        for peer, incoming in ((source, True), (destinations[0], False)):
            for other in (peer, peer.mplug(), str(peer)):
                with self.subTest(peer=str(peer), input_type=type(other).__name__):
                    self.assertTrue(center.isConnected(other))
                    self.assertEqual(center.isConnected(other, source=True, destination=False), incoming)
                    self.assertEqual(center.isConnected(other, source=False, destination=True), not incoming)
                    self.assertFalse(center.isConnected(other, source=False, destination=False))
        self.assertFalse(center.isConnected(unrelated))
        self.assertFalse(center.isConnected(center))
        self.assertTrue(source.isConnected(center, source=False, destination=True))
        self.assertFalse(source.isConnected(center, source=True, destination=False))

    def test_new_direction_flags_require_bool_and_reject_removed_aliases(self):
        """判定・全切断の方向はboolだけを受け付け、廃止した短縮名src/dstを拒否する。"""
        source, center, destinations = self._chain("validation")
        methods = (("isConnected", center.isConnected, ()), ("isConnected(other)", center.isConnected, (source,)), ("disconnectAll", center.disconnectAll, ()))
        invalid = ({"source": 1}, {"destination": 0}, {"source": None}, {"destination": "true"}, {"src": True}, {"dst": False})
        for label, method, args in methods:
            for kwargs in invalid:
                with self.subTest(method=label, kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        method(*args, **kwargs)
                    self._assert_chain(source, center, destinations)
            with self.subTest(method=label, positional=True):
                # 向きはキーワード専用(相手のPlugだけを位置で渡せる)。
                with self.assertRaises(TypeError):
                    method(source, True, False)
                self._assert_chain(source, center, destinations)
        with self.assertRaises(TypeError):
            center.disconnectAll(source)
        self._assert_chain(source, center, destinations)

    def test_input_and_outputs_match_explicit_flags(self):
        """getConnections(input=True)・(output=True)は、向きとたどり方を明示した書き方と同じ結果になる。"""
        source, center, destinations = self._chain("shortcut")
        empty = self._value("shortcutEmpty")
        for target in (source, center, destinations[0], empty):
            for flags in ({}, {"skipConversionNodes": True}, {"asNode": True}, {"asPair": True}, {"type": "network"}, {"type": "joint"}):
                with self.subTest(target=str(target), flags=flags):
                    self.assertEqual(
                        target.getConnections(input=True, **flags),
                        target.getConnections(source=True, destination=False, checkChildren=False, checkElements=False, index=0, **flags),
                    )
                    self.assertEqual(
                        target.getConnections(output=True, **flags),
                        target.getConnections(source=False, destination=True, checkChildren=False, checkElements=False, **flags),
                    )
                    for index in (0, -1, 5):
                        self.assertEqual(
                            target.getConnections(output=True, index=index, **flags),
                            target.getConnections(source=False, destination=True, checkChildren=False, checkElements=False, index=index, **flags),
                        )
        self.assertEqual(center.getConnections(input=True), source)
        self.assertIsNone(source.getConnections(input=True))
        self.assertIsInstance(center.getConnections(output=True), mlib.Plugs)
        self.assertEqual(sorted(str(plug) for plug in center.getConnections(output=True)), sorted(str(plug) for plug in destinations))
        self.assertEqual(destinations[0].getConnections(output=True), [])
        self.assertIsInstance(destinations[0].getConnections(output=True), mlib.Plugs)
        # cmds.listConnections(直接の接続)と突き合わせる。
        for target in (source, center, destinations[0], empty):
            with self.subTest(target=str(target), compare="cmds"):
                incoming = cmds.listConnections(str(target), source=True, destination=False, plugs=True) or []
                outgoing = cmds.listConnections(str(target), source=False, destination=True, plugs=True) or []
                found = target.getConnections(input=True)
                self.assertEqual([] if found is None else [str(found)], incoming)
                self.assertEqual(sorted(str(plug) for plug in target.getConnections(output=True)), sorted(outgoing))
                self.assertEqual(found is not None, target.isConnected(destination=False))
                self.assertEqual(bool(target.getConnections(output=True)), target.isConnected(source=False))

    def test_input_and_outputs_ignore_children_and_elements(self):
        """子・要素にだけ接続があるコンパウンド・マルチアトリビュートでは、input=TrueはNone、output=Trueは空。"""
        node = mlib.createNode("transform", name="shortcutParent")
        other = mlib.createNode("transform", name="shortcutOther")
        pma = mlib.createNode("plusMinusAverage", name="shortcutMulti")
        cmds.connectAttr(str(other) + ".translateX", str(node) + ".translateY")
        cmds.connectAttr(str(node) + ".scaleX", str(other) + ".scaleY")
        cmds.connectAttr(str(other) + ".translateZ", str(pma) + ".input1D[3]")
        translate, scale, multi = node.getPlug("translate"), node.getPlug("scale"), pma.getPlug("input1D")
        for target in (translate, multi):
            with self.subTest(target=str(target)):
                self.assertIsNone(target.getConnections(input=True))
                self.assertIsNone(target.getConnections(destination=False, checkChildren=False, checkElements=False, index=0))
                # destination=False だけでは子・要素の接続も集めるので、None の判定には使えない。
                self.assertEqual(len(target.getConnections(destination=False)), 1)
        self.assertEqual(scale.getConnections(output=True), [])
        self.assertEqual(len(scale.getConnections(source=False)), 1)
        self.assertEqual(node.getPlug("translateY").getConnections(input=True), other.getPlug("translateX"))
        self.assertEqual(multi[3].getConnections(input=True), other.getPlug("translateZ"))
        self.assertEqual(node.getPlug("scaleX").getConnections(output=True), [other.getPlug("scaleY")])

    def test_input_and_outputs_reject_conflicting_arguments(self):
        """input・outputは、向き・たどり方の指定(inputはindexも)やお互いとは同時に指定できない(TypeError)。接続は変えない。"""
        source, center, destinations = self._chain("conflict")
        conflicts = (
            {"s": False},
            {"d": False},
            {"source": False},
            {"destination": False},
            {"checkChildren": False},
            {"checkElements": False},
            {"source": False, "destination": False},
        )
        for shortcut in ("input", "output"):
            for kwargs in conflicts:
                with self.subTest(shortcut=shortcut, kwargs=kwargs):
                    with self.assertRaises(TypeError):
                        center.getConnections(**dict({shortcut: True}, **kwargs))
            for bad in (1, 0, None, "yes"):
                with self.subTest(shortcut=shortcut, value=bad):
                    with self.assertRaises(TypeError):
                        center.getConnections(**{shortcut: bad})
        for kwargs in ({"input": True, "output": True}, {"input": True, "index": 0}, {"input": True, "index": -1}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TypeError):
                    center.getConnections(**kwargs)
        with self.assertRaises(TypeError):
            center.getConnections(True)
        # 既定値と同じ指定(False)は、指定していない扱い。
        self.assertEqual(center.getConnections(input=False, output=False), center.getConnections())
        self.assertEqual(center.getConnections(input=True, output=False), source)
        self.assertEqual(center.getConnections(output=True, index=0), center.getConnections(output=True)[0])
        self._assert_chain(source, center, destinations)

    def test_disconnect_all_directions_return_self_and_preserve_other_side(self):
        """全切断も入力だけ・出力だけ・両方向・両Falseを選び、自身を返す。"""
        cases = ({}, {"source": True, "destination": False}, {"source": False, "destination": True}, {"source": False, "destination": False})
        for index, kwargs in enumerate(cases):
            with self.subTest(kwargs=kwargs):
                source, center, destinations = self._chain("disconnect" + str(index))
                src = kwargs.get("source", True)
                dst = kwargs.get("destination", True)
                self.assertIsNone(center.disconnectAll(**kwargs))
                self._assert_chain(source, center, destinations, incoming=not src, outgoing=not dst)

    def test_disconnect_all_is_one_undo_redo(self):
        """入力と複数出力の解除を一回のUndo/Redoでまとめて戻せる。"""
        source, center, destinations = self._chain("undo")
        cmds.flushUndo()
        self.assertIsNone(center.disconnectAll(source=True, destination=True))
        self._assert_chain(source, center, destinations, incoming=False, outgoing=False)
        cmds.undo()
        self._assert_chain(source, center, destinations)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))
        cmds.redo()
        self._assert_chain(source, center, destinations, incoming=False, outgoing=False)

    def test_conversion_queries_and_direct_operations_keep_conversion_nodes(self):
        """照会の変換省略を維持し、判定・全切断は直接の変換端点を対象にする。"""
        source = self._value("conversionSource")
        center = self._value("conversionCenter")
        output = self._value("conversionDestination")
        conversion = mlib.createNode("unitConversion", name="conversion")
        conversion_input = conversion.getPlug("input")
        conversion_output = conversion.getPlug("output")
        conversion_input.connect(source)
        center.connect(conversion_output)
        output.connect(center)
        # 既定は変換ノードを飛ばす。scn=False・skipConversionNodes=Falseは直結。
        self.assertEqual(center.getConnections(source=True, destination=False, skipConversionNodes=True), [source])
        self.assertEqual(center.getConnections(source=True, destination=False, scn=False), [conversion_output])
        self.assertEqual(source.getConnections(source=False, destination=True, skipConversionNodes=True), [center])
        self.assertEqual(source.getConnections(source=False, destination=True), [conversion_input])
        self.assertTrue(center.isConnected(conversion_output, source=True, destination=False))
        self.assertFalse(center.isConnected(source, source=True, destination=False))
        self.assertIsNone(center.disconnectAll(source=True, destination=False))
        self.assertFalse(cmds.isConnected(str(conversion_output), str(center)))
        self.assertTrue(cmds.isConnected(str(source), str(conversion_input)))
        self.assertTrue(cmds.isConnected(str(center), str(output)))
        self.assertTrue(cmds.objExists(str(conversion)))

    def test_invalid_self_and_other_references_are_still_checked(self):
        """削除済みノード・アトリビュートの参照を照会・判定・全切断で拒否する。"""
        valid = self._value("validReference")
        deleted_node = self._value("deletedNodeReference")
        deleted_attr = self._value("deletedAttrReference")
        deleted_node.getNode().delete()
        cmds.deleteAttr(str(deleted_attr))
        for target in (deleted_node, deleted_attr):
            for method_name in ("getConnections", "isConnected", "disconnectAll"):
                with self.subTest(target=target is deleted_node, method=method_name):
                    with self.assertRaises(RuntimeError):
                        getattr(target, method_name)(source=False, destination=False)
            with self.assertRaises(RuntimeError):
                target.isConnected(valid, source=True, destination=False)
            for kwargs in ({}, {"source": True, "destination": False}, {"source": False, "destination": False}):
                with self.subTest(target=target is deleted_node, direction=kwargs):
                    with self.assertRaises(RuntimeError):
                        valid.isConnected(target, **kwargs)
        with self.assertRaises(AttributeError):
            valid.isConnected("doesNotExist.value", source=True, destination=False)

    def test_both_false_and_unconnected_calls_do_not_create_undo_entries(self):
        """両False・未接続の操作は接続を保ち、Undoキューに編集を残さない。"""
        source, center, destinations = self._chain("noop")
        empty = self._value("noopEmpty")
        cmds.flushUndo()
        self.assertEqual(center.getConnections(source=False, destination=False, skipConversionNodes=True), [])
        self.assertFalse(center.isConnected(source=False, destination=False))
        self.assertFalse(center.isConnected(source, source=False, destination=False))
        self.assertIsNone(center.disconnectAll(source=False, destination=False))
        self.assertIsNone(empty.disconnectAll())
        self.assertEqual(empty.getConnections(source=True, destination=True, skipConversionNodes=True), [])
        self.assertFalse(empty.isConnected())
        self.assertFalse(empty.isConnected(source))
        self._assert_chain(source, center, destinations)
        self.assertTrue(cmds.undoInfo(query=True, undoQueueEmpty=True))

    def test_disconnect_all_does_not_force_or_unlock_locked_destinations(self):
        """全切断は既存のロック制約を守り、forceフラグを追加しない。"""
        source, center, destinations = self._chain("locked")
        destinations[0].setFlags(locked=True)
        with self.assertRaises(RuntimeError):
            center.disconnectAll(source=False, destination=True)
        self.assertTrue(destinations[0].isLocked())
        self.assertTrue(cmds.isConnected(str(center), str(destinations[0])))
        self.assertTrue(cmds.isConnected(str(source), str(center)))
        with self.assertRaises(TypeError):
            center.disconnectAll(force=True)
        self.assertTrue(destinations[0].isLocked())

    def _value(self, name):
        """接続に使用するdoubleアトリビュートのPlugを作る。

        Args:
            name (str): 所有ノード名。

        Returns:
            Plug: 作成したvalueアトリビュート。
        """
        node = mlib.createNode("network", name=name)
        return node.addAttr("value", attributeType="double")

    def _chain(self, prefix):
        """入力一つと出力二つを持つ中心Plugを作る。

        Args:
            prefix (str): ノード名の接頭辞。

        Returns:
            tuple[Plug, Plug, list[Plug]]: 入力元・中心・出力先。
        """
        source = self._value(prefix + "Source")
        center = self._value(prefix + "Center")
        destinations = [self._value(prefix + "First"), self._value(prefix + "Second")]
        center.connect(source)
        for destination in destinations:
            destination.connect(center)
        return source, center, destinations

    def _assert_chain(self, source, center, destinations, incoming=True, outgoing=True):
        """接続の保持状態を入力・出力別に確認する。

        Args:
            source (Plug): 入力元。
            center (Plug): 中心Plug。
            destinations (list[Plug]): 出力先。
            incoming (bool): 入力接続の期待値。
            outgoing (bool): 出力接続の期待値。
        """
        self.assertEqual(cmds.isConnected(str(source), str(center)), incoming)
        for destination in destinations:
            self.assertEqual(cmds.isConnected(str(center), str(destination)), outgoing)


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
