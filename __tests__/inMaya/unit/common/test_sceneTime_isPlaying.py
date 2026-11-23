"""``Time.isPlaying`` のテスト。"""

import sys
import unittest

import maya.cmds as cmds

import mlib

mlib.reload()

from mlib.common import Time


class IsPlayingTest(unittest.TestCase):
    """Time.isPlaying。"""

    def test_matches_play_query(self):
        """cmds.play(query=True, state=True) と同じ(バッチでは常にFalse)。"""
        self.assertIs(Time.isPlaying(), bool(cmds.play(query=True, state=True)))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
