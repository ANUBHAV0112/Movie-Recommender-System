from flask import Flask, request, render_template
import pickle
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import ast
import matplotlib.pyplot as plt
import seaborn as sns


app = Flask(__name__)

# Load data
movies = pd.read_csv('tmdb_5000_movies.csv')
credits = pd.read_csv('tmdb_5000_credits.csv')

movies = movies.merge(credits, left_on='id', right_on='movie_id')

def get_genres(obj):
    return [i['name'] for i in ast.literal_eval(obj)]

movies['genres_list'] = movies['genres'].apply(get_genres)

def get_director(obj):
    for i in ast.literal_eval(obj):
        if i['job'] == 'Director':
            return i['name']
    return ''

movies['director'] = movies['crew'].apply(get_director)

def get_keywords(obj):
    return [i['name'] for i in ast.literal_eval(obj)]

movies['keywords_list'] = movies['keywords'].apply(get_keywords)

def get_cast(obj):
    return [i['name'] for i in ast.literal_eval(obj)[:3]]

movies['cast_list'] = movies['cast'].apply(get_cast)

movies['genres_list'] = movies['genres_list'].apply(lambda x: [i.replace(" ", "").lower() for i in x])
movies['keywords_list'] = movies['keywords_list'].apply(lambda x: [i.replace(" ", "").lower() for i in x])
movies['cast_list'] = movies['cast_list'].apply(lambda x: [i.replace(" ", "").lower() for i in x])
movies['director'] = movies['director'].apply(lambda x: x.replace(" ", "").lower())

movies['tags'] = movies.apply(lambda row: row['genres_list'] + row['keywords_list'] + row['cast_list'] + [row['director']], axis=1)
movies['tags'] = movies['tags'].apply(lambda x: " ".join(x))

cv = CountVectorizer(max_features=5000, stop_words='english')
vectors = cv.fit_transform(movies['tags']).toarray()
similarity = cosine_similarity(vectors)

# Save for future use
pickle.dump(movies, open('movies.pkl', 'wb'))
pickle.dump(similarity, open('similarity.pkl', 'wb'))

# Load pickles (optional, shows how you’d do it in production)
movies = pickle.load(open('movies.pkl', 'rb'))
similarity = pickle.load(open('similarity.pkl', 'rb'))

@app.route('/')
def home():
    movie_list = movies['title_x'].values
    return render_template('index.html', movies=movie_list)

@app.route('/recommend', methods=['POST'])
def recommend():
    movie_name = request.form['movie_name'].lower()
    
    # Try partial matching
    matches = movies[movies['title_x'].str.lower().str.contains(movie_name)]
    
    if matches.empty:
        # No match found
        return render_template('recommend.html', movie_name=movie_name.title(), recommendations=[])
    
    # Pick the first matching movie
    movie_idx = matches.index[0]
    distances = sorted(list(enumerate(similarity[movie_idx])), reverse=True, key=lambda x: x[1])
    
    recommendations = []
    for i in distances[1:6]:
        recommendations.append(movies.iloc[i[0]]['title_x'])
        
    return render_template('recommend.html',
                           movie_name=movies.iloc[movie_idx]['title_x'],
                           recommendations=recommendations)

    
def generate_genre_plot():
    genres_count = pd.Series(sum(movies['genres_list'], [])).value_counts().head(10)
    plt.figure(figsize=(12,5))
    sns.barplot(x=genres_count.index, y=genres_count.values, palette='viridis')
    plt.title('Top 10 Genres')
    plt.ylabel('Number of Movies')
    plt.xlabel('Categories')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('static/genres_plot.png')
    plt.close()

# Generate once when the app starts
generate_genre_plot()

def generate_heatmap():
    import numpy as np
    import seaborn as sns
    sample_sim = similarity[:20, :20]
    plt.figure(figsize=(10,8))
    sns.heatmap(sample_sim, cmap='viridis')
    plt.title('Similarity Matrix Heatmap (Sample)')
    plt.tight_layout()
    plt.savefig('static/heatmap.png')
    plt.close()
generate_heatmap()  

if __name__ == '__main__':
    app.run(debug=True)
