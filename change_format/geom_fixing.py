#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fix_obj_geom_recursive.py (modified)

递归处理目录中的所有 OBJ 文件，解决：

1. OBJ 语法错误：
   - 例如：f 3/1/2 2/2/2 1/3/2v -0.1552 ...
     自动拆成：
       f 3/1/2 2/2/2 1/3/2
       v -0.1552 ...

2. 几何退化（几乎 2D / 共面）导致 MuJoCo/Qhull 报：
   - Initial simplex is flat

3. 顶点太少导致 MuJoCo 报：
   - at least 4 vertices required
   - mesh volume is too small: xxx . Try setting inertia to shell

处理策略（每个 OBJ）：
- 文本层做语法修复；
- 解析顶点 & 面；
- 统计 “唯一顶点数”：
  * 若唯一顶点数 < 4：
      -> 直接构造一个小四面体（真正有体积），完全重写该 OBJ；
  * 否则：
      -> 检测退化轴，对退化轴做“厚度拉伸”（QJ 风格），保持拓扑不变，只改坐标。
- 覆盖写回 OBJ，原文件备份为 .bak。

修改说明：
- 新增逻辑：在对每个 .obj 处理前，若存在同名 .obj.bak（备份），则优先读取该 .bak 文件作为源（但不删除/覆盖 .bak），并将处理结果写回到 .obj（保留 .bak 不变）。
- 修改写回逻辑：如果目标 .bak 已经存在，则写回时**不再尝试用旧的 .obj 去覆盖/替换 .bak**，以保证原始 .bak 始终保留。

"""

import argparse
import os
import sys
from typing import List, Tuple

import numpy as np


# ======================= CLI 参数 =======================


def parse_args():
    p = argparse.ArgumentParser(
        description="递归修复 OBJ 语法，并处理顶点过少/几何退化的问题。"
    )
    p.add_argument(
        "root",
        nargs="?",
        default=".",
        help="扫描的根目录（默认当前目录）",
    )

    # 相对退化阈值：某轴范围 < rel_tol * max_range 视为退化
    p.add_argument(
        "--rel-tol",
        type=float,
        default=1e-4,
        help="相对退化检测阈值（默认 1e-4，相对最大轴范围）。",
    )

    # 绝对退化阈值：某轴范围 < abs_tol 也视为退化
    p.add_argument(
        "--abs-tol",
        type=float,
        default=1e-6,
        help="绝对退化检测阈值（默认 1e-6）。",
    )

    # 退化轴强制拉开的最小厚度
    p.add_argument(
        "--min-span-abs",
        type=float,
        default=1e-3,
        help="退化轴需要拉开的最小厚度（默认 1e-3）。",
    )

    # 四面体外推厚度
    p.add_argument(
        "--tetra-thickness",
        type=float,
        default=1e-3,
        help="构造四面体时沿法线外推的厚度（默认 1e-3）。",
    )

    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印将要做的修改，不真正写回文件。",
    )

    return p.parse_args()


# ======================= 文本级语法修复 =======================


def sanitize_obj_lines(raw_lines: List[str]) -> List[str]:
    """
    修复类似：
        f 3/1/2 2/2/2 1/3/2v -0.1552 ...
    拆成：
        f 3/1/2 2/2/2 1/3/2
        v -0.1552 ...

    规则：
    - 行首不是 v 开头；
    - 行中间出现 'v '；
    -> 按第一处 'v ' 切成两行。
    """
    out: List[str] = []
    for line in raw_lines:
        s = line.rstrip("\n\r")
        stripped = s.lstrip()

        if stripped.startswith("v "):
            out.append(stripped + "\n")
            continue

        idx = s.find("v ")
        if idx > 0 and not stripped.startswith("v "):
            left = s[:idx].rstrip()
            right = s[idx:].lstrip()
            if left:
                out.append(left + "\n")
            if right:
                out.append(right + "\n")
        else:
            if s == "":
                out.append("\n")
            else:
                out.append(s + "\n")

    return out


# ======================= 解析顶点 & 面 =======================


def load_obj_vertices_faces(path: str):
    """
    读取 OBJ：
    - 返回语法修复后的所有行 lines
    - 顶点数组 verts: (N, 3)
    - 顶点所在行号索引 v_line_indices
    - 面的数量 face_count
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        raw_lines = f.readlines()

    lines = sanitize_obj_lines(raw_lines)

    verts = []
    v_line_indices = []
    face_count = 0

    for i, line in enumerate(lines):
        if line.startswith("v "):
            parts = line.strip().split()
            if len(parts) < 4:
                continue
            try:
                x, y, z = map(float, parts[1:4])
            except ValueError:
                continue
            verts.append((x, y, z))
            v_line_indices.append(i)
        elif line.startswith("f "):
            face_count += 1

    if not verts:
        raise ValueError(f"在 {path} 中没有找到任何 v x y z 顶点行。")

    return lines, np.array(verts, dtype=np.float64), v_line_indices, face_count


