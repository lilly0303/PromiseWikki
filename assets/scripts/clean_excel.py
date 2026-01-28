import pandas as pd
import re
import os
import sys

def parse_md_line(line):
    """解析单行 Markdown 表格，清理并返回单元格内容列表"""
    if not line.strip().startswith('|'):
        return None
    cells = [cell.strip() for cell in line.strip()[1:-1].split('|')]
    return cells

def is_separator_line(line):
    """判断是否为 Markdown 表格的分割线"""
    return re.match(r'^\s*\|[:\s-]*\|', line) is not None

def extract_tables_from_md(file_path):
    """从 Markdown 文件中提取所有表格"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"读取文件时出错：{e}")
        return None

    tables = []
    in_table = False
    current_header = []
    current_data = []

    for line in lines:
        if is_separator_line(line):
            if not in_table and current_header:
                in_table = True
            continue

        parsed_cells = parse_md_line(line)

        if parsed_cells is None:
            if in_table:
                if current_header and current_data:
                    tables.append({"header": current_header, "data": current_data})
                in_table = False
                current_header = []
                current_data = []
            continue

        if not in_table:
            current_header = parsed_cells
        else:
            while len(parsed_cells) < len(current_header):
                parsed_cells.append('')
            current_data.append(parsed_cells[:len(current_header)])
            
    if in_table and current_header and current_data:
        tables.append({"header": current_header, "data": current_data})

    return tables

def write_tables_to_excel(tables, output_path):
    """将表格列表写入 Excel 文件"""
    try:
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            for i, table in enumerate(tables):
                sheet_name = f'表格_{i + 1}'
                df = pd.DataFrame(table['data'], columns=table['header'])
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        print(f"🎉 成功！已将 {len(tables)} 个表格写入到 '{output_path}'")
    except Exception as e:
        print(f"写入 Excel 文件时出错：{e}")

def main():
    """主函数，处理输入和执行流程"""
    try:
        print("--- Markdown 表格转 Excel 工具 (支持拖拽) ---")
        
        md_file = ""
        # 核心功能1: 实现拖拽文件输入
        if len(sys.argv) > 1:
            # 如果脚本是通过拖拽文件运行的，文件路径会作为命令行参数传入
            md_file = sys.argv[1]
            print(f"\n已通过拖拽方式载入文件: {md_file}")
        else:
            # 如果是双击运行，则提示用户拖入或输入路径
            md_file = input("请将 Markdown 文件拖入此窗口后按 Enter, 或手动输入路径: ").strip().strip('"')

        if not md_file or not os.path.exists(md_file):
            print(f"错误：文件路径 '{md_file}' 无效或文件不存在。")
            return

        # 生成输出文件名
        base_name = os.path.splitext(md_file)[0]
        excel_file = f"{base_name}_converted.xlsx"

        print(f"\n🔍 正在从 '{md_file}' 中查找表格...")
        extracted_tables = extract_tables_from_md(md_file)

        if extracted_tables is None or not extracted_tables:
            print("未在文件中找到有效的 Markdown 表格。")
            return
            
        print(f"👍 找到了 {len(extracted_tables)} 个表格。")

        print(f"✍️ 正在写入到 '{excel_file}'...")
        write_tables_to_excel(extracted_tables, excel_file)

    except Exception as e:
        # 捕获任何意外错误，确保程序不会直接崩溃退出
        print(f"\n发生了一个未知错误: {e}")
    finally:
        # 核心功能2: 保证程序在退出前会暂停
        print("-" * 35)
        input("按 Enter 键退出...")

if __name__ == '__main__':
    main()