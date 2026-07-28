"""Shared DuckDB SQL queries for flight data analysis."""

from .flight_queries import (
    get_parquet_path,
    flight_summary,
    speed_distribution,
    speed_analysis,
    altitude_profile,
    altitude_stats,
    acceleration_stats,
    topic_distribution,
    trajectory_sample,
    validate_parquet,
)

__all__ = [
    "get_parquet_path",
    "flight_summary",
    "speed_distribution",
    "speed_analysis",
    "altitude_profile",
    "altitude_stats",
    "acceleration_stats",
    "topic_distribution",
    "trajectory_sample",
    "validate_parquet",
]
