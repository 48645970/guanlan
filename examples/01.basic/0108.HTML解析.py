# -*- coding: utf-8 -*-
"""
HTML 解析示例

演示 BeautifulSoup 库的用法：
- 网页内容获取
- HTML 标签解析
- 文本和属性提取
- 标签查找

使用前需要：
1. pip install requests beautifulsoup4

Author: 海山观澜
"""


def fetch_page(url: str) -> str | None:
    """获取网页内容"""
    try:
        import requests
    except ImportError:
        print("请先安装 requests: pip install requests")
        return None

    headers = {
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        return response.text
    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return None


def parse_html_demo(html: str):
    """演示 HTML 解析"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("请先安装 beautifulsoup4: pip install beautifulsoup4")
        return

    soup = BeautifulSoup(html, "html.parser")

    # 获取标题
    print("\n[页面标题]")
    if soup.title:
        print(f"  {soup.title.string}")

    # 获取所有链接
    print("\n[页面链接]")
    links = soup.find_all("a", href=True)
    for i, link in enumerate(links[:10]):  # 只显示前 10 个
        text = link.get_text(strip=True) or "(无文本)"
        href = link.get("href", "")
        print(f"  {i+1}. {text[:30]}")
        print(f"     -> {href[:60]}")

    if len(links) > 10:
        print(f"  ... 共 {len(links)} 个链接")

    # 获取所有图片
    print("\n[页面图片]")
    images = soup.find_all("img", src=True)
    for i, img in enumerate(images[:5]):  # 只显示前 5 个
        src = img.get("src", "")
        alt = img.get("alt", "(无描述)")
        print(f"  {i+1}. {alt[:30]}")
        print(f"     -> {src[:60]}")

    if len(images) > 5:
        print(f"  ... 共 {len(images)} 张图片")

    # 获取 meta 信息
    print("\n[Meta 信息]")
    metas = soup.find_all("meta")
    for meta in metas[:5]:
        name = meta.get("name") or meta.get("property", "")
        content = meta.get("content", "")
        if name and content:
            print(f"  {name}: {content[:50]}")


def main():
    print("=" * 50)
    print("HTML 解析示例")
    print("=" * 50)

    # 测试网页
    url = "https://www.baidu.com"
    print(f"\n目标网址: {url}")
    print("获取网页内容...")

    html = fetch_page(url)
    if html:
        print(f"获取成功，内容长度: {len(html)} 字符")
        parse_html_demo(html)
    else:
        print("获取失败")

    print("\nHTML 解析示例完成！")


if __name__ == "__main__":
    main()
