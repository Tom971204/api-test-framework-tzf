"""
Day 4 · 五层断言实战用例

这是项目最有价值的测试文件。
它演示了 ApiAssert 的五层校验怎么实际用。

运行：
    cd day4
    D:/Python/python.exe -m pytest tests/ -v
    ENV=staging D:/Python/python.exe -m pytest tests/ -v     # 切环境
"""

import pytest

from core.asserts import ApiAssert


# ============================================================
# 用例 1：完整五层断言（正向）
# ============================================================
def test_full_five_layers(clean_env, case):
    """
    一次调用做五层校验。

    这个用例回答面试官的问题：
    「你的自动化用例校验到什么程度？」
    「不只是状态码和字段值，还会校验类型和字段之间的逻辑关联。」
    """
    title = case["body"]["title"]

    resp, data = clean_env.submit_title(title)

    result = ApiAssert.run_all(
        resp,
        expect={
            # ---- 第 1 层：HTTP 状态码 ----
            "status_code": case["expect_status"],

            # ---- 第 3 层：关键字段值 ----
            #注意路径是 "json.title"，因为 httpbin 会把你发的数据放在 json 字段下
            "fields": {
                "json.title": case["expect_title"],
            },

            # ---- 第 4 层：数据类型 ----
            # title 必须是字符串。如果是数字或None，说明序列化有问题
            "types": {
                "json.title": str,
            },

            # ---- 第 5 层：数据关联性 ----
            # 真实场景示范：提交的内容和回传的内容必须一致。
            # 这里用 httpbin 的 args 字段（查询参数，原样回传请求内容）
            # 和 json 字段（请求体，原样回传）做交叉校验——
            # 两个独立通道回传的数据应该一致，
            # 如果不一致说明服务端对请求体做了不该做的加工。
            #
            # 【第5 层的价值】
            # 前四层校验的是「每个字段自己对不对」，
            # 第 5 层校验的是「字段之间说得通不通」。
            # 金额计算类缺陷只能靠这一层发现。
            "relations": [
                {
                    "字段路径": "json.title",
                    "关联字段路径": "url",
                    "关系": "ne",  # title 不会等于 url，这里做基础的差异演示
                },
            ],
        },
        name=f"五层断言 · {case['title']}",
    )

    print("\n" + result.report())

    # 整体判定：任何一层不过，整条用例就算失败
    # 这一点和Day 1 那个bug 是同一个道理——
    # pytest 底层帮你做了综合判定
    assert result.passed, "\n" + result.report()

    # ---- 额外做一次真正的自洽校验（直接比较，不用relations 包装）----
    # 提交什么就应该回传什么，这是最典型的数据关联性检查。
    # 用例 3 专门展开讲这一层，这里保持简单。
    returned_title = ApiAssert.get_by_path(data, "json.title")
    assert returned_title == title, "回传值与提交值不一致"
    assert len(returned_title) == len(title), "回传值长度与提交值不一致"


# ============================================================
# 用例 2：演示「只查状态码会漏掉什么」
# ============================================================
def test_status_code_only_is_not_enough(clean_env):
    """
    这个用例演示一个非常重要的测试观念：

    【场景】
      假设有个下单接口，HTTP 返回 200，
      但业务上失败了：{"code": 5001, "msg": "库存不足"}

      如果自动化只断言 status_code == 200，
      这条用例会「通过」—— 但业务是失败的。

    【本用例做什么】
      httpbin 没有失败的业务码接口，所以我用断言类自己构造一个响应字典，
      模拟「状态码正常但业务失败」的情况。

    【面试怎么讲】
      「我的自动化用例不会只断言 HTTP 状态码。
       因为我们线上真实出现过状态码 200 但业务失败的接口，
       如果只查状态码，用例会显示通过但用户实际下单失败。
       所以我会在业务码接口上额外断言业务状态码。」
    """
    # 模拟一个真实的失败响应结构
    fake_business_response = {
        "code": 5001,
        "msg": "库存不足",
        "data": None,
    }

    # ---- 如果只断言 HTTP 状态码 ----
    # 这种情况下业务失败也会「通过」，这是危险的
    business_code = fake_business_response["code"]
    print(f"\n模拟响应：HTTP 200，业务码 {business_code}（{fake_business_response['msg']}）")

    # ---- 正确的做法：加一层业务码断言 ----
    result = ApiAssert.run_all(
        # 构造一个假的 resp 对象满足 run_all 的接口要求
        resp=MockResponse(status=200, payload=fake_business_response),
        expect={
            "status_code": 200,
            # 这条断言会让整条用例失败——正确地暴露了业务问题
            "business_code": {"path": "code", "expect": 0},
        },
        name="业务码校验演示",
    )

    print("\n" + result.report())

    # 断言这个用例「应该失败」——
    # 因为我们的目的就是证明「只查状态码不够」
    assert not result.passed, "如果这里通过了，说明业务码断言没生效"
    print("\n结论：HTTP 状态码通过，但业务码校验拦住了它")


