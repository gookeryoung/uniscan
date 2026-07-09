"""内置通用规则子包。

随软件分发一套通用扫描规则，覆盖常见密钥凭证、敏感文件名与忽略目录。
用户规则可通过 :func:`load_with_builtin` 与内置规则按名称合并，
用户规则中同名规则覆盖内置规则。

公共 API：

- :func:`load_builtin_ruleset`：加载内置规则集
- :func:`load_with_builtin`：合并内置规则与用户规则
- :data:`BUILTIN_RULES_PATH`：内置规则文件路径
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from pyfilescan.rules import RuleSet, load_ruleset
from pyfilescan.rules.merge import merge_rulesets

__all__ = ["BUILTIN_RULES_PATH", "load_builtin_ruleset", "load_with_builtin"]

logger = logging.getLogger(__name__)

# 内置规则文件路径（随包分发）
BUILTIN_RULES_PATH = Path(__file__).parent / "rules.yaml"


def load_builtin_ruleset() -> RuleSet:
    """加载内置通用规则集。

    :return: 内置 RuleSet 实例
    :raises RuleError: 内置规则文件加载或解析失败
    """
    return load_ruleset(BUILTIN_RULES_PATH)


def load_with_builtin(user_path: Optional[Path] = None) -> RuleSet:
    """加载内置规则并与用户规则合并。

    用户规则中同名规则覆盖内置规则；ignore_dirs / ignore_extensions /
    ignore_paths 取并集。若 ``user_path`` 为 None，仅返回内置规则集。

    :param user_path: 用户规则文件路径（可选）
    :return: 合并后的 RuleSet
    :raises RuleError: 规则文件加载或解析失败
    """
    builtin = load_builtin_ruleset()
    if user_path is None:
        return builtin
    user = load_ruleset(user_path)
    logger.debug(
        "合并规则: 内置 %d 条 + 用户 %d 条",
        len(builtin.rules),
        len(user.rules),
    )
    return merge_rulesets(builtin, user)
