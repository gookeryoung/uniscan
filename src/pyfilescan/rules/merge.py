"""规则集合合并：将基础规则集与用户规则集按名称合并。

合并语义：

- ``rules``：用户规则中同名规则覆盖基础规则，基础规则中未被覆盖的保留
- ``ignore_dirs`` / ``ignore_extensions`` / ``ignore_paths``：取并集（去重保序）
- ``version``：采用用户规则集的版本号
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from pyfilescan.rules.model import Rule, RuleSet

__all__ = ["merge_rulesets"]


def merge_rulesets(base: RuleSet, override: RuleSet) -> RuleSet:
    """将 override 规则集合并到 base 之上，override 中同名规则覆盖 base。

    :param base: 基础规则集（如内置通用规则）
    :param override: 覆盖规则集（如用户自定义规则）
    :return: 合并后的新 RuleSet
    """
    override_names = {r.name for r in override.rules}

    # 保留 base 中未被覆盖的规则，再追加 override 的全部规则
    merged_rules: List[Rule] = [r for r in base.rules if r.name not in override_names]
    merged_rules.extend(override.rules)

    return RuleSet(
        version=override.version,
        rules=tuple(merged_rules),
        ignore_dirs=_union(base.ignore_dirs, override.ignore_dirs),
        ignore_extensions=_union(base.ignore_extensions, override.ignore_extensions),
        ignore_paths=_union(base.ignore_paths, override.ignore_paths),
    )


def _union(*tuples: Tuple[str, ...]) -> Tuple[str, ...]:
    """合并多个元组，去重并保持插入顺序。"""
    seen: Dict[str, None] = {}
    for t in tuples:
        for item in t:
            if item not in seen:
                seen[item] = None
    return tuple(seen.keys())
