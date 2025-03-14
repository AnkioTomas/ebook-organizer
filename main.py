import difflib
import json
import os
import random
import re
import time
from xml.sax.saxutils import escape

import PyPDF2
import colorama
import ebookmeta  # 处理 EPUB/MOBI/AWZ3 格式的元数据
import requests
from bs4 import BeautifulSoup
import opencc  # 用于繁体转简体

# 初始化繁体转简体转换器
converter = opencc.OpenCC('t2s')

# 繁体转简体函数
def to_simplified(text):
    """将繁体字转换为简体字"""
    if not text:
        return text
    return converter.convert(text)

# 初始化colorama，支持Windows下的彩色输出
colorama.init(autoreset=True)

# === 日志配置 ===
# 定义彩色打印函数，替代logger
def print_debug(msg):
    """打印调试信息（青色）"""
    print(f"{colorama.Fore.CYAN}DEBUG: {msg}{colorama.Style.RESET_ALL}")

def print_info(msg):
    """打印信息（绿色）"""
    print(f"{colorama.Fore.GREEN}INFO: {msg}{colorama.Style.RESET_ALL}")

def print_warning(msg):
    """打印警告（黄色）"""
    print(f"{colorama.Fore.YELLOW}WARNING: {msg}{colorama.Style.RESET_ALL}")

def print_error(msg):
    """打印错误（红色）"""
    print(f"{colorama.Fore.RED}ERROR: {msg}{colorama.Style.RESET_ALL}")

def print_critical(msg):
    """打印严重错误（红底白字）"""
    print(f"{colorama.Back.RED}{colorama.Fore.WHITE}CRITICAL: {msg}{colorama.Style.RESET_ALL}")

# 字符画和作者信息
ASCII_ART = r"""
 _____             _                    ______             _      _____                      _              
|  __ \           | |                  |  ____|           | |    / ____|                    (_)             
| |  | | ___  _   | |__   __ _ _ __    | |__   ___   ___ | | __| |     ___  _ ____   _____ _ _ __ ___ _ __ 
| |  | |/ _ \| | | | '_ \ / _` | '_ \   |  __| / _ \ / _ \| |/ /| |    / _ \| '_ \ \ / / _ \ | '__/ _ \ '__|
| |__| | (_) | |_| | |_) | (_| | | | |  | |___| (_) | (_) |   < | |___| (_) | | | \ V /  __/ | | |  __/ |   
|_____/ \___/ \__,_|_.__/ \__,_|_| |_|  |______\___/ \___/|_|\_\ \_____\___/|_| |_|\_/ \___|_|_|  \___|_|   
"""

AUTHOR_INFO = """
作者: Ankio
版本: 1.0.0
日期: 2024-01-07
描述: 电子书文件整理工具，自动解析文件名，获取豆瓣信息，整理到独立文件夹
"""

# === 目录 & 配置 ===
BOOKS_DIR = "./books"  # 书籍目录
CONFIG_FILE = "./douban_config.json"  # 配置文件
NEW_NAME_PATTERN = "{author} - {title} ({year})"  # 文件夹命名格式
DOUBAN_SEARCH_URL = "https://www.douban.com/search"
# 随机User-Agent列表
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36'
]
# 请求配置
REQUEST_CONFIG = {
    'timeout': 10,  # 请求超时时间（秒）
    'max_retries': 3,  # 最大重试次数
    'retry_delay': [2, 5],  # 重试延迟范围（秒）
    'request_delay': [1, 3],  # 请求间隔范围（秒）
    'proxy': None  # 代理设置，格式如 {'http': 'http://127.0.0.1:7890', 'https': 'http://127.0.0.1:7890'}
}
SUPPORTED_FORMATS = ['pdf', 'epub', 'mobi', 'txt', 'azw3','azw']

# === 请求工具函数 ===
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
    """安全的请求函数，带有重试、延迟和异常处理"""
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

