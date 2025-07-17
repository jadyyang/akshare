#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Redis Cache 单元测试
"""

import unittest
import time
import pandas as pd
from unittest.mock import patch

# 尝试导入 Redis 相关模块，如果失败则跳过测试
try:
    import redis
    from akshare.utils.redis_cache import (
        RedisLRUCache, 
        lru_cache, 
        cached_function,
        configure_default_cache,
        clear_all_cache
    )
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


@unittest.skipIf(not REDIS_AVAILABLE, "Redis not available")
class TestRedisLRUCache(unittest.TestCase):
    """测试 Redis LRU 缓存基础功能"""
    
    def setUp(self):
        """测试前准备"""
        # 使用测试专用的 Redis 数据库 (DB 15)
        self.cache = RedisLRUCache(
            redis_url='redis://localhost:6379/15',
            prefix='test_cache',
            max_age=10
        )
        
    def tearDown(self):
        """测试后清理"""
        try:
            self.cache.clear_prefix()
        except Exception:
            pass
    
    def test_basic_set_get(self):
        """测试基本的设置和获取"""
        key = "test_key"
        value = {"data": "test_value", "number": 123}
        
        # 设置缓存
        success = self.cache.set(key, value)
        self.assertTrue(success)
        
        # 获取缓存
        cached_value = self.cache.get(key)
        self.assertEqual(cached_value, value)
    
    def test_dataframe_caching(self):
        """测试 DataFrame 缓存"""
        key = "test_df"
        df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': ['a', 'b', 'c']
        })
        
        # 设置 DataFrame 缓存
        success = self.cache.set(key, df)
        self.assertTrue(success)
        
        # 获取 DataFrame 缓存
        cached_df = self.cache.get(key)
        pd.testing.assert_frame_equal(cached_df, df)
    
    def test_expiration(self):
        """测试缓存过期"""
        key = "test_expire"
        value = "expire_test"
        
        # 设置短期缓存
        self.cache.set(key, value, expire=1)
        
        # 立即获取应该成功
        cached_value = self.cache.get(key)
        self.assertEqual(cached_value, value)
        
        # 等待过期后获取应该返回 None
        time.sleep(2)
        expired_value = self.cache.get(key)
        self.assertIsNone(expired_value)
    
    def test_key_generation(self):
        """测试缓存键生成"""
        def test_func(a, b, c=1):
            return a + b + c
        
        # 测试相同参数生成相同键
        key1 = self.cache._generate_cache_key(test_func, (1, 2), {'c': 3})
        key2 = self.cache._generate_cache_key(test_func, (1, 2), {'c': 3})
        self.assertEqual(key1, key2)
        
        # 测试不同参数生成不同键
        key3 = self.cache._generate_cache_key(test_func, (1, 3), {'c': 3})
        self.assertNotEqual(key1, key3)


@unittest.skipIf(not REDIS_AVAILABLE, "Redis not available")
class TestLRUCacheDecorator(unittest.TestCase):
    """测试 lru_cache 装饰器"""
    
    def setUp(self):
        """测试前准备"""
        configure_default_cache(
            redis_url='redis://localhost:6379/15',
            prefix='test_decorator',
            max_age=10
        )
        
    def tearDown(self):
        """测试后清理"""
        try:
            clear_all_cache()
        except Exception:
            pass
    
    def test_basic_decorator(self):
        """测试基本装饰器功能"""
        call_count = 0
        
        @lru_cache()
        def test_function(x, y=1):
            nonlocal call_count
            call_count += 1
            return x + y
        
        # 第一次调用
        result1 = test_function(1, y=2)
        self.assertEqual(result1, 3)
        self.assertEqual(call_count, 1)
        
        # 第二次调用相同参数，应该从缓存返回
        result2 = test_function(1, y=2)
        self.assertEqual(result2, 3)
        self.assertEqual(call_count, 1)  # 调用次数不应该增加
        
        # 不同参数，应该执行函数
        result3 = test_function(2, y=3)
        self.assertEqual(result3, 5)
        self.assertEqual(call_count, 2)
    
    def test_custom_config_decorator(self):
        """测试自定义配置装饰器"""
        @lru_cache(
            prefix='custom_test',
            max_age=5
        )
        def custom_function(data):
            return f"processed_{data}"
        
        # 测试函数正常工作
        result = custom_function("test")
        self.assertEqual(result, "processed_test")
        
        # 测试缓存信息
        cache_info = custom_function.cache_info()
        self.assertEqual(cache_info['cache_prefix'], 'custom_test')
        self.assertEqual(cache_info['max_age'], 5)
    
    def test_dataframe_decorator(self):
        """测试 DataFrame 装饰器缓存"""
        call_count = 0
        
        @lru_cache()
        def get_dataframe(rows):
            nonlocal call_count
            call_count += 1
            return pd.DataFrame({
                'id': range(rows),
                'value': [f'value_{i}' for i in range(rows)]
            })
        
        # 第一次调用
        df1 = get_dataframe(3)
        self.assertEqual(len(df1), 3)
        self.assertEqual(call_count, 1)
        
        # 第二次调用，应该从缓存返回
        df2 = get_dataframe(3)
        pd.testing.assert_frame_equal(df1, df2)
        self.assertEqual(call_count, 1)
    
    def test_cache_clear(self):
        """测试缓存清除"""
        call_count = 0
        
        @lru_cache()
        def clearable_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        # 建立缓存
        result1 = clearable_function(5)
        self.assertEqual(result1, 10)
        self.assertEqual(call_count, 1)
        
        # 再次调用，从缓存获取
        result2 = clearable_function(5)
        self.assertEqual(result2, 10)
        self.assertEqual(call_count, 1)
        
        # 清除缓存
        clearable_function.cache_clear()
        
        # 再次调用，应该重新执行
        result3 = clearable_function(5)
        self.assertEqual(result3, 10)
        self.assertEqual(call_count, 2)


@unittest.skipIf(not REDIS_AVAILABLE, "Redis not available")
class TestCachedFunction(unittest.TestCase):
    """测试 cached_function 功能"""
    
    def setUp(self):
        configure_default_cache(
            redis_url='redis://localhost:6379/15',
            prefix='test_cached_func',
            max_age=10
        )
    
    def tearDown(self):
        try:
            clear_all_cache()
        except Exception:
            pass
    
    def test_cached_function(self):
        """测试包装现有函数"""
        call_count = 0
        
        def original_function(a, b):
            nonlocal call_count
            call_count += 1
            return a * b
        
        # 包装函数
        cached_func = cached_function(original_function, max_age=5)
        
        # 测试缓存功能
        result1 = cached_func(3, 4)
        self.assertEqual(result1, 12)
        self.assertEqual(call_count, 1)
        
        result2 = cached_func(3, 4)
        self.assertEqual(result2, 12)
        self.assertEqual(call_count, 1)  # 不应该重新调用


class TestFallbackBehavior(unittest.TestCase):
    """测试降级行为（当Redis不可用时）"""
    
    @patch('akshare.utils.redis_cache.redis.from_url')
    def test_redis_unavailable_fallback(self, mock_redis):
        """测试 Redis 不可用时的降级行为"""
        # 模拟 Redis 连接失败
        mock_redis.side_effect = Exception("Redis connection failed")
        
        # 这应该不会抛出异常，而是使用内存缓存
        @lru_cache()
        def fallback_function(x):
            return x * 2
        
        # 函数应该正常工作
        result = fallback_function(5)
        self.assertEqual(result, 10)


class TestSerializationEdgeCases(unittest.TestCase):
    """测试序列化边界情况"""
    
    def test_complex_objects(self):
        """测试复杂对象的序列化"""
        if not REDIS_AVAILABLE:
            self.skipTest("Redis not available")
            
        cache = RedisLRUCache(
            redis_url='redis://localhost:6379/15',
            prefix='test_serialization'
        )
        
        try:
            # 测试复杂对象
            complex_data = {
                'dataframe': pd.DataFrame({'a': [1, 2], 'b': [3, 4]}),
                'list': [1, 2, 3, {'nested': 'dict'}],
                'tuple': (1, 2, 3),
                'set': {1, 2, 3},  # 注意：集合序列化后可能变成列表
            }
            
            success = cache.set('complex', complex_data)
            self.assertTrue(success)
            
            cached_data = cache.get('complex')
            self.assertIsNotNone(cached_data)
            
            # 验证 DataFrame
            pd.testing.assert_frame_equal(
                cached_data['dataframe'], 
                complex_data['dataframe']
            )
            
        finally:
            cache.clear_prefix()


if __name__ == '__main__':
    # 检查 Redis 是否可用
    if REDIS_AVAILABLE:
        try:
            # 尝试连接 Redis
            test_client = redis.Redis(host='localhost', port=6379, db=15)
            test_client.ping()
            print("Redis is available, running all tests...")
        except Exception as e:
            print(f"Redis is not available: {e}")
            print("Some tests will be skipped.")
    else:
        print("Redis dependencies not installed, most tests will be skipped.")
    
    # 运行测试
    unittest.main(verbosity=2)
