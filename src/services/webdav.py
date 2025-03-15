import os
from webdav3.client import Client
from src.config.config import WEBDAV_CONFIG
from src.utils.logger import print_info, print_error, print_debug

def init_webdav_client():
    """初始化WebDAV客户端
    Returns:
        Client对象或None
    """

        
    options = {
        'webdav_hostname': WEBDAV_CONFIG['hostname'],
        'webdav_login': WEBDAV_CONFIG['username'],
        'webdav_password': WEBDAV_CONFIG['password'],
        'disable_check': True
    }
    
    try:
        client = Client(options)
        # 测试连接
        client.check()
        print_info("WebDAV连接测试成功")
        return client
    except Exception as e:
        print_error(f"WebDAV连接失败: {e}")
        return None

def upload_to_webdav(local_folder, folder_name):
    """上传文件夹到WebDAV服务器
    Args:
        local_folder: 本地文件夹路径
        folder_name: 文件夹名称
    Returns:
        bool: 是否上传成功
    """

        
    client = init_webdav_client()
    if not client:
        return False
        
    try:
        # 构建远程路径
        remote_folder = os.path.join(WEBDAV_CONFIG['root_path'], folder_name).replace('\\', '/')
        
        print_info(f"开始上传到WebDAV: {remote_folder}")
        
        # 确保远程目录存在
        if not client.check(remote_folder):
            client.mkdir(remote_folder)
        
        # 上传文件夹中的所有文件
        for file in os.listdir(local_folder):
            local_file = os.path.join(local_folder, file)
            remote_file = f"{remote_folder}/{file}"
            
            if os.path.isfile(local_file):
                print_info(f"上传文件: {file}")
                client.upload_file(remote_file, local_file)
        
        print_info(f"文件夹上传完成: {folder_name}")
        return True
        
    except Exception as e:
        print_error(f"上传到WebDAV失败: {e}")
        return False

def clean_local_folder(folder_path):
    """清理本地文件夹
    Args:
        folder_path: 要清理的文件夹路径
    """
    try:
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
                print_debug(f"删除文件: {file}")
        os.rmdir(folder_path)
        print_info(f"清理本地文件夹: {folder_path}")
    except Exception as e:
        print_error(f"清理本地文件夹失败: {e}") 