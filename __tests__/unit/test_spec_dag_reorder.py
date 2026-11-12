"""DagNode の並び順(アウトライナーの順番)の約束を固定する。

対象: getOutlinerOrder(親の直接の子の中の番号。Shape・中間オブジェクトも数え、ワールド直下は
``cmds.ls(assemblies=True)`` の並びで数える)、setOutlinerOrder(番号で移動。負の値・範囲外・型)、
reorder(front/f・back/b・relative/r のどれか1つ。relative は端を越えると反対側へ回る)、
Undo 1 回、インスタンスは保持パスの親の下だけ、無効なノード・ロックされたノードの例外、
複数形(Nodes)からの呼出し。
"""

import unittest

import maya.cmds as cmds

import mlib
mlib.reload()
from mlib.nodes import Node, Nodes
from support.specCase import NamespaceCase


def children(parent):
    """親の直接の子の完全パスを DAG の子順で返す。"""
    return cmds.listRelatives(parent, children=True, fullPath=True) or []


def assemblies():
    """ワールド直下のノードの完全パスを並び順で返す。"""
    return cmds.ls(assemblies=True, long=True)


class _SpecCase(NamespaceCase):
    """このテストファイルの名前空間の先頭と、共通基底からの差分。"""

    PREFIX = "mlibSpecDagReorder_"
    UNLOCK_NODES = True

    def xf(self, text, parent=None):
        """transform を作り完全パスを返す。"""
        return cmds.ls(self.make("transform", text, parent=parent), long=True)[0]


class SiblingsFixture(_SpecCase):
    """grp > n0〜n4 の階層。"""

    COUNT = 5

    def setUp(self):
        super().setUp()
        self.grp = self.xf("grp")
        self.kids = [self.xf("n{}".format(index), parent=self.grp) for index in range(self.COUNT)]

    def moved(self, current, target):
        """current 番目の子を target 番目へ移したときの子の並びを返す。"""
        expected = list(self.kids)
        expected.insert(target, expected.pop(current))
        return expected


class GetOutlinerOrderTest(SiblingsFixture):
    def test_matches_list_relatives(self):
        """番号は cmds.listRelatives(children=True) の位置と一致する。"""
        for name in self.kids:
            with self.subTest(name=name):
                result = Node(name).getOutlinerOrder()
                self.assertIs(type(result), int)
                self.assertEqual(result, children(self.grp).index(name))

    def test_counts_shapes_and_intermediate_objects(self):
        """Transform・Shape・中間オブジェクトを区別せず、親の直接の子すべてを数える。"""
        cube = cmds.ls(cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0], long=True)[0]
        orig = cmds.createNode("mesh", name=self.name("cubeShapeOrig"), parent=cube, skipSelect=True)
        cmds.setAttr(orig + ".intermediateObject", True)
        self.xf("cubeChild", parent=cube)
        names = children(cube)
        self.assertEqual(len(names), 3)
        for index, name in enumerate(names):
            with self.subTest(name=name):
                self.assertEqual(Node(name).getOutlinerOrder(), index)

    def test_world_matches_assemblies(self):
        """ワールド直下は cmds.ls(assemblies=True) の位置と一致する。"""
        for name in [self.grp, self.xf("w0"), self.xf("w1")]:
            with self.subTest(name=name):
                self.assertEqual(Node(name).getOutlinerOrder(), assemblies().index(name))

    def test_follows_cmds_reorder(self):
        """cmds.reorder で動かした後の番号を返す(保持した値ではない)。"""
        node = Node(self.kids[3])
        cmds.reorder(self.kids[3], front=True)
        self.assertEqual(node.getOutlinerOrder(), 0)

    def test_invalid_node_raises(self):
        """削除したノードは RuntimeError。"""
        node = Node(self.kids[1])
        cmds.delete(self.kids[1])
        with self.assertRaises(RuntimeError):
            node.getOutlinerOrder()


