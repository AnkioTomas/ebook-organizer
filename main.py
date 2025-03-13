import json
import os
import re
from xml.sax.saxutils import escape

import PyPDF2
import ebookmeta  # 处理 EPUB/MOBI/AWZ3 格式的元数据
import requests
from bs4 import BeautifulSoup
from lxml import etree

# === 目录 & 配置 ===
BOOKS_DIR = "./books"  # 书籍目录
NEW_NAME_PATTERN = "{author} - {title} ({year})"  # 文件夹命名格式
DOUBAN_SEARCH_URL = "https://www.douban.com/search"
DEFAULT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Encoding': 'gzip, deflate',
    'Referer': "https://book.douban.com/"
}
SUPPORTED_FORMATS = ['pdf', 'epub', 'mobi', 'txt', 'awz3']


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
        if re.search(r'〔[^〕]+〕', possible_author):
            # 提取国籍标记后的实际作者名
            author_parts = re.search(r'〔[^〕]+〕(.*)', possible_author)
            if author_parts:
                author = author_parts.group(1).strip()
            else:
                author = possible_author
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
        # 清理作者名中的特殊字符
        author = re.sub(r'\[[^\]]*\]|〔[^〕]*〕', '', author).strip()
    
    # 最后一步：确保标题和作者没有前导和尾部的特殊字符
    if title:
        title = re.sub(r'^[^\u4e00-\u9fa5a-zA-Z0-9]+|[^\u4e00-\u9fa5a-zA-Z0-9]+$', '', title).strip()
    if author:
        author = re.sub(r'^[^\u4e00-\u9fa5a-zA-Z0-9]+|[^\u4e00-\u9fa5a-zA-Z0-9]+$', '', author).strip()
    
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
            return author, title
    except Exception as e:
        print(f"⚠️ 无法读取 PDF 元数据: {e}")
        return None, None


# === 解析 EPUB/MOBI/AWZ3 文件元数据 ===
def extract_ebook_metadata(file_path):
    """尝试从 EPUB/MOBI/AWZ3 文件的元数据中提取书籍信息"""
    try:
        metadata = ebookmeta.get_metadata(file_path)
        return metadata.get("author"), metadata.get("title")
    except Exception as e:
        print(f"⚠️ 无法读取电子书元数据: {e}")
        return None, None


# === 从豆瓣获取书籍信息 ===
def search_douban(query, expected_author=None, fetch_detail=True):
    """在豆瓣搜索书籍，返回第一个匹配的书籍信息（确保作者匹配）
    Args:
        query: 搜索关键词
        expected_author: 期望的作者名（可选）
        fetch_detail: 是否获取详情页信息（可选，默认True）
    """
    params = {"cat": "1001", "q": query}
    res = requests.get(DOUBAN_SEARCH_URL, params=params, headers=DEFAULT_HEADERS)

    if res.status_code != 200:
        print(f"❌ 豆瓣搜索失败: {res.status_code}")
        return None

    soup = BeautifulSoup(res.content, 'html.parser')
    results = soup.select('.result-list .result')
    
    for result in results:
        try:
            # 获取标题和链接
            title_elem = result.select_one('.title h3 a')
            if not title_elem:
                continue
            
            title = title_elem.get_text(strip=True).replace(' ', '')
            book_url = title_elem.get('href', '')
            
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
                continue
                
            # 构建真实的豆瓣图书URL
            real_book_url = f'https://book.douban.com/subject/{subject_id}/'
            
            # 获取评分信息
            rating_info = result.select_one('.rating-info')
            if not rating_info:
                continue
                
            # 获取出版信息
            subject_info = rating_info.select_one('.subject-cast').get_text(strip=True)
            parts = subject_info.split('/')
            parts = [p.strip() for p in parts]
            
            # 解析作者、出版社、年份
            author = parts[0]
            publisher = parts[-2] if len(parts) > 2 else None
            
            # 尝试从出版信息中提取年份
            year = None
            for part in parts:
                if part.strip().isdigit() and len(part.strip()) == 4:
                    year = part.strip()
                    break
            
            # 获取封面图片URL
            cover_elem = result.select_one('.pic img')
            cover_url = cover_elem.get('src') if cover_elem else None
            
            # 获取评分和评价人数
            rating = rating_info.select_one('.rating_nums')
            rating = rating.get_text(strip=True) if rating else None
            
            rating_people = rating_info.select_one('.rating_nums + span')
            rating_people = rating_people.get_text(strip=True).strip('(人评价)') if rating_people else None
            
            # 获取简介
            intro = result.select_one('.content p')
            intro = intro.get_text(strip=True) if intro else None

            # 如果指定了期望作者且不匹配，则继续查找
            if expected_author and expected_author.lower() not in author.lower():
                continue

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
                "douban_id": subject_id
            }

            # 获取详情页信息（ISBN等）
            if fetch_detail and real_book_url:
                detail_info = fetch_douban_book_info(real_book_url)
                if detail_info:
                    book_info.update(detail_info)
            
            return book_info

        except Exception as e:
            print(f"解析搜索结果时出错: {e}")
            continue
            
    return None


