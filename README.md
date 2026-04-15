# HammerHUD 🔨

HammerHUD is a high-performance, real-time Poker HUD designed specifically for Ignition Casino. It provides dynamic player statistics (VPIP/PFR) and table awareness through low-level WebSocket protocol parsing.

## Key Features

- **Activity-Window Seat Tracking**: Advanced logic that accurately hides eliminated players while keeping active participants visible during hands, even if they haven't acted yet.
- **Auto-Table Detection**: Automatically detects 6-max vs 9-max layouts and aligns HUD badges correctly based on active seat indices.
- **Universal Protocol Support**: Works in both tournament (ante-heavy) and non-tournament phases by leveraging multiple state signals.
- **Real-time Statistics**: Tracks VPIP (Voluntarily Put In Pot), PFR (Pre-Flop Raise), and hands played for every seat at the table.
- **Non-Intrusive Overlay**: Clean, draggable PyQt6 badges that sit precisely over the player slots.

## Tech Stack

- **Language**: Python 3.10+
- **GUI Framework**: PyQt6
- **Memory Reading**: Pymem
- **Process Management**: psutil

## Getting Started

### Prerequisites

- Python installed on your Windows machine.
- Ignition Poker client running.

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/ethmah01/hammerHUD.git
   cd hammerHUD
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the HUD:
   ```bash
   python main.py
   ```

## Configuration

Settings can be adjusted in `ui/settings.py` or through the configuration dict in `main.py`. You can specify:
- `hero_seat`: The seat number where you are positioned (to hide your own HUD stats).
- `table_size`: Default table size (6 or 9).

## Project Structure

- `core/`: Protocol parsing and memory reading logic.
- `ui/`: Overlay management and badge design.
- `parser/`: Session-level statistics tracking and hand logging.
- `main.py`: Entry point and orchestration.

## License

This project is for personal educational use. Use responsibly.
