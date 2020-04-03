import os
import sys
import json
import spotipy
import webbrowser
import spotipy.util as util
from json.decoder import JSONDecodeError
import sqlite3
import collections
import matplotlib.pyplot as plt; plt.rcdefaults()
import matplotlib.pyplot as plt
import numpy as np
import re
from Spotify import spotipyObject
import pdb
import time
import warnings
warnings.filterwarnings("ignore")


# Key map, take from spotify used to map integer to key value
KEY_MAP = {
            -1: 'NoKey', 0: 'C', 1: 'Csharp', 2: 'D', 3: 'Dsharp', 4: 'E', 5: 'F', 6: 'Fsharp', 7: 'G', 8: 'Gsharp',
            9: 'A', 10: 'Asharp', 11: 'B'
          }


# Megan: https://open.spotify.com/user/1222209229?si=hYMEP4oHSoeHPGIERY8RDQ
# User ID: 129206905 1298080332?si=yRZfhikiTEq1b5-1Pj6Xrw
# user = 129206905

# # Erase cache and prompt for user permission
# try:
#     token = util.prompt_for_user_token(username, scope, client_id='8579ac79b14349bf96f34f51f5218c61',
#                                        client_secret='506ceb469d0f414782ca2eba41ac5613',
#                                        redirect_uri='https://google.com/')
# except:
#     os.remove(f".cache-{user}")
#     token = util.prompt_for_user_token(username, scope, client_id='8579ac79b14349bf96f34f51f5218c61',
#                                        client_secret='506ceb469d0f414782ca2eba41ac5613',
#                                        redirect_uri='https://google.com/')
#
# # Create Spotipy Object
# spt = spotipy.Spotify(auth=token)

class RecommendTables:
    def __init__(self, conn, cur):
        self.conn = conn
        self.cur = cur


    def createTables(self):
        self.cur.executescript('''
        DROP TABLE IF EXISTS Artist;
        DROP TABLE IF EXISTS Genre;
        DROP TABLE IF EXISTS Track;
        DROP TABLE IF EXISTS Album;
        
        CREATE TABLE IF NOT EXISTS Artist (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            name TEXT UNIQUE,
            genre_id TEXT,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS Genre (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            type TEXT UNIQUE
        );
        
        CREATE TABLE IF NOT EXISTS Track (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            name TEXT,
            artist_id INTEGER,
            uri TEXT
        );
        
        CREATE TABLE IF NOT EXISTS Album (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            name TEXT,
            artist_id INTEGER,
            uri TEXT
        );
        ''')


    def createFeatureTable(self):
        self.cur.executescript('''
        DROP TABLE IF EXISTS Features;
    
        CREATE TABLE IF NOT EXISTS Features (
            acousticness REAL,
            danceability REAL,
            energy REAL,
            instrumentalness REAL,
            key INTEGER,
            liveness REAL, 
            loudness REAL,
            mode REAL, 
            valence REAL,
            tempo REAL,
            artist_id INTEGER,
            song_id INTEGER,
            album_id INTEGER,
            uri TEXT, 
            sid INTEGER,
            length INTEGER
            )
        ''')


