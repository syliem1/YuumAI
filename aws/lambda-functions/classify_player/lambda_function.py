import json
import requests
import time
import os
import boto3
import pandas as pd
import numpy as np
import math

session = requests.Session()
sagemaker_runtime = boto3.client('sagemaker-runtime')
s3 = boto3.client('s3')

RIOT_API_KEY = os.environ['RIOT_API_KEY']
ENDPOINT_NAME = os.environ['ENDPOINT_NAME']
GLOBAL_STATS_S3_PATH = "s3://player-classifier-extra-files/percentile-files/global_avg.json"
RETRY_TIMER = 15

def get_s3_json(s3_uri: str):
    if not s3_uri.startswith("s3://"):
        raise ValueError("S3 path must start with s3://")
    bucket, key = s3_uri.replace("s3://", "").split("/", 1)
    response = s3.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def calculate_percentiles(player_stats, global_stats):
    feature_stats = global_stats.get("feature_stats", global_stats)
    regional_stats = global_stats.get("regional_stats", {})

    stats = list(feature_stats.keys())
    player_vals = np.array([player_stats.get(stat, np.nan) for stat in stats])
    means = np.array([feature_stats[stat].get("mean", 0.0) for stat in stats])
    stds = np.array([feature_stats[stat].get("std", 1.0) for stat in stats])

    valid_mask = np.isfinite(player_vals) & (stds != 0)
    z = np.zeros_like(player_vals)
    z[valid_mask] = (player_vals[valid_mask] - means[valid_mask]) / stds[valid_mask]

    pct = 50 * (1 + np.vectorize(math.erf)(z / math.sqrt(2)))
    pct = np.clip(pct, 0, 100)

    percentiles = {stat: round(p, 2) for stat, p in zip(stats, pct)}

    regional_keys = [
        "bandle", "bilgewater", "demacia", "ionia", "ixtal", "noxus",
        "piltover", "shadow_isles", "shurima", "targon", "freljord",
        "void", "zaun"
    ]
    for region in regional_keys:
        player_val = player_stats.get(region)
        if player_val is None:
            continue

        stat_group = regional_stats if region in regional_stats else feature_stats
        mean_val = stat_group.get(region, {}).get("mean", 0.0)
        std_val = stat_group.get(region, {}).get("std", 1.0)
        if std_val == 0:
            pct_val = 50.0
        else:
            z = (player_val - mean_val) / std_val
            pct_val = 50 * (1 + math.erf(z / math.sqrt(2)))
        percentiles[region] = round(np.clip(pct_val, 0, 100), 2)

    return percentiles


# from populate_match_data lambda
def get_puuid_by_riot_id(game_name, tag_line):
    ''' fetches puuid using a player's game name and tag line '''

    try:
        url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}"
        params = {'api_key': RIOT_API_KEY}
        response = session.get(url, params=params)
        response.raise_for_status()
        return response.json().get('puuid')

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get('Retry-After', RETRY_TIMER))
            print(f"Rate limit hit getting puuid. Waiting {retry_after} seconds.")
            time.sleep(retry_after)
            return get_puuid_by_riot_id(game_name, tag_line)
        elif e.response.status_code == 503:
            retry_after = int(e.response.headers.get('Retry-After', RETRY_TIMER))
            print(f"Riot service unavailable, waiting {retry_after} seconds.")
            time.sleep(retry_after)
            return get_puuid_by_riot_id(game_name, tag_line)
        elif e.response.status_code == 401:
            print(f"401 Unauthorized error getting puuid for {game_name}#{tag_line}: {e}")
            raise 
        print(f"HTTP Error getting puuid for {game_name}#{tag_line}: {e}")
        return None

    except Exception as e:
        print(f"Unexpected error getting puuid for {game_name}#{tag_line}: {e}")
        return None

