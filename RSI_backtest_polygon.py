# -*- coding: utf-8 -*-
"""
Created on Sat Dec 24 11:13:27 2022

@author: USER
"""

import streamlit as st 
import pandas_ta as ta
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests 
import pandas as pd
from datetime import date, datetime, timedelta, time
import time




API = api_key = "AI73Oy1KnUYUfHAKsOJLxSmVz9dWFC95"
deflaut_date = date.today() - timedelta(100)
min_date =  date.today() - timedelta(365)
max_date =  date.today()- timedelta(1)


def drawndown(trade_result_log):
    max_return, list_drawn_down  = [100], []
    for index,row in trade_result_log.iterrows():
        max_return.append(row["accumulated_return"])
        drawn_down = (row["accumulated_return"] - max(max_return))/max(max_return)
        list_drawn_down.append(drawn_down)
    return list_drawn_down


def get_data(symbol, end_date, start_date, interval=15):
    url = "https://api.polygon.io/v2/"
    symbol = symbol.upper()
    time_frame = "minute"
    limit = 50000
    sort = "desc"
    all_data = []  # Initialize an empty list to store all data


    # Loop to fetch data in 2-month intervals
    while start_date <= end_date:
        next_month_start = start_date + timedelta(days=60)  # 2 months later
        fetch_end_date = min(next_month_start - timedelta(days=1), end_date)

        print(f"Downloading {start_date.strftime('%Y-%m-%d')} to {fetch_end_date.strftime('%Y-%m-%d')} {symbol} Data")

        # Create the request URL
        request_url = f"{url}aggs/ticker/{symbol}/range/{interval}/{time_frame}/{start_date.strftime('%Y-%m-%d')}/{fetch_end_date.strftime('%Y-%m-%d')}?adjusted=true&sort={sort}&limit={limit}&apiKey={API}"
        data = requests.get(request_url).json()

        if "results" in data:
            all_data.extend(data["results"])

        # Update start_date for next iteration
        start_date = next_month_start

        # Wait for 15 seconds before the next API call
        # time.sleep(15)

    if len(all_data) == 0:
        print("No data")
        return None

    return all_data



### Streamlit ###


st.title('RSI (相對強弱指標) 指標回測')
ticker = st.sidebar.text_input("輸入美國股票代碼 👇", value="AAPL")
time_interval_selection = ["5分鐘", "15分鐘", "1小時", "4小時"]
time_interval_select = st.sidebar.selectbox("選擇交易時間段", time_interval_selection)

if time_interval_select == "5分鐘":
    time_interval = 5 

elif time_interval_select == "15分鐘":
    time_interval = 15 
    
elif time_interval_select == "1小時":
    time_interval = 60 
    
elif time_interval_select == "4小時":
    time_interval = 240 


start_date = st.sidebar.date_input("開始日期（此版本最長為1年）", value=deflaut_date, min_value = min_date, max_value=max_date)
rsi_length = st.sidebar.slider("RSI Length", min_value=1, max_value=30, value=14)


interval = int(time_interval)
end_date = date.today()
# day_range = (end_date - start_date).days #datatime to days
list_bars, bar = [],[]
list_bars = get_data(ticker, end_date, start_date, interval =interval)


df = pd.DataFrame(list_bars)
df["datetime"] = pd.to_datetime(df["t"], unit="ms")
df.set_index("datetime", inplace=True)
df = df [["o","h","l","c","v","n"]]
df.columns = ["Open","High","Low","Close","Volume","Transaction"]
    
# #convert Time zone to E.T time 
df.index = df.index.tz_localize('UTC').tz_convert('US/Eastern')

# Filter data to only include trading hours (9:30 AM to 4:00 PM)
df = df.between_time('09:30', '16:00')

df.sort_index(ascending=True, inplace=True)
df["rsi"] = ta.rsi(df.Close, length=rsi_length)
df.dropna(inplace=True)



