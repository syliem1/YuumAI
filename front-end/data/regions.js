import bilgewater_crest from "@/public/images/regions/bilgewater_crest_icon.png"
export const regions = {
    "bilgewater" : {
        icon: bilgewater_crest,
        description: (stats) => `Citizens from Bilgewater have a high affinity for gold and are prone to make risky, daring plays on their lonesome. They value efficient gold generation per minute and are more willing to take tower dives if they think it can swing the tides in their favor. Based on your stats, you make an average of ${stats.avg_gpm} gold per minute. You’ve also gotten roughly ${stats.avg_solo_kills} solo kills per game as well as an average of ${stats.avg_kills_near_tower} kills near enemy tower. These impressive stats prove that you are a bonafide Bilgerat, ready to plunder the enemy team’s economy.`,
        
    },
    "noxus": {
        description: (stats) => `Noxians are known for their bloodlust and are eager to show off their strength to any unfortunate opponents that happen to stand in their way. Not only do they live for the thrill of battle, but they also take great pleasure in asserting their dominance as quickly and brutally as possible. According to your average damage per minute, ${stats.avg_dpm}, as well as your exemplary average early gold advantage, ${stats.avg_early_gold_adv}, you are a perfect fit for the Noxian archetype.`
    },
    "bandle": {
        description: (stats) => `Everyone in Bandle City knows that the scout’s code is one of the most important rulebooks to follow for any aspiring Bandle scout. Bandle scouts are known for their vigilance and their dedication to never be detected. The average Bandle scout never backs down from a fight and always comes prepared for anything. Scouts usually have a high vision score, high KDA and can always find a way to outplay when outnumbered. Your average KDA, ${avg_kda}, and vision score, ${vs}, are exceptionally high. Your average kills when outnumbered, ${avg_outnumbered_kills}, are exceptionally high which demonstrates that you are ready to become a Bandle scout.`
    },
    "demacia": {

    },
    "ionia": {

    },
    "ixtal": {

    },
    "piltover": {
        
    },
    "shadow_isles": {
        
    },
    "shurima": {
        
    },
    "targon": {
        
    },
    "freljord": {
        
    },
    "void": {
        
    },
    "zaun": {
        
    }
}