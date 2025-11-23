// Global declaration
// Initialize globalUserName from localStorage if available
var globalUserName = localStorage.getItem('globalUserName') || '';  // Renaming to ensure no conflicts
var currentLanguage = "All";  // Initialize with default value
var currentLetter = "All";  // Initialize with default value
var requestListReloadInterval = 120000; // Interval in milliseconds (e.g., 60000ms = 1 minute)

// Retrieve the selected language from localStorage
const selectedLanguage = localStorage.getItem('selectedLanguage');
let userRequestedSongs = [];
let page = 1;
let messageDelay=4000;
 
document.addEventListener('DOMContentLoaded', function () {

    // Initializing elements and setting initial states
    const letterSelect = document.getElementById('letterSelect');
    const nameForm = document.getElementById('nameForm');
    const clearButton = document.getElementById('clearButton');
    const languageRadios = document.querySelectorAll('input[name="language"]');
    const editNameButton = document.getElementById('editNameButton');
    const languageSelect = document.getElementById('languageSelect');
    const errorContainer = document.getElementById('errorContainer');
    const songList = document.getElementById('song-list');

    // Set initial letter to 'All'
    letterSelect.value = 'All';
    currentLetter = 'All';  // Update global variable


    checkSession();



    // Check if globalUserName is set
    if (!globalUserName) {
        // Hide elements related to requesting songs
   
     // Optionally, hide the title name
        const titleNameElement = document.getElementById('welcome-name');
        if (titleNameElement) {
            titleNameElement.style.display = 'none';
        }


        const titleDiv = document.getElementById('title-div');
        if (titleDiv) {
            titleDiv.style.display = 'none';
        }
    }

    // Event listener for the letter dropdown
    letterSelect.addEventListener('change', function (event) {
        currentLetter = event.target.value;
        const sortBy = getCurrentSort(); // Fetch the current sort state
        const searchQuery = document.getElementById('searchBox').value.trim();
        const selectedSearchLanguage = getActiveLanguage(); // Get the currently active language

        // Determine the filter type based on the sort state
        let filterType = sortBy === 'author' ? 'author' : 'title';

        fetchSongs(searchQuery, selectedSearchLanguage, currentLetter, sortBy, 1);
    });

    // Sort by author or title buttons
    const sortByTitleBtn = document.getElementById('sortByTitleBtn');
    const sortByAuthorBtn = document.getElementById('sortByAuthorBtn');

    sortByTitleBtn.addEventListener('click', function () {
        sortSongs('title');
    });

    sortByAuthorBtn.addEventListener('click', function () {
        sortSongs('author');
    });

    // Initialize globalUserName with the content of userNameDisplay
    const userNameDisplay = document.getElementById('userNameDisplay');
    if (userNameDisplay && globalUserName) {
        userNameDisplay.textContent = `Welcome, ${globalUserName}!`;
    }

    // Add event listener to search button
    document.getElementById('searchButton').addEventListener('click', function () {
        const searchQuery = document.getElementById('searchBox').value.trim();
        const selectedSearchLanguage = getActiveLanguage(); // Get the currently active language
        const sortBy = getCurrentSort(); // Ensure this function fetches the current sort state
        fetchSongs(searchQuery, selectedSearchLanguage, currentLetter, sortBy, 1);
    });

    // Add event listeners to new language buttons
    document.getElementById('all-language-button').addEventListener('click', function () {
        setSearchLanguage('all');
    });
    document.getElementById('italian-language-button').addEventListener('click', function () {
        setSearchLanguage('it');
    });
    document.getElementById('english-language-button').addEventListener('click', function () {
        setSearchLanguage('en');
    });


    const titleButton = document.getElementById('sortByTitleBtn')
    titleButton.classList.add('language-button-selected');

    const welcomeTitle = document.getElementById('welcome-name')
    const welcomeText = translations.getAttribute('welcome');

    // Fetch venue name from the server and update the welcome message
    fetch('/get_venue_name')
        .then(response => response.json())
        .then(data => {
            const venueName = data.venue_name;
            welcomeTitle.textContent = `${welcomeText} ${venueName}, ${globalUserName}!`;
        })
        .catch(error => {
            console.error('Error fetching venue name:', error);
            welcomeTitle.textContent = `${welcomeText}, ${globalUserName}!`; // Fallback if there's an error
        });

    // menu management
    const hamburgerMenu = document.querySelector('#hamburgerMenu');
    const menu = document.querySelector('#menu');
    const searchBox = document.querySelector('#searchBox');
    const searchButton = document.querySelector('#searchButton');
    const menuItems = document.querySelectorAll('.menu-item');
    
    //setting up incremental search 
    if (searchBox) {
        searchBox.addEventListener('input', function () {
            searchSongs();
        });
    }
    // Function to update the selected language in the menu
    function updateSelectedLanguage(selectedLanguage) {
        menuItems.forEach(item => {
            if (item.getAttribute('data-lang') === selectedLanguage) {
                item.classList.add('selected');
            } else {
                item.classList.remove('selected');
            }
        });
    }

    // Function to change the UI language
    function changeUILanguage(language) {
        // Store the selected language in localStorage
        localStorage.setItem('selectedLanguage', language);

        // Update the language on the server side using AJAX
        fetch(`/change_language/${language}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ language: language })
        })
            .then(response => {
                if (response.ok) {
                    // Reload the current page to apply the new language
                    window.location.reload();
                } else {
                    console.error('Failed to change language on the server');
                }
            })
            .catch(error => {
                console.error('Error:', error);
            });
    }

    // Load the selected language from localStorage or default to browser language
    var userLang = navigator.language || navigator.userLanguage;
    userLang = userLang.substring(0, 2); // Get two-letter language code
    var selectedLanguage = localStorage.getItem('selectedLanguage') || userLang;
    if (!['en', 'it', 'es', 'de', 'fr'].includes(selectedLanguage)) {
        selectedLanguage = 'en'; // Default to English if not supported
    }
    updateSelectedLanguage(selectedLanguage);

    if (hamburgerMenu && menu) {
        hamburgerMenu.addEventListener('click', () => {
            menu.style.display = menu.style.display === 'block' ? 'none' : 'block';
        });
    }

    if (searchBox) {
        searchBox.addEventListener('keydown', function (event) {
            if (event.key === 'Enter') {
                event.preventDefault(); // Prevent the default form submission
                if (searchButton) {
                    searchButton.click(); // Trigger the search button click
                } else {
                    filterSongs(); // Call the search function directly if no button
                }
            }
        });
    }

    if (menuItems) {
        menuItems.forEach(item => {
            item.addEventListener('click', function (event) {
                const selectedLanguage = event.target.getAttribute('data-lang');
                updateSelectedLanguage(selectedLanguage);
                changeUILanguage(selectedLanguage);
            });
        });
    }


    const toggleButton = document.querySelector('.interface-hamburger-menu-color');

    toggleButton.addEventListener('click', (event) => {
        event.stopPropagation(); // Prevent the click from propagating to the document
        menu.classList.toggle('show');
    });

    document.addEventListener('click', (event) => {
        if (!menu.contains(event.target)) {
            menu.classList.remove('show');
        }
    });


    setSearchLanguage('all');  // This already calls fetchSongs, so no need to call it again below
    console.log("Selected Language:", selectedLanguage);

    // Fetch user requests
    console.log("Global User Name on DOMContentLoaded:", globalUserName);
    fetchUserRequests(globalUserName);

    
    // Initial load - REMOVED: setSearchLanguage already calls fetchSongs
    // fetchSongs('', 'all', 'All', 'title', 1); // Fetch the first page of songs with default parameters

    // Function to reload the request list
    function reloadRequestList() {
        fetchUserRequests(globalUserName);
    }

    // Set up the interval to reload the request list
        setInterval(reloadRequestList, requestListReloadInterval);


});

document.addEventListener('click', (event) => {
    const menu = document.querySelector('#menu');
    const hamburgerMenu = document.querySelector('#hamburgerMenu');
    if (menu && !menu.contains(event.target) && !hamburgerMenu.contains(event.target)) {
        menu.style.display = 'none';
    }
});

let isLoadingSongs = false;

const loadSongs = () => {
    if (isLoadingSongs) {
        console.log('Already loading songs, skipping...');
        return;
    }
    isLoadingSongs = true;
    const searchQuery = document.getElementById('searchBox').value.trim();
    const selectedSearchLanguage = getActiveLanguage();
    const sortBy = getCurrentSort();
    fetchSongs(searchQuery, selectedSearchLanguage, currentLetter, sortBy, page, true);
    page++;
    // Reset the flag after a short delay to allow the next load
    setTimeout(() => {
        isLoadingSongs = false;
    }, 500);
};

const handleScroll = () => {
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 500) {
        loadSongs();
    }
};
window.addEventListener('scroll', handleScroll);

function cacheUserRequests() {
    return new Promise((resolve, reject) => {
        if (!globalUserName) {
            console.log("No global user name provided, skipping fetch for user requests.");
            resolve(); // Resolve the promise even if there's no global user name
            return;
        }

        fetch('/get_user_requests')
            .then(response => response.json())
            .then(data => {
                console.log("User requests fetched successfully:", data);
                userRequestedSongs = data.map(song => song.song_id); // Ensure song_id is stored as a number
                resolve(); // Resolve the promise after fetching and processing the data
            })
            .catch(error => {
                console.error('Error fetching user requests:', error);
                reject(error); // Reject the promise if there's an error
            });
    });
}

function checkSession() {
    console.log('checkSession function called'); // Add this line for debugging

    if (!globalUserName) {
        console.log('No username provided, skipping session check.');
        // Hide elements related to requesting songs
        const requestElements = document.querySelectorAll('.request-element');
        requestElements.forEach(element => {
            element.style.display = 'none';
        });

        // Optionally, hide the title name
        const titleNameElement = document.getElementById('titleName');
        if (titleNameElement) {
            titleNameElement.style.display = 'none';
        }
        return;
    }

    fetch('/check_session')
        .then(response => response.json())
        .then(data => {
            console.log('Response from /check_session:', data); // Add this line for debugging
            if (data.redirect) {
                window.location.href = data.redirect;
            } else if (data.status === 'valid') {
                console.log('Session is valid');
            }
        })
        .catch(error => console.error('Error:', error));
}

function getActiveLanguage() {
    // Check which language button is active
    if (document.getElementById('italian-language-button').classList.contains('active-language-button')) {
        return 'it';
    } else if (document.getElementById('english-language-button').classList.contains('active-language-button')) {
        return 'en';
    } else {
        // Default to 'all' if no specific language button is active
        return 'all';
    }
}

function setSearchLanguage(language) {
    // Define all buttons
    const buttons = {
        'all': document.getElementById('all-language-button'),
        'it': document.getElementById('italian-language-button'),
        'en': document.getElementById('english-language-button')
    };

    // Reset all buttons to default style
    Object.values(buttons).forEach(button => {
        button.classList.remove('language-button-selected');
    });

    // Apply selected style to the active language button
    if (buttons[language]) {
        buttons[language].classList.add('language-button-selected');
    }
    const searchQuery = document.getElementById('searchBox').value.trim();
    const sortBy = getCurrentSort(); // Fetch the current sort state
    fetchSongs(searchQuery, language, currentLetter, sortBy, 1);
}

function sortSongs(sortBy, sortOrder = 'asc', event) {
    if (event) event.stopPropagation();

    const buttons = {
        'title': document.getElementById('sortByTitleBtn'),
        'author': document.getElementById('sortByAuthorBtn'),
        'popularity': document.getElementById('sortByPopularityDescBtn')
    };

    // Remove selected class from all buttons
    Object.values(buttons).forEach(button => {
        button.classList.remove('language-button-selected');
    });

    // Add selected class to the clicked button
    if (buttons[sortBy]) {
        buttons[sortBy].classList.add('language-button-selected');
    }

    // Fetch sorted songs from the server
    const searchQuery = document.getElementById('searchBox').value.trim();
    const selectedSearchLanguage = getActiveLanguage();
    fetchSongs(searchQuery, selectedSearchLanguage, currentLetter, sortBy, 1, false, sortOrder);
}

function submitName() {
    const userNameInput = document.getElementById('userName');
    globalUserName = userNameInput.value.trim();
    localStorage.setItem('globalUserName', globalUserName);  // Save to localStorage

    console.log("After assigning globalUserName:", typeof globalUserName, globalUserName);

    if (globalUserName) {
        const userNameDisplay = document.getElementById('userNameDisplay');
        userNameDisplay.textContent = `Welcome, ${globalUserName}!`;

        const nameForm = document.getElementById('nameForm');
        const userNameContainer = document.getElementById('userNameContainer');
        const editNameButton = document.getElementById('editNameButton');
        nameForm.style.display = 'none';
        userNameContainer.style.display = 'block';
        editNameButton.style.display = 'block';

        displayPlayButtons(true);
        filterSongs();
    } else {
        displayPlayButtons(false);
    }
}

function editName() {
    const nameForm = document.getElementById('nameForm');
    const userNameContainer = document.getElementById('userNameContainer');
    const editNameButton = document.getElementById('editNameButton');
    nameForm.style.display = 'block';
    userNameContainer.style.display = 'none';
    editNameButton.style.display = 'none';

    displayPlayButtons(false);
}

function displayPlayButtons(show) {
    const playButtons = document.querySelectorAll('.play-button');
    playButtons.forEach(button => {
        button.style.display = show ? 'block' : 'none';
    });
}

function clearSearch() {
    document.getElementById('searchBox').value = '';
    document.getElementById('letterSelect').value = 'All'; // Reset the dropdown to "All"
    currentLetter = 'All'; // Reset the letter filter
    const sortBy = getCurrentSort(); // Get current sort state
    const filteredBy = getCurrentLanguageFilter(); // Get current language filter
    fetchSongs('', filteredBy, 'All', sortBy, 1); // Fetch the first page of songs with the current sort state
}

function searchSongs() {
    const searchQuery = document.getElementById('searchBox').value.trim();
    const selectedSearchLanguage = getActiveLanguage(); // Get the currently active language
    const sortBy = getCurrentSort(); // Get current sort state
    fetchSongs(searchQuery, selectedSearchLanguage, currentLetter, sortBy, 1);
}


function resetFilters() {
    document.getElementById('all-language-button').classList.add('active-language-button');
    document.getElementById('italian-language-button').classList.remove('active-language-button');
    document.getElementById('english-language-button').classList.remove('active-language-button');

    document.getElementById('letterSelect').value = "All";
    currentLanguage = "All";
    currentLetter = "All";
}

function filterSongs(sortBy = 'title') {
    const searchQuery = document.getElementById('searchBox').value.trim();
    fetchSongs(searchQuery, getLanguageCode(currentLanguage), currentLetter, sortBy,1);
}

function getLanguageCode(language) {
    switch (language.toLowerCase()) {
        case 'english': return 'en';
        case 'italian': return 'it';
        case 'spanish': return 'es';
        case 'french': return 'fr';
        default: return 'all';
    }
}
function fetchSongs(query, language, letter, sortBy = 'title', page = 1, append = false, sortOrder = 'asc') {
    console.log("fetchSongs called with:", query, language, letter, sortBy, page, sortOrder);
    if (!append) {
        page = 1; // Reset pagination if not appending
    }
    const url = `/search_songs?s=${encodeURIComponent(query)}&language=${encodeURIComponent(language)}&letter=${encodeURIComponent(letter)}&sortBy=${encodeURIComponent(sortBy)}&sortOrder=${encodeURIComponent(sortOrder)}&page=${page}&username=${encodeURIComponent(globalUserName)}`;
    fetch(url)
        .then(response => {
            if (!response.ok) throw new Error(`Network response was not ok: ${response.statusText}`);
            return response.json();
        })
        .then(data => {
            updateSongList(data.songs, globalUserName, append);
            if (!append) {
                page = 2; // Reset to the next page for lazy loading
                // Don't auto-load next page - let user scroll to trigger it
            }
        })
        .catch(error => showMessage(error.message));
}


function fetchSongsOld(query, language, letter, sortBy = 'title', page = 1, append = false) {
    console.log("fetchSongs called with:", query, language, letter, sortBy, page);
    if (!append) {
        page = 1; // Reset pagination if not appending
    }
    const url = `/search_songs?s=${encodeURIComponent(query)}&language=${encodeURIComponent(language)}&letter=${encodeURIComponent(letter)}&sortBy=${encodeURIComponent(sortBy)}&page=${page}&username=${encodeURIComponent(globalUserName)}`;
    fetch(url)
        .then(response => {
            if (!response.ok) throw new Error(`Network response was not ok: ${response.statusText}`);
            return response.json();
        })
        .then(data => {
            updateSongList(data.songs, globalUserName, append);
            if (!append) {
                page = 2; // Reset to the next page for lazy loading
                loadSongs(); // Trigger lazy loading
            }
        })
        .catch(error => showMessage(error.message));
}


function fetchSongsOld3(query, language, letter, sortBy = 'title', page = 1, append = false) {
    console.log("fetchSongs called with:", query, language, letter, sortBy, page);
    const url = `/search_songs?s=${encodeURIComponent(query)}&language=${encodeURIComponent(language)}&letter=${encodeURIComponent(letter)}&sortBy=${encodeURIComponent(sortBy)}&page=${page}&username=${encodeURIComponent(globalUserName)}`;
    fetch(url)
        .then(response => {
            console.log("Response status:", response.status);  // Add logging
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            updateSongList(data.songs, globalUserName, append);
            if (!append) {
                page = 2; // Reset to the next page for lazy loading
                loadSongs(); // Trigger lazy loading
            }
        })
        .catch(error => {
            showMessage(error.message);
        });
}


function fetchSongsold2(query, language, letter, sortBy = 'title', page = 1, append = false) {
    console.log("fetchSongs called with:", query, language, letter, sortBy, page);
    const url = `/search_songs?s=${encodeURIComponent(query)}&language=${encodeURIComponent(language)}&letter=${encodeURIComponent(letter)}&sortBy=${encodeURIComponent(sortBy)}&page=${page}&username=${encodeURIComponent(globalUserName)}`;
    fetch(url)
        .then(response => {
            console.log("Response status:", response.status);  // Add logging
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            updateSongList(data.songs, globalUserName, append);
        })
        .catch(error => {
            showMessage(error.message);
        });
}

function fetchSongsOld(query, language, letter, sortBy = 'title', page = 1, append = false) {
    console.log("fetchSongs called with:", query, language, letter, sortBy, page);
    const url = `/search_songs?s=${encodeURIComponent(query)}&language=${encodeURIComponent(language)}&letter=${encodeURIComponent(letter)}&sortBy=${encodeURIComponent(sortBy)}&page=${page}&username=${encodeURIComponent(globalUserName)}`;
    fetch(url)
        .then(response => {
            console.log("Response status:", response.status);  // Add logging
            if (!response.ok) {
                throw new Error(`Network response was not ok: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            updateSongList(data.songs, globalUserName, append);
        })
        .catch(error => {
            showMessage(error.message);
        });
}


function updateSongList(songs, globalUserName, append = false) {
    cacheUserRequests().then(() => {
        const list = document.getElementById('song-list');
        if (!append) {
            list.innerHTML = '';
        }

        if (songs.length === 0 && !append) {
            const noSongsFound = translations.getAttribute('no-song');
            showMessage(noSongsFound);
            return;
        }

        songs.forEach(song => {
            const translations = document.getElementById('translations');
            const requestText = translations.getAttribute('song-request');

            const item = document.createElement('article');
            item.classList.add('song-container');

            const overlap = document.createElement('div');
            overlap.classList.add('overlap-group');
            item.appendChild(overlap);

            // Use centralized image utility
            const authorImage = createAuthorImage(song.image, `${song.author} Image`, null, 'author-image');

            const titleAuthor = document.createElement('div');
            titleAuthor.classList.add('title-author');

            const songTitle = document.createElement('div');
            songTitle.textContent = `${song.title}`;
            songTitle.classList.add('song-name');
            songTitle.classList.add('valign-text-middle');
            songTitle.classList.add('centurygothic-bold-cararra-18px');

            const songAuthor = document.createElement('div');
            songAuthor.textContent = `${song.author}`;
            songAuthor.classList.add('author-name');
            songAuthor.classList.add('valign-text-middle');
            songAuthor.classList.add('centurygothic-bold-regent-gray-13px');

            titleAuthor.appendChild(songTitle);
            titleAuthor.appendChild(songAuthor);

            overlap.appendChild(authorImage);
            overlap.appendChild(titleAuthor);

            const requestIcon = document.createElement('div');
            requestIcon.classList.add('song-add-icon');
            requestIcon.dataset.songId = song.id; // Ensure the data-song-id attribute is set
            overlap.appendChild(requestIcon);

            const isRequested = userRequestedSongs.includes(song.id);

            if (globalUserName && !isRequested) {
                item.dataset.songId = song.id;
                item.onclick = function () {
                    requestSong(song.id, globalUserName);
                };
            }

            if (isRequested) {
                requestIcon.style.display = 'none';
            }

            list.appendChild(item);
        });
    });
}

function updateSongListWorks(songs, globalUserName, append = false) {
    cacheUserRequests().then(() => {
        const list = document.getElementById('song-list');
        if (!append) {
            list.innerHTML = '';
        }

        if (songs.length === 0 && !append) {
            const noSongsFound = translations.getAttribute('no-song');
            showMessage(noSongsFound);
            return;
        }

        songs.forEach(song => {
            const translations = document.getElementById('translations');
            const requestText = translations.getAttribute('song-request');

            const item = document.createElement('article');
            item.classList.add('song-container');

            const overlap = document.createElement('div');
            overlap.classList.add('overlap-group');
            item.appendChild(overlap);

            // Use centralized image utility
            const authorImage = createAuthorImage(song.image, `${song.author} Image`, null, 'author-image');

            const titleAuthor = document.createElement('div');
            titleAuthor.classList.add('title-author');

            authorImage.appendChild(titleAuthor);

            const songTitle = document.createElement('div');
            songTitle.textContent = `${song.title}`;
            songTitle.classList.add('song-name');
            songTitle.classList.add('valign-text-middle');
            songTitle.classList.add('centurygothic-bold-cararra-18px');

            const songAuthor = document.createElement('div');
            songAuthor.textContent = `${song.author}`;
            songAuthor.classList.add('author-name');
            songAuthor.classList.add('valign-text-middle');
            songAuthor.classList.add('centurygothic-bold-regent-gray-13px');

            titleAuthor.appendChild(songTitle);
            titleAuthor.appendChild(songAuthor);

            overlap.appendChild(authorImage);
            overlap.appendChild(titleAuthor);

            const isRequested = userRequestedSongs.includes(song.id); // Ensure song_id is used

            if (globalUserName && !isRequested) {
                const requestIconOut = document.createElement('div');
                requestIconOut.classList.add('song-add-icon');

                const requestIconX = document.createElement('div');
                requestIconX.classList.add('x');

                // Set the dataset attribute to store the song ID
                requestIconOut.dataset.songId = song.id;

                // Attach the click event handler to the icon
                requestIconOut.onclick = function () {
                    const songId = this.dataset.songId;
                    requestSong(songId, globalUserName);
                };

                // Append the 'x' div to the icon container
                requestIconOut.appendChild(requestIconX);
                overlap.appendChild(requestIconOut);
            }

            list.appendChild(item);
        });
    });
}


function requestSong(songId, username) {
    const requestUrl = `/request_song/${songId}`;

    fetch(requestUrl, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            user: username
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.redirect) {
            // Redirect the browser to the URL provided by the server
            window.location.href = data.redirect;
        } else if (data.success) {
            // Remove the song from the list completely
            const songElement = document.querySelector(`[data-song-id="${songId}"]`)?.closest('.song-card, .song-item');
            if (songElement) {
                songElement.style.transition = 'opacity 0.3s ease-out';
                songElement.style.opacity = '0';
                setTimeout(() => {
                    songElement.remove();
                }, 300);
            }
            
            // Add the songId to userRequestedSongs to keep track
            userRequestedSongs.push(songId);

            // Reload the user requests
            fetchUserRequests(username);
            
            // Show success message
            showMessage(data.message || 'Song requested successfully!');
        } else {
            console.log(data.error || 'An error occurred while requesting the song.');
            showMessage(data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showMessage(error.message);
    });
}

function showMessage(message) {
    const messageDiv = document.querySelector('#user-messages');

    if (!messageDiv) {
        console.error('Message container not found');
        return;
    }

    messageDiv.textContent = message;
    messageDiv.style.display = 'block'; // Ensure the element is displayed

    // Force reflow to apply the display change
    messageDiv.offsetHeight;

    messageDiv.classList.add('show');
    messageDiv.style.maxHeight = messageDiv.scrollHeight + 'px'; // Set max-height to the scrollHeight

    setTimeout(() => {
        messageDiv.classList.remove('show');
        messageDiv.style.maxHeight = '0'; // Collapse the container
        setTimeout(() => {
            messageDiv.style.display = 'none';
        }, 500); // Wait for the transition to complete
    }, messageDelay); // Show for some seconds seconds
}




function updateRequestsListHeight(numItems) {
    var requestsList = document.getElementById('user-requests');
    if (requestsList) {
        // Calculate the potential new height based on the number of items
        var baseHeight = numItems > 0 ? 50 : 0; // 50px for the title if there are requests
        var childrenHeight = numItems * 50;
        var totalHeight = baseHeight + childrenHeight;

        // Ensure the new height does not exceed the maximum allowed height of 180px
        var newHeight = Math.min(totalHeight, 180);

        // Set the height to the new calculated height
        requestsList.style.height = newHeight + "px";
    }
}
// Function to fetch and display the user's requests
function fetchUserRequests(globalUserName) {
    if (!globalUserName) {
        console.log("No global user name provided, skipping fetch for user requests.");
        return;
    }

    fetch('/get_user_requests')
        .then(response => response.json())
        .then(data => {
            console.log("User requests fetched successfully:", data);

            const requestListTitle = translations.getAttribute('song-requests-title');

            const userRequestsDiv = document.getElementById('user-requests');
            userRequestsDiv.innerHTML = '';
            if (data.length > 0) {
                userRequestsDiv.innerHTML = '<h2 class="x-title">' + requestListTitle + '</h2>';  // Ensure the title is not overridden
            }

            data.forEach(song => {
                const translations = document.getElementById('translations');

                // Create the main container for the request
                const requestDiv = document.createElement('div');
                requestDiv.classList.add('request-div', 'request', 'screen');
                requestDiv.setAttribute('name', 'form1'); // Assuming 'form1' is static, adjust if dynamic
                requestDiv.id = `request-${song.song_id}`; // Assign a unique ID to each request

                // Create the vertical container for song details
                const songRequestsVertical = document.createElement('div');
                songRequestsVertical.classList.add('song-requests-vertical');

                // Create the container for author and song name
                const nameContainer = document.createElement('div');
                nameContainer.classList.add('name-container-request');

                // Create and append the author name element
                const authorName = document.createElement('div');
                authorName.classList.add('author-name-request', 'valign-text-middle');
                authorName.textContent = song.author;

                // Create and append the song name element
                const songName = document.createElement('div');
                songName.classList.add('song-name-request', 'valign-text-middle');
                songName.textContent = song.title;

                // Append author and song name to their container
                nameContainer.appendChild(authorName);
                nameContainer.appendChild(songName);

                // Append the name container to the vertical container
                songRequestsVertical.appendChild(nameContainer);

                // Check if there is a global username
                if (globalUserName) {
                    // Create the delete button as an anchor tag
                    const deleteLink = document.createElement('a');
                    deleteLink.href = "javascript:void(0)"; // Prevent default link behavior
                    deleteLink.classList.add('align-self-flex-center');

                    // Create the delete icon container
                    const removeRequestIcon = document.createElement('div');
                    removeRequestIcon.classList.add('remove-request-icon', 'request');

                    // Create the image element for the icon
                    const iconImage = document.createElement('img');
                    iconImage.classList.add('line-1');
                    iconImage.src = "/static/img/line-1.svg";
                    iconImage.alt = "Line 1";

                    // Append the image to the icon container
                    removeRequestIcon.appendChild(iconImage);

                    // Append the icon container to the link
                    deleteLink.appendChild(removeRequestIcon);

                    // Append the delete link to the vertical container
                    songRequestsVertical.appendChild(deleteLink);

                    // Attach the delete functionality
                    deleteLink.onclick = function () {
                        deleteRequest(song.song_id, globalUserName); // Ensure correct parameter is passed
                    };
                }

                // Append the vertical container to the main container
                requestDiv.appendChild(songRequestsVertical);

                // Append the main container to the user requests div
                userRequestsDiv.appendChild(requestDiv);
            });

            // Update the height of the requests list after rendering
            setTimeout(updateRequestsListHeight, 0);
            console.log("User requests rendered.");  // Debugging log
        })

        .catch(error => console.error('Error fetching user requests:', error));
}

function deleteRequest(songId, username) {
    fetch(`/delete_request/${songId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ user: username })
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to delete song');
            }
            return response.json();
        })
        .then(data => {
            console.log('Delete response data:', data); // Debugging log
            if (data.message === 'Song removed from queue successfully' || data.message === 'Song marked as played successfully') {
                // Re-fetch the user requests to re-render the list
                fetchUserRequests(username);
                // Re-fetch the songs to update the song list
                const searchQuery = document.getElementById('searchBox').value.trim();
                const selectedSearchLanguage = getActiveLanguage(); // Get the currently active language
                const sortBy = getCurrentSort(); // Get current sort state
                fetchSongs(searchQuery, selectedSearchLanguage, currentLetter, sortBy);
            } else {
                console.error('Error deleting request:', data.message);
                showMessage(data.message || 'Error removing request', 'error');
            }
        })
        .catch(error => {
            console.error('Error deleting request:', error);
        });
}




function getCurrentSort() {
    const sortByAuthorBtn = document.getElementById('sortByAuthorBtn');
    const sortByTitleBtn = document.getElementById('sortByTitleBtn');

    if (!sortByAuthorBtn || !sortByTitleBtn) {
        console.error('Sort buttons not found');
        return 'title'; // Default to 'title' if buttons are not found
    }

    if (sortByAuthorBtn.classList.contains('language-button-selected')) {
        return 'author';
    } else if (sortByTitleBtn.classList.contains('language-button-selected')) {
        return 'title';
    } else {
        return 'title'; // Default to title if neither button is active
    }
}

function getCurrentLanguageFilter() {
    const allLanguageButton = document.getElementById('all-language-button');
    const italianLanguageButton = document.getElementById('italian-language-button');
    const englishLanguageButton = document.getElementById('english-language-button');

    if (allLanguageButton.classList.contains('language-button-selected')) {
        return 'all';
    } else if (italianLanguageButton.classList.contains('language-button-selected')) {
        return 'it';
    } else if (englishLanguageButton.classList.contains('language-button-selected')) {
        return 'en';
    } else {
        return 'all';
    }
}

// ===== AUTO-REFRESH: Check if requested songs have been played =====
let lastRequestedSongIds = [];

function checkForPlayedSongs() {
    // Only poll if user is logged in
    if (!globalUserName) {
        return;
    }

    fetch('/api/user_requested_song_ids')
        .then(response => response.json())
        .then(data => {
            const currentRequestedIds = data.requested_song_ids || [];
            
            // On first load, just store the current state
            if (lastRequestedSongIds.length === 0) {
                lastRequestedSongIds = currentRequestedIds;
                return;
            }
            
            // Check if any songs were removed (played by artist)
            const songsRemoved = lastRequestedSongIds.filter(id => !currentRequestedIds.includes(id));
            
            if (songsRemoved.length > 0) {
                console.log(`🎵 ${songsRemoved.length} song(s) were played! Refreshing list...`);
                
                // Refresh the song list to show newly available songs
                const searchQuery = document.getElementById('searchBox')?.value.trim() || '';
                const selectedSearchLanguage = getActiveLanguage();
                const sortBy = getCurrentSort();
                fetchSongs(searchQuery, selectedSearchLanguage, currentLetter, sortBy, page);
                
                // ALSO refresh the user's request list to remove played songs
                fetchUserRequests(globalUserName);
                
                // Update the stored list
                lastRequestedSongIds = currentRequestedIds;
            } else {
                // Just update silently
                lastRequestedSongIds = currentRequestedIds;
            }
        })
        .catch(error => {
            console.error('Error checking for played songs:', error);
        });
}

// Start polling if user is logged in (interval configured in system settings)
document.addEventListener('DOMContentLoaded', function() {
    if (globalUserName) {
        // Get interval from window (set by template) or use default 30 seconds
        const refreshInterval = window.autoRefreshInterval || 30000;
        
        // Initial check after 5 seconds (give time for page to fully load)
        setTimeout(() => {
            checkForPlayedSongs();
        }, 5000);
        
        // Then check at configured interval
        setInterval(checkForPlayedSongs, refreshInterval);
        console.log(`✅ Auto-refresh enabled: checking for played songs every ${refreshInterval/1000} seconds`);
    }
});