# from populate_match_data lambda
def fetch_and_process_match(match_id):
    ''' gets a single match from a player '''

    try:
        detail_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
        timeline_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        params = {'api_key': RIOT_API_KEY}
        
        response = session.get(detail_url, params=params)
        response.raise_for_status()
        match_data = response.json()
        # get timeline
        response = session.get(timeline_url, params=params)
        response.raise_for_status()
        timeline_data = response.json()
        return match_data, timeline_data
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            retry_after = int(e.response.headers.get('Retry-After', RETRY_TIMER))
            print(f"Rate limit hit fetching match details. Waiting for {retry_after} seconds.")
            time.sleep(retry_after)
            return fetch_and_process_match(match_id)
        elif e.response.status_code == 503:
            retry_after = int(e.response.headers.get('Retry-After', RETRY_TIMER))
            print(f"Riot service unavailable, waiting {retry_after} seconds.")
            time.sleep(retry_after)
            return fetch_and_process_match(match_id)
        elif e.response.status_code == 401:
            print(f"401 Unauthorized error fetching match {match_id}: {e}")
            raise  
        else:
            print(f"HTTP Error fetching match {match_id}: {e}")
            return None

    except Exception as e:
        print(f"An unexpected error occurred processing match {match_id}: {e}")
        return None

# modified version from lol-match-etl
def get_player_vector(match_data, target_puuid):
    try:
        if isinstance(match_data, str):
            df_match = pd.json_normalize(json.loads(match_data))
        else:
            df_match = pd.json_normalize(match_data)
        participants = df_match.loc[0, "info.participants"]
        player_data = next((p for p in participants if p.get("puuid") == target_puuid), None)
        df_participant = pd.json_normalize(player_data).add_prefix("participant.")
        df_participant["metadata.matchId"] = df_match.loc[0, "metadata.matchId"]
        df_participant["info.gameCreation"] = df_match.loc[0, "info.gameCreation"]
        df_participant["info.gameDuration"] = df_match.loc[0, "info.gameDuration"]
        df_participant["info.gameVersion"] = df_match.loc[0, "info.gameVersion"]

        cols = {
            "metadata.matchId": "match_id",
            "info.gameCreation": "game_creation",
            "info.gameDuration": "game_duration",
            "info.gameVersion": "game_version",
            "participant.puuid": "puuid",
            "participant.riotIdGameName": "game_name",
            "participant.riotIdTagline": "tagline",
            "participant.championName": "champion",
            "participant.teamPosition": "position",
            "participant.teamId": "team_id",
            "participant.win": "win",
            "participant.kills": "kills",
            "participant.deaths": "deaths",
            "participant.assists": "assists",
            "participant.champLevel": "champ_level",
            "participant.totalMinionsKilled": "cs",
            "participant.neutralMinionsKilled": "jungle_cs",
            "participant.goldEarned": "gold_earned",
            "participant.totalDamageDealtToChampions": "damage_to_champions",
            "participant.totalDamageTaken": "damage_taken",
            "participant.visionScore": "vision_score",
            "participant.wardsPlaced": "wards_placed",
            "participant.wardsKilled": "wards_killed",
            "participant.damageDealtToTurrets": "damage_to_turrets",
            "participant.firstBloodKill": "first_blood",
            "participant.turretKills": "turret_kills",
            "participant.inhibitorKills": "inhibitor_kills",
            "participant.dragonKills": "dragon_kills",
            "participant.baronKills": "baron_kills",
            "participant.challenges.killParticipation": "kill_participation",
            "participant.challenges.soloKills": "solo_kills",
            "participant.challenges.damagePerMinute": "dpm",
            "participant.challenges.goldPerMinute": "gpm",
            "participant.challenges.visionScorePerMinute": "vspm",
            "participant.challenges.earlyLaningPhaseGoldExpAdvantage": "early_gold_advantage",
            "participant.challenges.maxCsAdvantageOnLaneOpponent": "max_cs_advantage",
            "participant.challenges.laneMinionsFirst10Minutes": "cs_at_10",
            "participant.challenges.jungleCsBefore10Minutes": "jungle_cs_at_10",
            "participant.challenges.visionScoreAdvantageLaneOpponent": "vision_advantage",
            "participant.timeCCingOthers": "cc_time",
            "participant.totalTimeSpentDead": "time_dead",
            "participant.longestTimeSpentLiving": "longest_time_alive",
            "participant.damageSelfMitigated": "damage_mitigated",
            "participant.totalHeal": "total_heal",
            "participant.totalHealsOnTeammates": "heals_on_teammates",
            "participant.totalDamageShieldedOnTeammates": "shields_on_teammates",
            "participant.challenges.outnumberedKills": "outnumbered_kills",
            "participant.challenges.killsUnderOwnTurret": "kills_under_tower",
            "participant.challenges.killsNearEnemyTurret": "kills_near_enemy_tower",
            "participant.challenges.pickKillWithAlly": "pick_kills_with_ally",
            "participant.challenges.effectiveHealAndShielding": "effective_heal_shield",
            "participant.challenges.teamDamagePercentage": "team_damage_pct",
            "participant.challenges.damageTakenOnTeamPercentage": "team_damage_taken_pct",
            "participant.damageDealtToObjectives": "objective_damage",
            "participant.challenges.epicMonsterKillsWithin30SecondsOfSpawn": "epic_monster_kills_early",
            "participant.challenges.riftHeraldTakedowns": "herald_takedowns",
            "participant.challenges.dragonTakedowns": "dragon_takedowns",
        }

        # Apply mapping
        df_flat = df_participant[list(cols.keys())].rename(columns=cols)

        # Derived features
        df_flat["kda"] = (df_flat["kills"] + df_flat["assists"]) / df_flat["deaths"].replace(0, pd.NA)
        df_flat["kda"].fillna(df_flat["kills"] + df_flat["assists"])

        df_flat["game_duration_minutes"] = df_flat["game_duration"] / 60
        df_flat["cs_per_min"] = df_flat["cs"] / df_flat["game_duration_minutes"]
        df_flat["death_rate_per_min"] = df_flat["deaths"] / df_flat["game_duration_minutes"]
        df_flat["gold_efficiency"] = df_flat["gpm"]

        return df_flat
    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

