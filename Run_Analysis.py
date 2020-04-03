import warnings
warnings.filterwarnings("ignore")
import time
import sys
import Sp_Comparable
import Spotify
import Sp_Analysis
import Sp_Prep
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
import statistics
import warnings
warnings.filterwarnings("ignore")


def main():
    st = time.time()
    Spotify.main()
    Sp_Analysis.main()
    Sp_Comparable.main()
    Sp_Prep.main()
    print('Script Finished. Total time {} seconds'.format(time.time() - st))

if __name__ == '__main__':
    main()
