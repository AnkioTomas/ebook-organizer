# 📚 电子书文件整理工具

一个自动整理和管理电子书文件的Python工具，能够智能解析文件名，获取豆瓣信息，并将电子书整理到规范的文件夹结构中。

![GitHub stars](https://img.shields.io/github/stars/AnkioTomas/ebook-organizer?style=social)
![GitHub forks](https://img.shields.io/github/forks/AnkioTomas/ebook-organizer?style=social)
![GitHub license](https://img.shields.io/github/license/AnkioTomas/ebook-organizer)

## ✨ 功能特点

- **智能文件名解析**：自动从复杂的文件名中提取书名、作者和年份信息
- **元数据提取**：支持从PDF、EPUB、MOBI和AWZ3文件中提取元数据
- **豆瓣信息获取**：自动搜索并获取豆瓣上的书籍信息、评分和封面
- **文件整理**：将电子书整理到格式统一的文件夹中
- **NFO文件生成**：创建包含书籍详细信息的NFO文件，便于管理和查询
- **用户确认机制**：在执行重命名和移动操作前请求用户确认
- **多格式支持**：支持PDF、EPUB、MOBI、TXT和AWZ3格式

## 🔧 安装方法

### 前提条件

- Python 3.6+
- pip (Python包管理器)

### 安装步骤

1. 克隆仓库到本地：

```bash
git clone https://github.com/AnkioTomas/ebook-organizer.git
cd ebook-organizer
```

2. 安装依赖项：

```bash
pip install -r requirements.txt
```

## 📖 使用方法

1. 将你的电子书文件放入`books`目录（如果不存在，程序会自动创建）

2. 运行程序：

```bash
python main.py
```

3. 程序会自动处理每个文件，并在执行操作前请求确认

4. 处理完成后，电子书将被整理到以下格式的文件夹中：
   - 有年份信息：`作者 - 书名 (年份)`
   - 无年份信息：`作者 - 书名`

## 📋 文件结构

处理后的文件结构示例：

```
books/
├── 林语堂 - 苏东坡传 (2018)/
│   ├── 苏东坡传.epub
│   ├── 苏东坡传.jpg (豆瓣封面)
│   └── 苏东坡传.nfo (书籍信息XML)
├── 费孝通 - 乡土中国 (2006)/
│   ├── 乡土中国.epub
│   ├── 乡土中国.jpg
│   └── 乡土中国.nfo
└── ...
```

## 🔍 文件名解析能力

该工具能够处理各种复杂的文件名格式，包括但不限于：

- 带有书名号的文件名：`《苏东坡传》 (林语堂) (Z-Library).epub`
- 带有国籍标记的作者名：`人都是要死的 (〔法〕西蒙娜·德·波伏瓦) (Z-Library).epub`
- 带有特殊符号的文件名：`【精排】鬼吹灯8部全集图文版 (天下霸唱 [天下霸唱]) (Z-Library).epub`
- 带有长描述的文件名：`人间草木（20世纪文学大家、生活家汪曾祺散文集，水一样的文字写妙趣生活） (汪曾祺) (Z-Library).mobi`

## 📝 配置选项

在`main.py`文件开头可以修改以下配置：

```python
BOOKS_DIR = "./books"  # 书籍目录
NEW_NAME_PATTERN = "{author} - {title} ({year})"  # 文件夹命名格式
```

## 📦 依赖项

- PyPDF2：处理PDF文件元数据
- ebookmeta：处理EPUB/MOBI/AWZ3文件元数据
- requests：进行网络请求
- BeautifulSoup4：解析HTML
- lxml：XML处理

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出改进建议！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 开启一个 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 详情请参阅 [LICENSE](LICENSE) 文件

## 🙏 致谢

- 感谢豆瓣提供的书籍信息API
- 感谢所有开源库的贡献者

## 📞 联系方式

如有任何问题或建议，请通过以下方式联系我：

- GitHub Issues: [ebook-organizer](https://github.com/AnkioTomas/ebook-organizer/issues)
- Email: ankio@ankio.net


## 🤖 开发说明

本项目约90%的代码由AI生成并经过人工审核和优化。

---

⭐ 如果这个项目对你有帮助，请给它一个Star！ 