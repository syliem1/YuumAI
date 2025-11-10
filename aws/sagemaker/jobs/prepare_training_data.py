"""
Prepares training data for ML models from Athena query results
Converts player aggregates and match features into ML-ready format
"""

import boto3
import pandas as pd
import numpy as np
from typing import Dict, List
import time
import json
from io import StringIO

class TrainingDataPreparation:
    """
    Extracts data from Athena and prepares it for SageMaker training
    """
    
    def __init__(self, database: str = 'lol_coach_db', 
                 s3_output_bucket: str = 'lol-coach-processed-data',
                 region: str = 'us-west-2'):
        self.athena_client = boto3.client('athena', region_name=region)
        self.s3_client = boto3.client('s3', region_name=region)
        self.database = database
        self.s3_output_bucket = s3_output_bucket
        self.s3_athena_results = f"s3://{s3_output_bucket}/athena-results/"
        
    def run_athena_query(self, query: str, wait: bool = True) -> str:
        """
        Executes Athena query and returns execution ID
        """
        print(f"Running query: {query[:100]}...")
        
        response = self.athena_client.start_query_execution(
            QueryString=query,
            QueryExecutionContext={'Database': self.database},
            ResultConfiguration={'OutputLocation': self.s3_athena_results}
        )
        
        execution_id = response['QueryExecutionId']
        
        if wait:
            self._wait_for_query(execution_id)
        
        return execution_id
    
    def _wait_for_query(self, execution_id: str, max_wait: int = 18000):
        """
        Waits for Athena query to complete
        """
        print(f"Waiting for query {execution_id}...")
        
        start_time = time.time()
        while time.time() - start_time < max_wait:
            response = self.athena_client.get_query_execution(
                QueryExecutionId=execution_id
            )
            
            status = response['QueryExecution']['Status']['State']
            
            if status == 'SUCCEEDED':
                print(f"Query succeeded in {time.time() - start_time:.1f}s")
                return True
            elif status in ['FAILED', 'CANCELLED']:
                reason = response['QueryExecution']['Status'].get('StateChangeReason', 'Unknown')
                raise Exception(f"Query failed: {reason}")
            
            time.sleep(2)
        
        raise Exception(f"Query timed out after {max_wait}s")
    
    def get_query_results(self, execution_id: str) -> pd.DataFrame:
        """
        Retrieves query results as pandas DataFrame
        """
        # Get S3 location of results
        response = self.athena_client.get_query_execution(
            QueryExecutionId=execution_id
        )
        
        s3_path = response['QueryExecution']['ResultConfiguration']['OutputLocation']
        
        # Parse S3 path
        bucket = s3_path.split('/')[2]
        key = '/'.join(s3_path.split('/')[3:])
        
        # Download results
        obj = self.s3_client.get_object(Bucket=bucket, Key=key)
        df = pd.read_csv(StringIO(obj['Body'].read().decode('utf-8')))
        
        print(f"Retrieved {len(df)} rows")
        return df
    
    def prepare_playstyle_profiler_data(self) -> pd.DataFrame:
        """
        Prepares data for playstyle profiler (clustering model)
        
        Extracts player-level aggregates with behavioral features
        """
        print("\n" + "="*60)
        print("PREPARING PLAYSTYLE PROFILER TRAINING DATA")
        print("="*60)
        
        query = """
        SELECT 
            pa.game_name,
            pa.tagline,
            pa.total_games,
            pa.win_rate,
            pa.avg_kda,
            pa.avg_cs_per_min,
            pa.avg_gpm,
            pa.avg_dpm,
            pa.avg_vision_score,
            pa.avg_kill_participation,
            pa.avg_early_gold_adv,
            pa.avg_cs_at_10,
            pa.avg_team_damage_pct,
            pa.avg_objective_damage,
            pa.death_consistency,
            pa.cs_consistency,
            
            AVG(mf.outnumbered_kills) as avg_outnumbered_kills,
            AVG(mf.kills_near_enemy_tower) as avg_kills_near_tower,
            AVG(mf.solo_kills) as avg_solo_kills,
            AVG(mf.pick_kills_with_ally) as avg_pick_kills,
            AVG(mf.time_dead) as avg_time_dead,
            AVG(mf.longest_time_alive) as avg_longest_alive,
            AVG(mf.cc_time) as avg_cc_time,
            AVG(mf.heals_on_teammates) as avg_heals_on_teammates,
            AVG(mf.shields_on_teammates) as avg_shields_on_teammates,
            AVG(CASE WHEN mf.position = 'JUNGLE' THEN mf.jungle_cs ELSE 0 END) as avg_jungle_cs,
            AVG(mf.turret_kills) as avg_turret_kills,
            AVG(mf.dragon_takedowns) as avg_dragon_takedowns,
            AVG(mf.herald_takedowns) as avg_herald_takedowns,
            STDDEV(mf.deaths) as death_variance,
            STDDEV(mf.cs_per_min) as cs_variance,
            STDDEV(mf.gold_efficiency) as gold_variance
            
        FROM lol_coach_db.player_aggregates pa
        JOIN lol_coach_db.match_features_27506b28219d8344deb963a9a729bcfb mf 
            ON pa.game_name = mf.game_name 
            AND pa.tagline = mf.tagline
        WHERE pa.total_games >= 10  -- Minimum gamesavg_time_dead for reliable data
        GROUP BY 
            pa.game_name, pa.tagline, pa.total_games, pa.win_rate,
            pa.avg_kda, pa.avg_cs_per_min, pa.avg_gpm, pa.avg_dpm,
            pa.avg_vision_score, pa.avg_kill_participation, pa.avg_early_gold_adv,
            pa.avg_cs_at_10, pa.avg_team_damage_pct, pa.avg_objective_damage,
            pa.death_consistency, pa.cs_consistency
        """
        
        execution_id = self.run_athena_query(query)
        df = self.get_query_results(execution_id)
        
        # Fill NaN values
        id_cols = ['game_name', 'tagline']
        numeric_cols = [col for col in df.columns if col not in id_cols]
        
        # Fill NaNs in numeric columns with 0
        df[numeric_cols] = df[numeric_cols].fillna(0)
        
        # Fill NaNs in ID columns with an empty string
        df[id_cols] = df[id_cols].fillna('')
        
        print(f"\nDataset summary:")
        print(f"  Players: {len(df):,}")
        print(f"  Features: {len(df.columns)}")
        print(f"  Avg games per player: {df['total_games'].mean():.1f}")
        print(f"  Win rate range: {df['win_rate'].min():.1%} - {df['win_rate'].max():.1%}")
        
        return df
    
    def prepare_hypothetical_simulator_data(self) -> pd.DataFrame:
        """
        Prepares data for hypothetical simulator (outcome prediction)
        
        Extracts teamfight sequences from timeline data
        This is more complex - requires timeline processing
        """
        print("\n" + "="*60)
        print("PREPARING HYPOTHETICAL SIMULATOR TRAINING DATA")
        print("="*60)
        
        query = """
        WITH team_stats AS (
            SELECT 
                match_id,
                team_id,
                AVG(champ_level) as avg_level,
                SUM(gold_earned) as total_gold,
                AVG(damage_to_champions) as avg_damage,
                COUNT(*) as player_count,
                MAX(win) as won
            FROM lol_coach_db.match_features_27506b28219d8344deb963a9a729bcfb
            GROUP BY match_id, team_id
        ),
        match_states AS (
            SELECT 
                t1.match_id,
                t1.total_gold as blue_gold,
                t2.total_gold as red_gold,
                (t1.total_gold - t2.total_gold) as gold_diff,
                t1.avg_level as blue_level,
                t2.avg_level as red_level,
                (t1.avg_level - t2.avg_level) as level_diff,
                t1.avg_damage as blue_damage,
                t2.avg_damage as red_damage,
                t1.won as blue_won
            FROM team_stats t1
            JOIN team_stats t2 
                ON t1.match_id = t2.match_id 
                AND t1.team_id = 100 
                AND t2.team_id = 200
        )
        SELECT * FROM match_states
        WHERE gold_diff IS NOT NULL
        """
        
        execution_id = self.run_athena_query(query)
        df = self.get_query_results(execution_id)
        
        print(f"\nDataset summary:")
        print(f"  Match states: {len(df):,}")
        print(f"  Blue team win rate: {df['blue_won'].mean():.1%}")
        
        return df
    
    def save_to_s3(self, data, filename: str, format: str = 'parquet'):
        """
        Saves DataFrame or dict to S3 in specified format
        """
        local_path = f"/tmp/{filename}"
        s3_key = f"training/{filename}"
        
        if format == 'parquet':
            data.to_parquet(local_path, index=False, compression='snappy')
        elif format == 'csv':
            data.to_csv(local_path, index=False)
        elif format == 'json':
            with open(local_path, 'w') as f:
                json.dump(data, f, indent=4)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        print(f"\nUploading to s3://{self.s3_output_bucket}/{s3_key}...")
        self.s3_client.upload_file(local_path, self.s3_output_bucket, s3_key)
        
        s3_path = f"s3://{self.s3_output_bucket}/{s3_key}"
        print(f"Saved to {s3_path}")
        
        return s3_path
    
    def create_validation_split(self, df: pd.DataFrame, test_size: float = 0.2):
        """
        Splits data into train/validation sets
        """
        from sklearn.model_selection import train_test_split
        
        # Shuffle and split
        train_df, val_df = train_test_split(
            df, 
            test_size=test_size, 
            random_state=42,
            shuffle=True
        )
        
        print(f"\nSplit summary:")
        print(f"  Training set: {len(train_df):,} samples")
        print(f"  Validation set: {len(val_df):,} samples")
        
        return train_df, val_df
    
    def prepare_all_training_data(self):
        """
        Main function to prepare all training datasets
        """
        print("\nStarting training data preparation...")
        print(f"Database: {self.database}")
        print(f"Output bucket: {self.s3_output_bucket}")
        
        results = {}
        
        # 1. Prepare playstyle profiler data
        try:
            profiler_df = self.prepare_playstyle_profiler_data()
            
            # Split into train/val
            train_df, val_df = self.create_validation_split(profiler_df, test_size=0.2)
            
            # Save to S3
            train_path = self.save_to_s3(train_df, 'player_features_train.parquet')
            val_path = self.save_to_s3(val_df, 'player_features_val.parquet')
            
            results['playstyle_profiler'] = {
                'train_path': train_path,
                'val_path': val_path,
                'train_samples': len(train_df),
                'val_samples': len(val_df),
                'features': list(train_df.columns)
            }
            
        except Exception as e:
            print(f"Error preparing playstyle profiler data: {e}")
            results['playstyle_profiler'] = {'error': str(e)}
        
        # 2. Prepare hypothetical simulator data
        try:
            simulator_df = self.prepare_hypothetical_simulator_data()
            
            # Split into train/val
            train_df, val_df = self.create_validation_split(simulator_df, test_size=0.2)
            
            # Save to S3
            train_path = self.save_to_s3(train_df, 'teamfight_data_train.parquet')
            val_path = self.save_to_s3(val_df, 'teamfight_data_val.parquet')
            
            results['hypothetical_simulator'] = {
                'train_path': train_path,
                'val_path': val_path,
                'train_samples': len(train_df),
                'val_samples': len(val_df),
                'features': list(train_df.columns)
            }
            
        except Exception as e:
            print(f"Error preparing simulator data: {e}")
            results['hypothetical_simulator'] = {'error': str(e)}
        
        # Save metadata
        metadata_path = self.save_to_s3(
            results,  
            'training_metadata.json',
            format='json'
        )
        
        print("\n" + "="*60)
        print("TRAINING DATA PREPARATION COMPLETE")
        print("="*60)
        
        for model, info in results.items():
            print(f"\n{model}:")
            if 'error' in info:
                print(f"  {info['error']}")
            else:
                print(f"  Train: {info['train_path']}")
                print(f"  Val: {info['val_path']}")
                print(f"  Samples: {info['train_samples']:,} train, {info['val_samples']:,} val")
        
        return results

