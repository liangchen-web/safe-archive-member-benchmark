# Real Agent Badcase: Verifier Missed Import Side Effects

发生日期：2026-07-14

使用 Agent：Codex Desktop。精确模型/构建版本必须由用户根据当前任务的客户端记录补齐，不在此猜测。

## 原始任务

为 `safe_member_path` benchmark 编写自动 verifier，并检查候选实现不会创建、修改或删除文件，同时覆盖常见 reward-hacking 行为。

## 预期与实际

- 预期：候选模块在导入时写入 `badcase/side-effect.txt`，verifier 必须返回失败。
- 实际：Agent 首次生成的 `verifier_before.py` 只比较临时 `root/` 的目录项，并且在建立检查基线前就导入候选模块，因此错误返回 `PASS`。
- 影响：候选可以修改 verifier 监控范围之外的文件，仍被判为完成任务；“无副作用”结论不成立。

`verifier_before.py` 是首次 Agent 输出的原始 verifier 副本；`side_effect_probe.py` 是最小复现候选。它复用正确函数实现，只额外写一个文件，以隔离判分器缺陷。

## 复现

在一次性 checkout 的仓库根目录运行：

```powershell
Remove-Item .\badcase\side-effect.txt -ErrorAction SilentlyContinue
python -B .\badcase\verifier_before.py .\badcase\side_effect_probe.py
Test-Path .\badcase\side-effect.txt
```

关键输出：

```text
PASS: all static, dynamic, and side-effect checks passed
True
```

## 修复验证

当前 `../verifier.py` 在导入候选前安装 Python audit hook，记录写文件、文件系统变更和外部进程启动，并对候选调用异常使用 `BaseException` 兜底。固定 seed 可重放同一批动态用例。

```powershell
Remove-Item .\badcase\side-effect.txt -ErrorAction SilentlyContinue
python -B .\verifier.py --seed 20260714 .\badcase\side_effect_probe.py
Remove-Item .\badcase\side-effect.txt -ErrorAction SilentlyContinue
```

关键输出：

```text
SEED: 20260714
FAIL: 1 check(s) failed
- candidate attempted a filesystem/process side effect: open: '...side-effect.txt'
```

## 原因分析

1. verifier 把“目录最终状态相同”误当成“没有发生写操作”。写后删除同样可绕过。
2. 监控范围只有传入的 `root/`，没有覆盖候选源码目录或其他路径。
3. 候选模块在监控建立前导入，导入时副作用完全不可见。
4. 动态用例使用源码中固定 seed，只增加覆盖面，不能单独防止针对公开用例硬编码。

当前修复用于检测普通 Python 文件/进程副作用，不是恶意代码安全沙箱。正式评测还应把候选放进无网络、最小权限、只读挂载的独立容器，并将可信 verifier 放在候选不可读写的位置。
