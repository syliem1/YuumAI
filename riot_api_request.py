from dotenv import load_dotenv
import requests
import os
import json

load_dotenv()
API_KEY = os.getenv('RIOT_API_KEY')
      
def make_requests(url):
     headers = {
         "X-Riot-Token" : API_KEY
     }
     return requests.get(url, headers=headers).json()

def get_puuid_by_id(game_name, tag_line):
     return make_requests(f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}")

def get_match_history(puuid, start, count):
     return make_requests(f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}")

def get_match_data(match_id):
     return make_requests(f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}")

def get_match_timeline(match_id):
     return make_requests(f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline")

if __name__ == "__main__":
    player_account = get_puuid_by_id("cheesmuncher", "moggd")
    puuid = player_account.get("puuid")
    match_ids = get_match_history(puuid, 0, 20)
    match_list = []
    for i in range(len(match_ids)):
       match_list.append(get_match_data(match_ids[i]))
