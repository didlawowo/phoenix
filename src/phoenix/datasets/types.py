from dataclasses import dataclass
from typing import Dict, List, NamedTuple, Optional


class EmbeddingColumnNames(NamedTuple):
    vector_column_name: str
    raw_data_column_name: Optional[str] = None
    link_to_data_column_name: Optional[str] = None


@dataclass(frozen=True)
class Schema:
    prediction_id_column_name: Optional[str] = None
    timestamp_column_name: Optional[str] = None
    feature_column_names: Optional[List[str]] = None
    prediction_label_column_name: Optional[str] = None
    prediction_score_column_name: Optional[str] = None
    actual_label_column_name: Optional[str] = None
    actual_score_column_name: Optional[str] = None
    embedding_feature_column_names: Optional[Dict[str, EmbeddingColumnNames]] = None
