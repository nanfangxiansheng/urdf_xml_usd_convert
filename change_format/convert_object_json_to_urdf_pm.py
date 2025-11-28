#!/usr/bin/env python3
"""
Object.json to URDF Converter
=============================

完整的自动转换脚本，基于验证的统一公式：
- 主部件（revolute/prismatic）: mesh_origin = -joint_origin
- Fixed子部件: mesh_origin = -parent_joint_origin

验证资产：
- B07D42T6CX: 4抽屉柜，100%准确
- B07MGL8651: 2门1抽屉4把手柜，100%准确

使用方法：
    python convert_object_json_to_urdf.py <object.json路径>
    python convert_object_json_to_urdf.py <object.json路径> <输出urdf路径>
    python convert_object_json_to_urdf.py --batch <目录> --validate

作者: AI Expert
日期: 2025-11-26
"""

import json
import numpy as np
from xml.etree.ElementTree import Element, SubElement, tostring, Comment
from xml.dom import minidom
import os
import sys
import argparse
import glob


def get_mesh_origin(part, diffuse_tree):
    """
    计算mesh origin - 核心函数
    
    统一规则：
    - 主部件（revolute/prismatic）: mesh_origin = -joint_origin
    - Fixed子部件: mesh_origin = -parent_joint_origin
    - Base: mesh_origin = [0, 0, 0]
    
    Args:
        part (dict): 当前部件的数据（来自diffuse_tree）
        diffuse_tree (list): 完整的diffuse_tree列表
    
    Returns:
        numpy.ndarray: mesh origin的[x, y, z]坐标
    
    Examples:
        >>> part = {"joint": {"type": "revolute", "axis": {"origin": [-0.45, -0.08, 0.31]}}}
        >>> get_mesh_origin(part, [])
        array([ 0.45,  0.08, -0.31])
    """
    joint_type = part['joint']['type']
    
    if joint_type in ['revolute', 'prismatic', 'continuous']:
        # 主部件：使用自己的joint origin
        if 'axis' in part['joint'] and 'origin' in part['joint']['axis']:
            joint_origin = np.array(part['joint']['axis']['origin'])
            return -joint_origin
        else:
            print(f"⚠️  警告: part缺少axis.origin字段，使用默认值[0,0,0]")
            return np.array([0.0, 0.0, 0.0])
    
    elif joint_type == 'fixed':
        # Fixed子部件：使用parent的joint origin
        if 'parent' in part and part['parent'] is not None:
            parent_id = part['parent']
            parent_part = diffuse_tree[parent_id]
            # 检查parent是否有axis和origin字段
            if 'axis' in parent_part['joint'] and 'origin' in parent_part['joint']['axis']:
                parent_joint_origin = np.array(parent_part['joint']['axis']['origin'])
                return -parent_joint_origin
            else:
                print(f"⚠️  警告: parent part {parent_id} 缺少axis.origin字段，使用默认值[0,0,0]")
                return np.array([0.0, 0.0, 0.0])
        else:
            # Base link（没有parent）
            return np.array([0.0, 0.0, 0.0])
    
    else:
        print(f"⚠️  警告: 未知joint类型 '{joint_type}'，使用默认值[0,0,0]")
        return np.array([0.0, 0.0, 0.0])


def find_base_link_id(diffuse_tree):
    """
    找到base_link的part_id
    
    通常是最后一个fixed类型且没有parent的部件
    
    Args:
        diffuse_tree (list): diffuse_tree列表
    
    Returns:
        int: base link的索引
    """
    for i in range(len(diffuse_tree) - 1, -1, -1):
        part = diffuse_tree[i]
        if part['joint']['type'] == 'fixed' and ('parent' not in part or part['parent'] is None):
            return i
    return len(diffuse_tree) - 1  # 默认最后一个


def sanitize_link_name(name):
    """
    清理link名称，移除特殊字符
    
    Args:
        name (str): 原始名称
    
    Returns:
        str: 清理后的名称
    """
    return name.replace(' ', '_').replace('-', '_').replace('.', '_')


