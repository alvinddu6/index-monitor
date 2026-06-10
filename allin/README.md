# 指数加仓提醒程序

在交易日自动获取指定指数的实时净值，计算回撤幅度，判断是否触发加仓条件。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

可选依赖（用于精确交易日历判断）：
```bash
pip install chinese_calendar
```

### 2. 修改配置

编辑 `config.json`，按需修改监控的指数和阈值：

```json
{
  "indices": [
    {
      "name": "沪深300",
      "code": "000300",
      "market": "a_share",
      "symbol": "sh000300",
      "thresholds": {
        "轻度补仓": 10,
        "中度补仓": 20,
        "深度补仓": 30
      }
    }
  ],
  "lookback_months": 6,
  "output": {
    "console": true,
    "save_to_file": true,
    "output_dir": "./reports"
  }
}
```

**配置说明**：

| 字段 | 说明 |
|------|------|
| `name` | 指数显示名称 |
| `code` | 指数标识代码 |
| `market` | 市场类型：`a_share`（A股）/ `us`（美股） |
| `symbol` | 数据源查询代码 |
| `thresholds` | 分级加仓阈值（%） |
| `lookback_months` | 回看月数，默认 6 |
| `output.save_to_file` | 是否保存报告到文件 |

**常用指数代码**：

| 指数 | market | symbol |
|------|--------|--------|
| 沪深300 | a_share | sh000300 |
| 中证500 | a_share | sh000905 |
| 创业板指 | a_share | sz399006 |
| 上证50 | a_share | sh000016 |
| 纳斯达克100 | us | ^NDX |
| 标普500 | us | ^GSPC |
| 道琼斯工业 | us | ^DJI |

### 3. 手动运行

```bash
python main.py
```

跳过交易日检查强制运行：
```bash
python main.py --dry-run
```

## 设置定时任务

### Windows（任务计划程序）

1. 打开"任务计划程序"
2. 创建基本任务 → 触发器设为"每天"，时间 **14:30**
3. 操作 → 启动程序：`python`，参数：`main.py`，起始于：程序目录路径

或使用命令行创建：
```cmd
schtasks /create /tn "IndexMonitor" /tr "python D:\path\to\main.py" /sc daily /st 14:30
```

### macOS（launchd）

创建 `~/Library/LaunchAgents/com.index.monitor.plist`：
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.index.monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/main.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>14</integer>
        <key>Minute</key><integer>30</integer>
    </dict>
    <key>WorkingDirectory</key>
    <string>/path/to/project</string>
</dict>
</plist>
```

加载任务：
```bash
launchctl load ~/Library/LaunchAgents/com.index.monitor.plist
```

### Linux（crontab）

```bash
crontab -e
```

添加：
```
30 14 * * 1-5 cd /path/to/project && python main.py >> logs/monitor.log 2>&1
```

## 输出示例

```
[2026-06-09] 指数加仓检查报告
============================================================

一、今日数据与回撤计算

■ 沪深300 (000300) — A股
  近6个月最高点：5,030.52（2026-05-14）
  今日净值：4,801.81，较前日变化 +1.87%
  今日回撤幅度：4.55%

■ 纳斯达克100 (NDX) — 美股
  近6个月最高点：30,762.20（2026-06-03）
  今日净值：29,414.26，较前日变化 +1.58%
  今日回撤幅度：4.38%

二、补仓决策汇总

+-------------+----------+----------+----------+----------+----------+
|    市场     | 当前回撤 | 轻度补仓 | 中度补仓 | 深度补仓 | 是否补仓 |
+-------------+----------+----------+----------+----------+----------+
|   沪深300   |  4.55%   |    —     |    —     |    —     |    否    |
| 纳斯达克100 |  4.38%   |    —     |    —     |    —     |    否    |
+-------------+----------+----------+----------+----------+----------+

三、操作建议

今日各指数回撤幅度均未达到补仓标准，建议保持不动，继续机械定投。

  · 沪深300：需回撤达 10% 以上（约 4,527.47 点附近）触发 轻度补仓
  · 纳斯达克100：需回撤达 10% 以上（约 27,685.98 点附近）触发 轻度补仓

一句话总结：今天不用动，继续机械定投即可。
```

触发加仓时，报告会在第二部分表格中标注 "⚠ 触发"，并在操作建议中给出具体加仓指示。

## 常见问题

**Q: akshare 安装或运行报错？**
A: akshare 依赖较多，确保 Python ≥ 3.9，可尝试 `pip install akshare --upgrade`。

**Q: 美股数据获取失败？**
A: yfinance 可能被网络限制，可尝试设置代理或更换为 akshare 的美股接口。

**Q: 无法判断法定假日？**
A: 安装 `pip install chinese_calendar` 即可精确判断 A 股交易日。
