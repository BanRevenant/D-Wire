#!/bin/bash

# Set the GitHub repository URL and the desired install directory
REPO_URL="https://github.com/BanRevenant/D-Wire.git"
INSTALL_DIR="/opt/bot"
GAME_DIR="/opt/factorio"
SAVE_DIR="/opt/factorio/saves"
MOD_DIR="/opt/factorio/mods"
CONFIG_DIR="/opt/factorio/config"

# Create the install directory if it doesn't exist
sudo mkdir -p $INSTALL_DIR
sudo mkdir -p $GAME_DIR
sudo mkdir -p $SAVE_DIR
sudo mkdir -p $MOD_DIR
sudo mkdir -p $CONFIG_DIR

# Create the verbose.log file in the game directory ( we do this to prevent console error spamming until factorio is installed )
sudo touch $GAME_DIR/verbose.log

# Clone the GitHub repository
sudo git clone $REPO_URL $INSTALL_DIR

# Navigate to the project directory
cd $INSTALL_DIR

# Prompt the user to create a new Discord bot and obtain the token
echo "Before proceeding, please follow these steps to create a new Discord bot and obtain the token:"
echo "1. Go to the Discord Developer Portal: https://discord.com/developers/applications"
echo "2. Click on the 'New Application' button and give your bot a name."
echo "3. In the left sidebar, click on 'Bot' and then click on 'Add Bot'."
echo "4. Under the 'Token' section, click on 'Reset Token' to generate a new token."
echo "5. Copy the generated token and provide it when prompted."
echo ""
read -p "Please enter the bot token: " BOT_TOKEN

# Update the config.json file with the provided bot token
sudo sed -i "s/\"bot_token\": \"x\"/\"bot_token\": \"$BOT_TOKEN\"/" $INSTALL_DIR/config.json

# Run the setup script to install dependencies
sudo python3 setup.py

echo ""
echo "Bot deployment completed!"
echo "To start the bot in the future, follow these steps:"
echo "1. Open a terminal and navigate to the bot directory:"
echo "   cd /opt/bot"
echo "2. Run the bot using the following command:"
echo "   sudo python3 bot.py"
echo ""
echo "Thank you for using the bot deployment script!"

echo ""
read -p "Press Enter to start the bot for the first time..."

# Run the bot
sudo python3 bot.py

