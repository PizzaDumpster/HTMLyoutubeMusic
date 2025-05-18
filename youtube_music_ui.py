#!/usr/bin/env python3
"""
YouTube Music Player UI

A simple Tkinter interface to control the WebSocket server
and play YouTube videos directly in the Python application.
"""

import asyncio
import json
import websockets
import re
import tkinter as tk
from tkinter import ttk, messagebox, Scale
import threading
import time
import subprocess
import sys
import os
import socket
import vlc
import yt_dlp
import urllib.request
import urllib.parse
import urllib.error
import traceback
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from tkinter import TclError

# Global variables
websocket_client = None
current_playlist = []
current_index = -1
ws_server_process = None

# Audio player variables
player = None  # type: ignore
media = None
is_playing = False
current_volume = 80  # Default volume (0-100)

# YouTube API variables
youtube_api_key = None
use_api = False

# Shutdown state
is_shutting_down = False  # Flag to track application shutdown state

# Try to load YouTube API key if available
try:
    api_key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_key.txt")
    if os.path.exists(api_key_path):
        with open(api_key_path, 'r') as f:
            youtube_api_key = f.read().strip()
            use_api = len(youtube_api_key) > 0
except Exception as e:
    print(f"Error loading API key: {e}")
    youtube_api_key = None
    use_api = False

def safe_ui_call(func, fallback=None):
    """Safely call a UI function, handling cases where UI elements aren't initialized yet"""
    try:
        return func()
    except (NameError, AttributeError, TclError) as e:
        print(f"UI not ready: {e}")
        if fallback:
            return fallback()
        return None
    except Exception as e:
        print(f"Error in UI operation: {e}")
        if fallback:
            return fallback()
        return None

def safe_get_global(var_name):
    """Safely get a global variable, returning None if it doesn't exist"""
    try:
        return globals().get(var_name)
    except:
        return None

def safe_set_status(message):
    """Safely set the status message, handling the case where the status_var isn't defined yet"""
    try:
        status_var = safe_get_global('status_var')
        if status_var:
            status_var.set(message)
        else:
            print(f"Status: {message}")
    except Exception as e:
        print(f"Status: {message} (error: {e})")

def safe_update_ui():
    """Safely update the UI, handling the case where root isn't defined yet"""
    try:
        root = safe_get_global('root')
        if root:
            root.update_idletasks()
    except Exception:
        pass

def safe_after(delay, func):
    """Safely schedule a function to run after a delay, handling the case where root isn't defined yet"""
    try:
        root = safe_get_global('root')
        if root:
            return root.after(delay, func)
        else:
            # Just run the function directly if root isn't available
            func()
    except Exception:
        # Just run the function directly if there's an error
        func()

def extract_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    if not url:
        return None
        
    # Check if it's already just an ID (11 characters)
    if len(url) == 11 and re.match(r'^[A-Za-z0-9_-]{11}$', url):
        return url
        
    # Extract from YouTube URL
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})',
        r'youtube\.com/embed/([A-Za-z0-9_-]{11})',
        r'youtube\.com/v/([A-Za-z0-9_-]{11})',
        r'youtube\.com/(?:.*?)#(?:.*?)v=([A-Za-z0-9_-]{11})',
        r'youtube\.com/watch\?(?:.*?)v=([A-Za-z0-9_-]{11})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def extract_playlist_id(url):
    """Extract YouTube playlist ID from various URL formats."""
    if not url:
        return None
        
    # Check if it's already just an ID (starts with PL, UU, LL, etc.)
    if re.match(r'^(PL|UU|LL|FL|RD|OL)[A-Za-z0-9_-]{16,32}$', url):
        return url
        
    # Extract from YouTube URL
    patterns = [
        r'youtube\.com/playlist\?list=([A-Za-z0-9_-]{16,})',  # Standard playlist URL
        r'youtube\.com/watch\?.*?list=([A-Za-z0-9_-]{16,})',  # Video within playlist
        r'youtu\.be/.*?[\?\&]list=([A-Za-z0-9_-]{16,})'       # Shortened URL with playlist
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None

def get_audio_stream_url(video_id):
    """Get the best audio stream URL from YouTube using yt-dlp."""
    if not video_id:
        return None
    
    try:
        # Set up yt-dlp options to extract audio only with enhanced anti-bot detection
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            # Use a more realistic user agent
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
            # Simulate browser cookies
            'cookiefile': None,
        }
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if not info:
                print(f"Could not extract info for video {video_id}")
                return None
                
            if 'url' in info:
                return info['url']
            elif 'formats' in info and info['formats']:
                # Get the best audio format
                for f in info['formats']:
                    if f.get('acodec') != 'none':
                        return f['url']
            
            print(f"No suitable audio formats found for video {video_id}")
            return None
    except yt_dlp.utils.YoutubeDLError as e:
        if "Sign in to confirm you're not a bot" in str(e):
            print(f"YouTube bot detection triggered: {e}")
            print("Try using the application less frequently or use another video ID")
        else:
            print(f"Error getting audio stream URL: {e}")
        return None
    except Exception as e:
        print(f"Error getting audio stream URL: {e}")
        return None