class SetOutlinerOrderTest(SiblingsFixture):
    def test_every_pair(self):
        """どの位置からどの位置へも移せ、他の子は互いの順番を保つ。"""
        for current in range(self.COUNT):
            for target in range(self.COUNT):
                with self.subTest(current=current, target=target):
                    node = Node(self.kids[current])
                    self.assertIs(node.setOutlinerOrder(target), node)
                    self.assertEqual(children(self.grp), self.moved(current, target))
                    self.assertEqual(node.getOutlinerOrder(), target)
                    if current != target:
                        cmds.undo()
                    self.assertEqual(children(self.grp), self.kids)

    def test_negative_counts_from_end(self):
        """負の値は末尾から数える。"""
        for index in range(-self.COUNT, 0):
            with self.subTest(index=index):
                node = Node(self.kids[2])
                node.setOutlinerOrder(index)
                self.assertEqual(node.getOutlinerOrder(), index + self.COUNT)
                node.setOutlinerOrder(2)
                self.assertEqual(children(self.grp), self.kids)

    def test_out_of_range_raises(self):
        """範囲外は IndexError で、順番を変えない。"""
        node = Node(self.kids[2])
        for index in (self.COUNT, self.COUNT + 3, -self.COUNT - 1):
            with self.subTest(index=index):
                with self.assertRaises(IndexError):
                    node.setOutlinerOrder(index)
                self.assertEqual(children(self.grp), self.kids)

    def test_non_int_raises(self):
        """int 以外(bool を含む)は TypeError で、順番を変えない。"""
        node = Node(self.kids[2])
        for index in (1.0, True, "1", None):
            with self.subTest(index=index):
                with self.assertRaises(TypeError):
                    node.setOutlinerOrder(index)
                self.assertEqual(children(self.grp), self.kids)

    def test_world(self):
        """ワールド直下でも番号で移せ、Undo 1 回で戻る。"""
        names = [self.xf("w{}".format(index)) for index in range(3)]
        before = assemblies()
        node = Node(names[2])
        node.setOutlinerOrder(0)
        self.assertEqual(assemblies()[0], names[2])
        self.assertEqual(node.getOutlinerOrder(), 0)
        cmds.undo()
        self.assertEqual(assemblies(), before)
        node.setOutlinerOrder(-2)
        self.assertEqual(assemblies()[-2], names[2])
        cmds.undo()
        self.assertEqual(assemblies(), before)

    def test_shape(self):
        """Shape も同じ親の Transform と並べ替えられる。"""
        cube = cmds.ls(cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0], long=True)[0]
        shape = children(cube)[0]
        child = self.xf("cubeChild", parent=cube)
        Node(shape).setOutlinerOrder(1)
        self.assertEqual(children(cube), [child, shape])

    def test_undo_once(self):
        """Undo 1 回で元の順番へ戻り、Redo で再び移る。"""
        node = Node(self.kids[0])
        node.setOutlinerOrder(3)
        moved = children(self.grp)
        cmds.undo()
        self.assertEqual(children(self.grp), self.kids)
        cmds.redo()
        self.assertEqual(children(self.grp), moved)

    def test_invalid_node_raises(self):
        """削除したノードは RuntimeError。"""
        node = Node(self.kids[1])
        cmds.delete(self.kids[1])
        with self.assertRaises(RuntimeError):
            node.setOutlinerOrder(0)