st.write(f"從 {start_date} 到 {end_date} 的測試數據，總共有 {len(df)} 行數據")
with st.expander("點擊以展開", expanded=False):
    st.write(f"總共有 {len(df)} 行數據")
    st.dataframe(df)

#RSI Signal 
col1, col2, col3, col4 =st.columns([1.3,1,1.3,1])
with col1:
    st.markdown("RSI 下穿（買入）:")
with col2:
    rsi_under = st.number_input("RSI Under:",min_value=10, max_value=50, value=30, label_visibility="collapsed")
with col3:
    st.markdown("RSI 上穿（賣出）:")
with col4:
    rsi_over = st.number_input("3", min_value=50, max_value=90, value=70, label_visibility="collapsed")

#calculate rsi signal
conditions = [(df["rsi"]<rsi_under)&(df["rsi"].shift()>rsi_under), (df["rsi"]>rsi_over)&(df["rsi"].shift()<rsi_over)]
actions = ["buy","sell"]
df["signal"] = np.select(conditions, actions) 
df["Adjusted_signal"] = df["signal"].shift() #buy or sell at next open 
df.dropna(inplace=True)

#check crossover
position = False 
list_open_date, list_close_date = [],[]
list_open_price, list_close_price = [],[]
list_order_type = []

for index,row in df.iterrows():
    if not position:
        if row["Adjusted_signal"] != "0":
            order_type = row["Adjusted_signal"]
            list_open_date.append(index)
            list_open_price.append(row["Open"])
            list_order_type.append(order_type)
            position = True
    if position:
        if (row["Adjusted_signal"] != "0") & (row["Adjusted_signal"] != order_type):
            list_close_date.append(index)
            list_close_price.append(row["Open"])  
            position = False

if position: #for position not close at the end 
    list_close_date.append(df.index[-1])
    list_close_price.append(df["Open"].iloc[-1])  
    
trade_result_log = pd.DataFrame({"open_date":list_open_date, "close_date":list_close_date, 
                   "open_price":list_open_price,"close_price":list_close_price,
                  "order_type":list_order_type}).set_index("open_date")

rsi_result = pd.concat([df, trade_result_log ], axis = 1)

#Calculate result statistics  


conditions = [(trade_result_log["order_type"] == "buy"), (trade_result_log["order_type"] == "sell")]
actions = [((trade_result_log["close_price"] - trade_result_log["open_price"])/trade_result_log["open_price"]), 
           (trade_result_log["open_price"] - trade_result_log["close_price"])/trade_result_log["open_price"]]
trade_result_log["trade_return"] = np.select(conditions, actions) 

