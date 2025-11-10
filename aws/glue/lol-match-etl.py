import sys
import boto3
import json
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import *
from pyspark.sql.types import *
from pyspark.sql.window import Window

args = getResolvedOptions(sys.argv, ['JOB_NAME', 'S3_INPUT_BUCKET', 'S3_OUTPUT_BUCKET'])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args['JOB_NAME'], args)

def flatten_match_data(s3_bucket):
    """
    Flattens nested JSON match data into tabular format for ML
    """
    
    # Read all match-data.json files
    df_match = spark.read.json(f"s3://{s3_bucket}/*/*/*/match-data.json")
    
    # Explode participants array to get one row per player per match
    df_participants = df_match.select(
        col("metadata.matchId").alias("match_id"),
        col("info.gameCreation").alias("game_creation"),
        col("info.gameDuration").alias("game_duration"),
        col("info.gameVersion").alias("game_version"),
        explode("info.participants").alias("participant")
    )
    
    # Flatten participant data - extract key features
    df_flat = df_participants.select(
        "match_id",
        "game_creation",
        "game_duration",
        col("participant.puuid").alias("puuid"),                # get player unique ID
        col("participant.riotIdGameName").alias("game_name"),   # get player in-game name
        col("participant.riotIdTagline").alias("tagline"),      # get player tagline
        col("participant.championName").alias("champion"),      # get champion played
        col("participant.teamPosition").alias("position"),      # get lane
        col("participant.teamId").alias("team_id"),             # get team (100 or 200)
        col("participant.win").cast(IntegerType()).alias("win"),                    # did the player win?
        
        # Core stats
        col("participant.kills").alias("kills"),                                        # number of kills
        col("participant.deaths").alias("deaths"),                                      # number of deaths
        col("participant.assists").alias("assists"),                                    # number of assists
        col("participant.champLevel").alias("champ_level"),                             # champion level
        col("participant.totalMinionsKilled").alias("cs"),                              # creep score
        col("participant.neutralMinionsKilled").alias("jungle_cs"),                     # jungle creep score
        col("participant.goldEarned").alias("gold_earned"),                             # gold earned
        col("participant.totalDamageDealtToChampions").alias("damage_to_champions"),    # total damage to champions
        col("participant.totalDamageTaken").alias("damage_taken"),                      # total damage taken
        col("participant.visionScore").alias("vision_score"),                           # vision score
        col("participant.wardsPlaced").alias("wards_placed"),                           # number of wards placed
        col("participant.wardsKilled").alias("wards_killed"),                           # number of wards killed
        col("participant.damageDealtToTurrets").alias("damage_to_turrets"),             # damage to turrets                      # crowd control time
        col("participant.firstBloodKill").alias("first_blood"),                         # first blood kill?

        # Objectives
        col("participant.turretKills").alias("turret_kills"),
        col("participant.inhibitorKills").alias("inhibitor_kills"),
        col("participant.dragonKills").alias("dragon_kills"),
        col("participant.baronKills").alias("baron_kills"),
        
        # Advanced stats from challenges
        col("participant.challenges.killParticipation").alias("kill_participation"),    # kill participation %
        col("participant.challenges.soloKills").alias("solo_kills"),                    # number of solo kills
        col("participant.challenges.damagePerMinute").alias("dpm"),                     # damage per minute
        col("participant.challenges.goldPerMinute").alias("gpm"),                       # gold per minute
        col("participant.challenges.visionScorePerMinute").alias("vspm"),
        col("participant.challenges.earlyLaningPhaseGoldExpAdvantage").alias("early_gold_advantage"),
        col("participant.challenges.maxCsAdvantageOnLaneOpponent").alias("max_cs_advantage"),
        col("participant.challenges.laneMinionsFirst10Minutes").alias("cs_at_10"),
        col("participant.challenges.jungleCsBefore10Minutes").alias("jungle_cs_at_10"),
        col("participant.challenges.visionScoreAdvantageLaneOpponent").alias("vision_advantage"),
        
        # Behavioral indicators
        col("participant.timeCCingOthers").alias("cc_time"),
        col("participant.totalTimeSpentDead").alias("time_dead"),
        col("participant.longestTimeSpentLiving").alias("longest_time_alive"),
        col("participant.damageSelfMitigated").alias("damage_mitigated"),
        col("participant.totalHeal").alias("total_heal"),
        col("participant.totalHealsOnTeammates").alias("heals_on_teammates"),
        col("participant.totalDamageShieldedOnTeammates").alias("shields_on_teammates"),
        
        # Positioning/playstyle indicators
        col("participant.challenges.outnumberedKills").alias("outnumbered_kills"),
        col("participant.challenges.killsUnderOwnTurret").alias("kills_under_tower"),
        col("participant.challenges.killsNearEnemyTurret").alias("kills_near_enemy_tower"),
        col("participant.challenges.pickKillWithAlly").alias("pick_kills_with_ally"),
        col("participant.challenges.effectiveHealAndShielding").alias("effective_heal_shield"),
        
        # Team fighting
        col("participant.challenges.teamDamagePercentage").alias("team_damage_pct"),
        col("participant.challenges.damageTakenOnTeamPercentage").alias("team_damage_taken_pct"),
        
        # Objective control
        col("participant.damageDealtToObjectives").alias("objective_damage"),
        col("participant.challenges.epicMonsterKillsWithin30SecondsOfSpawn").alias("epic_monster_kills_early"),
        col("participant.challenges.riftHeraldTakedowns").alias("herald_takedowns"),
        col("participant.challenges.dragonTakedowns").alias("dragon_takedowns")
    )
    
    # Calculate derived features
    df_features = df_flat.withColumn(
        "kda", 
        when(col("deaths") == 0, 
             (col("kills") + col("assists")))
        .otherwise((col("kills") + col("assists")) / col("deaths"))
    ).withColumn(
        "game_duration_minutes", 
        col("game_duration") / 60
    ).withColumn(
        "cs_per_min",
        col("cs") / (col("game_duration") / 60)
    ).withColumn(
        "death_rate_per_min",
        col("deaths") / (col("game_duration") / 60)
    ).withColumn(
        "gold_efficiency",
        col("gpm")
    )
    
    return df_features

