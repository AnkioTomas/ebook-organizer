import json
import re
import os

import requests
from src.config.config import DEEPSEEK_CONFIG, PREFERENCES
from src.utils.logger import print_error, print_info, print_debug

def call_deepseek_api(prompt, context=None):
    """调用DeepSeek API进行智能决策
    Args:
        prompt: 提示词
        context: 上下文信息（可选）
    Returns:
        API响应结果
    """
    if not DEEPSEEK_CONFIG['api_key']:
        print_error("DeepSeek API key未配置")
        return None
        
    headers = {
        'Authorization': f"Bearer {DEEPSEEK_CONFIG['api_key']}",
        'Content-Type': 'application/json'
    }
    
    messages = []
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": prompt})
    
    data = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 1000  # 限制响应长度
    }
    
    try:
        response = requests.post(
            DEEPSEEK_CONFIG['api_url'],
            headers=headers,
            json=data,
            timeout=30
        )
        
        response.raise_for_status()  # 抛出非200状态码的异常
        
        result = response.json()
        if not result.get('choices') or not result['choices'][0].get('message'):
            print_error("DeepSeek API返回格式异常")
            return None
            
        content = result['choices'][0]['message']['content'].strip()
        print_debug(f"DeepSeek API响应: {content[:200]}...")  # 打印响应预览
        return content
        
    except requests.exceptions.Timeout:
        print_error("DeepSeek API请求超时")
    except requests.exceptions.RequestException as e:
        print_error(f"DeepSeek API请求失败: {str(e)}")
    except json.JSONDecodeError:
        print_error("DeepSeek API返回非JSON格式数据")
    except Exception as e:
        print_error(f"调用DeepSeek API时出错: {str(e)}")
    return None

def extract_json_from_response(response):
    """从AI响应中提取JSON内容
    Args:
        response: AI响应文本
    Returns:
        dict: 解析后的JSON对象，如果解析失败返回None
    """
    try:
        # 首先尝试直接解析整个响应
        return json.loads(response)
    except json.JSONDecodeError:
        try:
            # 尝试提取markdown代码块中的JSON
            code_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', response, re.DOTALL)
            if code_block_match:
                return json.loads(code_block_match.group(1))
            
            # 尝试提取普通JSON对象
            json_match = re.search(r'\{[^{]*\}', response)
            if json_match:
                return json.loads(json_match.group(0))
                
        except (json.JSONDecodeError, AttributeError):
            pass
    return None

def ai_select_best_match(matches):
    """使用DeepSeek AI选择最佳匹配结果
    Args:
        matches: 匹配结果列表
    Returns:
        最佳匹配结果
    """
    if not matches:
        return None

    print_debug("开始AI选择最佳匹配...")
    
    # 构建提示词
    prompt = "请帮我从以下搜索结果中选择最佳匹配。我会提供每个结果的详细信息，请基于以下标准做出选择：\n"
    prompt += "1. 标题相似度（越高越好）\n"
    prompt += "2. 豆瓣评分（越高越好）\n"
    prompt += "3. 评价人数（越多越好）\n"
    prompt += "4. 出版信息的完整性\n\n"
    
    for i, match in enumerate(matches, 1):
        prompt += f"选项 {i}:\n"
        prompt += f"- 标题: {match['title']}\n"
        prompt += f"- 作者: {match['author']}\n"
        prompt += f"- 出版社: {match.get('publisher', '未知')}\n"
        prompt += f"- 出版年: {match.get('year', '未知')}\n"
        prompt += f"- 评分: {match.get('rating', '未知')} ({match.get('rating_people', '0')}人评价)\n"
        prompt += f"- 标题相似度: {match['similarity']:.2f}\n"
        if match.get('intro'):
            prompt += f"- 简介: {match['intro'][:100]}...\n"
        prompt += "\n"
    
    prompt += "请选择最佳匹配的选项编号，并简要解释选择原因。"
    
    print_debug(f"发送选择请求，共 {len(matches)} 个选项...")
    
    # 调用DeepSeek API
    response = call_deepseek_api(prompt)
    if not response:
        print_debug("AI响应失败，使用默认选择逻辑")
        return default_select_best_match(matches)
    
    print_debug(f"AI响应内容: {response}")
    
    # 解析响应，提取选择的编号
    try:
        # 使用正则表达式匹配选项编号
        choice_match = re.search(r'选项\s*(\d+)', response)
        if choice_match:
            choice = int(choice_match.group(1)) - 1
            if 0 <= choice < len(matches):
                selected = matches[choice]
                print_debug(f"AI成功选择选项 {choice + 1}")
                print_info(f"DeepSeek选择: '{selected['title']}' (原因: {response})")
                return selected
            else:
                print_debug(f"AI选择的选项 {choice + 1} 超出范围")
        else:
            print_debug("未能从AI响应中提取选项编号")
    except Exception as e:
        print_error(f"解析DeepSeek响应时出错: {e}")
    
    print_debug("使用默认选择逻辑作为后备方案")
    return default_select_best_match(matches)

