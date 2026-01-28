# !/usr/bin/env python
"""
Date: 2025/3/10 18:00
Desc: 通用帮助函数
"""

import math
import random
import time
from typing import List, Dict

import pandas as pd

from ..utils.request import get_session, get_tls_session, request_with_retry, request_with_retry_tls
from ..utils.tqdm import get_tqdm


def fetch_paginated_data(
    url: str,
    base_params: Dict,
    timeout: int = 15,
    headers: Dict = None,
    session=None,
    use_tls_impersonation: bool = False,
    impersonate: str = "chrome120",
):
    """
    东方财富-分页获取数据并合并结果
    https://quote.eastmoney.com/f1.html?newcode=0.000001
    :param url: 股票代码
    :type url: str
    :param base_params: 基础请求参数
    :type base_params: dict
    :param timeout: 请求超时时间
    :type timeout: str
    :return: 合并后的数据
    :rtype: pandas.DataFrame
    """
    # 复制参数以避免修改原始参数
    params = base_params.copy()
    # NOTE(akshare): 支持复用 Session + TLS 指纹（东财反爬适配）
    own_session = session is None
    if own_session:
        if use_tls_impersonation:
            session = get_tls_session(headers=headers, impersonate=impersonate)
        if session is None:
            session = get_session()

    try:
        # 获取第一页数据，用于确定分页信息
        # NOTE(akshare): 按需选择 TLS/常规请求函数
        request_func = (
            request_with_retry_tls if use_tls_impersonation else request_with_retry
        )
        request_kwargs = {
            "url": url,
            "params": params,
            "timeout": timeout,
            "session": session,
            "headers": headers,
        }
        if use_tls_impersonation:
            request_kwargs["impersonate"] = impersonate
        r = request_func(**request_kwargs)
        data_json = r.json()
        # 计算分页信息
        per_page_num = len(data_json["data"]["diff"])
        total_page = math.ceil(data_json["data"]["total"] / per_page_num)
        # 存储所有页面数据
        temp_list = []
        # 添加第一页数据
        temp_list.append(pd.DataFrame(data_json["data"]["diff"]))
        # 获取进度条
        tqdm = get_tqdm()
        # 获取剩余页面数据
        for page in tqdm(range(2, total_page + 1), leave=False):
            params.update({"pn": page})
            # 添加随机延迟，避免请求过于频繁
            time.sleep(random.uniform(0.5, 1.5))
            request_kwargs = {
                "url": url,
                "params": params,
                "timeout": timeout,
                "session": session,
                "headers": headers,
            }
            if use_tls_impersonation:
                request_kwargs["impersonate"] = impersonate
            r = request_func(**request_kwargs)
            data_json = r.json()
            inner_temp_df = pd.DataFrame(data_json["data"]["diff"])
            temp_list.append(inner_temp_df)
    finally:
        if own_session and session is not None:
            session.close()
    # 合并所有数据
    temp_df = pd.concat(temp_list, ignore_index=True)
    temp_df["f3"] = pd.to_numeric(temp_df["f3"], errors="coerce")
    temp_df.sort_values(by=["f3"], ascending=False, inplace=True, ignore_index=True)
    temp_df.reset_index(inplace=True)
    temp_df["index"] = temp_df["index"].astype(int) + 1
    return temp_df


def set_df_columns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """
    设置 pandas.DataFrame 为空的情况
    :param df: 需要设置命名的数据框
    :type df: pandas.DataFrame
    :param cols: 字段的列表
    :type cols: list
    :return: 重新设置后的数据
    :rtype: pandas.DataFrame
    """
    if df.shape == (0, 0):
        return pd.DataFrame(data=[], columns=cols)
    else:
        df.columns = cols
        return df
