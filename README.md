# YouTube Music Player

A desktop YouTube music player with a Tkinter UI, playlist management, VLC-based playback, and a WebSocket overlay for streamers.

---

## Features

- **Add individual YouTube URLs or playlists**
- **Play, pause, stop, next, previous controls**
- **Playlist management (add, remove, save, load)**
- **VLC-powered audio playback**
- **Overlay support:** Sends "now playing" info to a browser overlay via WebSocket
- **Google API integration** (requires your own API key)

---

## Requirements

- Python 3.8+
- [VLC media player](https://www.videolan.org/vlc/) (must be installed and in PATH)
- Python packages:
  - `python-vlc`
  - `yt-dlp`
  - `websockets`
  - `google-api-python-client`
  - `tkinter` (usually included with Python)
- A valid YouTube Data API key in `api_key.txt`

Install dependencies with:
```bash
pip install python-vlc yt-dlp websockets google-api-python-client
```

---

## Setup

1. **Clone or download this repository.**
2. **Install VLC** on your system.
3. **Add your YouTube Data API key** to `api_key.txt` (replace `API_KEY_HERE`).
4. **(Optional) Edit `saved_playlist.json`** to pre-load a playlist.

---

## Usage

### Run the Music Player UI

```bash
python youtube_music_ui.py
```

- Use the UI to add YouTube URLs or playlists.
- Control playback with the provided buttons.
- The playlist is saved automatically on exit.

### Overlay for Streaming

- Open `overlay.html` in your streaming software (e.g., OBS) as a browser source.
- The overlay will show the current song info, synced via WebSocket.

### WebSocket Server

- The UI starts the WebSocket server automatically.
- The overlay connects to `ws://localhost:8765` by default.

---

## Packaging as an EXE (Windows)

You can bundle the app as a standalone `.exe` using [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole youtube_music_ui.py
```
- The executable will be in the `dist` folder.
- Copy `api_key.txt`, `saved_playlist.json`, and any overlay files to the same folder as the `.exe`.

---

## Troubleshooting

- **VLC not found:** Ensure VLC is installed and accessible in your system PATH.
- **API errors:** Make sure your API key is valid and not over quota.
- **Overlay not updating:** Check that the WebSocket server is running and not blocked by a firewall.

---

## License

MIT License

---

## Credits

- [python-vlc](https://github.com/oaubert/python-vlc)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [Google API Python Client](https://github.com/googleapis/google-api-python-client)