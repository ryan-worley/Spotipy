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
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
import pdb
from collections import OrderedDict
import math
import statistics
import time
import warnings
warnings.filterwarnings("ignore")


class scalePanda():
    def __init__(self, dbuser, dbrec):
        self.dbuser = dbuser
        self.dbrec = dbrec
        self.conn_user = sqlite3.connect(self.dbuser)
        self.cur_user = self.conn_user.cursor()
        self.conn_rec = sqlite3.connect(self.dbrec)
        self.cur_rec = self.conn_rec.cursor()
        self.user_df = pd.read_sql_query('''SELECT * FROM Features JOIN Track ON Features.song_id = Track.id 
                                          WHERE Track.t_50 = 1''', self.conn_user)
        self.user_df.drop_duplicates(['name'], inplace=True)
        self.rec_df = pd.read_sql_query('''SELECT * FROM Features''', self.conn_rec)
        self.user_id = self.user_df.loc[:, ['artist_id', 'song_id', 'uri', 'name']]
        self.rec_id = self.rec_df.loc[:, ['artist_id', 'song_id', 'album_id']]

    def remove_nan(self, user, rec):
        user.fillna(0, inplace=True)
        rec.fillna(0, inplace=True)
        return user, rec

    def remove_id(self):
        drop_rec = ['artist_id', 'song_id', 'album_id', 'uri', 'sid', 'length', 'key']
        drop_user = ['artist_id', 'song_id', 'uri', 'sid', 'key', 'name']
        return self.user_df.drop(drop_user, axis=1), self.rec_df.drop(drop_rec, axis=1)
        # Get rid of Nan to 0's in Dataframe

    def scaleLoudness(self, user_df, rec_df):
        user_df.loc[:, 'loudness'] = np.log10(-user_df.loc[:, 'loudness']) / 1.3
        rec_df.loc[:, 'loudness'] = np.log10(-rec_df.loc[:, 'loudness']) / 1.3
        return user_df, rec_df

    def scaleTempo(self, user_df, rec_df):
        user_df.loc[:, 'tempo'] = (user_df.loc[:, 'tempo'] - 40) / 180
        rec_df.loc[:, 'tempo'] = (rec_df.loc[:, 'tempo'] - 40) / 180
        return user_df, rec_df

    def makeLike(self, user_df, rec_df):
        add = pd.Series([0] * len(rec_df.index))
        for col in list(user_df.columns.values):
            if col not in list(rec_df.columns.values):
                rec_df.loc[:, col] = add

        add = pd.Series([0] * len(user_df.index))
        for col in list(rec_df.columns.values):
            if col not in list(user_df.columns.values):
                user_df.loc[:, col] = add
        user_df.sort_index(axis=1, inplace=True)
        rec_df.sort_index(axis=1, inplace=True)
        return user_df, rec_df

    def prep(self):
        user, rec = self.remove_id()
        user, rec = self.scaleLoudness(user, rec)
        user, rec = self.scaleTempo(user, rec)
        user, rec = self.makeLike(user, rec)
        user, rec = self.remove_nan(user, rec)
        return user, rec


def fetchAdditionalData(sp, user, rec):
    u_name = sp.cur_user.execute('''SELECT Track.name FROM Track INNER JOIN Features 
                                        ON Track.id = Features.song_id WHERE t_50 = 1''').fetchall()
    u_name = [x[0] for x in u_name]
    u_name = list(OrderedDict.fromkeys(u_name))

    r_name = sp.cur_rec.execute('''SELECT Track.name FROM Track INNER JOIN Features 
                                    ON Track.id = Features.song_id''').fetchall()
    r_name = [x[0] for x in r_name]
    r_album = sp.cur_rec.execute('''SELECT Album.name FROM Album INNER JOIN Features 
                                    ON Album.id = Features.album_id''').fetchall()
    r_artist = sp.cur_rec.execute('''SELECT Artist.name FROM Artist INNER JOIN Features 
                                    ON Artist.id = Features.artist_id''').fetchall()
    r_artist = [x[0] for x in r_artist]
    r_album = [x[0] for x in r_album]
    user_array = user.values
    rec_array = rec.values
    sim = cosine_similarity(rec_array, user_array)
    sim = pd.DataFrame(data=sim, index=list(r_name), columns=list(u_name))
    sim.to_csv('foo.csv')
    return u_name, r_name, r_album, r_artist, sim

