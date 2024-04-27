
import json
import datetime
import os

import pandas as pd
import requests

# Obtain the api key that was passed in from the command line



# An api key is emailed to you when you sign up to a plan
# Get a free API key at https://api.the-odds-api.com/
API_KEY = "a448ed56b6713c585103d464b0cafbd9"

# Sport key
# Find sport keys from the /sports endpoint below, or from https://the-odds-api.com/sports-odds-data/sports-apis.html
# Alternatively use 'upcoming' to see the next 8 games across all sports
SPORTS = ['basketball_nba', 'baseball_mlb', 'soccer_epl',
         'soccer_spain_la_liga', 'soccer_usa_mls']
# Bookmaker regions
# uk | us | us2 | eu | au. Multiple can be specified if comma delimited.
# More info at https://the-odds-api.com/sports-odds-data/bookmaker-apis.html
REGIONS = 'us'
BOOKMAKERS = "pinnacle,draftkings,fanduel,betmgm,pointsbetus,betrivers,williamhill_us,betonlineag,wynnbet"
# Odds markets
# h2h | spreads | totals. Multiple can be specified if comma delimited
# More info at https://the-odds-api.com/sports-odds-data/betting-markets.html
# Note only featured markets (h2h, spreads, totals) are available with the odds endpoint.
MARKETS = 'h2h'

# Odds format
# decimal | american
ODDS_FORMAT = 'american'

# Date format
# iso | unix
DATE_FORMAT = 'iso'

def odds_api_call(api_key, sport, bookmakers = BOOKMAKERS, markets = MARKETS,
                  oddsFormat = ODDS_FORMAT, dateFormat = DATE_FORMAT):

  current_datetime = datetime.datetime.now()
  iso_current_datetime = current_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')


  # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
  #
  # Now get a list of live & upcoming games for the sport you want, along with odds for different bookmakers
  # This will deduct from the usage quota
  # The usage quota cost = [number of markets specified] x [number of regions specified]
  # For examples of usage quota costs, see https://the-odds-api.com/liveapi/guides/v4/#usage-quota-costs
  #
  # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

  odds_response = requests.get(f'https://api.the-odds-api.com/v4/sports/{sport}/odds', params={
      'api_key': api_key,
      'bookmakers': bookmakers,
      # 'regions': REGIONS,
      'markets': markets,
      'oddsFormat': oddsFormat,
      'dateFormat': dateFormat,
      'commenceTimeFrom': iso_current_datetime
  })

  if odds_response.status_code != 200:
      print(f'Failed to get odds: status_code {odds_response.status_code}, response body {odds_response.text}')

  else:
      odds_json = odds_response.json()
      print('Number of events:', len(odds_json))
      # Check the usage quota
      print('Remaining requests', odds_response.headers['x-requests-remaining'])
      print('Used requests', odds_response.headers['x-requests-used'])
  return odds_json

def american_to_prob(price):
  if price<0:
    risk = abs(price)
    return_num = risk + 100
  else:
    risk = 100
    return_num = risk+price
  return risk/return_num
def find_vig(prob1, prob2):
  overround = (prob1+prob2)*100
  vig = 1 - (1/overround) * 100
  return vig