class ReorderTest(SiblingsFixture):
    def test_front_and_back(self):
        """front は先頭、back は最後へ移す。短縮名 f・b も同じ。"""
        cases = (
            ({"front": True}, 0),
            ({"f": True}, 0),
            ({"back": True}, self.COUNT - 1),
            ({"b": True}, self.COUNT - 1),
        )
        for flags, target in cases:
            with self.subTest(flags=flags):
                node = Node(self.kids[2])
                self.assertIs(node.reorder(**flags), node)
                self.assertEqual(children(self.grp), self.moved(2, target))
                cmds.undo()
                self.assertEqual(children(self.grp), self.kids)

    def test_false_flags_are_ignored(self):
        """False の front・back は指定なしと同じに扱う。"""
        node = Node(self.kids[2])
        node.reorder(front=False, back=True)
        self.assertEqual(children(self.grp), self.moved(2, self.COUNT - 1))
        cmds.undo()
        node.reorder(front=False, back=False, relative=-1)
        self.assertEqual(children(self.grp), self.moved(2, 1))

    def test_relative(self):
        """relative はその数だけ前後へ動かす。0 は動かさない。短縮名 r も同じ。"""
        cases = (({"relative": 1}, 3), ({"relative": -2}, 0), ({"r": 2}, 4), ({"relative": 0}, 2))
        for flags, target in cases:
            with self.subTest(flags=flags):
                node = Node(self.kids[2])
                self.assertIs(node.reorder(**flags), node)
                self.assertEqual(children(self.grp), self.moved(2, target))
                if target != 2:
                    cmds.undo()
                self.assertEqual(children(self.grp), self.kids)

    def test_relative_wraps_around(self):
        """relative は端を越えると反対側へ回る(cmds.reorder と同じ)。"""
        last = Node(self.kids[-1])
        last.reorder(relative=1)
        self.assertEqual(last.getOutlinerOrder(), 0)
        cmds.undo()
        first = Node(self.kids[0])
        first.reorder(relative=-1)
        self.assertEqual(first.getOutlinerOrder(), self.COUNT - 1)
        cmds.undo()
        self.assertEqual(children(self.grp), self.kids)

    def test_matches_cmds_reorder(self):
        """同じフラグの cmds.reorder と同じ並びになる。"""
        for flags in ({"front": True}, {"back": True}, {"relative": 3}, {"relative": -4}, {"relative": 7}):
            with self.subTest(flags=flags):
                cmds.reorder(self.kids[1], **flags)
                expected = children(self.grp)
                cmds.undo()
                Node(self.kids[1]).reorder(**flags)
                self.assertEqual(children(self.grp), expected)
                cmds.undo()
                self.assertEqual(children(self.grp), self.kids)

    def test_requires_exactly_one_flag(self):
        """front・back・relative のどれか1つでなければ TypeError で、順番を変えない。"""
        node = Node(self.kids[2])
        cases = (
            {},
            {"front": False},
            {"back": False},
            {"front": True, "back": True},
            {"front": True, "relative": 1},
            {"back": True, "r": 1},
            {"front": True, "back": True, "relative": 1},
        )
        for flags in cases:
            with self.subTest(flags=flags):
                with self.assertRaises(TypeError):
                    node.reorder(**flags)
                self.assertEqual(children(self.grp), self.kids)

    def test_alias_conflict_raises(self):
        """ロング名と短縮名の同時指定は TypeError。"""
        node = Node(self.kids[2])
        for flags in ({"front": True, "f": True}, {"back": True, "b": False}, {"relative": 1, "r": 1}):
            with self.subTest(flags=flags):
                with self.assertRaises(TypeError):
                    node.reorder(**flags)
                self.assertEqual(children(self.grp), self.kids)

    def test_wrong_types_raise(self):
        """front・back は bool、relative は int(bool を除く)でなければ TypeError。"""
        node = Node(self.kids[2])
        cases = (
            {"front": 1},
            {"back": "yes"},
            {"relative": 1.0},
            {"relative": True},
            {"relative": "1"},
        )
        for flags in cases:
            with self.subTest(flags=flags):
                with self.assertRaises(TypeError):
                    node.reorder(**flags)
                self.assertEqual(children(self.grp), self.kids)

    def test_positional_arguments_are_rejected(self):
        """フラグはキーワードだけで受ける。"""
        with self.assertRaises(TypeError):
            Node(self.kids[2]).reorder(True)

    def test_world(self):
        """ワールド直下でも順番を変えられる。"""
        names = [self.xf("w{}".format(index)) for index in range(3)]
        before = assemblies()
        Node(names[1]).reorder(front=True)
        self.assertEqual(assemblies()[0], names[1])
        cmds.undo()
        Node(names[1]).reorder(back=True)
        self.assertEqual(assemblies()[-1], names[1])
        cmds.undo()
        self.assertEqual(assemblies(), before)

    def test_undo_once(self):
        """Undo 1 回で元の順番へ戻り、Redo で再び移る。"""
        Node(self.kids[4]).reorder(front=True)
        moved = children(self.grp)
        cmds.undo()
        self.assertEqual(children(self.grp), self.kids)
        cmds.redo()
        self.assertEqual(children(self.grp), moved)

    def test_invalid_node_raises(self):
        """削除したノードは RuntimeError。"""
        node = Node(self.kids[1])
        cmds.delete(self.kids[1])
        with self.assertRaises(RuntimeError):
            node.reorder(front=True)

    def test_locked_node_raises(self):
        """ロックされたノードは RuntimeError で、順番を変えない。"""
        cmds.lockNode(self.kids[3], lock=True)
        node = Node(self.kids[3])
        with self.assertRaises(RuntimeError):
            node.reorder(front=True)
        with self.assertRaises(RuntimeError):
            node.setOutlinerOrder(0)
        self.assertEqual(children(self.grp), self.kids)


class InstanceTest(_SpecCase):
    def test_only_held_parent_changes(self):
        """インスタンスは保持パスの親の下だけを数え、その親の下の順番だけを変える。"""
        first = self.xf("first")
        second = self.xf("second")
        for index in range(3):
            self.xf("k{}".format(index), parent=first)
        shared = first + "|" + self.name("k1")
        cmds.parent(shared, second, add=True)
        self.xf("x", parent=second)
        self.xf("y", parent=second)
        under_first = children(first)
        under_second = children(second)
        short_names = [name.rsplit("|", 1)[-1] for name in under_second]
        node = Node(second + "|" + self.name("k1"))
        self.assertEqual(node.getOutlinerOrder(), short_names.index(self.name("k1")))
        self.assertEqual(Node(shared).getOutlinerOrder(), 1)

        node.reorder(back=True)
        self.assertEqual(children(first), under_first)
        self.assertEqual([name.rsplit("|", 1)[-1] for name in children(second)][-1], self.name("k1"))
        self.assertEqual(node.getOutlinerOrder(), 2)
        self.assertEqual(Node(shared).getOutlinerOrder(), 1)

        node.setOutlinerOrder(0)
        self.assertEqual(children(first), under_first)
        self.assertEqual([name.rsplit("|", 1)[-1] for name in children(second)][0], self.name("k1"))


class NodesTest(SiblingsFixture):
    def test_plural_forwards(self):
        """複数形からは各要素のメソッドを呼び、戻り値を保持順のリストで返す。"""
        nodes = Nodes([self.kids[3], self.kids[1]])
        self.assertEqual(nodes.getOutlinerOrder(), [3, 1])
        result = nodes.reorder(front=True)
        self.assertEqual(result, [Node(self.kids[3]), Node(self.kids[1])])
        self.assertEqual(children(self.grp),
                         [self.kids[1], self.kids[3], self.kids[0], self.kids[2], self.kids[4]])
        self.assertEqual(nodes.getOutlinerOrder(), [1, 0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
