import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go
import warnings
warnings.filterwarnings('ignore')

# ページ設定
st.set_page_config(page_title="地域別観光者数マップ", layout="wide")

# タイトル
st.title("2024年 地域別観光者数の地図表示")

# データ読み込み（Shift_JISでエンコードされている）
@st.cache_data
def load_data():
    # 観光者数データの読み込み
    tourism_data = pd.read_csv('city2024.csv', encoding='shift_jis')
    
    # 座標データの読み込み
    coord_data = pd.read_csv('city_latlon.csv', encoding='shift_jis')
    
    return tourism_data, coord_data

# データ読み込み
tourism_data, coord_data = load_data()

# 月選択ボタン（1-12月）
st.subheader("表示する月を選択してください")
cols = st.columns(12)
selected_month = None

for i in range(12):
    month = i + 1
    with cols[i]:
        if st.button(f"{month}月", key=f"month_{month}"):
            selected_month = month

# セッション状態で選択された月を保持
if 'selected_month' not in st.session_state:
    st.session_state.selected_month = 1

if selected_month is not None:
    st.session_state.selected_month = selected_month

# 選択された月のデータをフィルタリング
month_to_show = st.session_state.selected_month
st.write(f"### {month_to_show}月のデータを表示中")

# 選択された月のデータを抽出
monthly_data = tourism_data[tourism_data['月'] == month_to_show].copy()

# 地域コードでマージ
merged_data = pd.merge(
    monthly_data,
    coord_data,
    on='地域コード',
    how='inner'
)

# PyDeck用にデータを整形
merged_data['観光者数'] = pd.to_numeric(merged_data['人数'], errors='coerce')
merged_data['緯度'] = pd.to_numeric(merged_data['緯度'], errors='coerce')
merged_data['経度'] = pd.to_numeric(merged_data['経度'], errors='coerce')

# 欠損値を除外
map_data = merged_data[['地域名称', '緯度', '経度', '観光者数']].dropna()

# 統計情報を表示
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("総観光者数", f"{map_data['観光者数'].sum():,.0f}人")
with col2:
    st.metric("平均観光者数", f"{map_data['観光者数'].mean():,.0f}人")
with col3:
    st.metric("地域数", f"{len(map_data)}地域")

# PyDeckで地図を表示
if len(map_data) > 0:
    # 観光者数を正規化してサイズに変換（最小100、最大5000）
    max_visitors = map_data['観光者数'].max()
    min_visitors = map_data['観光者数'].min()
    
    if max_visitors > min_visitors:
        map_data['size'] = 100 + (map_data['観光者数'] - min_visitors) / (max_visitors - min_visitors) * 4900
    else:
        map_data['size'] = 1000
    
    # 色も観光者数に応じて変化（緑→黄→赤）
    map_data['color_r'] = ((map_data['観光者数'] - min_visitors) / (max_visitors - min_visitors) * 255).astype(int)
    map_data['color_g'] = (255 - (map_data['観光者数'] - min_visitors) / (max_visitors - min_visitors) * 100).astype(int)
    map_data['color_b'] = 50
    
    # 日本の中心付近を初期ビューに設定
    view_state = pdk.ViewState(
        latitude=map_data['緯度'].mean(),
        longitude=map_data['経度'].mean(),
        zoom=6,
        pitch=0,
    )
    
    # ScatterplotLayerを使用
    layer = pdk.Layer(
        'ScatterplotLayer',
        data=map_data,
        get_position='[経度, 緯度]',
        get_radius='size',
        get_fill_color='[color_r, color_g, color_b, 160]',
        pickable=True,
        auto_highlight=True,
    )
    
    # ツールチップの設定
    tooltip = {
        "html": "<b>{地域名称}</b><br/>観光者数: {観光者数:,}人",
        "style": {
            "backgroundColor": "steelblue",
            "color": "white"
        }
    }
    
    # 地図を表示
    st.pydeck_chart(pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_provider="carto",  # 地図プロバイダー（cartoは無料で使用可能）
        map_style="road"       # 地図スタイル（road=道路地図）
    ))
    
    # 上位10地域のグラフ表示
    st.subheader(f"{month_to_show}月 観光者数トップ10地域")
    
    top10 = map_data.nlargest(10, '観光者数')[['地域名称', '観光者数']].reset_index(drop=True)
    top10.index = top10.index + 1
    
    # Plotlyで棒グラフを作成
    fig = px.bar(
        top10.sort_values('観光者数'),
        x='観光者数',
        y='地域名称',
        orientation='h',
        color='観光者数',
        color_continuous_scale='viridis',
        labels={'観光者数': '観光者数（人）', '地域名称': '地域'},
        height=400
    )
    fig.update_layout(
        showlegend=False,
        yaxis={'categoryorder': 'total ascending'}
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # データテーブルも表示
    st.subheader("トップ10地域の詳細")
    st.dataframe(top10, use_container_width=True)
    
else:
    st.warning("表示するデータがありません。")

# サイドバーに全体統計を表示
with st.sidebar:
    st.header("年間統計")
    
    # 全月の合計
    total_by_region = tourism_data.groupby('地域コード')['人数'].sum().reset_index()
    total_merged = pd.merge(total_by_region, coord_data, on='地域コード', how='inner')
    
    st.metric("年間総観光者数", f"{tourism_data['人数'].sum():,.0f}人")
    st.metric("年間平均（月別）", f"{tourism_data.groupby('月')['人数'].sum().mean():,.0f}人")
    
    # 月別合計の推移グラフ
    monthly_total = tourism_data.groupby('月')['人数'].sum().reset_index()
    monthly_total.columns = ['月', '観光者数']
    
    # Plotlyで折れ線グラフを作成
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(
        x=monthly_total['月'],
        y=monthly_total['観光者数'],
        mode='lines+markers',
        name='観光者数',
        line=dict(color='#1f77b4', width=2),
        marker=dict(size=8)
    ))
    fig_line.update_layout(
        title='月別観光者数の推移',
        xaxis_title='月',
        yaxis_title='観光者数',
        height=200,
        showlegend=False
    )
    
    st.plotly_chart(fig_line, use_container_width=True)
