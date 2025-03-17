import os
from xml.sax.saxutils import escape
from src.utils.logger import print_info, print_error, print_debug, print_warning
from src.utils.text_utils import safe_xml
from src.utils.network import safe_request
from src.config.config import BOOKS_DIR, NEW_NAME_PATTERN, generate_folder_name
import re

def download_cover(url, save_path):
    """下载豆瓣封面
    Args:
        url: 封面图片URL
        save_path: 保存路径
    """
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

def generate_nfo(book_info, save_path):
    """创建 NFO 文件，XML格式
    Args:
        book_info: 书籍信息字典
        save_path: 保存路径
    """
    if not book_info:
        print_warning("没有书籍信息，无法生成NFO文件")
        return
    
    print_info(f"生成NFO文件: {save_path}")
        
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

def create_book_folder(book_info, original_file_path):
    """创建书籍文件夹并移动文件
    Args:
        book_info: 书籍信息字典
        original_file_path: 原始文件路径
    Returns:
        (folder_path, new_file_path) 元组
    """
    from src.utils.text_utils import sanitize_filename
    
    # 获取必要信息
    title = book_info["title"]
    ext = os.path.splitext(original_file_path)[1].lstrip(".")
    
    # 生成文件夹名
    folder_name = generate_folder_name(book_info)
    print_info(f"生成文件夹名: {folder_name}")
    
    # 创建文件夹
    folder_path = os.path.join(BOOKS_DIR, folder_name)
    
    # 清理文件名
    safe_title = sanitize_filename(title)
    new_file_path = os.path.join(folder_path, f"{safe_title}.{ext}")
    
    try:
        os.makedirs(folder_path, exist_ok=True)
        print_info(f"创建文件夹: {folder_path}")
        
        os.rename(original_file_path, new_file_path)
        print_info(f"重命名文件: {original_file_path} -> {new_file_path}")
        
        return folder_path, new_file_path
    except Exception as e:
        print_error(f"创建文件夹或移动文件失败: {e}")
        return None, None 