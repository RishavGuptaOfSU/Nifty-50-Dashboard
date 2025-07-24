# 📊 Nifty-50 Options Trading Dashboard

A comprehensive multi-strategy options trading dashboard for NSE NIFTY 50 index options. This application provides real-time monitoring, automated strategy execution, and interactive visualization of options trading strategies.

## 🚀 Features

- **Multi-Strategy Support**: Manage and monitor multiple trading strategies simultaneously
- **Real-time Dashboard**: Live updates every 2 seconds with auto-refresh functionality
- **Automated Trading**: Automated entry/exit based on configurable triggers and thresholds
- **Strategy Management**: Easy creation, modification, and deletion of trading strategies
- **Live Data Tracking**: Real-time spot price monitoring and options data
- **Trade Logging**: Comprehensive logging of all trades, triggers, and spot prices
- **Interactive UI**: User-friendly Streamlit interface for strategy management
- **Risk Management**: Built-in profit targets and stop-loss mechanisms

## 🏗️ Architecture

The application consists of two main components:

### Backend (`backend.py`)
- **Strategy Engine**: Core trading logic and strategy execution
- **KiteConnect Integration**: Real-time market data and order execution
- **Multi-threading**: Parallel execution of multiple strategies
- **Data Logging**: JSONL-based logging system for trades, triggers, and spot prices
- **State Management**: Persistent strategy state and configuration management

### Frontend (`frontend.py`)
- **Streamlit Dashboard**: Interactive web interface
- **Real-time Monitoring**: Live strategy performance and status tracking
- **Strategy Configuration**: Easy setup and modification of trading parameters
- **Data Visualization**: Charts and tables for trade analysis
- **Manual Controls**: Start/stop strategies and clear logs

## 📋 Requirements

```
streamlit
pandas
python-dotenv
kiteconnect
streamlit-autorefresh
```

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/RishavGuptaOfSU/Nifty-50-Dashboard.git
   cd Nifty-50-Dashboard
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file in the project root:
   ```env
   API_KEY=your_zerodha_api_key
   ACCESS_TOKEN=your_zerodha_access_token
   ```

4. **Create data directory**
   ```bash
   mkdir -p data
   ```

## 🚦 Usage

### Starting the Dashboard
```bash
streamlit run frontend.py
```

### Running Strategies (Backend)
```bash
python backend.py
```

## ⚙️ Configuration

### Strategy Parameters

Each strategy can be configured with the following parameters:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `STRATEGY_NAME` | Display name for the strategy | - |
| `ENTRY_THRESHOLD` | CE + PE entry threshold | 200 |
| `EXIT_PROFIT` | Target profit for exit | 3000 |
| `EXIT_MOVE` | Spot price movement for exit | 180 |
| `STRIKE_OFFSET` | Strike price offset from spot | 100 |
| `INITIAL_TRIGGER_GAP` | Initial trigger level gap | 100 |
| `SUBSEQUENT_TRIGGER_GAP` | Subsequent trigger gap | 100 |
| `EXPIRY_DATE` | Options expiry date (DD-MM-YYYY) | - |
| `CUTOFF_TIME` | Daily cutoff time (HH:MM) | 15:30 |

### Example Strategy Configuration
```json
{
  "strategy_1": {
    "STRATEGY_NAME": "100 OTM",
    "ENTRY_THRESHOLD": 200,
    "EXIT_PROFIT": 3000,
    "EXIT_MOVE": 180,
    "STRIKE_OFFSET": 100,
    "INITIAL_TRIGGER_GAP": 100,
    "SUBSEQUENT_TRIGGER_GAP": 100,
    "EXPIRY_DATE": "31-07-2025",
    "CUTOFF_TIME": "15:30"
  }
}
```

## 📁 Project Structure

```
Nifty-50-Dashboard/
├── backend.py              # Core trading engine
├── frontend.py             # Streamlit dashboard
├── requirements.txt        # Python dependencies
├── README.md              # Project documentation
├── .env                   # Environment variables (create this)
└── data/                  # Data storage directory
    ├── strategies_config.json    # Strategy configurations
    ├── spot_strategy_*.jsonl     # Spot price logs per strategy
    ├── triggers_strategy_*.jsonl # Trigger logs per strategy
    ├── trades_strategy_*.jsonl   # Trade logs per strategy
    └── status_strategy_*.json    # Strategy status files
```

## 📊 Data Files

The application uses several data files for persistence:

- **`strategies_config.json`**: Central configuration for all strategies
- **`spot_strategy_*.jsonl`**: Real-time spot price data for each strategy
- **`triggers_strategy_*.jsonl`**: Trigger setup and execution logs
- **`trades_strategy_*.jsonl`**: Complete trade entry and exit records
- **`status_strategy_*.json`**: Current running status of each strategy

## 🔧 API Integration

The application integrates with **Zerodha KiteConnect API** for:
- Real-time market data
- Options instrument data
- Order placement and management
- Portfolio tracking

Ensure you have valid API credentials and access tokens before running the application.

## 🛡️ Risk Management

The application includes several risk management features:
- **Profit Targets**: Automatic exit when target profit is reached
- **Stop Loss**: Exit on adverse spot price movements
- **Time-based Exit**: Daily cutoff times to prevent overnight exposure
- **Position Tracking**: Real-time monitoring of open positions
- **Trigger Management**: Systematic trigger level management

## 📈 Monitoring

The dashboard provides comprehensive monitoring capabilities:
- **Live Strategy Status**: Real-time status of all strategies
- **Trade History**: Complete record of all executed trades
- **Trigger Levels**: Current and historical trigger levels
- **Spot Price Tracking**: Live NIFTY 50 spot price updates
- **Performance Metrics**: Strategy-wise performance analysis

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading in financial markets involves substantial risk of loss. The authors and contributors are not responsible for any financial losses incurred through the use of this software. Always consult with a qualified financial advisor before making trading decisions.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙋‍♂️ Support

For support and questions, please open an issue in the GitHub repository or contact the maintainers.

---

**Built with ❤️ for algorithmic trading enthusiasts**
