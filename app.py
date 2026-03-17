import streamlit as st
import datetime
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io

# --- 📂 フォルダIDの設定（★ここにコピーしたIDを貼る） ---
DRIVE_FOLDER_ID = "1lws8xR_vj5ksuGAmJMsujaE4xBvahNjT?ths=true"

# --- 🌕 潮回り自動計算ロジック ---
def get_tide(target_date):
    base_new_moon = datetime.date(2024, 1, 11)
    lunar_cycle = 29.530588853
    days_passed = (target_date - base_new_moon).days
    lunar_age = (days_passed % lunar_cycle)
    age = int(round(lunar_age)) % 30
    
    if age in [14, 15, 16, 17, 29, 0, 1, 2]: return "大潮"
    elif age in [3, 4, 5, 6, 12, 13, 18, 19, 20, 21, 27, 28]: return "中潮"
    elif age in [7, 8, 9, 22, 23, 24]: return "小潮"
    elif age in [10, 25]: return "長潮"
    elif age in [11, 26]: return "若潮"
    else: return "中潮"

# --- ☁️ クラウド連携（シート＆ドライブ） ---
@st.cache_resource
def init_connection():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    credentials_dict = json.loads(st.secrets["gcp_json"])
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    
    # スプレッドシート用とドライブ用の2つのロボットを起動
    client = gspread.authorize(creds)
    sheet = client.open("釣行記録DB").sheet1
    drive_service = build('drive', 'v3', credentials=creds)
    
    return sheet, drive_service

try:
    sheet, drive_service = init_connection()
    db_connected = True
except Exception as e:
    st.error(f"⚠️ データベースとの連携に失敗しました: {e}")
    db_connected = False

st.title("🎣 釣行記録アプリ")
st.write("現場でサクッと入力！写真もデータもクラウドに完全保存！")

tab1, tab2 = st.tabs(["📝 記録する", "📊 過去の戦歴を見る"])

with tab1:
    date = st.date_input("📅 釣行日", datetime.date.today())
    auto_tide = get_tide(date)
    tide_options = ["大潮", "中潮", "小潮", "長潮", "若潮"]
    default_tide_index = tide_options.index(auto_tide)

    with st.form(key='fishing_log'):
        col_time1, col_time2 = st.columns(2)
        with col_time1: start_time = st.time_input("開始時間", datetime.time(22, 0))
        with col_time2: end_time = st.time_input("終了時間", datetime.time(2, 0))
            
        st.divider()
            
        selected_location = st.selectbox("場所", ["下津井沖", "その他（下に入力）"])
        location_other = st.text_input("「その他」の場所")

        selected_targets = st.multiselect("魚種（複数選択可）", ["メバル", "アオリイカ", "アコウ", "アジ", "カサゴ", "シーバス", "その他（下に入力）"])
        target_other = st.text_input("「その他」の魚種")

        st.divider()
        
        col_tide1, col_tide2 = st.columns(2)
        with col_tide1: tide = st.selectbox("潮回り", tide_options, index=default_tide_index)
        with col_tide2: tide_movements = st.multiselect("潮の動き（複数選択可）", ["満ち潮（上げ）", "引き潮（下げ）", "潮止まり前後"])

        size = st.number_input("最大サイズ (cm)", min_value=0.0, step=0.5)
        bait = st.text_input("ベイト（捕食対象）", placeholder="例：アミ、シラス、バチ、イカなど")

        photo = st.file_uploader("釣果の写真📸", type=['png', 'jpg', 'jpeg'])
        memo = st.text_area("メモ（ヒットルアー、複数釣れた時の状況など）")
        
        submit_button = st.form_submit_button(label='クラウドDBに完全保存！')

    if submit_button:
        final_location = location_other if selected_location == "その他（下に入力）" else selected_location
        targets_list = [t for t in selected_targets if t != "その他（下に入力）"]
        if target_other != "": targets_list.append(target_other)
        final_target = "、".join(targets_list)
        
        time_str = f"{start_time.strftime('%H:%M')}〜{end_time.strftime('%H:%M')}"
        final_tide_movement = "、".join(tide_movements) if tide_movements else "未記録"

        if final_location == "" or final_target == "":
            st.error("⚠️ 場所と魚種はしっかり記録しよう！")
        elif final_tide_movement == "未記録":
            st.error("⚠️ 潮の動きを選択してね！")
        elif db_connected:
            image_url = ""
            if photo is not None:
                try:
                    # ① 画像をメモリ上で準備
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    image_name = f"{timestamp}_{photo.name}"
                    media = MediaIoBaseUpload(io.BytesIO(photo.getvalue()), mimetype=photo.type, resumable=True)
                    
                    # ② ロボットがGoogleドライブにアップロード
                    file_metadata = {'name': image_name, 'parents': [DRIVE_FOLDER_ID]}
                    uploaded_file = drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                    file_id = uploaded_file.get('id')
                    
                    # ③ アプリ上で写真を見れるように権限を開放
                    drive_service.permissions().create(fileId=file_id, body={'type': 'anyone', 'role': 'reader'}).execute()
                    
                    # ④ 直接画像を表示できる魔法のURLを生成
                    image_url = f"https://drive.google.com/uc?id={file_id}"
                except Exception as e:
                    st.error(f"画像のアップロードに失敗しました: {e}")

            # スプレッドシートに書き込むデータ（画像はURLとして保存！）
            row_data = [
                str(date), time_str, final_location, final_target, 
                tide, final_tide_movement, bait, size, memo, image_url
            ]
            
            try:
                sheet.append_row(row_data)
                st.success(f"よし！ {final_location}での記録を「写真付き」でクラウドに完全保存したよ！")
            except Exception as e:
                st.error(f"書き込みエラーが発生しました: {e}")

with tab2:
    st.header("これまでの戦歴")
    
    if db_connected:
        try:
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                st.dataframe(df, use_container_width=True)

                st.divider()
                st.subheader("📸 釣果ギャラリー")
                
                if "画像パス" in df.columns:
                    df_with_images = df[df["画像パス"].fillna("") != ""]
                    
                    if not df_with_images.empty:
                        cols = st.columns(3)
                        for i, (index, row) in enumerate(df_with_images.iterrows()):
                            col_idx = i % 3
                            with cols[col_idx]:
                                img_url = row["画像パス"]
                                # URL（httpから始まる）場合のみ画像を表示
                                if str(img_url).startswith("http"):
                                    caption_text = f"{row.get('日付', '')}\n{row.get('魚種', '')}\n最大{row.get('最大サイズ(cm)', '')}cm\n({row.get('潮の動き', '')})"
                                    st.image(img_url, caption=caption_text, use_container_width=True)
                    else:
                        st.info("写真付きの記録はまだありません。")
            else:
                st.info("まだ記録がありません。タブ1から最初の釣果を登録しよう！")
        except Exception as e:
            st.warning("戦歴の読み込みに失敗しました。")