class recFeatures(RecommendTables):
    def __init__(self, conn, cur, spt):
        self.conn = conn
        self.cur = cur
        self.spt = spt
        super().__init__(conn, cur)


    def addArtistsAlbums(self):
        dump = self.spt.new_releases(limit=50)
        dumps = dump['albums']['items']
        uri_cache = []
        # print(json.dumps(dumps, indent=3, sort_keys=True))

        for alb in dumps:
            # print(alb['artists'])
            # print(alb['artists'][0])
            artist = alb['artists'][0]['name']
            artist_uri = alb['artists'][0]['uri']
            album_uri = alb['uri']
            album = alb['name']

            self.cur.execute('''INSERT OR IGNORE INTO Artist (name, uri) VALUES (?, ?)''', (artist, artist_uri))
            artist_id = self.cur.execute('''SELECT id FROM Artist WHERE uri = (?)''', (artist_uri, )).fetchone()[0]
            self.cur.execute('''INSERT OR IGNORE INTO Album (name, uri, artist_id) VALUES (?, ?, ?)''', (album, album_uri, artist_id))
            uri_cache.append(artist_uri)
        self.conn.commit()
        return uri_cache


    def add_genres(self, new_artists):
        for artist in new_artists['artists']:
            name = artist['name']
            genre = artist['genres']
            if genre:
                self.cur.execute('INSERT OR IGNORE INTO Genre (type) VALUES ( ? )', (repr(genre),))
                genre_id = self.cur.execute('SELECT * FROM Genre WHERE type = ( ? )', (repr(genre),)).fetchone()[0]
                self.cur.execute('''UPDATE Artist SET (genre_id) = (?) WHERE name = (?)''',
                            (genre_id, name))
            else:
                # Delete Album and Delete artist
                id = self.cur.execute('SELECT id FROM Artist WHERE name = (?)', (name,)).fetchone()[0]
                self.cur.execute('DELETE FROM Artist WHERE name = (?)', (name,))
                self.cur.execute('DELETE FROM Album WHERE artist_id = (?)', (id,))
                print('New Artist deleted due to lack of information')
        self.conn.commit()


    # Add songs from album or single
    def AlbumSongs(self, album_uri):
        for album in album_uri:
            tracks = self.spt.album_tracks(album)
            artist = tracks['items'][0]['artists'][0]['name']
            try:
                artist_id = self.cur.execute('''SELECT id FROM Artist WHERE name = (?)''', (artist,)).fetchone()[0]
                for track in tracks['items']:
                    uri = track['uri']
                    name = track['name']
                    self.cur.execute('''INSERT OR IGNORE INTO Track (artist_id, uri, name) VALUES (?, ?, ?)''', (artist_id, uri, name))
            except:
                print('FAULTY ALBUM URI')

        self.conn.commit()


    def genre_feature(self, sid):
        # Loop over all the rows in the features database, add genres found from the artist table
        for genre_id, song_id in self.cur.execute(
                '''SELECT genre_id, song_id FROM Features INNER JOIN Artist ON Features.artist_id = Artist.id
                 WHERE sid = (?)''', (sid, )).fetchall():

            # Pull out genres list from genre table for correponding artist
            genres = eval(self.cur.execute('''SELECT type FROM Genre WHERE id = (?)''', (genre_id, )).fetchone()[0])
            genre_weight = 1

            # Account for the fact that multiple genres happend for each artist
            for genre in genres:
                # Regex replace all symbols with nothing, not allowed for column title
                genre = re.sub(r'[^\w]', '_', genre)
                # Replace all spaces
                genre.replace(' ', '_')

                # Try to add column if does not exist, if this fails column is already present. Add bianary value
                try:
                    query = 'ALTER TABLE Features ADD {} INTEGER'.format(genre)
                    self.cur.execute(query)
                    query = 'UPDATE Features SET {} = (?) WHERE song_id = (?)'.format(genre)
                    self.cur.execute(query, (genre_weight, song_id))
                except:
                    query = 'UPDATE Features SET {} = (?) WHERE song_id = (?)'.format(genre)
                    self.cur.execute(query, (genre_weight, song_id))
        self.conn.commit()


    def key_feature(self, sid):
        # Add 'key' bianary feature, loop over all new songs added to feature
        for song_id, key, uri in self.cur.execute(
                '''SELECT song_id, key, uri FROM Features WHERE sid = (?)''', (sid, )).fetchall():
            str_key = KEY_MAP[key]
            try:
                query = 'ALTER TABLE Features ADD {} INTEGER'.format(str_key)
                self.cur.execute(query)
                query = 'UPDATE Features SET {} = (?) WHERE song_id = (?)'.format(str_key)
                self.cur.execute(query, (1, song_id))
            except:
                query = 'UPDATE Features SET {} = (?) WHERE song_id = (?)'.format(str_key)
                self.cur.execute(query, (1, song_id))
        self.conn.commit()


    def features(self, uris, sid=1):
        # Get audio featues for songs
        features = self.spt.audio_features(tracks=uris)
        faulty = 0

        # Loop over all songs in features, pull out individuals
        for song in features:
            try:
                length = song['duration_ms']
                if int(length) < 105000:
                    continue

                uri = song['uri']
                acousticness = song['acousticness']
                danceability = song['danceability']
                energy = song['energy']
                instrumentalness = song['instrumentalness']
                key = song['key']
                liveness = song['liveness']
                loudness = song['loudness']
                mode = song['mode']  # 1 = major, 0 = minor
                valence = song['valence']
                tempo = song['tempo']

                # Pull ou the song and artist id's for each song searched, match uri
                song_id, name, artist_id = self.cur.execute('''SELECT id, name, artist_id FROM Track WHERE uri = (?)''', (uri, )).fetchone()

                # Find album id
                album_id = self.cur.execute('''SELECT id FROM Album WHERE artist_id = (?)''', (artist_id, )).fetchone()[0]


                # Insert all features into feature database
                self.cur.execute('''INSERT OR IGNORE INTO Features 
                                (
                                    acousticness, danceability, energy, instrumentalness, key, liveness, 
                                    loudness, mode, valence, tempo, uri, song_id, artist_id, sid, album_id
                                ) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (
                                    acousticness, danceability, energy, instrumentalness, key, liveness,
                                    loudness, mode, valence, tempo, uri, song_id, artist_id, sid, album_id
                                )
                            )
            except:
                faulty += 1

        if faulty > 0:
            print('{} faulty uris found'.format(faulty))

        # Commit once all features have been inserted
        self.conn.commit()
        self.genre_feature(sid)
        self.key_feature(sid)
        # print(json.dumps(features, sort_keys=True, indent=3))


    def generateFeatures(self):
        # Create Basic Tables in Database for comparison songs
        self.createTables()

        # Add artists to previously created tables for comparison songs
        uri_cache = self.addArtistsAlbums()
        artists = self.spt.artists(uri_cache)
        self.add_genres(artists)

        # Add albums into database from the new artists
        albums = self.cur.execute('''SELECT uri FROM Album''').fetchall()
        albums = [alb[0] for alb in albums]
        self.AlbumSongs(albums)

        # Add features into database of songs from those artists
        self.createFeatureTable()
        uris = self.cur.execute('''SELECT uri FROM Track''').fetchall()
        uris = [uri[0] for uri in uris]
        chunks_uri = [uris[x:x + 100] for x in range(0, len(uris), 100)]
        for chunk in chunks_uri:
            self.features(chunk, sid=1)

        self.close()

    def close(self):
        self.cur.close()
        self.conn.close()


def main():
    username = sys.argv[1]
    scope = 'user-top-read'
    conn = sqlite3.connect('Spotify_compare.sqlite')
    cur = conn.cursor()
    spt = spotipyObject(username, scope)
    start = time.time()
    print('Collecting and analyzing new songs on Spotify...')
    rec = recFeatures(conn, cur, spt)
    rec.generateFeatures()
    print('Finished analyzing Spotify new music, this took about {}'.format(time.time()-start))
    time.sleep(3)
    print()

if __name__ == '__main__':
    main()