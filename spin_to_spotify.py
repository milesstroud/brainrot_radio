import requests
import time as t
from datetime import time, timedelta, datetime as dt
import pandas as pd
import sys
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import spotipy.util as util
from spotipy.oauth2 import SpotifyOAuth
import re
from rapidfuzz import fuzz, process #Will use this to handle misspellings/fatfingering/etc. Used Indel distance which is essentially just (len(text1) + len(text2)) - char_diff, used to determine how far off two texts are.
from unidecode import unidecode
import asyncio
from googletrans import Translator
import os
import pytz


#Function to generate a list of show times, split by 90 minute intervals starting at 12:30AM
def generate_show_times(start_time="00:30:00", interval=90, count=16):
    show_times = []
    time_format = "%H:%M:%S"
    current_time = dt.strptime(start_time, time_format)
    for _ in range(count):
        next_time = current_time + timedelta(minutes=interval)
        show_times.append({
            'start': f"T{current_time.strftime(time_format)}",
            'end': f"T{next_time.strftime(time_format)}"
        })
        current_time = next_time
    return show_times

def normalize_text(text):
    text = unidecode(text)  # Converts accented or non-Latin characters to closest Latin equivalent
    return text.lower().strip()

translator = Translator()

def translate_text(text, target_lang='en'):
    translation = translator.translate(text, dest=target_lang)
    return translation.text

def fuzzy_match_spotify(song, artist, spotify_results, threshold=80):
    """
    Finds the best match for a song and artist from Spotify API results using fuzzy matching.
    :param song: The song title from the radio station.
    :param artist: The artist name from the radio station.
    :param spotify_results: The JSON response from Spotify API.
    :param threshold: Minimum similarity score for a valid match.
    :return: The best matching Spotify track (or None if no match found).
    """
    best_match = None
    best_score = 0
    for track in spotify_results["tracks"]["items"]:
        track_name = track["name"]
        track_artists = [artist["name"] for artist in track["artists"]]
        # Compute fuzzy scores
        song_score = fuzz.ratio(song.lower(), track_name.lower())
        artist_score = max(fuzz.ratio(artist.lower(), a.lower()) for a in track_artists)
        # Weighted score: prioritize song title, then artist
        total_score = (song_score * 0.6) + (artist_score * 0.4)
        print(track['name'])
        print(total_score)
        if total_score > best_score and total_score >= threshold:
            best_score = total_score
            best_match = track['id']
    return best_match  # Returns None if no match meets the threshold

def get_best_spotify_match(row):
    spotify_results = search_spotify(row["Title"], row["Artist"])  # Get Spotify data
    return fuzzy_match_spotify(row["Title"], row["Artist"], spotify_results)  # Find best match


def search_spotify(song, artist):
    """Search Spotify for a song and return API results."""
    query = f"{song} {artist}"  # Combine song and artist for better accuracy
    results = sp.search(q=query, type='track', limit=10)
    return results  # Returns the full Spotify JSON response

def get_playlist_tracks(username,playlist_id):
    results = sp.user_playlist_tracks(username,playlist_id)
    playlist = results['items']
    while results['next']:
        results = sp.next(results)
        playlist.extend(results['items'])
    return playlist


show_times = generate_show_times()
page_iter = 1
spins = []

SPINITRON_API_KEY = os.getenv('SPINITRON_API_KEY')
SPOTIPY_SCOPE = os.getenv('SPOTIPY_SCOPE')
SPOTIFY_USERNAME = os.getenv('SPOTIFY_USERNAME')
SPOTIPY_CLIENT_ID = os.getenv('SPOTIPY_CLIENT_ID')
SPOTIPY_SECRET = os.getenv('SPOTIPY_SECRET')
redirect_uri = os.getenv('REDIRECT_URI')

try:
    while page_iter < 11: #Goes back a maximum of 10 pages
        r = requests.get(f'https://spinitron.com/api/spins?access-token={SPINITRON_API_KEY}&page={page_iter}')
        print(r)
        for spin in r.json()['items']:
            spins.append({
                'Title': spin['song'],
                'Album': spin['release'],
                'Artist': spin['artist'],
                'Time_Played': spin['start'][:19]
            })
        page_iter+=1
        t.sleep(10)
except requests.exceptions.RequestException as e:
    try:
        t.sleep(30)
        while page_iter < 11:
            r = requests.get(f'https://spinitron.com/api/spins?access-token={SPINITRON_API_KEY}&page={page_iter}')
            for spin in r.json()['items']:
                spins.append({
                    'Title': spin['song'],
                    'Album': spin['release'],
                    'Artist': spin['artist'],
                    'Time_Played': spin['start'][:19]
                })
            page_iter+=1
            t.sleep(10)
    except:
        sys.exit(1)

