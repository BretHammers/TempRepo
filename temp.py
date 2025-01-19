# Configuration file for TmMch

# GPIO Pin Definitions
class PinConfig:
    ENCODER_PINS = {
        'month': (17, 18),
        'day': (22, 23),
        'year': (24, 25)
    }
    SELECT = 27
    PLAY_PAUSE = 19
    FF = 20
    REW = 21

# LCD Configuration
LCD_I2C_ADDR = 0x27
LCD_COLS = 20
LCD_ROWS = 4

# Debounce Times (in milliseconds)
BUTTON_DEBOUNCE_TIME = 300
ENCODER_DEBOUNCE_TIME = 100

# API Configuration
ARCHIVE_API_URL = "https://archive.org/advancedsearch.php"
ARCHIVE_METADATA_URL = "https://archive.org/metadata"
MAX_API_RETRIES = 3
API_TIMEOUT = 10

# Database Configuration
DATABASE_FILE = "music_cache.db"

# Logging Configuration
LOG_FILE = "time_machine.log"

import os
import sqlite3
import requests
import vlc
from datetime import datetime, timedelta
import threading
import time
from internetarchive import search_items, get_item, download

from config import PinConfig, LCD_I2C_ADDR, LCD_COLS, LCD_ROWS, BUTTON_DEBOUNCE_TIME, ENCODER_DEBOUNCE_TIME, \
    ARCHIVE_API_URL, ARCHIVE_METADATA_URL, MAX_API_RETRIES, API_TIMEOUT, DATABASE_FILE, LOG_FILE


class MusicDownloader:
    def __init__(self):
        self.conn = self.setup_database()
        self.player = None

    ### SETUP ###
    def setup_database(self):
        """Initialize SQLite database to cache downloaded files."""
        conn = sqlite3.connect(DATABASE_FILE)
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS songs (
                    id INTEGER PRIMARY KEY,
                    identifier TEXT UNIQUE,
                    title TEXT,
                    artist TEXT,
                    date TEXT,
                    file_path TEXT
                )
            ''')
        return conn

    ### SEARCH AND DOWNLOAD ###
    def search_and_download(self, artist, date, file_format="mp3"):
        """
        Search for songs by artist and date on the Internet Archive and download them.

        Args:
            artist (str): Artist name (e.g., "GratefulDead" or "Phish").
            date (str): Date of the show in YYYY-MM-DD format.
            file_format (str): Preferred audio file format (default is "mp3").
        """
        # Check if the songs are already cached in the database
        cached_songs = self.get_cached_songs(artist, date)
        if cached_songs:
            print(f"Found {len(cached_songs)} cached songs. Skipping download.")
            return cached_songs

        # Search for items on the Internet Archive
        query = f"collection:{artist} AND date:{date}"
        print(f"Searching for {artist} shows on {date}...")
        results = list(search_items(query))

        if not results:
            print("No results found.")
            return []

        item_id = results[0]['identifier']
        print(f"Found item: {item_id}")

        # Get item metadata and filter files by format
        item = get_item(item_id)
        audio_files = [
            file['name'] for file in item.files 
            if file['format'].lower() == file_format.lower()
        ]

        if not audio_files:
            print(f"No '{file_format}' files found for this show.")
            return []

        # Download files
        print(f"Downloading {len(audio_files)} '{file_format}' files...")
        download(item_id, files=audio_files, destdir=DOWNLOAD_DIR, verbose=True)

        # Cache downloaded songs in the database
        downloaded_songs = []
        for file_name in audio_files:
            file_path = os.path.join(DOWNLOAD_DIR, item_id, file_name)
            self.cache_song(item_id, artist, date, file_name, file_path)
            downloaded_songs.append(file_path)

        print("Download complete.")
        return downloaded_songs

    ### DATABASE OPERATIONS ###
    def get_cached_songs(self, artist, date):
        """Retrieve cached songs from the database."""
        with self.conn:
            cursor = self.conn.execute(
                "SELECT file_path FROM songs WHERE artist=? AND date=?",
                (artist, date)
            )
            return [row[0] for row in cursor.fetchall()]

    def cache_song(self, identifier, artist, date, title, file_path):
        """Cache song metadata in the database."""
        with self.conn:
            self.conn.execute('''
                INSERT OR IGNORE INTO songs (identifier, artist, date, title, file_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (identifier, artist, date, title, file_path))

    ### PLAYBACK ###
    def play_song(self, file_path):
        """Play a song using VLC."""
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return

        if self.player:
            self.player.stop()

        print(f"Playing: {file_path}")
        self.player = vlc.MediaPlayer(file_path)
        self.player.play()

    def stop_playback(self):
        """Stop playback."""
        if self.player:
            self.player.stop()
            print("Playback stopped.")

    ### UTILITY ###
    def list_cached_shows(self):
        """List all cached shows in the database."""
        with self.conn:
            cursor = self.conn.execute(
                "SELECT DISTINCT artist, date FROM songs ORDER BY artist, date"
            )
            shows = cursor.fetchall()

        if not shows:
            print("No cached shows found.")

        for artist, date in shows:
            print(f"{artist} - {date}")

    def cleanup(self):
        """Clean up resources."""
        if self.conn:
            self.conn.close()


### MAIN FUNCTIONALITY ###
if __name__ == "__main__":
    downloader = MusicDownloader()

    try:
        # Example usage: Download and play Grateful Dead show from 1972-09-03
        artist_name = "GratefulDead"
        show_date = "1972-09-03"

        # Search and download songs
        downloaded_files = downloader.search_and_download(artist_name, show_date)

        # List cached shows
        downloader.list_cached_shows()

        # Play the first downloaded song
        if downloaded_files:
            downloader.play_song(downloaded_files[0])

    except KeyboardInterrupt:
        print("\nExiting...")

    finally:
        downloader.cleanup()

