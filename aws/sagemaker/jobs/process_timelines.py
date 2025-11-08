import json
import boto3
import pandas as pd
from typing import List, Dict, Tuple
import numpy as np
import time
from io import StringIO
import re
import os

# ==============================================================================
# CLASS 1: CRITICAL MOMENT DETECTOR
# ==============================================================================

class CriticalMomentDetector:
    """
    Identifies critical moments in matches from timeline data
    """
    
    def __init__(self):
        pass 
        
    def detect_critical_moments(self, timeline_data: Dict) -> List[Dict]:
        critical_moments = []
        frames = timeline_data.get('info', {}).get('frames', [])
        processed_timestamps = set()

        for i, frame in enumerate(frames):
            teamfight = self._detect_teamfight(frame, frames, i)
            if teamfight and teamfight['timestamp'] not in processed_timestamps:
                critical_moments.append({
                    'type': 'TEAMFIGHT',
                    'timestamp': teamfight['timestamp_sec'],
                    'details': teamfight,
                    'impact_score': teamfight['impact_score']
                })
                processed_timestamps.add(teamfight['timestamp'])
            
            objective_contest = self._detect_objective_contest(frame, frames, i)
            if objective_contest and objective_contest['timestamp'] not in processed_timestamps:
                critical_moments.append({
                    'type': 'OBJECTIVE',
                    'timestamp': objective_contest['timestamp_sec'],
                    'details': objective_contest,
                    'impact_score': objective_contest['impact_score']
                })
                processed_timestamps.add(objective_contest['timestamp'])

        critical_moments.sort(key=lambda x: x['impact_score'], reverse=True)
        return critical_moments[:10]

    def _detect_teamfight(self, frame: Dict, all_frames: List, frame_idx: int) -> Dict:
        events = frame.get('events', [])
        kills = [e for e in events if e.get('type') == 'CHAMPION_KILL']
        
        if len(kills) < 2: return None
        
        first_kill_time = kills[0].get('timestamp', 0)
        positions = []
        valid_kills = []
        
        for kill in kills:
            kill_time = kill.get('timestamp', 0)
            if kill_time - first_kill_time > 10000: break
            pos = kill.get('position', {})
            if pos:
                positions.append((pos.get('x', 0), pos.get('y', 0)))
                valid_kills.append(kill)
        
        if len(valid_kills) < 2: return None
            
        gold_swing = sum([k.get('bounty', 300) for k in valid_kills])
        impact_score = len(valid_kills) * 10 + gold_swing / 100
        
        return {
            'kills': len(valid_kills), 'gold_swing': gold_swing,
            'duration': valid_kills[-1].get('timestamp', 0) - first_kill_time,
            'participants_involved': self._get_participants_in_fight(valid_kills),
            'impact_score': impact_score, 'positions': positions,
            'timestamp': first_kill_time, 'timestamp_sec': first_kill_time / 1000.0
        }

    def _detect_objective_contest(self, frame: Dict, all_frames: List, frame_idx: int) -> Dict:
        events = frame.get('events', [])
        elite_kills = [e for e in events if e.get('type') == 'ELITE_MONSTER_KILL']
        
        if not elite_kills: return None
        
        for elite_kill in elite_kills:
            monster_type = elite_kill.get('monsterType', '')
            timestamp = elite_kill.get('timestamp', 0)
            
            kills_nearby = [e for e in events 
                            if e.get('type') == 'CHAMPION_KILL' 
                            and abs(e.get('timestamp', 0) - timestamp) < 15000]
            
            impact_multiplier = 2.0 if monster_type == 'BARON_NASHOR' else 1.5
            impact_score = (30 * impact_multiplier) + (len(kills_nearby) * 10)
            
            if len(kills_nearby) > 0 or monster_type in ['BARON_NASHOR', 'ELDER_DRAGON']:
                return {
                    'monster_type': monster_type, 'killer_team': elite_kill.get('killerTeamId'),
                    'was_contested': len(kills_nearby) > 0, 'nearby_kills': len(kills_nearby),
                    'impact_score': impact_score, 'position': elite_kill.get('position', {}),
                    'timestamp': timestamp, 'timestamp_sec': timestamp / 1000.0
                }
        return None

    def _get_participants_in_fight(self, kills: List[Dict]) -> Dict:
        participants = {'killers': set(), 'victims': set(), 'assistants': set()}
        for kill in kills:
            participants['killers'].add(kill.get('killerId'))
            participants['victims'].add(kill.get('victimId'))
            participants['assistants'].update(kill.get('assistingParticipantIds', []))
        
        return {
            'killers': list(participants['killers']), 'victims': list(participants['victims']),
            'assistants': list(participants['assistants'])
        }

