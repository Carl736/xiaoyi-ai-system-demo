import ast
import operator


_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


def _eval_node(node):

    # 数字
    if isinstance(node, ast.Constant):

        if isinstance(
                node.value,
                (int, float)
        ):
            return node.value

        raise ValueError(
            "只允许数字"
        )

    # 正负号
    if isinstance(node, ast.UnaryOp):

        if isinstance(
                node.op,
                ast.USub
        ):
            return -_eval_node(
                node.operand
            )

        if isinstance(
                node.op,
                ast.UAdd
        ):
            return _eval_node(
                node.operand
            )

        raise ValueError(
            "不支持的运算符"
        )

    # 二元运算
    if isinstance(node, ast.BinOp):

        operator_func = _ALLOWED_OPERATORS.get(
            type(node.op)
        )

        if operator_func is None:
            raise ValueError(
                "不支持的运算符"
            )

        left = _eval_node(
            node.left
        )

        right = _eval_node(
            node.right
        )

        return operator_func(
            left,
            right
        )

    raise ValueError(
        "表达式包含不允许的内容"
    )


def calculator(
        expression: str
):
    """
    安全数学计算工具。
    """

    try:

        tree = ast.parse(
            expression,
            mode="eval"
        )

        result = _eval_node(
            tree.body
        )

        return {
            "expression": expression,
            "result": result
        }

    except Exception as e:

        return {
            "expression": expression,
            "error": str(e)
        }