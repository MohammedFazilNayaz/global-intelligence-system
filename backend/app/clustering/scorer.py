from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Set, Dict, Any, Tuple
from uuid import UUID

from backend.app.clustering.similarity import (
    tokenize_and_normalize,
    jaccard_similarity,
    temporal_proximity_score,
    location_similarity_score,
)

DEFAULT_CLUSTER_THRESHOLD = 0.75

# Rigorously calibrated, explainable scoring weights (sum = 1.00)
WEIGHT_EVENT_TYPE = 0.20
WEIGHT_TEMPORAL = 0.25
WEIGHT_LOCATION = 0.20
WEIGHT_ACTOR = 0.15
WEIGHT_ENTITY = 0.10
WEIGHT_LEXICAL = 0.10


@dataclass
class ClusterMatchScore:
    """Detailed, explainable score breakdown for event cluster candidate evaluation."""
    event_type_score: float
    temporal_score: float
    location_score: float
    actor_overlap_score: float
    entity_overlap_score: float
    lexical_score: float
    final_score: float
    threshold: float
    is_match: bool
    is_vetoed: bool
    veto_reason: Optional[str] = None
    candidate_cluster_id: Optional[UUID] = None

    def to_metadata_dict(self) -> Dict[str, Any]:
        """Serialize score breakdown into auditable metadata dictionary."""
        return {
            "method": "deterministic_event_clustering",
            "version": "0.3.0",
            "event_type_score": round(self.event_type_score, 4),
            "temporal_score": round(self.temporal_score, 4),
            "location_score": round(self.location_score, 4),
            "actor_overlap_score": round(self.actor_overlap_score, 4),
            "entity_overlap_score": round(self.entity_overlap_score, 4),
            "lexical_score": round(self.lexical_score, 4),
            "final_score": round(self.final_score, 4),
            "threshold": round(self.threshold, 4),
            "is_match": self.is_match,
            "is_vetoed": self.is_vetoed,
            "veto_reason": self.veto_reason,
            "candidate_cluster_id": str(self.candidate_cluster_id) if self.candidate_cluster_id else None,
        }


