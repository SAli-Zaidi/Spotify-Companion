  
import requests
import urllib.parse
from flask import Flask, redirect, request, jsonify, session, render_template
from datetime import datetime, timedelta
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.oauth2 import SpotifyClientCredentials
# import pandas as pd

app = Flask(__name__)

TOP_TRACKS_ALLTIME = []

app.secret_key = ".secret_key"

CLIENT_ID = 'a37086d750d9439bb4b7bd16d934c961'
CLIENT_SECRET = 'd34345e581294355993a2ddfbf028772'
REDIRECT_URI = 'http://localhost:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'
SCOPE='user-read-currently-playing user-library-read user-top-read playlist-modify-public playlist-read-private user-modify-playback-state'

SHORT_TERM = 'short_term'
MID_TERM = 'medium_term'
LONG_TERM = 'long_term'

sp_oauth = SpotifyOAuth(CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, scope=SCOPE)
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=CLIENT_ID,
                                                client_secret=CLIENT_SECRET,
                                                redirect_uri=REDIRECT_URI,
                                                scope=SCOPE,
                                                cache_path=".cashe"))
@app.route('/')
def index():
    # return "Welcome to Spotify Recommendation <a href='/login'>Login with Spotify</a>"
    return render_template('index.html')

@app.route('/login')
def login():

    auth_url = sp_oauth.get_authorize_url()
    
    # auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    return redirect(auth_url)


@app.route('/callback')
def callback():
    if 'error' in request.args:
        return jsonify({"error": request.args['error']})
    
    if 'code' in request.args:
        token_info = sp_oauth.get_access_token(request.args['code'])
        
        session['access_token'] = token_info['access_token']
        session['refresh_token'] = token_info['refresh_token']
        session['expires_at'] = token_info['expires_at']
        
        return redirect('/main')
    else:
        return jsonify({"error": "Authorization code not found in request."})



@app.route('/main')
def main():
    return render_template('main.html')

@app.route('/top-songs')
def top_songs():

    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    sp = spotipy.Spotify(auth=session['access_token'])  # Create Spotify API client with access token

    top_tracks = sp.current_user_top_tracks(limit=10, time_range='long_term')

    return render_template('top-tracks.html', top_tracks=top_tracks['items'])

@app.route('/current-songs')
def current_song():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')
    
    sp = spotipy.Spotify(auth=session['access_token'])

    # Get the user's current playing song
    current_track = sp.current_user_playing_track()

    # Check if the user is currently playing a track
    if current_track is None:
        return "No track is currently playing."

    # Extract track details
    track_name = current_track['item']['name']
    artists = ", ".join([artist['name'] for artist in current_track['item']['artists']])
    album_name = current_track['item']['album']['name']
    album_cover_url = current_track['item']['album']['images'][0]['url']
    track_url = current_track['item']['external_urls']['spotify']

    return render_template('current-songs.html', track_name=track_name, artists=artists, album_name=album_name, album_cover_url=album_cover_url, track_url=track_url)
    
@app.route('/recommended-songs')
def recommended_songs():
   
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    sp = spotipy.Spotify(auth=session['access_token'])  # Create Spotify API client with access token

    top_tracks_short = sp.current_user_top_tracks(limit=5, offset=0, time_range=MID_TERM)
    track_ids = [track['id'] for track in top_tracks_short['items']]
    
    recommended_songs = sp.recommendations(seed_tracks=track_ids, country="CA")
    
    formatted_recommendations = []
    for track in recommended_songs['tracks']:
        artists = ', '.join([artist['name'] for artist in track['artists']])
        formatted_recommendations.append({
            'name': track['name'],
            'artists': artists,
            'album_name': track['album']['name'],
            'album_cover': track['album']['images'][0]['url'] if track['album']['images'] else None,
            'external_url': track['external_urls']['spotify'] if 'external_urls' in track and 'spotify' in track['external_urls'] else None
        })



    return render_template('recommended-tracks.html', recommended_tracks=formatted_recommendations)


