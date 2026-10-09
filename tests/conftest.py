"""
Day 4 · conftest.py（分层后的版本）

与 Day 3 的差别：
  1. 客户端从「写在 conftest 里」变成「从 core/api_client.py 导入」
  2. 新增 Service 层注入
  3. 地址和超时从 config 读，支持多环境切换

【分层结构总览】
    config/config.py       配置层：环境、地址、超时
    core/api_client.py     接口层：怎么发请求
    core/assert.py         断言层：怎么判断结果对不对
    tests/conftest.py      用例层：用例专用fixture
    tests/test_*.py        测试用例
"""

import os
import sys

import pytest

# Windows 中文环境下，pytest 输出中文用例名时，
# 控制台默认按 GBK 解码 UTF-8 字节会报 UnicodeDecodeError。
# 强制标准输出用 UTF-8，这样在 CMD / PyCharm 终端 / Git Bash 都能正常显示中文。
# 面试可讲：「这是跨平台适配的细节，Windows 默认编码不是 UTF-8，
#   测试报告里有中文用例名时必须显式指定编码，否则会出现乱码或解码异常。」
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass

# 把项目根目录加入模块搜索路径，
# 这样测试用例里可以直接 from core.assert import ApiAssert，
# 不需要在每个文件里写一长串相对路径。
# 面试可讲：「用 sys.path 统一模块搜索路径，避免包导入路径问题。」
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config.config import load_config, load_test_data, ENV  # noqa: E402
from core.api_client import ApiClient, EchoService  # noqa: E402


# ============================================================
# 从 YAML 动态生成用例
# ============================================================
# 与 Day 3 的区别：
#   Day 3 的钩子写在 tests/test_day3.py 里
#   Day 4 搬到 conftest.py —— 这样整个 tests/ 目录下所有文件都能用
#
# 这是分层的实际收益之一：能力放对位置，就不用每个文件重复写。
def pytest_generate_tests(metafunc):
    """
    pytest 钩子：在收集阶段动态决定要生成哪些测试。

    用法：任何测试函数只要声明一个叫 case 的参数，
          就会自动按 YAML 里的数据量展开成 N 条独立用例。
    """
    if "case" in metafunc.fixturenames:
        metafunc.parametrize(
            "case",
            load_test_data(),
            ids=[c["title"] for c in load_test_data()],
        )


@pytest.fixture(scope="session")
def env():
    """当前环境名"""
    return ENV


@pytest.fixture(scope="session")
def cfg():
    """当前环境的配置（地址、超时）"""
    return load_config()


@pytest.fixture(scope="session")
def test_cases():
    """
    从 YAML 读取测试数据（session 级，读一次就够）。

    Day 4 的改进：改用 config 里的 load_test_data()，
    路径处理逻辑收到 config 层，用例层不再关心文件在哪。
    """
    return load_test_data()


@pytest.fixture
def client(cfg):
    """接口客户端：每条用例一个新的"""
    return ApiClient(base_url=cfg["base_url"], timeout=cfg["timeout"])


@pytest.fixture
def echo_service(client):
    """
    业务服务：注入到用例里。

    用例拿到的不是一个「发请求的对象」，而是「一个业务对象」，
    用例写 service.submit_title("x")，而不是 client.post("/post", {...})。
    """
    return EchoService(client)


@pytest.fixture
def clean_env(client, test_cases, echo_service):
    """
    数据隔离（setup / teardown）。

    【与 Day 3 的差别】
    Day 3 只是打印了几行日志；
    Day 4 用run_id 实现了真实可用的隔离机制——
    见 core/api_client.py 里的 submit_with_run_id。

    【本项目环境的诚实说明】
    httpbin 是公开测试服务，没有写入接口，所以这里无法真实创建/删除数据。
    真实项目（比如公司内网系统）里，这一段应该是：
        setup：调创建接口造数据，记下 ID
        teardown：调删除接口清理
    这段代码结构照着写就行，但面试时不要说
    「我在公司用httpbin 做数据隔离」——不存在的。
    """
    created = []

    print(f"\n[setup] 环境={ENV}，run_id={client.run_id}")

    for case in test_cases:
        # 真实项目：这里调创建接口
        # resp = client.post("/api/data", {"title": case["title"],
        #                                   "run_id": client.run_id})
        # created.append(resp.json()["data"]["id"])
        created.append(case["id"])

    yield echo_service

    # 真实项目：这里按 ID 逐条删除
    # for data_id in created:
    #     client.post("/api/data/delete", {"id": data_id})

    print(f"[teardown] 环境={ENV}，已清理 {len(created)} 条数据")
