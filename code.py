import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
from PIL import Image
import os

# 💡 AIで画像を解析するためのライブラリ
try:
    import google.generativeai as genai
except ImportError:
    genai = None

st.set_page_config(page_title="AIカロリー管理ダッシュボード", layout="wide")
st.title("📸 AIカロリー管理ダッシュボード 🏃‍♀️")

# --- 1. CSVデータの読み書き設定 ---
CSV_FILE = "calorie_history.csv"

def load_data():
    if os.path.exists(CSV_FILE):
        df = pd.read_csv(CSV_FILE)
        columns = ["日付", "体重", "食べたもの", "摂取カロリー", "運動カロリー", "基礎代謝", "カロリー収支"]
        for col in columns:
            if col not in df.columns:
                df[col] = ""
        if "日付" in df.columns:
            df["日付"] = pd.to_datetime(df["日付"], format='mixed', errors='coerce')
        return df
    else:
        columns = ["日付", "体重", "食べたもの", "摂取カロリー", "運動カロリー", "基礎代謝", "カロリー収支"]
        return pd.DataFrame(columns=columns)

df = load_data()

# --- 2. ユーザー設定（基礎代謝の自動計算） ---
st.sidebar.header("👤 プロフィール設定")
age = st.sidebar.number_input("年齢", value=39, step=1)
height = st.sidebar.number_input("身長 (cm)", value=162.0, step=0.1)
weight = st.sidebar.number_input("体重 (kg)", value=53.0, step=0.1)
gender = st.sidebar.radio("性別", ["男性", "女性"])

if gender == "男性":
    bmr = 13.397 * weight + 4.799 * height - 5.677 * age + 88.362
else:
    bmr = 9.247 * weight + 3.098 * height - 4.33 * age + 447.593
bmr = int(bmr)

st.sidebar.metric("🔥 あなたの基礎代謝", f"{bmr} kcal")

# --- 3. 日々の記録入力 ---
st.markdown("---")
st.subheader("📝 今日の記録")

col1, col2 = st.columns(2)

with col1:
    record_date = st.date_input("日付", datetime.date.today())
    current_weight = st.number_input("今日の体重 (kg)", value=weight, step=0.1)
    food_memo = st.text_input("食べたもの（例: 豚骨ラーメン、プロテインなど）", value="")
    exercise_kcal = st.number_input("運動の消費カロリー (kcal) ※ランニングなど", value=0, step=10)

with col2:
    st.write("🍔 食事の写真をアップロードしてAI推定！")
    
    # SecretsからAPIキーを安全に取得
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = ""
    
    uploaded_file = st.file_uploader("食事の写真を選ぶ", type=["jpg", "jpeg", "png"])
    
    if "ai_kcal" not in st.session_state:
        st.session_state.ai_kcal = 0
    if "ai_comment" not in st.session_state:
        st.session_state.ai_comment = ""
    
    food_kcal = st.number_input("摂取カロリー (kcal)", value=st.session_state.ai_kcal, step=10)

    if uploaded_file is not None and st.button("✨ AIでカロリーを推定する"):
        if genai and api_key:
            try:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel('gemini-2.5-flash')
                image = Image.open(uploaded_file)
                st.image(image, width=300)
                
                with st.spinner("AIが食事を分析中..."):
                    prompt = """
                    この食事の写真を見て、以下の2点を教えてください。
                    1. 推定される総摂取カロリーの数字（半角数字のみ、例: 800）
                    2. 何が何kcalくらいか、およびその内訳の簡単な解説（日本語で3〜4行程度）

                    出力形式は必ず以下のようにしてください：
                    ---CAL--
                    [総カロリーの数字]
                    ---COM--
                    [解説コメント]
                    """
                    response = model.generate_content([prompt, image])
                    text_res = response.text
                    
                    if "---CAL--" in text_res and "---COM--" in text_res:
                        parts = text_res.split("---COM--")
                        cal_part = parts[0].replace("---CAL--", "").strip()
                        comment_part = parts[1].strip()
                        
                        estimated_kcal = int(''.join(filter(str.isdigit, cal_part)))
                        st.session_state.ai_kcal = estimated_kcal
                        st.session_state.ai_comment = comment_part
                    else:
                        estimated_kcal = int(''.join(filter(str.isdigit, text_res)))
                        st.session_state.ai_kcal = estimated_kcal
                        st.session_state.ai_comment = text_res
                    
                    st.success(f"推定摂取カロリー: {st.session_state.ai_kcal} kcal やで！")
                    st.rerun()
            except Exception as e:
                st.error(f"画像解析でエラーが出ちゃったわ: {e}")

    if st.session_state.ai_comment:
        st.info(f"💡 **AIの判定内訳・コメント:**\n\n{st.session_state.ai_comment}")

