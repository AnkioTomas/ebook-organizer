import difflib
import re

import requests
from bs4 import BeautifulSoup
from src.utils.network import safe_request
from src.utils.text_utils import to_simplified, calculate_title_similarity
from src.utils.logger import print_info, print_error, print_debug, print_warning
from src.services.ai_service import ai_select_best_match

DOUBAN_SEARCH_URL = "https://www.douban.com/search"

def search_douban(query, expected_author=None, fetch_detail=True, min_similarity=0.6):
    """在豆瓣搜索书籍，返回匹配度最高的书籍信息
    Args:
        query: 搜索关键词
        expected_author: 预期的作者名（可选，用于比较）
        fetch_detail: 是否获取详情页信息（可选，默认True）
        min_similarity: 最小标题相似度（可选，默认0.6）
    Returns:
        匹配的书籍信息字典
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
                # 如果没有作者匹配，使用AI选择
                best_match = ai_select_best_match(top_matches)
        else:
            # 如果没有预期作者或只有一个匹配，使用AI选择
            best_match = ai_select_best_match(top_matches)
    
    # 获取详情页信息（ISBN等）
    if fetch_detail and best_match["url"]:
        print_info(f"获取详情页信息: {best_match['url']}")
        detail_info = fetch_douban_book_info(best_match["url"])
        if detail_info:
            best_match.update(detail_info)
    
    return best_match

def fetch_douban_book_info(book_url):
    """解析豆瓣书籍详情页，返回补充信息
    Args:
        book_url: 豆瓣图书URL
    Returns:
        补充信息字典
    """
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
        
        # 提取作者信息
        authors = []
        # 首先查找作者标签
        author_span = info.find('span', text=lambda t: t and '作者' in t)
        if author_span:
            # 获取作者span后面的所有作者链接
            author_links = author_span.find_parent('span').find_all('a')
            if author_links:
                authors = [to_simplified(a.get_text(strip=True)) for a in author_links]
                # 处理作者名：去除国籍标记和英文名
                cleaned_authors = []
                for author in authors:
                    # 去除国籍标记 [美] [英] 等
                    author = re.sub(r'[\[（\(【〔][^\]）\)】〕]*[\]）\)】〕]', '', author)
                    # 去除括号内的英文名
                    author = re.sub(r'\s*\([^)]*\)', '', author)
                    # 去除英文名（通常在点号或空格后）
                    author = re.sub(r'(?<=[\u4e00-\u9fff])\s*[A-Za-z\s.]+(?:\s+[A-Za-z\s.]+)*$', '', author)
                    # 清理多余的空格
                    author = author.strip()
                    if author:
                        cleaned_authors.append(author)
                authors = cleaned_authors
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