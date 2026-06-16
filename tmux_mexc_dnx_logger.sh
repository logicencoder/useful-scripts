#!/bin/bash

# Function to set the terminal title
set_title() {
    echo -ne "\033]0;DNX_LOGm\007"
}

# Enable mouse support in tmux so you can scroll with your mouse wheel
set_title  # Set the terminal title to 'DNX_LOGm'

# Create a new tmux session named "DNXUSDTm" and run the Python script inside it
tmux new-session -d -s "DNXUSDTm" "tmux setw -g mouse on; python3  base_fetchrealtime_trades_MEXC_API_V3_1ok.py --coin DNX"
# tmux new-session -d -s "DNXUSDTm" "tmux setw -g mouse on; python3 mexc_tickerz_V3m_db1a.py --update 1 --show_info 1 --port 0 --logging 1 --coinpair DNXUSDT --database 1"

# Attach to the "DNXUSDTm" session
tmux attach-session -t "DNXUSDTm"
