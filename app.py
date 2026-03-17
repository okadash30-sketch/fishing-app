import streamlit as st
import datetime
import pandas as pd
import json
import gspread
from google.oauth2.service_account import Credentials
import requests
import base64

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

@st.cache_resource
def init_connection():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    credentials_dict = json.loads(st.secrets["gcp_json"])
    creds = Credentials.from_service_account_info(credentials_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open("釣行記録DB").sheet1

try:
    sheet = init_connection()
    db_connected = True
except Exception as e:
    st.error(f"⚠️ スプレッドシート連携エラー: {e}")
    db_connected = False

st.title("🎣 釣行記録アプリ")
st.write("現場でサクッと入力！最強の爆釣予測AIに向けたデータ収集！")

tab1, tab2 = st.tabs(["📝 記録する", "📊 過去の戦歴を見る"])

with tab1:
    date = st.date_input("📅 釣行日", datetime.date.today())
    auto_tide = get_tide(date)
    tide_options = ["大潮", "中潮", "小潮", "長潮", "若潮"]
    default_tide_index = tide_options.index(auto_tide)

    # ★ フォーム(st.form)を廃止し、リアルタイムに動くUIに変更！
    col_time1, col_time2 = st.columns(2)
    with col_time1: start_time = st.time_input("開始時間", datetime.time(22, 0))
    with col_time2: end_time = st.time_input("終了時間", datetime.time(2, 0))
        
    st.divider()
    
    selected_location = st.selectbox("場所", ["下津井沖", "その他（下に入力）"])
    location_other = st.text_input("「その他」の場所")
    
    st.divider()
    
    # --- 🐟 魚種と匹数のダイナミック入力エリア ---
    st.subheader("🐟 釣果の記録（魚種と匹数）")
    selected_targets = st.multiselect("釣れた魚種を選んでね", ["メバル", "アオリイカ", "アコウ", "アジ", "カサゴ", "シーバス", "その他（下に入力）"])
    
    target_results = [] # 最終的な「メバル(10尾)」などの文字列を貯めるリスト
    
    if selected_targets:
        cols = st.columns(3) # 画面を3分割して綺麗に並べる
        for i, target in enumerate(selected_targets):
            with cols[i % 3]:
                # 「その他」が選ばれたら、名前と匹数を両方聞く
                if target == "その他（下に入力）":
                    other_name = st.text_input("魚種名", key=f"name_{i}")
                    count = st.number_input("匹数", min_value=1, step=1, key=f"count_{i}")
                    if other_name:
                        target_results.append(f"{other_name}({count}尾)")
                # それ以外は匹数だけ聞く
                else:
                    count = st.number_input(f"{target}の匹数", min_value=1, step=1, key=f"count_{i}")
                    target_results.append(f"{target}({count}尾)")
                    
    # スプレッドシートに書き込むための文字列を生成
    final_target = "、".join(target_results)

    st.divider()
    
    col_tide1, col_tide2 = st.columns(2)
    with col_tide1: tide = st.selectbox("潮回り", tide_options, index=default_tide_index)
    with col_tide2: tide_movements = st.multiselect("潮の動き（複数選択可）", ["満ち潮（上げ）", "引き潮（下げ）", "潮止まり前後"])

    size = st.number_input("最大サイズ (cm)", min_value=0.0, step=0.5)
    bait = st.text_input("ベイト（捕食対象）", placeholder="例：アミ、シラス、バチ、イカなど")

    photo = st.file_uploader("釣果の写真📸", type=['png', 'jpg', 'jpeg'])
    memo = st.text_area("メモ（ヒットルアー、複数釣れた時の状況など）")
    
    # 登録ボタン
    submit_button = st.button('クラウドDBに完全保存！', type="primary", use_container_width=True)

    if submit_button:
        final_location = location_other if selected_location == "その他（下に入力）" else selected_location
        time_str = f"{start_time.strftime('%H:%M')}〜{end_time.strftime('%H:%M')}"
        final_tide_movement = "、".join(tide_movements) if tide_movements else "未記録"

        if final_location == "":
            st.error("⚠️ 場所をしっかり記録しよう！")
        elif not target_results:
            st.error("⚠️ 魚種と匹数を入力してね！")
        elif final_tide_movement == "未記録":
            st.error("⚠️ 潮の動きを選択してね！")
        elif db_connected:
            image_url = ""
            if photo is not None:
                try:
                    gas_url = st.secrets["gas_url"]
                    base64_image = base64.b64encode(photo.getvalue()).decode("utf-8")
                    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
                    filename = f"{timestamp}_{photo.name}"
                    
                    payload = {
                        "image": base64_image,
                        "filename": filename,
                        "mimetype": photo.type
                    }
                    
                    response = requests.post(gas_url, json=payload)
                    res_data = response.json()
                    
                    if res_data.get("status") == "success":
                        image_url = res_data.get("url")
                    else:
                        st.error(f"写真の保存に失敗しました: {res_data.get('message')}")
                except Exception as e:
                    st.error(f"画像処理エラー: {e}")

            row_data = [
                str(date), time_str, final_location, final_target, 
                tide, final_tide_movement, bait, size, memo, image_url
            ]
            
            try:
                sheet.append_row(row_data)
                st.success(f"よし！ {final_location}での記録を「君のGoogleドライブ」へ完全保存したよ！")
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
                                if str(img_url).startswith("http"):
                                    if "drive.google.com/uc?id=" in img_url:
                                        img_url = img_url.replace("uc?id=", "thumbnail?id=") + "&sz=w1000"
                                    caption_text = f"{row.get('日付', '')}\n{row.get('魚種', '')}\n最大{row.get('最大サイズ(cm)', '')}cm\n({row.get('潮の動き', '')})"
                                    st.image(img_url, caption=caption_text, use_container_width=True)
                    else:
                        st.info("写真付きの記録はまだありません。")
            else:
                st.info("まだ記録がありません。タブ1から最初の釣果を登録しよう！")
        except Exception as e:
            st.warning("戦歴の読み込みに失敗しました。")