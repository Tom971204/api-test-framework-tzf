"""
Day 4 · 断言层（项目核心亮点）

这是整个项目最有价值的一个文件。

【为什么需要这一层】
  Day 3 里的断言是这样的：
      assert resp.status_code == 200
      assert resp.json()["json"]["title"] == "xxx"

  问题：
      1. 每个用例写两行，10 个用例就是 20 行重复代码
      2. 失败信息只有"assert 200 == 999"，不知道是哪个字段
      3. 断言维度不统一，有人查状态码有人查长度，容易漏

  做法：封装成 ApiAssert，一个方法一次做多层检查。

【五层断言是什么】
  一次接口调用，从外到内要检查五层：
    第1 层  HTTP 状态码      —— 这次请求成功了吗
    第 2 层  业务状态码      —— 接口业务上成功了吗（不同接口字段名不同）
    第 3 层  关键字段值      —— 返回的核心数据对吗
    第 4 层  数据类型与格式    —— 类型、长度、格式符合约定吗
    第 5 层  数据关联性      —— 多个字段之间逻辑自洽吗（最强的一层）

  举例说明第 5 层—— 这也是你最值钱的一条：
    「提交订单时传的金额是 100 元，
      返回的实付金额应该是 100 元、优惠金额 0 元，
      而不是随便一个看起来合理的数字。」

  「看起来合理」和「逻辑自洽」的区别，就是资深测试和初级测试的分水岭。

【面试怎么讲（这段是核心）】
  「我封装了 ApiAssert 类做多层断言，把接口校验拆成五层：
     HTTP 状态码、业务状态码、关键字段值、数据类型格式、数据关联性。

   为什么拆五层？因为一次接口失败的原因不止一种，
   只查状态码会漏掉『状态码 200 但业务码是失败』这种最常见的问题。

   尤其第五层数据关联性——比如提交金额 100 元，
   检查返回的实付金额是不是 100、优惠是不是 0，
   而不是只检查『实付金额存在』。
   这种校验才能发现真正影响业务的逻辑缺陷。

   而且每层校验失败都会输出结构化的失败信息，
   报告里能直接看到是第几层、哪个字段、期望什么实际什么。」
"""


class AssertResult:
    """收集断言结果，最后统一汇总"""

    def __init__(self, name):
        self.name = name
        self.checks = []  # [(层数, 层名, 是否通过, 说明)]

    def add(self, layer, layer_name, passed, message):
        self.checks.append((layer, layer_name, passed, message))
        return passed

    @property
    def passed(self):
        return all(c[2] for c in self.checks)

    def report(self):
        """生成人类可读的校验报告"""
        lines = [f"校验报告 · {self.name}"]
        for layer, layer_name, passed, message in self.checks:
            mark = "PASS" if passed else "FAIL"
            lines.append(f"  [第{layer}层][{mark}] {layer_name} —— {message}")
        return "\n".join(lines)