class groupData():
    def __init__(self, sim, albums, artist):
        self.sim = sim
        self.albums = albums
        self.artists = artist
        self.num_songs = len(self.albums)
        self.rec_songs = list(self.sim.index)

    def top_sim(self):
        score = []
        i = 0
        for name, song in self.sim.iterrows():
            np_song = song.values
            max_5 = np_song[np.argpartition(np_song, -6)[-6:]]
            avg = np.average(max_5)
            score.append(avg)
            i += 1
        return score

    def ind_song(self, score):
        song_score = [[self.albums[i], self.rec_songs[i], self.artists[i], val] for i, val in enumerate(score)]
        song_score.sort(key=lambda x: x[3], reverse=True)
        TOP_SONGS = []
        artist_track = []
        i = 0
        while True:
            if song_score[i][2] not in artist_track:
                TOP_SONGS.append(song_score[i])
                artist_track.append(song_score[i][2])
            i += 1
            if len(TOP_SONGS) == 10:
                break
        return song_score, TOP_SONGS

    def alb_single_song(self, song_score):
        song_score.sort()
        scores = []
        num_songs = 0
        current_album = song_score[0][0]
        current_artist = song_score[0][2]
        log = []
        albums = []

        for album, song, artist, val in song_score:
            if album == current_album:
                scores.append([album, song, artist, val])
                num_songs += 1
            else:
                # Create Analysis for albums, albums that are more than 3 songs
                if num_songs > 3:
                    # Round songs divided by 1.8 rounded down
                    avg_index = int(num_songs//1.8)
                    scores.sort(key=lambda x: x[3], reverse=True)
                    top_scores = scores[:avg_index]
                    a_val = statistics.mean([x[3] for x in top_scores])
                    summary = [[x[1] for x in top_scores], current_artist, a_val, 0, 'album']
                    albums.append(current_album)
                # Do Analysis for singles, albums that are 3 or less songs
                else:
                    scores.sort(key=lambda x: x[3], reverse=True)
                    s_val = statistics.mean([x[3] for x in scores])
                    summary = [[x[1] for x in scores], current_artist, s_val, 0, 'single']
                    albums.append(current_album)
                log.append(summary)
                current_artist = artist
                current_album = album
                num_songs = 1
                scores = [[album, song, artist, val]]
        return albums, log

    def runAll(self):
        scores = self.top_sim()
        song_score, TOP_SONGS = self.ind_song(scores)
        albums, df = self.alb_single_song(song_score)
        df = pd.DataFrame(df, columns=['Songs_for_songs', 'Artist', 'song_score', 'artist_score', 'category'], index=albums)
        df.sort_values('song_score', ascending=False, inplace=True)
        df.to_csv('check.csv')
        return df, scores

class analyzeResults():
    def __init__(self, df, scores, gd):
        self.df = df
        self.scores = scores
        self.gd = gd
        self.single = self.df[self.df.loc[:, 'category'] == 'single'].sort_values('song_score', ascending=False)
        self.album = self.df[self.df.loc[:, 'category'] == 'album'].sort_values('song_score', ascending=False)

    def singles(self, num):
        top = self.single.iloc[0:num, :]

        print()
        print('Top {} Singles for You:'.format(num))

        i = 1
        for index, row in top.iterrows():
            print('{}. {} by {}'.format(int(i), index, row['Artist']))
            i += 1
        return top

    def albums(self, num):
        top = self.album.iloc[0:num, :]
        print()
        print('Top {} albums for You:'.format(num))
        i = 1
        for index, row in top.iterrows():
            print('{}. {} by {}'.format(int(i), index, row['Artist']))
            i += 1
        return top

    def songs(self,):
        _, TOP_SONGS = self.gd.ind_song(self.scores)
        print()
        print('Top Songs for You:')
        for i, song in enumerate(TOP_SONGS):
            print('{}. {} by {} from the new album/single {}'.format(i+1, song[1], song[2], song[0]))
        return TOP_SONGS

def main():
    sp = scalePanda('Spotify.sqlite', 'Spotify_compare.sqlite')
    start = time.time()
    print('Prepping for analysis...')
    user, rec = sp.prep()
    u_name, r_name, r_album, r_artist, sim = fetchAdditionalData(sp, user, rec)
    gd = groupData(sim, r_album, r_artist)
    print('Running analysis...')
    df, scores = gd.runAll()
    print('Comparative analysis over, took {} seconds. Results being generated for display...'.format(time.time()-start))
    anal = analyzeResults(df, scores, gd)
    anal.singles(num=5)
    anal.albums(num=5)
    anal.songs()

if __name__ == '__main__':
    main()