# @app.route('/new-playlist')
# def new_playlists():


#     return render_template('new-playlists.html', new_playlists=new_playlists)


# def get_trending_playlist_data(playlist_id, access_token):
#     # Set up Spotipy with the access token
#     sp = spotipy.Spotify(auth=access_token)

#     # Get the tracks from the playlist
#     playlist_tracks = sp.playlist_tracks(playlist_id, fields='items(track(id, name, artists, album(id, name)))')

#     # Extract relevant information and store in a list of dictionaries
#     music_data = []
#     for track_info in playlist_tracks['items']:
#         track = track_info['track']
#         track_name = track['name']
#         artists = ', '.join([artist['name'] for artist in track['artists']])
#         album_name = track['album']['name']
#         album_id = track['album']['id']
#         track_id = track['id']

#         # Get audio features for the track
#         audio_features = sp.audio_features(track_id)[0] if track_id != 'Not available' else None

#         # Get release date of the album
#         try:
#             album_info = sp.album(album_id) if album_id != 'Not available' else None
#             release_date = album_info['release_date'] if album_info else None
#         except:
#             release_date = None

#         # Get popularity of the track
#         try:
#             track_info = sp.track(track_id) if track_id != 'Not available' else None
#             popularity = track_info['popularity'] if track_info else None
#         except:
#             popularity = None

#         # Add additional track information to the track data
#         track_data = {
#             'Track Name': track_name,
#             'Artists': artists,
#             'Album Name': album_name,
#             'Album ID': album_id,
#             'Track ID': track_id,
#             'Popularity': popularity,
#             'Release Date': release_date,
#             'Duration (ms)': audio_features['duration_ms'] if audio_features else None,
#             'Explicit': track_info.get('explicit', None),
#             'External URLs': track_info.get('external_urls', {}).get('spotify', None),
#             'Danceability': audio_features['danceability'] if audio_features else None,
#             'Energy': audio_features['energy'] if audio_features else None,
#             'Key': audio_features['key'] if audio_features else None,
#             'Loudness': audio_features['loudness'] if audio_features else None,
#             'Mode': audio_features['mode'] if audio_features else None,
#             'Speechiness': audio_features['speechiness'] if audio_features else None,
#             'Acousticness': audio_features['acousticness'] if audio_features else None,
#             'Instrumentalness': audio_features['instrumentalness'] if audio_features else None,
#             'Liveness': audio_features['liveness'] if audio_features else None,
#             'Valence': audio_features['valence'] if audio_features else None,
#             'Tempo': audio_features['temp'] if audio_features else None, 
#         }
#         music_data.append(track_data)

#         df = pd.Dataframe(music_data)

#         return df
    
    
@app.route('/playlists')
def get_playlists():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }
    response = requests.get(API_BASE_URL + 'me/playlists', headers=headers)
    # sp = spotipy.Spotify(auth=session['access_token'])  # Create Spotify API client with access token
    if response.status_code != 200:
        return f"Error: {response.status_code}"

    playlists_data = response.json()['items']
    
    playlists = []

    for playlist in playlists_data:
        playlist_info = {
            'name': playlist.get('name', 'Unknown Playlist'),
            'image_url': (playlist.get('images', [{'url': 'default_image_url'}]) or [{'url': 'default_image_url'}])[0]['url'],
            'external_urls': playlist.get('external_urls', {'spotify': 'https://open.spotify.com/playlist/playlist_id_1'}),
        }
        playlists.append(playlist_info)

    return render_template('playlists.html', playlists=playlists)
    

@app.route('/refresh-token')
def refresh_token():
    if 'refresh_token' not in session:
        redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            'grant_type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET
        }

        response = requests.post(TOKEN_URL, data=req_body)
        new_token_info = response.json()
        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']

        return redirect('/playlists')

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
