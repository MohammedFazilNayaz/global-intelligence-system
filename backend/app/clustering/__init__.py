"""V0.3 Deduplication and Event Clustering package."""
from backend.app.clustering.similarity import (
    tokenize_and_normalize,
    jaccard_similarity,
    temporal_proximity_score,
    location_similarity_score,
)
from backend.app.clustering.scorer import (
    ClusterMatchScore,
    calculate_cluster_match,
    DEFAULT_CLUSTER_THRESHOLD,
)

__all__ = [
    "tokenize_and_normalize",
    "jaccard_similarity",
    "temporal_proximity_score",
    "location_similarity_score",
    "ClusterMatchScore",
    "calculate_cluster_match",
    "DEFAULT_CLUSTER_THRESHOLD",
]
