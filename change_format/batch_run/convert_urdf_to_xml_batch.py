#!/usr/bin/env python3
"""
将所有处理后的model_fixed.urdf文件转换为XML格式
"""

import os
import subprocess
import sys
from pathlib import Path

def find_all_model_fixed_urdf(root_dir):
    """查找所有model_fixed.urdf文件"""
    urdf_files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        for filename in filenames:
            if filename == 'model_fixed.urdf':
                urdf_files.append(os.path.join(dirpath, filename))
    return urdf_files

def convert_urdf_to_xml(urdf_file):
    """将单个URDF文件转换为XML格式"""
    # 构建输出文件路径
    xml_file = urdf_file.replace('.urdf', '.xml')
    
    # 构建urdf2mjcf命令
    cmd = ['urdf2mjcf', urdf_file, xml_file]
    
    try:
        # 执行转换
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0:
            return True, f"成功转换: {urdf_file} -> {xml_file}"
        else:
            return False, f"转换失败: {urdf_file}\n  stderr: {result.stderr}"
    except subprocess.TimeoutExpired:
        return False, f"转换超时: {urdf_file}"
    except FileNotFoundError:
        return False, "错误: 找不到urdf2mjcf命令，请确保已安装"
    except Exception as e:
        return False, f"转换出错: {urdf_file}, 错误: {e}"

def main():
    # 定义路径
    articulated_assets_dir = '/home/blackbird/GYH/out_pm'
    
    # 检查目录是否存在
    if not os.path.exists(articulated_assets_dir):
        print(f"错误: 目录 {articulated_assets_dir} 不存在")
        return 1
    
    # 查找所有model_fixed.urdf文件
    print("正在查找所有model_fixed.urdf文件...")
    urdf_files = find_all_model_fixed_urdf(articulated_assets_dir)
    print(f"找到 {len(urdf_files)} 个model_fixed.urdf文件")
    
    # 转换每个URDF文件为XML格式
    print("\n开始转换URDF文件为XML格式...")
    success_count = 0
    fail_count = 0
    
    for i, urdf_file in enumerate(urdf_files, 1):
        print(f"[{i}/{len(urdf_files)}] ", end="")
        success, message = convert_urdf_to_xml(urdf_file)
        print(message)
        
        if success:
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\n========== 转换统计 ==========")
    print(f"总文件数: {len(urdf_files)}")
    print(f"成功转换: {success_count}")
    print(f"转换失败: {fail_count}")
    print("\n所有转换完成!")
    return 0

if __name__ == '__main__':
    sys.exit(main())