if st.button("💾 記録を保存する"):
    balance = food_kcal - (bmr + exercise_kcal)
    date_str = pd.to_datetime(record_date).strftime('%Y-%m-%d')
    
    new_data = pd.DataFrame([{
        "日付": date_str,
        "体重": current_weight,
        "食べたもの": food_memo,
        "摂取カロリー": food_kcal,
        "運動カロリー": exercise_kcal,
        "基礎代謝": bmr,
        "カロリー収支": balance
    }])
    
    if os.path.exists(CSV_FILE):
        saved_df = pd.read_csv(CSV_FILE)
        saved_df = saved_df[saved_df["日付"] != date_str]
        saved_df = pd.concat([saved_df, new_data], ignore_index=True)
    else:
        saved_df = new_data
        
    saved_df.to_csv(CSV_FILE, index=False)
    st.success("🎉 CSVに記録を保存したで！")
    st.session_state.ai_kcal = 0
    st.session_state.ai_comment = ""
    st.rerun()

# --- 4. グラフ推移確認 ---
st.markdown("---")
st.subheader("📈 グラフで推移を確認")

if not df.empty and "日付" in df.columns:
    df["日付"] = pd.to_datetime(df["日付"], format='mixed', errors='coerce')
    df = df.dropna(subset=["日付"]).sort_values("日付")
    
    view_mode = st.radio("表示単位", ["日別", "週単位（平均）", "月単位（平均）"], horizontal=True)
    
    plot_df = df.copy()
    if view_mode == "週単位（平均）":
        plot_df = plot_df.resample('W', on='日付').mean().reset_index()
        plot_df["表示用日付"] = plot_df["日付"].dt.strftime('%Y-%m-%d')
    elif view_mode == "月単位（平均）":
        plot_df = plot_df.resample('ME', on='日付').mean().reset_index()
        plot_df["表示用日付"] = plot_df["日付"].dt.strftime('%Y年%m月')
    else:
        plot_df["表示用日付"] = plot_df["日付"].dt.strftime('%Y-%m-%d')

    tab1, tab2 = st.tabs(["📊 カロリー収支", "⚖️ 体重推移"])
    
    with tab1:
        fig_cal = px.bar(
            plot_df, x="表示用日付", y=["摂取カロリー", "運動カロリー", "基礎代謝"], 
            barmode="group", title="カロリーのインとアウト"
        )
        fig_cal.add_scatter(
            x=plot_df["表示用日付"], y=plot_df["カロリー収支"], 
            mode='lines+markers', name='カロリー収支 (最終結果)', 
            line=dict(color='#FF0000', width=3)
        )
        fig_cal.update_xaxes(type='category')
        st.plotly_chart(fig_cal, width="stretch")
        
    with tab2:
        fig_weight = px.line(
            plot_df, x="表示用日付", y="体重", markers=True, title="体重の推移",
            line_shape="spline"
        )
        if not plot_df["体重"].empty and plot_df["体重"].notnull().any():
            min_w = plot_df["体重"].min() - 2
            max_w = plot_df["体重"].max() + 2
            fig_weight.update_layout(yaxis_range=[min_w, max_w])
        fig_weight.update_xaxes(type='category')
        st.plotly_chart(fig_weight, width="stretch")
else:
    st.info("💡 記録が入ったら、ここにグラフが表示されるで！")

# --- 5. 日々の記録一覧テーブル ---
st.markdown("---")
st.subheader("📋 過去の記録一覧")

if not df.empty and "日付" in df.columns:
    display_df = df.copy()
    display_df["日付"] = pd.to_datetime(display_df["日付"], errors='coerce').dt.strftime('%Y-%m-%d')
    display_df = display_df.sort_values("日付", ascending=False)
    
    st.dataframe(
        display_df[["日付", "体重", "食べたもの", "摂取カロリー", "運動カロリー", "基礎代謝", "カロリー収支"]],
        hide_index=True,
        width="stretch"
    )
else:
    st.info("💡 記録が保存されたら、ここに一覧表が表示されるで！")
