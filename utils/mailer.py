import smtplib
from email.mime.text import MIMEText
import os

def send_sos_mail(user_name: str, message_content: str) -> bool:
    """
    アプリ内からの緊急SOSをMasterのメールアドレスへ転送する関数。
    """
    # デモ環境では実際にメールは飛ばさず、コンソールに出力してシミュレート
    print(f"--- 🚨 【緊急SOSメール転送シミュレート】 ---")
    print(f"送信元: {user_name}")
    print(f"内容: {message_content}")
    print(f"----------------------------------------")
    
    # 本番用の環境変数が揃っている時だけ実際に送信するロジック
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_PASSWORD")
    master_email = os.getenv("MASTER_EMAIL")
    
    if not all([gmail_user, gmail_password, master_email]):
        return True # デモ用に成功扱いにする
        
    try:
        msg = MIMEText(f"メンバーの {user_name} さんからSOSが届きました。\n\n内容:\n{message_content}")
        msg['Subject'] = f"【Hibi SOS】{user_name}さんからの緊急通知"
        msg['From'] = gmail_user
        msg['To'] = master_email
        
        # GmailのSMTPサーバーを利用して送信
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(gmail_user, gmail_password)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"Mail sending failed: {e}")
        return False