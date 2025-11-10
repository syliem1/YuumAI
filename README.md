# YuumAI: Rift Rewind 2025

## Introduction
For our project, we wanted to create a project that went beyond the standard statistic measurement tools and provide in-depth insights backed with comprehensive metrics. The core theme that we wanted to avoid was a generic "Spotify Wrapped" application that just plainly summarized a culmination of numbers on an uninteractive slideshow. We aimed to create an application that was **interactive, unique, and personalized.** After brainstorming through a series of alternatives that included:

1. A Chess.com blitz-like puzzle game (too technical!).
2. A quizzer that allowed players to guess their past team compositions' win conditions and playstyles (not that fun!).
3. A hypothetical team fight simulator that allowed players to query "what would have happened if..." decisions (not enough information!).

In the end, with the current information available to us through the Riot Games API along with the sophisticated backend AWS tools, we decided on a project themed around Yuumi and her book, nicknamed **YuumAI**. 

## Features
There are four main features that we included in our project, each a different aspect of what the magical book tells the player they input their information. This consists of a summary, social, match history and questions tab. 

### Summary
Within the summary is a brief description of what **region archetype** the user received when the magic book analyzes their match history. The archetype is chosen typically by weighing specific stats found in those respective games against other stats. For example, if the player provided around 20 games where they were super aggressive and constantly looking for fights early game, they would most likely be given the Noxian archetype. These archetypes are meant to represent the playstyles of players while also tying back to the lore of League. It also gives users a way to build a connection by seeing if they received their favorite region. Underneath the archetype box we can find the **profile** section. This section is meant to give more interesting descriptors to the user's playstyle. These extra descriptions are chosen based on what archetype the user recieves. **Key statistics** can be found underneath the profile section; the key statistics section provides the average winrate, KDA, CS per minute, and gold earned per minute. These statistics are all based on the selected number of matches chosen from the player in order to give a rough estimate of what the player's playstyle looks like. This section also features a list of the top 3 most picked champions within the match pool. This also gives insight to what characters the user may excel with. On the right side of the book lies the **Overall performance percentile**, which returns a precentage based on the key metrics from a short list of important stats. Right below it is the list of **strengths & weaknesses**; it filters through a list of stats and sorts positive stats into strengths and negative ones into weakenessses. 

### Social
On the social section, a list of the user's important stats is shown on one side, with the option to search for another player on the other side. After a request is made to our API, the user is shown a one to one comparison for each important stat against their chosen other player. These stats include KDA, CS per minute, Kill Participation, Damage per minute, Gold per minute, Solo Kills, Vision Score, and Crowd Control time. This page is intended to provide players with insight on how they stack up against their peers at a glance. 

### Match History
In the match history section, the book shows the user a list of their recent games, each with up to 15 **Impactful Events**. These events are displayed in a vertical list ordered by their estimated impact whenever the user selects a specific match. Events can be either objectives or teamfights, with objectives having subcategories such as dragon, tower, inhibitor, etc. Each event in the list includes a title for the event, its estimated impact, timestamp rounded to the full minute, and if it's an objective, which team took said objective. The user can select each event on the timeline, which expands additional details about the event, including general location, the player's distance to the event, and the gold difference between the player's team and their opponent. The expanded event also includes an AI generated description of the event and feedback for the player based on the result of said event. For example, if the player was far away in an important teamfight, the feedback for that event might encourage the player to group with their team more. This section is designed to provide personalized feedback to players based on their actual match history. Players can look back on their games and get feedback on their decision making and macro play.

### Questions
In our questions section, the book provides the user a place to inquire about their profile and what the book has generated about the user. This allows the user to delve deeper into the naunces of why they were assigned their traits and regions. Further, the book also allows the user to ask more open-ended questions, even outside their own dataset & history. 

## Methodology

### Establishing a Dataset

Collecting relevant match information proved to be one of the hardest parts as it was many of our first time dealing with AWS. We developed **Lambda** functions to continuously pull from the Riot Games API in the following steps:

1. Feed a Lambda function a single PUUID of a player.
2. Retrieve all played **RANKED SOLO/DUO** game ```matchIds``` of that player up to a year ago.
3. For each of those matches, add the other 9 players into an AWS **Simple Queue Service** to be processed later.
4. Add the processed player to a "already-processed" **DynamoDB** to avoid repeats.
5. Download both the ```MatchDto.json``` ("```match-data.json```" later in our write-up) and the ```TimelineDto.json``` ("```timeline-data.json```") into an **S3** bucket from the ```/lol/match/v5/matches/{matchId}``` and ```/lol/match/v5/matches/{matchId}/timeline``` endpoints respectively.
6. Pop a player from the **SQS** queue and repeat from step 2. 

By running four concurrent Lambda functions all cross-checking from the same DynamoDB "processed" table, we were able to get around the Riot Games API rate limits to achieve 4x the amount of games within the same amount of time. The hardest part was reminding each member in the group to update their API keys on the daily. After about two weeks of processing, we collected approximately ***150,000 ranked matches*** (~110.4 GB), though we aimed for 1 million.

A noteworthy point is why we decided to use only **ranked solo/duo** matches. We believed that the quality of matches in these games would be far less likely to contain gameplay anomalies that might skew metrics. We believed that players in these games were far more likely to be trying their best to achieve victory and, thus, made perfect candidates for learned coaching patterns. 

### Packaging the Data

A dataset of 150,000 matches all in highly nested ```.json``` format proved to be a formidable challenge for an AI to crawl through. We created a **Glue ETL job** to sift through the ```match-data.json``` files to collect important endgame information about players, including total CS killed, kill participation, vision score, and other stats that contributed to either a win or loss. The Glue job allowed us to flatten out the ```.json``` files to produce ```.parquet``` files that could be easily read by any future machine learning models.

Here, we encounted an expensive lesson in data analysis. At first, we created a separate ```.parquet``` file partitioned on a player's ```game-name``` and their ```tagline``` so that querying would be fast. However, what we did not realize was that, if we ever wanted to query through all those ```.parquet``` files to calculate, say the average KDA, each one would incur a S3 LIST request. We sent over 100,000,000 requests testing out our model and racked up a bill of over $300. After that, we stuck at a maximum of 5 ```.parquet``` files.

### Creating Aggregates

Now that we had a good sample that we thought represented the League of Legends community well, we shifted our sights to develop a playstyle classifier. We settled on a kNN classifier with 13 hyperparameter clusters defined by the 13 unique regions in the League of Legends universe. For every player in our training set, we established 23 features as shown by the block below.

