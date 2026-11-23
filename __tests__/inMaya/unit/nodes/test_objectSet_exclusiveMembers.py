"""partition内の排他所属とUndoを検証する。"""

import sys
import unittest

import maya.cmds as cmds
from support.namespaceCase import NamespaceCase

import mlib


class ObjectSetExclusiveMembersTest(NamespaceCase):
    def test_members_move_only_within_partition_and_undo(self):
        node = cmds.createNode("transform", name=self.ns + ":node")
        first = cmds.sets(empty=True, name=self.ns + ":first")
        second = cmds.sets(empty=True, name=self.ns + ":second")
        unrelated = cmds.sets(empty=True, name=self.ns + ":unrelated")
        cmds.partition(first, second, name=self.ns + ":partition")
        cmds.sets(node, addElement=first)
        cmds.sets(node, addElement=unrelated)
        target = mlib.getNode(second)
        self.assertIsNone(target.addMembers(node, exclusive=True))
        self.assertFalse(cmds.sets(node, isMember=first))
        self.assertTrue(cmds.sets(node, isMember=second))
        self.assertTrue(cmds.sets(node, isMember=unrelated))
        cmds.undo()
        self.assertTrue(cmds.sets(node, isMember=first))
        self.assertFalse(cmds.sets(node, isMember=second))
        cmds.redo()
        self.assertTrue(cmds.sets(node, isMember=second))
        self.assertIsNone(target.addMembers(exclusive=True))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
