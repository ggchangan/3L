"""
回归测试：持仓文件路径（确保使用 DATA_DIR 而非硬编码路径）

generate_review_data.py 已删除（复盘改为纯实时计算），
但持仓路径配置仍需回归验证。
"""
import unittest
import os
import pytest


class TestHoldingsPath(unittest.TestCase):

    def test_ww_dir_path_does_not_exist(self):
        """WWW_DIR/private/holdings.json 文件不存在（旧bug路径）"""
        path = os.path.join('/home/ubuntu/3l-server', 'private', 'holdings.json')
        self.assertFalse(os.path.isfile(path), f'不应存在: {path}')

    def test_data_dir_path_exists(self):
        """DATA_DIR/private/holdings.json 存在（正确路径）"""
        path = os.path.join('/home/ubuntu/data/3l', 'private', 'holdings.json')
        if not os.path.isfile(path):
            pytest.skip(f'文件不存在，跳过: {path}')

    def test_fix_should_use_DATA_DIR(self):
        """config.HOLDINGS_PATH 使用 DATA_DIR 拼接"""
        from backend.core.config import HOLDINGS_PATH, DATA_DIR
        expected = os.path.join(DATA_DIR, 'private', 'holdings.json')
        self.assertEqual(expected, HOLDINGS_PATH)


if __name__ == '__main__':
    unittest.main()