def create_player_aggregates(df_features):
    """
    Create player-level aggregate statistics
    """
    
    # drop duplicates
    df_features = df_features.dropDuplicates(["match_id", "puuid"])

    # Group by player and calculate aggregates
    player_stats = df_features.groupBy("game_name", "tagline").agg(
        count("*").alias("total_games"),
        avg("win").alias("win_rate"),
        avg("kills").alias("avg_kills"),
        avg("deaths").alias("avg_deaths"),
        avg("assists").alias("avg_assists"),
        avg("kda").alias("avg_kda"),
        avg("cs_per_min").alias("avg_cs_per_min"),
        avg("gpm").alias("avg_gpm"),
        avg("dpm").alias("avg_dpm"),
        avg("vision_score").alias("avg_vision_score"),
        avg("kill_participation").alias("avg_kill_participation"),
        avg("early_gold_advantage").alias("avg_early_gold_adv"),
        avg("cs_at_10").alias("avg_cs_at_10"),
        avg("team_damage_pct").alias("avg_team_damage_pct"),
        avg("objective_damage").alias("avg_objective_damage"),
        coalesce(stddev("deaths"), lit(0.0)).alias("death_consistency"),
        coalesce(stddev("cs_per_min"), lit(0.0)).alias("cs_consistency")
    )
    
    return player_stats

# Execute ETL
print("Starting ETL process...")
df_features = flatten_match_data(args['S3_INPUT_BUCKET'])
df_player_stats = create_player_aggregates(df_features)

# Write to S3 in Parquet format for efficient querying
output_bucket = args['S3_OUTPUT_BUCKET']

df_features.coalesce(5).write.mode("overwrite").parquet(
    f"s3://{output_bucket}/processed/match_features/"
)

df_player_stats.write.mode("overwrite").parquet(
    f"s3://{output_bucket}/processed/player_aggregates/"
)

print("ETL process completed successfully")
job.commit()