# === 解析文件名 ===
def parse_filename(filename):
    """
    解析电子书文件名：
    - 书名：提取主要标题部分
    - 作者：从括号中提取可能的作者
    - 年份：括号内的四位数字
    """
    # 保存原始文件名用于调试
    original_name = filename
    name, ext = os.path.splitext(filename)
    ext = ext.lstrip(".")
    
    # 第一步：清理文件名，删除常见的无关标记
    # 删除Z-Library标记
    name = re.sub(r'\s*\(Z-Library\)', '', name).strip()
    
    # 第二步：提取年份（如果存在）
    year = None
    year_match = re.search(r"\((\d{4})\)", name)
    if year_match:
        year = year_match.group(1)
    
    # 第三步：提取作者（优先从括号中提取）
    author = None
    
    # 尝试从括号中提取作者
    author_matches = re.findall(r"\(([^()]+)\)", name)
    for possible_author in author_matches:
        possible_author = possible_author.strip()
        # 跳过年份和明显不是作者的内容
        if possible_author.isdigit() or len(possible_author) > 20:
            continue
            
        # 如果包含特殊标记如"〔法〕"，很可能是作者
        if re.search(r'〔[^〕]+〕|\([^)]+\)|\[[^\]]+\]|（[^）]+）', possible_author):
            # 直接去除国籍标记，保留作者名
            author = re.sub(r'〔[^〕]+〕|\([^)]+\)|\[[^\]]+\]|（[^）]+）', '', possible_author).strip()
            break
            
        # 否则，如果长度合适，可能是作者
        author = possible_author
        break
    
    # 如果括号中没找到作者，尝试从文件名格式推断
    if not author and " - " in name:
        parts = name.split(" - ", 1)
        if len(parts[0].strip()) < 20:  # 如果前半部分较短，可能是作者
            author = parts[0].strip()
    
    # 第四步：提取标题
    title = None
    
    # 首先检查是否有书名号，优先提取
    title_match = re.search(r'《([^》]+)》', name)
    if title_match:
        title = title_match.group(1).strip()
    else:
        # 如果没有书名号，尝试去除所有括号内容后提取主要部分
        clean_name = re.sub(r'\([^)]*\)|\[[^\]]*\]|（[^）]*）|【[^】]*】', ' ', name).strip()
        
        # 如果有横线且已经找到作者，取横线后面的部分作为标题
        if author and " - " in clean_name:
            parts = clean_name.split(" - ", 1)
            if parts[0].strip() == author:
                title = parts[1].strip()
            else:
                title = clean_name
        else:
            title = clean_name
    
    # 第五步：清理标题和作者
    if title:
        # 删除标题中的特殊标记
        title = re.sub(r'【[^】]*】|《|》', '', title).strip()
        # 如果标题太长，尝试截取主要部分
        if len(title) > 30:
            # 尝试在第一个标点符号处截断
            short_title_match = re.search(r'^[^，。：；！？,.:;!?]+', title)
            if short_title_match:
                title = short_title_match.group(0).strip()
    
    if author:
        # 清理作者名中的特殊字符和国籍标记
        author = re.sub(r'\[[^\]]*\]|〔[^〕]*〕|\([^)]*\)|（[^）]*）|【[^】]*】', '', author).strip()
    
    # 最后一步：确保标题和作者没有前导和尾部的特殊字符
    if title:
        title = re.sub(r'^[^\u4e00-\u9fa5a-zA-Z0-9]+|[^\u4e00-\u9fa5a-zA-Z0-9]+$', '', title).strip()
        # 转换为简体字
        title = to_simplified(title)
    if author:
        author = re.sub(r'^[^\u4e00-\u9fa5a-zA-Z0-9]+|[^\u4e00-\u9fa5a-zA-Z0-9]+$', '', author).strip()
        # 转换为简体字
        author = to_simplified(author)
    
    # 调试信息
    # print(f"解析 '{original_name}' => 作者: '{author}', 标题: '{title}', 年份: '{year}'")
    
    return author, title, year, ext


# === 解析 PDF 文件元数据 ===
def extract_pdf_metadata(pdf_path):
    """尝试从 PDF 文件元数据中提取书籍信息"""
    try:
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            metadata = reader.metadata
            title = metadata.get("/Title", "").strip() if metadata else None
            author = metadata.get("/Author", "").strip() if metadata else None
            # 转换为简体字
            if title:
                title = to_simplified(title)
            if author:
                author = to_simplified(author)
            return author, title
    except Exception as e:
        print_error(f"无法读取 PDF 元数据: {e}")
        return None, None


# === 解析 EPUB/MOBI/AWZ3 文件元数据 ===
def extract_ebook_metadata(file_path):
    """尝试从 EPUB/MOBI/AWZ3 文件的元数据中提取书籍信息"""
    try:
        metadata = ebookmeta.get_metadata(file_path)
        author = metadata.get("author")
        title = metadata.get("title")
        # 转换为简体字
        if title:
            title = to_simplified(title)
        if author:
            author = to_simplified(author)
        return author, title
    except Exception as e:
        print_error(f"无法读取电子书元数据: {e}")
        return None, None


# === 从豆瓣获取书籍信息 ===
def calculate_title_similarity(title1, title2):
    """计算两个标题的相似度"""
    # 移除空格和标点符号，便于比较
    def normalize(text):
        # 先转为简体字
        text = to_simplified(text)
        return re.sub(r'[\s.,，。:：;；!！?？《》\[\]【】()（）]', '', text.lower())
    
    norm_title1 = normalize(title1)
    norm_title2 = normalize(title2)
    
    # 使用difflib计算相似度
    similarity = difflib.SequenceMatcher(None, norm_title1, norm_title2).ratio()
    
    # 如果一个标题是另一个的子串，增加相似度
    if norm_title1 in norm_title2 or norm_title2 in norm_title1:
        similarity = max(similarity, 0.8)  # 至少80%相似
        
    return similarity