if len(trade_result_log) > 0:
    accumulated_return = 100
    list_accumulated_return = []  
    for index,row in trade_result_log.iterrows():
        accumulated_return = (1+row["trade_return"]) *accumulated_return
        list_accumulated_return.append(accumulated_return)

    trade_result_log["accumulated_return"] = list_accumulated_return

    final_result = trade_result_log["accumulated_return"][-1] -100



    testing_period = (df.index[-1] - df.index[0])/np.timedelta64(1, 'D')
    number_of_trade = (len(trade_result_log))

    win_rate = (len(trade_result_log[trade_result_log["trade_return"] >0])/number_of_trade)
    loss_rate = (len(trade_result_log[trade_result_log["trade_return"] <0])/number_of_trade)
    win_loss_ratiio = win_rate/loss_rate

    best_trade = max(trade_result_log["trade_return"])*100
    worst_trade = min(trade_result_log["trade_return"])*100
    Longest_trade_holding = max((trade_result_log["close_date"] - trade_result_log.index)/np.timedelta64(1, 'D'))

    # Handle ZeroDivisionError for reward_ratio
    if len(trade_result_log[trade_result_log["trade_return"] > 0]) != 0:
        reward_ratio = sum(trade_result_log.loc[trade_result_log['trade_return'] > 0]["trade_return"]) / len(trade_result_log[trade_result_log["trade_return"] > 0])
    else:
        reward_ratio = 0

    # Handle ZeroDivisionError for risk_ratio
    if len(trade_result_log[trade_result_log["trade_return"] < 0]) != 0:
        risk_ratio = sum(trade_result_log.loc[trade_result_log['trade_return'] < 0]["trade_return"]) / len(trade_result_log[trade_result_log["trade_return"] < 0])
    else:
        risk_ratio = 0

    # Handle ZeroDivisionError for risk_reward_ratio
    if risk_ratio != 0:
        risk_reward_ratio = reward_ratio / (-risk_ratio)
    else:
        risk_reward_ratio = 0
    max_dawndown = min(drawndown(trade_result_log))*100

    tab1, tab2, tab3 = st.tabs(["統計資料", "股票圖表", "交易結果日誌"])


    with tab1:
        st.header("總計")
        col1, col2, col3= st.columns([1,1,1])
        with col1:
            st.metric(
                "總結果",
                f"{final_result:.2f}%")
            st.metric(
                "最大回撤",
                f"{max_dawndown:.2f}%")
        with col2:
            st.metric(
                "總勝/敗率",
                f"{win_loss_ratiio:.2f}")

        with col3:
            st.metric(
            "風險/報酬比率",
            f"{risk_reward_ratio:.2f}")
            st.metric(
            "交易次數",
            f"{number_of_trade:.0f}")

        st.header("單一交易")
        col1, col2, col3= st.columns([1,1,1])
        with col1:
            st.metric(
                "最佳交易",
                f"{best_trade:.2f}%")

        with col2:
            st.metric(
                "最差交易",
                f"{worst_trade:.2f}%")
    
        with col3:
            st.metric(
            "最長交易持有期（天）",
            f"{Longest_trade_holding:.1f}")


        st.title("回測策略")
        with st.expander("入市條件", expanded=False):
            st.text(f"當 RSI 下穿 {rsi_under} 時，在下一個開盤價買入")
            st.text(f"當 RSI 上穿 {rsi_over} 時，在下一個開盤價賣出")
        
        with st.expander("平倉、止損、止盈", expanded=False):
        
            st.text("平倉: 一旦 RSI 出現相反信號")
            st.text("止損: 無")
            st.text("止盈: 無")
        
        with st.expander("交易費用", expanded=False):
            st.text("無交易費用")
                    
    with tab2:
        # Create subplots and mention plot grid size
        fig_ticker = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                vertical_spacing=0.03, subplot_titles=('OHLC', 'Volume'), 
                row_width=[0.2, 0.7])
        

        fig_ticker.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"]) )    # Plot OHLC on 1st row
        fig_ticker.update_layout(xaxis_rangeslider_visible=False) # Do not show OHLC's rangeslider plot 
        st.plotly_chart(fig_ticker)   

        

        fig = px.line(
            trade_result_log,
            x="close_date",
            y="accumulated_return")
        st.plotly_chart(fig) 

    with tab3:
        st.dataframe(trade_result_log) 
        st.download_button(
        label="Download trade result log",
        data=pd.DataFrame(trade_result_log).to_csv(index=True),
        file_name='trade_result_log.csv',
        mime='text/csv',
        )

else:
    st.write("沒有交易訊號")
    st.stop()


#disclaimer
with st.expander("免責聲明", expanded=False):
    st.markdown("""
    </small>

    本應用程式及其內容僅供教育和資訊目的使用，不應被視為財務或投資建議。在採取任何財務或投資行動之前，您應諮詢合格的財務或投資顧問。
    開發者不對因使用或依賴本應用程式內容而產生的任何損失或損害承擔責任。交易和投資固有風險，包括但不限於資本損失的風險。
    本應用程式中提到的交易策略和指標是基於過去的數據和經驗，並不保證未來的表現或利潤。您應自行評估所有風險，並根據自己的財務狀況和投資目標謹慎行事。
    本應用程式的數據來自第三方，我們不保證其準確性。
    使用或依賴本應用程式內容即表示您接受本免責聲明的所有條款和條件。如果您不同意這些條款，請不要使用或依賴本應用程式或其內容。
    </small>
    """, unsafe_allow_html=True)