def get_video_info_from_youtube(video_id):
    """Get video information from YouTube Video ID."""
    if not video_id:
        return None
    
    try:
        # Set up yt-dlp options with additional options to avoid getting blocked
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'skip_download': True,
            'nocheckcertificate': True,
            'ignoreerrors': True,
            # Add a randomized user agent to avoid detection
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
        }
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info:
                return {
                    "title": info.get('title', f"Video {video_id}"),
                    "author": info.get('uploader', "Unknown Artist"),
                    "id": video_id
                }
            else:
                # Fallback if info is None
                print(f"Could not get info for video {video_id}, using placeholder")
                return {
                    "title": f"Video {video_id}",
                    "author": "Unknown Artist",
                    "id": video_id
                }
    except Exception as e:
        print(f"Error getting video info: {e}")
        # Create a fallback entry anyway so the video can still be played
        return {
            "title": f"Video {video_id}",
            "author": "Unknown Artist",
            "id": video_id
        }

def get_video_info_from_api(video_id):
    """Get video information from YouTube Data API v3."""
    if not youtube_api_key or not video_id:
        return None
    
    try:
        # Import is already at the top of the file
        # from googleapiclient.discovery import build
        # from googleapiclient.errors import HttpError
        
        # Create a YouTube API service object
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        
        # Call the API to get video details
        response = youtube.videos().list(
            part='snippet',
            id=video_id
        ).execute()
        
        # Check if we got a valid response with items
        if 'items' in response and len(response['items']) > 0:
            snippet = response['items'][0]['snippet']
            return {
                "title": snippet['title'],
                "author": snippet['channelTitle'],
                "id": video_id
            }
        else:
            print(f"No video found with ID: {video_id}")
            return None
    except ImportError:
        print("Google API client not installed. Run 'pip install google-api-python-client'")
        return None
    except HttpError as e:
        print(f"YouTube API error: {e}")
        if "quota" in str(e).lower():
            print("YouTube API quota exceeded. Try again later or use yt-dlp method.")
            # Could display a message here about quota limits if desired
        return None
    except Exception as e:
        print(f"Error using YouTube API: {e}")
        return None

def get_playlist_videos_from_youtube(playlist_id):
    """Get video IDs from a YouTube playlist using yt-dlp."""
    if not playlist_id:
        return []
    
    try:
        print(f"Fetching playlist videos for playlist ID: {playlist_id}")
        # Configure yt-dlp options to extract playlist info
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,  # Don't download videos, just get info
            'skip_download': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            'dump_single_json': True,
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',
        }
        
        url = f"https://www.youtube.com/playlist?list={playlist_id}"
        
        videos = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            playlist_info = ydl.extract_info(url, download=False)
            
            if playlist_info and 'entries' in playlist_info:
                # Process each video entry in the playlist
                count = 0
                total_entries = len(playlist_info['entries'])
                print(f"Found {total_entries} videos in playlist")
                
                for entry in playlist_info['entries']:
                    count += 1
                    if entry:
                        # Extract basic info and create a video entry
                        video_id = entry.get('id')
                        if video_id:
                            videos.append({
                                "id": video_id,
                                "title": entry.get('title', f"Video {video_id}"),
                                "author": entry.get('uploader', "Unknown Artist")
                            })
                            if count % 5 == 0:  # Update status every 5 videos
                                status_text = f"Processing playlist: {count}/{total_entries} videos"
                                print(status_text)
                                # Note: root.after call removed to avoid undefined reference
        
        print(f"Successfully extracted {len(videos)} videos from playlist")
        return videos
    except Exception as e:
        print(f"Error getting playlist videos: {e}")
        return []
        
