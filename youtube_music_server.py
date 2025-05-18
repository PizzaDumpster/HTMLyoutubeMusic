#!/usr/bin/env python3
"""
Simple WebSocket Server for YouTube Music OBS Integration

This server sends song information to connected WebSocket clients
and can be used as a simpler alternative to the C++ version.
"""

import asyncio
import json
import websockets
import time
import logging
import signal
import sys
import socket
import argparse
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Global variables
connected_clients = set()
current_song_info = {
    "title": "No song playing",
    "author": "",
    "videoId": "",
    "playlist": [],
    "currentIndex": -1
}

# Default volume setting
current_volume = 100

# Real playlist (empty by default)
playlist = []

async def register(websocket):
    """Register a new client connection."""
    global current_volume
    
    connected_clients.add(websocket)
    logger.info(f"New client connected. Total clients: {len(connected_clients)}")
    
    # Send current song info to the new client with proper format
    await websocket.send(json.dumps({
        "command": "nowPlaying",
        "params": current_song_info
    }))
    
    # Send current volume setting
    await websocket.send(json.dumps({
        "command": "volumeUpdate",
        "value": current_volume
    }))

async def unregister(websocket):
    """Unregister a disconnected client."""
    connected_clients.remove(websocket)
    logger.info(f"Client disconnected. Remaining clients: {len(connected_clients)}")

def extract_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    import re
    
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

async def get_video_info(video_id):
    """Get video information from YouTube Video ID.
    
    This is a simplified version that doesn't actually fetch from YouTube API.
    In a real implementation, you would call the YouTube API to get actual metadata.
    """
    # Return placeholder data - in a real implementation, you'd get this from YouTube API
    return {
        "title": f"Video {video_id}",
        "author": "Unknown Artist",
        "id": video_id
    }

async def ws_handler(websocket, path=""):
    """Handle WebSocket connections.
    
    Args:
        websocket: The WebSocket connection
        path: The request path (required by websockets library)
    """
    global current_song_info, playlist, current_volume
    
    # Register new client
    await register(websocket)
    
    try:
        # Process incoming messages
        async for message in websocket:
            try:
                data = json.loads(message)
                command = data.get("command")
                
                if command:
                    logger.info(f"Received command: {command}")
                    
                    # Handle song info - special handling for nowPlaying command
                    if command == "nowPlaying" and "params" in data:
                        song_params = data["params"]
                        if "title" in song_params and "author" in song_params:
                            # Update the current song info
                            current_song_info = {
                                "title": song_params["title"],
                                "author": song_params["author"],
                                "videoId": song_params.get("videoId", ""),
                                "playlist": song_params.get("playlist", []),
                                "currentIndex": song_params.get("currentIndex", -1)
                            }
                            # Broadcast updated song info to all clients
                            await broadcast_song_info(current_song_info)
                            logger.info(f"Updated song info: {song_params['title']} by {song_params['author']}")
                    
                    # Handle playback controls
                    elif command == "play":
                        # Logic for play would go here
                        logger.info("Play command received")
                    elif command == "pause":
                        # Logic for pause would go here
                        logger.info("Pause command received")
                    elif command == "next":
                        # Move to next song
                        if playlist and len(playlist) > 0:
                            current_index = current_song_info.get("currentIndex", -1)
                            current_index = (current_index + 1) % len(playlist)
                            current_song_info = {
                                "title": playlist[current_index]["title"],
                                "author": playlist[current_index]["author"],
                                "videoId": playlist[current_index]["id"],
                                "playlist": playlist,
                                "currentIndex": current_index
                            }
                            await broadcast_song_info(current_song_info)
                    elif command == "previous":
                        # Move to previous song
                        if playlist and len(playlist) > 0:
                            current_index = current_song_info.get("currentIndex", -1)
                            current_index = (current_index - 1) % len(playlist)
                            current_song_info = {
                                "title": playlist[current_index]["title"],
                                "author": playlist[current_index]["author"],
                                "videoId": playlist[current_index]["id"],
                                "playlist": playlist,
                                "currentIndex": current_index
                            }
                            await broadcast_song_info(current_song_info)
                    
                    # Handle adding videos to playlist
                    elif command == "addVideo" and "url" in data:
                        video_id = extract_video_id(data["url"])
                        if video_id:
                            # If video info is provided directly, use it
                            if "info" in data:
                                video_info = data["info"]
                            else:
                                # Otherwise get video info (title, author)
                                video_info = await get_video_info(video_id)
                            
                            # Add to playlist
                            playlist.append(video_info)
                            
                            # If this is the first song, start playing it
                            if len(playlist) == 1:
                                current_song_info = {
                                    "title": video_info["title"],
                                    "author": video_info["author"],
                                    "videoId": video_info["id"],
                                    "playlist": playlist,
                                    "currentIndex": 0
                                }
                            else:
                                # Otherwise just update the playlist in the current info
                                current_song_info["playlist"] = playlist
                            
                            # Broadcast the updated playlist to all clients
                            await broadcast_song_info(current_song_info)
                            logger.info(f"Added video {video_id} to playlist")
                        else:
                            logger.warning(f"Invalid YouTube URL: {data['url']}")
                    
                    # Handle loading a specific video from playlist
                    elif command == "loadVideo" and "index" in data:
                        index = int(data["index"])
                        if 0 <= index < len(playlist):
                            current_song_info = {
                                "title": playlist[index]["title"],
                                "author": playlist[index]["author"],
                                "videoId": playlist[index]["id"],
                                "playlist": playlist,
                                "currentIndex": index
                            }
                            await broadcast_song_info(current_song_info)
                            logger.info(f"Loaded video at index {index}")
                    
                    # Handle volume control
                    elif command == "volume" and "value" in data:
                        volume = int(data["value"])
                        if 0 <= volume <= 100:
                            current_volume = volume
                            # In a real implementation, you might control actual system volume
                            logger.info(f"Volume set to {volume}")
                            # You could broadcast this to all clients if needed
                    
                    # Handle request for current song info
                    elif command == "requestCurrentSongInfo":
                        logger.info("Client requested current song info")
                        # Send the current song info with proper command formatting
                        await websocket.send(json.dumps({
                            "command": "nowPlaying",
                            "params": current_song_info
                        }))
                        logger.info(f"Sent current song info to client: {current_song_info.get('title', 'No title')}")
                        
                    # Handle ping command to keep connections alive
                    elif command == "ping":
                        # Just log the ping and don't need to send a response
                        logger.debug("Received ping from client")
                            
            except json.JSONDecodeError:
                logger.warning(f"Received invalid JSON message: {message}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info("Connection closed")
    finally:
        # Unregister client on disconnect
        await unregister(websocket)

async def broadcast_song_info(song_info):
    """Send song info to all connected clients."""
    if not connected_clients:
        return
    
    # Format message in the expected structure
    formatted_message = {
        "command": "nowPlaying",
        "params": song_info
    }
    
    message = json.dumps(formatted_message)
    logger.info(f"Broadcasting: {message}")
    
    await asyncio.gather(
        *[client.send(message) for client in connected_clients]
    )
    logger.info(f"Sent song info to {len(connected_clients)} clients")

async def initialize_player():
    """Initialize the music player state.
    
    This function replaces the demo_player function and just sets up
    the initial state without continuously cycling through demo songs.
    """
    global current_song_info, playlist
    
    # If we have songs in the playlist, set the current song to the first one
    if playlist:
        current_song_info = {
            "title": playlist[0]["title"],
            "author": playlist[0]["author"],
            "videoId": playlist[0]["id"],
            "playlist": playlist,
            "currentIndex": 0
        }
        logger.info(f"Initialized with song: {playlist[0]['title']} by {playlist[0]['author']}")
    
    # Otherwise just keep the default "No song playing" state
    else:
        logger.info("Initialized with empty playlist")
    
    # Initial broadcast to all clients
    await broadcast_song_info(current_song_info)

def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('0.0.0.0', port))
            return False
        except socket.error:
            return True

