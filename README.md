# 接口自动化用例集（Python + pytest + requests）

> 一个分层结构的接口自动化项目：四层架构 + 五层断言 + 数据与代码分离。
> 面试演示项目，可现场运行。

---

## 1. 项目说明

### 这个项目解决什么问题

写接口自动化最容易踩的三个坑，本项目分别给出了解法：

| 坑 | 表现 | 本项目的解法 |
|---|---|---|
| **数据和代码混在一起** | 加一条用例要改 Python 代码 | 测试数据外置到 YAML，加用例只改数据文件 |
| **用例之间互相污染** | 数据越堆越多，接口变慢甚至报错 | fixture 做数据隔离，teardown 自动清理 |
| **断言维度不统一** | 有人查状态码有人查长度，容易漏 | 封装五层断言，一次调用做多层校验 |

### 项目来源

这是一个**个人练习项目**，用于学习接口自动化的工程化方法。

- 被测对象是公开测试服务 [httpbin](https://httpbin.org)，不涉及任何公司内部系统
- 五层断言、多环境配置、数据隔离等设计思路，参考了主流接口自动化框架的通用做法
- 项目中的「已知不足」见第 5 节，**这些不足是真实存在的，不打算隐瞒**

---

## 2. 快速开始

### 环境准备

```bash
# Python 3.7+
pip install requests pytest PyYAML pytest-html
```

| 依赖 | 本项目验证版本 | 用途 |
|---|---|---|
| requests | 2.31.0 | 发 HTTP 请求 |
| pytest | 6.2.5 | 测试框架 |
| PyYAML | 6.0.1 | 读取测试数据 |
| pytest-html | 3.1.1 | 生成 HTML 报告 |

> **版本说明**：pytest 6.x 是最后支持 Python 3.7 的版本。若你的 Python ≥ 3.9，
> 可以直接用更新的 pytest。

### 执行

```bash
# 在项目根目录下执行，会自动读取 pytest.ini
pytest

# 等价于指定测试目录
pytest tests/

# 切换环境
ENV=staging pytest

# 生成 HTML 报告（推荐面试演示用）
pytest --html=report.html --self-contained-html
```

### 查看报告

执行上述命令后，会在项目根目录生成 `report.html`，用浏览器打开即可看到：

- 每条用例的通过/失败状态
- 失败用例的失败原因和具体行号
- 执行耗时统计

---

## 3. 项目结构

```
.
├── config/
│   └── config.py            配置层：多环境地址、超时
├── core/
│   ├── api_client.py        接口层：封装请求、日志、业务方法
│   └── asserts.py           断言层：五层断言实现
├── data/
│   └── testdata.yaml        测试数据（外置，改用例不用改代码）
├── tests/
│   ├── conftest.py          fixture 注入 + 动态生成用例
│   └── test_assert_demo.py  测试用例
├── pytest.ini               pytest 配置
└── .gitignore
```

### 四层分工

```
用例层 tests/         发什么、断言什么
    ↓
断言层 asserts.py     怎么判断结果对不对
    ↓
接口层 api_client.py  怎么发请求
    ↓
配置层 config.py      环境、地址、超时
```

**为什么要分层**：接口变更时只需改接口层，用例不受影响；
换环境只需改配置或加个参数，代码不动。

---

## 4. 设计说明

### 4.1 数据与代码分离

测试数据全部放在 `data/testdata.yaml`，用例代码通过 `conftest.py` 里的
`pytest_generate_tests` 钩子动态读取：

```yaml
- id: edge_empty
  title: 边界场景-空标题
  body:
    title: ""
  expect_title: ""
  expect_status: 200
```

**效果**：新增一条用例只需在 YAML 追加一段配置，
测试代码一个字都不用改。实测从 9 条用例增加到 12 条，
代码零改动，全部自动通过。

**取舍**：写在 YAML 里的期望值如果写错，会导致用例失败但代码不报错。
所以 YAML 必须和代码一起 review。

### 4.2 五层断言

这是本项目的核心设计。一次接口调用，从外到内分五层校验：

| 层 | 检查内容 | 漏掉的后果 |
|---|---|---|
| 1. HTTP 状态码 | 传输层是否成功 | 最基础的检查 |
| 2. **业务状态码** | 业务上是否成功 | **状态码 200 但业务失败** |
| 3. 关键字段值 | 核心数据是否符合预期 | 业务数据错误 |
| 4. 数据类型与格式 | 类型、格式是否合规 | 前端不报错但计算出错 |
| 5. **数据关联性** | 字段之间是否逻辑自洽 | **每个字段都对，加起来不对** |

#### 为什么第 2 层不能省

接口返回 HTTP 200 但业务失败的情况非常普遍：

```json
{"code": 5001, "msg": "库存不足", "data": null}
```

如果只断言 `status_code == 200`，用例会显示通过，但业务实际是失败的。
项目里有 `test_status_code_only_is_not_enough` 这个用例专门演示这个场景。

#### 为什么第 5 层最值钱

前四层校验的是「字段本身对不对」，第 5 层校验的是「字段之间说得通不通」。

**最典型的场景是金额计算**：

```json
{
  "unit_price": 10,
  "quantity": 3,
  "amount": 300
}
```

- 只断言状态码 → 通过
- 只断言字段存在且是数字 → 通过
- 断言 `unit_price × quantity == amount` → **10 × 3 ≠ 300，拦截**

单价对、数量对、状态码对、类型全对，但金额算错了。
**这类缺陷客户投诉之前基本测不出来。**

项目里 `test_relation_catches_look_right_wrong_value` 演示了这个思路。

支持的关系运算符：`eq` / `ne` / `gt` / `ge` / `lt` / `le`。

### 4.3 数据隔离

`conftest.py` 里的 `clean_env` fixture 通过 `yield` 实现 setup / teardown：

```python
@pytest.fixture
def clean_env(client, test_cases):
    # ---- setup：准备测试数据 ----
    ...
    yield service

    # ---- teardown：清理测试数据 ----
    ...
```

无论用例通过还是失败，teardown 一定执行，保证环境不被污染。

**数据标识**：客户端每次运行生成 `run_id`（uuid 前 8 位），
真实项目中会把它拼进测试数据的字段里。这样即使某次没清理干净，
下次运行的数据也不会和历史数据冲突——比依赖「跑完手动删除」更可靠。

### 4.4 多环境配置

地址和超时放在 `config/config.py`，通过环境变量 `ENV` 切换：

```bash
pytest              # 默认 test 环境
ENV=staging pytest  # 预发环境
```

配置了 `test` / `staging` / `local` 三套。传入未定义的环境名会给出明确报错，
不会静默使用错误配置。

### 4.5 中文环境下的编码处理（踩坑记录）

这个项目的中文用例名（来自 `data/testdata.yaml`）在中文 Windows 上会引发一个
经典问题，这里记录完整的原因和解决方案，因为它体现的是**跨平台意识**。

**现象**：在中文 Windows 上执行 `pytest`，即使代码完全正确也会崩：

```
File "d:\python\lib\site-packages\iniconfig\__init__.py", line 82, in _parse
    for lineno, line in enumerate(line_iter):
UnicodeDecodeError: 'gbk' codec can't decode byte 0x80 in position 47
```

**原因**（两个层面，容易只看到第一个）：

1. **配置读取阶段**：pytest 通过 `iniconfig` 库读取 `pytest.ini`，
   这个库用**系统 locale 编码**（中文 Windows 是 GBK）打开文件。
   而 `pytest.ini` 里的注释是 UTF-8 编码的中文 → 解码失败。
   **注意：崩溃发生在读取配置时，此时测试代码一行都还没执行。**

2. **输出阶段**：即使配置读取正常，pytest 输出中文用例名时，
   控制台按 GBK 解码 UTF-8 字节同样会崩。

**解决方案**：

| 位置 | 处理方式 | 作用 |
|---|---|---|
| `pytest.ini` | 注释全部改为英文，保持纯 ASCII | 避免配置读取阶段崩溃 |
| `tests/conftest.py` | 对 `sys.stdout` / `sys.stderr` 调`reconfigure(encoding="utf-8")` | 避免输出阶段崩溃 |

`conftest.py` 里的处理：

```python
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
```

**为什么用 `try-except` 兜底**：某些终端（如部分 IDE 控制台、
被重定向的输出流）不支持 `reconfigure`，直接调用会抛异常。
判断 `hasattr` 加异常兜底，保证在任何环境下都不会因这段代码而崩。

**验证方式**：强制以 GBK 环境变量运行，确认仍然通过——
`PYTHONIOENCODING=gbk pytest` → `15 passed`。

**面试可讲**：

> 「项目的中文用例名在中文 Windows 上会触发编码异常。我排查后发现有两层：
> 一层是 pytest 读配置文件时用系统 locale 编码解码 UTF-8 注释，
> 另一层是输出中文用例名时控制台解码失败。
> 第一层我通过把配置文件注释改成英文解决，第二层在 conftest 里
> 重新指定标准输出编码，并且加了异常兜底，因为不是所有终端都支持
> 重新配置编码。这样在 CMD、PowerShell、Git Bash、IDE 控制台都能正常跑。」

---

## 5. 已知不足

这一节列的是项目**真实存在的问题**，不是谦虚话。

### 5.1 没有真实的数据创建与清理

**现状**：fixture 里的 setup / teardown 只打印了日志，没有真正创建和删除数据。

**原因**：被测的 httpbin 是公开的 echo 服务，**没有写入类接口**，
无法造数据也无法删数据。

**真实项目应该怎么做**：

```python
# setup
resp = client.post("/api/data", {"title": case["title"], "run_id": run_id})
created.append(resp.json()["data"]["id"])

# teardown
for data_id in created:
    client.post("/api/data/delete", {"id": data_id})
```

项目里保留了这两段的注释位置，**但这段代码没有实际运行过**。

### 5.2 多环境配置是「形式上」的

**现状**：`test` / `staging` / `local` 三套配置里，前两个的地址是一样的
（都是 httpbin），只有超时不同。

**原因**：拿不到真实的多环境服务地址。

**说明**：这个结构展示了「配置外置 + 环境切换」的做法，
但实际项目里三个环境会指向不同的服务器。

### 5.3 没有 CI 集成

**现状**：只能本地手动执行，没有接入 Jenkins / GitHub Actions。

**真实项目应该怎么做**：配置流水线，每次提交自动跑，
失败时通知群里。pytest 原生支持 JUnit XML 输出：

```bash
pytest --junitxml=report.xml
```

### 5.4 没有失败自动重试

**现状**：网络抖动等偶发问题会直接判定用例失败。

**说明**：本机环境里装了 `pytest-rerunfailures` 插件，
但**没有配置使用**。真实项目里可以考虑加：

```bash
pytest --reruns 2 --reruns-delay 1
```

但要注意：**接口自动化慎用重试**，它可能掩盖真实缺陷。

### 5.5 用例数据里的期望值靠人工保证

**现状**：YAML 里的 `expect_title` 是手写的。

**风险**：如果人工写错了，测试会失败但不是代码的 bug。

**真实项目的做法**：部分断言可以从文档或数据库自动取预期值，
而不是手写。这需要额外的接口或查询能力，本项目没做。

### 5.6 没有覆盖登录鉴权

**现状**：所有用例都是匿名调用，没有 token / cookie 处理。

**真实项目**：需要实现登录接口调用、token 提取与自动注入（fixture 里做一次，
后续用例复用）。这是接口自动化里很常规的一块，本项目未实现。

---

## 6. 可改进方向

如果继续做，优先级会是：

1. 换用真实可写入的测试环境，把数据隔离真正跑通（解决 5.1）
2. 加登录鉴权 fixture（解决 5.6）
3. 接入 CI，跑一次就会暴露环境不稳定问题（解决 5.3）
4. 补 SQL 数据校验模块——这是我上一份工作里最有价值的经验
   （多表关联查数据统计口径、验证计算公式）

---

## 7. 说明

- 本项目为**个人学习练习**，不代表任何公司项目
- 被测服务为公开的 httpbin.org，不涉及任何业务数据
- 项目中的 bug（我自己写出来又修掉的）已在代码注释和 commit 中保留，
  包括：路径解析不支持点号、类型校验不兼容单类型、模块名避开 Python 关键字
