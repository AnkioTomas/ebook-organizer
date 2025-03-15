import colorama

# 初始化colorama，支持Windows下的彩色输出
colorama.init(autoreset=True)

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

def print_success(msg):
    """打印成功信息（绿色）"""
    print(f"{colorama.Fore.GREEN}✅ {msg}{colorama.Style.RESET_ALL}")

def print_section(title):
    """打印分节标题（青色）"""
    print(f"\n{colorama.Fore.CYAN}=== {title} ==={colorama.Style.RESET_ALL}")

def print_divider():
    """打印分隔线（青色）"""
    print(f"{colorama.Fore.CYAN}{'=' * 50}{colorama.Style.RESET_ALL}")

def print_prompt(msg):
    """打印用户提示（黄色）"""
    return input(f"{colorama.Fore.YELLOW}{msg}: {colorama.Style.RESET_ALL}")

def print_highlight(msg):
    """打印高亮文本（白色）"""
    print(f"{colorama.Fore.WHITE}{msg}{colorama.Style.RESET_ALL}")

# ASCII艺术字体
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