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
import time
import warnings
warnings.filterwarnings("ignore")

KEY_MAP = {
            -1: 'NoKey', 0: 'C', 1: 'Csharp', 2: 'D', 3: 'Dsharp', 4: 'E', 5: 'F', 6: 'Fsharp', 7: 'G', 8: 'Gsharp',
            9: 'A', 10: 'Asharp', 11: 'B'
          }

class FeaturesDatabase:
    def __init__(self, cur, conn):
        self.cur = cur
        self.conn = conn

    def FeatureTable(self):
        self.cur.executescript('''
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
                    uri TEXT, 
                    sid INTEGER
                    )
                ''')
        self.cur.execute('''DELETE FROM Track WHERE t_50 IS NULL''')
        self.conn.commit()

    def createNewFeatureTable(self):
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
            uri TEXT, 
            sid INTEGER
            )
        ''')
        self.cur.execute('''DELETE FROM Track WHERE t_50 IS NULL''')
        self.conn.commit()


class Features(FeaturesDatabase):
    def __init__(self, cur, conn, spt):
        self.cur = cur
        self.conn = conn
        super().__init__(cur, conn)
        self.verbose = 1
        self.spt = spt

    def genreCount(self):
        self.cur.execute('SELECT * FROM Genre')
        genrecount = collections.defaultdict(int)

        for genre in self.cur.fetchall():
            genres = eval(genre[1])
            for g in genres:
                genrecount[g] += 1

        gct = sorted(genrecount.items(), key=lambda x: x[1], reverse=True)

        objects = []
        count = []
        for gc in gct:
            objects.append(gc[0])
            count.append(gc[1])
            if gc == gct[15]:
                objects.reverse()
                count.reverse()
                break

        y_pos = np.arange(len(objects))

        if self.verbose:
            plt.barh(y_pos, count, align='center', alpha=0.5)
            plt.yticks(y_pos, objects, rotation='horizontal')
            plt.xticks(np.arange(0, max(count) + 1 , 2.0))
            plt.ylabel('Track List')
            plt.xlabel('Genre')
            plt.title('Genre Preferences')
            plt.show()

    def popularity(self):
        art_avg = self.cur.execute('SELECT  avg(popularity) FROM Artist').fetchone()
        song_avg = self.cur.execute('SELECT  avg(popularity) FROM Track').fetchone()
        art_max, pop_art_max = self.cur.execute('''SELECT name, popularity FROM Artist
                                           WHERE popularity = (SELECT max(popularity) FROM Artist)''').fetchone()
        song_max, pop_song_max = self.cur.execute('''SELECT name, popularity FROM Track
                                              WHERE popularity = (SELECT max(popularity) FROM Track)''').fetchone()
        art_min, pop_art_min = self.cur.execute('''SELECT name, popularity FROM Artist
                                           WHERE popularity = (SELECT min(popularity) FROM Artist)''').fetchone()
        song_min, pop_song_min = self.cur.execute('''SELECT name, popularity FROM Track 
                                              WHERE popularity = (SELECT min(popularity) FROM Track)''').fetchone()

        return art_avg, song_avg, art_max, pop_art_max, song_max, pop_song_max, art_min, pop_art_min, song_min, pop_song_min


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


    def genre_feature(self, sid):
        # Loop over all the rows in the features database, add genres found from the artist table
        for artist_id, song_id, key, uri in self.cur.execute(
                '''SELECT artist_id, song_id, key, uri FROM Features WHERE sid = (?)''', (sid, )).fetchall():

            # Pull out genres list from genre table for correponding artist
            try:
                genres = eval(self.cur.execute('''SELECT type FROM Genre WHERE id = (?)''', (artist_id, )).fetchone()[0])
            except:
                continue

            # Account for the fact that multiple genres happend for each artist
            for genre in genres:
                # Regex replace all symbols with nothing, not allowed for column title
                genre = re.sub(r'[^\w]', '', genre)
                # Replace all spaces
                genre.replace(' ', '_')

                # Try to add column if does not exist, if this fails column is already present. Add bianary value
                try:
                    query = 'ALTER TABLE Features ADD {} INTEGER'.format(genre)
                    self.cur.execute(query)
                    query = 'UPDATE Features SET {} = (?) WHERE song_id = (?)'.format(genre)
                    self.cur.execute(query, (1, song_id))
                except:
                    query = 'UPDATE Features SET {} = (?) WHERE song_id = (?)'.format(genre)
                    self.cur.execute(query, (1, song_id))
        self.conn.commit()


    def features(self, uris, sid=1):
        # Get audio featues for songs
        features = self.spt.audio_features(tracks=uris)

        # Loop over all songs in features, pull out individuals
        for song in features:
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
            song_id, artist_id = self.cur.execute('''SELECT id, artist_id FROM Track WHERE uri = (?)''', (uri, )).fetchone()

            # Insert all features into feature database
            self.cur.execute('''INSERT OR IGNORE INTO Features 
                            (
                                acousticness, danceability, energy, instrumentalness, key, liveness, 
                                loudness, mode, valence, tempo, uri, song_id, artist_id, sid
                            ) 
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                            (
                                acousticness, danceability, energy, instrumentalness, key, liveness,
                                loudness, mode, valence, tempo, uri, song_id, artist_id, sid
                            )
                        )

        # Commit once all features have been inserted
        self.conn.commit()
        self.genre_feature(sid)
        self.key_feature(sid)
        # print(json.dumps(features, sort_keys=True, indent=3))


    def getArtist10Songs(self, information):
        # Separate out the necessary fields from information for previous database request
        artists = [artist[0] for artist in information]
        artist_ids = [artist[1] for artist in information]

        # Delete all test cases from table
        self.cur.execute('''DELETE FROM Track WHERE t_50 IS NULL''')

        # Loop over the information, one at a time
        for i, artist in enumerate(artists):
            # Get out top 10 tracks from a single spotify artist
            tracks = self.spt.artist_top_tracks(artist)
            artist_id = artist_ids[i]
            #artist_name = tracks['tracks'][0]['name']
            for track in tracks['tracks']:
                song = track['name']
                uri = track['uri']
                popularity = track['popularity']
                self.cur.execute('''INSERT INTO Track (name, artist_id, popularity, uri) VALUES (?, ?, ?, ?)''',
                            (song, artist_id, popularity, uri))
            self.conn.commit()


