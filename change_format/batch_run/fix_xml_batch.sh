#!/bin/bash

# 脚本功能：修复 /home/blackbird/GYH/out_pm 下的所有 model_fixed.xml 文件
# 并将修复后的文件保存为 model_fixed1.xml

INPUT_DIR="/home/blackbird/GYH/out_pm"
FIX_SCRIPT="/home/blackbird/GYH/urdf_xml_usd_convert/change_format/fix_xml.py"

# 检查修复脚本是否存在
if [ ! -f "$FIX_SCRIPT" ]; then
    echo "错误：修复脚本 $FIX_SCRIPT 不存在"
    exit 1
fi

# 计数器
total_files=0
processed_files=0
failed_files=0

echo "开始修复 XML 文件..."
echo "=========================="

# 遍历所有子目录中的 model_fixed.xml 文件
find "$INPUT_DIR" -name "model_fixed.xml" -type f | while read xml_file; do
    ((total_files++))
    
    # 获取文件所在目录
    dir_path=$(dirname "$xml_file")
    
    # 定义输出文件路径
    output_file="$dir_path/model_fixed1.xml"
    
    echo "正在处理: $xml_file"
    
    # 运行修复脚本
    if python3 "$FIX_SCRIPT" "$xml_file" "$output_file"; then
        ((processed_files++))
        echo "成功修复: $xml_file -> $output_file"
    else
        ((failed_files++))
        echo "修复失败: $xml_file"
    fi
    
    echo "--------------------------"
done

echo "处理完成!"
echo "总计文件数: $total_files"
echo "成功处理: $processed_files"
echo "处理失败: $failed_files"