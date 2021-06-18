import schedule
import time
import requests
import tweepy
from bs4 import BeautifulSoup
import re
from matplotlib import pyplot as plt
import matplotlib.patches as mpatches
from operator import add
import numpy as np
import facebook

CONSUMER_TOKEN = ""
CONSUMER_SECRET = ""

ACCESS_TOKEN = ""
ACCESS_TOKEN_SECRET = ""
BEARER_TOKEN = ""

fb_api = facebook.GraphAPI(access_token="")

auth = tweepy.OAuthHandler(CONSUMER_TOKEN, CONSUMER_SECRET)
auth.set_access_token(ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
api = tweepy.API(auth)

simplified_party_names = {
    "Scottish National Party": "SNP",
    "Scottish Labour": "Labour",
    "Scottish Conservative and Unionist Party": "Conservative",
    "Scottish Green Party": "Greens",
    "Scottish Liberal Democrats": "Lib Dem",
    "No Party Affiliation": "No Party"
}

plt.style.use('fivethirtyeight')


VOTES_API_URL = "https://www.parliament.scot/api/sitecore/VotesMotionsSearch/SearchVotes?Length=18"
VOTES_URL = "https://www.parliament.scot/chamber-and-committees/votes-and-motions/votes-and-motions-search/"

# given most recently published vote, returns list of new votes to be published in order.
def fetch_votes():
    file = open("prev_vote.txt", "r")
    PREV_VOTE = file.read()
    file.close()

    page = requests.get(VOTES_API_URL).text
    soup = BeautifulSoup(page, 'html.parser')

    # assumes list is not empty.
    vote_div = soup.find("div", {"id": "voteresults"})
    votes = vote_div.find_all("div", {"class": "vm-list"})

    # the most recent vote, this will replace the previous most recent vote.
    new_prev_vote = votes[0].find("p").text
    file = open("prev_vote.txt", "w")
    file.write(new_prev_vote)
    file.close()
    # this will store the IDs of votes not published yet
    new_votes = []
    for i, vote in enumerate(votes):
        vote_ID = vote.find("p").text
        vote_name = vote.find("h4").text
        print(vote_name)
        print(vote_ID)
        if vote_ID == PREV_VOTE:
            PREV_VOTE = new_prev_vote
            # we are up to date.
            break

        get_vote_data(vote_ID, vote_name)

def tweet_vote(vote_ID, vote_name, vote_status, link, vote_tallies):
    msg = "Motion {vote_ID} ({name}) has {status} in the Scottish Parliament.\n\nVotes:\nYes: {yes}\nNo: {no}\nAbstained: {abs}\nNo vote: {no_v}\n\nMore information: {link}".format(yes=vote_tallies[0],
                                                                                                                                                                                    no = vote_tallies[1],
                                                                                                                                                                                    abs = vote_tallies[2],
                                                                                                                                                                                    no_v = vote_tallies[3],
                                                                                                                                                                                    vote_ID = vote_ID,
                                                                                                                                                                                    name = vote_name,
                                                                                                                                                                                    status = vote_status,
                                                                                                                                                                                    link=link)

    api.update_with_media("figs/"+vote_ID+".png", msg)

    fb_api.put_photo(image=open("figs/"+vote_ID+".png", 'rb'),
                      parent_object=100810442202573,
                      connection_name="feed",
                      message=msg)

def get_vote_data(vote_ID, vote_name):
    # need to find: name of bill, passed or not, votes from each party (dictionary)
    # replace "."s with "-"s since that is how vote URLs work.
    # also regex to extract vote part itself
    if "Motion ref. " in vote_ID:
        vote_ID = re.search(r"(?<=Motion ref. ).*", vote_ID)
        vote_ID = vote_ID.group(0)
    url_vote_ID = vote_ID.replace(".", "-")

    vote_page = requests.get(VOTES_URL + url_vote_ID).text
    soup = BeautifulSoup(vote_page, 'html.parser')

    votes = soup.find("div", {"class": "votes-wrapper"})
    vote_status = ""

    # extract data
    if "Vote Defeated" in str(votes):
        vote_status = "been defeated"
    if "Vote Passed" in str(votes):
        vote_status = "passed"

    def extract_numbers(text):
        votes_for = int(re.search(r"(\d*)(?= for,)", text).group(0))
        votes_against = int(re.search(r"(?<=for, )(\d*)(?= against)", text).group(0))
        votes_abstained = int(re.search(r"(?<=against, )(\d*)(?= abstained)", text).group(0))
        votes_no_vote = int(re.search(r"(?<=abstained, )(\d*)(?= no vote)", text).group(0))
        return votes_for, votes_against, votes_abstained, votes_no_vote

    total_vote_stats = extract_numbers(votes.find("span", {"class": "vote_result--text"}).text)
    ### extract party data:

    party_votes = soup.find("div", {"class": "pv_panel"})
    parties = party_votes.find_all("p")
    party_votes_dict = {}
    for party in parties:
        party_votes_dict[party.find("span").text.strip()] = extract_numbers(party.text)

    fig = plt.figure()

    ax = fig.add_subplot(111)
    ax.set_yticks(np.arange(0, 150, 10))
    ax.xaxis.grid(False)

    ### plot bar chart:
    offset = [0,0,0,0]
    colour_dict = {"Scottish Conservative and Unionist Party" : "#0087DC",
                   "Scottish National Party": "#FDF38E",
                   "Scottish Labour": "#E4003B",
                   "No Party Affiliation": "#000000",
                   "Scottish Liberal Democrats": "#FAA61A",
                   "Scottish Green Party": "#00B140"}
    handles = []
    for i, party in enumerate(party_votes_dict.keys()):
        plt.bar(["Yes", "No", "Abstained", "No vote"], party_votes_dict[party], bottom=offset, color = colour_dict[party])
        # increase offset by amount just added to graph
        offset = list(map(add, offset,  party_votes_dict[party]))
        # if the party was involved in the vote
        if sum(party_votes_dict[party]):
            handles.append(mpatches.Patch(color=colour_dict[party], label=simplified_party_names[party]))

    ax.set_title('Results of motion '+vote_ID)

    plt.legend(handles=handles)
    plt.savefig("figs/"+vote_ID+".png")
    print(vote_status, total_vote_stats)
    tweet_vote(vote_ID, vote_name, vote_status, VOTES_URL + url_vote_ID, offset)


schedule.every(30).minutes.do(fetch_votes)

print("beginning")
fetch_votes()
while 1:
    schedule.run_pending()
    time.sleep(1)