def main():
    # Get username from terminal
    username = sys.argv[1]
    scope = 'user-top-read'
    spt = spotipyObject(username, scope=scope)
    conn = sqlite3.connect('Spotify.sqlite')
    cur = conn.cursor()

    # Create Features Object
    obj = Features(cur, conn, spt)
    print()

    if '-genre' in sys.argv:
        # Genre Count
        print('Displaying Genre count data. Close graph to continue')
        print()
        obj.genreCount()

    if '-pop' in sys.argv:
        # Get out popularity stats
        pop = obj.popularity()
        print('Average song popularity: {}, Average artist popularity: {} (out of 100)'.format(pop[0], pop[1]))
        wait = input("PRESS ENTER TO CONTINUE.")
        print()

    print('Analyzing data from your favorite music and artists...')
    start = time.time()
    # Features for top 50 songs, add to database
    obj.createNewFeatureTable()
    top50_songs = obj.cur.execute('SELECT uri FROM Track WHERE t_50 = 1').fetchall()
    top50_songs = [val for sublist in top50_songs for val in sublist]
    obj.features(top50_songs, sid=1)

    # # Fetch all uri's, id's, and names from artists in the top 50, add to db
    information = obj.cur.execute('''SELECT uri, id, name FROM Artist WHERE t_50 = 1''').fetchall()
    obj.getArtist10Songs(information)

    # Get features for top artist songs in database, 100 at a time
    information = obj.cur.execute('''SELECT uri FROM Track WHERE t_50 IS NULL''').fetchall()
    uris = [x[0] for x in information]
    chunks_uri = [uris[x:x+100] for x in range(0, len(uris), 100)]
    for chunk in chunks_uri:
        obj.features(chunk, sid=2)
    print('Finished analyzing your current music library. This took about {} seconds'.format(time.time()-start))
    time.sleep(3)
    print()
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()


# ''' Could move to main, make all cur and conn calls based off object '''
# # Count and plot genre's
# if '-g' or '-a' in sys.argv:
#     obj.genreCount()
#
# # Assess popularity stats of songs
# if '-p' or '-a' in sys.argv:
#     pop = obj.popularity()
#
# # Features for top 50 songs, add to database
# if '-t50sf' or '-a' in sys.argv:
#     obj.createNewFeatureTable()
#     top50_songs = cur.execute('SELECT uri FROM Track WHERE t_50 = 1').fetchall()
#     top50_songs = [val for sublist in top50_songs for val in sublist]
#     obj.features(top50_songs, sid=1)
#
# # Fetch all uri's, id's, and names from artists in the top 50, add to db
# if '-t50a' or '-a' in sys.argv:
#     information = cur.execute('''SELECT uri, id, name FROM Artist WHERE t_50 = 1''').fetchall()
#     obj.getArtist10Songs(information)
#
# # Get features for top artist songs in database, 100 at a time
# if '-t50af' or '-a' in sys.argv:
#     information = cur.execute('''SELECT uri FROM Track WHERE t_50 IS NULL''').fetchall()
#     uris = [x[0] for x in information]
#     chunks_uri = [uris[x:x+100] for x in range(0, len(uris), 100)]
#     for chunk in chunks_uri:
#         obj.features(chunk, sid=2)
#
# obj.close()
# cur.close()
# conn.close()
