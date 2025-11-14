async function fetchQueue() {
    try {
        const response = await fetch('/get_queue');
        const queue = await response.json();

        const queueElement = document.getElementById('queue');
        queueElement.innerHTML = '';

        if (queue.length === 0) {
            queueElement.innerHTML = '<p>No songs in the queue.</p>';
        } else {
            queue.forEach(song => {
                const songElement = document.createElement('div');
                songElement.innerHTML = `<strong>${song.title}</strong> by ${song.author}<br>Requested by: ${song.requesters.join(', ')}`;

                if (isAdmin) {
                    const deleteButton = document.createElement('button');
                    deleteButton.innerText = 'Delete';
                    deleteButton.onclick = () => deleteSong(song.song_id);
                    songElement.appendChild(deleteButton);
                }

                queueElement.appendChild(songElement);
            });
        }
    } catch (error) {
        console.error("Error fetching queue:", error);
    }
}

async function deleteAllSongs() {
    try {
        await fetch('/delete_all_requests', { method: 'DELETE' });
        fetchQueue();
    } catch (error) {
        console.error("Error deleting all songs:", error);
    }
}

async function deleteSong(songId) {
    try {
        await fetch(`/delete_song/${songId}`, { method: 'DELETE' });
        fetchQueue();
    } catch (error) {
        console.error(`Error deleting song with id ${songId}:`, error);
    }
}

async function updateMaxRequests() {
    const maxRequests = document.getElementById('max-requests').value;
    try {
        await fetch('/update_max_requests', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ max_requests: maxRequests })
        });
    } catch (error) {
        console.error("Error updating max requests:", error);
    }
}

const isAdmin = true;
if (isAdmin) {
    document.getElementById('admin-section').style.display = 'block';
}

fetchQueue();
setInterval(fetchQueue, 5000);

document.addEventListener('DOMContentLoaded', function() {
    const languageSelect = document.getElementById('languageSelect');
    const currentLanguage = localStorage.getItem('selectedLanguage') || 'en';
    languageSelect.value = currentLanguage;

    languageSelect.addEventListener('change', function() {
        const selectedLanguage = this.value;
        localStorage.setItem('selectedLanguage', selectedLanguage);
        window.location.href = `/change_language/${selectedLanguage}`;
    });
});

