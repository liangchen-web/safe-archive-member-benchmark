# Safe Archive Member Benchmark

这是一个小型 Coding Agent 任务设计样例，用于展示：

- 明确的输入、约束和 ground truth
- 可独立运行的自动 verifier
- 跨平台边界测试
- 带 seed 的动态用例，可记录并重放失败
- 检查候选实现不会写文件或启动外部进程

它不是已经发生的真实 Agent badcase。只有实际让某个 Agent 执行任务、保留原始输出并复现失败后，才能将对应记录称为 badcase。

## 任务

修复 `starter.py` 中的 `safe_member_path(root, member_name)`。

函数用于在解压归档前解析成员路径：

- 安全路径返回 `root` 下的绝对 `Path`
- 不安全或无效路径返回 `None`
- 同时把 `/` 和 `\` 视为分隔符
- 忽略空片段和 `.`，但任何 `..` 都必须拒绝
- 拒绝 POSIX 绝对路径、UNC 路径、Windows 盘符路径和盘符相对路径
- 拒绝控制字符、Windows 非法字符、NTFS ADS、Windows 设备名、以空格或点结尾的片段
- 不创建、修改或删除任何文件

Windows 设备名按不区分大小写处理，包括带扩展名的 `CON.txt`、`NUL.log`、`COM1.json` 等。

## 验证

```powershell
python verifier.py --seed 20260714 starter.py
python verifier.py --seed 20260714 reference_solution.py
```

固定 seed 用于发布前回归。实际测试 Agent 时省略 `--seed`，保存输出中的 seed，即可用 `--seed <值>` 重放同一批动态用例。

`verifier.py` 是可信判分器，实际 benchmark 中应放在候选 Agent 无法读取或修改的位置。`reference_solution.py` 仅用于证明任务可解；正式给 Agent 时不提供参考答案。

## 真实 Agent 运行记录

执行 Agent 前保存：

```text
Agent/版本：
开始时间：
原始任务提示：本 README 的“任务”部分
原始仓库哈希：
Agent 修改内容：
Agent 自报结果：
verifier 输出：
verifier seed：
失败的最早用例：
是否修改测试/verifier：
```

不要补写或美化原始失败输出。
