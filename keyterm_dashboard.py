"""
Keyterm Dashboard - Interactive analysis and visualization of extracted keyterms
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from keyterm_analyzer import KeytermAnalyzer
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime, timedelta
import argparse

def create_dashboard():
    """Create an interactive dashboard for keyterm analysis."""
    
    # Initialize analyzer
    analyzer = KeytermAnalyzer()
    
    print("=" * 60)
    print("JERSEY CITY POLITICS KEYTERM DASHBOARD")
    print("=" * 60)
    
    # Get basic stats
    top_keyterms = analyzer.get_top_keyterms(limit=20, days_back=30)
    
    if top_keyterms.empty:
        print("No keyterms found in database. Run the bot first to collect data.")
        return
    
    print(f"\n📊 OVERVIEW (Last 30 days)")
    print("-" * 30)
    print(f"Total unique keyterms: {len(top_keyterms)}")
    print(f"Total term occurrences: {top_keyterms['total_frequency'].sum()}")
    print(f"Most frequent term: '{top_keyterms.iloc[0]['term']}' ({top_keyterms.iloc[0]['total_frequency']} times)")
    
    # Top 10 keyterms
    print(f"\n🔝 TOP 10 KEYTERMS")
    print("-" * 25)
    for i, row in top_keyterms.head(10).iterrows():
        print(f"{i+1:2d}. {row['term']:20} - {row['total_frequency']:3d} occurrences")
    
    # Context examples for top term
    if len(top_keyterms) > 0:
        top_term = top_keyterms.iloc[0]['term']
        context = analyzer.get_keyterm_context(top_term, limit=3)
        
        if context:
            print(f"\n💬 CONTEXT EXAMPLES FOR '{top_term.upper()}'")
            print("-" * 40)
            for i, ctx in enumerate(context, 1):
                print(f"{i}. {ctx['context'][:80]}...")
                print(f"   Source: {ctx['source_type']} | {ctx['created_date'][:10]}")
                print()
    
    # Generate visualizations
    print("\n📈 GENERATING VISUALIZATIONS...")
    print("-" * 35)
    
    # 1. Word Cloud
    try:
        wordcloud = analyzer.generate_wordcloud(days_back=30, max_words=50)
        if wordcloud:
            plt.figure(figsize=(12, 6))
            plt.imshow(wordcloud, interpolation='bilinear')
            plt.axis('off')
            plt.title('Jersey City Politics - Keyterm Word Cloud (Last 30 Days)', fontsize=16)
            plt.tight_layout()
            plt.savefig('keyterm_wordcloud.png', dpi=300, bbox_inches='tight')
            plt.close()
            print("✓ Word cloud saved as 'keyterm_wordcloud.png'")
    except Exception as e:
        print(f"✗ Word cloud generation failed: {e}")
    
    # 2. Interactive Dashboard
    try:
        fig = analyzer.create_trend_visualization(top_n=10, days_back=30)
        if fig:
            fig.write_html('keyterm_dashboard.html')
            print("✓ Interactive dashboard saved as 'keyterm_dashboard.html'")
    except Exception as e:
        print(f"✗ Interactive dashboard generation failed: {e}")
    
    # 3. Export data
    try:
        df = analyzer.export_keyterms_csv('keyterm_data.csv', days_back=30)
        print(f"✓ Data exported to 'keyterm_data.csv' ({len(df)} records)")
    except Exception as e:
        print(f"✗ Data export failed: {e}")
    
    # 4. Trend analysis for top terms
    print(f"\n📊 TREND ANALYSIS")
    print("-" * 20)
    
    for term in top_keyterms.head(5)['term']:
        trend_data = analyzer.get_keyterm_trends(term, days_back=30)
        if not trend_data.empty:
            recent_avg = trend_data['daily_frequency'].tail(7).mean()
            total_mentions = trend_data['daily_frequency'].sum()
            print(f"'{term}': {total_mentions:.0f} total mentions, {recent_avg:.1f} avg/day (last 7 days)")
    
    print("\n" + "=" * 60)
    print("Dashboard complete! Check the generated files:")
    print("• keyterm_wordcloud.png - Visual word cloud")
    print("• keyterm_dashboard.html - Interactive dashboard")
    print("• keyterm_data.csv - Raw data export")
    print("=" * 60)

def analyze_specific_term(term):
    """Analyze a specific keyterm in detail."""
    analyzer = KeytermAnalyzer()
    
    print(f"\n📊 DETAILED ANALYSIS FOR: '{term.upper()}'")
    print("=" * 50)
    
    # Get trend data
    trend_data = analyzer.get_keyterm_trends(term, days_back=30)
    
    if trend_data.empty:
        print(f"No data found for term '{term}'")
        return
    
    # Basic stats
    total_mentions = trend_data['daily_frequency'].sum()
    avg_daily = trend_data['daily_frequency'].mean()
    peak_day = trend_data.loc[trend_data['daily_frequency'].idxmax()]
    
    print(f"Total mentions (30 days): {total_mentions}")
    print(f"Average per day: {avg_daily:.1f}")
    print(f"Peak day: {peak_day['date']} ({peak_day['daily_frequency']} mentions)")
    
    # Get context examples
    context = analyzer.get_keyterm_context(term, limit=5)
    
    if context:
        print(f"\nRECENT CONTEXT EXAMPLES:")
        print("-" * 25)
        for i, ctx in enumerate(context, 1):
            print(f"{i}. {ctx['context'][:100]}...")
            print(f"   Post: {ctx['post_title'][:50]}...")
            print(f"   Date: {ctx['created_date'][:10]} | Type: {ctx['source_type']}")
            print()
    
    # Create trend chart
    try:
        fig = px.line(trend_data, x='date', y='daily_frequency', 
                     title=f"Trend for '{term}' - Last 30 Days")
        fig.update_layout(xaxis_title="Date", yaxis_title="Daily Mentions")
        fig.write_html(f'trend_{term.replace(" ", "_")}.html')
        print(f"✓ Trend chart saved as 'trend_{term.replace(' ', '_')}.html'")
    except Exception as e:
        print(f"✗ Trend chart generation failed: {e}")

def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(description='Jersey City Politics Keyterm Dashboard')
    parser.add_argument('--dashboard', action='store_true', help='Generate full dashboard')
    parser.add_argument('--term', type=str, help='Analyze specific term')
    parser.add_argument('--export', action='store_true', help='Export data to CSV')
    parser.add_argument('--top', type=int, default=10, help='Number of top terms to show')
    
    args = parser.parse_args()
    
    if args.dashboard:
        create_dashboard()
    elif args.term:
        analyze_specific_term(args.term)
    elif args.export:
        analyzer = KeytermAnalyzer()
        df = analyzer.export_keyterms_csv('keyterm_export.csv', days_back=30)
        print(f"Exported {len(df)} records to keyterm_export.csv")
    else:
        # Default: show top terms
        analyzer = KeytermAnalyzer()
        top_keyterms = analyzer.get_top_keyterms(limit=args.top, days_back=7)
        
        if top_keyterms.empty:
            print("No keyterms found. Run the bot first to collect data.")
        else:
            print(f"Top {args.top} keyterms (last 7 days):")
            for i, row in top_keyterms.iterrows():
                print(f"{i+1}. {row['term']:20} - {row['total_frequency']} occurrences")

if __name__ == "__main__":
    main() 