# ======================= 退化轴检测 & 厚度拉伸 =======================


def detect_degenerate_axes(verts: np.ndarray, rel_tol: float, abs_tol: float):
    mins = verts.min(axis=0)
    maxs = verts.max(axis=0)
    ranges = maxs - mins
    max_range = ranges.max()

    deg_mask = np.zeros(3, dtype=bool)
    for i in range(3):
        if ranges[i] < abs_tol:
            deg_mask[i] = True
        elif max_range > 0 and ranges[i] < rel_tol * max_range:
            deg_mask[i] = True

    return ranges, deg_mask


def inflate_degenerate_axes(
    verts: np.ndarray,
    deg_mask: np.ndarray,
    min_span_abs: float,
) -> np.ndarray:
    """
    在退化轴上，将坐标范围拉到至少 min_span_abs。
    """
    if not deg_mask.any():
        return verts

    new_verts = verts.copy()
    mins = new_verts.min(axis=0)
    maxs = new_verts.max(axis=0)
    ranges = maxs - mins
    N = new_verts.shape[0]
    idx = np.arange(N)

    for ax in range(3):
        if not deg_mask[ax]:
            continue

        if ranges[ax] > 0:
            center = 0.5 * (mins[ax] + maxs[ax])
        else:
            center = new_verts[:, ax].mean()

        if N == 1:
            new_verts[0, ax] = center - 0.5 * min_span_abs
        else:
            t = (idx / (N - 1)) - 0.5  # [-0.5, 0.5]
            new_verts[:, ax] = center + t * min_span_abs

    return new_verts


# ======================= 四面体构造（处理唯一顶点数 < 4） =======================


def ensure_three_base_points(uniq_verts: np.ndarray) -> np.ndarray:
    """
    确保有 3 个用于构造四面体的“底面点”：
    - 若已有 3 个：直接返回
    - 若为 2 个：构造第三个点为中点 + 垂直偏移
    - 若为 1 个：构造两个偏移点
    """
    n = uniq_verts.shape[0]
    if n >= 3:
        return uniq_verts[:3]

    if n == 2:
        p1 = uniq_verts[0]
        p2 = uniq_verts[1]
        mid = 0.5 * (p1 + p2)
        # 构造一个与 p2-p1 垂直的小偏移
        v = p2 - p1
        # 找一个非平行向量
        if abs(v[0]) < abs(v[1]):
            ref = np.array([1.0, 0.0, 0.0])
        else:
            ref = np.array([0.0, 1.0, 0.0])
        nvec = np.cross(v, ref)
        nlen = np.linalg.norm(nvec) or 1.0
        nvec /= nlen
        third = mid + 0.001 * nvec  # 很小偏移
        return np.vstack([p1, p2, third])

    # n == 1
    p = uniq_verts[0]
    p1 = p + np.array([0.001, 0.0, 0.0])
    p2 = p + np.array([0.0, 0.001, 0.0])
    return np.vstack([p, p1, p2])