def search_douban(query, expected_author=None, fetch_detail=True, min_similarity=0.6):
    """在豆瓣搜索书籍，返回匹配度最高的书籍信息
    Args:
        query: 搜索关键词
        expected_author: 预期的作者名（可选，用于比较）
        fetch_detail: 是否获取详情页信息（可选，默认True）
        min_similarity: 最小标题相似度（可选，默认0.6）
    """
    print_info(f"搜索豆瓣: '{query}'")
    params = {"cat": "1001", "q": query}
    res = safe_request(DOUBAN_SEARCH_URL, params=params)
    
    if not res:
        print_error("豆瓣搜索失败")
        return None

    soup = BeautifulSoup(res.content, 'html.parser')
    results = soup.select('.result-list .result')
    
    print_info(f"找到 {len(results)} 个搜索结果")
    
    # 存储所有匹配的结果，按相似度排序
    matched_results = []
    
    for index, result in enumerate(results):
        try:
            # 获取标题和链接
            title_elem = result.select_one('.title h3 a')
            if not title_elem:
                print_debug(f"结果 #{index+1}: 无法找到标题元素")
                continue
            
            # 获取标题并转为简体字
            title = to_simplified(title_elem.get_text(strip=True).replace(' ', ''))
            book_url = title_elem.get('href', '')
            
            # 计算标题相似度
            similarity = calculate_title_similarity(query, title)
            print_info(f"结果 #{index+1}: 标题='{title}', 相似度={similarity:.2f}")
            
            # 如果相似度太低，跳过
            if similarity < min_similarity:
                print_debug(f"结果 #{index+1}: 标题相似度过低 ({similarity:.2f} < {min_similarity})")
                continue
            
            # 从重定向URL中提取真实的豆瓣图书链接
            subject_id = None
            if 'link2' in book_url:
                from urllib.parse import parse_qs, urlparse
                parsed = urlparse(book_url)
                query_params = parse_qs(parsed.query)
                real_url = query_params.get('url', [''])[0]
                
                # URL解码
                real_url = requests.utils.unquote(real_url)
                
                # 从真实URL中提取ID
                subject_match = re.search(r'subject/(\d+)', real_url)
                if subject_match:
                    subject_id = subject_match.group(1)
            
            if not subject_id:
                print_debug(f"结果 #{index+1}: 无法提取豆瓣ID")
                continue
                
            # 构建真实的豆瓣图书URL
            real_book_url = f'https://book.douban.com/subject/{subject_id}/'
            print_debug(f"结果 #{index+1}: 豆瓣URL={real_book_url}")
            
            # 获取评分信息
            rating_info = result.select_one('.rating-info')
            if not rating_info:
                print_debug(f"结果 #{index+1}: 无法找到评分信息")
                continue
                
            # 获取出版信息
            subject_cast = rating_info.select_one('.subject-cast')
            if not subject_cast:
                print_debug(f"结果 #{index+1}: 无法找到出版信息")
                continue
                
            subject_info = to_simplified(subject_cast.get_text(strip=True))
            parts = subject_info.split('/')
            parts = [p.strip() for p in parts]
            
            # 解析作者、出版社、年份
            author = to_simplified(parts[0])
            publisher = to_simplified(parts[-2]) if len(parts) > 2 else None
            
            # 尝试从出版信息中提取年份
            year = None
            for part in parts:
                if part.strip().isdigit() and len(part.strip()) == 4:
                    year = part.strip()
                    break
            
            print_debug(f"结果 #{index+1}: 作者='{author}', 出版社='{publisher}', 年份='{year}'")
            
            # 获取封面图片URL
            cover_elem = result.select_one('.pic img')
            cover_url = None
            if cover_elem:
                cover_url = cover_elem.get('src')
            
            # 获取评分和评价人数
            rating = rating_info.select_one('.rating_nums')
            rating = rating.get_text(strip=True) if rating else None
            
            rating_people = rating_info.select_one('.rating_nums + span')
            rating_people = rating_people.get_text(strip=True).strip('(人评价)') if rating_people else None
            
            print_debug(f"结果 #{index+1}: 评分={rating}, 评价人数={rating_people}")
            
            # 获取简介
            intro = result.select_one('.content p')
            intro = to_simplified(intro.get_text(strip=True)) if intro else None

            book_info = {
                "title": title,
                "author": author,
                "year": year,
                "publisher": publisher,
                "cover_url": cover_url,
                "rating": rating,
                "rating_people": rating_people,
                "intro": intro,
                "url": real_book_url,
                "douban_id": subject_id,
                "similarity": similarity,
                "index": index + 1  # 保存结果的序号，用于用户选择
            }
            
            # 将结果添加到匹配列表
            matched_results.append(book_info)

        except Exception as e:
            print_error(f"解析搜索结果 #{index+1} 时出错: {e}")
            continue
    
    # 如果没有匹配的结果，返回None
    if not matched_results:
        print_warning("没有找到匹配的书籍")
        return None
        
    # 按相似度排序
    matched_results.sort(key=lambda x: x["similarity"], reverse=True)
    
    # 获取最高相似度
    highest_similarity = matched_results[0]["similarity"]
    
    # 筛选出相似度相同的最高匹配结果
    top_matches = [r for r in matched_results if abs(r["similarity"] - highest_similarity) < 0.01]
    
    print_info(f"找到 {len(top_matches)} 个最佳匹配结果 (相似度: {highest_similarity:.2f})")
    
    # 如果只有一个最佳匹配，直接返回
    if len(top_matches) == 1:
        best_match = top_matches[0]
        print_info(f"最佳匹配: '{best_match['title']}' (相似度: {best_match['similarity']:.2f})")
    else:
        # 如果有多个匹配且提供了预期作者，尝试匹配作者
        if expected_author and len(top_matches) > 1:
            # 清理预期作者名
            expected_author = re.sub(r'[\[（\(【〔][^\]）\)】〕]*[\]）\)】〕]', '', expected_author).strip()
            expected_author = to_simplified(expected_author)
            
            # 尝试找到作者匹配的结果
            author_matches = []
            for match in top_matches:
                # 清理作者名以便比较
                clean_author = re.sub(r'[\[（\(【〔][^\]）\)】〕]*[\]）\)】〕]', '', match["author"]).strip()
                
                # 计算作者相似度
                author_similarity = difflib.SequenceMatcher(None, expected_author.lower(), clean_author.lower()).ratio()
                match["author_similarity"] = author_similarity
                
                # 如果作者相似度高，加入匹配列表
                if author_similarity > 0.7:
                    author_matches.append(match)
            
            # 如果找到作者匹配的结果，按作者相似度排序
            if author_matches:
                author_matches.sort(key=lambda x: x["author_similarity"], reverse=True)
                best_match = author_matches[0]
                print_info(f"根据作者匹配选择: '{best_match['title']}' 作者: '{best_match['author']}' (作者相似度: {best_match['author_similarity']:.2f})")
            else:
                # 如果没有作者匹配，让用户选择
                best_match = user_select_match(top_matches)
        else:
            # 如果没有预期作者或只有一个匹配，让用户选择
            best_match = user_select_match(top_matches)
    
    # 获取详情页信息（ISBN等）
    if fetch_detail and best_match["url"]:
        print_info(f"获取详情页信息: {best_match['url']}")
        detail_info = fetch_douban_book_info(best_match["url"])
        if detail_info:
            best_match.update(detail_info)
    
    return best_match

