"""
Day 4 · 接口层

解决的问题：
    用例里直接写 requests.post(...) 会导致：
      1. 地址、超时在每个用例里重复
      2. 接口变了要改一堆文件
      3. 打印日志、加认证头都没有统一入口

    做法：把「怎么发请求」收进这一层，用例只关心「发什么、断言什么」。

分层结构：
    config/  配置层 —— 环境、地址、超时
    core/    接口层 —— 怎么发请求
    core/    断言层 —— 怎么判断结果对不对
    tests/    用例层 —— 发什么、断言什么

面试时怎么讲：
  「我把项目分成配置层、接口层、断言层、用例层四层。
    接口层封装发请求和日志，用例层只描述场景和预期。
    这样接口变更只需改接口层，用例不受影响。」

【关于装饰器】
  这个文件用了一个「装饰器」来做统一日志。
  装饰器是 Python 的进阶语法，这里不要求你完全理解，
  先看懂它做了什么即可：
    @log_request
    def post(...): ...
  等价于在函数执行前后自动打印日志。
  Day 5 之前能看懂 80% 即可，面试不会考你装饰器原理。
"""

import functools
import json
import time
import uuid

import requests


def log_request(func):
    """
    装饰器：给函数自动加上「打印请求日志」的能力。

    @functools.wraps 保留原函数的元信息，
    这样出错时栈信息能显示真正的函数名和行号，而不是 log_request 内部。
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print(f"\n  → 发起请求：{func.__name__}()")
        start = time.time()
        try:
            resp = func(*args, **kwargs)
            cost = (time.time() - start) * 1000
            print(f"  ← 响应状态：{resp.status_code}，耗时 {cost:.0f}ms")
            return resp
        except Exception as e:
            cost = (time.time() - start) * 1000
            print(f"  ← 请求异常：{type(e).__name__}，耗时 {cost:.0f}ms")
            raise

    return wrapper


class ApiClient:
    """
    接口客户端。

    Day 3 里这个类写在 conftest.py 里，现在搬到 core/ 单独成文件——
    这就是「分层」：接口相关的都放一起，不和测试逻辑混着。

    【run_id 的作用】
    每次运行生成一个唯一标识，真实项目里会拼进测试数据，
    保证每次运行造的数据唯一，天然实现数据隔离。
    这比「跑完手动删数据」更可靠——万一没删干净，下次也不会撞。
    """

    def __init__(self, base_url: str, timeout: int = 20):
        self.base_url = base_url.rstrip("/")  # rstrip 去掉末尾斜杠，避免拼接出双斜杠
        self.timeout = timeout
        self.run_id = uuid.uuid4().hex[:8]
        self.session = requests.Session()  # Session 会复用连接，比每次新建更快

    @log_request
    def post(self, path: str, body: dict = None):
        """发送 POST 请求"""
        return self.session.post(
            url=f"{self.base_url}{path}",
            json=body or {},
            timeout=self.timeout,
        )

    @log_request
    def get(self, path: str, params: dict = None):
        """发送 GET 请求"""
        return self.session.get(
            url=f"{self.base_url}{path}",
            params=params or {},
            timeout=self.timeout,
        )

    def echo_title(self, title: str):
        """
        一个业务语义的方法：提交标题并返回服务回传的内容。

        【为什么要封一层业务方法】
        如果每个用例都写 post("/post", {"title": x})，
        哪天接口路径变了，要改几十个用例。
        封成echo_title 之后，只有这一个文件需要改。
      """
        resp = self.post("/post", {"title": title})
        return resp, resp.json()


class EchoService:
    """
    业务服务封装（Day 4 新增）。

    这是比 ApiClient 更进一层的封装：
      ApiClient 关心「怎么发请求」
      EchoService 关心「这个业务怎么用」

    真实项目里你会按业务模块分：UserService、OrderService...
    这样用例写起来就是 service.submit_title("x")，
    可读性比 resp = client.post(...) 强很多。

    【面试可讲】
    「接口层我做了两层封装：底层 ApiClient 负责发请求和日志，
      上层按业务模块封装成 Service 类。
      用例只调 Service 的方法，不用关心底层请求细节，
      接口变更时只需要改 Service 层。」
    """

    def __init__(self, client: ApiClient):
        self.client = client

    def submit_title(self, title: str):
        """提交一个标题，返回 (响应对象, 解析后的JSON)"""
        return self.client.echo_title(title)

    def submit_with_run_id(self, title: str):
        """
        带运行标识提交——这是数据隔离的真实做法。

        每次运行的数据都带上当次的 run_id，
        即使没清理干净，下次也不会和历史数据冲突。
        """
        resp = self.client.post(
            "/post",
            {"title": title, "run_id": self.client.run_id},
        )
        return resp, resp.json()

    def health_check(self):
        """健康检查，用于验证环境是否可用"""
        return self.client.get("/get")
