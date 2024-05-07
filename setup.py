import sys
import subprocess
import os

def install_pip():
    try:
        import pip
    except ImportError:
        print("pip not found. Installing pip...")
        try:
            subprocess.check_call([sys.executable, '-m', 'ensurepip', '--default-pip'])
            print("pip installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error installing pip: {str(e)}")
            sys.exit(1)

def install_dependencies():
    try:
        print("Installing dependencies...")
        with open('requirements.txt', 'r') as file:
            requirements = file.read().splitlines()
        for requirement in requirements:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', requirement])
        print("Dependencies installed successfully.")
    except FileNotFoundError:
        print("requirements.txt file not found.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    install_pip()
    install_dependencies()
    print("Setup completed successfully!")
    print("You can now run the bot using: python3 bot.py")