# modified version from lol-match-etl
def create_player_aggregate(df_features: pd.DataFrame) -> dict:
    df_features = df_features.drop_duplicates(subset=["match_id", "puuid"])

    def safe_mean(col):
        return df_features[col].mean() if col in df_features.columns else 0.0

    # Only keep relevant metrics used downstream
    features = {
        "avg_dpm": safe_mean("dpm"),
        "avg_gpm": safe_mean("gpm"),
        "avg_kill_participation": safe_mean("kill_participation"),
        "avg_kda": safe_mean("kda"),
        "avg_vision_score": safe_mean("vision_score"),
        "avg_cs_per_min": safe_mean("cs_per_min"),
        "avg_team_damage_pct": safe_mean("team_damage_pct"),
        "avg_outnumbered_kills": safe_mean("outnumbered_kills"),
        "avg_solo_kills": safe_mean("solo_kills"),
        "avg_kills_near_tower": safe_mean("kills_near_enemy_tower"),
        "avg_shields_on_teammates": safe_mean("shields_on_teammates"),
        "avg_objective_damage": safe_mean("objective_damage"),
        "avg_dragon_takedowns": safe_mean("dragon_takedowns"),
        "avg_herald_takedowns": safe_mean("herald_takedowns"),
        "avg_early_gold_adv": safe_mean("early_gold_advantage"),
        "avg_turret_kills": safe_mean("turret_kills"),
        "avg_heals_on_teammates": safe_mean("heals_on_teammates"),
        "avg_longest_alive": safe_mean("longest_time_alive"),
        "avg_cc_time": safe_mean("cc_time"),
        "avg_time_dead": safe_mean("time_dead"),
        "avg_pick_kills": safe_mean("pick_kills_with_ally"),
        "death_consistency": df_features["deaths"].std(ddof=0) if len(df_features) > 1 else 0.0,
        "cs_consistency": df_features["cs_per_min"].std(ddof=0) if len(df_features) > 1 else 0.0,
    }

    # --- Region composite scores ---
    features["bandle"] = (
        features["avg_outnumbered_kills"] * 0.4 +
        features["avg_kda"] * 0.3 +
        (features["avg_vision_score"] / 40.0) * 0.3
    )
    features["bilgewater"] = (
        (features["avg_gpm"] / 400) * 0.4 +
        features["avg_solo_kills"] * 0.3 +
        features["avg_kills_near_tower"] * 0.3
    )
    features["demacia"] = (
        features["avg_kill_participation"] * 0.4 +
        features["avg_team_damage_pct"] * 0.3 +
        (features["avg_shields_on_teammates"] / 500) * 0.3
    )
    features["ionia"] = (
        (features["avg_kda"] / 4) * 0.3 +
        ((features["avg_kill_participation"] * features["avg_cs_per_min"]) / 7) * 0.4 +
        (features["avg_vision_score"] / 40) * 0.3
    )
    features["ixtal"] = (
        (features["avg_objective_damage"] / 10000) * 0.4 +
        features["avg_dragon_takedowns"] * 0.3 +
        features["avg_herald_takedowns"] * 0.3
    )
    features["noxus"] = (
        (features["avg_dpm"] / 600) * 0.4 +
        (features["avg_early_gold_adv"] / 500) * 0.3 +
        features["avg_turret_kills"] * 0.3
    )
    features["piltover"] = (
        (features["avg_gpm"] / 400) * 0.4 +
        (features["avg_cs_per_min"] / 7) * 0.3 +
        features["cs_consistency"] * 0.3
    )
    features["shadow_isles"] = (
        (features["avg_heals_on_teammates"] / 1000) * 0.4 +
        (features["avg_longest_alive"] / 600) * 0.3 +
        features["avg_kda"] * 0.3
    )
    features["shurima"] = (
        (features["avg_cs_per_min"] / 7) * 0.5 +
        features["avg_gpm"] * 0.5
    )
    features["targon"] = (
        (features["avg_vision_score"] / 40) * 0.4 +
        (features["avg_shields_on_teammates"] / 500) * 0.3 +
        (features["avg_heals_on_teammates"] / 1000) * 0.3
    )
    features["freljord"] = (
        (features["avg_cc_time"] / 20) * 0.4 +
        (features["avg_time_dead"] / 60) * -0.3 +
        (1 / (features["death_consistency"] + 0.1)) * 0.3
    )
    features["void"] = (
        (features["avg_dpm"] / 600) * 0.4 +
        features["avg_team_damage_pct"] * 0.4 +
        features["avg_solo_kills"] * 0.2
    )
    features["zaun"] = (
        (1 / (features["death_consistency"] + 0.1)) * -0.3 +
        features["avg_outnumbered_kills"] * 0.4 +
        features["avg_pick_kills"] * 0.3
    )

    return features


