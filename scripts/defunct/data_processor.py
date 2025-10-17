import scripts.defunct.riot_api_request as riotreq
import pandas
import json


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
    metadata = match_data['metadata']
    info = match_data['info']
    players = info['participants']
    participants = metadata['participants']
    match_id = metadata['matchId']
    frame_interval = info['frameInterval']
    frames = info['frames']
    for fr in frames:
        if fr['timestamp'] == time:
            frame = fr
    timestamp = frame['timestamp']
    participantFrames = frame['participantFrames']
    playerFrame = participantFrames[str(participants.index(puuid) + 1)] #for some reason the names for each participant are only numbered 1-9, no 0, which is kinda odd bc there are 10 players
    try:
        playerStat = playerFrame[str(stat)]
    except:
        try:
            playerStat=playerFrame['championStats'][str(stat)]
        except:
            try: 
                playerStat = playerFrame['position'][str(stat)]
            except:
                try:
                    playerStat = playerFrame['damageStats'][str(stat)]
                except:
                    return "error"
    return playerStat

def extract_games(match_list, puuid):
    multi_match_dataframe = pandas.DataFrame()
    for match in match_list:
        match_dataframe = extract_stats(match, puuid)
        multi_match_dataframe = pandas.concat([multi_match_dataframe, match_dataframe])
    avg_duration = multi_match_dataframe['game_duration'].mean()
    wins = 0
    for match in multi_match_dataframe['win']:
        if match:
            wins += 1
    winrate = wins / len(match_list)
    champs = []
    for champ in multi_match_dataframe['champ_name']:
        champs.append(champ)
    avg_champ_level = multi_match_dataframe['champ_level'].mean()
    avg_kills = multi_match_dataframe['kills'].mean()
    avg_assists = multi_match_dataframe['assists'].mean()
    avg_deaths = multi_match_dataframe['deaths'].mean()
    avg_gold_earned = multi_match_dataframe['gold_earned'].mean()
    avg_vision_score = multi_match_dataframe['vision_score'].mean()
    avg_minions_killed = multi_match_dataframe['total_minions_killed'].mean()
    summary_dataframe = pandas.DataFrame({
        'avg_duration': [avg_duration],
        'winrate': [winrate],
        'champions_played': [champs],
        'avg_champ_level': [avg_champ_level],
        'avg_kills': [avg_kills],
        'avg_assits': [avg_assists],
        'avg_deaths': [avg_deaths],
        'avg_gold_earned': [avg_gold_earned],
        'avg_vision_score': [avg_vision_score],
        'avg_minions_killed': [avg_minions_killed]
    })
    return summary_dataframe

if __name__ == "__main__":
    player_account = riotreq.get_puuid_by_id("Kron1s", "aster")
    puuid = player_account.get("puuid")
    match_ids = riotreq.get_match_history(puuid, 0, 10)
    match_list = []
    for i in range(len(match_ids)):
       match_list.append(riotreq.get_match_data(match_ids[i]))
    print(match_ids)
    match_data = riotreq.get_match_data(match_ids[0])
    timeline = riotreq.get_match_timeline(match_ids[1])
    dataframe = extract_stats(match_data, puuid)
    print(dataframe)
    playerstat = extract_stats_at_time(timeline, puuid, 'attackDamage', 0)
    print(playerstat)
    summary = extract_games(match_list, puuid)
    print(summary)