spins_df = pd.json_normalize(spins)
#If it's greater than a show's start time but less than its end time, it's currently running. Get the start and end from the PRIOR timeslot.
show_iter = 0



eastern_tz = pytz.timezone("America/New_York")

# Get the current time in Eastern Time
eastern_now = dt.utcnow().replace(tzinfo=pytz.utc).astimezone(eastern_tz)


# Extract only the time component for comparison
eastern_now_time = eastern_now.time()

# Get today's and yesterday's date in Eastern Time
eastern_today_str = eastern_now.strftime('%Y-%m-%d')
eastern_yesterday_str = (eastern_now - timedelta(days=1)).strftime('%Y-%m-%d')

# Iterate over show_times with Eastern Time handling
for show_iter, slot in enumerate(show_times, start=1):
    # Convert time slot strings to native Python time objects
    start_time = time(
        int(slot['start'][1:3].lstrip("0") or "00"),
        int(slot['start'][4:6].lstrip("0") or "00")
    )
    end_time = time(
        int(slot['end'][1:3].lstrip("0") or "00"),
        int(slot['end'][4:6].lstrip("0") or "00")
    )
    # Handle normal case where start_time is before end_time
    if start_time <= end_time:
        is_active = start_time <= eastern_now_time < end_time
    else:
        # Handle the special case where the show crosses midnight
        is_active = eastern_now_time >= start_time or eastern_now_time < end_time
    if is_active:
        start = show_times[show_iter - 2]['start']
        end = show_times[show_iter - 2]['end']

#Combine today's date with timeslot timestamps
if start == 'T23:00:00':
    start_date = dt.strptime(eastern_yesterday_str + start, "%Y-%m-%dT%H:%M:%S")
    end_date = dt.strptime(eastern_today_str + end, "%Y-%m-%dT%H:%M:%S")
else:
    start_date = dt.strptime(eastern_today_str + start, "%Y-%m-%dT%H:%M:%S")
    end_date = dt.strptime(eastern_today_str + end, "%Y-%m-%dT%H:%M:%S")

#Slice/Index: Keep only entries from last show based on start and end times.
#Using a try/except
spins_df['Time_Played_Dt'] = pd.to_datetime(spins_df['Time_Played'])
last_show_spins = spins_df.loc[(spins_df['Time_Played_Dt'] > start_date) & (spins_df['Time_Played_Dt'] < end_date)]

if last_show_spins.empty == True:
    raise RuntimeError('No spins during last show block.')

#Spotipy Authentication
token = SpotifyOAuth(scope=SPOTIPY_SCOPE,username=SPOTIFY_USERNAME, client_id=SPOTIPY_CLIENT_ID,client_secret=SPOTIPY_SECRET, redirect_uri=redirect_uri)
sp = spotipy.Spotify(auth_manager=token)

#Read current playlist to prevent duplication in the future
current_playlist = get_playlist_tracks(SPOTIFY_USERNAME, '1pOUJGc0eEmEjzRNB0L5CV')
current_tracks = pd.json_normalize(current_playlist)
current_tracks=current_tracks.rename(columns = {'track.id':'track_id'})
tracks = []
bad_chars = "'"

#Cleaning

spins_df[['Title', 'Album', 'Artist']] = spins_df[['Title', 'Album', 'Artist']].map(normalize_text)
spins_df[['Title', 'Album', 'Artist']] = spins_df[['Title', 'Album', 'Artist']].applymap(translate_text)

for index, row in last_show_spins.iterrows():
    spins_df["spotify_match"][index] = get_best_spotify_match(row)

tracks.reverse()
try:
    for track in tracks:
        if track in current_tracks.track_id.values:
            tracks.remove(track)
        else:
            pass
except AttributeError as e:
    print("Empty Dataframe. Proceeding to add tracks." + str(e))
    pass
sp.playlist_add_items('1pOUJGc0eEmEjzRNB0L5CV', tracks) 


#If needed - remove duplicates. Removes last instance of a track id.
# def wrap_in_list(x):
#     return [x]

# dupes = current_tracks[current_tracks['track.id'].duplicated()]
# dupes['index'] = dupes.index
# dupes['index'] = dupes['index'].apply(wrap_in_list)
# dupes = dupes[['track.id','index']]
# dupes = dupes.rename(columns = {'track.id':'uri', 'index':'positions'})
# dupes = dupes.to_dict('records')

# sp.playlist_remove_specific_occurrences_of_items('1pOUJGc0eEmEjzRNB0L5CV', dupes)
