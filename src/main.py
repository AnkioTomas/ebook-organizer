import os
import re

import PyPDF2

from src.config.config import (
    BOOKS_DIR, PREFERENCES, WEBDAV_CONFIG, DEEPSEEK_CONFIG,
    REQUEST_CONFIG, load_config, save_config, generate_folder_name
)
from src.utils.logger import (
    print_info, print_error, print_warning, print_section,
    print_divider, print_prompt, print_success, ASCII_ART, AUTHOR_INFO
)
from src.utils.filename_parser import parse_filename, extract_pdf_metadata, extract_ebook_metadata
from src.services.douban import search_douban
from src.services.file_service import download_cover, generate_nfo, create_book_folder
from src.services.webdav import upload_to_webdav, clean_local_folder
from src.services.ai_service import ai_extract_title_author, ai_confirm_rename
from src.utils.text_utils import sanitize_filename

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
        file_content = None
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
                # 获取PDF内容预览用于AI分析
                try:
                    with open(file_path, 'rb') as f:
                        reader = PyPDF2.PdfReader(f)
                        if len(reader.pages) > 0:
                            file_content = reader.pages[0].extract_text()[:500]
                except:
                    pass
            elif ext.lower() in ["epub", "mobi", "azw3","azw"]:
                meta_author, meta_title = extract_ebook_metadata(file_path)
                if not author and meta_author: 
                    author = meta_author
                    print_info(f"从电子书元数据获取作者: {author}")
                if not title and meta_title: 
                    title = meta_title
                    print_info(f"从电子书元数据获取标题: {title}")
        
        # 如果仍然无法获取标题或作者，使用AI尝试提取
        if (not title or not author) and PREFERENCES.ai_enabled:
            ai_title, ai_author = ai_extract_title_author(filename, file_content)
            if not title and ai_title:
                title = ai_title
                print_info(f"AI提取标题: {title}")
            if not author and ai_author:
                author = ai_author
                print_info(f"AI提取作者: {author}")
        
        # 如果仍然无法获取，请求用户输入
        if not title:
            title = print_prompt("⚠️ 未能获取到书籍标题，请手动输入").strip()
            print_info(f"用户输入标题: {title}")

            
        # 确保必要信息存在
        if not title:
            print_error(f"无法处理文件 {filename}：缺少必要的标题")
            continue

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
                    author = re.sub(r'[\[（\(【〔][^\]）\)】〕]*[\]）\)】〕]', '', author).strip()
                    if author != original_author:
                        print_info(f"清理作者名中的国籍标记: '{original_author}' -> '{author}'")

            # 根据是否有年份信息使用不同的命名模式
        folder_name = generate_folder_name({
            'title': title,
            'author': author,
            'year': year,
        })

        # 使用AI判断是否确认重命名
        should_rename = True
        if PREFERENCES.ai_enabled and PREFERENCES.auto_confirm_rename:
            should_rename = ai_confirm_rename(filename, f"{folder_name}/{title}.{ext}", douban_info or {
                'title': title,
                'author': author,
                'year': year
            })
            if should_rename:
                print_info("AI确认进行重命名")
                # 显示操作信息但不要求确认
                print_section("执行以下操作")
                print_info(f"原文件: {filename}")
                print_info(f"新文件夹: {folder_name}")
                print_info(f"新文件名: {title}.{ext}")
                if douban_info and douban_info.get("cover_url"):
                    print_info("将下载豆瓣封面")
                print_info("将生成NFO文件")
            else:
                print_warning("AI不建议进行重命名，跳过此文件")
                continue
        else:
            # 显示将要执行的操作并等待用户确认
            print_section("即将执行以下操作")
            print_info(f"原文件: {filename}")
            print_info(f"新文件夹: {folder_name}")
            print_info(f"新文件名: {title}.{ext}")
            if douban_info and douban_info.get("cover_url"):
                print_info("将下载豆瓣封面")
            print_info("将生成NFO文件")
            
            confirm = print_prompt("是否继续？(输入 'no' 取消，其他任意键继续)").strip().lower()
            if confirm == 'no':
                print_info("用户取消操作")
                continue

        # 执行文件操作
        try:
            # 创建文件夹并移动文件
            folder_path, new_file_path = create_book_folder({
                'title': title,
                'author': author,
                'year': year
            }, file_path)
            
            if not folder_path or not new_file_path:
                continue

            # 获取安全的文件名（与create_book_folder中使用相同的处理方式）
            safe_title = sanitize_filename(title)

            if douban_info and douban_info.get("cover_url"):
                cover_path = os.path.join(folder_path, f"{safe_title}.jpg")
                download_cover(douban_info["cover_url"], cover_path)

            nfo_path = os.path.join(folder_path, f"{safe_title}.nfo")
            generate_nfo(douban_info, nfo_path)
            
            print_success(f"文件处理完成: {title}")

            # 上传到WebDAV
            if PREFERENCES.webdav_enabled and PREFERENCES.auto_upload_webdav:
                print_info("开始上传到WebDAV")
                upload_success = upload_to_webdav(folder_path, os.path.basename(folder_path))
                if upload_success:
                    print_success("上传成功")
                    # 根据用户偏好决定是否清理本地文件
                    if PREFERENCES.auto_clean_local:
                        print_info("根据用户偏好，清理本地文件")
                        clean_local_folder(folder_path)
                        print_success("本地文件已清理")

                else:
                    print_error("WebDAV上传失败，保留本地文件")
        except Exception as e:
            print_error(f"处理文件时出错: {e}")