def find_available_port(start_port=8765, max_attempts=10):
    """Find an available port starting from start_port."""
    port = start_port
    for _ in range(max_attempts):
        if not is_port_in_use(port):
            return port
        port += 1
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

async def main():
    """Main server function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='YouTube Music WebSocket Server')
    parser.add_argument('--port', type=int, default=8765, help='Port to bind the WebSocket server to')
    parser.add_argument('--auto-port', action='store_true', help='Automatically find an available port if default is in use')
    args = parser.parse_args()
    
    port = args.port
    
    # Check if port is in use
    if is_port_in_use(port):
        if args.auto_port:
            old_port = port
            port = find_available_port(port)
            logger.warning(f"Port {old_port} is in use, using port {port} instead")
        else:
            logger.error(f"Port {port} is already in use! Try:")
            logger.error(f"  1. Run './stop-server.sh' to stop existing servers")
            logger.error(f"  2. Run with --auto-port to automatically find an available port")
            logger.error(f"  3. Specify a different port with --port PORT")
            sys.exit(1)
    
    # Create a port file that UI can read
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.server_port'), 'w') as f:
        f.write(str(port))
    
    # Start WebSocket server
    try:
        server = await websockets.serve(ws_handler, "localhost", port)
        logger.info(f"WebSocket server started on ws://localhost:{port}")
    except Exception as e:
        logger.error(f"Failed to start WebSocket server: {e}")
        sys.exit(1)
    
    # Initialize the player (replaces demo_player)
    init_task = asyncio.create_task(initialize_player())
    
    # Set up graceful shutdown
    loop = asyncio.get_event_loop()
    
    def shutdown_handler(sig, frame):
        logger.info("Shutting down server...")
        if not init_task.done():
            init_task.cancel()
        server.close()
        loop.stop()
        
        # Clean up port file on shutdown
        try:
            port_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.server_port')
            if os.path.exists(port_file):
                os.remove(port_file)
        except:
            pass
    
    # Register shutdown handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, shutdown_handler)
    
    logger.info("Press Ctrl+C to exit")
    
    # Keep the server running
    await server.wait_closed()

if __name__ == "__main__":
    # Define port_file outside the try block so it's available in finally
    port_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.server_port')
    
    try:
        # Ensure clean exit by removing port file on shutdown
        try:
            if os.path.exists(port_file):
                os.remove(port_file)
        except:
            pass
            
        # Run the main async function
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    finally:
        # Clean up port file on exit
        try:
            if os.path.exists(port_file):
                os.remove(port_file)
        except:
            pass
