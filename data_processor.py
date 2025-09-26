import riot_api_request


def extract_stats(match_data, puuid):
    metadata = match_data['metadata']
    info = match_data['info']
    players = info['participants']
    participants = metadata['participants']
    teams = info['teams']

    match_id = metadata["matchId"]
    playerdata = players[participants.index(puuid)]
    for team in teams:
        if team['teamId'] == playerdata['teamId']:
            objs = team['objectives']
            baron = objs['baron']
            dragon = objs['dragon']
            grubs = objs['horde']
            rift_herald = objs['riftHerald']
            tower= objs['tower']
            inhibitor = objs['inhibitor']
    

    return 0

def extract_stats_at_time(match_data, puuid, stat, time):
    return 0

def extract_games(match_list, puuid):
    return 0
