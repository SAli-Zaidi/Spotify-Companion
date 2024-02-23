import requests
from flask import Flask, redirect, request, jsonify, session, render_template
from datetime import datetime
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy import util
from threading import Thread
import time
import random
from dotenv import load_dotenv
import os
from flask_socketio import SocketIO, emit
# import pandas as pd

load_dotenv()

app = Flask(__name__)
app.secret_key = ".secret_key"

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
REDIRECT_URI = 'http://localhost:5000/callback'

AUTH_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token'
API_BASE_URL = 'https://api.spotify.com/v1/'
SCOPE='user-read-currently-playing user-library-read user-top-read playlist-modify-public playlist-modify-private playlist-read-private user-modify-playback-state'

SHORT_TERM = 'short_term'
MID_TERM = 'medium_term'
LONG_TERM = 'long_term'

sp_oauth = SpotifyOAuth(client_id, client_secret, REDIRECT_URI, scope=SCOPE)
sp = spotipy.Spotify(auth_manager=SpotifyOAuth(client_id=client_id,
                                                client_secret=client_secret,
                                                redirect_uri=REDIRECT_URI,
                                                scope=SCOPE,
                                                cache_path=".cashe"))

socketio = SocketIO(app)
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


def emit_current_song():
    while True:
        sp = spotipy.Spotify(auth=session.get('access_token'))  # Moved inside the loop to reinitialize with a new access token
        if 'access_token' not in session:
            socketio.emit('current_song_response', {'error': 'User not authenticated'})
            time.sleep(10)
            continue

        # Check if the access token has expired
        if datetime.now().timestamp() > session.get('expires_at', 0):
            socketio.emit('current_song_response', {'error': 'Access token expired'})
            time.sleep(5)
            continue

        # Get the user's current playing song
        current_track = sp.current_user_playing_track()

        if current_track is None:
            socketio.emit('current_song_response', {'error': 'No track is currently playing'})
            time.sleep(5)
            continue

        # Extract track details
        track_name = current_track['item']['name']
        artists = ", ".join([artist['name'] for artist in current_track['item']['artists']])
        album_name = current_track['item']['album']['name']
        album_cover_url = current_track['item']['album']['images'][0]['url']
        track_url = current_track['item']['external_urls']['spotify']

        # Get recommendations based on the current song
        recommendations = sp.recommendations(seed_tracks=[current_track['item']['id']], limit=5)

        # Extract recommended tracks
        recommended_tracks = []
        for track in recommendations['tracks']:
            recommended_tracks.append({
                'name': track['name'],
                'artists': ", ".join([artist['name'] for artist in track['artists']]),
                'album_name': track['album']['name'],
                'album_cover_url': track['album']['images'][0]['url'],
                'track_url': track['external_urls']['spotify']
            })

        # Emit the current song data and recommendations to all clients
        socketio.emit('current_song_response', {
            'track_name': track_name,
            'artists': artists,
            'album_name': album_name,
            'album_cover_url': album_cover_url,
            'track_url': track_url,
            'recommended_tracks': recommended_tracks
        })

        # Sleep for 10 seconds before emitting again
        time.sleep(10)


# Start the thread to emit the current song data
thread = Thread(target=emit_current_song)
thread.daemon = True
thread.start()

# Route to render the template
@app.route('/current-song')
def current_song():
    return render_template('current-song.html')

# WebSocket event handler to handle requests for current song data
@socketio.on('current_song_request')
def handle_current_song_request():
    # Emit the current song data from the thread
    emit_current_song()


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

def get_user_playlists():
    headers = {
        'Authorization': f"Bearer {session['access_token']}"
    }

    response = requests.get(API_BASE_URL + 'me/playlists', headers=headers)
    
    if response.status_code != 200:
        return f"Error: {response.status_code}"

    playlists_data = response.json()['items']
    
    playlists = []

    for playlist in playlists_data:
        playlist_info = {
            'id': playlist['id'],
            'name': playlist.get('name', 'Unknown Playlist'),
            'image_url': (playlist.get('images', [{'url': 'default_image_url'}]) or [{'url': 'default_image_url'}])[0]['url'],
            'external_urls': playlist.get('external_urls', {'spotify': 'https://open.spotify.com/playlist/playlist_id_1'}),
        }
        playlists.append(playlist_info)
    return playlists

@app.route('/playlists')
def get_playlists():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    playlists = get_user_playlists()

    return render_template('playlists.html', playlists=playlists)

