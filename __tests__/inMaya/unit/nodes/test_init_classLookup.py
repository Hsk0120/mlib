"""``mlib.nodes`` の ``__getattr__`` が、登録の無い型名からクラスを探すときの候補の作り方を確かめる。"""

import sys
import unittest

import mlib

mlib.reload()

import mlib.nodes


class ClassLookupTest(unittest.TestCase):
    """先頭の文字を小文字にしても変わらない名前と、Mayaにない型名。"""

    def test_name_without_lowercase_form(self):
        """先頭が小文字の形を持たない大文字(U+2102 など)は、候補が1つだけになり、Mayaにない型として AttributeError。"""
        name = chr(0x2102) + "MlibNoSuchType"
        self.assertTrue(name[0].isupper())
        self.assertEqual(name[0].lower(), name[0])
        with self.assertRaises(AttributeError):
            getattr(mlib.nodes, name)

    def test_unknown_type_name(self):
        """先頭を小文字にした形も、名前そのままも、Mayaにない型なら AttributeError。"""
        with self.assertRaises(AttributeError):
            mlib.nodes.MlibNoSuchType
        self.assertFalse(hasattr(mlib.nodes, "MlibNoSuchType"))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