def default_select_best_match(matches):
    """默认的最佳匹配选择逻辑
    Args:
        matches: 匹配结果列表
    Returns:
        最佳匹配结果
    """
    print_debug("开始默认选择逻辑...")
    
    # 按评分和评价人数筛选
    qualified_matches = []
    for match in matches:
        try:
            rating = float(match['rating']) if match.get('rating') else 0
            rating_people = int(match['rating_people'].replace(',', '')) if match.get('rating_people') else 0
            
            if (rating >= PREFERENCES.min_rating_threshold and 
                rating_people >= PREFERENCES.min_rating_people):
                qualified_matches.append(match)
                print_debug(f"合格匹配: {match['title']} (评分: {rating}, 评价人数: {rating_people})")
        except (ValueError, AttributeError) as e:
            print_debug(f"解析评分信息失败: {str(e)}")
            continue
    
    if not qualified_matches:
        print_debug("没有满足评分条件的匹配，返回相似度最高的结果")
        best_match = matches[0]
    else:
        print_debug(f"从 {len(qualified_matches)} 个合格匹配中选择相似度最高的")
        best_match = max(qualified_matches, key=lambda x: x['similarity'])
    
    print_info(f"默认选择: '{best_match['title']}' (评分: {best_match.get('rating', 'N/A')}, 评价人数: {best_match.get('rating_people', 'N/A')})")
    return best_match

def ai_extract_title_author(filename, file_content=None):
    """使用AI从文件名和内容中提取标题和作者
    Args:
        filename: 文件名
        file_content: 文件内容预览（可选）
    Returns:
        (title, author) 元组
    """
    # 从文件名中提取基本信息
    base_name = os.path.splitext(filename)[0]
    
    # 如果文件名中包含作者信息（通过分隔符判断）
    separators = [' - ', ' – ', '_', '：', ':', '  ']
    for sep in separators:
        if sep in base_name:
            parts = base_name.split(sep, 1)
            if len(parts) == 2:
                author, title = parts
                return title.strip(), author.strip()
            
    # 如果没有找到分隔符，直接返回文件名作为标题
    return base_name, ""

def ai_confirm_rename(old_name, new_name, book_info):
    """使用AI判断是否确认重命名
    Args:
        old_name: 原文件名
        new_name: 新文件名
        book_info: 书籍信息
    Returns:
        bool: 是否确认重命名
    """
    print_debug(f"开始确认重命名: {old_name} -> {new_name}")
    
    prompt = f"""请帮我判断是否应该进行以下文件重命名操作：

原文件名: {old_name}
新文件名: {new_name}

书籍信息:
- 标题: {book_info.get('title', '未知')}
- 作者: {book_info.get('author', '未知')}
- 出版社: {book_info.get('publisher', '未知')}
- 出版年: {book_info.get('year', '未知')}
- 豆瓣评分: {book_info.get('rating', '未知')}
- 评价人数: {book_info.get('rating_people', '未知')}

请考虑以下因素：
1. 新文件名是否准确反映了书籍信息
2. 是否存在明显的信息丢失
3. 是否可能是错误匹配
4. 新文件名是否符合命名规范
5. 只需要根据我给你的信息进行分析，不用管你记忆里的内容。

请直接回答：APPROVE 或 REJECT ，然后换行说明原因。
"""
    
    response = call_deepseek_api(prompt)
    if not response:
        print_debug("AI响应失败，默认同意重命名")
        return True
    
    print_debug(f"AI响应内容: {response}")
    
    # 检查第一行的决定
    first_line = response.split('\n')[0].strip().upper()
    decision = first_line == 'APPROVE'
    print_debug(f"重命名决定: {'同意' if decision else '拒绝'}")
    return decision
