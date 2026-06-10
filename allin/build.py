"""
PyInstaller 打包脚本 — 将 app.py 打包为单个 exe

用法:
    python build.py              # 打包为单文件 exe
    python build.py --onedir     # 打包为文件夹（启动更快）
"""

import sys
import os
import shutil
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
BUILD_DIR = APP_DIR / "build_output"

# PyInstaller 参数
EXE_NAME = "IndexMonitor"

COMMON_ARGS = [
    "--name", EXE_NAME,
    "--clean",
    "--noconfirm",
    # 隐藏导入 (akshare/yfinance 依赖多)
    "--hidden-import", "akshare",
    "--hidden-import", "yfinance",
    "--hidden-import", "requests",
    "--hidden-import", "bs4",
    "--hidden-import", "lxml",
    "--hidden-import", "openpyxl",
    "--hidden-import", "lzma",
    "--hidden-import", "tcl",
    "--hidden-import", "tkinter",
    # 排除不必要的包减小体积
    "--exclude-module", "matplotlib",
    "--exclude-module", "numpy",
    "--exclude-module", "PIL",
    "--exclude-module", "scipy",
    "--exclude-module", "IPython",
    "--exclude-module", "jupyter",
    "--exclude-module", "notebook",
    "--exclude-module", "sqlalchemy",
    "--exclude-module", "pytest",
]

ONEFILE_ARGS = COMMON_ARGS + [
    "--onefile",
    "--windowed",
    "--add-data", f"{APP_DIR / 'config.json'}{os.pathsep}.",  # 打包后在 os.pathsep 当前目录
    "--icon", "NONE",
    f"{APP_DIR / 'app.py'}",
]

ONEDIR_ARGS = COMMON_ARGS + [
    "--onedir",
    "--windowed",
    "--add-data", f"{APP_DIR / 'config.json'}{os.pathsep}.",
    f"{APP_DIR / 'app.py'}",
]


def ensure_pyinstaller():
    try:
        import PyInstaller
    except ImportError:
        os.system(f"{sys.executable} -m pip install pyinstaller")
        import PyInstaller


def build(onedir: bool = False):
    """打包"""
    import PyInstaller.__main__

    args = ONEDIR_ARGS if onedir else ONEFILE_ARGS
    print(f"[BUILD] 开始打包 {'文件夹' if onedir else '单文件'} 模式...")
    PyInstaller.__main__.run(args)

    # 复制分发文件
    dist_dir = APP_DIR / "dist"
    output = dist_dir / EXE_NAME

    if not onedir:
        # 单文件模式，exe 直接在 dist/ 下
        exe_path = dist_dir / f"{EXE_NAME}.exe"
        if exe_path.exists():
            dest = BUILD_DIR
            dest.mkdir(exist_ok=True)
            shutil.copy2(exe_path, dest / f"{EXE_NAME}.exe")
            # 复制运行说明
            _copy_readme(dest)
            print(f"\n[DONE] 单文件已生成: {dest / f'{EXE_NAME}.exe'}")
            print(f"        大小: {_fmt_size((dest / f'{EXE_NAME}.exe').stat().st_size)}")
    else:
        if output.exists():
            dest = BUILD_DIR
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(output, dest)
            _copy_readme(dest)
            print(f"\n[DONE] 程序文件夹已生成: {dest}")
            total = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
            print(f"        大小: {_fmt_size(total)}")

    print(f"\n发送给别人只需复制 build_output 文件夹里的内容。")


def _copy_readme(dest: Path):
    readme = dest / "使用说明.txt"
    readme.write_text(
        "指数加仓提醒程序\n"
        "================\n\n"
        "使用方法：\n"
        "1. 双击 IndexMonitor.exe 启动程序\n"
        "2. 程序自动拉取指数数据并显示报告\n"
        "3. 如需修改监控指数或阈值，编辑同目录下的 config.json\n"
        "4. 点击窗口中的「刷新数据」可重新检查\n\n"
        "配置文件说明：\n"
        "- 用记事本打开 config.json\n"
        "- 修改 indices 数组里的指数名称、代码、阈值\n"
        "- 保存后重启程序即可生效\n\n"
        "注意事项：\n"
        "- 需要联网才能获取数据\n"
        "- 首次启动可能需要 5-10 秒加载\n",
        encoding="utf-8",
    )


def _fmt_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--onedir", action="store_true", help="打包为文件夹（非单文件）")
    args = parser.parse_args()

    ensure_pyinstaller()
    build(onedir=args.onedir)
