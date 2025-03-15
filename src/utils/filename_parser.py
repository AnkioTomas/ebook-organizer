import re
import os
import PyPDF2
import ebookmeta
from src.utils.logger import print_debug, print_error
from src.utils.text_utils import to_simplified

def parse_filename(filename):
    """
    解析电子书文件名：
    - 书名：提取主要标题部分
    - 作者：从括号中提取可能的作者
    - 年份：括号内的四位数字
    
    Args:
        filename: 文件名
    Returns:
        (author, title, year, ext) 元组
    """
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
        # 转换为简体字
        title = to_simplified(title)
    
    if author:
        # 清理作者名中的特殊字符和国籍标记
        author = re.sub(r'\[[^\]]*\]|〔[^〕]*〕|\([^)]*\)|（[^）]*）|【[^】]*】', '', author).strip()
        # 转换为简体字
        author = to_simplified(author)
    
    return author, title, year, ext

def extract_pdf_metadata(pdf_path):
    """尝试从 PDF 文件元数据中提取书籍信息
    Args:
        pdf_path: PDF文件路径
    Returns:
        (author, title) 元组
    """
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

def extract_ebook_metadata(file_path):
    """尝试从 EPUB/MOBI/AWZ3 文件的元数据中提取书籍信息
    Args:
        file_path: 电子书文件路径
    Returns:
        (author, title) 元组
    """
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