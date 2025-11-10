import json
import boto3
from pyspark.sql import SparkSession
from pyspark.sql.functions import mean as _mean, stddev as _stddev, col
from pyspark.sql.types import NumericType

S3_AGG_FEATURES = "s3://lol-coach-processed-data/processed/player_aggregates/"
S3_OUTPUT_PATH = "s3://player-classifier-extra-files/percentile-files/global_avg.json"

spark = SparkSession.builder.appName("AggregateFeatureStats").getOrCreate()

print("Reading aggregate features from:", S3_AGG_FEATURES)
df = spark.read.parquet(S3_AGG_FEATURES)

numeric_cols = [f.name for f in df.schema.fields if isinstance(f.dataType, NumericType)]

if not numeric_cols:
    raise ValueError("No numeric columns found in input parquet files!")

df = df.select(*numeric_cols)

agg_exprs = []
for c in numeric_cols:
    agg_exprs.append(_mean(col(c)).alias(f"{c}_mean"))
    agg_exprs.append(_stddev(col(c)).alias(f"{c}_std"))

agg_df = df.agg(*agg_exprs)
agg_values = agg_df.collect()[0].asDict()

stats = {}
for c in numeric_cols:
    stats[c] = {
        "mean": float(agg_values.get(f"{c}_mean", 0.0) or 0.0),
        "std": float(agg_values.get(f"{c}_std", 0.0) or 0.0)
    }

def safe_get(key):
    return stats.get(key, {}).get("mean", 0.0)

agg_features = {}

agg_features["bandle"] = (
    safe_get("avg_outnumbered_kills") * 0.4 +
    safe_get("avg_kda") * 0.3 +
    (safe_get("avg_vision_score") / 40.0) * 0.3
)
agg_features["bilgewater"] = (
    (safe_get("avg_gpm") / 400) * 0.4 +
    safe_get("avg_solo_kills") * 0.3 +
    safe_get("avg_kills_near_tower") * 0.3
)
agg_features["demacia"] = (
    safe_get("avg_kill_participation") * 0.4 +
    safe_get("avg_team_damage_pct") * 0.3 +
    (safe_get("avg_shields_on_teammates") / 500) * 0.3
)
agg_features["ionia"] = (
    (safe_get("avg_kda") / 4) * 0.3 +
    ((safe_get("avg_kill_participation") * safe_get("avg_cs_per_min")) / 7) * 0.4 +
    (safe_get("avg_vision_score") / 40) * 0.3
)
agg_features["ixtal"] = (
    (safe_get("avg_objective_damage") / 10000) * 0.4 +
    safe_get("avg_dragon_takedowns") * 0.3 +
    safe_get("avg_herald_takedowns") * 0.3
)
agg_features["noxus"] = (
    (safe_get("avg_dpm") / 600) * 0.4 +
    (safe_get("avg_early_gold_adv") / 500) * 0.3 +
    safe_get("avg_turret_kills") * 0.3
)
agg_features["piltover"] = (
    (safe_get("avg_gpm") / 400) * 0.4 +
    (safe_get("avg_cs_per_min") / 7) * 0.3 +
    safe_get("cs_consistency") * 0.3
)
agg_features["shadow_isles"] = (
    (safe_get("avg_heals_on_teammates") / 1000) * 0.4 +
    (safe_get("avg_longest_alive") / 600) * 0.3 +
    safe_get("avg_kda") * 0.3
)
agg_features["shurima"] = (
    (safe_get("avg_cs_per_min") / 7) * 0.5 +
    safe_get("avg_gpm") * 0.5
)
agg_features["targon"] = (
    (safe_get("avg_vision_score") / 40) * 0.4 +
    (safe_get("avg_shields_on_teammates") / 500) * 0.3 +
    (safe_get("avg_heals_on_teammates") / 1000) * 0.3
)
agg_features["freljord"] = (
    (safe_get("avg_cc_time") / 20) * 0.4 +
    (safe_get("avg_time_dead") / 60) * -0.3 +
    (1 / (safe_get("death_consistency") + 0.1)) * 0.3
)
agg_features["void"] = (
    (safe_get("avg_dpm") / 600) * 0.4 +
    safe_get("avg_team_damage_pct") * 0.4 +
    safe_get("avg_solo_kills") * 0.2
)
agg_features["zaun"] = (
    (1 / (safe_get("death_consistency") + 0.1)) * -0.3 +
    safe_get("avg_outnumbered_kills") * 0.4 +
    safe_get("avg_pick_kills") * 0.3
)

output_json = {
    "feature_stats": stats,
    "aggregate_features": agg_features
}

print(f"Uploading aggregate-only JSON to {S3_OUTPUT_PATH}")
s3 = boto3.client("s3")

if S3_OUTPUT_PATH.startswith("s3://"):
    path_parts = S3_OUTPUT_PATH.replace("s3://", "").split("/", 1)
    bucket = path_parts[0]
    key = path_parts[1]
else:
    raise ValueError("S3_OUTPUT_PATH must start with s3://")

s3.put_object(
    Bucket=bucket,
    Key=key,
    Body=json.dumps(output_json, indent=2),
    ContentType="application/json"
)

print("Aggregate feature aggregation completed successfully")

spark.stop()
