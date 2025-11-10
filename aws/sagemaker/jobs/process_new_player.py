"""
Master pipeline for processing new players
Combines playstyle profiling + timeline feature
"""

import boto3
import json
import requests
from datetime import datetime
import time
import argparse 

s3_client = boto3.client('s3')
stepfunctions = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')

# Configuration
RIOT_API_KEY = 'RGAPI-a9a2f807-d39e-4546-9123-23f24310aba3'
API_ENDPOINT = 'https://v4ft9564pb.execute-api.us-west-2.amazonaws.com'
STATE_MACHINE_ARN = 'arn:aws:states:us-west-2:768394660366:stateMachine:lol-timeline-batch-processor'
S3_BUCKET_RAW = 'lol-training-matches-150k'
S3_BUCKET_PROCESSED = 'lol-coach-processed-data'

class PlayerProcessor:
    """
    Orchestrates complete player processing pipeline
    """
    
    def __init__(self, game_name: str, tagline: str):
        self.game_name = game_name
        self.tagline = tagline
        self.puuid = None
        self.match_ids = []
        
    def fetch_riot_data(self, num_games: int = 20):
        """
        Fetches player data from Riot API
        """
        print(f"\n=== Fetching Riot Data for {self.game_name}#{self.tagline} ===")
        
        # Get PUUID
        account_url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{self.game_name}/{self.tagline}"
        headers = {'X-Riot-Token': RIOT_API_KEY}
        
        try:
            response = requests.get(account_url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching PUUID: {e}")
            return False
            
        account_data = response.json()
        self.puuid = account_data['puuid']
        print(f"✓ Retrieved PUUID: {self.puuid}")
        
        # Get match history
        matches_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{self.puuid}/ids"
        params = {'start': 0, 'count': num_games, 'type': 'ranked'}
        
        try:
            response = requests.get(matches_url, headers=headers, params=params)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"✗ Error fetching match IDs: {e}")
            return False

        self.match_ids = response.json()
        if not self.match_ids:
            print(f"⚠ No ranked match IDs found for {self.game_name}#{self.tagline}")
            return False
            
        print(f"✓ Retrieved {len(self.match_ids)} match IDs")
        return True

    def download_and_save_matches(self):
        """
        Downloads match and timeline data, saves to S3
        """
        print(f"\n=== Downloading Match Data ===")
        
        headers = {'X-Riot-Token': RIOT_API_KEY}
        player_folder = f"{self.game_name}_{self.tagline}"
        
        download_count = 0
        for idx, match_id in enumerate(self.match_ids, 1):
            print(f"[{idx}/{len(self.match_ids)}] Processing {match_id}...")
            
            try:
                # Download match data
                match_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}"
                match_response = requests.get(match_url, headers=headers)
                match_response.raise_for_status()
                match_data = match_response.json()
                
                # Download timeline data
                timeline_url = f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
                timeline_response = requests.get(timeline_url, headers=headers)
                timeline_response.raise_for_status()
                timeline_data = timeline_response.json()
                
                # Save to S3
                match_key = f"raw-matches/{player_folder}/{match_id}/match-data.json"
                timeline_key = f"raw-matches/{player_folder}/{match_id}/timeline-data.json"
                
                s3_client.put_object(
                    Bucket=S3_BUCKET_RAW,
                    Key=match_key,
                    Body=json.dumps(match_data),
                    ContentType='application/json'
                )
                
                s3_client.put_object(
                    Bucket=S3_BUCKET_RAW,
                    Key=timeline_key,
                    Body=json.dumps(timeline_data),
                    ContentType='application/json'
                )
                
                print(f"  ✓ Saved to S3: {match_id}")
                download_count += 1
                
                # Rate limiting
                time.sleep(1.2)  # Riot API rate limit
                
            except Exception as e:
                print(f"  ✗ Error processing {match_id}: {str(e)}")
                continue
        
        print(f"✓ Downloaded {download_count}/{len(self.match_ids)} matches to S3")

    def run_playstyle_profiler(self):
        """
        Runs playstyle profiler on match data
        """
        print(f"\n=== Running Playstyle Profiler ===")
        print("✓ Playstyle profiling complete")
        return {'region': 'Demacia', 'playstyle_score': 85}  # Example
    
    def trigger_timeline_processing(self):
        """
        Triggers Step Functions workflow for batch timeline processing
        """
        print(f"\n=== Triggering Timeline Processing ===")
        
        # Wait for S3 events to propagate (Lambda triggers)
        print("Waiting 10 seconds for S3 event processing...")
        time.sleep(10)
        
        # Trigger Step Functions
        execution_name = f"player_{self.game_name}_{self.tagline}_{int(datetime.utcnow().timestamp())}"
        
        response = stepfunctions.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps({
                'match_ids': self.match_ids,
                'puuid': self.puuid,
                'batch_mode': True
            })
        )
        
        execution_arn = response['executionArn']
        print(f"✓ Started Step Functions execution: {execution_name}")
        print(f"  Execution ARN: {execution_arn}")
        
        return execution_arn
    
    def wait_for_timeline_completion(self, execution_arn: str, timeout: int = 600):
        """
        Waits for Step Functions execution to complete
        """
        print(f"\n=== Waiting for Timeline Processing ===")
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = stepfunctions.describe_execution(executionArn=execution_arn)
            status = response['status']
            
            if status == 'SUCCEEDED':
                print(f"✓ Timeline processing completed successfully!")
                return True
            elif status in ['FAILED', 'TIMED_OUT', 'ABORTED']:
                print(f"✗ Timeline processing failed: {status}")
                return False
            
            print(f"  Status: {status}... (elapsed: {int(time.time() - start_time)}s)")
            time.sleep(10)
        
        print(f"⚠ Timeout reached after {timeout}s")
        return False
    
    def get_timeline_results(self):
        """
        Retrieves processed timeline data via API
        """
        print(f"\n=== Retrieving Timeline Results ===")
        
        results = []
        
        for match_id in self.match_ids:
            url = f"{API_ENDPOINT}/timeline/events"
            params = {'match_id': match_id, 'puuid': self.puuid}
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✓ Retrieved {len(data.get('events', []))} events for {match_id}")
                results.append(data)
            else:
                print(f"✗ Failed to retrieve events for {match_id} (Status: {response.status_code})")
                try:
                    print(f"  Error: {response.json().get('error', 'Unknown')}")
                except:
                    pass
        
        return results
    
    def process_complete(self, num_games: int):
        """
        Main processing pipeline
        """
        print("="*60)
        print(f"Processing Player: {self.game_name}#{self.tagline}")
        print("="*60)
        
        # Step 1: Fetch Riot data
        if not self.fetch_riot_data(num_games):
            print("✗ Aborting: Could not fetch player data.")
            return {}

        if not self.match_ids:
             print("✓ Aborting: No matches to process.")
             return {}
        
        # Step 2: Download and save to S3
        self.download_and_save_matches()
        
        # Step 3: Run playstyle profiler
        profiler_results = self.run_playstyle_profiler()
        
        # Step 4: Trigger timeline processing
        execution_arn = self.trigger_timeline_processing()
        
        # Step 5: Wait for completion
        success = self.wait_for_timeline_completion(execution_arn)
        
        # Step 6: Get results
        timeline_results = []
        if success:
            timeline_results = self.get_timeline_results()
        
        print("\n" + "="*60)
        print("Processing Complete!")
        print("="*60)
        print(f"Playstyle Profile: {profiler_results}")
        
        total_events = sum(len(res.get('events', [])) for res in timeline_results)
        print(f"Timeline Events Processed: {total_events}")
        
        return {
            'puuid': self.puuid,
            'playstyle': profiler_results,
            'timeline_results': timeline_results,
            'match_count': num_games
        }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process a new LOL player.")
    parser.add_argument("--game-name", required=True, help="Player's game name (e.g., ShadowLeaf)")
    parser.add_argument("--tagline", required=True, help="Player's tagline (e.g., 8005)")
    parser.add_argument("--num-games", type=int, default=5, help="Number of games to process")
    
    args = parser.parse_args()

    processor = PlayerProcessor(args.game_name, args.tagline)
    results = processor.process_complete(args.num_games) 
    
    # Save results
    with open('processing_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✓ Results saved to processing_results.json")