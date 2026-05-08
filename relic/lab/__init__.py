"""relic.lab — Evaluation lab contracts for adapter training."""

from relic.lab.dataset_card import DatasetCard, DatasetCardSchema
from relic.lab.eval_contract import EvalCommand, EvalContract
from relic.lab.promote_blocked import PromoteBlocked, PromoteResult
from relic.lab.train_contract import TrainCommand, TrainContract
from relic.lab.validate_dataset import DatasetValidator, ValidationResult

__all__ = [
    "DatasetCard",
    "DatasetCardSchema",
    "DatasetValidator",
    "ValidationResult",
    "TrainContract",
    "TrainCommand",
    "EvalContract",
    "EvalCommand",
    "PromoteBlocked",
    "PromoteResult",
]