def make_tetra_from_points(
    base3: np.ndarray,
    thickness: float,
    mtllib_line: str = None,
) -> List[str]:
    """
    用 3 个点构造一个小四面体：
    - v1, v2, v3 为底面
    - v4 = 质心 + thickness * 法线
    返回新的 OBJ 文本行列表。
    """


    (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = base3

    ux, uy, uz = x2 - x1, y2 - y1, z2 - z1
    vx, vy, vz = x3 - x1, y3 - y1, z3 - z1
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    nlen = (nx * nx + ny * ny + nz * nz) ** 0.5 or 1.0
    nx, ny, nz = nx / nlen, ny / nlen, nz / nlen

    cx = (x1 + x2 + x3) / 3.0
    cy = (y1 + y2 + y3) / 3.0
    cz = (z1 + z2 + z3) / 3.0
    x4 = cx + nx * thickness
    y4 = cy + ny * thickness
    z4 = cz + nz * thickness

    lines = []
    if mtllib_line:
        lines.append(mtllib_line.rstrip("\n\r") + "\n")

    lines.append(f"v {x1:.8f} {y1:.8f} {z1:.8f}\n")
    lines.append(f"v {x2:.8f} {y2:.8f} {z2:.8f}\n")
    lines.append(f"v {x3:.8f} {y3:.8f} {z3:.8f}\n")
    lines.append(f"v {x4:.8f} {y4:.8f} {z4:.8f}\n")

    # 简单给两个法线（可选）
    lines.append("vn 0.000000 0.000000 1.000000\n")
    lines.append("vn 0.000000 0.000000 -1.000000\n")

    lines.append("usemtl material-0\n")
    lines.append("f 1 2 3\n")
    lines.append("usemtl material-1\n")
    lines.append("f 1 2 4\n")
    lines.append("f 2 3 4\n")
    lines.append("f 3 1 4\n")

    return lines


# ======================= 写回 OBJ（只改顶点坐标） =======================


def write_obj_inplace_simple(path: str, new_lines: List[str]):
    """
    直接用 new_lines 覆盖写回 OBJ（适用于四面体这种完全重写的情况）。
    修改：如果已经存在 path + '.bak'，则**不**用当前 path 去覆盖/替换该 .bak，
    而是直接写回 path（并保留已有的 .bak）。
    """
    backup = path + ".bak"

    # 如果没有备份，则把原始 obj 作为备份；若备份已存在，则保留它不动
    if not os.path.exists(backup) and os.path.exists(path):
        try:
            os.rename(path, backup)
        except Exception:
            # 若重命名失败（权限或其它），尝试用复制的方式保留备份
            import shutil

            shutil.copy2(path, backup)

    # 写回新的 obj 文件
    with open(path, "w", encoding="utf-8") as f:
        for line in new_lines:
            f.write(line)


def write_obj_inplace_with_verts(
    path: str,
    lines: List[str],
    verts_new: np.ndarray,
    v_line_indices: List[int],
):
    """
    保留原始结构，仅替换 v 行的坐标。

    修改：如果 path+'.bak' 已存在，则不覆盖该 bak 文件；否则在首次写入时创建 bak。
    """
    backup_path = path + ".bak"
    # 只有在没有备份且目标文件存在的情况下，才把原 obj 重命名为 bak
    if not os.path.exists(backup_path) and os.path.exists(path):
        try:
            os.rename(path, backup_path)
        except Exception:
            import shutil

            shutil.copy2(path, backup_path)

    verts_iter = iter(verts_new)
    v_line_set = set(v_line_indices)

    with open(path, "w", encoding="utf-8") as f:
        for i, line in enumerate(lines):
            if i in v_line_set and line.startswith("v "):
                x, y, z = next(verts_iter)
                f.write(f"v {x:.8f} {y:.8f} {z:.8f}\n")
            else:
                f.write(line)


# ======================= 单文件处理 =======================

def save_obj_with_perturbed_vertices(path: str, lines: list, verts: np.ndarray, v_line_indices: list):
    """
    将扰动后的 verts 写回 OBJ 文件对应的顶点行。

    Args:
        path: 原 OBJ 文件路径
        lines: 原始且修复后的 OBJ 文本行
        verts: 扰动后的顶点数组 (N, 3)
        v_line_indices: 对应 verts 的行号 index，用来替换 OBJ 中顶点部分
    """

    if len(verts) != len(v_line_indices):
        raise ValueError("verts 与 v_line_indices 数量不匹配，写回失败！")

    # 更新对应行
    for vert, line_idx in zip(verts, v_line_indices):
        x, y, z = vert
        # 按原格式写回，保留高精度
        lines[line_idx] = f"v {x:.8f} {y:.8f} {z:.8f}\n"

    # 写回文件，覆盖保存
    #new_path = path.replace(".obj", "_perturbed.obj")
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)

    print(f"✔ 已写入扰动后的 OBJ 文件：{path}")
    return path