def main():
    """主程序入口"""
    # 显示字符画和作者信息
    print(ASCII_ART)
    print(AUTHOR_INFO)
    
    print_info("电子书文件整理工具启动")
    
    print_divider()
    print_section("电子书文件整理工具")
    print_divider()
    print_info("功能：自动解析电子书文件名，整理到独立文件夹，并获取豆瓣信息")
    print_info(f"书籍目录: {BOOKS_DIR}")
    print_info("支持格式: pdf, epub, mobi, txt, azw3, azw")
    print_divider()
    
    # 加载配置
    has_config = load_config()
    
    # 配置网络设置
    print_section("网络设置")
    if has_config:
        use_saved = print_prompt("检测到已保存的配置，是否使用? (y/n, 默认: y)").strip().lower() != 'n'
        if not use_saved:
            print_info("用户选择不使用已保存的配置")
            has_config = False
    
    if not has_config:
        print_info("开始配置网络设置")
        print_info("(可选) 配置代理和请求参数，避免IP封锁")
        
        use_proxy = print_prompt("是否使用代理? (y/n, 默认: n)").strip().lower() == 'y'
        if use_proxy:
            proxy_host = print_prompt("请输入代理地址 (例如: 127.0.0.1)").strip()
            proxy_port = print_prompt("请输入代理端口 (例如: 7890)").strip()
            if proxy_host and proxy_port:
                proxy_url = f"http://{proxy_host}:{proxy_port}"
                REQUEST_CONFIG['proxy'] = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                print_success(f"已设置代理: {proxy_url}")
        
        # 配置请求延迟
        custom_delay = print_prompt("是否自定义请求延迟? (y/n, 默认: n)").strip().lower() == 'y'
        if custom_delay:
            try:
                min_delay = float(print_prompt("最小延迟秒数 (默认: 1)").strip() or "1")
                max_delay = float(print_prompt("最大延迟秒数 (默认: 3)").strip() or "3")
                if min_delay > 0 and max_delay >= min_delay:
                    REQUEST_CONFIG['request_delay'] = [min_delay, max_delay]
                    print_success(f"已设置请求延迟: {min_delay}-{max_delay}秒")
            except ValueError:
                print_warning("输入无效，使用默认延迟设置")
        
        # 配置WebDAV
        print_section("WebDAV设置")
        use_webdav = print_prompt("是否启用WebDAV? (y/n, 默认: n)").strip().lower() == 'y'
        if use_webdav:
            PREFERENCES.webdav_enabled = True
            WEBDAV_CONFIG['hostname'] = print_prompt("请输入WebDAV服务器地址").strip()
            WEBDAV_CONFIG['username'] = print_prompt("请输入用户名").strip()
            WEBDAV_CONFIG['password'] = print_prompt("请输入密码").strip()
            WEBDAV_CONFIG['root_path'] = print_prompt("请输入远程根目录 (默认: /books)").strip() or '/books'
            
            # 测试WebDAV连接
            from src.services.webdav import init_webdav_client
            if init_webdav_client():
                print_success("WebDAV连接测试成功")
            else:
                print_error("WebDAV连接测试失败")
                PREFERENCES.webdav_enabled= False
        
        # 配置DeepSeek API
        print_section("DeepSeek API设置")
        print_info("配置DeepSeek API，用于智能选择最佳匹配")
        
        use_deepseek = print_prompt("是否启用DeepSeek AI? (y/n, 默认: n)").strip().lower() == 'y'
        if use_deepseek:
            PREFERENCES.ai_enabled = True
            DEEPSEEK_CONFIG['api_key'] = print_prompt("请输入DeepSeek API密钥").strip()
            custom_url = print_prompt("是否自定义API地址? (y/n, 默认: n)").strip().lower() == 'y'
            if custom_url:
                DEEPSEEK_CONFIG['api_url'] = print_prompt("请输入API地址").strip()
            
            # 测试DeepSeek API
            from src.services.ai_service import call_deepseek_api
            test_response = call_deepseek_api("测试连接")
            if test_response is not None:
                print_success("DeepSeek API连接测试成功")
                
                # 配置自动处理选项
                print_section("自动处理设置")
                PREFERENCES.auto_select_best_match = True
                PREFERENCES.auto_confirm_rename = print_prompt("是否自动确认重命名? (y/n, 默认: y)").strip().lower() != 'n'
                
                if PREFERENCES.webdav_enabled:
                    PREFERENCES.auto_upload_webdav = print_prompt("是否自动上传到WebDAV? (y/n, 默认: y)").strip().lower() != 'n'
                    if PREFERENCES.auto_upload_webdav:
                        PREFERENCES.auto_clean_local = print_prompt("是否自动清理本地文件? (y/n, 默认: n)").strip().lower() == 'y'
                
                print_section("AI选择阈值设置")
                try:
                    PREFERENCES.min_similarity_threshold = float(print_prompt("最小标题相似度阈值 (0-1, 默认: 0.6)").strip() or "0.6")
                    PREFERENCES.min_rating_threshold = float(print_prompt("最小评分阈值 (0-10, 默认: 7.0)").strip() or "7.0")
                    PREFERENCES.min_rating_people = int(print_prompt("最小评价人数阈值 (默认: 100)").strip() or "100")
                except ValueError:
                    print_warning("输入无效，使用默认阈值设置")
            else:
                print_error("DeepSeek API连接测试失败")
                PREFERENCES.ai_enabled = False
        
        # 保存配置
        save_config_choice = print_prompt("是否保存当前配置? (y/n, 默认: y)").strip().lower() != 'n'
        if save_config_choice:
            if save_config():
                print_success("配置已保存")
            else:
                print_error("保存配置失败")
    
    print_info("开始处理书籍文件")
    rename_books()
    
    print_success("处理完成！")
    print_divider()

if __name__ == "__main__":
    main() 