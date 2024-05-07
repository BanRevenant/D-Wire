import sys
import subprocess

def install_dependencies():
    with open('requirements.txt', 'r') as file:
        dependencies = file.read().splitlines()

    for dependency in dependencies:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', dependency])

if __name__ == '__main__':
    install_dependencies()
    print("Dependencies installed successfully!")
    print("You can now run the bot using: python bot.py")