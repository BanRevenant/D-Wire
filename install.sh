#!/bin/bash

# Download the deploy_bot.sh script
curl -sSL https://raw.githubusercontent.com/BanRevenant/D-Wire/master/deploy_bot.sh > deploy_bot.sh

# Make the script executable
chmod +x deploy_bot.sh

# Run the script
bash --init-file deploy_bot.sh
