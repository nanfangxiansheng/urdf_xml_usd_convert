#!/usr/bin/env python3
import os
import subprocess

# 根目录
root_dir = "/home/blackbird/GYH/articulated_assets/acd_test/hssd-data"

# 遍历所有子目录
for category in os.listdir(root_dir):
    category_path = os.path.join(root_dir, category)
    
    # 确保是目录
    if os.path.isdir(category_path):
        print(f"Processing category: {category}")
        
        # 遍历类别下的每个模型目录
        for model in os.listdir(category_path):
            model_path = os.path.join(category_path, model)
            
            # 确保是目录
            if os.path.isdir(model_path):
                object_json_path = os.path.join(model_path, "object.json")
                
                # 检查object.json是否存在
                if os.path.exists(object_json_path):
                    # 生成输出文件路径
                    output_urdf_path = os.path.join(model_path, "model_pm.urdf")
                    
                    # 调用转换脚本
                    cmd = [
                        "python3",
                        "/home/blackbird/GYH/articulated_assets/convert_object_json_to_urdf_pm.py",
                        object_json_path,
                        output_urdf_path
                    ]
                    
                    print(f"  Converting {object_json_path}...")
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        print(f"    Success: {output_urdf_path}")
                    else:
                        print(f"    Error: {result.stderr}")
                else:
                    print(f"  No object.json found in {model_path}")

print("Conversion completed.")
