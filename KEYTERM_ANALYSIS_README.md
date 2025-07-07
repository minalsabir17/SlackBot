# Jersey City Politics Keyterm Analysis System

This system extracts and analyzes keyterms from your Reddit monitoring bot, excluding stop words like "the", "of", and pronouns like "it". It stores the data in a SQLite database and provides visualization tools.

## 🚀 Quick Start

1. **Install the system:**
   ```bash
   python setup_keyterm_analysis.py
   ```

2. **Test the integration:**
   ```bash
   python integrate_keyterm_analysis.py
   ```

3. **Generate a dashboard:**
   ```bash
   python keyterm_dashboard.py --dashboard
   ```

## 📁 Files Overview

### Core Files
- `keyterm_analyzer.py` - Main keyterm extraction and analysis engine
- `keyterm_dashboard.py` - Interactive dashboard and visualization tools
- `integrate_keyterm_analysis.py` - Integration guide and examples
- `setup_keyterm_analysis.py` - Setup script for dependencies

### Database
- `keyterms.db` - SQLite database storing extracted keyterms (created automatically)

### Generated Files
- `keyterm_wordcloud.png` - Word cloud visualization
- `keyterm_dashboard.html` - Interactive dashboard
- `keyterm_data.csv` - Exported data for external analysis

## 🛠️ Integration with Your Bot

### Step 1: Add Import
Add this to the top of your `bot.py`:
```python
from keyterm_analyzer import KeytermAnalyzer, analyze_reddit_post, analyze_reddit_comment

# Initialize analyzer
keyterm_analyzer = KeytermAnalyzer()
```

### Step 2: Enhance Your Producer Function
In your `reddit_item_producer()` function, add keyterm analysis:
```python
# After finding a relevant post
if any(keyword.lower() in submission_text.lower() for keyword in KEYWORDS_TO_MONITOR):
    # Your existing code...
    
    # ADD THIS: Keyterm analysis
    try:
        analyze_reddit_post(keyterm_analyzer, submission)
        print(f"[Keyterm] Analyzed post {submission.id} for keyterms")
    except Exception as e:
        print(f"[Keyterm] Error analyzing post {submission.id}: {e}")
```

### Step 3: Add Slack Reaction Handler
Add keyterm analysis to your Slack reaction handler:
```python
# Check for chart emoji reaction
if event.get("reaction") == "chart_with_upwards_trend":
    # Generate keyterm analysis
    top_keyterms = keyterm_analyzer.get_top_keyterms(limit=10, days_back=7)
    
    if not top_keyterms.empty:
        keyterm_text = "*📊 Top Keyterms (Last 7 Days)*\n\n"
        for _, row in top_keyterms.head(10).iterrows():
            keyterm_text += f"• *{row['term']}*: {row['total_frequency']} occurrences\n"
        
        client.chat_postMessage(
            channel=channel,
            thread_ts=timestamp,
            text=keyterm_text
        )
```

## 📊 Usage Examples

### Command Line Dashboard
```bash
# Generate full dashboard
python keyterm_dashboard.py --dashboard

# Show top 15 keyterms
python keyterm_dashboard.py --top 15

# Analyze specific term
python keyterm_dashboard.py --term "fulop"

# Export data to CSV
python keyterm_dashboard.py --export
```

### Programmatic Usage
```python
from keyterm_analyzer import KeytermAnalyzer

# Initialize analyzer
analyzer = KeytermAnalyzer()

# Get top keyterms
top_keyterms = analyzer.get_top_keyterms(limit=20, days_back=7)
print(top_keyterms)

# Get trend data for a specific term
trend_data = analyzer.get_keyterm_trends("fulop", days_back=30)
print(trend_data)

# Get context examples
context = analyzer.get_keyterm_context("housing", limit=5)
for ctx in context:
    print(f"Context: {ctx['context']}")
    print(f"Source: {ctx['source_type']} on {ctx['created_date']}")
```

## 🎯 What Gets Extracted

The system extracts meaningful keyterms while filtering out:

### Excluded (Stop Words)
- Prepositions: "the", "of", "and", "or", "but", "in", "on", "at", "to", "for", "with"
- Pronouns: "it", "he", "she", "they", "we", "you", "i", "me", "him", "her", "them"
- Common verbs: "is", "are", "was", "were", "have", "has", "had", "do", "does", "did"
- Generic words: "really", "just", "also", "even", "still", "well", "good", "bad"

### Included (Keyterms)
- **Nouns**: "housing", "development", "council", "election", "budget"
- **Proper nouns**: "Fulop", "Ali", "Jersey City", "HCDO"
- **Adjectives**: "affordable", "important", "local", "political"
- **Verbs**: "support", "oppose", "develop", "improve"
- **Named entities**: People, organizations, places, events

## 🗄️ Database Schema

The system uses SQLite with two main tables:

### `keyterms` Table
- `id` - Primary key
- `term` - The extracted keyterm
- `frequency` - How many times it appeared in the text
- `source_type` - "post" or "comment"
- `source_id` - Reddit post/comment ID
- `post_title` - Title of the Reddit post
- `subreddit` - Source subreddit
- `created_date` - When the analysis was performed
- `pos_tag` - Part of speech tag
- `context` - Surrounding text context

### `posts` Table
- `id` - Primary key
- `reddit_id` - Reddit post ID
- `title` - Post title
- `content` - Post content
- `author` - Post author
- `subreddit` - Source subreddit
- `created_date` - When the post was created
- `score` - Reddit score
- `num_comments` - Number of comments

## 📈 Visualization Features

### Word Cloud
- Visual representation of most frequent keyterms
- Size indicates frequency
- Saves as `keyterm_wordcloud.png`

### Interactive Dashboard
- Bar chart of top keyterms
- Trend lines over time
- Pie chart distribution
- Saves as `keyterm_dashboard.html`

### Trend Analysis
- Track specific terms over time
- Daily frequency charts
- Peak detection
- Context examples

## 🔧 Customization

### Modify Stop Words
Edit the `stop_words` set in `KeytermAnalyzer.__init__()`:
```python
self.stop_words.update([
    'your', 'custom', 'stop', 'words'
])
```

### Change Extraction Parameters
Modify the `extract_keyterms()` method:
```python
# Change minimum word length
keyterms = self.extract_keyterms(text, min_length=3)

# Change included part-of-speech tags
if token.pos_ in ['NOUN', 'PROPN', 'ADJ']:  # Only nouns and adjectives
```

### Database Location
Change the database path:
```python
analyzer = KeytermAnalyzer(db_path='custom_path/keyterms.db')
```

## 🚨 Troubleshooting

### Common Issues

1. **spaCy model not found:**
   ```bash
   python -m spacy download en_core_web_sm
   ```

2. **NLTK data missing:**
   ```python
   import nltk
   nltk.download('punkt')
   nltk.download('stopwords')
   nltk.download('averaged_perceptron_tagger')
   ```

3. **No keyterms found:**
   - Check if the bot is running and collecting data
   - Verify the database has data: `python keyterm_dashboard.py --top 5`
   - Check date ranges in queries

4. **Visualization errors:**
   - Install missing dependencies: `pip install matplotlib seaborn wordcloud plotly`
   - Check if database has sufficient data

### Debug Mode
Add debug prints to see what's happening:
```python
analyzer = KeytermAnalyzer()
analyzer.store_keyterms(
    text="Your test text here",
    source_type='debug',
    source_id='test_001',
    post_title='Debug Test',
    subreddit='test'
)

# Check results
top_keyterms = analyzer.get_top_keyterms(limit=5)
print(top_keyterms)
```

## 🔮 Future Enhancements

Potential improvements you could add:

1. **Sentiment Analysis**: Track positive/negative sentiment for each keyterm
2. **Network Analysis**: Map relationships between keyterms
3. **Real-time Alerting**: Get notified when certain keyterms spike
4. **Export Options**: Add JSON, Excel export formats
5. **Web Interface**: Create a web dashboard instead of static HTML
6. **Machine Learning**: Predict trending topics based on keyterm patterns

## 📞 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Run the setup script again: `python setup_keyterm_analysis.py`
3. Test with sample data: `python integrate_keyterm_analysis.py`

The system is designed to work alongside your existing bot without interfering with its core functionality. 