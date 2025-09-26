import riot_api_request as riotreq
import pandas


def extract_stats(match_data, puuid):
    metadata = match_data['metadata']
    info = match_data['info']
    players = info['participants']
    participants = metadata['participants']
    teams = info['teams']
    game_creation = info['gameCreation']
    game_duration = info['gameDuration']

    match_id = metadata["matchId"]
    playerdata = players[participants.index(puuid)]
    assists = playerdata['assists']
    champ_level = playerdata['champLevel']
    champ_id = playerdata['championId']
    champ_name = playerdata['championName']
    champ_transform = playerdata['championTransform'] #for kayn
    deaths = playerdata['deaths']
    early_surrender = playerdata['gameEndedInEarlySurrender']
    gold_earned = playerdata['goldEarned']
    gold_spent = playerdata['goldSpent']
    item0 = playerdata['item0']
    item1 = playerdata['item1']
    item2 = playerdata['item2']
    item3 = playerdata['item3']
    item4 = playerdata['item4']
    item5 = playerdata['item5']
    item6 = playerdata['item6']
    itemsPurchased = playerdata['itemsPurchased']
    kills = playerdata['kills']
    lane = playerdata['lane']
    neutral_minions_killed = playerdata['neutralMinionsKilled']
    participant_id = playerdata['participantId']
    riot_id_game_name = playerdata['riotIdGameName']
    riot_id_tagline = playerdata['riotIdTagline']
    summoner1_id = playerdata['summoner1Id']
    summoner2_id = playerdata['summoner2Id']
    team_id = playerdata['teamId']
    team_position = playerdata['teamPosition']
    total_damage_dealt = playerdata['totalDamageDealt']
    total_minions_killed = playerdata['totalMinionsKilled']
    vision_score = playerdata['visionScore']
    win = playerdata['win']

    for team in teams:
        if team['teamId'] == playerdata['teamId']:
            objs = team['objectives']
            baron = objs['baron']
            dragon = objs['dragon']
            grubs = objs['horde']
            rift_herald = objs['riftHerald']
            tower= objs['tower']
            inhibitor = objs['inhibitor']
    
    dataframe = pandas.DataFrame({
        'match_id': [match_id],
        'participants': [participants],
        'game_creation': [game_creation],
        'game_duration':[game_duration],
        'match_id':[match_id],
        'early_surrender':[early_surrender],
        'puuid':[puuid],
        'participant_id': [participant_id],
        'riot_name': [riot_id_game_name],
        'riot_tagline':[riot_id_tagline],
        'win': [win],
        'team_id': [team_id],
        'team_position': [team_position],
        'champ_id': [champ_id],
        'champ_name': [champ_name],
        'champ_level': [champ_level],
        'champ_transform': [champ_transform],
        'lane': [lane],
        'kills': [kills],
        'deaths': [deaths],
        'assists': [assists],
        'gold_earned': [gold_earned],
        'gold_spent': [gold_spent],
        'total_damage_dealt': [total_damage_dealt],
        'vision_score': [vision_score],
        'neutral_minions_killed': [neutral_minions_killed],
        'total_minions_killed': [total_minions_killed],
        'summoner1': [summoner1_id],
        'summoner2': [summoner2_id],
        'item0': [item0],
        'item1': [item1],
        'item2': [item2],
        'item3': [item3],
        'item4': [item4],
        'item5': [item5],
        'item6': [item6],
        'items_purchased': [itemsPurchased]
    })
    return dataframe

def extract_stats_at_time(match_data, puuid, stat, time):
    return 0

def extract_games(match_list, puuid):
    return 0

if __name__ == "__main__":
    player_account = riotreq.get_puuid_by_id("cheesmuncher", "moggd")
    puuid = player_account.get("puuid")
    match_ids = riotreq.get_match_history(puuid, 0, 1)
    match_data = riotreq.get_match_data(match_ids[0])
    dataframe = extract_stats(match_data, puuid)
    print(dataframe)