# 🔄 How to Restart the AI Tutor App

## The app MUST be restarted for the quiz fixes to work!

### Method 1: Manual Restart (Recommended)

1. **Find the terminal running Streamlit**
   - Look for the terminal window that shows Streamlit output
   - You'll see logs like "You can now view your Streamlit app..."

2. **Stop the app**
   - Click on that terminal window
   - Press `Ctrl+C` on your keyboard
   - Wait for it to fully stop

3. **Start it again**
   ```bash
   streamlit run apps/ui.py
   ```

### Method 2: Kill Process & Restart

```bash
# Find and kill the process
pkill -f streamlit

# Start the app
streamlit run apps/ui.py
```

### Method 3: Using the script

```bash
# Stop any running instances
pkill -f streamlit

# Start via script
python scripts/tutor_web.py
```

## ✅ How to Verify It's Working

After restart, test with:

```
create 10 quizzes from the documents
```

### You should see:
- ✅ "I've created a 10-question quiz on **[Your Document Title]**"
- ✅ "Switch to the 🎓 Student Quiz tab"
- ✅ Quiz appears in Student Quiz tab
- ✅ 10 questions (not 8!)
- ✅ Questions about YOUR document content (not about "creating quizzes")

### If you still see OLD behavior:
- ❌ "Creating Quizzes from Documents" as topic
- ❌ "Scroll down to take it" message
- ❌ Only 8 questions

**Then the app has NOT been restarted!**

## 🆘 Still Not Working?

Run this to force a clean restart:

```bash
# Kill all streamlit processes
pkill -9 -f streamlit

# Clear streamlit cache
rm -rf ~/.streamlit/cache

# Restart
cd /home/henry/Projects/ai-tutor
streamlit run apps/ui.py
```

