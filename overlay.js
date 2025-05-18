// Global variables
let player;
let currentVideoId = '';
let playlist = [];
let currentIndex = 0;
let controlsVisible = false;

// Initialize keyboard shortcut to toggle controls visibility
document.addEventListener('DOMContentLoaded', function() {
    // Create toggle button for controls
    const toggleButton = document.createElement('button');
    toggleButton.id = 'toggle-controls';
    toggleButton.innerHTML = '⚙️';
    toggleButton.title = 'Toggle Controls (Press C)';
    toggleButton.addEventListener('click', toggleControls);
    document.body.appendChild(toggleButton);

    // Add keyboard shortcut
    document.addEventListener('keydown', function(event) {
        // Toggle controls with 'c' key
        if (event.key === 'c' || event.key === 'C') {
            toggleControls();
        }
    });

    // Check URL params for autostart
    const urlParams = new URLSearchParams(window.location.search);
    const autostart = urlParams.get('autostart');
    if (autostart === 'true') {
        // Auto-hide controls if autostart is true
        toggleButton.style.display = 'none';
    }
});

// Toggle controls visibility
function toggleControls() {
    controlsVisible = !controlsVisible;
    if (controlsVisible) {
        document.body.classList.add('show-controls');
    } else {
        document.body.classList.remove('show-controls');
    }
}

// Initialize the YouTube Player API
function onYouTubeIframeAPIReady() {
    player = new YT.Player('youtube-player', {
        height: '120',  // Smaller size since it's hidden
        width: '200',
        videoId: '',
        playerVars: {
            'playsinline': 1,
            'controls': 0,
            'rel': 0,
            'mute': 0,  // Not muted by default to allow volume control
            'volume': 50 // Default volume at 50%
        },
        events: {
            'onReady': onPlayerReady,
            'onStateChange': onPlayerStateChange
        }
    });
}

// The API will call this function when the video player is ready
function onPlayerReady(event) {
    // Load saved playlist from local storage if available
    loadPlaylistFromStorage();
    
    // Add event listeners to buttons
    document.getElementById('play-button').addEventListener('click', function() {
        if (playlist.length > 0) {
            player.playVideo();
        }
    });
    
    document.getElementById('pause-button').addEventListener('click', function() {
        player.pauseVideo();
    });
    
    document.getElementById('prev-button').addEventListener('click', function() {
        playPreviousVideo();
    });
    
    document.getElementById('next-button').addEventListener('click', function() {
        playNextVideo();
    });
    
    document.getElementById('add-video').addEventListener('click', function() {
        addVideoToPlaylist();
    });
    
    // Volume control event listener
    const volumeSlider = document.getElementById('volume-slider');
    const volumeValue = document.getElementById('volume-value');
    
    // Set initial volume value from local storage or default
    const savedVolume = localStorage.getItem('youtubePlayerVolume');
    if (savedVolume !== null) {
        volumeSlider.value = savedVolume;
        volumeValue.textContent = savedVolume;
        player.setVolume(parseInt(savedVolume));
    } else {
        volumeSlider.value = 50;
        volumeValue.textContent = "50";
        player.setVolume(50);
    }
    
    // Update volume when slider is moved
    volumeSlider.addEventListener('input', function() {
        const volume = this.value;
        volumeValue.textContent = volume;
        player.setVolume(parseInt(volume));
        
        // Save volume setting to local storage
        localStorage.setItem('youtubePlayerVolume', volume);
        
        // Toggle mute state based on volume
        if (parseInt(volume) === 0) {
            player.mute();
        } else if (player.isMuted()) {
            player.unMute();
        }
    });

    // Check URL params for autostart
    const urlParams = new URLSearchParams(window.location.search);
    const autostart = urlParams.get('autostart');
    const videoId = urlParams.get('video');
    
    if (autostart === 'true' && videoId) {
        // Add the video to playlist and play it
        addVideoToPlaylistById(videoId);
    }
}

// The API calls this function when the player's state changes
function onPlayerStateChange(event) {
    // Get the current video data
    if (event.data == YT.PlayerState.PLAYING) {
        updateMarquee();
        
        // Check if the player is ready to get video data
        const interval = setInterval(function() {
            if (player && player.getPlayerState() === YT.PlayerState.PLAYING) {
                updateMarquee();
            } else {
                clearInterval(interval);
            }
        }, 3000); // Update every 3 seconds
    }
    
    // When video ends, play next video
    if (event.data == YT.PlayerState.ENDED) {
        playNextVideo();
    }
}

// Update the marquee with the current song info
function updateMarquee() {
    try {
        const videoData = player.getVideoData();
        const videoTitle = videoData.title || 'Unknown Title';
        const author = videoData.author || 'Unknown Artist';
        
        // Update the marquee text
        const marqueeText = `Now Playing: ${videoTitle} by ${author}`;
        document.getElementById('song-info').textContent = marqueeText;
        
        // Also update the current playlist item with the actual title and author
        if (playlist[currentIndex]) {
            playlist[currentIndex].title = videoTitle;
            playlist[currentIndex].author = author;
            
            // Update the playlist UI to show the updated info
            updatePlaylistUI();
            
            // Save the updated playlist to storage
            savePlaylistToStorage();
        }
        
        // Restart the animation
        const marqueeElement = document.getElementById('song-info');
        marqueeElement.style.animation = 'none';
        setTimeout(() => {
            marqueeElement.style.animation = 'marquee 15s linear infinite';
        }, 10);
    } catch (error) {
        console.error('Error updating marquee:', error);
    }
}