# ==============================================================================
# CLASS 2: HYPOTHETICAL SIMULATOR
# ==============================================================================

class HypotheticalSimulator:
    def __init__(self):
        pass
        
    def prepare_teamfight_features(self, moment: Dict, match_data: Dict, 
                                     timeline_data: Dict) -> np.ndarray:
        timestamp_ms = moment['timestamp'] * 1000
        frames = timeline_data.get('info', {}).get('frames', [])
        if not frames: return None

        frame = min(frames, key=lambda x: abs(x.get('timestamp', 0) - timestamp_ms))
        participants = frame.get('participantFrames', {})
        
        blue_team_ids = [1, 2, 3, 4, 5]
        red_team_ids = [6, 7, 8, 9, 10]
        features = []
        
        blue_gold = sum([participants.get(str(pid), {}).get('totalGold', 0) for pid in blue_team_ids])
        red_gold = sum([participants.get(str(pid), {}).get('totalGold', 0) for pid in red_team_ids])
        features.append((blue_gold - red_gold) / 1000.0)
        
        blue_levels = [participants.get(str(pid), {}).get('level', 0) for pid in blue_team_ids]
        red_levels = [participants.get(str(pid), {}).get('level', 0) for pid in red_team_ids]
        features.append(sum(blue_levels) - sum(red_levels))
        
        features.extend([5.0, 5.0])
        
        blue_positions = [(p.get('position', {}).get('x', 0), p.get('position', {}).get('y', 0)) 
                          for p in (participants.get(str(pid), {}) for pid in blue_team_ids)]
        red_positions = [(p.get('position', {}).get('x', 0), p.get('position', {}).get('y', 0)) 
                         for p in (participants.get(str(pid), {}) for pid in red_team_ids)]
            
        features.extend([self._calculate_team_spread(blue_positions) / 1000.0, 
                         self._calculate_team_spread(red_positions) / 1000.0])
        
        features.extend([0.6, 0.6, 0.7, 0.7, 1.0, 1.0, 0.5, 0.5])
        
        while len(features) < 50:
            features.append(0.0)
        
        return np.array(features[:50], dtype=np.float32)

    def _calculate_team_spread(self, positions: List[Tuple[float, float]]) -> float:
        if len(positions) < 2: return 0.0
        distances = []
        for i in range(len(positions)):
            for j in range(i + 1, len(positions)):
                dist = np.sqrt((positions[i][0] - positions[j][0]) ** 2 + (positions[i][1] - positions[j][1]) ** 2)
                distances.append(dist)
        return np.mean(distances) if distances else 0.0

# ==============================================================================
# CLASS 3: ATHENA HELPER
# ==============================================================================

class AthenaQuery:
    def __init__(self, database: str, s3_output: str, region: str = 'us-west-2'):
        self.athena_client = boto3.client('athena', region_name=region)
        self.database = database
        self.s3_output = s3_output
        self.s3_client = boto3.client('s3', region_name=region)

    def run_query(self, query: str) -> str:
        print(f"Running Athena query: {query[:60]}...", flush=True)
        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.s3_output}
        )
        return response['QueryExecutionId']

    def wait_for_query(self, execution_id: str, max_wait: int = 120000): # Increased wait time
        start_time = time.time()
        while time.time() - start_time < max_wait:
            response = self.athena_client.get_query_execution(QueryExecutionId=execution_id)
            status = response['QueryExecution']['Status']['State']
            if status == 'SUCCEEDED':
                print(f"Query succeeded in {time.time() - start_time:.1f}s", flush=True)
                return True
            elif status in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Query failed: {reason}")
            time.sleep(5) # Poll less frequently
        raise Exception(f"Query timed out after {max_wait}s")

    def get_query_results(self, execution_id: str) -> pd.DataFrame:
        response = self.athena_client.get_query_execution(QueryExecutionId=execution_id)
        s3_path = response['QueryExecution']['ResultConfiguration']['OutputLocation']
        match = re.match(r"s3://([^/]+)/(.+)", s3_path)
        if not match: raise ValueError(f"Could not parse S3 path: {s3_path}")
        bucket, key = match.group(1), match.group(2)
        obj = self.s3_client.get_object(Bucket=bucket, Key=key)
        return pd.read_csv(StringIO(obj['Body'].read().decode('utf-8')))

    def repair_table(self, table_name: str):
        print(f"Repairing table {table_name}. This may take a few minutes...", flush=True)
        repair_query = f"MSCK REPAIR TABLE `{table_name}`"
        try:
            exec_id = self.run_query(repair_query)
            self.wait_for_query(exec_id, max_wait=120000) 
            print("Table repair query finished.", flush=True)
        except Exception as e:
            print(f"Warning: Table repair failed. This might be okay. Error: {e}", flush=True)