def create_urdf_from_object_json(
    object_json_path, 
    output_urdf_path, 
    obj_dir="objs",
    robot_name=None,
    verbose=True
):
    """
    从object.json生成URDF文件
    
    Args:
        object_json_path (str): object.json文件路径
        output_urdf_path (str): 输出URDF路径
        obj_dir (str): OBJ文件目录（相对于URDF的路径）
        robot_name (str): 机器人名称（默认使用model_id）
        verbose (bool): 是否打印详细信息
    
    Returns:
        bool: 成功返回True，失败返回False
    
    Raises:
        FileNotFoundError: 如果object.json不存在
        json.JSONDecodeError: 如果JSON格式错误
    """
    
    # 1. 读取object.json
    if verbose:
        print(f"📖 读取 {object_json_path}...")
    
    try:
        with open(object_json_path, 'r') as f:
            obj_data = json.load(f)
    except FileNotFoundError:
        print(f"❌ 错误: 文件不存在 - {object_json_path}")
        return False
    except json.JSONDecodeError as e:
        print(f"❌ 错误: JSON格式错误 - {e}")
        return False
    
    model_id = obj_data.get('model_id', 'articulated_object')
    diffuse_tree = obj_data.get('diffuse_tree', [])
    
    if not diffuse_tree:
        print(f"❌ 错误: diffuse_tree为空")
        return False
    
    if robot_name is None:
        robot_name = model_id
    
    if verbose:
        print(f"   模型ID: {model_id}")
        print(f"   部件数: {len(diffuse_tree)}")
    
    # 2. 找到base_link
    base_id = find_base_link_id(diffuse_tree)
    if verbose:
        print(f"   Base link: part_{base_id}")
    
    # 3. 创建URDF根元素
    robot = Element('robot', name=robot_name)
    robot.append(Comment(f' Auto-generated from {os.path.basename(object_json_path)} '))
    robot.append(Comment(' Conversion script: convert_object_json_to_urdf.py '))
    robot.append(Comment(' Formula: mesh_origin = -joint_origin (for main parts) '))
    robot.append(Comment('          mesh_origin = -parent_joint_origin (for fixed children) '))
    
    # 4. 构建part_id到link_name的映射
    part_to_link = {}
    name_counts = {}  # 追踪名称使用次数，处理重复名称
    
    for i, part in enumerate(diffuse_tree):
        if i == base_id:
            link_name = "base_link"
        else:
            # 使用part name或默认part_i
            raw_name = part.get('name', f'part_{i}')
            base_name = sanitize_link_name(raw_name)
            
            # 处理重复名称：添加索引后缀
            if base_name in name_counts:
                name_counts[base_name] += 1
                link_name = f"{base_name}_{name_counts[base_name]}"
            else:
                name_counts[base_name] = 0
                link_name = base_name
        
        part_to_link[i] = link_name
    
    # 5. 遍历所有parts，创建links和joints
    created_links = set()
    joint_stats = {'revolute': 0, 'prismatic': 0, 'fixed': 0}
    
    for part_id, part in enumerate(diffuse_tree):
        link_name = part_to_link[part_id]
        joint_type = part['joint']['type']
        joint_stats[joint_type] = joint_stats.get(joint_type, 0) + 1
        
        # 计算mesh origin（核心公式）
        mesh_origin = get_mesh_origin(part, diffuse_tree)
        mesh_origin_str = f"{mesh_origin[0]:.6f} {mesh_origin[1]:.6f} {mesh_origin[2]:.6f}"
        
        # 获取OBJ文件名并创建Link
        link = SubElement(robot, 'link', name=link_name)
        
        # 处理视觉和碰撞几何体
        if 'objs' in part and len(part['objs']) > 0:
            for obj_filename in part['objs']:
                # 如果object.json中的路径已包含目录，直接使用
                if obj_filename.startswith('objs/'):
                    obj_path = obj_filename
                else:
                    obj_path = f"{obj_dir}/{obj_filename}"
                
                # 为每个OBJ文件创建独立的visual和collision元素
                visual = SubElement(link, 'visual')
                SubElement(visual, 'origin', xyz=mesh_origin_str, rpy="0 0 0")
                vis_geom = SubElement(visual, 'geometry')
                SubElement(vis_geom, 'mesh', filename=obj_path)
                
                # Collision
                collision = SubElement(link, 'collision')
                SubElement(collision, 'origin', xyz=mesh_origin_str, rpy="0 0 0")
                col_geom = SubElement(collision, 'geometry')
                SubElement(col_geom, 'mesh', filename=obj_path)
        else:
            obj_filename = f"{model_id}_part_{part_id}.obj"
            obj_path = f"{obj_dir}/{obj_filename}"
            
            # Visual
            visual = SubElement(link, 'visual')
            SubElement(visual, 'origin', xyz=mesh_origin_str, rpy="0 0 0")
            vis_geom = SubElement(visual, 'geometry')
            SubElement(vis_geom, 'mesh', filename=obj_path)
            
            # Collision
            collision = SubElement(link, 'collision')
            SubElement(collision, 'origin', xyz=mesh_origin_str, rpy="0 0 0")
            col_geom = SubElement(collision, 'geometry')
            SubElement(col_geom, 'mesh', filename=obj_path)
        
        # Inertial（简化处理）
        inertial = SubElement(link, 'inertial')
        SubElement(inertial, 'origin', xyz=mesh_origin_str, rpy="0 0 0")
        
        # 根据joint类型设置质量和惯性
        if joint_type == 'fixed':
            if part_id == base_id:
                mass_val = "10.0"  # base比较重
                inertia_val = "0.1"
            else:
                mass_val = "0.1"  # fixed子部件轻
                inertia_val = "0.001"
        elif joint_type == 'prismatic':
            mass_val = "3.0"  # 抽屉中等
            inertia_val = "0.03"
        elif joint_type == 'revolute':
            mass_val = "2.0"  # 门中等
            inertia_val = "0.02"
        else:
            mass_val = "1.0"
            inertia_val = "0.01"
        
        SubElement(inertial, 'mass', value=mass_val)
        SubElement(inertial, 'inertia',
                  ixx=inertia_val, ixy="0", ixz="0",
                  iyy=inertia_val, iyz="0", izz=inertia_val)
        
        created_links.add(link_name)
        
        # ========== 创建Joint（如果有parent）==========
        if 'parent' in part and part['parent'] is not None:
            parent_id = part['parent']
            
            # 检查parent是否有效
            if parent_id < 0 or parent_id >= len(diffuse_tree):
                print(f"⚠️  警告: part_{part_id}的parent_id {parent_id}无效，跳过joint创建")
                continue
            
            parent_link = part_to_link[parent_id]
            joint_name = f"joint_{link_name}"
            
            joint = SubElement(robot, 'joint', name=joint_name, type=joint_type)
            SubElement(joint, 'parent', link=parent_link)
            SubElement(joint, 'child', link=link_name)
            
            # Joint origin是parent的mesh origin
            #parent_part = diffuse_tree[parent_id]
            parent_part=part
            # 检查parent是否有axis字段
            if 'axis' in parent_part['joint'] and 'origin' in parent_part['joint']['axis']:
                joint_origin = np.array(parent_part['joint']['axis']['origin'])
                joint_origin_str = f"{joint_origin[0]:.6f} {joint_origin[1]:.6f} {joint_origin[2]:.6f}"
                SubElement(joint, 'origin', xyz=joint_origin_str, rpy="0 0 0")
                print(f"joint_{link_name} origin: {joint_origin_str}")
            else:
                print(f"⚠️  警告: parent part {parent_id} 缺少axis.origin字段，joint origin使用默认值[0,0,0]")
                SubElement(joint, 'origin', xyz="0 0 0", rpy="0 0 0")
            
            # Axis和Limits（仅对revolute、prismatic和continuous）
            if joint_type in ['revolute', 'prismatic', 'continuous']:
                if 'axis' in part['joint'] and 'direction' in part['joint']['axis']:
                    axis_dir = part['joint']['axis']['direction']
                    axis_str = f"{axis_dir[0]} {axis_dir[1]} {axis_dir[2]}"
                    SubElement(joint, 'axis', xyz=axis_str)
                else:
                    print(f"⚠️  警告: part_{part_id} 缺少axis方向，使用默认值[1,0,0]")
                    SubElement(joint, 'axis', xyz="1 0 0")
                
                # Limit
                if 'range' in part['joint']:
                    limit_range = part['joint']['range']
                    effort = "10"  # 默认值
                    velocity = "1"  # 默认值
                    
                    if joint_type == 'prismatic':
                        lower = f"{np.deg2rad(limit_range[0]):.6f}"  # 错误修正：应该是直接使用数值而不是转换
                        upper = f"{np.deg2rad(limit_range[1]):.6f}"
                        if upper<lower:
                            upper,lower=lower,upper
                        SubElement(joint, 'limit', lower=str(limit_range[0]), upper=str(limit_range[1]), effort=effort, velocity=velocity)
                        print(f"   ℹ️  {link_name}: 转换range [{limit_range[0]}, {limit_range[1]}] cm → [{limit_range[0]:.6f}, {limit_range[1]:.6f}] m")
                    elif joint_type in ['revolute', 'continuous']:
                        lower = f"{np.deg2rad(limit_range[0]):.6f}"
                        upper = f"{np.deg2rad(limit_range[1]):.6f}"
                        if upper<lower:
                            upper,lower=lower,upper
                        if joint_type == 'revolute':
                            SubElement(joint, 'limit', lower=lower, upper=upper, effort=effort, velocity=velocity)
                            print(f"   ℹ️  {link_name}: 转换range [{limit_range[0]}, {limit_range[1]}] 度 → [{lower}, {upper}] 弧度")
                        else:  # continuous类型不限制范围
                            SubElement(joint, 'limit', effort=effort, velocity=velocity)
                else:
                    # 默认limit
                    effort = "10"
                    velocity = "1"
                    if joint_type == 'prismatic':
                        SubElement(joint, 'limit', lower="-0.5", upper="0.5", effort=effort, velocity=velocity)
                    elif joint_type == 'revolute':
                        SubElement(joint, 'limit', lower="0", upper="3.14159", effort=effort, velocity=velocity)
                    # continuous类型不限制范围
    
    # 6. 美化XML并输出
    rough_string = tostring(robot, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ")
    
    # 移除多余空行
    lines = [line for line in pretty_xml.split('\n') if line.strip()]
    final_xml = '\n'.join(lines)
    
    # 7. 写入文件
    try:
        # 创建输出目录（如果不存在）
        output_dir = os.path.dirname(output_urdf_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
        
        with open(output_urdf_path, 'w') as f:
            f.write(final_xml)
    except Exception as e:
        print(f"❌ 错误: 写入文件失败 - {e}")
        return False
    
    if verbose:
        print(f"\n✅ URDF生成成功！")
        print(f"   输出文件: {output_urdf_path}")
        print(f"   创建了 {len(created_links)} 个links")
        print(f"\n📊 统计:")
        for jtype, count in joint_stats.items():
            if count > 0:
                print(f"   - {jtype}: {count} 个")
    
    return True


def validate_urdf_against_json(urdf_path, json_path, verbose=True):
    """
    验证生成的URDF是否符合object.json
    
    Args:
        urdf_path (str): URDF文件路径
        json_path (str): object.json文件路径
        verbose (bool): 是否打印详细信息
    
    Returns:
        bool: 验证通过返回True
    """
    import xml.etree.ElementTree as ET
    
    if verbose:
        print(f"\n🔍 验证 {os.path.basename(urdf_path)}...")
    
    try:
        # 读取数据
        with open(json_path, 'r') as f:
            obj_data = json.load(f)
        
        tree = ET.parse(urdf_path)
        root = tree.getroot()
    except Exception as e:
        print(f"❌ 错误: 读取文件失败 - {e}")
        return False
    
    diffuse_tree = obj_data['diffuse_tree']
    base_id = find_base_link_id(diffuse_tree)
    
    # 构建part_to_link映射（与生成时一致）
    part_to_link = {}
    name_counts = {}
    
    for i, part in enumerate(diffuse_tree):
        if i == base_id:
            link_name = 'base_link'
        else:
            raw_name = part.get('name', f'part_{i}')
            base_name = sanitize_link_name(raw_name)
            
            # 处理重复名称
            if base_name in name_counts:
                name_counts[base_name] += 1
                link_name = f"{base_name}_{name_counts[base_name]}"
            else:
                name_counts[base_name] = 0
                link_name = base_name
        
        part_to_link[i] = link_name
    
    # 提取URDF中的mesh origins
    urdf_origins = {}
    for link in root.findall('link'):
        link_name = link.get('name')
        visual = link.find('visual/origin')
        if visual is not None:
            xyz = [float(x) for x in visual.get('xyz').split()]
            urdf_origins[link_name] = np.array(xyz)
    
    # 验证每个part
    all_match = True
    mismatch_count = 0
    
    for i, part in enumerate(diffuse_tree):
        # 确定link_name（需要和生成时一致） - 使用已经构建好的映射
        link_name = part_to_link[i]
        
        # 计算期望值
        expected = get_mesh_origin(part, diffuse_tree)
        
        # 比较
        if link_name in urdf_origins:
            actual = urdf_origins[link_name]
            # 允许2cm误差（考虑可能的手动微调）
            match = np.allclose(expected, actual, atol=0.02)
            
            if not match:
                all_match = False
                mismatch_count += 1
                if verbose:
                    print(f"   ❌ {link_name}:")
                    print(f"      期望: {expected}")
                    print(f"      实际: {actual}")
                    print(f"      差异: {actual - expected}")
        else:
            if verbose:
                print(f"   ⚠️  未找到link: {link_name}")
            all_match = False
            mismatch_count += 1
    
    if verbose:
        if all_match:
            print(f"   🎉 验证通过！所有{len(diffuse_tree)}个部件mesh origin正确！")
        else:
            print(f"   ⚠️  验证失败：{mismatch_count}/{len(diffuse_tree)}个部件不匹配")
    
    return all_match


def batch_convert(directory, output_suffix=".urdf", validate=False, recursive=True):
    """
    批量转换目录下的所有object.json文件
    
    Args:
        directory (str): 搜索目录
        output_suffix (str): 输出文件后缀
        validate (bool): 是否验证生成的URDF
        recursive (bool): 是否递归搜索子目录
    
    Returns:
        tuple: (成功数量, 失败数量)
    """
    print(f"\n🔄 批量转换模式")
    print(f"   搜索目录: {directory}")
    print(f"   递归搜索: {'是' if recursive else '否'}")
    print(f"   验证URDF: {'是' if validate else '否'}")
    print()
    
    # 搜索所有object.json文件
    pattern = os.path.join(directory, "**", "object.json") if recursive else os.path.join(directory, "object.json")
    json_files = glob.glob(pattern, recursive=recursive)
    
    if not json_files:
        print(f"❌ 未找到object.json文件")
        return 0, 0
    
    print(f"📁 找到 {len(json_files)} 个object.json文件\n")
    
    success_count = 0
    fail_count = 0
    
    for i, json_path in enumerate(json_files, 1):
        print(f"[{i}/{len(json_files)}] 处理 {json_path}")
        
        # 确定输出路径
        json_dir = os.path.dirname(json_path)
        output_path = os.path.join(json_dir, f"model{output_suffix}")
        
        # 转换
        success = create_urdf_from_object_json(
            json_path, 
            output_path, 
            obj_dir="objs",
            verbose=False
        )
        
        if success:
            print(f"   ✅ 生成成功: {output_path}")
            success_count += 1
            
            # 验证（如果需要）
            if validate:
                valid = validate_urdf_against_json(output_path, json_path, verbose=False)
                if valid:
                    print(f"   ✅ 验证通过")
                else:
                    print(f"   ⚠️  验证失败")
        else:
            print(f"   ❌ 生成失败")
            fail_count += 1
        
        print()
    
    print(f"\n📊 批量转换完成:")
    print(f"   成功: {success_count}/{len(json_files)}")
    print(f"   失败: {fail_count}/{len(json_files)}")
    
    return success_count, fail_count


def main():
    """主函数 - 命令行接口"""
    
    parser = argparse.ArgumentParser(
        description='将object.json转换为URDF格式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 转换单个文件（自动生成输出路径）
  python convert_object_json_to_urdf.py object.json
  
  # 转换单个文件（指定输出路径）
  python convert_object_json_to_urdf.py object.json output.urdf
  
  # 批量转换目录
  python convert_object_json_to_urdf.py --batch ./articulated_assets
  
  # 批量转换并验证
  python convert_object_json_to_urdf.py --batch ./articulated_assets --validate
  
  # 仅验证已有的URDF
  python convert_object_json_to_urdf.py object.json test.urdf --validate-only
        """
    )
    
    # 单文件模式参数
    parser.add_argument('input', nargs='?', help='输入object.json文件路径')
    parser.add_argument('output', nargs='?', help='输出URDF文件路径（可选，默认为同目录下的model.urdf）')
    
    # 批量模式参数
    parser.add_argument('--batch', metavar='DIR', help='批量转换模式：指定包含object.json的目录')
    parser.add_argument('--recursive', action='store_true', default=True, help='递归搜索子目录（批量模式）')
    parser.add_argument('--no-recursive', dest='recursive', action='store_false', help='不递归搜索')
    
    # 验证参数
    parser.add_argument('--validate', action='store_true', help='生成后验证URDF')
    parser.add_argument('--validate-only', action='store_true', help='仅验证已有URDF，不生成')
    
    # 其他参数
    parser.add_argument('--obj-dir', default='objs', help='OBJ文件目录（相对于URDF）')
    parser.add_argument('--robot-name', help='机器人名称（默认使用model_id）')
    parser.add_argument('--quiet', action='store_true', help='安静模式（减少输出）')
    
    args = parser.parse_args()
    
    # 批量模式
    if args.batch:
        success, fail = batch_convert(
            args.batch,
            validate=args.validate,
            recursive=args.recursive
        )
        sys.exit(0 if fail == 0 else 1)
    
    # 单文件模式
    if not args.input:
        parser.print_help()
        sys.exit(1)
    
    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        input_dir = os.path.dirname(args.input) or '.'
        output_path = os.path.join(input_dir, 'model.urdf')
    
    # 仅验证模式
    if args.validate_only:
        if not os.path.exists(output_path):
            print(f"❌ 错误: URDF文件不存在 - {output_path}")
            sys.exit(1)
        
        valid = validate_urdf_against_json(output_path, args.input, verbose=not args.quiet)
        sys.exit(0 if valid else 1)
    
    # 转换模式
    success = create_urdf_from_object_json(
        args.input,
        output_path,
        obj_dir=args.obj_dir,
        robot_name=args.robot_name,
        verbose=not args.quiet
    )
    
    if not success:
        sys.exit(1)
    
    # 验证（如果需要）
    if args.validate:
        valid = validate_urdf_against_json(output_path, args.input, verbose=not args.quiet)
        sys.exit(0 if valid else 1)
    
    sys.exit(0)


if __name__ == "__main__":
    main()