def user_select_match(matches):
    """让用户从多个匹配结果中选择一个"""
    print("\n" + colorama.Fore.CYAN + "=== 找到多个匹配结果，请选择 ===" + colorama.Style.RESET_ALL)
    
    for i, match in enumerate(matches):
        print(f"{colorama.Fore.YELLOW}[{i+1}] {colorama.Fore.GREEN}{match['title']}{colorama.Style.RESET_ALL}")
        print(f"   作者: {colorama.Fore.WHITE}{match['author']}{colorama.Style.RESET_ALL}")
        print(f"   出版社: {colorama.Fore.WHITE}{match['publisher'] or '未知'}{colorama.Style.RESET_ALL}")
        print(f"   年份: {colorama.Fore.WHITE}{match['year'] or '未知'}{colorama.Style.RESET_ALL}")
        print(f"   评分: {colorama.Fore.WHITE}{match['rating'] or '未知'} ({match['rating_people'] or '0'}人评价){colorama.Style.RESET_ALL}")
        if match.get('intro'):
            # 截取简介的前50个字符
            short_intro = match['intro'][:50] + ('...' if len(match['intro']) > 50 else '')
            print(f"   简介: {colorama.Fore.WHITE}{short_intro}{colorama.Style.RESET_ALL}")
        print()
    
    # 获取用户选择
    while True:
        try:
            choice = input(f"{colorama.Fore.YELLOW}请输入选择的序号 (1-{len(matches)}): {colorama.Style.RESET_ALL}")
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(matches):
                selected = matches[choice_idx]
                print_info(f"已选择: '{selected['title']}' 作者: '{selected['author']}'")
                return selected
            else:
                print_error(f"无效的选择，请输入1-{len(matches)}之间的数字")
        except ValueError:
            print_error("请输入有效的数字")


