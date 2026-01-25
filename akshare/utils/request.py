# !/usr/bin/env python
"""
Date: 2025/12/31
Desc: HTTP 请求工具函数
"""

import logging
import random
import time
from typing import Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

try:
    # NOTE(akshare): TLS 指纹模拟支持（东财反爬适配）
    from curl_cffi import requests as curl_requests

    _HAS_CURL_CFFI = True
except Exception:
    curl_requests = None
    _HAS_CURL_CFFI = False


DEFAULT_HEADERS: Dict[str, str] = {
    # NOTE(akshare): 模拟浏览器请求头，配合会话与 TLS 指纹提升稳定性
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


logger = logging.getLogger(__name__)


def get_session(headers: Optional[Dict[str, str]] = None) -> requests.Session:
    """
    创建带默认浏览器头的 Session
    :param headers: 额外请求头
    :type headers: dict
    :return: Session
    :rtype: requests.Session
    """
    # NOTE(akshare): 统一 Session 以保留 Cookie（东财连续请求稳定性）
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(DEFAULT_HEADERS)
    if headers:
        session.headers.update(headers)
    return session


def get_tls_session(
    headers: Optional[Dict[str, str]] = None,
    impersonate: str = "chrome120",
):
    """
    创建带 TLS 指纹模拟的 Session（基于 curl_cffi）
    :param headers: 额外请求头
    :type headers: dict
    :param impersonate: 浏览器指纹名称
    :type impersonate: str
    :return: Session 或 None（未安装 curl_cffi）
    :rtype: requests.Session | None
    """
    # NOTE(akshare): TLS 指纹模拟会话（优先用于东财请求）
    if not _HAS_CURL_CFFI:
        return None
    session = curl_requests.Session(impersonate=impersonate)
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

    # NOTE(akshare): 允许复用外部 Session 保持 Cookie
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
                # NOTE(akshare): 输出失败日志，便于定位底层错误
                logger.warning(
                    "HTTP request failed (attempt %s/%s): %s",
                    attempt + 1,
                    max_retries,
                    e,
                    extra={"url": url, "params": params},
                )

                if attempt < max_retries - 1:
                    # 指数退避 + 随机抖动
                    delay = base_delay * (2**attempt) + random.uniform(*random_delay_range)
                    time.sleep(delay)
    finally:
        if own_session and session is not None:
            session.close()

    raise last_exception


def request_with_retry_tls(
    url: str,
    params: Dict = None,
    timeout: int = 15,
    max_retries: int = 3,
    base_delay: float = 1.0,
    random_delay_range: Tuple[float, float] = (0.5, 1.5),
    session: Optional[requests.Session] = None,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[Dict[str, str]] = None,
    impersonate: str = "chrome120",
) -> requests.Response:
    """
    带 TLS 指纹模拟的重试请求（基于 curl_cffi）；不可用时回退到 requests
    """
    # NOTE(akshare): TLS 指纹模拟不可用时自动回退
    if not _HAS_CURL_CFFI:
        return request_with_retry(
            url,
            params=params,
            timeout=timeout,
            max_retries=max_retries,
            base_delay=base_delay,
            random_delay_range=random_delay_range,
            session=session,
            headers=headers,
            cookies=cookies,
        )

    # NOTE(akshare): 复用 TLS Session 保持 Cookie/连接状态
    own_session = session is None
    if own_session:
        session = get_tls_session(headers=headers, impersonate=impersonate)
        if session is None:
            return request_with_retry(
                url,
                params=params,
                timeout=timeout,
                max_retries=max_retries,
                base_delay=base_delay,
                random_delay_range=random_delay_range,
                session=None,
                headers=headers,
                cookies=cookies,
            )

    last_exception = None
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
                # NOTE(akshare): 输出 TLS 失败日志，便于定位底层错误
                logger.warning(
                    "TLS request failed (attempt %s/%s): %s",
                    attempt + 1,
                    max_retries,
                    e,
                    extra={"url": url, "params": params},
                )
                err_text = str(e)
                # NOTE(akshare): curl_cffi 异常时回退到 requests
                if "curl:" in err_text or err_text.startswith("curl:"):
                    if own_session and session is not None:
                        session.close()
                    return request_with_retry(
                        url,
                        params=params,
                        timeout=timeout,
                        max_retries=max_retries,
                        base_delay=base_delay,
                        random_delay_range=random_delay_range,
                        session=None,
                        headers=headers,
                        cookies=cookies,
                    )
                if attempt < max_retries - 1:
                    delay = base_delay * (2**attempt) + random.uniform(
                        *random_delay_range
                    )
                    time.sleep(delay)
    finally:
        if own_session and session is not None:
            session.close()

    raise last_exception
