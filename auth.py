import hmac
import hashlib
import streamlit as st
from datetime import datetime, timedelta
from streamlit_cookies_controller import CookieController

COOKIE_NAME = "fantasy_cowriter_auth"
COOKIE_EXPIRY_DAYS = 7

controller = CookieController()

def get_auth_token():
    secret_key = st.secrets["GEMINI_API_KEY"]
    app_pwd = st.secrets.get("APP_PASSWORD", "fantasy2026")
    return hmac.new(secret_key.encode(), app_pwd.encode(), hashlib.sha256).hexdigest()

def check_password():
    """Cookie またはパスワード入力で認証を行い、認証済みなら True を返す"""
    expected_token = get_auth_token()
    saved_token = controller.get(COOKIE_NAME)

    # 1. Cookieによる自動認証
    if saved_token == expected_token:
        st.session_state["authenticated"] = True
        return True

    # 2. セッション内の既存認証確認
    if st.session_state.get("authenticated", False):
        return True

    # 3. 未認証時のログインフォーム描画
    st.subheader("🔐 Fantasy Co-Writer ログイン")
    pwd_input = st.text_input("パスワードを入力してください", type="password", key="login_password_field")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        login_btn = st.button("ログイン", type="primary", use_container_width=True)

    if login_btn:
        app_pwd = st.secrets.get("APP_PASSWORD", "fantasy2026")
        if pwd_input == app_pwd:
            st.session_state["authenticated"] = True
            # 7日間の有効期限でCookieを保存
            expires = datetime.now() + timedelta(days=COOKIE_EXPIRY_DAYS)
            controller.set(COOKIE_NAME, expected_token, expires=expires)
            st.rerun()
        else:
            st.error("パスワードが正しくありません。")

    return False

def logout():
    """Cookieとセッションを破棄してログアウト"""
    controller.remove(COOKIE_NAME)
    st.session_state["authenticated"] = False
    st.rerun()