# === 解析豆瓣书籍详情页 ===
def fetch_douban_book_info(book_url):
    """解析豆瓣书籍详情页，返回补充信息"""
    print_info(f"获取书籍详情: {book_url}")
    try:
        res = safe_request(book_url)
        if not res:
            print_error("获取详情页失败")
            return None

        soup = BeautifulSoup(res.content, 'html.parser')
        
        # 获取图书信息区域
        info = soup.select_one('#info')
        if not info:
            print_error("无法找到图书信息区域")
            return None
            
        # 获取所有文本行
        info_text = info.get_text()

        # 解析详细信息
        def extract_field(field):
            pattern = f'{field}:\\s*([^\\n]+)'
            match = re.search(pattern, info_text)
            value = match.group(1).strip() if match else None
            # 转换为简体字
            if value:
                value = to_simplified(value)
            print_debug(f"提取字段 '{field}': {value}")
            return value
            
        # 获取各种信息
        isbn = extract_field('ISBN')
        pages = extract_field('页数')
        price = extract_field('定价')
        binding = extract_field('装帧')
        series = extract_field('丛书')
        publish_year = extract_field('出版年')
        publisher = extract_field('出版社')
        
        # 获取作者（可能有多个）
        authors = []
        author_links = info.select('a[href^="/author/"]')
        if author_links:
            authors = [to_simplified(a.get_text(strip=True)) for a in author_links]
            print_debug(f"找到作者: {authors}")
            
        # 获取译者（如果有）
        translators = []
        translator_text = extract_field('译者')
        if translator_text:
            translators = [to_simplified(t.strip()) for t in translator_text.split(',')]
            print_debug(f"找到译者: {translators}")

        # 获取标签
        tags = []
        # 查找包含criteria的script标签
        script_tags = soup.find_all('script', type='text/javascript')
        for script in script_tags:
            script_text = script.string
            if script_text and 'criteria' in script_text:
                # 使用正则表达式提取criteria中的标签
                criteria_match = re.search(r"criteria\s*=\s*'([^']*)'", script_text)
                if criteria_match:
                    criteria_text = criteria_match.group(1)
                    # 分割并提取7:开头的标签，排除包含subject的标签
                    tag_parts = [part for part in criteria_text.split('|') 
                               if part.startswith('7:') and 'subject' not in part]
                    tags = [to_simplified(part.split(':')[1]) for part in tag_parts]
                break

        # 如果从JS中没有找到标签，尝试从页面中提取
        if not tags:
            tag_elements = soup.select('a.tag')
            if tag_elements:
                tags = [to_simplified(tag.get_text(strip=True)) for tag in tag_elements]
        
        # 标签去重
        tags = list(dict.fromkeys(tags))  # 保持原有顺序的去重方法
        
        print_debug(f"找到标签: {tags}")

        # 获取完整简介
        full_intro = None
        intro_element = soup.select_one('#link-report .intro')
        if intro_element:
            full_intro = to_simplified(intro_element.get_text(strip=True))
        else:
            # 尝试其他可能的简介位置
            intro_element = soup.select_one('.related_info .intro')
            if intro_element:
                full_intro = to_simplified(intro_element.get_text(strip=True))
        
        if full_intro:
            print_debug(f"找到完整简介: {full_intro[:50]}...")

            
        # 获取评分信息
        rating = None
        rating_element = soup.select_one('.rating_self strong.rating_num')
        if rating_element:
            rating = rating_element.get_text(strip=True)
            
        rating_people = None
        people_element = soup.select_one('.rating_sum .rating_people')
        if people_element:
            rating_people = people_element.get_text(strip=True).replace('人评价', '')
        
        print_debug(f"评分: {rating}, 评价人数: {rating_people}")

        detail_info = {
            "isbn": isbn,
            "pages": pages,
            "price": price,
            "binding": binding,
            "series": series,
            "publish_year": publish_year,
            "publisher": publisher,
            "authors": authors,
            "translators": translators,
            "tags": tags,
            "full_intro": full_intro,
            "rating": rating,
            "rating_people": rating_people
        }
        
        print_info(f"成功获取书籍详情: ISBN={isbn}, 出版社={publisher}, 出版年={publish_year}")
        return detail_info

    except Exception as e:
        print_error(f"获取详情页信息时出错: {e}")
        return None


# === 下载封面 ===
def download_cover(url, save_path):
    """下载豆瓣封面"""
    print_info(f"下载封面: {url}")
    try:
        res = safe_request(url)
        if not res:
            print_error("下载封面失败")
            return
            
        with open(save_path, "wb") as f:
            f.write(res.content)
        print_info(f"封面已保存到: {save_path}")
    except Exception as e:
        print_error(f"下载封面失败: {e}")


