"""
Integration Guide: Adding Keyterm Analysis to Your Existing Bot

This file shows how to modify your existing bot.py to include keyterm analysis.
"""

from keyterm_analyzer import KeytermAnalyzer, analyze_reddit_post, analyze_reddit_comment

# 1. Add this near the top of your bot.py, after imports
# Initialize Keyterm Analyzer
keyterm_analyzer = KeytermAnalyzer()
print("Keyterm analyzer initialized with database.")

# 2. Modify your reddit_item_producer() function to include keyterm analysis
def reddit_item_producer_with_keyterms():
    """
    Enhanced version of your reddit_item_producer function
    Add this code after you find relevant posts/comments
    """
    print(f"[Producer] Starting to monitor r/{SUBREDDIT_TO_MONITOR} for keywords...")
    while not stop_event.is_set():
        try:
            subreddit = reddit.subreddit(SUBREDDIT_TO_MONITOR)
            
            for submission in subreddit.new(limit=SUBMISSION_LIMIT):
                # Your existing code for checking keywords...
                if submission.id not in seen_submission_ids:
                    submission_text = submission.title + " " + submission.selftext
                    if any(keyword.lower() in submission_text.lower() for keyword in KEYWORDS_TO_MONITOR):
                        print(f"[Producer] Found relevant new post {submission.id}: '{submission.title}'.")
                        
                        # ADD THIS: Keyterm analysis
                        try:
                            analyze_reddit_post(keyterm_analyzer, submission)
                            print(f"[Keyterm] Analyzed post {submission.id} for keyterms")
                        except Exception as e:
                            print(f"[Keyterm] Error analyzing post {submission.id}: {e}")
                        
                        items_queue.put({'type': 'submission', 'data': submission})
                        seen_submission_ids.add(submission.id)
                
                # Check comments...
                submission.comments.replace_more(limit=0)
                for comment in submission.comments.list():
                    if comment.id not in seen_comment_ids:
                        if any(keyword.lower() in comment.body.lower() for keyword in KEYWORDS_TO_MONITOR):
                            print(f"[Producer] Found relevant new comment {comment.id}")
                            
                            # ADD THIS: Keyterm analysis
                            try:
                                analyze_reddit_comment(keyterm_analyzer, comment)
                                print(f"[Keyterm] Analyzed comment {comment.id} for keyterms")
                            except Exception as e:
                                print(f"[Keyterm] Error analyzing comment {comment.id}: {e}")
                            
                            items_queue.put({'type': 'comment', 'data': comment})
                            seen_comment_ids.add(comment.id)
            
            stop_event.wait(FETCH_INTERVAL)
        except Exception as e:
            print(f"[Producer] An error occurred: {e}")
            stop_event.wait(FETCH_INTERVAL)

# 3. Add keyterm analysis to your Slack reaction handler
def enhanced_handle_reaction_added(client, event):
    """
    Enhanced reaction handler that includes keyterm analysis
    """
    # Your existing AI overview code...
    
    # ADD THIS: Check for chart emoji reaction (keyterm analysis)
    if event.get("reaction") == "chart_with_upwards_trend":
        channel = event.get("item", {}).get("channel")
        timestamp = event.get("item", {}).get("ts")
        
        if not channel or not timestamp:
            return
        
        try:
            # Generate keyterm analysis
            top_keyterms = keyterm_analyzer.get_top_keyterms(limit=10, days_back=7)
            
            if not top_keyterms.empty:
                keyterm_text = "*📊 Top Keyterms (Last 7 Days)*\n\n"
                for _, row in top_keyterms.head(10).iterrows():
                    keyterm_text += f"• *{row['term']}*: {row['total_frequency']} occurrences\n"
                
                # Get context for top term
                if len(top_keyterms) > 0:
                    top_term = top_keyterms.iloc[0]['term']
                    context = keyterm_analyzer.get_keyterm_context(top_term, limit=2)
                    if context:
                        keyterm_text += f"\n*Recent context for '{top_term}':*\n"
                        for ctx in context[:2]:
                            keyterm_text += f"• _{ctx['context'][:100]}..._\n"
                
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=timestamp,
                    text=keyterm_text
                )
                print("[Reaction Handler] Posted keyterm analysis")
            else:
                client.chat_postMessage(
                    channel=channel,
                    thread_ts=timestamp,
                    text="📊 No keyterm data available yet. Keep monitoring!"
                )
                
        except Exception as e:
            print(f"[Reaction Handler] Error generating keyterm analysis: {e}")

# 4. Add a daily report function
def generate_daily_keyterm_report():
    """Generate daily keyterm report"""
    try:
        top_keyterms = keyterm_analyzer.get_top_keyterms(limit=20, days_back=1)
        
        if not top_keyterms.empty:
            report_text = "*📊 Daily Keyterm Report*\n\n"
            report_text += f"*Top keyterms from the last 24 hours:*\n"
            
            for _, row in top_keyterms.head(15).iterrows():
                report_text += f"• *{row['term']}*: {row['total_frequency']} occurrences\n"
            
            print("\n" + "="*50)
            print("DAILY KEYTERM REPORT")
            print("="*50)
            print(report_text)
            print("="*50)
            
            # Optionally send to Slack
            # You can add code here to send the report to a Slack channel
            
        else:
            print("No keyterms found for today's report")
            
    except Exception as e:
        print(f"Error generating daily report: {e}")

# 5. Simple testing function
def test_keyterm_analysis():
    """Test the keyterm analysis with sample data"""
    analyzer = KeytermAnalyzer()
    
    # Test with sample political text
    sample_text = """
    Jersey City mayoral race is heating up with candidates like Mussab Ali and Steven Fulop. 
    The Board of Education elections are also important for local governance.
    Many residents are concerned about housing costs and development projects.
    City council meetings have been discussing budget allocations and infrastructure improvements.
    """
    
    analyzer.store_keyterms(
        text=sample_text,
        source_type='test',
        source_id='sample_001',
        post_title='Test Post About Jersey City Politics',
        subreddit='jerseycity'
    )
    
    print("Test keyterms stored!")
    
    # Show results
    top_keyterms = analyzer.get_top_keyterms(limit=10)
    print("Top keyterms:")
    for _, row in top_keyterms.iterrows():
        print(f"  {row['term']}: {row['total_frequency']} occurrences")

if __name__ == "__main__":
    print("Testing keyterm analysis...")
    test_keyterm_analysis()
    
    print("\nGenerating sample report...")
    generate_daily_keyterm_report()
    
    print("\nIntegration guide complete!")
    print("To integrate with your bot:")
    print("1. Add the keyterm_analyzer import to your bot.py")
    print("2. Initialize the analyzer in your main function")
    print("3. Add keyterm analysis calls in your reddit_item_producer")
    print("4. Add keyterm reaction handling in your Slack handler")
    print("5. Optionally add daily reporting") 