# ==============================================================================
# MAIN DRIVER SCRIPT (NEW BATCHING LOGIC)
# ==============================================================================

def chunk_list(data: List, size: int):
    """Yield successive n-sized chunks from a list."""
    for i in range(0, len(data), size):
        yield data[i:i + size]

def get_all_timeline_files(bucket: str, prefix: str) -> Dict[str, str]:
    print(f"Step 1: Scanning S3 bucket {bucket} for timeline files...", flush=True)
    s3_paginator = boto3.client('s3').get_paginator('list_objects_v2')
    match_map = {}
    key_regex = re.compile(r"raw-matches/[^/]+/(NA1_\d+|EUW1_\d+|KR_\d+)/timeline-data\.json")
    page_count = 0
    file_count = 0

    for page in s3_paginator.paginate(Bucket=bucket, Prefix=prefix):
        page_count += 1
        if 'Contents' not in page: continue
        for obj in page['Contents']:
            key = obj['Key']
            match = key_regex.search(key)
            if match:
                match_id = match.group(1)
                match_map[match_id] = key
                file_count += 1
        if page_count % 100 == 0:
             print(f"Scanned {page_count * 1000} objects, found {file_count} timelines...", flush=True)

    print(f"Step 1 Complete: Found {len(match_map)} timeline files in S3.", flush=True)
    return match_map

