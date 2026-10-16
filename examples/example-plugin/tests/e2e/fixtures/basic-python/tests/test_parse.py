import unittest
from app.parse import first_word


class ParseTest(unittest.TestCase):
    def test_first_word(self):
        self.assertEqual(first_word('hello world'), 'hello')


if __name__ == '__main__':
    unittest.main()