# === 解析豆瓣书籍详情页 ===
def fetch_douban_book_info(book_url):
    """解析豆瓣书籍详情页，返回补充信息"""
    try:
        res = requests.get(book_url, headers=DEFAULT_HEADERS)
        if res.status_code != 200:
            return None

        soup = BeautifulSoup(res.content, 'html.parser')
        
        # 获取图书信息区域
        info = soup.select_one('#info')
        if not info:
            return None
            
        # 获取所有文本行
        info_text = info.get_text()

        # 解析详细信息
        def extract_field(field):
            pattern = f'{field}:\\s*([^\\n]+)'
            match = re.search(pattern, info_text)
            return match.group(1).strip() if match else None
            
        # 获取各种信息
        isbn = extract_field( 'ISBN')
        pages = extract_field( '页数')
        price = extract_field( '定价')
        binding = extract_field( '装帧')
        series = extract_field( '丛书')
        publish_year = extract_field( '出版年')
        publisher = extract_field( '出版社')
        
        # 获取作者（可能有多个）
        authors = []
        author_links = info.select('a[href^="/author/"]')
        if author_links:
            authors = [a.get_text(strip=True) for a in author_links]
            
        # 获取译者（如果有）
        translators = []
        translator_text = extract_field( '译者')
        if translator_text:
            translators = [t.strip() for t in translator_text.split(',')]

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
                    tags = [part.split(':')[1] for part in tag_parts]
                break

        # 如果从JS中没有找到标签，尝试从页面中提取
        if not tags:
            tag_elements = soup.select('a.tag')
            if tag_elements:
                tags = [tag.get_text(strip=True) for tag in tag_elements]

        # 获取完整简介
        full_intro = None
        intro_element = soup.select_one('#link-report .intro')
        if intro_element:
            full_intro = intro_element.get_text(strip=True)
        else:
            # 尝试其他可能的简介位置
            intro_element = soup.select_one('.related_info .intro')
            if intro_element:
                full_intro = intro_element.get_text(strip=True)

            
        # 获取评分信息
        rating = None
        rating_element = soup.select_one('.rating_self strong.rating_num')
        if rating_element:
            rating = rating_element.get_text(strip=True)
            
        rating_people = None
        people_element = soup.select_one('.rating_sum .rating_people')
        if people_element:
            rating_people = people_element.get_text(strip=True).replace('人评价', '')

        return {
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

    except Exception as e:
        print(f"获取详情页信息时出错: {e}")
        return None


# === 下载封面 ===
def download_cover(url, save_path):
    """下载豆瓣封面"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Referer': 'https://book.douban.com/'
        }
        res = requests.get(url, headers=headers)
        with open(save_path, "wb") as f:
            f.write(res.content)
    except Exception as e:
        print(f"❌ 下载封面失败: {e}")


# === 生成 NFO 文件 ===
def generate_nfo(book_info, save_path):
    """创建 NFO 文件，XML格式"""
    if not book_info:
        return
        
    def safe_xml(text):
        """确保文本安全用于XML"""
        if not text:
            return ""
        return escape(str(text))
        
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
    xml_content += f'    <artist>{safe_xml(book_info.get("author", ""))}</artist>\n'
    
    # 添加简介，优先使用完整简介
    intro = book_info.get("full_intro") or book_info.get("intro") or ""
    xml_content += f'    <introduction>{safe_xml(intro)}</introduction>\n'
    
    xml_content += '</book>'
    
    # 写入文件
    with open(save_path, "w", encoding="utf-8") as f:
        f.write(xml_content)


# === 文件重命名主逻辑 ===
def rename_books():
    """遍历目录，重命名书籍文件，并整理到独立文件夹"""
    # 确保books目录存在
    if not os.path.exists(BOOKS_DIR):
        os.makedirs(BOOKS_DIR)
        print(f"✅ 已创建书籍目录: {BOOKS_DIR}")
        return  # 如果是新创建的目录，里面没有文件，直接返回
        
    for filename in os.listdir(BOOKS_DIR):
        file_path = os.path.join(BOOKS_DIR, filename)
        if not os.path.isfile(file_path):
            continue

        author, title, year, ext = parse_filename(filename)

        if not title or not author:
            if ext.lower() == "pdf":
                meta_author, meta_title = extract_pdf_metadata(file_path)
                if meta_author: author = meta_author
                if meta_title: title = meta_title
            elif ext.lower() in ["epub", "mobi", "awz3"]:
                meta_author, meta_title = extract_ebook_metadata(file_path)
                if meta_author: author = meta_author
                if meta_title: title = meta_title
        douban_info = None
        if not title or not year:
            douban_info = search_douban(title, author)
            if douban_info:
                author, title, year = douban_info["author"], douban_info["title"], douban_info["year"]

        # 如果标题或作者为空，请求用户输入
        if not title:
            title = input("⚠️ 未能获取到书籍标题，请手动输入: ").strip()
        if not author:
            author = input("⚠️ 未能获取到作者信息，请手动输入: ").strip()
            
        # 确保必要信息存在
        if not title or not author:
            print(f"❌ 无法处理文件 {filename}：缺少必要的标题或作者信息")
            continue

        # 根据是否有年份信息使用不同的命名模式
        if year:
            folder_name = NEW_NAME_PATTERN.format(author=author, title=title, year=year)
        else:
            folder_name = f"{author} - {title}"
            
        folder_path = os.path.join(BOOKS_DIR, folder_name)
        new_book_path = os.path.join(folder_path, f"{title}.{ext}")

        # 显示将要执行的操作并等待用户确认
        print("\n=== 即将执行以下操作 ===")
        print(f"原文件: {filename}")
        print(f"新文件夹: {folder_name}")
        print(f"新文件名: {title}.{ext}")
        if douban_info and douban_info.get("cover_url"):
            print("将下载豆瓣封面")
        print("将生成NFO文件")
        
        confirm = input("\n是否继续？(输入 'no' 取消，其他任意键继续): ").strip().lower()
        if confirm == 'no':
            print("已取消操作")
            continue

        # 执行文件操作
        os.makedirs(folder_path, exist_ok=True)
        os.rename(file_path, new_book_path)

        if douban_info and douban_info.get("cover_url"):
            cover_path = os.path.join(folder_path, f"{title}.jpg")
            download_cover(douban_info["cover_url"], cover_path)

        nfo_path = os.path.join(folder_path, f"{title}.nfo")
        generate_nfo(douban_info, nfo_path)
        print(f"✅ 文件处理完成: {title}\n")


if __name__ == "__main__":
    print("=" * 50)
    print("📚 电子书文件整理工具")
    print("=" * 50)
    print("功能：自动解析电子书文件名，整理到独立文件夹，并获取豆瓣信息")
    print(f"书籍目录: {BOOKS_DIR}")
    print("支持格式: " + ", ".join(SUPPORTED_FORMATS))
    print("=" * 50)
    
    rename_books()
    
    print("\n✅ 处理完成！")
    print("=" * 50)
