import sqlite3
import nltk
import spacy
import re
from collections import Counter
from datetime import datetime
from typing import List, Dict, Tuple, Set
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Download required NLTK data (run once)
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
    nltk.data.find('taggers/averaged_perceptron_tagger')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')
    nltk.download('averaged_perceptron_tagger')

# Load spaCy model (you may need to install: python -m spacy download en_core_web_sm)
try:
    nlp = spacy.load('en_core_web_sm')
except OSError:
    print("Warning: spaCy model not found. Install with: python -m spacy download en_core_web_sm")
    nlp = None

from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.tag import pos_tag

class KeytermAnalyzer:
    def __init__(self, db_path='keyterms.db'):
        self.db_path = db_path
        self.stop_words = set(stopwords.words('english'))
        
        # Add custom stop words and pronouns
        self.stop_words.update([
            'the', 'of', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'among', 'under', 'over',
            'it', 'he', 'she', 'they', 'we', 'you', 'i', 'me', 'him', 'her',
            'them', 'us', 'this', 'that', 'these', 'those', 'my', 'your',
            'his', 'her', 'its', 'our', 'their', 'mine', 'yours', 'ours',
            'theirs', 'myself', 'yourself', 'himself', 'herself', 'itself',
            'ourselves', 'yourselves', 'themselves', 'what', 'which', 'who',
            'whom', 'whose', 'where', 'when', 'why', 'how', 'is', 'are', 'was',
            'were', 'be', 'been', 'being', 'have', 'has', 'had', 'having',
            'do', 'does', 'did', 'doing', 'will', 'would', 'should', 'could',
            'can', 'may', 'might', 'must', 'shall', 'should', 'reddit', 'post',
            'comment', 'said', 'says', 'get', 'got', 'go', 'going', 'come',
            'came', 'way', 'made', 'make', 'take', 'took', 'see', 'saw',
            'know', 'knew', 'think', 'thought', 'really', 'just', 'also',
            'even', 'still', 'well', 'back', 'only', 'first', 'last', 'new',
            'old', 'good', 'bad', 'great', 'little', 'big', 'small', 'long',
            'short', 'high', 'low', 'right', 'left', 'yes', 'no', 'ok', 'okay'
        ])
        
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database with required tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create keyterms table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS keyterms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                term TEXT NOT NULL,
                frequency INTEGER NOT NULL,
                source_type TEXT NOT NULL,  -- 'post' or 'comment'
                source_id TEXT NOT NULL,    -- Reddit post/comment ID
                post_title TEXT,
                subreddit TEXT,
                created_date TEXT NOT NULL,
                pos_tag TEXT,              -- Part of speech tag
                context TEXT               -- Surrounding context
            )
        ''')
        
        # Create posts table for reference
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reddit_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                author TEXT,
                subreddit TEXT,
                created_date TEXT NOT NULL,
                score INTEGER,
                num_comments INTEGER
            )
        ''')
        
        # Create index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_keyterms_term 
            ON keyterms (term)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_keyterms_date 
            ON keyterms (created_date)
        ''')
        
        conn.commit()
        conn.close()
    
    def extract_keyterms(self, text: str, min_length: int = 2) -> List[Tuple[str, str, str]]:
        """
        Extract keyterms from text using NLTK and spaCy.
        Returns list of tuples: (term, pos_tag, context)
        """
        if not text or len(text.strip()) < 3:
            return []
        
        keyterms = []
        
        # Clean text
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        text = re.sub(r'[^a-zA-Z\s]', ' ', text)
        text = ' '.join(text.split())
        
        # Use spaCy if available for better NER and POS tagging
        if nlp:
            doc = nlp(text)
            for token in doc:
                if (token.text.lower() not in self.stop_words and 
                    len(token.text) >= min_length and
                    token.pos_ in ['NOUN', 'PROPN', 'ADJ', 'VERB'] and
                    not token.is_punct and
                    not token.is_space):
                    
                    # Get context (5 words before and after)
                    start = max(0, token.i - 5)
                    end = min(len(doc), token.i + 6)
                    context = ' '.join([t.text for t in doc[start:end]])
                    
                    keyterms.append((token.lemma_.lower(), token.pos_, context))
            
            # Also extract named entities
            for ent in doc.ents:
                if (ent.label_ in ['PERSON', 'ORG', 'GPE', 'EVENT'] and 
                    len(ent.text) >= min_length):
                    keyterms.append((ent.text.lower(), ent.label_, ent.sent.text))
        
        else:
            # Fallback to NLTK
            tokens = word_tokenize(text.lower())
            pos_tags = pos_tag(tokens)
            
            for i, (token, pos) in enumerate(pos_tags):
                if (token not in self.stop_words and 
                    len(token) >= min_length and
                    pos in ['NN', 'NNS', 'NNP', 'NNPS', 'JJ', 'JJR', 'JJS', 'VB', 'VBD', 'VBG', 'VBN', 'VBP', 'VBZ']):
                    
                    # Get context
                    start = max(0, i - 5)
                    end = min(len(tokens), i + 6)
                    context = ' '.join(tokens[start:end])
                    
                    keyterms.append((token, pos, context))
        
        return keyterms
    
    def store_keyterms(self, text: str, source_type: str, source_id: str, 
                      post_title: str = '', subreddit: str = '', 
                      additional_context: Dict = None):
        """
        Extract and store keyterms from text in the database.
        """
        if not text:
            return
        
        keyterms = self.extract_keyterms(text)
        if not keyterms:
            return
        
        # Count frequency of each term
        term_counts = Counter([term for term, _, _ in keyterms])
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        created_date = datetime.now().isoformat()
        
        for term, count in term_counts.items():
            # Find the POS tag and context for this term
            pos_tag = ''
            context = ''
            for kt_term, kt_pos, kt_context in keyterms:
                if kt_term == term:
                    pos_tag = kt_pos
                    context = kt_context
                    break
            
            cursor.execute('''
                INSERT INTO keyterms 
                (term, frequency, source_type, source_id, post_title, subreddit, 
                 created_date, pos_tag, context)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (term, count, source_type, source_id, post_title, subreddit,
                  created_date, pos_tag, context))
        
        conn.commit()
        conn.close()
        
        print(f"Stored {len(term_counts)} unique keyterms from {source_type} {source_id}")
    
    def store_post_data(self, reddit_post):
        """
        Store Reddit post data for reference.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO posts 
                (reddit_id, title, content, author, subreddit, created_date, score, num_comments)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                reddit_post.id,
                reddit_post.title,
                reddit_post.selftext,
                str(reddit_post.author),
                str(reddit_post.subreddit),
                datetime.fromtimestamp(reddit_post.created_utc).isoformat(),
                reddit_post.score,
                reddit_post.num_comments
            ))
            
            conn.commit()
        except Exception as e:
            print(f"Error storing post data: {e}")
        finally:
            conn.close()
    
    def get_top_keyterms(self, limit: int = 50, days_back: int = 30) -> pd.DataFrame:
        """
        Get the most frequent keyterms from the last N days.
        """
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT term, SUM(frequency) as total_frequency, 
                   COUNT(*) as occurrences,
                   GROUP_CONCAT(DISTINCT pos_tag) as pos_tags
            FROM keyterms 
            WHERE created_date >= date('now', '-{} days')
            GROUP BY term
            ORDER BY total_frequency DESC
            LIMIT ?
        '''.format(days_back)
        
        df = pd.read_sql_query(query, conn, params=[limit])
        conn.close()
        
        return df
    
    def get_keyterm_trends(self, term: str, days_back: int = 30) -> pd.DataFrame:
        """
        Get trend data for a specific keyterm over time.
        """
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT DATE(created_date) as date, SUM(frequency) as daily_frequency
            FROM keyterms 
            WHERE term = ? AND created_date >= date('now', '-{} days')
            GROUP BY DATE(created_date)
            ORDER BY date
        '''.format(days_back)
        
        df = pd.read_sql_query(query, conn, params=[term])
        conn.close()
        
        return df
    
    def generate_wordcloud(self, days_back: int = 30, max_words: int = 100) -> WordCloud:
        """
        Generate a word cloud from keyterms.
        """
        df = self.get_top_keyterms(limit=max_words, days_back=days_back)
        
        if df.empty:
            return None
        
        # Create frequency dictionary
        freq_dict = dict(zip(df['term'], df['total_frequency']))
        
        wordcloud = WordCloud(
            width=800, 
            height=400, 
            background_color='white',
            max_words=max_words,
            colormap='viridis'
        ).generate_from_frequencies(freq_dict)
        
        return wordcloud
    
    def create_trend_visualization(self, top_n: int = 10, days_back: int = 30):
        """
        Create a trend visualization for top keyterms.
        """
        # Get top terms
        top_terms = self.get_top_keyterms(limit=top_n, days_back=days_back)
        
        if top_terms.empty:
            print("No keyterms found for visualization")
            return None
        
        # Create subplots
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Top Keyterms', 'Word Cloud', 'Trend Over Time', 'Term Distribution'),
            specs=[[{"type": "bar"}, {"type": "scatter"}],
                   [{"type": "scatter"}, {"type": "pie"}]]
        )
        
        # Bar chart of top terms
        fig.add_trace(
            go.Bar(x=top_terms['term'][:10], y=top_terms['total_frequency'][:10]),
            row=1, col=1
        )
        
        # Get trend data for top 5 terms
        for i, term in enumerate(top_terms['term'][:5]):
            trend_data = self.get_keyterm_trends(term, days_back)
            if not trend_data.empty:
                fig.add_trace(
                    go.Scatter(
                        x=trend_data['date'], 
                        y=trend_data['daily_frequency'],
                        mode='lines+markers',
                        name=term
                    ),
                    row=2, col=1
                )
        
        # Pie chart of top terms
        fig.add_trace(
            go.Pie(
                labels=top_terms['term'][:8], 
                values=top_terms['total_frequency'][:8]
            ),
            row=2, col=2
        )
        
        fig.update_layout(
            title=f'Keyterm Analysis - Last {days_back} Days',
            showlegend=True,
            height=800
        )
        
        return fig
    
    def get_keyterm_context(self, term: str, limit: int = 10) -> List[Dict]:
        """
        Get context examples for a specific keyterm.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT source_type, source_id, post_title, context, created_date
            FROM keyterms 
            WHERE term = ?
            ORDER BY created_date DESC
            LIMIT ?
        ''', (term, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            {
                'source_type': r[0],
                'source_id': r[1],
                'post_title': r[2],
                'context': r[3],
                'created_date': r[4]
            }
            for r in results
        ]
    
    def export_keyterms_csv(self, filename: str = 'keyterms_export.csv', days_back: int = 30):
        """
        Export keyterms to CSV for external analysis.
        """
        conn = sqlite3.connect(self.db_path)
        
        query = '''
            SELECT term, frequency, source_type, source_id, post_title, 
                   subreddit, created_date, pos_tag, context
            FROM keyterms 
            WHERE created_date >= date('now', '-{} days')
            ORDER BY created_date DESC
        '''.format(days_back)
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        df.to_csv(filename, index=False)
        print(f"Exported {len(df)} keyterm records to {filename}")
        
        return df


# Helper functions for integration with existing bot
def analyze_reddit_post(analyzer: KeytermAnalyzer, reddit_post):
    """
    Analyze a Reddit post and store keyterms.
    """
    # Store post data
    analyzer.store_post_data(reddit_post)
    
    # Analyze post title and content
    full_text = reddit_post.title + " " + reddit_post.selftext
    analyzer.store_keyterms(
        text=full_text,
        source_type='post',
        source_id=reddit_post.id,
        post_title=reddit_post.title,
        subreddit=str(reddit_post.subreddit)
    )

def analyze_reddit_comment(analyzer: KeytermAnalyzer, reddit_comment):
    """
    Analyze a Reddit comment and store keyterms.
    """
    analyzer.store_keyterms(
        text=reddit_comment.body,
        source_type='comment',
        source_id=reddit_comment.id,
        post_title=reddit_comment.submission.title,
        subreddit=str(reddit_comment.subreddit)
    )

# Example usage and testing
if __name__ == "__main__":
    # Initialize analyzer
    analyzer = KeytermAnalyzer()
    
    # Test with sample text
    sample_text = """
    Jersey City mayoral race is heating up with candidates like Mussab Ali and Steven Fulop. 
    The Board of Education elections are also important for local governance.
    Many residents are concerned about housing costs and development projects.
    """
    
    analyzer.store_keyterms(
        text=sample_text,
        source_type='test',
        source_id='sample_001',
        post_title='Test Post',
        subreddit='jerseycity'
    )
    
    # Display results
    print("Top keyterms:")
    print(analyzer.get_top_keyterms(limit=10))
    
    print("\nGenerating visualizations...")
    fig = analyzer.create_trend_visualization()
    if fig:
        fig.write_html('keyterm_analysis.html')
        print("Visualization saved as keyterm_analysis.html") 