# === 生成 NFO 文件 ===
def generate_nfo(book_info, save_path):
    """创建 NFO 文件，XML格式"""
    if not book_info:
        print_warning("没有书籍信息，无法生成NFO文件")
        return
    
    print_info(f"生成NFO文件: {save_path}")
        
    def safe_xml(text):
        """确保文本安全用于XML"""
        if not text:
            return ""
        # 确保是简体字
        text = to_simplified(str(text))
        return escape(text)
        
    # 构建XML内容
    xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml_content += '<book>\n'
    
    # 添加基本信息
    xml_content += f'    <title>{safe_xml(book_info.get("title", ""))}</title>\n'
    xml_content += f'    <publish_date>{safe_xml(book_info.get("publish_year", ""))}</publish_date>\n'
    xml_content += f'    <year>{safe_xml(book_info.get("year", ""))}</year>\n'
    xml_content += f'    <isbn>{safe_xml(book_info.get("isbn", ""))}</isbn>\n'
    xml_content += f'    <language>中文</language>\n'
    
    # 添加标签
    if book_info.get("tags"):
        # 将所有标签用/连接成一个字符串
        tags_str = " / ".join(book_info["tags"])
        xml_content += f'    <tag>{safe_xml(tags_str)}</tag>\n'
            
    # 添加genre（使用第一个标签作为genre）
    if book_info.get("tags"):
        xml_content += f'    <genre>{safe_xml(book_info["tags"][0])}</genre>\n'
    else:
        xml_content += '    <genre></genre>\n'
    
    # 添加其他信息
    xml_content += f'    <publisher>{safe_xml(book_info.get("publisher", ""))}</publisher>\n'
    
    # 获取作者信息，优先使用authors字段
    artist = ""
    if book_info.get("authors") and len(book_info["authors"]) > 0:
        # 使用第一个作者
        artist = book_info["authors"][0]
        print_debug(f"使用详情页作者: {artist}")
    else:
        artist = book_info.get("author", "")
        print_debug(f"使用搜索结果作者: {artist}")
        
    # 清理作者名中的国籍标记
    if artist:
        original_artist = artist
        artist = re.sub(r'[\[（\(【〔][^\]）\)】〕]*[\]）\)】〕]', '', artist).strip()
        if artist != original_artist:
            print_debug(f"清理作者名中的国籍标记: '{original_artist}' -> '{artist}'")
        
    xml_content += f'    <artist>{safe_xml(artist)}</artist>\n'
    
    # 添加简介，优先使用完整简介
    intro = book_info.get("full_intro") or book_info.get("intro") or ""
    if intro:
        print_debug(f"使用简介: {intro[:50]}...")
    xml_content += f'    <introduction>{safe_xml(intro)}</introduction>\n'
    
    xml_content += '</book>'
    
    # 写入文件
    try:
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        print_info(f"NFO文件已保存: {save_path}")
    except Exception as e:
        print_error(f"保存NFO文件失败: {e}")