// Add a video to the playlist
function addVideoToPlaylist() {
    const input = document.getElementById('video-url');
    const url = input.value.trim();
    
    if (!url) return;
    
    // Extract video ID from URL or use as is if it's just an ID
    const videoId = extractVideoId(url);
    
    if (!videoId) {
        alert('Invalid YouTube URL or ID');
        return;
    }
    
    // Add video with temporary title that will be updated when played
    addToPlaylist(videoId, 'Loading...', 'Loading...');
    input.value = '';
    
    // If this is the first video, start playing it
    if (playlist.length === 1) {
        loadVideo(0);
    }
}

// Add video to playlist by ID (for autostart from URL)
function addVideoToPlaylistById(videoId) {
    addToPlaylist(videoId, 'Loading...', 'Loading...');
    
    // Start playing it immediately
    loadVideo(0);
}

// Extract YouTube video ID from various URL formats
function extractVideoId(url) {
    // Handle standard YouTube URL
    const regExp = /^.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/;
    const match = url.match(regExp);
    
    // If it's a standard YouTube URL
    if (match && match[2].length === 11) {
        return match[2];
    }
    
    // If it's just a YouTube ID (11 characters)
    if (url.length === 11) {
        return url;
    }
    
    return null;
}

// Add video to playlist with received details
function addToPlaylist(videoId, title, author) {
    playlist.push({
        id: videoId,
        title: title,
        author: author
    });
    
    // Update the playlist UI
    updatePlaylistUI();
    
    // Save playlist to local storage
    savePlaylistToStorage();
}

// Update the playlist display in the UI
function updatePlaylistUI() {
    const playlistElement = document.getElementById('playlist-items');
    playlistElement.innerHTML = '';
    
    playlist.forEach((video, index) => {
        const li = document.createElement('li');
        li.textContent = `${video.title} - ${video.author}`;
        
        if (index === currentIndex && player.getPlayerState() !== YT.PlayerState.ENDED) {
            li.classList.add('active');
        }
        
        li.addEventListener('click', function() {
            loadVideo(index);
        });
        
        playlistElement.appendChild(li);
    });
}

// Load a specific video from the playlist
function loadVideo(index) {
    if (index >= 0 && index < playlist.length) {
        currentIndex = index;
        currentVideoId = playlist[index].id;
        player.loadVideoById(currentVideoId);
        
        // Update UI
        updatePlaylistUI();
    }
}

// Play the next video in the playlist
function playNextVideo() {
    if (playlist.length === 0) return;
    
    currentIndex = (currentIndex + 1) % playlist.length;
    loadVideo(currentIndex);
}

// Play the previous video in the playlist
function playPreviousVideo() {
    if (playlist.length === 0) return;
    
    currentIndex = (currentIndex - 1 + playlist.length) % playlist.length;
    loadVideo(currentIndex);
}

// Save playlist to local storage
function savePlaylistToStorage() {
    localStorage.setItem('youtubePlaylist', JSON.stringify(playlist));
    localStorage.setItem('currentIndex', currentIndex.toString());
}

// Load playlist from local storage
function loadPlaylistFromStorage() {
    const savedPlaylist = localStorage.getItem('youtubePlaylist');
    const savedIndex = localStorage.getItem('currentIndex');
    const savedVolume = localStorage.getItem('youtubePlayerVolume');
    
    // Load volume settings if available
    if (savedVolume !== null) {
        const volumeSlider = document.getElementById('volume-slider');
        const volumeValue = document.getElementById('volume-value');
        
        if (volumeSlider && volumeValue) {
            volumeSlider.value = savedVolume;
            volumeValue.textContent = savedVolume;
            
            // Apply volume if player is ready
            if (player && player.setVolume) {
                player.setVolume(parseInt(savedVolume));
                
                // Set mute state based on volume
                if (parseInt(savedVolume) === 0) {
                    player.mute();
                } else {
                    player.unMute();
                }
            }
        }
    }
    
    if (savedPlaylist) {
        playlist = JSON.parse(savedPlaylist);
        currentIndex = savedIndex ? parseInt(savedIndex) : 0;
        
        // Update UI
        updatePlaylistUI();
        
        // Load the current video if available
        if (playlist.length > 0) {
            loadVideo(currentIndex);
        }
    }
}

// Handle video URL input with Enter key
document.addEventListener('DOMContentLoaded', function() {
    const input = document.getElementById('video-url');
    input.addEventListener('keypress', function(event) {
        if (event.key === 'Enter') {
            event.preventDefault();
            document.getElementById('add-video').click();
        }
    });
});
