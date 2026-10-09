"""
Day 4 · 配置文件（多环境支持）

解决的问题：
    真实项目里，测试环境、预发环境、生产环境的接口地址不同。
    如果地址写死在代码里，换环境就要改代码——这不可接受。

    做法：地址、账号、超时全部放配置文件，用环境变量指定用哪一套。

使用方式：
    # 默认用 test 环境
    python -m pytest tests/

    # 切换到 staging 环境
    ENV=staging python -m pytest tests/

面试时怎么讲：
  「我用 YAML 管理多环境配置，通过环境变量 ENV 切换，
    接口地址、超时、账号都不写死在代码里，
    换环境不需要改代码，也不需要重新打包。」

【诚实说明】
  本项目用的是公开测试服务 httpbin，所有环境地址相同。
  这里刻意保留多环境结构，是为了展示「配置外置」这个设计，
  面试时可以照着讲，但不要声称自己在公司项目里做过——
  你公司项目里用的是内网地址和真实环境变量体系。
"""

import os

import yaml

# 读取当前环境，默认test
ENV = os.environ.get("ENV", "test")

# 所有环境的配置
CONFIGS = {
    "test": {
        "base_url": "https://httpbin.org",
        "timeout": 20,
        "desc": "公开测试服务，用例数据即发即弃",
    },
    "staging": {
        "base_url": "https://httpbin.org",
        "timeout": 30,
        "desc": "预发环境（示例，实际项目地址不同）",
    },
    "local": {
        "base_url": "http://127.0.0.1:8080",
        "timeout": 10,
        "desc": "本地环境，自己起的服务",
    },
}


def load_config():
    """加载当前环境的配置"""
    cfg = CONFIGS.get(ENV)
    if cfg is None:
        raise ValueError(
            f"未知环境 {ENV!r}，可选值：{list(CONFIGS.keys())}"
        )
    return cfg


def load_test_data():
    """从 YAML 读取测试数据（沿用 Day 3 的做法）"""
    data_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "data",
        "testdata.yaml",
    )
    with open(data_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["cases"]