def get_most_played_champions(df_features: pd.DataFrame, top_n: int = 3) -> dict:
    if "champion" not in df_features.columns:
        return {}

    champ_counts = (
        df_features["champion"]
        .value_counts()
        .head(top_n)
        .to_dict()
    )
    return champ_counts


def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        username = body.get('username')
        tag = body.get('tag')
        
        print(f"Received user: {username}#{tag}")
        if not username or not tag:
            return {'statusCode': 400, 'body': json.dumps({'error': 'Missing username or tag'})}
        puuid = get_puuid_by_riot_id(username, tag)
        
        match_count = body.get('match_count')
        if not match_count:
            return{'statusCode': 400, 'body': json.dumps({'error': 'Missing match count'})}
        
        #fetch most recent ranked matches
        ids_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids"
        start_time = int(time.time()) - (365 * 24 * 60 * 60)
        params = {'startTime': start_time, 'count': match_count, 'queue': 420, 'api_key': RIOT_API_KEY}
        
        response = session.get(ids_url, params=params)
        response.raise_for_status()
        match_ids = response.json()

        matches = []
        timelines = []
        for match_id in match_ids:
            match_data, timeline_data = fetch_and_process_match(match_id)
            matches.append(match_data)
            timelines.append(timeline_data)
        matches_df = pd.DataFrame()
        for match in matches:
            match_df = get_player_vector(match, puuid)
            if match_df is None or not isinstance(match_df, pd.DataFrame):
                print(f"Skipping invalid match {match_id}")
                continue
            matches_df = pd.concat([matches_df, match_df], ignore_index=True)
        features_map = create_player_aggregate(matches_df)
        most_played = get_most_played_champions(matches_df)
        print(f"features: {features_map}")
        global_json = get_s3_json(GLOBAL_STATS_S3_PATH)
        global_feature_stats = global_json.get("feature_stats", {})
        print(f"global stats: {global_feature_stats}")
        percentiles = calculate_percentiles(features_map, global_feature_stats)

        print(f"percentiles: {percentiles}")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'features': features_map,
                'percentiles': percentiles,
                'most-played': most_played
            })
        }

    except Exception as e:
        print(f"Error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
