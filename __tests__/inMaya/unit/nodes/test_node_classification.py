"""``Node.isClassified`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase


class IsClassifiedTest(NamespaceCase):
    """isClassified は cmds.listNodeTypes(分類) に型が入るかと同じ。"""

    PREFIX = "mlibClassified_"

    def test_matches_list_node_types(self):
        """シェーダー・テクスチャ・ユーティリティ・分類の無い型で一致する。"""
        nodes = [
            mlib.createNode(kind, name=self.name(kind), skipSelect=True) for kind in ("blinn", "lambert", "file", "multiplyDivide", "transform", "network")
        ]
        for classification in ("shader", "shader/surface", "texture", "texture/2d", "utility"):
            listed = set(cmds.listNodeTypes(classification) or [])
            for node in nodes:
                with self.subTest(classification=classification, node=node.getType()):
                    self.assertIs(node.isClassified(classification), node.getType() in listed)

    def test_errors(self):
        """文字列でない・空の分類と、削除したノードを拒否する。"""
        node = mlib.createNode("blinn", name=self.name("deleted"), skipSelect=True)
        with self.assertRaises(TypeError):
            node.isClassified(None)
        with self.assertRaises(ValueError):
            node.isClassified("")
        node.delete()
        with self.assertRaises(RuntimeError):
            node.isClassified("shader")


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