def calculate_cluster_match(
    # Event types
    event_type_a: str,
    event_type_b: str,
    # Temporal anchors
    time_a: Optional[datetime],
    time_b: Optional[datetime],
    # Locations
    loc_a_id: Optional[UUID],
    loc_b_id: Optional[UUID],
    country_a: Optional[str] = None,
    country_b: Optional[str] = None,
    # Entity sets
    actor_ids_a: Optional[Set[UUID]] = None,
    actor_ids_b: Optional[Set[UUID]] = None,
    all_entity_ids_a: Optional[Set[UUID]] = None,
    all_entity_ids_b: Optional[Set[UUID]] = None,
    # Lexical representations
    text_a: Optional[str] = None,
    text_b: Optional[str] = None,
    # Threshold & candidate
    threshold: float = DEFAULT_CLUSTER_THRESHOLD,
    candidate_cluster_id: Optional[UUID] = None,
) -> ClusterMatchScore:
    """Calculate deterministic, decomposable match score between an extracted event and a cluster candidate.
    
    Hard blocking rules (vetoes):
    - Mismatched event types immediately veto.
    - Temporal distance exceeding 48 hours immediately vetoes.
    - Conflicting sovereign locations immediately veto.
    - Disjoint primary actors for domain-specific events (e.g. corporate action, central bank) veto.
    """
    actors_a = actor_ids_a or set()
    actors_b = actor_ids_b or set()
    all_entities_a = all_entity_ids_a or set()
    all_entities_b = all_entity_ids_b or set()

    # 1. Event Type Compatibility
    if event_type_a.lower() != event_type_b.lower():
        return ClusterMatchScore(
            event_type_score=0.0,
            temporal_score=0.0,
            location_score=0.0,
            actor_overlap_score=0.0,
            entity_overlap_score=0.0,
            lexical_score=0.0,
            final_score=0.0,
            threshold=threshold,
            is_match=False,
            is_vetoed=True,
            veto_reason="event_type_mismatch",
            candidate_cluster_id=candidate_cluster_id,
        )
    s_type = 1.0

    # 2. Temporal Proximity
    s_temp = temporal_proximity_score(time_a, time_b, max_hours=48.0, tau_hours=24.0)
    if s_temp == 0.0 and time_a is not None and time_b is not None:
        return ClusterMatchScore(
            event_type_score=s_type,
            temporal_score=0.0,
            location_score=0.0,
            actor_overlap_score=0.0,
            entity_overlap_score=0.0,
            lexical_score=0.0,
            final_score=0.0,
            threshold=threshold,
            is_match=False,
            is_vetoed=True,
            veto_reason="temporal_distance_exceeded_48h",
            candidate_cluster_id=candidate_cluster_id,
        )

    # 3. Location Consistency
    s_loc, loc_vetoed = location_similarity_score(loc_a_id, loc_b_id, country_a, country_b)
    if loc_vetoed:
        return ClusterMatchScore(
            event_type_score=s_type,
            temporal_score=s_temp,
            location_score=0.0,
            actor_overlap_score=0.0,
            entity_overlap_score=0.0,
            lexical_score=0.0,
            final_score=0.0,
            threshold=threshold,
            is_match=False,
            is_vetoed=True,
            veto_reason="conflicting_sovereign_locations",
            candidate_cluster_id=candidate_cluster_id,
        )

    # 4. Actor Overlap
    if actors_a and actors_b:
        s_actor = jaccard_similarity(actors_a, actors_b)
        # For actor-centric events (central bank decision, corporate action), non-overlapping actors veto
        if s_actor == 0.0 and event_type_a.lower() in ("central_bank_decision", "corporate_action"):
            return ClusterMatchScore(
                event_type_score=s_type,
                temporal_score=s_temp,
                location_score=s_loc,
                actor_overlap_score=0.0,
                entity_overlap_score=0.0,
                lexical_score=0.0,
                final_score=0.0,
                threshold=threshold,
                is_match=False,
                is_vetoed=True,
                veto_reason="disjoint_primary_actors",
                candidate_cluster_id=candidate_cluster_id,
            )
    elif not actors_a and not actors_b:
        # Neither has explicit actor entities (e.g. natural disaster, generic market movement)
        s_actor = 0.5
    else:
        # One has an actor, one does not (partial asymmetry)
        s_actor = 0.3

    # 5. General Entity Overlap
    if all_entities_a and all_entities_b:
        s_ent = jaccard_similarity(all_entities_a, all_entities_b)
    elif not all_entities_a and not all_entities_b:
        s_ent = 0.5
    else:
        s_ent = 0.3

    # 6. Lexical Similarity
    tokens_a = tokenize_and_normalize(text_a)
    tokens_b = tokenize_and_normalize(text_b)
    s_lex = jaccard_similarity(tokens_a, tokens_b)

    # Domain veto: If both events have text and lexical overlap is essentially 0 and actor overlap is 0, veto
    if tokens_a and tokens_b and s_lex == 0.0 and s_actor <= 0.3:
        return ClusterMatchScore(
            event_type_score=s_type,
            temporal_score=s_temp,
            location_score=s_loc,
            actor_overlap_score=s_actor,
            entity_overlap_score=s_ent,
            lexical_score=0.0,
            final_score=0.0,
            threshold=threshold,
            is_match=False,
            is_vetoed=True,
            veto_reason="zero_lexical_and_actor_overlap",
            candidate_cluster_id=candidate_cluster_id,
        )

    # Weighted composite score calculation
    final_score = (
        WEIGHT_EVENT_TYPE * s_type
        + WEIGHT_TEMPORAL * s_temp
        + WEIGHT_LOCATION * s_loc
        + WEIGHT_ACTOR * s_actor
        + WEIGHT_ENTITY * s_ent
        + WEIGHT_LEXICAL * s_lex
    )

    is_match = final_score >= threshold

    return ClusterMatchScore(
        event_type_score=s_type,
        temporal_score=s_temp,
        location_score=s_loc,
        actor_overlap_score=s_actor,
        entity_overlap_score=s_ent,
        lexical_score=s_lex,
        final_score=final_score,
        threshold=threshold,
        is_match=is_match,
        is_vetoed=False,
        veto_reason=None,
        candidate_cluster_id=candidate_cluster_id,
    )
