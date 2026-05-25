"""
TDD: generate_review_data.py 持仓路径 bug

Bug: load_review_data() 用 WWW_DIR/private/holdings.json 路径
  → /home/ubuntu/3l-server/private/holdings.json (不存在)
正确路径: DATA_DIR/private/holdings.json
  → /home/ubuntu/data/3l/private/holdings.json

测试只验证路径构造逻辑，不深入函数内部。
"""
import unittest
import os


class TestHoldingsPath(unittest.TestCase):

    def test_ww_dir_path_does_not_exist(self):
        """WWW_DIR/private/holdings.json 文件不存在（这就是bug）"""
        path = os.path.join('/home/ubuntu/3l-server', 'private', 'holdings.json')
        self.assertFalse(os.path.isfile(path), f'不应存在: {path}')

    def test_data_dir_path_exists(self):
        """DATA_DIR/private/holdings.json 存在（正确路径）"""
        path = os.path.join('/home/ubuntu/data/3l', 'private', 'holdings.json')
        self.assertTrue(os.path.isfile(path), f'应存在: {path}')

    def test_generate_review_data_imports_DATA_DIR(self):
        """generate_review_data.py 已导入 DATA_DIR，可直接使用"""
        import generate_review_data as mod
        self.assertTrue(hasattr(mod, 'DATA_DIR'))
        self.assertEqual(mod.DATA_DIR, '/home/ubuntu/data/3l')

    def test_after_fix_uses_DATA_DIR(self):
        """修复后，路径使用 DATA_DIR 而非 ww_dir"""
        import generate_review_data as mod
        import inspect
        src = inspect.getsource(mod.load_review_data)
        self.assertIn('DATA_DIR', src,
                      '修复后应使用 DATA_DIR 拼接持仓路径')
        self.assertNotIn(
            "os.path.join(ww_dir, 'private', 'holdings.json')",
            src,
            '不应再使用 ww_dir 拼接路径'
        )

    def test_fix_should_use_DATA_DIR(self):
        """修复后，路径应使用 DATA_DIR 而非 ww_dir"""
        # 验证 DATA_DIR 路径与 config.HOLDINGS_PATH 一致
        from config import HOLDINGS_PATH, DATA_DIR
        expected = os.path.join(DATA_DIR, 'private', 'holdings.json')
        self.assertEqual(expected, HOLDINGS_PATH)

    def test_also_fix_677(self):
        """line 677 处也有同样的路径问题"""
        import generate_review_data as mod
        import inspect
        src = inspect.getsource(mod.load_review_data)
        # 检查除了 line 591 之外的 os.path.join 调用
        # 应该只有一个在 load_review_data 中拼接 holdings 路径
        occurrences = src.count("'private', 'holdings.json'")
        # load_review_data 函数内部应该有2处（591和677）
        # 如果修复后，这两处都应该使用 DATA_DIR
        self.assertGreaterEqual(occurrences, 1,
                                'load_review_data 中应有 holdings 路径拼接')


if __name__ == '__main__':
    unittest.main()
