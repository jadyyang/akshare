#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Redis Cache 使用示例
演示如何在 akshare 中使用基于 Redis 的分布式缓存
"""

import os
import time
import pandas as pd
from talib import func
from akshare.utils.redis_cache import lru_cache, configure_default_cache, cached_function

# 配置示例 - 你可以根据实际情况修改
# 1. 通过环境变量配置 (推荐)
# export REDIS_URL="redis://localhost:6379"
# export AKSHARE_CACHE_PREFIX="akshare_prod"

# 2. 或者通过代码配置默认缓存
configure_default_cache(
    redis_url=os.getenv('REDIS_URL', 'redis://localhost:6379'),
    prefix=os.getenv('AKSHARE_CACHE_PREFIX', 'akshare'),
    max_age=24 * 60 * 60  # 24小时
)


# 示例1: 最简单的使用方式 - 使用默认配置
@lru_cache()
def get_stock_basic_info(symbol: str) -> dict:
    """获取股票基本信息 - 使用默认缓存配置"""
    print(f"正在获取 {symbol} 的基本信息...")
    time.sleep(1)  # 模拟API调用延迟
    return {
        "symbol": symbol,
        "name": f"股票{symbol}",
        "price": 100.0,
        "timestamp": time.time()
    }


# 示例2: 自定义缓存配置
@lru_cache(
    prefix='stock_data',
    func_key='get_stock_price_history',  # 使用函数名作为缓存键
    max_age=60 * 60,  # 1小时缓存
)
def get_stock_price_history(symbol: str, days: int = 30) -> pd.DataFrame:
    """获取股票历史价格 - 自定义缓存时间"""
    print(f"正在获取 {symbol} 最近 {days} 天的价格数据...")
    time.sleep(2)  # 模拟较慢的API调用
    
    # 模拟返回 DataFrame
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days)
    data = {
        'date': dates,
        'price': [100 + i * 0.5 for i in range(days)],
        'volume': [1000000 + i * 10000 for i in range(days)]
    }
    return pd.DataFrame(data)


# 示例3: 针对不同环境使用不同缓存配置
def get_cache_for_env():
    """根据环境返回不同的缓存配置"""
    env = os.getenv('ENV', 'dev')
    
    if env == 'prod':
        return lru_cache(
            redis_url='redis://prod-redis-cluster:6379',
            prefix='akshare_prod',
            max_age=4 * 60 * 60,  # 生产环境缓存4小时
        )
    elif env == 'staging':
        return lru_cache(
            redis_url='redis://staging-redis:6379',
            prefix='akshare_staging',
            max_age=2 * 60 * 60,  # 测试环境缓存2小时
        )
    else:  # dev
        return lru_cache(
            redis_url='redis://localhost:6379',
            prefix='akshare_dev',
            max_age=30 * 60,  # 开发环境缓存30分钟
        )


# 使用环境相关的缓存
@get_cache_for_env()
def get_market_data(market: str = "A股") -> dict:
    """获取市场数据 - 环境相关缓存"""
    print(f"正在获取 {market} 市场数据...")
    time.sleep(1.5)
    return {
        "market": market,
        "total_stocks": 4000,
        "total_value": 50000000000,
        "timestamp": time.time()
    }


# 示例4: 原有函数的缓存改造
def original_expensive_function(param1: str, param2: int) -> str:
    """原有的耗时函数"""
    print(f"执行耗时操作: {param1}, {param2}")
    time.sleep(2)
    return f"结果: {param1}-{param2}"

# 使用 cached_function 包装现有函数
cached_expensive_function = cached_function(
    original_expensive_function, 
    max_age=30 * 60  # 30分钟缓存
)


def demo_basic_usage():
    """演示基本使用"""
    print("=== 基本使用演示 ===")
    
    # 第一次调用 - 会执行实际函数
    print("第一次调用:")
    result1 = get_stock_basic_info("600519")
    print(f"结果: {result1}")
    
    # 第二次调用 - 从缓存返回
    print("\n第二次调用 (应该从缓存返回):")
    result2 = get_stock_basic_info("600519")
    print(f"结果: {result2}")
    
    # 不同参数 - 会执行实际函数
    print("\n不同参数:")
    result3 = get_stock_basic_info("000001")
    print(f"结果: {result3}")


def demo_dataframe_caching():
    """演示 DataFrame 缓存"""
    print("\n=== DataFrame 缓存演示 ===")
    
    print("第一次获取历史数据:")
    df1 = get_stock_price_history("600519", 10)
    print(f"DataFrame shape: {df1.shape}")
    print(df1.head())
    
    print("\n第二次获取相同数据 (应该从缓存返回):")
    df2 = get_stock_price_history("600519", 10)
    print(f"DataFrame shape: {df2.shape}")
    
    # 验证是否是同一个对象的引用
    print(f"两次结果是否相等: {df1.equals(df2)}")


def demo_cache_management():
    """演示缓存管理"""
    print("\n=== 缓存管理演示 ===")
    
    # 调用一些函数生成缓存
    get_stock_basic_info("test1")
    get_market_data("A股")
    
    # 查看缓存信息
    print(f"stock_basic_info 缓存信息: {get_stock_basic_info.cache_info()}")
    print(f"market_data 缓存信息: {get_market_data.cache_info()}")
    
    # 清除特定函数的缓存
    print("\n清除 stock_basic_info 的缓存...")
    cleared = get_stock_basic_info.cache_clear()
    print(f"清除的缓存数量: {cleared}")
    
    # 再次调用应该重新执行
    print("再次调用 stock_basic_info (应该重新执行):")
    get_stock_basic_info("test1")


def demo_airflow_scenario():
    """演示 Airflow 场景下的使用"""
    print("\n=== Airflow 场景演示 ===")
    print("这模拟了两个不同的 Airflow 任务调用相同的函数")
    
    # 模拟 Task 1
    def airflow_task_1():
        print("Task 1 执行中...")
        data = get_market_data("A股")
        print(f"Task 1 获取到数据: {data['total_stocks']} 只股票")
        
    # 模拟 Task 2  
    def airflow_task_2():
        print("Task 2 执行中...")
        data = get_market_data("A股")  # 应该从缓存获取
        print(f"Task 2 获取到数据: {data['total_stocks']} 只股票")
    
    airflow_task_1()
    airflow_task_2()


if __name__ == "__main__":
    print("Redis 缓存使用示例")
    print("=" * 50)
    
    try:
        # 运行所有演示
        demo_basic_usage()
        demo_dataframe_caching()
        demo_cache_management()
        demo_airflow_scenario()
        
        print("\n=== 缓存改造示例 ===")
        print("原函数第一次调用:")
        result1 = cached_expensive_function("test", 123)
        print(f"结果: {result1}")
        
        print("原函数第二次调用 (从缓存):")
        result2 = cached_expensive_function("test", 123)
        print(f"结果: {result2}")
        
    except Exception as e:
        print(f"演示过程中出现错误: {e}")
        print("请确保 Redis 服务器正在运行，或者查看错误日志")
        
    print("\n演示完成！")
    print("\n使用提示:")
    print("1. 在生产环境中，建议通过环境变量配置 Redis 连接")
    print("2. 根据数据更新频率合理设置 max_age")
    print("3. 使用有意义的 prefix 来区分不同应用的缓存")
    print("4. 定期监控 Redis 内存使用情况")
