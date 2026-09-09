"""Rules 子包：从 .trae/rules.md 加载规则并拼装到系统消息。"""

from .loader import RuleLoader, load_rules

__all__ = ["RuleLoader", "load_rules"]