class RuleError(Exception):
    """规则定义或规则加载错误。"""


class CalculationError(RuleError):
    """某条活动无法按规则计算分值。"""
