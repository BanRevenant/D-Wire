import sys
import subprocess

def install_pip():
    try:
        import pip
    except ImportError:
        print("pip not found. Installing pip...")
        subprocess.check_call([sys.executable, '-m', 'ensurepip'])
        print("pip installed successfully.")

def install_dependencies():
    try:
        import pkg_resources
        installed_packages = {pkg.key for pkg in pkg_resources.working_set}
        with open('requirements.txt', 'r') as file:
            required_packages = file.read().splitlines()
        for package in required_packages:
            if package not in installed_packages:
                print(f"Installing {package}...")
                subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                print(f"{package} installed successfully.")
    except ImportError:
        print("Error: Unable to import pkg_resources module.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error installing dependencies: {str(e)}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    install_pip()
    install_dependencies()
    print("Dependencies installed successfully!")
    print("You can now run the bot using: python3 bot.py")
