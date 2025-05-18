# YouTube Music Overlay for OBS

This is a simple HTML/CSS/JavaScript overlay that shows currently playing YouTube Music information in a scrolling marquee. It's designed to be added as a Browser Source in OBS Studio or similar streaming software.

## How It Works

This system consists of two parts:

### Option 1: JavaScript-only Version
1. **Main Player (`index.html`)** - Handles the actual music playback and sends song information
2. **Overlay (`overlay.html` or `overlay-white.html`)** - Displays song information without playing audio

### Option 2: C++ and JavaScript Version
1. **C++ Main Player** - Native application that handles music playback and sends information via WebSockets
2. **Overlay (`overlay.html` or `overlay-white.html`)** - Displays song information received from the C++ application

## Features

- Displays a scrolling marquee with "Now Playing" information from YouTube videos
- Main player handles actual audio playback while the overlay just displays information
- Customizable background for chroma keying
- Control panel that can be hidden during streaming
- Playlist management with local storage
- Can autostart a video using URL parameters
- Volume control from both the main player and overlay
- Communication between main player and overlay via BroadcastChannel API

## Setup Instructions

You can choose either the JavaScript-only version or the C++ version:

### JavaScript-Only Version

#### Step 1: Start the Main Player
1. Open `index.html` in your browser (Chrome recommended)
2. This will be your control center for playing music
3. Add videos to your playlist and control playback from here

### C++ Version

#### Step 1: Build the C++ Sender
1. See the instructions in the `cpp-sender/README.md` file
2. Build and run the C++ application
3. Use this native app to play YouTube videos and control playback

### Step 2: Set Up the Overlay in OBS (Both Versions)
1. In OBS Studio, add a new "Browser" source to your scene
2. Check "Local file" and browse to either:
   - `overlay.html` (green background for chroma keying)
   - `overlay-white.html` (white background for chroma keying)
3. Set Width and Height to match your desired overlay size (e.g., 800x60)
4. Add a chroma key filter to the browser source:
   - Right-click the browser source
   - Select "Filters"
   - Add a "Chroma Key" filter
   - Select the appropriate key color (Green or White)
   - Adjust the settings for smoothness, similarity, etc.

### Important Notes

#### For JavaScript-Only Version
- Both the main player (index.html) and overlay must be open simultaneously
- They must be running on the same computer (same browser origin)
- Communication happens via the BroadcastChannel API

#### For C++ Version
- The C++ application and overlay must be running on the same computer
- Communication happens via WebSockets on port 8765
- Make sure the port is not blocked by a firewall

#### For Both Versions
- The main player (JavaScript or C++) handles the actual audio playback
- The overlay only displays information and doesn't play audio
- Controls on either the main player or overlay will control playback

## Controls

The control panel is hidden by default, but can be toggled:
- Press the gear icon in the bottom right corner
- Press the 'C' key on your keyboard

From the control panel you can:
- Add YouTube videos to your playlist
- Navigate between videos
- Play/pause the current video

## URL Parameters

You can use the following URL parameters:
- `?autostart=true` - Automatically starts playing without showing controls
- `?video=VIDEO_ID` - Specifies a YouTube video ID to play immediately
- `?autostart=true&video=VIDEO_ID` - Combines both options

Example:
```
overlay.html?autostart=true&video=dQw4w9WgXcQ
```

## Customizing

You can edit the CSS in `overlay.css` to change:
- Text size and color
- Background opacity
- Marquee animation speed
- Overall appearance

## Browser Compatibility

This overlay works best in Google Chrome, which is also what OBS Browser Source uses by default.