def get_playlist_videos_from_api(playlist_id):
    """Get videos from a YouTube playlist using YouTube Data API v3."""
    if not youtube_api_key or not playlist_id:
        return []
    
    try:
        from googleapiclient.discovery import build
        # Import is already at the top of the file
        # from googleapiclient.errors import HttpError
        
        # Create a YouTube API service object
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
        
        videos = []
        next_page_token = None
        
        # Get playlist items (max 50 per request, need to use pagination for large playlists)
        while True:
            # Request playlist items
            request = youtube.playlistItems().list(
                part="snippet,contentDetails",
                maxResults=50,
                playlistId=playlist_id,
                pageToken=next_page_token if next_page_token else ""
            )
            response = request.execute()
            
            # Process items
            for item in response.get('items', []):
                video_id = item['contentDetails']['videoId']
                title = item['snippet']['title']
                author = item['snippet']['videoOwnerChannelTitle'] if 'videoOwnerChannelTitle' in item['snippet'] else "Unknown Artist"
                
                videos.append({
                    "id": video_id,
                    "title": title,
                    "author": author
                })
                
                # Update status every 10 videos
                if len(videos) % 10 == 0:
                    status_text = f"Processing playlist: {len(videos)} videos so far..."
                    print(status_text)
                    # Note: root.after call removed to avoid undefined reference
            
            # Check if there are more pages
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        print(f"API: Found {len(videos)} videos in playlist {playlist_id}")
        return videos
            
    except ImportError:
        print("Google API client not installed. Run 'pip install google-api-python-client'")
        return []
    except HttpError as e:
        print(f"YouTube API error fetching playlist: {e}")
        if "quota" in str(e).lower():
            print("API quota exceeded. Please try again later or use the yt-dlp fallback method.")
        return []
    except Exception as e:
        print(f"Error using YouTube API for playlist: {e}")
        return []

def add_playlist_videos():
    """Add all videos from a YouTube playlist to the current playlist."""
    try:
        # Get URL safely
        url = ""
        url_entry = safe_get_global('url_entry')
        if url_entry:
            try:
                url = url_entry.get().strip()
            except Exception:
                pass
        
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube playlist URL or ID.")
            return
        
        playlist_id = extract_playlist_id(url)
        if not playlist_id:
            # Check if it's a regular video - offer to add it instead
            video_id = extract_video_id(url)
            if video_id:
                if messagebox.askyesno("Not a Playlist", 
                                    "This URL appears to be a single video, not a playlist.\n\nDo you want to add it as a single video instead?"):
                    # Use our utility function
                    add_url_to_playlist()
                return
            else:
                messagebox.showerror("Error", "Could not extract valid YouTube playlist ID.")
                return
        
        # Show confirmation dialog with options
        confirm = messagebox.askyesnocancel("Add Playlist", 
                                          "This will add all videos from the playlist to your current queue.\n\n"
                                          "Would you like to:\n"
                                          "- Yes: Keep current playlist and append new videos\n"
                                          "- No: Clear current playlist and add only the new videos\n"
                                          "- Cancel: Don't add any videos")
        
        if confirm is None:  # User clicked Cancel
            return
        
        # Clear the existing playlist if requested
        if confirm is False:  # User clicked No
            current_playlist.clear()
            current_index = -1
        
        # Show loading indicator
        safe_set_status("Fetching playlist info...")
        safe_update_ui()
        
        # Start a thread to fetch playlist info and add to playlist
        threading.Thread(target=fetch_and_add_playlist_thread, args=(playlist_id,), daemon=True).start()
    except Exception as e:
        print(f"Error in add_playlist_videos: {e}")
        traceback.print_exc()

def fetch_and_add_playlist_thread(playlist_id):
    """Thread function to fetch playlist videos and add them to the playlist."""
    try:
        # First try to get information from the YouTube Data API if available
        videos = []
        api_error = None
        
        if use_api and youtube_api_key:
            try:
                safe_after(0, lambda: safe_set_status("Fetching playlist info from YouTube API..."))
                videos = get_playlist_videos_from_api(playlist_id)
            except Exception as api_e:
                api_error = str(api_e)
                print(f"API error for playlist: {api_e}")
        
        # Fall back to yt-dlp if API didn't work or isn't available
        if not videos:
            if api_error:
                safe_after(0, lambda: safe_set_status("API failed, trying fallback method..."))
            else:
                safe_after(0, lambda: safe_set_status("Fetching playlist info..."))
                
            videos = get_playlist_videos_from_youtube(playlist_id)
        
        if videos:
            # Add to local playlist
            global current_playlist, current_index
            initial_playlist_length = len(current_playlist)
            
            # Add each video to the playlist
            for video in videos:
                current_playlist.append(video)
            
            # If this is the first song, set it as current
            if initial_playlist_length == 0 and videos:
                current_index = 0
                
            # Update UI in the main thread
            safe_after(0, update_playlist_display)
            safe_after(0, lambda: safe_set_status(f"Added {len(videos)} videos from playlist"))
            
            # Clear the URL entry if it exists
            def clear_url_entry():
                entry = safe_get_global('url_entry')
                if entry:
                    try:
                        entry.delete(0, tk.END)
                    except Exception:
                        pass
            safe_after(0, clear_url_entry)
            
            # Send to websocket clients
            if 'send_command' in globals():
                try:
                    send_command("updatePlaylist", {"playlist": current_playlist, "currentIndex": current_index})
                except Exception as e:
                    print(f"Error sending command: {e}")
            
            
            # Show completion message
            safe_after(0, lambda: messagebox.showinfo(
                "Playlist Added", 
                f"Successfully added {len(videos)} videos from the playlist."
            ))
        else:
            safe_after(0, lambda: messagebox.showerror("Error", "Failed to fetch playlist information."))
            safe_after(0, lambda: safe_set_status("Failed to add playlist"))
    except Exception as e:
        print(f"Error in fetch_and_add_playlist_thread: {e}")
        safe_after(0, lambda: messagebox.showerror("Error", f"Failed to add playlist: {e}"))
        safe_after(0, lambda: safe_set_status("Error"))

