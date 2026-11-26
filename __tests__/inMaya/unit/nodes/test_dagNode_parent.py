"""``DagNode.getParent`` の、祖先をすべて取る ``all=True`` と step を確かめる。

- Joint の鎖とその上の transform を、近い順にすべて返す(cmds の完全パスと突き合わせる)。
- すべてJointなら ``Joints``、途中にtransformがあれば ``Nodes``。ワールド直下は空の集まり。
- 取った後に階層を変えても、今の階層の祖先を返す。Shape からも親をたどれる。
- step・instances との組み合わせと、型の誤りは TypeError。
"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.nodes import Joints, Nodes


class _Case(NamespaceCase):
    """このテストファイルの名前空間の先頭と、Jointの鎖の補助。"""

    PREFIX = "mlibDagParent_"

    def chain(self, count, parent=None):
        """選択を使わずにJointの鎖を作り、完全パスの並びを返す。"""
        cmds.select(clear=True)
        names = []
        for index in range(count):
            if names:
                cmds.select(names[-1], replace=True)
            names.append(cmds.joint(name=self.name(f"j{index}"), position=(index, 0, 0)))
        cmds.select(clear=True)
        if parent is not None:
            cmds.parent(names[0], parent)
        return cmds.ls(names, long=True)


class GetParentAllTest(_Case):
    def ancestors_of(self, name):
        """cmdsの完全パスから、祖先の完全パスを近い順に求める。"""
        parts = name.split("|")[1:]
        return ["|" + "|".join(parts[:end]) for end in range(len(parts) - 1, 0, -1)]

    def test_joint_chain_all_ancestors(self):
        """Jointの鎖の末端から、親・親の親…ワールド直下まで、近い順にすべて返す。"""
        top = cmds.createNode("transform", name=self.name("top"))
        group = cmds.createNode("transform", name=self.name("group"), parent=top)
        joints = self.chain(4, parent=group)
        leaf = mlib.getNode(cmds.ls(joints[-1], long=True)[0])
        result = leaf.getParent(all=True)
        expected = self.ancestors_of(leaf.getName(full=True))
        self.assertEqual([node.getName(full=True) for node in result], expected)
        self.assertEqual(len(result), 5)
        self.assertIsInstance(result, Nodes)
        # 1つずつ step でたどった結果とも同じ。
        self.assertEqual([node.getName(full=True) for node in result], [leaf.getParent(step).getName(full=True) for step in range(1, 6)])

    def test_only_joints_returns_joints(self):
        """祖先がすべてJointなら Joints、ワールド直下は空の集まり。"""
        joints = self.chain(3)
        leaf = mlib.getNode(joints[-1])
        result = leaf.getParent(all=True)
        self.assertIsInstance(result, Joints)
        self.assertEqual([node.getName(full=True) for node in result], [joints[1], joints[0]])
        self.assertEqual(list(mlib.getNode(joints[0]).getParent(all=True)), [])

    def test_follows_reparent_after_getting_the_node(self):
        """取った後に上の階層を変えても、今の階層の祖先を返す。"""
        joints = self.chain(3)
        leaf = mlib.getNode(joints[-1])
        self.assertEqual(len(leaf.getParent(all=True)), 2)
        group = cmds.createNode("transform", name=self.name("later"))
        cmds.parent(joints[0], group)
        self.assertEqual([node.getName(short=True) for node in leaf.getParent(all=True)][-1], group.split("|")[-1])
        self.assertEqual(len(leaf.getParent(all=True)), 3)

    def test_shape_ancestors(self):
        """Shapeの祖先は、持ち主のtransformから上をすべて返す。"""
        group = cmds.createNode("transform", name=self.name("holder"))
        cube = cmds.polyCube(name=self.name("cube"), constructionHistory=False)[0]
        cube = cmds.parent(cube, group)[0]
        shape = mlib.getNode(cmds.listRelatives(cube, shapes=True, fullPath=True)[0])
        self.assertEqual([node.getName(short=True) for node in shape.getParent(all=True)], [cube.split("|")[-1], group.split("|")[-1]])

    def test_invalid_arguments(self):
        """allとstep・instances・indirectの同時指定と、boolでないallはTypeError。"""
        leaf = mlib.getNode(self.chain(2)[-1])
        for kwargs in ({"all": True, "instances": True}, {"all": True, "indirect": True}, {"all": 1}, {"all": True, "step": 2}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TypeError):
                if "step" in kwargs:
                    step = kwargs.pop("step")
                    leaf.getParent(step, **kwargs)
                else:
                    leaf.getParent(**kwargs)
        self.assertEqual(leaf.getParent(all=False).getName(full=True), cmds.listRelatives(leaf.getName(full=True), parent=True, fullPath=True)[0])


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
