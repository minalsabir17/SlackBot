#!/usr/bin/env python3
"""
Setup script for Jersey City Politics Keyterm Analysis System
"""

import subprocess
import sys
import os

def install_dependencies():
    """Install required dependencies"""
    print("🔧 Installing dependencies...")
    
    try:
        # Install Python packages
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Python packages installed successfully")
        
        # Download NLTK data
        print("📥 Downloading NLTK data...")
        import nltk
        nltk.download('punkt')
        nltk.download('stopwords')
        nltk.download('averaged_perceptron_tagger')
        print("✅ NLTK data downloaded")
        
        # Install spaCy model
        print("📥 Installing spaCy English model...")
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_sm"])
        print("✅ spaCy model installed")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error installing dependencies: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

def test_system():
    """Test the keyterm analysis system"""
    print("\n🧪 Testing keyterm analysis system...")
    
    try:
        from keyterm_analyzer import KeytermAnalyzer
        
        # Initialize analyzer
        analyzer = KeytermAnalyzer()
        print("✅ Database initialized successfully")
        
        # Test with sample data
        sample_text = """
        Jersey City mayoral race is heating up with candidates like Mussab Ali and Steven Fulop. 
        The Board of Education elections are also important for local governance.
        Many residents are concerned about housing costs and development projects.
        City council meetings have been discussing budget allocations and infrastructure improvements.
        Public transportation and PATH train access are key issues for voters.
        """
        
        analyzer.store_keyterms(
            text=sample_text,
            source_type='test',
            source_id='setup_test',
            post_title='Setup Test Post',
            subreddit='jerseycity'
        )
        print("✅ Sample keyterms stored successfully")
        
        # Test retrieval
        top_keyterms = analyzer.get_top_keyterms(limit=5)
        if not top_keyterms.empty:
            print("✅ Keyterm retrieval working")
            print("\n📊 Sample results:")
            for i, row in top_keyterms.head(5).iterrows():
                print(f"  • {row['term']}: {row['total_frequency']} occurrences")
        else:
            print("⚠️  No keyterms found (this might be normal)")
        
        # Test visualization
        try:
            wordcloud = analyzer.generate_wordcloud(days_back=7, max_words=20)
            if wordcloud:
                print("✅ Word cloud generation working")
            else:
                print("⚠️  Word cloud generation returned None (might be normal with limited data)")
        except Exception as e:
            print(f"⚠️  Word cloud generation failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ System test failed: {e}")
        return False

def create_sample_env():
    """Create a sample .env file if it doesn't exist"""
    env_file = ".env"
    
    if not os.path.exists(env_file):
        print("\n📝 Creating sample .env file...")
        
        sample_env = """# Jersey City Politics Bot Configuration
# Copy this file and add your actual credentials

# Slack Configuration
SLACK_WEBHOOK_URL=your_slack_webhook_url_here
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here

# Reddit Configuration
REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=JerseyCity Politics Bot 1.0

# OpenAI Configuration (optional)
OPENAI_API_KEY=your_openai_api_key_here
"""
        
        with open(env_file, 'w') as f:
            f.write(sample_env)
        
        print(f"✅ Sample .env file created: {env_file}")
        print("⚠️  Please edit the .env file with your actual credentials")
    else:
        print(f"✅ .env file already exists: {env_file}")

def main():
    """Main setup function"""
    print("🚀 Jersey City Politics Keyterm Analysis Setup")
    print("=" * 50)
    
    # Create sample .env file
    create_sample_env()
    
    # Install dependencies
    if not install_dependencies():
        print("\n❌ Setup failed during dependency installation")
        sys.exit(1)
    
    # Test the system
    if not test_system():
        print("\n❌ Setup failed during system testing")
        sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 Setup completed successfully!")
    print("=" * 50)
    
    print("\n📋 Next steps:")
    print("1. Edit the .env file with your actual API credentials")
    print("2. Test the integration with: python integrate_keyterm_analysis.py")
    print("3. Run the dashboard with: python keyterm_dashboard.py --dashboard")
    print("4. Integrate with your bot by following the examples in integrate_keyterm_analysis.py")
    
    print("\n🔧 Available commands:")
    print("• python keyterm_dashboard.py --dashboard    # Generate full dashboard")
    print("• python keyterm_dashboard.py --term 'ali'   # Analyze specific term")
    print("• python keyterm_dashboard.py --export       # Export data to CSV")
    print("• python keyterm_dashboard.py --top 15       # Show top 15 terms")
    
    print("\n📊 Database location: keyterms.db")
    print("📁 Generated files will be saved in the current directory")

if __name__ == "__main__":
    main() 