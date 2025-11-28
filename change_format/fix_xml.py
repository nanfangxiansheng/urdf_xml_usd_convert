import xml.etree.ElementTree as ET
import re

def update_mjcf_file_paths(xml_file_path, output_file_path=None):
    """
    修改MJCF文件中的mesh文件路径，将绝对路径改为相对路径
    
    Args:
        xml_file_path: 输入的MJCF文件路径
        output_file_path: 输出文件路径（如果为None，则覆盖原文件）
    """
    # 读取XML文件
    with open(xml_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 定义要替换的模式
    pattern = r'file="/home/hcy/work/TeleIllusion/USDToolbox/848c2cc9428329445b3de7dc982469c583b16c1d/objs/([^"]+)"'
    
    # 执行替换
    new_content = re.sub(pattern, r'file="objs/\1"', content)
    
    # 写入输出文件
    if output_file_path is None:
        output_file_path = xml_file_path
    
    with open(output_file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"文件路径已更新，保存到: {output_file_path}")
    
    # 统计替换的数量
    old_matches = re.findall(pattern, content)
    new_matches = re.findall(r'file="objs/([^"]+)"', new_content)
    
    print(f"共替换了 {len(old_matches)} 个文件路径")
    
    return new_content

# 使用方法
if __name__ == "__main__":
    # 输入文件路径
    input_file = "/home/hcy/work/TeleIllusion/USDToolbox/848c2cc9428329445b3de7dc982469c583b16c1d/model.xml"
    
    # 输出文件路径（如果为None则覆盖原文件）
    output_file ="/home/hcy/work/TeleIllusion/USDToolbox/848c2cc9428329445b3de7dc982469c583b16c1d/model_fixed.xml" # 或者设为None覆盖原文件
    
    # 执行替换
    updated_content = update_mjcf_file_paths(input_file, output_file)
    
    # 显示修改前后的对比
    print("\n修改示例:")
    with open(input_file, 'r', encoding='utf-8') as f:
        original_content = f.read()
    
    # 显示前几个mesh的修改对比
    original_meshes = re.findall(r'<mesh name="[^"]+"[^>]*file="([^"]+)"', original_content)[:3]
    updated_meshes = re.findall(r'<mesh name="[^"]+"[^>]*file="([^"]+)"', updated_content)[:3]
    
    print("\n修改前:")
    for mesh in original_meshes:
        print(f"  {mesh}")
    
    print("\n修改后:")
    for mesh in updated_meshes:
        print(f"  {mesh}")