# === 文件重命名主逻辑 ===
def rename_books():
    """遍历目录，重命名书籍文件，并整理到独立文件夹"""
    # 确保books目录存在
    if not os.path.exists(BOOKS_DIR):
        os.makedirs(BOOKS_DIR)
        print_info(f"已创建书籍目录: {BOOKS_DIR}")
        return  # 如果是新创建的目录，里面没有文件，直接返回
    
    # 获取所有文件
    files = [f for f in os.listdir(BOOKS_DIR) if os.path.isfile(os.path.join(BOOKS_DIR, f))]
    print_info(f"找到 {len(files)} 个文件待处理")
        
    for filename in files:
        file_path = os.path.join(BOOKS_DIR, filename)
        print_info(f"\n开始处理文件: {filename}")
        
        # 解析文件名
        author, title, year, ext = parse_filename(filename)
        print_info(f"文件名解析结果: 作者='{author}', 标题='{title}', 年份='{year}', 格式='{ext}'")

        # 如果无法从文件名解析，尝试从元数据获取
        if not title or not author:
            print_info("尝试从文件元数据获取信息")
            if ext.lower() == "pdf":
                meta_author, meta_title = extract_pdf_metadata(file_path)
                if not author and meta_author: 
                    author = meta_author
                    print_info(f"从PDF元数据获取作者: {author}")
                if not title and meta_title: 
                    title = meta_title
                    print_info(f"从PDF元数据获取标题: {title}")
            elif ext.lower() in ["epub", "mobi", "azw3","azw"]:
                meta_author, meta_title = extract_ebook_metadata(file_path)
                if not author and meta_author: 
                    author = meta_author
                    print_info(f"从电子书元数据获取作者: {author}")
                if not title and meta_title: 
                    title = meta_title
                    print_info(f"从电子书元数据获取标题: {title}")
        
        # 从豆瓣获取信息
        douban_info = None
        if title:
            print_info(f"尝试从豆瓣获取信息: {title}")
            # 传递预期的作者信息
            douban_info = search_douban(title, expected_author=author)
            if douban_info:
                print_info(f"成功获取豆瓣信息: {douban_info['title']}")
                # 优先使用豆瓣的作者信息
                title = douban_info["title"]
                year = douban_info.get("year")
                
                # 优先使用豆瓣详情页的authors字段
                if douban_info.get("authors") and len(douban_info["authors"]) > 0:
                    author = douban_info["authors"][0]
                    print_info(f"使用豆瓣详情页作者: {author}")
                else:
                    author = douban_info["author"]
                    print_info(f"使用豆瓣搜索结果作者: {author}")
                
                # 清理作者名中的国籍标记
                if author:
                    original_author = author
                    # 移除如〔法〕、（美）等国籍标记
                    author = re.sub(r'[\[（\(【〔][^\]）\)】〕]*[\]）\)】〕]', '', author).strip()
                    # 移除可能的前导和尾部特殊字符
                    author = re.sub(r'^[^\u4e00-\u9fa5a-zA-Z0-9]+|[^\u4e00-\u9fa5a-zA-Z0-9]+$', '', author).strip()
                    if author != original_author:
                        print_info(f"清理作者名中的国籍标记: '{original_author}' -> '{author}'")

        # 如果标题或作者为空，请求用户输入
        if not title:
            title = input("⚠️ 未能获取到书籍标题，请手动输入: ").strip()
            print_info(f"用户输入标题: {title}")
        if not author:
            author = input("⚠️ 未能获取到作者信息，请手动输入: ").strip()
            print_info(f"用户输入作者: {author}")
            
        # 确保必要信息存在
        if not title or not author:
            print_error(f"无法处理文件 {filename}：缺少必要的标题或作者信息")
            continue

        # 根据是否有年份信息使用不同的命名模式
        if year:
            folder_name = NEW_NAME_PATTERN.format(author=author, title=title, year=year)
        else:
            folder_name = f"{author} - {title}"
        
        print_info(f"生成文件夹名: {folder_name}")
            
        folder_path = os.path.join(BOOKS_DIR, folder_name)
        new_book_path = os.path.join(folder_path, f"{title}.{ext}")

        # 显示将要执行的操作并等待用户确认
        print("\n" + colorama.Fore.CYAN + "=== 即将执行以下操作 ===" + colorama.Style.RESET_ALL)
        print(f"{colorama.Fore.WHITE}原文件: {colorama.Fore.YELLOW}{filename}{colorama.Style.RESET_ALL}")
        print(f"{colorama.Fore.WHITE}新文件夹: {colorama.Fore.GREEN}{folder_name}{colorama.Style.RESET_ALL}")
        print(f"{colorama.Fore.WHITE}新文件名: {colorama.Fore.GREEN}{title}.{ext}{colorama.Style.RESET_ALL}")
        if douban_info and douban_info.get("cover_url"):
            print(f"{colorama.Fore.WHITE}将下载豆瓣封面{colorama.Style.RESET_ALL}")
        print(f"{colorama.Fore.WHITE}将生成NFO文件{colorama.Style.RESET_ALL}")
        
        confirm = input(f"\n{colorama.Fore.YELLOW}是否继续？(输入 'no' 取消，其他任意键继续): {colorama.Style.RESET_ALL}").strip().lower()
        if confirm == 'no':
            print_info("用户取消操作")
            print(f"{colorama.Fore.RED}已取消操作{colorama.Style.RESET_ALL}")
            continue

        # 执行文件操作
        try:
            os.makedirs(folder_path, exist_ok=True)
            print_info(f"创建文件夹: {folder_path}")
            
            os.rename(file_path, new_book_path)
            print_info(f"重命名文件: {file_path} -> {new_book_path}")

            if douban_info and douban_info.get("cover_url"):
                cover_path = os.path.join(folder_path, f"{title}.jpg")
                download_cover(douban_info["cover_url"], cover_path)

            nfo_path = os.path.join(folder_path, f"{title}.nfo")
            generate_nfo(douban_info, nfo_path)
            print_info(f"生成NFO文件: {nfo_path}")
            
            print_info(f"文件处理完成: {title}")
            print(f"{colorama.Fore.GREEN}✅ 文件处理完成: {title}\n{colorama.Style.RESET_ALL}")
        except Exception as e:
            print_error(f"处理文件时出错: {e}")
            print(f"{colorama.Fore.RED}❌ 处理文件时出错: {e}{colorama.Style.RESET_ALL}")


