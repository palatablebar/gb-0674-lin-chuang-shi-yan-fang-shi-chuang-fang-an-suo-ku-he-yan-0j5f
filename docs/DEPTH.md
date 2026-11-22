# 深度登记 临床试验访视窗与方案锁库核验

规模：中型。使用者：临床试验数据管理员。核心规则：按入组基准计算访视半开窗，方案修订按受试者生效时间选版；漏访不可用复检伪填。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 记录采信 | 执行并复核记录采信 | `POST /api/intake` | `app/modules/intake/rules.py` | `tests/test_intake.py` |
| M2 方案版本 | 执行并复核方案版本 | `POST /api/protocol` | `app/modules/protocol/rules.py` | `tests/test_protocol.py` |
| M3 分段裁决 | 执行并复核分段裁决 | `POST /api/segment` | `app/modules/segment/rules.py` | `tests/test_segment.py` |
| M4 访视排窗 | 执行并复核访视排窗 | `POST /api/windows` | `app/modules/windows/rules.py` | `tests/test_windows.py` |
| M5 偏离复核 | 执行并复核偏离复核 | `POST /api/deviation` | `app/modules/deviation/rules.py` | `tests/test_deviation.py` |
| M6 复检裁决 | 执行并复核复检裁决 | `POST /api/retest` | `app/modules/retest/rules.py` | `tests/test_retest.py` |
| M7 锁库检查 | 执行并复核锁库检查 | `POST /api/locking` | `app/modules/locking/rules.py` | `tests/test_locking.py` |
| M8 冻结归档 | 执行并复核冻结归档 | `POST /api/archive` | `app/modules/archive/rules.py` | `tests/test_archive.py` |

## 陷阱登记

| TRAP | 现象 | 朴素实现 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-01 | 旧编码检验单位 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_legacy_real` |
| TRAP-02 | BOM表头 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_bom_real` |
| TRAP-08 | 受试者前导零 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_leading_zero_real` |
| TRAP-04 | 分段表头 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_header_real` |
| TRAP-05 | 缺列记录 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_columns_real` |
| TRAP-18 | 空态 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/intake/rules.py` | `tests/test_intake.py::test_empty_types` |
| TRAP-07 | 缺失检验值 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/protocol/rules.py` | `tests/test_protocol.py::test_sentinel_real` |
| TRAP-25 | 个体方案生效重叠 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/protocol/rules.py` | `tests/test_protocol.py::test_overlap_assignment` |
| TRAP-15 | 检验单位换算 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/protocol/rules.py` | `tests/test_protocol.py::test_unit_conversion_real` |
| TRAP-23 | 访视窗末端 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/windows/rules.py` | `tests/test_windows.py::test_half_open_end` |
| TRAP-11 | UTC日历归一 | 静默错算或证据丢失 | 以可复核规则显式处理 | `app/modules/windows/rules.py` | `tests/test_windows.py::test_utc_day_equivalence` |
| TRAP-31 | 分段访视跨方案切换 | 整次算首日沿用旧版，或拆两次重复占窗 | 取补完时刻定版，合并只占一个应访视 | `app/modules/segment/rules.py` | `tests/test_segment.py::test_adopted_date_and_version` |
| TRAP-32 | 分段缺任一段依据 | 静默错算或证据丢失 | 继续阻断且不重复计缺失 | `app/modules/segment/rules.py` | `tests/test_segment.py::test_missing_segment_keeps_blocking` |
| TRAP-33 | 分段版本替换失败 | 静默错算或证据丢失 | 保留首段版本正式结论并标注回退 | `app/modules/segment/rules.py` | `tests/test_segment.py::test_version_fallback_keeps_formal_conclusion` |
| TRAP-34 | 分段重跑与上游补正 | 重复生成应访视或旧结论被误改 | 同输入同批号，补正另起新批，失败保留旧批 | `app/engine.py` | `tests/test_segment.py::test_rerun_same_segment_no_duplicate` |

## 对账规则

原始逻辑输入=采纳行+隔离行+空行+重复表头+同值重复。业务计算按 DATA-DICTIONARY.md 分别核验，不能把上级与下级重复加总。所有隔离保留编号、原值、原始行号和稳定原因码。

## 已知不覆盖

数据来自仓内样例或用户粘贴文件，不连接外部业务生产系统。平台不执行实际资金划转或行政审批。
