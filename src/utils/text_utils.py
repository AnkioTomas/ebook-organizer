import opencc
import difflib
from xml.sax.saxutils import escape
import re

# 初始化繁体转简体转换器
converter = opencc.OpenCC('t2s')

def to_simplified(text):
    """将繁体字转换为简体字
    Args:
        text: 要转换的文本
    Returns:
        转换后的文本
    """
    if not text:
        return text
    return converter.convert(text)

def safe_xml(text):
    """确保文本安全用于XML
    Args:
        text: 要处理的文本
    Returns:
        处理后的文本
    """
    if not text:
        return ""
    # 确保是简体字
    text = to_simplified(str(text))
    return escape(text)

def sanitize_filename(filename):
    """清理文件名中Windows不支持的特殊字符
    Args:
        filename: 原始文件名
    Returns:
        清理后的文件名
    """
    if not filename:
        return ""
    
    # Windows不允许的字符: \ / : * ? " < > |
    invalid_chars = r'[\\/:*?"<>|]'
    # 替换为下划线
    sanitized = re.sub(invalid_chars, '', filename)
    
    # 处理其他可能导致问题的字符，如引号
    sanitized = sanitized.replace('"', "'")
    
    # 确保文件名不以点或空格结尾（Windows不允许）
    sanitized = sanitized.rstrip('. ')
    
    # 如果文件名为空，提供默认名称
    if not sanitized or sanitized.isspace():
        sanitized = "未命名"
        
    return sanitized

def calculate_title_similarity(title1, title2):
    """计算两个标题的相似度
    Args:
        title1: 第一个标题
        title2: 第二个标题
    Returns:
        相似度（0-1之间的浮点数）
    """
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