# === 配置管理 ===
def save_config():
    """保存当前配置到文件"""
    config = {
        'proxy': REQUEST_CONFIG['proxy'],
        'request_delay': REQUEST_CONFIG['request_delay'],
        'retry_delay': REQUEST_CONFIG['retry_delay'],
        'timeout': REQUEST_CONFIG['timeout'],
        'max_retries': REQUEST_CONFIG['max_retries']
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        print_info(f"配置已保存到 {CONFIG_FILE}")
    except Exception as e:
        print_error(f"保存配置失败: {e}")

def load_config():
    """从文件加载配置"""
    if not os.path.exists(CONFIG_FILE):
        print_info("未找到配置文件")
        return False
        
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # 更新配置
        for key, value in config.items():
            if key in REQUEST_CONFIG:
                REQUEST_CONFIG[key] = value
                
        print_info(f"已加载配置: {CONFIG_FILE}")
        
        # 显示当前配置
        if REQUEST_CONFIG['proxy']:
            proxy_info = REQUEST_CONFIG['proxy'].get('http', 'None')
            print_info(f"  - 代理: {proxy_info}")
        print_info(f"  - 请求延迟: {REQUEST_CONFIG['request_delay'][0]}-{REQUEST_CONFIG['request_delay'][1]}秒")
        print_info(f"  - 超时: {REQUEST_CONFIG['timeout']}秒")
        print_info(f"  - 最大重试: {REQUEST_CONFIG['max_retries']}次")
        
        return True
    except Exception as e:
        print_error(f"加载配置失败: {e}")
        return False


if __name__ == "__main__":
    # 显示字符画和作者信息
    print(colorama.Fore.BLUE + ASCII_ART + colorama.Style.RESET_ALL)
    print(colorama.Fore.YELLOW + AUTHOR_INFO + colorama.Style.RESET_ALL)
    
    print_info("电子书文件整理工具启动")
    
    print(colorama.Fore.CYAN + "=" * 50 + colorama.Style.RESET_ALL)
    print(colorama.Fore.MAGENTA + "📚 电子书文件整理工具" + colorama.Style.RESET_ALL)
    print(colorama.Fore.CYAN + "=" * 50 + colorama.Style.RESET_ALL)
    print(colorama.Fore.WHITE + "功能：自动解析电子书文件名，整理到独立文件夹，并获取豆瓣信息" + colorama.Style.RESET_ALL)
    print(colorama.Fore.WHITE + f"书籍目录: {colorama.Fore.GREEN}{BOOKS_DIR}{colorama.Style.RESET_ALL}")
    print(colorama.Fore.WHITE + "支持格式: " + colorama.Fore.GREEN + ", ".join(SUPPORTED_FORMATS) + colorama.Style.RESET_ALL)
    print(colorama.Fore.CYAN + "=" * 50 + colorama.Style.RESET_ALL)
    
    # 加载配置
    has_config = load_config()
    
    # 配置网络设置
    print("\n" + colorama.Fore.CYAN + "=== 网络设置 ===" + colorama.Style.RESET_ALL)
    if has_config:
        use_saved = input(f"{colorama.Fore.YELLOW}检测到已保存的配置，是否使用? (y/n, 默认: y): {colorama.Style.RESET_ALL}").strip().lower() != 'n'
        if not use_saved:
            print_info("用户选择不使用已保存的配置")
            has_config = False
    
    if not has_config:
        print_info("开始配置网络设置")
        print(f"{colorama.Fore.WHITE}(可选) 配置代理和请求参数，避免IP封锁{colorama.Style.RESET_ALL}")
        
        use_proxy = input(f"{colorama.Fore.YELLOW}是否使用代理? (y/n, 默认: n): {colorama.Style.RESET_ALL}").strip().lower() == 'y'
        if use_proxy:
            proxy_host = input(f"{colorama.Fore.YELLOW}请输入代理地址 (例如: 127.0.0.1): {colorama.Style.RESET_ALL}").strip()
            proxy_port = input(f"{colorama.Fore.YELLOW}请输入代理端口 (例如: 7890): {colorama.Style.RESET_ALL}").strip()
            if proxy_host and proxy_port:
                proxy_url = f"http://{proxy_host}:{proxy_port}"
                REQUEST_CONFIG['proxy'] = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                print_info(f"设置代理: {proxy_url}")
                print(f"{colorama.Fore.GREEN}✅ 已设置代理: {proxy_url}{colorama.Style.RESET_ALL}")
        
        # 配置请求延迟
        custom_delay = input(f"{colorama.Fore.YELLOW}是否自定义请求延迟? (y/n, 默认: n): {colorama.Style.RESET_ALL}").strip().lower() == 'y'
        if custom_delay:
            try:
                min_delay = float(input(f"{colorama.Fore.YELLOW}最小延迟秒数 (默认: 1): {colorama.Style.RESET_ALL}").strip() or "1")
                max_delay = float(input(f"{colorama.Fore.YELLOW}最大延迟秒数 (默认: 3): {colorama.Style.RESET_ALL}").strip() or "3")
                if min_delay > 0 and max_delay >= min_delay:
                    REQUEST_CONFIG['request_delay'] = [min_delay, max_delay]
                    print_info(f"设置请求延迟: {min_delay}-{max_delay}秒")
                    print(f"{colorama.Fore.GREEN}✅ 已设置请求延迟: {min_delay}-{max_delay}秒{colorama.Style.RESET_ALL}")
            except ValueError:
                print_warning("输入无效，使用默认延迟设置")
                print(f"{colorama.Fore.RED}⚠️ 输入无效，使用默认延迟设置{colorama.Style.RESET_ALL}")
        
        # 保存配置
        save_config_choice = input(f"{colorama.Fore.YELLOW}是否保存当前配置? (y/n, 默认: y): {colorama.Style.RESET_ALL}").strip().lower() != 'n'
        if save_config_choice:
            save_config()
    
    print_info("开始处理书籍文件")
    print(f"\n{colorama.Fore.CYAN}开始处理书籍文件...{colorama.Style.RESET_ALL}")
    rename_books()
    
    print_info("处理完成")
    print(f"\n{colorama.Fore.GREEN}✅ 处理完成！{colorama.Style.RESET_ALL}")
    print(colorama.Fore.CYAN + "=" * 50 + colorama.Style.RESET_ALL)
