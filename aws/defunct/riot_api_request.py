from dotenv import load_dotenv
import requests
import os

load_dotenv()
API_KEY = os.getenv('RIOT_API_KEY')
      
def make_requests(url):
     headers = {
         "X-Riot-Token" : API_KEY
     }
     return requests.get(url, headers=headers).json()

def get_puuid_by_id(game_name, tag_line):
     try:
          res = make_requests(f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}")
     except Exception as e:
          print(f"error occured: {e}")
          res = "error:" + e
     finally:
          return res


def get_match_history(puuid, start, count):
     try:
          res = make_requests(f"https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}")
     except Exception as e:
          print(f"error occured: {e}")
          res = "error:" + e
     finally:
          return res
     

def get_match_data(match_id):
     try:
          res = make_requests(f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}")
     except Exception as e:
          print(f"error occured: {e}")
          res = "error:" + e
     finally:
          return res

def get_match_timeline(match_id):
     try:
          res = make_requests(f"https://americas.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline")
     except Exception as e:
          print(f"error occured: {e}")
          res = "error:" + e
     finally:
          return res

if __name__ == "__main__":
    player_account = get_puuid_by_id("cheesmuncher", "moggd")
    puuid = player_account.get("puuid")
    match_ids = get_match_history(puuid, 0, 20)
    match_list = []
    for i in range(len(match_ids)):
       match_list.append(get_match_data(match_ids[i]))