@app.route('/select-playlist')
def select_playlist():
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    sp = spotipy.Spotify(auth=session['access_token'])
    # playlists = sp.current_user_playlists()
    playlists = get_user_playlists()

    return render_template('select_playlist.html', playlists=playlists)

@app.route('/generate-recommendations')
def generate_recommendations_route():
    playlist_id = request.args.get('playlist_id')
    return generate_recommendations(playlist_id)

def generate_recommendations(playlist_id):
    if 'access_token' not in session:
        return redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        return redirect('/refresh-token')

    try:
        # Initialize Spotify client
        sp = spotipy.Spotify(auth=session['access_token'])

        # Retrieve playlist details
        playlist = sp.playlist(playlist_id)
        
        # Extract playlist songs
        playlist_songs = []
        playlist_genres = set()  # To store unique genres from the playlist
        
        for item in playlist['tracks']['items']:
            if 'track' in item and item['track']:
                playlist_songs.append(item['track']['id'])
                track_artists = item['track']['artists']
                
                # Get random genre from each track's artists
                if track_artists:
                    random_artist = random.choice(track_artists)
                    if 'genres' in random_artist:
                        random_genre = random.choice(random_artist['genres'])
                        playlist_genres.add(random_genre)

                # Break if we have collected 2 genres
                if len(playlist_genres) >= 2:
                    break

        # Randomly select 2 songs from the playlist
        seed_tracks = random.sample(playlist_songs, min(2, len(playlist_songs)))

        # Convert playlist_genres to list to make it compatible with random.sample
        playlist_genres = list(playlist_genres)

        # Randomly select 2 genres from the playlist
        seed_genres = random.sample(playlist_genres, min(2, len(playlist_genres)))

        # Generate recommendations based on playlist songs and genres
        recommendations = sp.recommendations(seed_tracks=seed_tracks, seed_genres=seed_genres, limit=10, country='CA')

        # Extract relevant information from recommendations
        recommended_tracks = []
        for track in recommendations['tracks']:
            recommended_track = {
                'name': track['name'],
                'artists': ', '.join([artist['name'] for artist in track['artists']]),
                'album_name': track['album']['name'],
                'album_cover': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'spotify_url': track['external_urls']['spotify'] if 'external_urls' in track else None
            }
            recommended_tracks.append(recommended_track)

        return render_template('recommended_playlist.html', recommended_tracks=recommended_tracks)
    except spotipy.exceptions.SpotifyException as e:
        return f"Error: {e}"
    
@app.route('/add-to-playlist-confirmation', methods=['POST'])
def add_to_playlist_confirmation():
    # Retrieve selected tracks and playlist ID from form data
    selected_tracks = request.form.get('selected_tracks')
    playlist_id = session.get('playlist_id')

    try:
        # Ensure that both playlist ID and selected tracks are provided
        if not playlist_id or not selected_tracks:
            raise ValueError("Playlist ID or selected tracks not provided")

        # Split the selected tracks string into a list of track IDs
        selected_track_ids = selected_tracks.split(',')

        # Add the selected tracks to the playlist
        sp.playlist_add_items(playlist_id, selected_track_ids)

        # Retrieve the details of the newly added tracks
        new_tracks = []
        for track_id in selected_track_ids:
            track_info = sp.track(track_id)
            track_details = {
                'name': track_info['name'],
                'artists': ', '.join([artist['name'] for artist in track_info['artists']])
            }
            new_tracks.append(track_details)

        # Render the "Add to Playlist Confirmation" page with the list of newly added tracks
        return render_template('add_to_playlist_confirmation.html', new_tracks=new_tracks)
    except Exception as e:
        # Handle error and return appropriate message
        return render_template('add_to_playlist_confirmation.html', error=e)

@app.route('/refresh-token')
def refresh_token():
    if 'refresh_token' not in session:
        redirect('/login')

    if datetime.now().timestamp() > session['expires_at']:
        req_body = {
            'grant_type': 'refresh_token',
            'refresh_token': session['refresh_token'],
            'client_id': client_id,
            'client_secret': client_secret
        }

        response = requests.post(TOKEN_URL, data=req_body)
        new_token_info = response.json()
        session['access_token'] = new_token_info['access_token']
        session['expires_at'] = datetime.now().timestamp() + new_token_info['expires_in']

        return redirect('/main')

if __name__ == '__main__':
    socketio.run(app)