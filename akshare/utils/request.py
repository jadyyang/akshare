# !/usr/bin/env python
"""
Date: 2025/12/31
Desc: HTTP 请求工具函数
"""

import random
import time
from typing import Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter


DEFAULT_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


def get_session(headers: Optional[Dict[str, str]] = None) -> requests.Session:
    """
    创建带默认浏览器头的 Session
    :param headers: 额外请求头
    :type headers: dict
    :return: Session
    :rtype: requests.Session
    """
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    if headers:
        session.headers.update(headers)
    return session


def request_with_retry(
    url: str,
    params: Dict = None,
    timeout: int = 15,
    max_retries: int = 3,
    base_delay: float = 1.0,
    random_delay_range: Tuple[float, float] = (0.5, 1.5),
    session: Optional[requests.Session] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
) -> requests.Response:
    """
    带重试机制的 HTTP GET 请求
    :param url: 请求 URL
    :type url: str
    :param params: 请求参数
    :type params: dict
    :param timeout: 超时时间（秒）
    :type timeout: int
    :param max_retries: 最大重试次数
    :type max_retries: int
    :param base_delay: 基础延迟时间（秒），用于指数退避
    :type base_delay: float
    :param random_delay_range: 随机延迟范围（秒）
    :type random_delay_range: tuple
    :return: Response 对象
    :rtype: requests.Response
    :raises: 最后一次请求的异常
    """
    last_exception = None

    own_session = session is None
    if own_session:
        session = get_session()

    try:
        for attempt in range(max_retries):
            try:
                response = session.get(
                    url,
                    params=params,
                    timeout=timeout,
                    headers=headers,
                    cookies=cookies,
                )
                response.raise_for_status()
                return response

            except (requests.RequestException, ValueError) as e:
                last_exception = e

                if attempt < max_retries - 1:
                    # 指数退避 + 随机抖动
                    delay = base_delay * (2**attempt) + random.uniform(*random_delay_range)
                    time.sleep(delay)
    finally:
        if own_session and session is not None:
            session.close()

    raise last_exception