def add_url_to_playlist():
    """Add a URL to the playlist - simplified function to handle missing reference"""
    try:
        url = ""
        url_entry = safe_get_global('url_entry')
        if url_entry:
            try:
                url = url_entry.get().strip()
            except Exception:
                pass
                
        if not url:
            return
            
        video_id = extract_video_id(url)
        if not video_id:
            messagebox.showerror("Error", "Could not extract YouTube video ID.")
            return
            
        # Get video info - first try API, then fallback to yt-dlp
        video_info = None
        if use_api and youtube_api_key:
            video_info = get_video_info_from_api(video_id)
            
        if not video_info:
            video_info = get_video_info_from_youtube(video_id)
            
        if not video_info:
            # Create a minimal entry if all else fails
            video_info = {
                "id": video_id,
                "title": f"Video {video_id}",
                "author": "Unknown"
            }
            
        # Add to playlist
        global current_playlist, current_index
        current_playlist.append(video_info)
        
        # If this is the first song, set it as current
        if len(current_playlist) == 1:
            current_index = 0
            
        # Update UI
        update_playlist_display()
        
        # Clear URL entry - get it again to be safe
        entry = safe_get_global('url_entry')
        if entry:
            try:
                entry.delete(0, tk.END)
            except Exception:
                pass
            

        
        # Send to websocket clients if the function is available
        send_cmd = safe_get_global('send_command')
        if send_cmd:
            try:
                send_cmd("updatePlaylist", {"playlist": current_playlist, "currentIndex": current_index})
            except Exception as e:
                print(f"Error sending command: {e}")
                
        return True
    except Exception as e:
        print(f"Error adding URL to playlist: {e}")
        traceback.print_exc()
        return False

def send_command(command, data=None):
    """Send a command to connected WebSocket clients.
    
    This function tries to send a command to the WebSocket server,
    which will then relay it to all connected clients.
    """
    try:
        # Create a JSON message with proper command structure
        message = {
            "command": command,
            "params": data  # Put data in params field for consistent format
        }
        
        # Convert to JSON string
        json_message = json.dumps(message)
        
        print(f"Sending message: {json_message}")  # Debug output
        
        # Use asyncio to send the message over WebSocket
        async def send_ws_message():
            try:
                # Connect to the WebSocket server (default port 8765)
                uri = "ws://localhost:8765"
                # Remove 'timeout' argument for compatibility
                async with websockets.connect(uri) as websocket:
                    await websocket.send(json_message)
                    print(f"Successfully sent command: {command}")
                    return True
            except (ConnectionRefusedError, websockets.exceptions.ConnectionClosedError) as e:
                print(f"WebSocket connection error: {e}")
                safe_set_status("WebSocket server not connected")
                return False
            except Exception as e:
                print(f"Error sending WebSocket command: {e}")
                return False
        
        # Run the async function in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(send_ws_message())
        loop.close()
        
        return success
    except Exception as e:
        print(f"Error in send_command: {e}")
        return False

def update_song_info():
    """Send the current song information to WebSocket clients."""
    global current_index, current_playlist
    
    if current_playlist and 0 <= current_index < len(current_playlist):
        song_info = {
            "title": current_playlist[current_index].get("title", "Unknown Title"),
            "author": current_playlist[current_index].get("author", "Unknown Artist"),
            "videoId": current_playlist[current_index].get("id", "")
        }
        print(f"Updating song info: {song_info['title']} by {song_info['author']}")
        if 'send_command' in globals():
            try:
                max_attempts = 5
                for attempt in range(1, max_attempts + 1):
                    success = send_command("nowPlaying", song_info)
                    if success:
                        break
                    else:
                        print(f"Attempt {attempt} to send song info failed, retrying...")
                        time.sleep(0.5)
                else:
                    print("[ERROR] Could not send song info to WebSocket server after multiple attempts.")
            except Exception as e:
                print(f"Error sending command: {e}")
       
    else:
        # Send a 'no song' message
        song_info = {
            "title": "No song playing",
            "author": "",
            "videoId": ""
        }
        if 'send_command' in globals():
            send_command("nowPlaying", song_info)
       

