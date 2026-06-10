#!/usr/bin/env python3
"""
指数加仓提醒程序 - 命令行入口

用法:
    python main.py              # 使用默认 config.json
    python main.py -c my.json   # 指定配置文件
    python main.py --dry-run    # 强制运行（忽略交易日检查）
"""

import sys
import os
import argparse
import logging
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core import (
    load_config, fetch_all_indices, generate_report,
    is_weekend, is_trading_day,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("index_monitor")


def main():
    parser = argparse.ArgumentParser(description="指数加仓提醒程序")
    parser.add_argument("-c", "--config", default="config.json", help="配置文件路径")
    parser.add_argument("--dry-run", action="store_true", help="强制运行，跳过交易日检查")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = Path(__file__).resolve().parent / config_path

    log.info(f"加载配置: {config_path}")
    config = load_config(str(config_path))

    today = date.today()
    if not args.dry_run:
        if is_weekend(today):
            log.info(f"今天是周末 ({today})，跳过检查")
            return
        if not is_trading_day(today):
            log.info(f"今天是非交易日 ({today})，跳过检查")
            return
    else:
        log.info("Dry-run 模式，跳过交易日检查")

    results = fetch_all_indices(config)
    for r in results:
        if "error" in r:
            log.warning(f"  {r['name']}: {r['error']}")
        else:
            log.info(f"  {r['name']}: 回撤 {r['drawdown_pct']:.2f}%")

    report = generate_report(results, config)
    print(report)

    output_cfg = config.get("output", {})
    if output_cfg.get("save_to_file", False):
        output_dir = Path(output_cfg.get("output_dir", "./reports"))
        if not output_dir.is_absolute():
            output_dir = Path(__file__).resolve().parent / output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / f"report_{today.strftime('%Y%m%d')}.txt"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        log.info(f"报告已保存: {report_path}")


if __name__ == "__main__":
    main()
