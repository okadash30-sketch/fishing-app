import streamlit as st
import datetime
import pandas as pd
import os

# --- 設定部分 ---
CSV_FILE = 'fishing_data.csv'
IMAGE_DIR = 'images'

if not os.path.exists(IMAGE_DIR):
    os.makedirs(IMAGE_DIR)

st.title("🎣 釣行記録アプリ")
st.write("現場でサクッと入力して、データを蓄積しよう！")

# --- ★新機能：タブで画面を分ける ---
tab1, tab2 = st.tabs(["📝 記録する", "📊 過去の戦歴を見る"])

# === タブ1：入力画面（前回と同じ） ===
with tab1:
    with st.form(key='fishing_log'):
        date = st.date_input("日付", datetime.date.today())
        location = st.text_input("場所", value="下津井沖")
        target = st.selectbox("魚種", ["メバル", "アオリイカ", "アコウ", "アジ", "その他"])
        tide = st.selectbox("潮回り", ["大潮", "中潮", "小潮", "長潮", "若潮"])
        size = st.number_input("サイズ (cm)", min_value=0.0, step=0.5)
        photo = st.file_uploader("釣果の写真📸", type=['png', 'jpg', 'jpeg'])
        memo = st.text_area("メモ（ヒットルアー、潮の動きなど）")
        
        submit_button = st.form_submit_button(label='データベースに保存')

    if submit_button:
        image_path = ""
        if photo is not None:
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            image_name = f"{timestamp}_{photo.name}"
            image_path = os.path.join(IMAGE_DIR, image_name)
            with open(image_path, "wb") as f:
                f.write(photo.getbuffer())

        new_data = pd.DataFrame({
            "日付": [date],
            "場所": [location],
            "魚種": [target],
            "潮回り": [tide],
            "サイズ(cm)": [size],
            "メモ": [memo],
            "画像パス": [image_path]
        })

        if os.path.exists(CSV_FILE):
            existing_data = pd.read_csv(CSV_FILE)
            updated_data = pd.concat([existing_data, new_data], ignore_index=True)
            updated_data.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')
        else:
            new_data.to_csv(CSV_FILE, index=False, encoding='utf-8-sig')

        st.success(f"よし！ {location}での{target}（{size}cm）の記録を保存したよ！")

# === タブ2：振り返り画面 ===
with tab2:
    st.header("これまでの戦歴")
    
    # CSVファイルが存在するかチェック
    if os.path.exists(CSV_FILE):
        # データを読み込む
        df = pd.read_csv(CSV_FILE)
        
        # 1. データを一覧表で表示
        st.dataframe(df, use_container_width=True)

        st.divider() # 区切り線
        st.subheader("📸 釣果ギャラリー")
        
        # 画像パスが空ではない（写真がある）データだけを絞り込む
        df_with_images = df[df["画像パス"].fillna("") != ""]
        
        if not df_with_images.empty:
            # 写真を3列に並べて綺麗に表示するレイアウト
            cols = st.columns(3)
            for i, (index, row) in enumerate(df_with_images.iterrows()):
                col_idx = i % 3
                with cols[col_idx]:
                    img_path = row["画像パス"]
                    if os.path.exists(img_path):
                        # 写真と、その下に日付・魚種・サイズのキャプションを表示
                        st.image(img_path, caption=f"{row['日付']} - {row['魚種']} {row['サイズ(cm)']}cm", use_container_width=True)
        else:
            st.info("写真付きの記録はまだありません。")
    else:
        st.info("まだ記録がありません。タブ1から最初の釣果を登録しよう！")