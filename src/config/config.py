import json
import os

class Preferences:
    """用户偏好设置类"""
    def __init__(self):
        # AI相关设置
        self.ai_enabled = False  # 是否启用AI
        self.auto_select_best_match = False  # 是否自动选择最佳匹配
        self.auto_confirm_rename = False  # 是否自动确认重命名
        
        # WebDAV相关设置
        self.webdav_enabled = False  # 是否启用WebDAV
        self.auto_upload_webdav = False  # 是否自动上传到WebDAV
        self.auto_clean_local = False  # 是否自动清理本地文件
        
        # AI选择阈值
        self.min_similarity_threshold = 0.6  # 最小标题相似度阈值
        self.min_rating_threshold = 7.0  # 最小评分阈值
        self.min_rating_people = 100  # 最小评价人数阈值
    
    def save_to_json(self):
        """将设置保存为JSON格式"""
        return {
            'ai_enabled': self.ai_enabled,
            'auto_select_best_match': self.auto_select_best_match,
            'auto_confirm_rename': self.auto_confirm_rename,
            'webdav_enabled': self.webdav_enabled,
            'auto_upload_webdav': self.auto_upload_webdav,
            'auto_clean_local': self.auto_clean_local,
            'min_similarity_threshold': self.min_similarity_threshold,
            'min_rating_threshold': self.min_rating_threshold,
            'min_rating_people': self.min_rating_people
        }
    
    def load_from_json(self, data):
        """从JSON加载设置"""
        if not data:
            return
        self.ai_enabled = data.get('ai_enabled', False)
        self.auto_select_best_match = data.get('auto_select_best_match', False)
        self.auto_confirm_rename = data.get('auto_confirm_rename', False)
        self.webdav_enabled = data.get('webdav_enabled', False)
        self.auto_upload_webdav = data.get('auto_upload_webdav', False)
        self.auto_clean_local = data.get('auto_clean_local', False)
        self.min_similarity_threshold = data.get('min_similarity_threshold', 0.6)
        self.min_rating_threshold = data.get('min_rating_threshold', 7.0)
        self.min_rating_people = data.get('min_rating_people', 100)

# 获取项目根目录的绝对路径
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# 基础配置
BOOKS_DIR = os.path.join(ROOT_DIR, "books")  # 书籍目录
CONFIG_FILE = os.path.join(ROOT_DIR, "douban_config.json")  # 配置文件
NEW_NAME_PATTERN = "{author} - {title} ({year})"  # 文件夹命名格式
SUPPORTED_FORMATS = ['pdf', 'epub', 'mobi', 'txt', 'azw3', 'azw']

# 网络请求配置
REQUEST_CONFIG = {
    'timeout': 10,  # 请求超时时间（秒）
    'max_retries': 3,  # 最大重试次数
    'retry_delay': [2, 5],  # 重试延迟范围（秒）
    'request_delay': [1, 3],  # 请求间隔范围（秒）
    'proxy': None  # 代理设置
}

# WebDAV配置
WEBDAV_CONFIG = {
    'hostname': '',    # WebDAV服务器地址
    'username': '',    # 用户名
    'password': '',    # 密码
    'root_path': '/books'  # 远程根目录
}

# DeepSeek API配置
DEEPSEEK_CONFIG = {
    'api_key': '',  # DeepSeek API密钥
    'api_url': 'https://api.deepseek.com/v1/chat/completions'  # DeepSeek API地址
}

# 创建全局偏好设置实例
PREFERENCES = Preferences()

def save_config():
    """保存当前配置到文件"""
    config = {
        'proxy': REQUEST_CONFIG['proxy'],
        'request_delay': REQUEST_CONFIG['request_delay'],
        'retry_delay': REQUEST_CONFIG['retry_delay'],
        'timeout': REQUEST_CONFIG['timeout'],
        'max_retries': REQUEST_CONFIG['max_retries'],
        'webdav': WEBDAV_CONFIG,
        'deepseek': {
            'api_key': DEEPSEEK_CONFIG['api_key'],
            'api_url': DEEPSEEK_CONFIG['api_url']
        },
        'preferences': PREFERENCES.save_to_json()
    }
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def load_config():
    """从文件加载配置"""
    if not os.path.exists(CONFIG_FILE):
        return False
        
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # 更新配置
        for key, value in config.items():
            if key in REQUEST_CONFIG:
                REQUEST_CONFIG[key] = value
            elif key == 'webdav':
                # 兼容旧版本配置，忽略 enabled 字段
                webdav_config = value.copy()
                if 'enabled' in webdav_config:
                    del webdav_config['enabled']
                WEBDAV_CONFIG.update(webdav_config)
            elif key == 'deepseek':
                # 兼容旧版本配置，忽略 enabled 字段
                deepseek_config = value.copy()
                if 'enabled' in deepseek_config:
                    del deepseek_config['enabled']
                DEEPSEEK_CONFIG.update(deepseek_config)
            elif key == 'preferences':
                PREFERENCES.load_from_json(value)
                
        return True
    except Exception:
        return False

def generate_folder_name(book_info):
    """根据书籍信息生成标准化的文件夹名称
    Args:
        book_info: 包含 title、author、year(可选) 的字典
    Returns:
        str: 生成的文件夹名称
    """
    title = book_info["title"]
    author = book_info["author"]
    year = book_info.get("year")
    
    if year:
        return NEW_NAME_PATTERN.format(author=author, title=title, year=year)
    return f"{author} - {title}" 