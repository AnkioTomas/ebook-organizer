import random
import time
import requests
from src.config.config import REQUEST_CONFIG
from src.utils.logger import print_debug, print_info, print_error, print_warning

# 随机User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
]

def get_random_headers():
    """获取随机User-Agent的请求头"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Referer': 'https://book.douban.com/',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

def safe_request(url, method='get', params=None, retry_count=0, **kwargs):
    """安全的请求函数，带有重试、延迟和异常处理
    Args:
        url: 请求URL
        method: 请求方法，默认get
        params: 请求参数
        retry_count: 当前重试次数
        **kwargs: 其他请求参数
    Returns:
        requests.Response对象或None
    """
    # 合并默认请求头和自定义请求头
    headers = get_random_headers()
    if 'headers' in kwargs:
        headers.update(kwargs.pop('headers'))
    
    # 添加代理
    proxies = REQUEST_CONFIG['proxy']
    
    print_debug(f"发起请求: {method.upper()} {url}")
    if params:
        print_debug(f"请求参数: {params}")
    if proxies:
        print_debug(f"使用代理: {proxies}")
    
    try:
        # 请求前随机延迟，避免频繁请求
        if retry_count > 0 or random.random() < 0.8:  # 80%概率延迟
            delay = random.uniform(*REQUEST_CONFIG['request_delay'])
            print_debug(f"请求延迟: {delay:.2f}秒")
            time.sleep(delay)
        
        # 发起请求
        if method.lower() == 'get':
            response = requests.get(
                url, 
                headers=headers, 
                params=params, 
                proxies=proxies,
                timeout=REQUEST_CONFIG['timeout'],
                **kwargs
            )
        else:
            response = requests.post(
                url, 
                headers=headers, 
                data=params, 
                proxies=proxies,
                timeout=REQUEST_CONFIG['timeout'],
                **kwargs
            )
        
        # 检查响应状态
        if response.status_code == 200:
            print_info(f"请求成功: {response.status_code}")
            return response
        elif response.status_code == 403 or response.status_code == 429:
            print_warning(f"请求被限制 (状态码: {response.status_code})，等待后重试...")
            retry_delay = random.uniform(*REQUEST_CONFIG['retry_delay']) * (retry_count + 1)
            print_debug(f"重试延迟: {retry_delay:.2f}秒")
            time.sleep(retry_delay)
        else:
            print_warning(f"请求失败 (状态码: {response.status_code})")
            
    except requests.exceptions.Timeout:
        print_error("请求超时")
    except requests.exceptions.ConnectionError:
        print_error("连接错误")
    except Exception as e:
        print_error(f"请求异常: {e}")
    
    # 重试逻辑
    if retry_count < REQUEST_CONFIG['max_retries']:
        print_info(f"第 {retry_count + 1} 次重试...")
        return safe_request(url, method, params, retry_count + 1, **kwargs)
    else:
        print_error("达到最大重试次数，请求失败")
        return None 