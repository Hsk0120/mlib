"""``mlib.common.environment`` のテスト。

- common の照会・コールバックの契約を固定する。
"""

import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from support.namespaceCase import NamespaceCase

from mlib.common import Version
from mlib.common.environment import Environment

_FAKE_PLUGIN = "mlibSpecFakePlugin"


class EnvironmentTest(NamespaceCase):
    def test_matches_about(self):
        """各照会は cmds.about と一致し、版の年は API 版と一致する。"""
        self.assertIs(Environment.isBatch(), bool(cmds.about(batch=True)))
        self.assertIs(Environment.isInteractive(), not cmds.about(batch=True))
        version = Environment.getMayaVersion()
        self.assertIsInstance(version, Version)
        self.assertEqual(version, Version(cmds.about(version=True)))
        api = Environment.getApiVersion()
        self.assertIsInstance(api, int)
        self.assertEqual(api, cmds.about(apiVersion=True))
        self.assertEqual(version.major, api // 10000)

    def test_no_instance(self):
        """インスタンスは作れない。"""
        self.assertRaises(TypeError, Environment)


if __name__ == "__main__":
    unittest.main()