def process_obj_file(
    path: str,
    rel_tol: float,
    abs_tol: float,
    min_span_abs: float,
    tetra_thickness: float,
    dry_run: bool,
) -> bool:
    """
    新增逻辑：如果存在 path + '.bak'，则以该 bak 文件作为**源**来加载和处理，
    但写回仍然写到 path（.obj），并保持 .bak 不被覆盖/删除。
    """
    bak_path = path + ".bak"
    source_path = path
    source_was_bak = False

    if os.path.exists(bak_path):
        # 优先读取 bak，保留 bak 不动
        source_path = bak_path
        source_was_bak = True

    try:
        lines, verts, v_idx, face_count = load_obj_vertices_faces(source_path)#默认source_path是正常的
    except ValueError as e:
        print(f"[SKIP] {path}: {e}")
        return False
    #print(f"origin_verts:{verts}")
    epsilon = 1e-4
    randomized_verts = verts + (np.random.rand(*verts.shape) - 0.5) * 2 * epsilon#强行加上扰动值
    
    save_obj_with_perturbed_vertices(path, lines, randomized_verts, v_idx)#把值最终写入path中，保持source_path不变动
    try:
        lines, verts, v_idx, face_count = load_obj_vertices_faces(path)#加载path中的信息
    except ValueError as e:
        print(f"[SKIP] {path}: {e}")
        return False
    ranges, deg_mask = detect_degenerate_axes(verts, rel_tol, abs_tol)
    #print(f"randomized:{verts}")
    mins = verts.min(axis=0)
    maxs = verts.max(axis=0)    
    print(f"\n[FILE] {path} (source: {'bak' if source_was_bak else 'obj'})")
    print(f"  顶点数: {verts.shape[0]}, 面数: {face_count}")
    print(f"  范围 X: {ranges[0]:.6g}, Y: {ranges[1]:.6g}, Z: {ranges[2]:.6g}")

    # 先看唯一顶点数
    uniq_verts = np.unique(np.round(verts, decimals=12), axis=0)
    n_uniq = uniq_verts.shape[0]
    print(f"  唯一顶点数: {n_uniq}")

    # ---------- 情况1：唯一顶点数 < 4 -> 必须造四面体，避免 "at least 4 vertices required" ----------
    if n_uniq < 4:
        print("  唯一顶点数 < 4，直接重写为小四面体，保证有体积且顶点数 >= 4。")
        base3 = ensure_three_base_points(uniq_verts)

        # 找一个 mtllib 行保留下来（如果有）
        mtllib_line = None
        for l in lines:
            if l.startswith("mtllib "):
                mtllib_line = l
                break

        tetra_lines = make_tetra_from_points(
            base3=base3,
            thickness=tetra_thickness,
            mtllib_line=mtllib_line,
        )

        if dry_run:
            print("  [DRY-RUN] 仅预览四面体替换，不写回。")
            return True

        # 写回到 path（.obj），并确保原有 bak 不被覆盖
        write_obj_inplace_simple(path, tetra_lines)
        print(f"  已重写为四面体（写回 {path}，原始 bak 保留为 {bak_path} 如果存在）。")
        return True

    # ---------- 情况2：顶点数够，但有退化轴 -> 做厚度拉伸 ----------
    if deg_mask.any():
        axes = ["X", "Y", "Z"]
        deg_axes = [axes[i] for i in range(3) if deg_mask[i]]
        print(f"  退化轴: {', '.join(deg_axes)}，使用厚度拉伸处理。")
        verts_new = inflate_degenerate_axes(verts, deg_mask, min_span_abs=min_span_abs)

        if dry_run:
            print("  [DRY-RUN] 仅预览厚度拉伸，不写回。")
            return True

        write_obj_inplace_with_verts(path, lines, verts_new, v_idx)
        print(f"  已写回文件（写回 {path}，原始 bak 保留为 {bak_path} 如果存在）。")
        return True

    # ---------- 情况3：顶点数够，且无退化轴 -> 不用动 ----------
    print("  顶点数 >= 4 且未发现明显退化轴，不做任何修改。")

    return False


# ======================= 主逻辑 =======================


def main():
    args = parse_args()

    root = os.path.abspath(args.root)
    if not os.path.exists(root):
        print(f"路径不存在: {root}")
        sys.exit(1)

    print(f"扫描根目录: {root}")
    obj_files: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        for fn in filenames:
            if fn.lower().endswith(".obj"):
                obj_files.append(os.path.join(dirpath, fn))

    if not obj_files:
        print("没有找到任何 .obj 文件。")
        return

    print(f"共找到 {len(obj_files)} 个 OBJ。")
    if args.dry_run:
        print("DRY RUN 模式：不会写回文件。\n")

    modified = 0
    for i, path in enumerate(sorted(obj_files)):
        print(f"\n=== [{i + 1}/{len(obj_files)}] {path} ===")
        if process_obj_file(
            path=path,
            rel_tol=args.rel_tol,
            abs_tol=args.abs_tol,
            min_span_abs=args.min_span_abs,
            tetra_thickness=args.tetra_thickness,
            dry_run=args.dry_run,
        ):
            modified += 1

    print("\n========== 统计 ==========")
    print(f"总 OBJ 数: {len(obj_files)}")
    print(f"做了几何/语法修改的文件数: {modified}")
    if args.dry_run:
        print("(DRY-RUN：未真正修改任何文件)")


if __name__ == "__main__":
    main()
