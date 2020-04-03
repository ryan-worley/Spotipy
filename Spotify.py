import warnings
warnings.filterwarnings("ignore")
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
import time



def spotipyObject(username, scope='user-top-read'):
    # Erase cache and prompt for user permission
    try:
        token = util.prompt_for_user_token(username, scope, client_id='8579ac79b14349bf96f34f51f5218c61',
                                           client_secret='506ceb469d0f414782ca2eba41ac5613',
                                           redirect_uri='https://google.com/')
    except:
        os.remove(f".cache-{user}")
        token = util.prompt_for_user_token(username, scope, client_id='8579ac79b14349bf96f34f51f5218c61',
                                           client_secret='506ceb469d0f414782ca2eba41ac5613',
                                           redirect_uri='https://google.com/')
    # Create Spotipy Object
    spt = spotipy.Spotify(auth=token)
    return spt

class userSongs():
    def __init__(self, cur, conn):
        self.cur = cur
        self.conn = conn

    def createNewDatabase(self):
        # Make new tables to store data
        self.cur.executescript('''
           DROP TABLE IF EXISTS Artist;
           DROP TABLE IF EXISTS Genre;
           DROP TABLE IF EXISTS Track;

           CREATE TABLE IF NOT EXISTS Artist (
               id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
               name TEXT UNIQUE,
               popularity INTEGER,
               genre_id TEXT,
               uri TEXT,
               t_50 INTEGER
           );

           CREATE TABLE IF NOT EXISTS Genre (
               id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
               type TEXT UNIQUE
           );

           CREATE TABLE IF NOT EXISTS Track (
               id  INTEGER NOT NULL PRIMARY KEY 
                   AUTOINCREMENT UNIQUE,
               name TEXT,
               artist_id INTEGER,
               popularity INTEGER,
               uri TEXT,
               t_50 INTEGER
           );
           ''')
        self.conn.commit()

    def addExistingDatabase(self):
        # Make new tables to store data
        self.cur.executescript('''
        CREATE TABLE IF NOT EXISTS Artist (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            name TEXT UNIQUE,
            popularity INTEGER,
            genre_id TEXT,
            uri TEXT,
            t_50 INTEGER
        );

        CREATE TABLE IF NOT EXISTS Genre (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
            type TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS Track (
            id  INTEGER NOT NULL PRIMARY KEY 
                AUTOINCREMENT UNIQUE,
            name TEXT,
            artist_id INTEGER,
            popularity INTEGER,
            uri TEXT,
            t_50 INTEGER
        );
        ''')
        self.conn.commit()

class top50Store(userSongs):
    def __init__(self, cur, conn, object):
        super().__init__(cur, conn)
        self.spt = object
        self.artists = self.spt.current_user_top_artists(limit=50, time_range='medium_term')
        self.songs = self.spt.current_user_top_tracks(limit=50, time_range='medium_term')
        self.cur = cur
        self.conn = conn

    def artistsInfo(self):
        # Loop over all artist pulled in from top 50, remove information from them, store in artist table
        for item in self.artists["items"]:
            name = item['name']
            genre = item['genres']
            popularity = item['popularity']
            uri = item['uri']

            self.cur.execute('INSERT OR IGNORE INTO Genre (type) VALUES ( ? )', ( repr(genre), ))
            self.cur.execute('SELECT * FROM Genre WHERE type = ( ? )', (repr(genre), ))
            genre_id = self.cur.fetchone()[0]

            self.cur.execute('''INSERT OR IGNORE INTO Artist (name, popularity, genre_id, uri, t_50)
                        VALUES (?, ?, ?, ?, ?)''',
                        (name, popularity, genre_id, uri, 1))

            self.cur.execute('SELECT * FROM Artist WHERE name = ( ? )', (name, ))
            # artist_id = cur.fetchone()[0]
        # commit changes to database
        self.conn.commit()

    def songInfo(self):
        # Pull out information about top 50 songs, put information into database regarding them
        artists_add = []
        artists_ = []
        for item in self.songs["items"]:
            artist = item['artists'][0]['name'] # Just taking the first artist in the list
            name = item['name'] # NAme of the song
            popularity = item['popularity'] # Pop of song
            uri = item['uri']  # Link to song if needed
            self.cur.execute('INSERT OR IGNORE INTO Track (name, popularity, uri, t_50) VALUES (?, ?, ?, ?)', (name, popularity, uri, 1))
            try:
                self.cur.execute('SELECT * FROM Artist WHERE name = (?)', (artist, ))
                artist_id = cur.execute('SELECT * FROM Artist WHERE name = (?)', (artist,)).fetchone()[0]
                self.cur.execute('UPDATE Track SET (artist_id) = (?) WHERE name = (?)', (artist_id, name))
            except:
                artist_uri = item['artists'][0]['uri']
                self.cur.execute('INSERT OR IGNORE INTO Artist (name, uri) VALUES (?, ?)', (artist, artist_uri))
                artist_id = self.cur.execute('SELECT * FROM Artist WHERE name = (?)', (artist, )).fetchone()[0]
                self.cur.execute('UPDATE Track SET (artist_id) = (?) WHERE name = (?)', (artist_id, name))
                artists_add.append(artist_uri)
                artists_.append(artist)
        self.conn.commit()
        if artists_add:
            self.newArtistsFromSongs(artists_add)

    def newArtistsFromSongs(self, artists_add):
        new_artists = self.spt.artists(artists_add)
        for artist in new_artists['artists']:
            name = artist['name']
            genre = artist['genres']
            popularity = artist['popularity']

            self.cur.execute('INSERT OR IGNORE INTO Genre (type) VALUES ( ? )', (repr(genre),))
            self.cur.execute('SELECT * FROM Genre WHERE type = ( ? )', (repr(genre),))
            genre_id = self.cur.fetchone()[0]

            self.cur.execute('''UPDATE Artist SET (popularity) = (?),
                        (genre_id) = (?), (t_50) = (?)
                        WHERE name = (?)''',
                        (popularity, genre_id, 0, name))
        self.conn.commit()

    def createDatabase(self):
        self.createNewDatabase()
        self.artistsInfo()
        self.songInfo()
        print('Gathered Top 50 Artists and Top 50 songs form last 4 months of listening Spotify Data')

def main():
    # Connect to database
    conn = sqlite3.connect('Spotify.sqlite')
    cur = conn.cursor()
    start = time.time()
    username = sys.argv[1]
    scope = 'user-top-read'
    spt = spotipyObject(username, scope)
    obj = top50Store(cur, conn, spt)
    obj.createDatabase()
    cur.close()
    conn.close()
    end = time.time()
    print('Total time spent mining data is : {} seconds'.format(end - start))

if __name__ == '__main__':
    main()
