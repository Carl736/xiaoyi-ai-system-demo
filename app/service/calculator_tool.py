import ast
import operator


OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def calculate(expression: str):
    """
    安全计算数学表达式。

    支持：
    + - * / **
    以及括号和负数。

    不使用 eval()。
    """

    def _calculate(node):

        # 数字
        if isinstance(node, ast.Constant):

            if isinstance(node.value, (int, float)):
                return node.value

            raise ValueError("只允许数字")

        # 二元运算
        if isinstance(node, ast.BinOp):

            operator_func = OPERATORS.get(type(node.op))

            if operator_func is None:
                raise ValueError("不支持的运算符")

            left = _calculate(node.left)
            right = _calculate(node.right)

            return operator_func(left, right)

        # 一元运算，例如 -5
        if isinstance(node, ast.UnaryOp):

            operator_func = OPERATORS.get(type(node.op))

            if operator_func is None:
                raise ValueError("不支持的运算符")

            operand = _calculate(node.operand)

            return operator_func(operand)

        raise ValueError("不支持的表达式")

    try:

        tree = ast.parse(expression, mode="eval")

        return _calculate(tree.body)

    except ZeroDivisionError:
        raise ValueError("除数不能为 0")

    except SyntaxError:
        raise ValueError("数学表达式格式错误")