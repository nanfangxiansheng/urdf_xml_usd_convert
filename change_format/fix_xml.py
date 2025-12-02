#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
update_mjcf_file_paths_auto.py

功能：
- 读取输入 MJCF/XML 文件
- 自动检测第一个包含 '/objs/' 的 mesh 文件路径前缀（例如：
  file="/home/xxx/.../objs/"）
- 将所有以该前缀开头的 file=".../objs/NAME" 替换为 file="objs/NAME"
- 输出到指定输出文件，或覆盖原文件（若未给出输出路径）

用法：
    python update_mjcf_file_paths_auto.py input.xml [output.xml]
"""
import sys
import os
import re

def update_mjcf_file_paths_auto(xml_file_path: str, output_file_path: str | None = None):
    # 读取原始文件
    with open(xml_file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 找到第一个包含 '/objs/' 的 file=".../objs/..." 路径并提取前缀
    m = re.search(r'file="([^"]*/objs/)([^"]+)"', content)
    if not m:
        print("未在文件中找到任何包含 '/objs/' 的 mesh 路径。无需替换。")
        return content

    detected_prefix = m.group(1)  # e.g. /home/blackbird/GYH/.../objs/
    print(f"检测到的 objs 前缀: '{detected_prefix}'")

    # 构造针对该前缀的替换正则：只替换以检测到的前缀开头的路径
    # 使用 re.escape 确保前缀里的特殊字符被正确转义
    pref_escaped = re.escape(detected_prefix)
    pattern = rf'file="{pref_escaped}([^"]+)"'

    # 替换为相对路径 file="objs/<name>"
    new_content, nsub = re.subn(pattern, r'file="objs/\1"', content)
    print(f"已替换 {nsub} 处匹配到的路径（基于检测到的前缀）。")

    # 如果某些路径使用不同的前缀（例如多个不同根），可额外再做一次更广泛的替换（可选）
    # 以下代码被注释掉：若需要，也可以启用，将所有含 '/objs/' 的绝对路径一并替换为相对路径


    # 写入输出文件（默认覆盖原文件）
    if output_file_path is None or output_file_path.strip() == "":
        output_file_path = xml_file_path

    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"已写入：{output_file_path}")
    return new_content

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python update_mjcf_file_paths_auto.py input.xml [output.xml]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else None

    if not os.path.exists(input_file):
        print(f"输入文件不存在: {input_file}")
        sys.exit(1)

    update_mjcf_file_paths_auto(input_file, output_file)