def get_ev_games(odds_json):
  df = pd.json_normalize(odds_json)

  pinnacle_probs_list = []
  remove_games_list = []
  pinnacle_odds_list = []
  for i in range(len(df)):
    maker_list = df["bookmakers"].iloc[i]
    pinnacle_checker = False
    for maker in maker_list:
      if maker["key"] == "pinnacle":
        pinnacle_checker = True
        if len(maker["markets"][0]["outcomes"])==2:

          pinnacle1 = maker["markets"][0]["outcomes"][0]["price"]
          pinnacle2 = maker["markets"][0]["outcomes"][1]["price"]
          team1 = maker["markets"][0]["outcomes"][0]["name"]
          team2 = maker["markets"][0]["outcomes"][1]["name"]
          pinnacle1_prob = american_to_prob(pinnacle1)
          pinnacle2_prob = american_to_prob(pinnacle2)

          pinnacle1_prob_actual = pinnacle1_prob/(pinnacle1_prob+pinnacle2_prob)
          pinnacle2_prob_actual = pinnacle2_prob/(pinnacle1_prob+pinnacle2_prob)

          pinnacle_probs_list.append({team1:pinnacle1_prob_actual, team2:pinnacle2_prob_actual})
          pinnacle_odds_list.append({team1:pinnacle1, team2:pinnacle2})
        if len(maker["markets"][0]["outcomes"])==3:
          pinnacle1 = maker["markets"][0]["outcomes"][0]["price"]
          pinnacle2 = maker["markets"][0]["outcomes"][1]["price"]
          pinnacle3 = maker["markets"][0]["outcomes"][2]["price"]
          team1 = maker["markets"][0]["outcomes"][0]["name"]
          team2 = maker["markets"][0]["outcomes"][1]["name"]
          team3 = maker["markets"][0]["outcomes"][2]["name"]
          pinnacle1_prob = american_to_prob(pinnacle1)
          pinnacle2_prob = american_to_prob(pinnacle2)
          pinnacle3_prob = american_to_prob(pinnacle3)

          pinnacle1_prob_actual = pinnacle1_prob/(pinnacle1_prob+pinnacle2_prob+pinnacle3_prob)
          pinnacle2_prob_actual = pinnacle2_prob/(pinnacle1_prob+pinnacle2_prob+pinnacle3_prob)
          pinnacle3_prob_actual = pinnacle3_prob/(pinnacle1_prob+pinnacle2_prob+pinnacle3_prob)

          pinnacle_probs_list.append({team1:pinnacle1_prob_actual, team2:pinnacle2_prob_actual, team3:pinnacle3_prob_actual})
          pinnacle_odds_list.append({team1:pinnacle1, team2:pinnacle2, team3:pinnacle3})
    if pinnacle_checker==False:
      remove_games_list.append(i)

      # df = df.drop(df.index[i])

  subtraction = 0
  for i in remove_games_list:
    df = df.drop(df.index[i-subtraction])
    subtraction+=1
    df.reset_index()

  df["pinnacle_probs"] = pinnacle_probs_list
  df["pinnacle_odds"] = pinnacle_odds_list

  plus_ev_df = pd.DataFrame(columns=["Team Name", "Sportsbook", "Sportsbook Odds", "Pinnacle Odds", "EV"])
  for i in range(len(df)):
    maker_list = df["bookmakers"].iloc[i]
    pinnacle_dict = df["pinnacle_probs"].iloc[i]
    for maker in maker_list:
      if maker["key"] == "pinnacle":
        pass
        # pinnacle_odds1 = maker["markets"][0]["outcomes"][0]["price"]
        # pinnacle_odds2 = maker["markets"][0]["outcomes"][1]["price"]
      else:
        if len(maker["markets"][0]["outcomes"])==2:
          book1 = maker["markets"][0]["outcomes"][0]["price"]
          book2 = maker["markets"][0]["outcomes"][1]["price"]
          team1 = maker["markets"][0]["outcomes"][0]["name"]
          team2 = maker["markets"][0]["outcomes"][1]["name"]

          # vig = find_vig(book1_prob, book2_prob)
          team1_actual_probs = pinnacle_dict[team1]
          team2_actual_probs = pinnacle_dict[team2]

          if book1<0:
            profit1 = 100
            loss1 = abs(book1)
          else:
            profit1 = abs(book1)
            loss1 = 100

          if book2<0:
            profit2 = 100
            loss2 = abs(book2)
          else:
            profit2 = abs(book2)
            loss2 = 100
          EV1 = (team1_actual_probs*profit1) - (1-team1_actual_probs)*loss1
          EV2 = (team2_actual_probs*profit2) - (1-team2_actual_probs)*loss2
          # print(f"{maker['key']} {team1} {EV1}")
          pinnacle_odds_dict = df["pinnacle_odds"].iloc[i]
          # print(pinnacle_odds_dict)
          pinnacle_odds1 = pinnacle_odds_dict[team1]
          pinnacle_odds2 = pinnacle_odds_dict[team2]
          if EV1>0:
            new_row = {"Team Name": team1, "Sportsbook": maker['key'], "Sportsbook Odds": book1, "Pinnacle Odds": pinnacle_odds1, "EV": EV1}
            plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index = [0])], axis=0, ignore_index=True)

            # plus_ev_df.append(new_row)
          if EV2>0:
            new_row = {"Team Name": team2, "Sportsbook": maker['key'], "Sportsbook Odds": book2, "Pinnacle Odds": pinnacle_odds2, "EV": EV2}

              # plus_ev_df.append(new_row)
            plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index = [0])], axis=0, ignore_index=True)

          # print(f"{maker['key']} {team2} {EV2}")

          # print(f"{maker['key']} {team1} {book1} {team1_actual_probs} {EV1}")


        if len(maker["markets"][0]["outcomes"])==3:

          book1 = maker["markets"][0]["outcomes"][0]["price"]
          book2 = maker["markets"][0]["outcomes"][1]["price"]
          book3 = maker["markets"][0]["outcomes"][2]["price"]
          team1 = maker["markets"][0]["outcomes"][0]["name"]
          team2 = maker["markets"][0]["outcomes"][1]["name"]
          team3 = maker["markets"][0]["outcomes"][2]["name"]

          # vig = find_vig(book1_prob, book2_prob)
          team1_actual_probs = pinnacle_dict[team1]
          team2_actual_probs = pinnacle_dict[team2]
          team3_actual_probs = pinnacle_dict[team3]

          if book1<0:
            profit1 = 100
            loss1 = abs(book1)
          else:
            profit1 = abs(book1)
            loss1 = 100

          if book2<0:
            profit2 = 100
            loss2 = abs(book2)
          else:
            profit2 = abs(book2)
            loss2 = 100
          if book3<0:
            profit3 = 100
            loss3 = abs(book3)
          else:
            profit3 = abs(book3)
            loss3 = 100
          EV1 = (team1_actual_probs*profit1) - (1-team1_actual_probs)*loss1
          EV2 = (team2_actual_probs*profit2) - (1-team2_actual_probs)*loss2
          EV3 = (team3_actual_probs*profit3) - (1-team3_actual_probs)*loss3
          # print(f"{maker['key']} {team1} {EV1}")
          pinnacle_odds_dict = df["pinnacle_odds"].iloc[i]
          # print(pinnacle_odds_dict)
          pinnacle_odds1 = pinnacle_odds_dict[team1]
          pinnacle_odds2 = pinnacle_odds_dict[team2]
          pinnacle_odds3 = pinnacle_odds_dict[team3]

          if EV1>0:
            new_row = {"Team Name": team1, "Sportsbook": maker['key'], "Sportsbook Odds": book1, "Pinnacle Odds": pinnacle_odds1, "EV": EV1}
            plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index = [0])], axis=0, ignore_index=True)

            # plus_ev_df.append(new_row)
          if EV2>0:
            new_row = {"Team Name": team2, "Sportsbook": maker['key'], "Sportsbook Odds": book2, "Pinnacle Odds": pinnacle_odds2, "EV": EV2}
          if EV3>0:
            new_row = {"Team Name": team1+" v "+ team2+" " + team3, "Sportsbook": maker['key'], "Sportsbook Odds": book3, "Pinnacle Odds": pinnacle_odds3, "EV": EV3}
              # plus_ev_df.append(new_row)
            plus_ev_df = pd.concat([plus_ev_df, pd.DataFrame(new_row, index = [0])], axis=0, ignore_index=True)

  plus_ev_df = plus_ev_df.sort_values(by=['EV'], ascending=False)
  return plus_ev_df

def run(event, lambda_context):
  for sport in SPORTS:
    print(sport)
    odds_json = odds_api_call(api_key=API_KEY, sport=sport)
    # print(get_ev_games(odds_json).to_markdown())
    discord_url = "https://discord.com/api/v9/channels/1231674320468836395/messages"
    auth = {
        'authorization': os.environ['discord_authorization']
        
    }
    message = {
        'content': get_ev_games(odds_json).to_markdown()
    }
    
    requests.post(discord_url, headers = auth, data = message)