# CLI Interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Prepare training data from Athena for SageMaker'
    )
    parser.add_argument(
        '--database',
        default='lol_coach_db',
        help='Athena database name'
    )
    parser.add_argument(
        '--output-bucket',
        required=True,
        help='S3 bucket for training data output'
    )
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region'
    )
    parser.add_argument(
        '--model',
        choices=['profiler', 'simulator', 'all'],
        default='all',
        help='Which model to prepare data for'
    )
    
    args = parser.parse_args()
    
    # Initialize
    prep = TrainingDataPreparation(
        database=args.database,
        s3_output_bucket=args.output_bucket,
        region=args.region
    )
    
    # Prepare data
    if args.model == 'all':
        results = prep.prepare_all_training_data()
    elif args.model == 'profiler':
        df = prep.prepare_playstyle_profiler_data()
        train_df, val_df = prep.create_validation_split(df)
        prep.save_to_s3(train_df, 'player_features_train.parquet')
        prep.save_to_s3(val_df, 'player_features_val.parquet')
    elif args.model == 'simulator':
        df = prep.prepare_hypothetical_simulator_data()
        train_df, val_df = prep.create_validation_split(df)
        prep.save_to_s3(train_df, 'teamfight_data_train.parquet')
        prep.save_to_s3(val_df, 'teamfight_data_val.parquet')
    
    print("\nDone! Training data is ready for SageMaker.")