class ApiAssert:
    """
    接口断言器。

    用法：
        result = ApiAssert("商品查询").run_all(resp, expect={
            "status_code": 200,
            "fields": {"code": 0},
            "types": {"data.price": (int, float)},
            "relations": [...],
        })
    """

    # ---------------- 第 1 层：HTTP 状态码 ----------------
    @staticmethod
    def check_status_code(result, resp, expect_status):
        """HTTP 层：确认请求在传输层面成功"""
        actual = resp.status_code
        passed = actual == expect_status
        result.add(
            1, "HTTP 状态码", passed,
            f"期望 {expect_status}，实际 {actual}",
        )
        return passed

    # ---------------- 第 2 层：业务状态码 ----------------
    @staticmethod
    def check_business_code(result, data, path, expect_code):
        """
        业务层：接口在业务上是否成功。

        这是最容易漏的一层—— 状态码 200 但业务码是失败的情况非常多。
        比如下单接口返回 {"code": 500, "msg": "库存不足"}，HTTP 是 200。

        path 是字段路径，字符串或列表：
            "code"          → data["code"]
            ["data", "code"] → data["data"]["code"]
        """
        actual = ApiAssert.get_by_path(data, path)
        passed = actual == expect_code
        path_desc = path if isinstance(path, str) else ".".join(str(p) for p in path)
        result.add(
            2, "业务状态码", passed,
            f"{path_desc} 期望 {expect_code}，实际 {actual}",
        )
        return passed

    # ---------------- 第 3 层：关键字段值 ----------------
    @staticmethod
    def check_fields(result, data, expect_fields):
        """
        业务层：核心字段的值是否符合预期。

        expect_fields 格式：{"字段路径": 期望值}
            {"code": 0, ["data","name"]: "商品A"}
        """
        all_passed = True
        for path, expect in expect_fields.items():
            actual = ApiAssert.get_by_path(data, path)
            passed = actual == expect
            if not passed:
                all_passed = False
            ApiAssert.show_path(result, 3, path, passed, expect, actual)
        return all_passed

    # ---------------- 第 4 层：数据类型与格式 ----------------
    @staticmethod
    def check_types(result, data, type_rules):
        """
        数据层：字段的类型和格式是否合规。

        自动化里最常见的隐性 bug 就是类型错误——
        接口该返回数字却返回了字符串，前端不报错但计算出错。

        type_rules 格式：{"字段路径": 允许的类型}
        允许单个类型或元组，两种写法都支持：
            {"data.id": str}              → 必须是 str
            {"data.price": (int, float)}  → 可以是 int 或 float
        """
        all_passed = True
        for path, types in type_rules.items():
            # 统一成元组处理，兼容单个类型和多个类型两种写法
            allowed = types if isinstance(types, tuple) else (types,)

            actual = ApiAssert.get_by_path(data, path)
            passed = isinstance(actual, allowed)
            if not passed:
                all_passed = False
            expect_desc = "或".join(t.__name__ for t in allowed)
            ApiAssert.show_path(
                result, 4, path, passed,
                f"类型为 {expect_desc}", f"类型为 {type(actual).__name__}",
            )
        return all_passed

    # ---------------- 第 5 层：数据关联性 ----------------
    @staticmethod
    def check_relations(result, data, relations):
        """
        逻辑层：多个字段之间是否逻辑自洽。

        relations 格式：[{"字段路径":..., "关联字段路径":..., "关系":"eq"}]
        关系支持：
            "eq"   两个值相等
            "gt"   左侧 > 右侧
            "ge"   左侧 >= 右侧
            "lt"   左侧 < 右侧
            "ne"   两个值不等

        举例（这才是真正能发现业务缺陷的检查）：
            提交金额 100、优惠 0 → 实付金额必须等于 100
            商品数量 3、单价 10 → 订单金额必须等于 30
            开始时间 < 结束时间

        【面试重点】
        这一层是本项目的核心价值。前面四层是「格式对不对」，
        这一层是「业务逻辑对不对」—— 格式全对的接口照样可能算错钱。
        """
        all_passed = True
        for rule in relations:
            left_path = rule["字段路径"]
            right_path = rule["关联字段路径"]
            op = rule.get("关系", "eq")

            left = ApiAssert.get_by_path(data, left_path)
            right = ApiAssert.get_by_path(data, right_path)

            passed = ApiAssert.compare(left, right, op)
            if not passed:
                all_passed = False

            op_desc = {
                "eq": "等于", "ne": "不等于",
                "gt": "大于", "ge": "大于等于",
                "lt": "小于", "le": "小于等于",
            }.get(op, op)

            ApiAssert.show_path(
                result, 5, f"{left_path} {op_desc} {right_path}",
                passed, f"两者{op_desc}", f"实际 {left!r} vs {right!r}",
            )
        return all_passed

    # ---------------- 工具方法 ----------------
    @staticmethod
    def get_by_path(data, path):
        """
        按路径取值。支持三种写法（都是为了用起来方便）：
            get_by_path(d, "code")            → data["code"]
            get_by_path(d, "json.title")      → data["json"]["title"]  ← 点号分隔
            get_by_path(d, ["data", "items"]) → data["data"]["items"]  ← 列表

        【为什么要支持多种写法】
        项目早期我用列表形式，后来发现断言配置写在 YAML 里用点号更直观，
        就统一支持两种。
        注意列表形式可以处理数组下标：["items", 0, "id"]
        点号形式不能，所以取数组元素时仍需用列表。
        """
        if isinstance(path, str):
            # 点号分隔 → 拆成列表
            keys = path.split(".")
        elif isinstance(path, list):
            keys = path
        else:
            keys = [path]

        cur = data
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            elif isinstance(cur, list) and isinstance(k, int) and k < len(cur):
                cur = cur[k]
            else:
                return None
        return cur

    @staticmethod
    def compare(left, right, op):
        """按关系运算符比较"""
        try:
            return {
                "eq": lambda: left == right,
                "ne": lambda: left != right,
                "gt": lambda: left > right,
                "ge": lambda: left >= right,
                "lt": lambda: left < right,
                "le": lambda: left <= right,
            }[op]()
        except TypeError:
            return False  # 类型不同无法比较，视为不通过

    @staticmethod
    def show_path(result, layer, path, passed, expect, actual):
        """统一输出第 3/4/5 层的校验信息"""
        result.add(
            layer, f"字段 {path}", passed,
            f"期望 {expect!r}，实际 {actual!r}",
        )

    # ---------------- 统一入口 ----------------
    @staticmethod
    def run_all(resp, expect, name="接口校验"):
        """
        一次执行多层断言。

        expect 的结构示例：
            {
                "status_code": 200,
                "business_code": {"path": "code", "expect": 0},
                "fields": {"json.title": "xxx"},
                "types": {"json.title": str},
                "relations": [
                    {"字段路径": "json.title", "关联字段路径": "json.title",
                     "关系": "eq"},
                ],
            }

        返回 AssertResult，调用 .passed 判断整体是否通过。
        """
        result = AssertResult(name)
        data = resp.json() if resp.text else {}

        # 第 1 层必做
        ApiAssert.check_status_code(result, resp, expect.get("status_code", 200))

        # 第 2-5 层按需做
        if "business_code" in expect:
            bc = expect["business_code"]
            ApiAssert.check_business_code(result, data, bc["path"], bc["expect"])

        if "fields" in expect:
            ApiAssert.check_fields(result, data, expect["fields"])

        if "types" in expect:
            ApiAssert.check_types(result, data, expect["types"])

        if "relations" in expect:
            ApiAssert.check_relations(result, data, expect["relations"])

        return result