def get_match_outcomes(athena: AthenaQuery, match_ids: List[str], match_features_table: str) -> Dict[str, int]:
    print(f"Step 2: Querying Athena for {len(match_ids)} match outcomes in batches...", flush=True)
    BATCH_SIZE = 10000
    full_outcome_map = {}
    batch_num = 0
    total_batches = (len(match_ids) // BATCH_SIZE) + 1
    
    for batch_match_ids in chunk_list(match_ids, BATCH_SIZE):
        batch_num += 1
        print(f"  - Processing batch {batch_num}/{total_batches}...", flush=True)
        match_id_str = ", ".join([f"'{mid}'" for mid in batch_match_ids])
        
        query = f"""
        SELECT 
            match_id,
            MAX(CASE WHEN team_id = 100 THEN win ELSE 0 END) as blue_won
        FROM {match_features_table}
        WHERE match_id IN ({match_id_str})
        GROUP BY 1
        """
        
        try:
            exec_id = athena.run_query(query)
            athena.wait_for_query(exec_id)
            results_df = athena.get_query_results(exec_id)
            batch_map = pd.Series(results_df.blue_won.values, index=results_df.match_id).to_dict()
            full_outcome_map.update(batch_map)
        except Exception as e:
            print(f"  - Error processing batch {batch_num}: {e}", flush=True)
            continue
    
    print(f"Step 2 Complete: Found outcomes for {len(full_outcome_map)} matches.", flush=True)
    return full_outcome_map

# --- NEW FUNCTION TO SAVE BATCHES ---
def save_batch_to_s3(batch_data: List[Dict], bucket: str, batch_num: int):
    """Converts a list of row-dictionaries to a DataFrame and saves to S3 as Parquet."""
    if not batch_data:
        print(f"Batch {batch_num} is empty. Skipping save.", flush=True)
        return
        
    print(f"\nSaving batch {batch_num} with {len(batch_data)} samples to S3...", flush=True)
    df = pd.DataFrame(batch_data)
    
    # Define S3 key for this batch
    s3_key = f"training/batch_output/teamfight_data_batch_{batch_num}.parquet"
    s3_path = f"s3://{bucket}/{s3_key}"
    
    try:
        df.to_parquet(s3_path, index=False)
        print(f"Successfully saved {s3_key}", flush=True)
    except Exception as e:
        print(f"Error saving batch {batch_num} to S3: {e}", flush=True)


def process_all_matches(
    athena: AthenaQuery, 
    detector: CriticalMomentDetector, 
    simulator: HypotheticalSimulator,
    raw_bucket: str, 
    processed_bucket: str,
    match_features_table: str
):
    """
    Main ETL function, now with batch processing to save memory.
    """
    s3_client = boto3.client('s3')
    
    # 1. Get all timeline files
    match_map = get_all_timeline_files(bucket=raw_bucket, prefix="raw-matches/")
    if not match_map:
        print("Fatal Error: No timeline files found.", flush=True)
        return
        
    # 2. Get outcomes for all found matches
    match_ids_list = list(match_map.keys())
    outcome_map = get_match_outcomes(athena, match_ids_list, match_features_table)
    
    print(f"Step 3: Processing {len(outcome_map)} matches with known outcomes...", flush=True)
    
    # --- BATCHING LOGIC ---
    BATCH_SIZE = 10000  # Process 10,000 matches before saving
    batch_num = 0
    training_data_rows = []
    total_processed_count = 0
    # -----------------------

    for match_id, outcome in outcome_map.items():
        timeline_key = match_map.get(match_id)
        if not timeline_key: continue
            
        try:
            file_obj = s3_client.get_object(Bucket=raw_bucket, Key=timeline_key)
            timeline_data = json.loads(file_obj['Body'].read())
        except Exception as e:
            print(f"Warning: Could not load timeline {timeline_key}. Skipping. Error: {e}", flush=True)
            continue
            
        moments = detector.detect_critical_moments(timeline_data)
        
        for moment in moments:
            features = simulator.prepare_teamfight_features(moment, {}, timeline_data)
            if features is not None:
                feature_dict = {f'feature_{i}': val for i, val in enumerate(features)}
                feature_dict['match_id'] = match_id
                feature_dict['outcome'] = int(outcome)
                training_data_rows.append(feature_dict)
        
        total_processed_count += 1
        
        # --- SAVE BATCH AND CLEAR MEMORY ---
        if total_processed_count % BATCH_SIZE == 0:
            save_batch_to_s3(training_data_rows, processed_bucket, batch_num)
            training_data_rows.clear() 
            batch_num += 1
            print(f"Processed {total_processed_count}/{len(outcome_map)} matches...", flush=True)
            
    # --- SAVE THE FINAL BATCH ---
    if training_data_rows:
        save_batch_to_s3(training_data_rows, processed_bucket, batch_num)
        training_data_rows.clear()
        
    print(f"Step 4: Finished processing all {total_processed_count} matches.", flush=True)
    print(f"Training data batches saved to s3://{processed_bucket}/training/batch_output/", flush=True)


if __name__ == "__main__":
    RAW_DATA_BUCKET = 'lol-training-matches-150k' 
    PROCESSED_DATA_BUCKET = 'lol-coach-processed-data'
    ATHENA_DB = 'lol_coach_db'
    MATCH_FEATURES_TABLE = 'match_features' 
    ATHENA_RESULTS_S3 = f"s3://{PROCESSED_DATA_BUCKET}/athena-results/"
    AWS_REGION = 'us-west-2'
    
    print("--- SCRIPT STARTED (BATCH PROCESSING LOGIC). Initializing helpers... ---", flush=True)
    
    athena = AthenaQuery(database=ATHENA_DB, s3_output=ATHENA_RESULTS_S3, region=AWS_REGION)
    detector = CriticalMomentDetector()
    simulator = HypotheticalSimulator()

    try:
        print("\nStep 1.5: Attempting to repair Athena table metadata...", flush=True)
        #athena.repair_table(MATCH_FEATURES_TABLE)
        print("Step 1.5 Complete.\n", flush=True)
    except Exception as e:
        print(f"Warning: MSCK REPAIR TABLE failed: {e}", flush=True)

    print("Starting timeline processing job...", flush=True)
    process_all_matches(
        athena=athena,
        detector=detector,
        simulator=simulator,
        raw_bucket=RAW_DATA_BUCKET,
        processed_bucket=PROCESSED_DATA_BUCKET,
        match_features_table=MATCH_FEATURES_TABLE
    )
    print("Timeline processing job complete.", flush=True)