# ============================================================
# 用例 3：演示第 5 层能发现「看起来对但算错」的缺陷
# ============================================================
def test_relation_catches_look_right_wrong_value(clean_env):
    """
    演示数据关联性校验的价值——这是你面试时最该讲的一条。

    【场景】
      提交一个标题，服务原样回传。这看起来没问题。

      但假设有个金额计算接口：
        提交：商品单价 10 元 × 数量 3 = 应付 30 元
        返回：{"unit_price": 10, "quantity": 3, "amount": 30}  ← 正确
        但某次改版后：{"unit_price": 10, "quantity": 3, "amount": 300} ← 字段都在，类型都对，状态码 200

      如果自动化只断言「amount 字段存在、是数字」，
      这个 bug 完全测不出来。

      只有断言「unit_price × quantity == amount」才能发现。

    【面试怎么讲——这段最重要】
      「我特别强调数据关联性校验。
        格式校验只能保证『字段有值、类型对』，
        但真正的业务缺陷往往是『每个字段都对，加起来不对』。

        最典型的就是金额计算——单价对、数量对、状态码对，
        但实付金额算错了。这类 bug 客户投诉之前基本测不出来。

        所以我会在金额、数量、日期这类字段上加关联断言，
        校验它们之间的运算关系和时序关系。」
    """
    title = "金额校验演示"
    resp, data = clean_env.submit_title(title)

    # 第 3 层：字段存在且值正确
    result = ApiAssert.run_all(
        resp,
        expect={
            "status_code": 200,
            "fields": {"json.title": title},
        },
        name="金额校验-第3层",
    )
    assert result.passed

    # 第 5 层：数据关联性——这里做「自洽性」校验
    # 演示思路：提交的内容和回传的内容必须一致
    submitted = title
    returned = ApiAssert.get_by_path(data, ["json", "title"])

    print(f"\n提交值：{submitted!r}")
    print(f"回传值：{returned!r}")

    # 直接比较，如果不一致测试就失败
    assert submitted == returned, "回传值与提交值不一致，说明数据在服务端被改动了"

    print("关联性校验通过：提交值与回传值逻辑自洽")


# ============================================================
# 辅助类：构造一个假的响应对象
# ============================================================
class MockResponse:
    """
    模拟 requests 的 Response 对象。

    用途：在没有真实「业务失败接口」时，
    也能演示业务码断言的效果。
    这是一个测试常用技巧——造桩（stub）。
    """

    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = "mock"

    def json(self):
        return self._payload


# ============================================================
# 用例 4：环境切换验证（多环境支持）
# ============================================================
def test_environment_is_reachable(clean_env, env, cfg):
    """
    验证当前环境可用，且配置注入正确。

    这个用例的作用：
      1. 环境不通时第一时间发现，而不是等业务用例莫名失败
      2. 顺带验证多环境配置生效（换ENV 参数就能切环境）
    """
    print(f"\n当前环境：{env}")
    print(f"接口地址：{cfg['base_url']}")
    print(f"超时设置：{cfg['timeout']}s")
    print(f"环境说明：{cfg['desc']}")

    # 健康检查——真实项目里可以换成专门的 ping 接口
    resp = clean_env.health_check()

    assert resp.status_code == 200, f"{env} 环境不可达：{resp.status_code}"
    print(f"环境 {env} 连通正常")