def save_playlist_to_file():
    """Save playlist to a local file."""
    global current_playlist, current_index
    
    try:
        playlist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_playlist.json")
        data = {
            "playlist": current_playlist,
            "currentIndex": current_index
        }
        
        with open(playlist_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        print(f"Playlist saved to {playlist_file}")
    except Exception as e:
        print(f"Error saving playlist to file: {e}")

def load_playlist_from_file():
    """Load playlist from a local file on startup."""
    global current_playlist, current_index
    try:
        playlist_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_playlist.json")
        if os.path.exists(playlist_file):
            with open(playlist_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                current_playlist = data.get("playlist", [])
                current_index = data.get("currentIndex", -1)
            print(f"Loaded playlist from {playlist_file}")
        else:
            current_playlist = []
            current_index = -1
    except Exception as e:
        print(f"Error loading playlist: {e}")
        current_playlist = []
        current_index = -1

def update_playlist_display():
    """Update the playlist in the UI."""
    # This function needs to be defined globally so it can be referenced
    # by other functions before the UI is created
    global current_playlist, current_index
    
    # Only update if the playlist_listbox has been created
    playlist_listbox = safe_get_global('playlist_listbox')
    if playlist_listbox and hasattr(playlist_listbox, 'delete'):
        try:
            playlist_listbox.delete(0, tk.END)
            
            for i, item in enumerate(current_playlist):
                title = item.get("title", "Unknown Title")
                author = item.get("author", "Unknown Artist")
                display_text = f"{title} - {author}"
                
                # Highlight the current track
                if i == current_index:
                    display_text = f"▶ {display_text}"
                    
                playlist_listbox.insert(tk.END, display_text)
        except Exception as e:
            print(f"Error updating playlist display: {e}")
    else:
        print("Warning: playlist_listbox not available yet, skipping UI update")

def init_app():
    # Load playlist FIRST
    load_playlist_from_file()
    # ...then initialize UI and other logic
    update_playlist_display()
    update_ui_playback_state()
    update_song_info()

# Call this function after the UI has been initialized
# The following is a hook that might be called by code we can't see
# so we'll define it in case it's used elsewhere

def remove_selected():
    """Remove the selected item from the playlist."""
    global current_playlist, current_index
    
    try:
        # Get the selected item from the playlist
        playlist_listbox = safe_get_global('playlist_listbox')
        if not playlist_listbox:
            return
            
        # Get selected indices
        selection = playlist_listbox.curselection()
        if not selection:
            safe_set_status("No item selected")
            return
            
        # Get the selected index
        selected_index = selection[0]
        
        # Remove from playlist
        if 0 <= selected_index < len(current_playlist):
            # Get info about what we're removing
            removed_item = current_playlist[selected_index]
            title = removed_item.get("title", "Unknown")
            
            # Remove the item
            current_playlist.pop(selected_index)
            
            # Update current_index if needed
            if selected_index == current_index:
                # We removed the currently playing item
                stop_playback()  # Stop playback since this item is gone
                
                # If we still have items in the playlist, keep the same position unless it's out of bounds
                if current_playlist:
                    current_index = min(selected_index, len(current_playlist) - 1)
                else:
                    current_index = -1  # Reset if playlist is empty
            elif selected_index < current_index:
                # We removed an item before the current one, shift current index down
                current_index -= 1
            
            # Update the UI
            update_playlist_display()
            safe_set_status(f"Removed: {title}")
            
            # Send updated playlist to websocket clients
            send_command("updatePlaylist", {"playlist": current_playlist, "currentIndex": current_index})
            
            # Save the updated playlist
          
        
    except Exception as e:
        print(f"Error removing item from playlist: {e}")
        traceback.print_exc()


def on_app_loaded():
    """Called when the application is loaded."""
    # Schedule playlist loading to happen after UI is fully initialized
    safe_after(500, init_app)

# UI Functions
def play_current():
    print(f"[DEBUG] play_current called, current_index={current_index}, playlist length={len(current_playlist)}")
    global is_playing, player, media, current_volume

    if not current_playlist or current_index < 0 or current_index >= len(current_playlist):
        safe_set_status("No track selected")
        return

    try:
        # Get the current track info
        track = current_playlist[current_index]
        video_id = track.get("id")

        if not video_id:
            safe_set_status("Invalid track (no video ID)")
            return

        # Get audio stream URL
        safe_set_status(f"Getting audio for {track.get('title', 'Unknown')}...")
        audio_url = get_audio_stream_url(video_id)

        if not audio_url:
            safe_set_status("Could not get audio stream")
            return

        try:
            # Stop any existing playback
            if player:
                player.stop()
                # Remove previous event manager if any
                try:
                    event_manager = player.event_manager()
                    event_manager.event_detach(MEDIAPLAYER_ENDREACHED)
                except Exception:
                    pass

            # Create a new VLC instance if needed
            if player is None:
                vlc_instance = vlc.Instance('--no-xlib')
                if vlc_instance is None:
                    safe_set_status("VLC is not available. Please check your VLC installation.")
                    print("Error: vlc.Instance() returned None. VLC may not be installed or configured correctly.")
                    return
                player = vlc_instance.media_player_new()

            # Create a new media object from the audio URL
            media = vlc.Media(audio_url)

            # Set the media to the player
            player.set_media(media)

            # Set the volume
            player.audio_set_volume(current_volume)

            # --- FIX: Detach all previous handlers before attaching a new one ---
            try:
                event_manager = player.event_manager()
                event_manager.event_detach(MEDIAPLAYER_ENDREACHED)
            except Exception:
                pass

            # Attach event to play next song when current ends
            def on_song_end(event):
                print(f"[DEBUG] on_song_end called, current_index={current_index}")
                safe_set_status("Song ended, playing next track...")
                root = safe_get_global('root')
                if root:
                    root.after(0, play_next)
                else:
                    play_next()

            try:
                event_manager = player.event_manager()
                event_manager.event_attach(MEDIAPLAYER_ENDREACHED, on_song_end)
            except Exception as e:
                print(f"Error attaching end-of-song event: {e}")

            # Start playback
            player.play()

            # Update status
            title = track.get("title", "Unknown Title")
            author = track.get("author", "Unknown Artist")
            safe_set_status(f"Now playing: {title} - {author}")

            # Update UI state
            is_playing = True
            update_ui_playback_state()
            update_song_info()

            # Display success message
            safe_set_status(f"Playing: {title} - {author}")

        except Exception as e:
            safe_set_status(f"Error playing track: {e}")
            traceback.print_exc()
    except Exception as e:
        safe_set_status(f"Playback error: {e}")
        traceback.print_exc()

def toggle_play_pause():
    """Toggle between play and pause states."""
    global is_playing, player
    
    # If not playing, start playback
    if not is_playing:
        play_current()
        return
    else:
        # Pause the VLC player
        if player:
            player.pause()
            
        # Update display state
        is_playing = False
        safe_set_status("Playback paused")
        update_ui_playback_state()

def stop_playback():
    """Stop the current playback."""
    global is_playing, player
    
    # Stop the VLC player
    if player:
        player.stop()
    
    # Update state
    is_playing = False
    update_ui_playback_state()
    safe_set_status("Playback stopped")

def play_next():
    """Play the next track in the playlist."""
    global current_index, current_playlist
    
    if not current_playlist:
        return
        
    if current_index < len(current_playlist) - 1:
        current_index += 1
        update_playlist_display()
        play_current()
    else:
        safe_set_status("End of playlist")

def play_previous():
    """Play the previous track in the playlist."""
    global current_index
    
    if not current_playlist:
        return
        
    if current_index > 0:
        current_index -= 1
        update_playlist_display()
        play_current()
    else:
        safe_set_status("Start of playlist")

def update_ui_playback_state():
    """Update the UI elements to reflect the current playback state."""
    play_button = safe_get_global('play_button')
    pause_button = safe_get_global('pause_button')
    
    if is_playing:
        if play_button:
            play_button.config(state=tk.DISABLED)
        if pause_button:
            pause_button.config(state=tk.NORMAL)
    else:
        if play_button:
            play_button.config(state=tk.NORMAL)
        if pause_button:
            pause_button.config(state=tk.DISABLED)
    
    # Update now playing display
    update_now_playing_display()

def update_now_playing_display():
    """Update the 'Now Playing' text in the UI."""
    try:
        now_playing_var = safe_get_global('now_playing_var')
        if now_playing_var and current_playlist and 0 <= current_index < len(current_playlist):
            title = current_playlist[current_index].get("title", "Unknown Title")
            author = current_playlist[current_index].get("author", "Unknown Artist")
            now_playing_var.set(f"Now Playing: {title} - {author}")
        elif now_playing_var:
            now_playing_var.set("Not Playing")
    except Exception as e:
        print(f"Error updating now playing display: {e}")

def on_playlist_item_select(event):
    """Handle click on playlist item."""
    try:
        playlist_listbox = safe_get_global('playlist_listbox')
        if not playlist_listbox:
            return
            
        # Get the selected index
        selection = playlist_listbox.curselection()
        if not selection:
            return
            
        # Update current index and play
        global current_index
        current_index = selection[0]
        
        # Update display and play
        update_playlist_display()
        play_current()
        
    except Exception as e:
        print(f"Error in playlist selection: {e}")
        traceback.print_exc()

def set_volume(val):
    """Set the volume level."""
    global current_volume, player
    
    try:
        # Convert to int as the Scale returns a string
        volume = int(float(val))
        current_volume = volume
        
        # Update VLC player volume if it exists
        if player:
            player.audio_set_volume(volume)
            
        # Update volume label if it exists
        volume_label = safe_get_global('volume_label')
        if volume_label:
            volume_label.config(text=f"Volume: {volume}%")
            
        # Send updated volume to WebSocket server
        update_song_info()
        
        return True
    except Exception as e:
        print(f"Error setting volume: {e}")
        return False
                     

def start_websocket_server():
    """Start the WebSocket server in a separate process."""
    global ws_server_process
    
    try:
        # Check if server is already running
        if ws_server_process and ws_server_process.poll() is None:
            print("Server is already running")
            safe_set_status("WebSocket server already running")
            return
            
        # Get server script path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        server_script = os.path.join(script_dir, "youtube_music_server.py")
        
        # Start the server (no --host argument)
        if os.path.exists(server_script):
            ws_server_process = subprocess.Popen([sys.executable, server_script])
            
            # Check if process started successfully
            if ws_server_process.poll() is None:  # None means still running
                safe_set_status("WebSocket server started")
                print(f"Started server with PID: {ws_server_process.pid}")
                
                # Give the server a moment to initialize
                time.sleep(0.5)
                
                # Send current song information to the overlay
                update_song_info()
                
                # Set a timer to check server status after a few seconds
                root = safe_get_global('root')
                if root:
                    root.after(3000, check_server_status)
            else:
                safe_set_status("Failed to start WebSocket server")
                print("Server process exited immediately with code:", ws_server_process.returncode)
                ws_server_process = None
        else:
            safe_set_status("Server script not found")
            print(f"Server script not found: {server_script}")
    except Exception as e:
        safe_set_status(f"Error starting server: {str(e)}")
        print(f"Error starting WebSocket server: {e}")
        traceback.print_exc()
        
def check_server_status():
    """Check if WebSocket server is still running after initial startup."""
    global ws_server_process
    if ws_server_process:
        # Check if process is still running
        if ws_server_process.poll() is None:
            print("WebSocket server is running properly")
        else:
            print(f"WebSocket server exited with code {ws_server_process.returncode}")
            safe_set_status(f"WebSocket server crashed (code {ws_server_process.returncode})")
            ws_server_process = None

def stop_websocket_server():
    """Stop the WebSocket server."""
    global ws_server_process
    
    if ws_server_process:
        try:
            ws_server_process.terminate()
            ws_server_process.wait(timeout=5)
            safe_set_status("WebSocket server stopped")
        except Exception as e:
            print(f"Error stopping server: {e}")
            try:
                ws_server_process.kill()
                print("Server process killed")
            except Exception as kill_e:
                print(f"Error killing server process: {kill_e}")
        ws_server_process = None
    else:
        safe_set_status("WebSocket server is not running")


def on_window_close():
    """Handle window close event."""
    global is_shutting_down, player, media
    try:
        print("Application shutting down...")
        is_shutting_down = True
        stop_websocket_server()
        save_playlist_to_file()
        if player:
            player.stop()
            player.release()
        if media:
            media.release()
    except Exception as e:
        print(f"Error during shutdown: {e}")
        traceback.print_exc()
    finally:
        try:
            root = safe_get_global('root')
            if root:
                root.destroy()
        except Exception as e:
            print(f"Error destroying root window: {e}")

def create_ui():
    """Create the main UI."""
    global root, status_var, now_playing_var, url_entry, playlist_listbox
    
    # Create main window
    root = tk.Tk()
    root.title("YouTube Music Player")
    root.geometry("800x600")
    root.protocol("WM_DELETE_WINDOW", on_window_close)
    
    # Create top-level status and control variables
    status_var = tk.StringVar(value="Ready")
    now_playing_var = tk.StringVar(value="Not Playing")
    
    # Create main frame
    main_frame = ttk.Frame(root)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    # URL Input section
    url_frame = ttk.LabelFrame(main_frame, text="Add Music")
    url_frame.pack(fill=tk.X, padx=5, pady=5)
    
    url_input_frame = ttk.Frame(url_frame)
    url_input_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Label(url_input_frame, text="YouTube URL:").pack(side=tk.LEFT, padx=5)
    url_entry = ttk.Entry(url_input_frame)
    url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
    
    # Add URL/Playlist buttons
    url_buttons_frame = ttk.Frame(url_frame)
    url_buttons_frame.pack(fill=tk.X, padx=5, pady=5)
    
    add_url_button = ttk.Button(url_buttons_frame, text="Add URL", command=add_url_to_playlist)
    add_url_button.pack(side=tk.LEFT, padx=5)
    
    add_playlist_button = ttk.Button(url_buttons_frame, text="Add Playlist", command=add_playlist_videos)
    add_playlist_button.pack(side=tk.LEFT, padx=5)
    
    # Now Playing section
    now_playing_frame = ttk.LabelFrame(main_frame, text="Now Playing")
    now_playing_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Label(now_playing_frame, textvariable=now_playing_var, font=("", 10, "bold")).pack(padx=10, pady=10)
    
    # Playback controls section
    controls_frame = ttk.Frame(now_playing_frame)
    controls_frame.pack(fill=tk.X, pady=5)
    
    prev_button = ttk.Button(controls_frame, text="⏮︎", width=5, command=play_previous)
    play_button = ttk.Button(controls_frame, text="▶", width=5, command=play_current)
    pause_button = ttk.Button(controls_frame, text="⏸︎", width=5, command=toggle_play_pause)
    stop_button = ttk.Button(controls_frame, text="⏹︎", width=5, command=stop_playback)
    next_button = ttk.Button(controls_frame, text="⏭︎", width=5, command=play_next)
    
    prev_button.pack(side=tk.LEFT, padx=5)
    play_button.pack(side=tk.LEFT, padx=5)
    pause_button.pack(side=tk.LEFT, padx=5)
    stop_button.pack(side=tk.LEFT, padx=5)
    next_button.pack(side=tk.LEFT, padx=5)
    
    # Volume control
    volume_frame = ttk.Frame(now_playing_frame)
    volume_frame.pack(fill=tk.X, pady=5, padx=5)
    
    volume_label = ttk.Label(volume_frame, text=f"Volume: {current_volume}%")
    volume_label.pack(side=tk.LEFT, padx=5)
    
    volume_slider = Scale(volume_frame, from_=0, to=100, orient=tk.HORIZONTAL,
                          command=set_volume, length=200, showvalue=False)
    volume_slider.set(current_volume)
    volume_slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
    
    # WebSocket server controls
    server_frame = ttk.Frame(now_playing_frame)
    server_frame.pack(fill=tk.X, pady=5)
    
    start_server_button = ttk.Button(server_frame, text="Start WebSocket Server", command=start_websocket_server)
    start_server_button.pack(side=tk.LEFT, padx=5)
    
    stop_server_button = ttk.Button(server_frame, text="Stop WebSocket Server", command=stop_websocket_server)
    stop_server_button.pack(side=tk.LEFT, padx=5)
    
    # Playlist section
    playlist_frame = ttk.LabelFrame(main_frame, text="Playlist")
    playlist_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    # Create playlist controls frame
    playlist_controls_frame = ttk.Frame(playlist_frame)
    playlist_controls_frame.pack(fill=tk.X, pady=5, padx=5, side=tk.BOTTOM)
    
    # Add remove button
    remove_button = ttk.Button(playlist_controls_frame, text="Remove Selected", command=remove_selected)
    remove_button.pack(side=tk.LEFT, padx=5)
    
    # Add resync button to force websocket update
    resync_button = ttk.Button(
        playlist_controls_frame, 
        text="Resync Overlay", 
        command=update_song_info
    )
    resync_button.pack(side=tk.RIGHT, padx=5)
    
    # Create scrollable playlist listbox
    playlist_scroll = ttk.Scrollbar(playlist_frame)
    playlist_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    
    playlist_listbox = tk.Listbox(playlist_frame, yscrollcommand=playlist_scroll.set, font=("", 10))
    playlist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    playlist_listbox.bind('<<ListboxSelect>>', on_playlist_item_select)
    
    playlist_scroll.config(command=playlist_listbox.yview)
    
    # Status bar
    status_bar = ttk.Label(root, textvariable=status_var, relief=tk.SUNKEN, anchor=tk.W)
    status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    # Initial UI update
    update_ui_playback_state()
    
    # Register callback for when app is fully loaded
    root.after(100, on_app_loaded)
    
    return root

# Use the integer value for MediaPlayerEndReached event (265) as fallback
MEDIAPLAYER_ENDREACHED = getattr(getattr(vlc, 'EventType', None), 'MediaPlayerEndReached', 265)

# Main function
if __name__ == "__main__":
    try:
        # Start the WebSocket server first
        start_websocket_server()
        
        # Create the UI
        root = create_ui()
        
        # Make sure initial song info is sent if there's a song loaded
        root.after(1000, update_song_info)  # Give the server a second to start up
        
        root.mainloop()
    except Exception as e:
        print(f"Error starting application: {e}")
        traceback.print_exc()
