import os
import re

def rename_obj_files(objs_directory):
    """
    将objs目录中所有包含横线的obj文件名中的横线替换为下划线
    
    Args:
        objs_directory (str): objs目录路径
        
    Returns:
        dict: 旧文件名到新文件名的映射
    """
    # 存储文件名映射关系
    file_mapping = {}
    
    # 检查目录是否存在
    if not os.path.exists(objs_directory):
        return file_mapping
    
    # 遍历objs目录中的所有文件
    for filename in os.listdir(objs_directory):
        # 检查是否是obj或mtl文件且文件名包含横线
        if (filename.endswith('.obj') or filename.endswith('.mtl')) and '-' in filename:
            # 生成新文件名，将横线替换为下划线
            new_filename = filename.replace('-', '_')
            
            # 构造完整路径
            old_filepath = os.path.join(objs_directory, filename)
            new_filepath = os.path.join(objs_directory, new_filename)
            
            # 重命名文件
            os.rename(old_filepath, new_filepath)
            print(f"重命名文件: {filename} -> {new_filename}")
            
            # 记录映射关系
            file_mapping[filename] = new_filename
    
    return file_mapping

def rename_ply_files(plys_directory):
    """
    将plys目录中所有包含横线的ply文件名中的横线替换为下划线
    
    Args:
        plys_directory (str): plys目录路径
        
    Returns:
        dict: 旧文件名到新文件名的映射
    """
    # 存储文件名映射关系
    file_mapping = {}
    
    # 检查目录是否存在
    if not os.path.exists(plys_directory):
        return file_mapping
    
    # 遍历plys目录中的所有文件
    for filename in os.listdir(plys_directory):
        # 检查是否是ply文件且文件名包含横线
        if filename.endswith('.ply') and '-' in filename:
            # 生成新文件名，将横线替换为下划线
            new_filename = filename.replace('-', '_')
            
            # 构造完整路径
            old_filepath = os.path.join(plys_directory, filename)
            new_filepath = os.path.join(plys_directory, new_filename)
            
            # 重命名文件
            os.rename(old_filepath, new_filepath)
            print(f"重命名文件: {filename} -> {new_filename}")
            
            # 记录映射关系
            file_mapping[filename] = new_filename
    
    return file_mapping

def update_urdf_references(urdf_file_path, obj_file_mapping, ply_file_mapping):
    """
    更新URDF文件中对obj文件和ply文件的引用
    
    Args:
        urdf_file_path (str): URDF文件路径
        obj_file_mapping (dict): obj旧文件名到新文件名的映射
        ply_file_mapping (dict): ply旧文件名到新文件名的映射
    """
    # 检查文件是否存在
    if not os.path.exists(urdf_file_path):
        return 0
    
    # 读取URDF文件内容
    with open(urdf_file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 统计替换次数
    replacement_count = 0
    
    # 根据映射关系替换obj文件名
    for old_name, new_name in obj_file_mapping.items():
        # 创建要查找的旧引用和新引用
        old_reference = f'filename="objs/{old_name}"'
        new_reference = f'filename="objs/{new_name}"'
        
        # 执行替换并统计次数
        content, count = re.subn(re.escape(old_reference), new_reference, content)
        replacement_count += count
    
    # 根据映射关系替换ply文件名
    for old_name, new_name in ply_file_mapping.items():
        # 创建要查找的旧引用和新引用
        old_reference = f'filename="plys/{old_name}"'
        new_reference = f'filename="plys/{new_name}"'
        
        # 执行替换并统计次数
        content, count = re.subn(re.escape(old_reference), new_reference, content)
        replacement_count += count
    
    # 将更新后的内容写回文件
    with open(urdf_file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    if replacement_count > 0:
        print(f"在 {urdf_file_path} 中完成了 {replacement_count} 处替换")
    
    return replacement_count

def process_model_directory(model_dir):
    """
    处理单个模型目录中的所有相关文件
    
    Args:
        model_dir (str): 模型目录路径
    """
    objs_directory = os.path.join(model_dir, "objs")
    plys_directory = os.path.join(model_dir, "plys")
    urdf_file_path = os.path.join(model_dir, "model_fixed.urdf")
    
    print(f"\n正在处理目录: {model_dir}")
    
    # 重命名obj文件
    obj_file_mapping = rename_obj_files(objs_directory)
    
    # 重命名ply文件
    ply_file_mapping = rename_ply_files(plys_directory)
    
    total_renamed = len(obj_file_mapping) + len(ply_file_mapping)
    if total_renamed > 0:
        print(f"完成重命名 {len(obj_file_mapping)} 个obj文件和 {len(ply_file_mapping)} 个ply文件")
        
        # 更新URDF文件中的引用
        replacement_count = update_urdf_references(urdf_file_path, obj_file_mapping, ply_file_mapping)
        if replacement_count > 0:
            print(f"总共更新了 {replacement_count} 处引用")
    else:
        print("没有找到需要重命名的文件")

def process_all_models(base_directory):
    """
    递归处理base_directory下所有的模型目录
    
    Args:
        base_directory (str): 基础目录路径
    """
    # 遍历所有模型类别目录
    for category in os.listdir(base_directory):
        category_path = os.path.join(base_directory, category)
        
        # 确保是一个目录
        if os.path.isdir(category_path):
            print(f"\n处理模型类别: {category}")
            
            # 遍历该类别下的所有模型目录
            for model in os.listdir(category_path):
                model_path = os.path.join(category_path, model)
                
                # 确保是一个模型目录（包含objs或plys子目录）
                if os.path.isdir(model_path):
                    objs_dir = os.path.join(model_path, "objs")
                    plys_dir = os.path.join(model_path, "plys")
                    
                    # 如果该目录包含objs或plys子目录，则处理它
                    if os.path.exists(objs_dir) or os.path.exists(plys_dir):
                        try:
                            process_model_directory(model_path)
                        except Exception as e:
                            print(f"处理目录 {model_path} 时出错: {e}")

def main():
    # 设置路径
    base_directory = "/home/blackbird/GYH/back_pm"
    
    # 检查基础目录是否存在
    if not os.path.exists(base_directory):
        print(f"错误: 目录 {base_directory} 不存在")
        return
    
    print("开始递归处理所有模型目录...")
    process_all_models(base_directory)
    print("\n所有操作已完成!")

if __name__ == "__main__":
    main()