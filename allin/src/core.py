"""
指数加仓提醒 - 核心业务逻辑
数据获取 / 回撤计算 / 报告生成
"""

import json
import sys
import time
import logging
import unicodedata
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger("index_monitor")


# ══════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════

DEFAULT_CONFIG = {
    "indices": [
        {"name": "沪深300", "code": "000300", "market": "a_share", "symbol": "sh000300",
         "thresholds": {"轻度补仓": 10, "中度补仓": 20, "深度补仓": 30}},
        {"name": "纳斯达克100", "code": "NDX", "market": "us", "symbol": "^NDX",
         "thresholds": {"轻度补仓": 10, "中度补仓": 20, "深度补仓": 30}},
        {"name": "黄金9999", "code": "Au99.99", "market": "gold", "symbol": "Au99.99",
         "thresholds": {"轻度补仓": 5, "中度补仓": 10, "深度补仓": 15}},
    ],
    "lookback_months": 6,
    "output": {"console": True, "save_to_file": True, "output_dir": "./reports"},
    "retry": {"max_attempts": 3, "delay_seconds": 5},
}


def _get_app_dir() -> Path:
    """获取 exe/脚本 所在目录（用户可编辑配置文件的位置）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    else:
        return Path(__file__).resolve().parent.parent


def _get_bundle_dir() -> Optional[Path]:
    """获取 PyInstaller 打包后的内置资源目录 (_MEIPASS)"""
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', None)
        if base:
            return Path(base)
    return None


def _sync_default_config(user_config_path: Path):
    """如果用户目录没有 config.json，从内置资源（或默认值）复制一份"""
    if user_config_path.exists():
        return

    # 尝试从 PyInstaller bundle 复制
    bundled = _get_bundle_dir()
    if bundled and (bundled / "config.json").exists():
        import shutil
        shutil.copy2(bundled / "config.json", user_config_path)
        logger.info(f"已从内置资源复制配置文件至: {user_config_path}")
        return

    # 都没有，生成默认配置
    user_config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(user_config_path, "w", encoding="utf-8") as f:
        json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    logger.info(f"已生成默认配置文件: {user_config_path}")


def load_config(config_path: str = "config.json") -> dict:
    path = Path(config_path)
    if not path.is_absolute():
        path = _get_app_dir() / config_path
    _sync_default_config(path)
    with open(path, "r", encoding="utf-8") as f:
        config = json.load(f)
    _validate_config(config)
    return config


def _validate_config(config: dict):
    if "indices" not in config or not config["indices"]:
        raise ValueError("配置中未定义任何监控指数 (indices 为空)")
    for idx in config["indices"]:
        for field in ["name", "market", "symbol", "thresholds"]:
            if field not in idx:
                raise ValueError(f"指数配置缺少必需字段 '{field}': {idx.get('name', '未知')}")
        if not idx.get("thresholds"):
            raise ValueError(f"指数 '{idx['name']}' 未设置任何阈值")


# ══════════════════════════════════════════════════════════════
# Display Width Helper (CJK alignment)
# ══════════════════════════════════════════════════════════════

def display_width(s: str) -> int:
    w = 0
    for ch in s:
        ea = unicodedata.east_asian_width(ch)
        w += 2 if ea in ("W", "F") else 1
    return w


def pad_to_width(s: str, target: int, align: str = "left") -> str:
    current = display_width(s)
    diff = target - current
    if diff <= 0:
        return s
    if align == "left":
        return s + " " * diff
    elif align == "right":
        return " " * diff + s
    else:
        left = diff // 2
        return " " * left + s + " " * (diff - left)


# ══════════════════════════════════════════════════════════════
# Retry helper
# ══════════════════════════════════════════════════════════════

def retry(func, max_attempts: int = 3, delay: float = 5.0, label: str = ""):
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            result = func()
            if result is not None:
                return result
            logger.warning(f"{label} 第 {attempt} 次返回空数据")
        except Exception as e:
            last_err = e
            logger.warning(f"{label} 第 {attempt} 次失败: {e}")
        if attempt < max_attempts:
            time.sleep(delay)
    logger.error(f"{label} 重试 {max_attempts} 次后仍失败: {last_err}")
    return None


# ══════════════════════════════════════════════════════════════
# A-Share Data (akshare)
# ══════════════════════════════════════════════════════════════

def fetch_a_share_history(symbol: str, lookback_months: int) -> Optional[pd.DataFrame]:
    import akshare as ak

    def _fetch():
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or df.empty:
            return None
        # find date column
        date_col = None
        for c in df.columns:
            if "date" in str(c).lower() or "日期" in str(c):
                date_col = c
                break
        if date_col is None:
            return None
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)
        cutoff = datetime.now() - timedelta(days=lookback_months * 31)
        df = df[df[date_col] >= cutoff]
        # normalize column names
        col_map = {}
        for c in df.columns:
            cl = str(c).lower().strip()
            if cl in ("date", "日期"): col_map[c] = "date"
            elif cl in ("open", "开盘"): col_map[c] = "open"
            elif cl in ("high", "最高"): col_map[c] = "high"
            elif cl in ("low", "最低"): col_map[c] = "low"
            elif cl in ("close", "收盘"): col_map[c] = "close"
        df = df.rename(columns=col_map)
        return df

    return retry(_fetch, label=f"[{symbol}] 历史数据")


def fetch_a_share_current(symbol: str) -> Optional[tuple]:
    import akshare as ak

    def _fetch():
        spot_df = None
        for func_name in ["stock_zh_index_spot_em", "stock_zh_index_spot_sina"]:
            try:
                fn = getattr(ak, func_name, None)
                if fn:
                    spot_df = fn()
                    if spot_df is not None and not spot_df.empty:
                        break
            except Exception:
                continue

        if spot_df is None or spot_df.empty:
            return None

        code_col = None
        for col_name in ["代码", "名称", "name", "code"]:
            if col_name in spot_df.columns:
                code_col = col_name
                break
        if code_col is None:
            code_col = spot_df.columns[0]

        clean_symbol = symbol.replace("sh", "").replace("sz", "").replace("^", "")
        for _, row in spot_df.iterrows():
            if clean_symbol in str(row.get(code_col, "")):
                current = 0
                for price_col in ["最新价", "当前", "current", "price"]:
                    if price_col in spot_df.columns:
                        current = float(row[price_col])
                        if current > 0:
                            break
                if current == 0:
                    for c in spot_df.columns:
                        try:
                            v = float(row[c])
                            if 0 < v < 100000:
                                current = v
                                break
                        except (ValueError, TypeError):
                            continue

                prev_close = 0
                for pc_col in ["昨收", "前收", "previous_close"]:
                    if pc_col in spot_df.columns:
                        prev_close = float(row[pc_col])
                        break

                if current > 0:
                    return (current, prev_close if prev_close > 0 else current)
        return None

    return retry(_fetch, label=f"[{symbol}] 实时数据")


# ══════════════════════════════════════════════════════════════
# US Stock Data (akshare sina → yfinance fallback)
# ══════════════════════════════════════════════════════════════

def _yf_ticker(symbol: str):
    import yfinance as yf
    import requests

    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    })
    return yf.Ticker(symbol, session=session)


def fetch_us_history(symbol: str, lookback_months: int) -> Optional[pd.DataFrame]:
    sina_symbol = symbol.replace("^", ".")
    yf_symbol = symbol if symbol.startswith("^") else symbol

    def _fetch_sina():
        import akshare as ak
        df = ak.index_us_stock_sina(symbol=sina_symbol)
        if df is None or df.empty:
            return None
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        cutoff = datetime.now() - timedelta(days=lookback_months * 31)
        df = df[df["date"] >= cutoff]
        return df

    result = retry(_fetch_sina, max_attempts=2, delay=3, label=f"[{symbol}] sina历史")
    if result is not None:
        return result

    logger.info(f"[{symbol}] sina 不可用，尝试 yfinance")
    import yfinance as yf

    def _fetch_yf():
        ticker = _yf_ticker(yf_symbol)
        df = ticker.history(period=f"{lookback_months}mo")
        if df is None or df.empty:
            return None
        df = df.reset_index()
        col_map = {c: str(c).lower().strip() for c in df.columns}
        col_map = {k: v for k, v in col_map.items() if v in ("date", "open", "high", "low", "close")}
        df = df.rename(columns=col_map)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        return df

    return retry(_fetch_yf, max_attempts=2, delay=8, label=f"[{symbol}] yf历史")


def fetch_us_current(symbol: str) -> Optional[tuple]:
    sina_symbol = symbol.replace("^", ".")
    yf_symbol = symbol if symbol.startswith("^") else symbol

    def _fetch_sina():
        import akshare as ak
        df = ak.index_us_stock_sina(symbol=sina_symbol)
        if df is None or df.empty:
            return None
        closes = df["close"].values
        if len(closes) >= 2:
            return (float(closes[-1]), float(closes[-2]))
        elif len(closes) == 1:
            return (float(closes[-1]), float(closes[-1]))
        return None

    result = retry(_fetch_sina, max_attempts=2, delay=3, label=f"[{symbol}] sina实时")
    if result is not None:
        return result

    logger.info(f"[{symbol}] sina 实时不可用，尝试 yfinance")
    import yfinance as yf

    def _fetch_yf():
        ticker = _yf_ticker(yf_symbol)
        hist = ticker.history(period="5d")
        if hist is not None and not hist.empty:
            current = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) >= 2 else current
            return (current, prev_close)
        info = ticker.info or {}
        current = info.get("regularMarketPrice") or info.get("currentPrice") or info.get("previousClose")
        if current is not None:
            prev_close = info.get("previousClose") or current
            return (float(current), float(prev_close))
        return None

    return retry(_fetch_yf, max_attempts=2, delay=8, label=f"[{symbol}] yf实时")


# ══════════════════════════════════════════════════════════════
# Gold / Commodity Data (akshare SGE)
# ══════════════════════════════════════════════════════════════

def fetch_gold_history(symbol: str, lookback_months: int) -> Optional[pd.DataFrame]:
    """获取上海金交所黄金现货日线数据（含 date/open/high/low/close）"""
    import akshare as ak

    def _fetch():
        df = ak.spot_hist_sge(symbol=symbol)
        if df is None or df.empty:
            return None
        # 列名已是标准: date, open, close, low, high
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        cutoff = datetime.now() - timedelta(days=lookback_months * 31)
        df = df[df["date"] >= cutoff]
        return df

    return retry(_fetch, max_attempts=2, delay=3, label=f"[{symbol}] 黄金历史")


def fetch_gold_current(symbol: str) -> Optional[tuple]:
    """获取黄金现货最新价，返回 (当前价, 前日收盘价)。
    从 spot_hist_sge 取最近两日数据即可。"""
    import akshare as ak

    def _fetch():
        df = ak.spot_hist_sge(symbol=symbol)
        if df is None or df.empty:
            return None
        closes = df["close"].values
        if len(closes) >= 2:
            return (float(closes[-1]), float(closes[-2]))
        elif len(closes) == 1:
            return (float(closes[-1]), float(closes[-1]))
        return None

    return retry(_fetch, max_attempts=2, delay=3, label=f"[{symbol}] 黄金实时")


# ══════════════════════════════════════════════════════════════
# Analysis
# ══════════════════════════════════════════════════════════════

def analyze_index(history_df: pd.DataFrame, current_price: float,
                  prev_close: Optional[float] = None,
                  lookback_months: int = 6) -> dict:
    result = {}

    if "high" not in history_df.columns:
        if "close" in history_df.columns:
            price_col = "close"
            result["price_source"] = "收盘价（无最高价数据）"
        else:
            result["error"] = "历史数据缺少必要列 (high/close)"
            return result
    else:
        price_col = "high"

    high_row = history_df.loc[history_df[price_col].idxmax()]
    result["high_6m"] = round(float(high_row[price_col]), 2)
    result["high_date"] = pd.Timestamp(high_row["date"]).strftime("%Y-%m-%d") if "date" in history_df.columns else "未知"
    result["current_price"] = round(current_price, 2)
    result["data_days"] = len(history_df)

    expected_days = lookback_months * 21
    if result["data_days"] < expected_days * 0.7:
        result["data_warning"] = f"历史数据仅 {result['data_days']} 个交易日（不足 6 个月），以实际数据计算"

    result["drawdown_pct"] = round((result["high_6m"] - current_price) / result["high_6m"] * 100, 2) if result["high_6m"] > 0 else 0.0

    if prev_close and prev_close > 0:
        result["change_pct"] = round((current_price - prev_close) / prev_close * 100, 2)
        result["prev_close"] = round(prev_close, 2)

    return result


# ══════════════════════════════════════════════════════════════
# Trading Day Check
# ══════════════════════════════════════════════════════════════

def is_weekend(check_date: date = None) -> bool:
    if check_date is None:
        check_date = date.today()
    return check_date.weekday() >= 5


def is_trading_day(check_date: date = None) -> bool:
    if check_date is None:
        check_date = date.today()
    if is_weekend(check_date):
        return False
    try:
        from chinese_calendar import is_workday
        return is_workday(check_date)
    except ImportError:
        pass
    try:
        import exchange_calendars as ec
        xshg = ec.get_calendar("XSHG")
        return xshg.is_session(str(check_date))
    except ImportError:
        pass
    return True


# ══════════════════════════════════════════════════════════════
# Data pipeline: config → fetch → analyze
# ══════════════════════════════════════════════════════════════

def fetch_data_for_index(idx_cfg: dict, lookback_months: int, retry_cfg: dict) -> dict:
    name = idx_cfg["name"]
    market = idx_cfg["market"]
    symbol = idx_cfg["symbol"]
    code = idx_cfg.get("code", symbol)

    base = {"name": name, "code": code, "market": market}

    if market == "a_share":
        history = fetch_a_share_history(symbol, lookback_months)
        current = fetch_a_share_current(symbol)
    elif market == "us":
        history = fetch_us_history(symbol, lookback_months)
        current = fetch_us_current(symbol)
    elif market == "gold":
        history = fetch_gold_history(symbol, lookback_months)
        current = fetch_gold_current(symbol)
    else:
        base["error"] = f"不支持的市场类型: {market}"
        return base

    if history is None or history.empty:
        base["error"] = "无法获取历史数据"
        return base

    if current is None:
        if "close" in history.columns:
            fallback_price = float(history["close"].iloc[-1])
            prev_close = float(history["close"].iloc[-2]) if len(history) >= 2 else fallback_price
            current = (fallback_price, prev_close)
            base["price_note"] = "（使用最近收盘价，实时数据不可用）"
        else:
            base["error"] = "无法获取当前净值且无历史收盘价兜底"
            return base

    current_price, prev_close = current[0], current[1]
    result = analyze_index(history, current_price, prev_close, lookback_months)
    result.update(base)
    if base.get("price_note"):
        result["price_note"] = base["price_note"]
    return result


def fetch_all_indices(config: dict) -> list:
    """拉取配置中所有指数的数据，返回结果列表"""
    lookback = config.get("lookback_months", 6)
    retry_cfg = config.get("retry", {"max_attempts": 3, "delay_seconds": 5})
    results = []
    for idx_cfg in config["indices"]:
        results.append(fetch_data_for_index(idx_cfg, lookback, retry_cfg))
    return results


# ══════════════════════════════════════════════════════════════
# Report Generation
# ══════════════════════════════════════════════════════════════

def format_price(val: float) -> str:
    return f"{val:,.2f}"


def format_pct(val: float) -> str:
    return f"{val:+.2f}%" if val >= 0 else f"{val:.2f}%"


def generate_report(results: list, config: dict) -> str:
    today_str = datetime.now().strftime("%Y-%m-%d")
    lines = []
    sep = "=" * 60

    lines.append(f"[{today_str}] 指数加仓检查报告")
    lines.append(sep)
    lines.append("")

    # ── 一、今日数据与回撤计算 ──
    lines.append("一、今日数据与回撤计算")
    lines.append("")

    for r in results:
        name = r.get("name", "未知")
        code = r.get("code", "")
        market = r.get("market", "")

        if "error" in r:
            lines.append(f"■ {name} ({code}) — 数据获取失败: {r['error']}")
            lines.append("")
            continue

        market_label = {"a_share": "A股", "us": "美股", "hk": "港股", "gold": "黄金"}.get(market, market)
        lines.append(f"■ {name} ({code}) — {market_label}")

        if r.get("data_warning"):
            lines.append(f"  ⚠ {r['data_warning']}")

        lines.append(f"  近6个月最高点：{format_price(r['high_6m'])}（{r.get('high_date', '未知')}）")

        if r.get("change_pct") is not None:
            lines.append(f"  今日净值：{format_price(r['current_price'])}，较前日变化 {format_pct(r['change_pct'])}")
        else:
            lines.append(f"  最新净值：{format_price(r['current_price'])}")

        lines.append(f"  今日回撤幅度：{r['drawdown_pct']:.2f}%")
        lines.append("")

    # ── 二、补仓决策汇总 ──
    lines.append("二、补仓决策汇总")
    lines.append("")

    all_thresholds = []
    for idx_cfg in config["indices"]:
        for label in idx_cfg.get("thresholds", {}):
            if label not in all_thresholds:
                all_thresholds.append(label)

    if not all_thresholds:
        lines.append("（未配置阈值）")
        lines.append("")
    else:
        header = ["市场", "当前回撤"] + all_thresholds + ["是否补仓"]
        all_rows = [header]

        for r in results:
            name = r.get("name", "未知")
            idx_cfg = next((i for i in config["indices"] if i["name"] == name), None)
            thresholds = idx_cfg.get("thresholds", {}) if idx_cfg else {}

            if "error" in r:
                row = [name, "N/A"] + ["—"] * (len(all_thresholds) + 1)
            else:
                drawdown_str = f"{r['drawdown_pct']:.2f}%"
                row = [name, drawdown_str]
                triggered_any = False
                for t_label in all_thresholds:
                    threshold_val = thresholds.get(t_label, float("inf"))
                    if r.get("drawdown_pct", 0) >= threshold_val:
                        row.append("⚠ 触发")
                        triggered_any = True
                    else:
                        row.append("—")
                row.append("是 ⚠" if triggered_any else "否")
            all_rows.append(row)

        col_widths = []
        for ci in range(len(header)):
            max_w = max(display_width(str(row[ci])) for row in all_rows)
            col_widths.append(max(max_w + 2, 8))

        def fmt_row(cells):
            return "| " + " | ".join(
                pad_to_width(str(cells[i]), col_widths[i] - 2, "center") for i in range(len(cells))
            ) + " |"

        def fmt_sep():
            return "+" + "+".join("-" * w for w in col_widths) + "+"

        lines.append(fmt_sep())
        lines.append(fmt_row(header))
        lines.append(fmt_sep())
        for i in range(len(results)):
            lines.append(fmt_row(all_rows[i + 1]))
        lines.append(fmt_sep())
        lines.append("")

    # ── 三、操作建议 ──
    lines.append("三、操作建议")
    lines.append("")

    triggered = [r for r in results if "error" not in r and "drawdown_pct" in r]
    any_triggered = False

    for r in triggered:
        name = r["name"]
        idx_cfg = next((i for i in config["indices"] if i["name"] == name), None)
        if idx_cfg is None:
            continue
        thresholds = idx_cfg.get("thresholds", {})
        dd = r.get("drawdown_pct", 0)
        for t_label, t_val in sorted(thresholds.items(), key=lambda x: x[1]):
            if dd >= t_val:
                any_triggered = True
                trigger_price = round(r["high_6m"] * (1 - t_val / 100), 2)
                lines.append(f"  ⚠ {name} 已达 {t_label} 条件（≥{t_val}%），当前回撤 {dd:.2f}%，对应点位约 {format_price(trigger_price)}")

    if any_triggered:
        lines.append("")
        lines.append("建议按补仓计划执行加仓操作，注意控制仓位。")
    else:
        lines.append("今日各指数回撤幅度均未达到补仓标准，建议保持不动，继续机械定投。")
        lines.append("")
        for r in triggered:
            name = r["name"]
            idx_cfg = next((i for i in config["indices"] if i["name"] == name), None)
            if idx_cfg:
                t_vals = idx_cfg.get("thresholds", {})
                if t_vals:
                    min_t = min(t_vals.values())
                    target_price = round(r["high_6m"] * (1 - min_t / 100), 2)
                    threshold_label = next(
                        (k for k, v in t_vals.items() if v == min_t), f"{min_t}%"
                    )
                    lines.append(f"  · {name}：需回撤达 {min_t}% 以上（约 {format_price(target_price)} 点附近）触发 {threshold_label}")

    lines.append("")
    lines.append("一句话总结：" + (
        "按补仓计划执行加仓操作。" if any_triggered else "今天不用动，继续机械定投即可。"
    ))
    lines.append("")

    return "\n".join(lines)


def generate_report_json(results: list, config: dict) -> dict:
    """生成结构化 JSON 报告，供前端渲染"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 收集所有阈值标签
    all_thresholds = []
    for idx_cfg in config["indices"]:
        for label in idx_cfg.get("thresholds", {}):
            if label not in all_thresholds:
                all_thresholds.append(label)

    indices_data = []
    any_triggered = False

    for r in results:
        name = r.get("name", "未知")
        code = r.get("code", "")
        market = r.get("market", "")
        market_label = {"a_share": "A股", "us": "美股", "hk": "港股", "gold": "黄金"}.get(market, market)

        item = {
            "name": name,
            "code": code,
            "market": market_label,
            "error": r.get("error"),
            "data_warning": r.get("data_warning"),
            "high_6m": r.get("high_6m"),
            "high_date": r.get("high_date"),
            "current_price": r.get("current_price"),
            "drawdown_pct": r.get("drawdown_pct"),
            "change_pct": r.get("change_pct"),
            "price_note": r.get("price_note"),
            "triggered": [],
        }

        if "error" not in r and "drawdown_pct" in r:
            idx_cfg = next((i for i in config["indices"] if i["name"] == name), None)
            thresholds = idx_cfg.get("thresholds", {}) if idx_cfg else {}
            dd = r.get("drawdown_pct", 0)

            for t_label in all_thresholds:
                t_val = thresholds.get(t_label, float("inf"))
                triggered = dd >= t_val
                item["triggered"].append({
                    "label": t_label,
                    "threshold": t_val,
                    "hit": triggered,
                    "target_price": round(r["high_6m"] * (1 - t_val / 100), 2) if r.get("high_6m") else None,
                })
                if triggered:
                    any_triggered = True

        indices_data.append(item)

    # 操作建议
    suggestions = []
    for item in indices_data:
        if item["error"]:
            continue
        hit_triggers = [t for t in item["triggered"] if t["hit"]]
        if hit_triggers:
            suggestions.append({
                "name": item["name"],
                "action": "补仓",
                "details": [f"已达 {t['label']} 条件（≥{t['threshold']}%），当前回撤 {item['drawdown_pct']:.2f}%，对应点位约 {t['target_price']:,.2f}" for t in hit_triggers],
            })
        else:
            t_vals = sorted([t for t in item["triggered"] if t["threshold"] > 0], key=lambda x: x["threshold"])
            next_target = t_vals[0] if t_vals else None
            suggestions.append({
                "name": item["name"],
                "action": "观望",
                "next_target": next_target["target_price"] if next_target else None,
                "next_label": next_target["label"] if next_target else None,
                "next_threshold": next_target["threshold"] if next_target else None,
            })

    summary = "按补仓计划执行加仓操作。" if any_triggered else "今天不用动，继续机械定投即可。"

    return {
        "date": today_str,
        "time": now_str,
        "indices": indices_data,
        "suggestions": suggestions,
        "summary": summary,
        "any_triggered": any_triggered,
        "threshold_labels": all_thresholds,
    }