```python=
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
```
<!-- ![image](https://hackmd.io/_uploads/rJyjnckgbe.png) -->

Inside a **Sagemaker** workspace, we associated specific features to certain regions. This meant players that had high objective damage combined with a good average of monsters killed per game were ranked highly in Ixtal, while aggressive, daring players that had excellent kill participant along with high average damage placed in the Noxus classification. 
```python=
features["bandle"] = (
    features["avg_outnumbered_kills"] * 0.4 + features["avg_kda"] * 0.3 + (features["avg_vision_score"] / 40.0) * 0.3
)
features["bilgewater"] = (
    (features["avg_gpm"] / 400) * 0.4 + features["avg_solo_kills"] * 0.3 + features["avg_kills_near_tower"] * 0.3
)
features["demacia"] = (
    features["avg_kill_participation"] * 0.4 + features["avg_team_damage_pct"] * 0.3 + (features["avg_shields_on_teammates"] / 500) * 0.3
)
features["ionia"] = (
    (features["avg_kda"] / 4) * 0.3 + ((features["avg_kill_participation"] * features["avg_cs_per_min"]) / 7) * 0.4 + (features["avg_vision_score"] / 40) * 0.3
)
features["ixtal"] = (
    (features["avg_objective_damage"] / 10000) * 0.4 + features["avg_dragon_takedowns"] * 0.3 + features["avg_herald_takedowns"] * 0.3
)
features["noxus"] = (
    (features["avg_dpm"] / 600) * 0.4 + (features["avg_early_gold_adv"] / 500) * 0.3 + features["avg_turret_kills"] * 0.3
)
features["piltover"] = (
    (features["avg_gpm"] / 400) * 0.4 + (features["avg_cs_per_min"] / 7) * 0.3 + features["cs_consistency"] * 0.3
)
features["shadow_isles"] = (
    (features["avg_heals_on_teammates"] / 1000) * 0.4 + (features["avg_longest_alive"] / 600) * 0.3 + features["avg_kda"] * 0.3
)
features["shurima"] = (
    (features["avg_cs_per_min"] / 7) * 0.5 + features["avg_gpm"] * 0.5
)
features["targon"] = (
    (features["avg_vision_score"] / 40) * 0.4 + (features["avg_shields_on_teammates"] / 500) * 0.3 + (features["avg_heals_on_teammates"] / 1000) * 0.3
)
features["freljord"] = (
    (features["avg_cc_time"] / 20) * 0.4 + (features["avg_time_dead"] / 60) * -0.3 + (1 / (features["death_consistency"] + 0.1)) * 0.3
)
features["void"] = (
    (features["avg_dpm"] / 600) * 0.4 + features["avg_team_damage_pct"] * 0.4 + features["avg_solo_kills"] * 0.2
)
features["zaun"] = (
    (1 / (features["death_consistency"] + 0.1)) * -0.3 + features["avg_outnumbered_kills"] * 0.4 +features["avg_pick_kills"] * 0.3
)
```

<!-- ![image](https://hackmd.io/_uploads/rJUH0ckxZx.png) -->

A list of features that influenced region selection is shown above. The weights on each of those features was chosen accordingly so that a rough amount of players belonged to each region, but to create an equal distribution was difficult, time-consuming, and expensive. We saw a silhouette score of 0.1278 after all 13-NN classification was completed, which we deemed sufficient: 

| Region | Number of Players | Win Rate |
| -------- | -------- | -------- |
| Bandle City     | 1452     | 58.66%     |
| Demacia     | 792     | 49.01%     |
| Zaun     | 1844     | 41.69%     |
| The Freljord     | 1558     | 51.87%     |
| Shurima     | 1208     | 47.73%     |
| Piltover     | 2278     | 50.51%     |
| Noxus     | 2313     | 47.85%     |
| Targon     | 431     | 54.82%     |
| Shadow Isles     | 796     | 56.72%     |
| The Void     | 2961     | 49.77%     |
| Ixtal     | 1008     | 57.19%     |
| Ionia     | 1330     | 47.22%     |
| Bilgewater     | 865     | 58.68%     |

The saved model that was produced a result of this 13-NN clustering was saved and a 1-NN classifier would later be used to group new players into their corresponding region.

Additionally, this step generated global averages for KDA, CS per minute, kill participation, etc. that we used for our player percentile metrics. 

### Batch Processing for OpenSearch

The next step would be transform our ```timeline-data.json```. This step was completed near the end of the submission since our AI open-ended questionnaire part was developed at the end. We wanted to implement Retrieval-Augmented Generation (RAG) to ground our model in a knowledge base. We were content to have our 150,000 matches serve as the ground truth for our model, but given the time constraints, we were only able to index 2,000 matches. Unfortunately, this time around, we were not able to utilize four API keys since our region quota for the embedding model used, **AWS Bedrock Titan Embeddings V2**, was account-wide. From each ```timeline-data.json``` file, we were able to produce a 1024-dimensional vector to serve as a RAG database for open-ended questions. Processing was done on an EC2 t2-nano instance to preserve the small remaining budget we had. 

### Pinpointing Critical Events

To create a comprehensive view of how a player performed in their recent games, we decided to extract out "game-changing" events that turned the tide of a game. We based the structure off of what op.gg uses, but with a deep dive of each match itself. Complete with an AI summary of each event, we calculated "impact scores" of every event frame found in the ```timeline-data.json``` file. Working with the structure of the ```timeline-data.json``` files, we grouped each event into one of four categories: 
1. **Objectives**: Elite monster kills that provided crucial, permanent buffs to the team that slayed them. Monsters included dragons, rift herald, the baron, and void grubs. 
2. **Structures**: Destruction of turrets or inhibitors that allowed greater map control and extend the presence of a team's advantage into corners of the map. 
3. **Teamfights**: Moments categorized by three or more players and kills in a set amount of time. The function outputs a "WIN" if the number of friendly kills outnumbers the number of enemy kills, otherwise show a "LOSE."
4. **Kills**: High impact kills that contributed to swinging the team's gold in the allied team's favor. Rarely appears in the top 15 most impactful events unless a bounty is claimed.

*Impact score* is calculated using a wide diversity of factors. With some of the weights shown below:

1. **Objectives**: Increasing weights for void grubs, rift herald, dragons, and barons, respectively. 
2. **Structure**: Varied weights for tower plating, outer turrets, and inner towers. Nexus towers counted as the highest impact with inhibitors being the next. Rationale is that the destruction of these structures creates drastic pressure on the enemy.
3. **Teamfights**: Base amount of score given for the first kill and increasingly higher score for each kill from there on.
4. **Kills**: Assisting members count for more impact since more gold distributed. Shutdowns counted extremely high. Player-involved kills weighted higher to provide a learning opportunity. 

In hindsight, we believe that this part could use way more fine-tuning for the weights. We noticed that, with our current parameters, structures were skewed to be shown, while solo kills were less prominent, despite there being a greater opportunity to learn macro gameplay from those moments. 

Finally, each event is paired with an AI-generated summary that takes into account where the player was at that time frame, whether their summoner spells were available, and a Euclidean distance to the objective. These statistics are fed into the AI to provide a rich, holistic summary of the event to remind players what happened, along with learned takeaways. For example, events where players were "close" or had teleport available are *typically* marked by the AI with "you should have participated," or if the player was too far, the AI responded with "keep pushing." Here, we aimed to create a 2-in-1 feature: allow players to reflect and learn from recent events in their past games. 

## Workflow

### Overview
1. Frontend receives in a ```game_name```, ```tagline```, ```num_games``` and sends the information to our backend endpoint ```POST /player/process```. 
2. ```POST``` asychronously downloads the ```num_games``` most recent matches into an S3 bucket for later analysis and to feed into a growing comparison database.
3. Once inside the S3 bucket, immediately parse ```match-data.json``` files to calculate aggregates like ```avg_kda```, ```avg_cs_per_min```, top 3 most played champions, etc.
4. Classify playstyle by calling a Sagemaker endpoint that holds the 1-NN classifier using calculated aggregates.
5. At the same time of the classification, a call to AWS OpenSearch to embed all of the player's games into vectors is performed. 
6. ```timeline-data.json``` files in the S3 buckets are extracted to get critical, game-changing events. Impact score is calculated and the top 15 most impactful events are saved in a DynamoDB database for rapid querying.

### Open-Ended Questioning

For our conversational AI, we decided on Amazon Nova Pro for its cheap, intelligent responses. Nova Pro's pricing is $0.0008/1000 input tokens and $0.0032/1000 output tokens. Originally we wanted to use Anthropic's Claude 3.5 Haiku because it provided excellent responses in a testing sandbox environment on League of Legends queries, however, recent changes in AWS Bedrock policies required us to submit a usage request to access any of Anthropic's models. 

Next we decided on OpenAI's recently introduced gpt-oss-20b model with its *incredibly cheap* $0.00007/1000 input tokens and $0.0003/1000 output tokens pricing. While the model provided sufficiently-advanced responses, we encountered a problem where the model constantly provided a "<reasoning>" output that rapidly drained the allocated output tokens per query. No amount of prompt engineering would remove the "<reasoning>" response, so we decided to forgo it.

Finally, we looked into developing a fine-tuned, custom model tailored with League of Legends terminology and background knowledge. AWS Bedrock requires all fine-tuned models to purchase Provisioned Throughput, meaning we would pay a one-time fee for a set quantity of time per hour, even when the model was not working or idle. The cheapest model would cost $15,000/month which we deemed absurd for a hackathon. 

Overall:
- **Amazon Nova Pro**: ~$0.00097/question with maximum 400 input tokens, maximum 300 output tokens.
-  **Claude 3.5**: Good reasoning model, but locked behind a service quota request form.
-  **gpt-oss-20b**: Cheap, decently logical model, but mandatory "<reasoning>" output.
-  **Custom-Tuned**: Incredibly expensive. 

For RAG, we stuck with AWS's native **Bedrock Titan Embeddings v2**. We generate 1024-dimensional vector embeddings for each of the 150,000 games stored in our database. After converting the user's question into an embedding, we perform a semantic search for similar scenarios (we chose 10-NN) in our 150,000 match database using AWS OpenSearch as the serverless service. 

### Prompt Engineering

Tuning the prompts to output a reasonable response turned out to be relatively difficult despite the lack of coding necessary to complete this task. We settled on a strict set of rules based on what we noticed:

1. Reference stats SPARINGLY and try to reference concepts (e.g., "high death volatility").
2. Keep under 380 words. Avoid fluff. No generic motivational lines.
3. If the user question is unrelated (e.g., math), briefly answer then still deliver coaching.
4. Focus highly on the user question.
5. Can refer to the player's top champions for response.

Since our prompt has fed in calculated player metrics (see below), we found that the AI was prone to outputting a wall of stats that were irrelevant to the situation and question asked. While we did want the model to refer to the data to provide personalized advice, it was heavily biased towards that route. We include the following aggregates to produce a response that was well-balanced between general, fact-based, and personalized:

- KDA
- CS/min
- Average deaths/game
- Kill participation
- Vision score
- Win rate
- Recent champions played
- Laning efficiency (CS + KDA + win rate)
- Objective efficiency (objective damage + dragon kills + herald kills)
- Map influence (kill participation, vision score, deaths)
- Risk management (deaths, KDA, vision score)
- Tempo conversion (early gold advantage at 10, win rate, KDA)
- CS strength flag
    - "inefficient": cs < 6.2/min
    - "stable": 6.2/min <= cs < 7.2/min 
    - "strong": 7.2/min <= cs
- Death tendancy flag
    - "high": avg 5/game <= deaths
    - "moderate": avg 3.5/game <= deaths
    - "controlled": deaths < 3.5/game
- Vision flag
    - "needs improvement": vision <  avg 15/game
    - "acceptable": avg 15/game <= vision < avg 22/game
    - "impactful": avg 22/game <= vision

## Takeaways

Rift Rewind 2025 presented a wonderful opportunity for our team to collaborate and work on innovative solutions in a fantastically structured environment. We would like to give a huge shout out to Riot Games for sponsoring this event and providing us with an understandable API pipeline outfitted with a great selection of data. Also thank you for Amazon Web Services for providing us with $400 in AWS credits to experiment, develop, and push to production with. Some lessons learned:

1. **AI models are not built equally!** Next time, we needed a quantitive measurement method to rate the responses of AI models and their costs. While fine-tuning a model would be ideal for a video game coach like this, we needed a comprehensive test suite to study the responses of different AI models under similar conditions. 
2. **Develop a basic plan at the very beginning!** Thankfully, the project's $400 worth of credits gave us plenty of leeway, but such a complicated ETL pipeline like ours would take days and perhaps weeks to remake a missing index for example. The reason we had so little vector embeddings from our original set of 150,000 matches is because we forgot to set up the kNN setting at the beginning of the OpenSearch's index creation. 
3. **Experiment with weights!** We ball-parked a lot of the weights and biases used to establish our 13-NN classifier as well as to calculate the impact score of the differents within our timeline. League of Legends is a complex environment where hard-coded values like +150 impact score for each kill is not completely representative of the state of the game; having an exponentially increasing impact score per kill in a teamfight would make a lot more sense. 

## Future Work
1. Modify our weight and biases system for both the region 13-NN classifier and critical event impact score rating.
2. Add more features that represents each region to increase the silhouette score.
3. Implement caching through DynamoDB for frequent questions to improve the response times of our AI.
4. Completely convert our 150,000 games into vector embeddings for a more accurate semantic search.
5. Develop a concurrency feature to implement batch processing of a player's matches to get them into our S3 bucket faster to start parsing immediately.

