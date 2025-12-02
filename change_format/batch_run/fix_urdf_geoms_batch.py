#!/usr/bin/env python3
"""
处理所有 model_fixed.urdf 文件中引用的 OBJ 文件几何形状
"""

import os
import xml.etree.ElementTree as ET
import subprocess
import sys
from pathlib import Path

def extract_obj_files_from_urdf(urdf_path):
    """从URDF文件中提取所有引用的OBJ文件路径"""
    obj_files = set()
    
    try:
        tree = ET.parse(urdf_path)
        root = tree.getroot()
        
        # 查找所有mesh元素中的filename属性
        for mesh in root.findall('.//mesh'):
            filename = mesh.get('filename')
            if filename and filename.endswith('.obj'):
                # 构建完整的OBJ文件路径
                full_path = os.path.join(os.path.dirname(urdf_path), filename)
                obj_files.add(full_path)
                
    except Exception as e:
        print(f"警告: 无法解析 {urdf_path}: {e}")
        
    return obj_files

def find_all_model_fixed_urdf(root_dir):
    """查找所有model_fixed.urdf文件"""
    urdf_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == 'model_fixed.urdf':
                urdf_files.append(os.path.join(dirpath, filename))
    return urdf_files

def process_obj_files_with_geom_fixing(obj_files, geom_fixing_script):
    """使用geom_fixing.py处理OBJ文件"""
    if not obj_files:
        print("没有找到需要处理的OBJ文件")
        return
        
    print(f"总共找到 {len(obj_files)} 个OBJ文件需要处理")
    
    # 创建临时目录列表，以便geom_fixing.py处理
    temp_dirs = set()
    for obj_file in obj_files:
        temp_dirs.add(os.path.dirname(obj_file))
    
    print(f"涉及 {len(temp_dirs)} 个目录")
    
    # 对每个目录运行geom_fixing.py
    processed = 0
    for directory in temp_dirs:
        print(f"\n处理目录: {directory}")
        try:
            # 使用geom_fixing.py处理整个目录
            result = subprocess.run([
                sys.executable, geom_fixing_script, directory
            ], capture_output=True, text=True, cwd=os.path.dirname(geom_fixing_script))
            
            if result.returncode == 0:
                print(f"成功处理目录: {directory}")
                print(result.stdout)
            else:
                print(f"处理目录失败: {directory}")
                print(result.stderr)
                
            processed += 1
            print(f"进度: {processed}/{len(temp_dirs)}")
            
        except Exception as e:
            print(f"处理目录 {directory} 时出错: {e}")
    
    print(f"\n完成处理 {processed}/{len(temp_dirs)} 个目录")

def main():
    # 定义路径
    articulated_assets_dir = '/home/blackbird/GYH/out_pm'
    geom_fixing_script = '/home/blackbird/GYH/urdf_xml_usd_convert/change_format/geom_fixing.py'
    
    # 检查必要文件和目录是否存在
    if not os.path.exists(articulated_assets_dir):
        print(f"错误: 目录 {articulated_assets_dir} 不存在")
        return 1
        
    if not os.path.exists(geom_fixing_script):
        print(f"错误: 脚本 {geom_fixing_script} 不存在")
        return 1
    
    # 查找所有model_fixed.urdf文件
    print("正在查找所有model_fixed.urdf文件...")
    urdf_files = find_all_model_fixed_urdf(articulated_assets_dir)
    print(f"找到 {len(urdf_files)} 个model_fixed.urdf文件")
    
    # 从URDF文件中提取OBJ文件路径
    print("正在从URDF文件中提取OBJ文件路径...")
    all_obj_files = set()
    for urdf_file in urdf_files:
        obj_files = extract_obj_files_from_urdf(urdf_file)
        all_obj_files.update(obj_files)
        print(f"  {urdf_file}: 提取到 {len(obj_files)} 个OBJ文件")
    
    # 处理OBJ文件
    print("\n开始处理OBJ文件几何形状...")
    process_obj_files_with_geom_fixing(all_obj_files, geom_fixing_script)
    
    print("\n所有处理完成!")
    return 0

if __name__ == '__main__':
    sys.exit(main())