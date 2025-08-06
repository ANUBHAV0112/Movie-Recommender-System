from flask import Flask, request, render_template
import pickle
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import ast
import matplotlib
matplotlib.use('Agg')  # ✅ Fix RuntimeError: main thread not in main loop
import matplotlib.pyplot as plt
import seaborn as sns
import requests
from dotenv import load_dotenv
import os
import mysql.connector
from wordcloud import WordCloud

# Load environment variables
load_dotenv()
TMDB_API_KEY = os.getenv('TMDB_API_KEY')

# Database connection
db = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    port=os.getenv("DB_PORT")
)
cursor = db.cursor()

app = Flask(__name__)

# Load pickled data
movies = pickle.load(open('movies.pkl', 'rb'))
similarity = pickle.load(open('similarity.pkl', 'rb'))

# Fetch poster using TMDB API
def fetch_poster(movie_title):
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={movie_title}"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['results']:
            poster_path = data['results'][0].get('poster_path')
            if poster_path:
                return f"https://image.tmdb.org/t/p/w500{poster_path}"
    except Exception as e:
        print(f"Error fetching poster: {e}")
    return "https://via.placeholder.com/200x300?text=No+Poster"

@app.route('/')
def home():
    movie_list = movies['title_x'].values
    return render_template('index.html', movies=movie_list)

@app.route("/rate", methods=["POST"])
def rate_movie():
    data = request.json
    movie_id = data["movie_id"]
    rating = data["rating"]
    user_id = 1  # You can change this to dynamic user ID if needed

    cursor.execute(
        "INSERT INTO user_ratings (user_id, movie_id, rating) VALUES (%s, %s, %s)",
        (user_id, movie_id, rating)
    )
    db.commit()
    return {"message": "Rating submitted!"}, 200

@app.route('/recommend', methods=['POST'])
def recommend():
    movie_name = request.form['movie_name'].lower()
    matches = movies[movies['title_x'].str.lower().str.contains(movie_name)]

    if matches.empty:
        return render_template('recommend.html', movie_name=movie_name.title(), recommendations=[])

    movie_idx = matches.index[0]
    distances = sorted(list(enumerate(similarity[movie_idx])), reverse=True, key=lambda x: x[1])

    recommendations = []
    for i in distances[1:6]:
        movie_data = movies.iloc[i[0]]
        movie_title = movie_data.title_x
        poster_url = fetch_poster(movie_title)
        recommendations.append({
            'id': movie_data.id,
            'title': movie_title,
            'poster': poster_url
        })

    return render_template('recommend.html',
                           movie_name=movies.iloc[movie_idx]['title_x'],
                           recommendations=recommendations)

# ------------------- PLOTS ------------------

def generate_genre_plot():
    genres_count = pd.Series(sum(movies['genres_list'], [])).value_counts().head(10)
    plt.figure(figsize=(12,5))
    sns.barplot(x=genres_count.index, y=genres_count.values, palette='viridis')
    plt.title('Top 10 Genres')
    plt.ylabel('Number of Movies')
    plt.xlabel('Genres')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('static/genres_plot.png')
    plt.close()

def generate_heatmap():
    sample_sim = similarity[:20, :20]
    plt.figure(figsize=(10,8))
    sns.heatmap(sample_sim, cmap='viridis')
    plt.title('Similarity Matrix Heatmap (Sample)')
    plt.tight_layout()
    plt.savefig('static/heatmap.png')
    plt.close()

def generate_directors_pie():
    directors = []
    for crew_data in movies['crew']:
        try:
            crew_list = ast.literal_eval(crew_data)
            for member in crew_list:
                if member.get('job') == 'Director':
                    directors.append(member.get('name'))
        except:
            continue
    director_series = pd.Series(directors).value_counts().head(10)
    plt.figure(figsize=(8, 8))
    plt.pie(director_series.values, labels=director_series.index, autopct='%1.1f%%')
    plt.title('Top 10 Directors')
    plt.tight_layout()
    plt.savefig('static/directors_pie.png')
    plt.close()

def generate_release_histogram():
    movies['release_date'] = pd.to_datetime(movies['release_date'], errors='coerce')
    valid_dates = movies['release_date'].dropna()
    plt.figure(figsize=(10, 6))
    valid_dates.dt.year.hist(bins=30, color='skyblue', edgecolor='black')
    plt.title('Movies Released Over Time')
    plt.xlabel('Year')
    plt.ylabel('Number of Movies')
    plt.tight_layout()
    plt.savefig('static/release_histogram.png')
    plt.close()

def generate_keywords_wordcloud():
    all_keywords = []
    for kw_str in movies['keywords']:
        try:
            kws = ast.literal_eval(kw_str)
            for k in kws:
                all_keywords.append(k['name'])
        except:
            continue
    text = ' '.join(all_keywords)
    wc = WordCloud(width=800, height=400, background_color='white').generate(text)
    plt.figure(figsize=(10, 5))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    plt.title('Most Common Keywords')
    plt.tight_layout()
    plt.savefig('static/keywords_wordcloud.png')
    plt.close()

# Call them once at start-up
generate_genre_plot()
generate_heatmap()
generate_directors_pie()
generate_release_histogram()
generate_keywords_wordcloud()

if __name__ == '__main__':
    app.run(debug=True)
