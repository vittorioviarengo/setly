import csv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import string  # For filename sanitization
import requests  # For image download

# Replace with your Spotify Client ID and Client Secret
client_id = "4dd130b8c960408798e64c30f04d67ad"
client_secret = "96c2357eea1e400e9921799f45581370"


# Local directory to store images
image_dir = "author_images"

def get_spotify_artist_data(author_name):
    """
    Attempts to retrieve the author's data from Spotify using artist search.

    Args:
        author_name (str): The name of the author.

    Returns:
        dict: Dictionary with 'image_url' and 'genres' if found, None otherwise.
    """
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id, client_secret))
    results = sp.search(q=author_name, type="artist")
    items = results.get("artists", {}).get("items", [])

    if items:
        artist_data = items[0]
        images = artist_data.get("images", [])
        genres = artist_data.get("genres", [])
        
        image_url = images[0]["url"] if images else None
        # Join multiple genres with commas, or use first genre
        genre = genres[0] if genres else None
        
        return {
            'image_url': image_url,
            'genre': genre
        }
    return None

def download_image(url, filename):
    """
    Downloads an image from the specified URL and saves it to the given filename.

    Args:
        url (str): The URL of the image.
        filename (str): The filename to save the image under.
    """
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        safe_filename = "".join(c for c in filename if c in string.ascii_letters + string.digits + '_-.')
        filepath = os.path.join(image_dir, safe_filename)  # Directory appended here
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"Downloaded image for {safe_filename}")
    else:
        print(f"Failed to download image for {filename} (status code: {response.status_code})")

def process_csv(csv_file, output_file):
    """
    Processes the CSV file, attempting to retrieve and download author images and genres from Spotify,
    and creates an output CSV with image filenames in the 4th column and genre in the 5th column.

    Args:
        csv_file (str): The path to the input CSV file.
        output_file (str): The path to the output CSV file.
    """
    # Create the image directory if it doesn't exist
    if not os.path.exists(image_dir):
        os.makedirs(image_dir)

    with open(csv_file, 'r', encoding='utf-8') as f_in, open(output_file, 'w', newline='', encoding='utf-8') as f_out:
        reader = csv.reader(f_in)
        writer = csv.writer(f_out)

        # Write header row
        header = next(reader)
        header.append("Image File")  # Add header for image filename
        header.append("Genre")  # Add header for genre
        writer.writerow(header)

        for row in reader:
            title = row[0] if len(row) > 0 else None
            author = row[1] if len(row) > 1 else None
            language = row[2] if len(row) > 2 else None
            image_filename = ""
            genre = ""

            if author:
                author = author.strip('"')
                artist_data = get_spotify_artist_data(author)
                if artist_data:
                    if artist_data.get('image_url'):
                        safe_filename = "".join(c for c in author if c in string.ascii_letters + string.digits + '_-.') + ".jpg"
                        download_image(artist_data['image_url'], safe_filename)  # Only the filename, without directory
                        image_filename = safe_filename  # Save just the filename for CSV
                    if artist_data.get('genre'):
                        genre = artist_data['genre']

            # Write row data with image filename in the 4th column and genre in 5th
            writer.writerow([title, author, language, image_filename, genre])

if __name__ == "__main__":
    csv_file = "songs.csv"  # Update with your actual file name
    output_file = "songs_images.csv"
    process_csv(csv_file, output_file)
