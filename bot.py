import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import asyncio
import traceback
import logging
import sys
from getpass import getpass
from typing import Optional
import time
import subprocess
import traceback
from config_manager import ConfigManager
from logger import setup_logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Set up logger
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
logger = setup_logger('bot', os.path.join(log_dir, 'bot.log'))

def check_service_exists():
    """Check if the D-Wire service already exists"""
    service_path = '/etc/systemd/system/dwire.service'
    return os.path.exists(service_path)

def is_running_as_service():
    """Check if bot is running as a systemd service"""
    try:
        return os.getppid() == 1
    except:
        return False

def setup_system_service():
    """Setup systemd service for the bot"""
    try:
        print("\n=== Starting D-Wire Service Setup ===")
        
        # Debug - Current directory and user
        print(f"Current directory: {os.getcwd()}")
        print(f"Running as user: {os.getenv('USER')}")
        print(f"Effective UID: {os.geteuid()}")

        # 1. Create required directories
        required_dirs = [
            '/var/log/dwire',
            '/usr/local/bin'
        ]
        
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True)
                print(f"Created directory: {dir_path}")
            current_perms = oct(os.stat(dir_path).st_mode)[-3:]
            print(f"Permissions for {dir_path}: {current_perms}")
            os.chmod(dir_path, 0o755)
            new_perms = oct(os.stat(dir_path).st_mode)[-3:]
            print(f"Updated permissions for {dir_path}: {new_perms}")

        # 2. Create service file
        service_template = f"""[Unit]
Description=D-Wire Discord Bot
After=network.target

[Service]
Type=simple
User={os.getenv('USER')}
WorkingDirectory={os.path.abspath(os.path.dirname(__file__))}
ExecStart=/usr/bin/python3 {os.path.abspath(__file__)}
Restart=always
RestartForceExitStatus=42
RestartSec=5
StandardOutput=append:/var/log/dwire/bot.log
StandardError=append:/var/log/dwire/error.log

[Install]
WantedBy=multi-user.target
"""
        
        service_path = '/etc/systemd/system/dwire.service'
        with open(service_path, 'w') as f:
            f.write(service_template)
        os.chmod(service_path, 0o644)
        print(f"Created service file: {service_path}")
        
        # 3. Create control commands with detailed debugging
        commands = {
            'start_bot': """#!/bin/bash
        systemctl start dwire.service
        systemctl status dwire.service""",

            'stop_bot': """#!/bin/bash
        systemctl stop dwire.service
        systemctl status dwire.service""",

            'listen_bot': """#!/bin/bash
        echo "=== D-Wire Bot Console ==="
        echo "Press Ctrl+C to stop viewing the console (bot will continue running)"
        echo "Starting console view..."
        echo ""
        tail -f /var/log/dwire/bot.log"""
        }

        print("\n=== Creating Control Commands ===")
        for cmd_name, cmd_content in commands.items():
            cmd_path = f'/usr/local/bin/{cmd_name}'
            try:
                print(f"\nCreating command: {cmd_name}")
                print(f"Writing to path: {cmd_path}")
                print(f"Content length: {len(cmd_content)} bytes")
                
                with open(cmd_path, 'w') as f:
                    f.write(cmd_content)
                print(f"File written successfully")
                
                # Check file exists and contents
                if os.path.exists(cmd_path):
                    with open(cmd_path, 'r') as f:
                        saved_content = f.read()
                    print(f"File exists with size: {os.path.getsize(cmd_path)} bytes")
                    print(f"Content verification: {'MATCH' if saved_content == cmd_content else 'MISMATCH'}")
                else:
                    print(f"ERROR: File does not exist after creation!")
                
                # Set and verify permissions
                os.chmod(cmd_path, 0o755)
                current_perms = oct(os.stat(cmd_path).st_mode)[-3:]
                print(f"File permissions set to: {current_perms}")
                
            except Exception as e:
                print(f"Error creating {cmd_name}: {str(e)}")
                print(f"Full error:\n{traceback.format_exc()}")
                raise

        print("\n=== Verifying Commands ===")
        for cmd_name in commands.keys():
            cmd_path = f'/usr/local/bin/{cmd_name}'
            if os.path.exists(cmd_path):
                perms = oct(os.stat(cmd_path).st_mode)[-3:]
                print(f"{cmd_name}: EXISTS (permissions: {perms})")
                # Try to list using subprocess
                try:
                    result = subprocess.run(['ls', '-l', cmd_path], capture_output=True, text=True)
                    print(f"ls output: {result.stdout.strip()}")
                except Exception as e:
                    print(f"Error checking {cmd_name}: {str(e)}")
            else:
                print(f"{cmd_name}: MISSING")

        # 4. Setup and start service
        print("\n=== Configuring Systemd Service ===")
        try:
            subprocess.run(['systemctl', 'daemon-reload'], check=True)
            print("Systemd daemon reloaded")
            
            subprocess.run(['systemctl', 'enable', 'dwire.service'], check=True)
            print("Service enabled")
            
            # Remove the automatic restart
            # subprocess.run(['systemctl', 'restart', 'dwire.service'], check=True)
            # print("Service restarted")
            
        except subprocess.CalledProcessError as e:
            print(f"Error during systemd configuration: {str(e)}")
            raise

        print("\n=== Setup Complete ===")
        print("Available commands:")
        print("  start_bot  - Start the D-Wire bot")
        print("  stop_bot   - Stop the D-Wire bot")
        print("  listen_bot - View bot console output")
        print("\nService is ready but not running. Use 'start_bot' to start the service.")
        
        return True

    except Exception as e:
        print(f"\n=== Setup Failed ===")
        print(f"Error during setup: {str(e)}")
        print(f"Full error: {traceback.format_exc()}")
        return False

def check_token_setup():
    """Check if Discord token is set and valid"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            token = config.get('discord', {}).get('bot_token', '')
            if len(token) < 30 or token == 'your-bot-token-here':
                return False
        return True
    except Exception:
        return False

def ensure_service_running():
    """Make sure bot is running as a service"""
    print("\n=== Checking D-Wire Service Status ===")
    
    # Only proceed if running as root
    if os.geteuid() != 0:
        print("Not running as root, skipping service setup")
        return

    # Initialize config first
    if not initialize_config():
        print("\nFailed to initialize configuration.")
        print("Please ensure your config.json is set up correctly before running as a service.")
        sys.exit(1)

    if is_running_as_service():
        print("Already running as a service")
        return

    # Check if commands exist
    commands_exist = all(os.path.exists(f"/usr/local/bin/{cmd}") 
                        for cmd in ['start_bot', 'stop_bot', 'listen_bot'])
    
    if not commands_exist:
        print("Commands missing - forcing setup...")
        setup_system_service()
        print("\nSetup complete. Please use 'start_bot' to start the service.")
        sys.exit(0)  # Exit after setup

    # If service exists but not running
    if check_service_exists():
        print("Service exists but not running. Starting service...")
        try:
            subprocess.run(['systemctl', 'start', 'dwire.service'], check=True)
            print("Service started successfully")
        except subprocess.CalledProcessError as e:
            print(f"Failed to start service: {e}")
        sys.exit(0)  # Exit after starting service
    else:
        print("Service doesn't exist. Setting up D-Wire service...")
        setup_system_service()
        print("\nSetup complete. Please use 'start_bot' to start the service.")
        sys.exit(0)  # Exit after setup

    # Check if commands exist
    commands_exist = all(os.path.exists(f"/usr/local/bin/{cmd}") 
                        for cmd in ['start_bot', 'stop_bot', 'listen_bot'])
    
    if not commands_exist:
        print("Commands missing - forcing setup...")
        setup_system_service()
        return

    # If service exists but not running
    if check_service_exists():
        print("Service exists but not running. Starting service...")
        try:
            subprocess.run(['systemctl', 'start', 'dwire.service'], check=True)
            print("Service started successfully")
        except subprocess.CalledProcessError as e:
            print(f"Failed to start service: {e}")
        sys.exit(0)
    else:
        print("Service doesn't exist. Setting up D-Wire service...")
        setup_system_service()
        sys.exit(0)

def initialize_config():
    """Initialize config file and validate bot token"""
    config_path = 'config.json'
    default_config_path = 'default.config.json'
    
    # Check if config.json exists, if not rename default
    if not os.path.exists(config_path):
        if os.path.exists(default_config_path):
            try:
                os.rename(default_config_path, config_path)
                print('Renamed default.config.json to config.json')
            except Exception as e:
                print(f'Failed to rename config file: {e}')
                return False
        else:
            print('No config file found and no default config to rename')
            return False
            
    # Load and validate config
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        bot_token = config.get('discord', {}).get('bot_token', '')
        
        # Check if token needs to be set
        if len(bot_token) < 30 or bot_token == 'your-bot-token-here':
            print("Discord bot token not found or invalid.")
            token = getpass("Please enter your Discord bot token or edit the config.json file: ")
            
            if len(token) >= 30:
                if 'discord' not in config:
                    config['discord'] = {}
                config['discord']['bot_token'] = token
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                print('Bot token updated in config')
                return True
            else:
                print("Invalid token length. Please enter a valid Discord bot token.")
                return False
                
        return True
        
    except Exception as e:
        print(f'Error initializing config: {e}')
        return False

# Initialize config and check for bot token
if not initialize_config():
    logger.error("Failed to initialize config. Exiting.")
    sys.exit(1)

# Initialize ConfigManager
config_manager = ConfigManager('config.json')

class CogWatcher(FileSystemEventHandler):
    def __init__(self, bot):
        self.bot = bot
        self.last_reload = {}
        self.reload_lock = asyncio.Lock()
        
    async def reload_cog(self, path):
        async with self.reload_lock:  # Ensure only one reload happens at a time
            try:
                relative_path = os.path.relpath(path)
                if relative_path.startswith('cogs/') and relative_path.endswith('.py'):
                    cog_name = relative_path[:-3].replace('/', '.')
                    current_time = time.time()
                    
                    # Check if we've reloaded this cog recently
                    if cog_name in self.last_reload:
                        if current_time - self.last_reload[cog_name] < 2:  # 2 second cooldown
                            return
                            
                    self.last_reload[cog_name] = current_time
                    
                    try:
                        await self.bot.unload_extension(cog_name)
                    except:
                        pass  # Ignore unload errors
                        
                    await asyncio.sleep(0.5)  # Give a small delay
                    
                    try:
                        await self.bot.load_extension(cog_name)
                        logger.info(f"Reloaded {cog_name}")
                    except Exception as e:
                        logger.error(f"Failed to reload {cog_name}: {e}")
                        
            except Exception as e:
                logger.error(f"Error in reload_cog: {e}")

    def on_modified(self, event):
        if event.src_path.endswith('.py') and 'cogs' in event.src_path:
            asyncio.run_coroutine_threadsafe(
                self.reload_cog(event.src_path), 
                self.bot.loop
            ).result()  # Wait for the result

class AutoReconnectBot(commands.Bot):
    async def setup_hook(self):
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # Initial delay in seconds
        
        # Auto-update application ID in config
        if self.application_id:
            logger.info(f'Setting application ID in config: {self.application_id}')
            self.config_manager.set('discord.application_id', str(self.application_id))
            self.config_manager.save()

    async def on_guild_join(self, guild):
        """Handle bot joining a new guild"""
        logger.info(f'Bot joined guild: {guild.name} (ID: {guild.id})')
        
        # Update server ID and owner ID in config
        logger.info(f'Setting server ID in config: {guild.id}')
        self.config_manager.set('discord.server_id', str(guild.id))
        
        logger.info(f'Setting owner ID in config: {guild.owner_id}')
        self.config_manager.set('discord.owner_id', str(guild.owner_id))
        
        self.config_manager.save()
        
        # Trigger setup for the new guild
        await self.setup_guild(guild)

    async def setup_guild(self, guild):
        """Setup roles and channels for a new guild"""
        try:
            # Initial permissions check
            permissions_ok, issues = await check_bot_permissions(guild)
            if not permissions_ok:
                logger.warning(f"Permission issues detected: {issues}")
            
            # Set up roles and channels
            role_ids = await setup_roles(guild)
            channel_ids = await setup_channels(guild)
            
            # Update config with new IDs
            if role_ids:
                for key, role_id in role_ids.items():
                    self.config_manager.set(f'discord.{key}', role_id)
            
            if channel_ids:
                for key, channel_id in channel_ids.items():
                    self.config_manager.set(f'discord.{key}', channel_id)
            
            self.config_manager.save()
            
        except Exception as e:
            logger.error(f'Error during guild setup: {e}')
            traceback.print_exc()

    async def close(self):
        self.reconnect_attempts = 0
        await super().close()

    async def connect(self, *, reconnect=True):
        while True:
            try:
                await super().connect(reconnect=True)
                self.reconnect_attempts = 0
                self.reconnect_delay = 5
                break
            except discord.GatewayNotFound:
                logger.error("Discord gateway not found. Retrying...")
            except discord.ConnectionClosed as e:
                if e.code == 1000:  # Normal closure
                    self.reconnect_attempts += 1
                    if self.reconnect_attempts >= self.max_reconnect_attempts:
                        logger.error(f"Failed to reconnect after {self.max_reconnect_attempts} attempts")
                        raise
                    
                    logger.warning(f"Connection closed normally. Attempting reconnect #{self.reconnect_attempts}")
                    await asyncio.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(300, self.reconnect_delay * 2)  # Exponential backoff, max 5 minutes
                else:
                    logger.error(f"Connection closed with code {e.code}")
                    raise
    async def track_role_assignment(self, member: discord.Member, role: discord.Role):
        """Track when a role is assigned to a member"""
        try:
            assignments_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "role_assignments.json")
            assignments = {}
            
            if os.path.exists(assignments_file):
                with open(assignments_file, 'r') as f:
                    assignments = json.load(f)
            
            # Add the member to the role's assignments
            role_assignments = assignments.get(str(role.id), [])
            if str(member.id) not in role_assignments:
                role_assignments.append(str(member.id))
                assignments[str(role.id)] = role_assignments
                
                with open(assignments_file, 'w') as f:
                    json.dump(assignments, f, indent=2)
                
                logger.debug(f"Tracked role assignment: {role.name} -> {member.name}")
            
        except Exception as e:
            logger.error(f"Error tracking role assignment: {str(e)}")            

# Start the bot
intents = discord.Intents.all()
intents.messages = True
intents.message_content = True

bot = AutoReconnectBot(command_prefix='/', intents=intents)
bot.config_manager = config_manager
bot.logger = logger

if config_manager.get('debug_mode', False):
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.WARNING)

async def load_cogs():
    """Load all cogs from the cogs directory."""
    disabled_cogs = config_manager.get('disabled_cogs', [])
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            cog_name = filename[:-3]
            if cog_name not in disabled_cogs:
                try:
                    await bot.load_extension(f'cogs.{cog_name}')
                    logger.info(f'Loaded {filename}')
                except Exception as e:
                    logger.error(f'Failed to load {filename}: {e}')
                    if hasattr(bot, 'error_channel'):
                        await bot.error_channel.send(f'Failed to load {filename}: {e}')
            else:
                logger.info(f'Skipped loading {filename} (disabled)')

async def check_bot_permissions(guild):
    """
    Checks if the bot has all required permissions and proper role hierarchy.
    Returns (bool, list of issues)
    """
    required_permissions = {
        'manage_roles': 'Manage Roles',
        'manage_channels': 'Manage Channels',
        'view_channel': 'View Channels',
        'send_messages': 'Send Messages',
        'embed_links': 'Embed Links',
        'read_message_history': 'Read Message History',
        'manage_messages': 'Manage Messages',
        'add_reactions': 'Add Reactions'
    }
    
    issues = []
    bot_member = guild.get_member(bot.user.id)
    
    # Check bot's permissions
    missing_perms = []
    for perm, perm_name in required_permissions.items():
        if not getattr(bot_member.guild_permissions, perm):
            missing_perms.append(perm_name)
    
    if missing_perms:
        issues.append(f"Missing permissions: {', '.join(missing_perms)}")
    
    # Check if bot is administrator
    if bot_member.guild_permissions.administrator:
        # Bot is admin, no need for hierarchy checks
        return len(issues) == 0, issues
    
    # Only check hierarchy if bot is not an administrator
    if bot_member.top_role.position <= 1:
        issues.append("Bot's role is too low in the hierarchy. Please move the bot's role higher.")
    
    # Only check managed roles if bot is not an administrator
    managed_roles = [
        role for role in guild.roles 
        if role.name in ['Factorio-Admin', 'Factorio-Mod', 'Factorio-User']
    ]
    for role in managed_roles:
        if role.position >= bot_member.top_role.position:
            issues.append(f"Cannot manage '{role.name}' - bot's role must be higher in the hierarchy.")
    
    return len(issues) == 0, issues

async def send_status_message(channel, title, description, color=discord.Color.blue()):
    """Sends a formatted status message to the specified channel"""
    embed = discord.Embed(
        title=title,
        description=description,
        color=color
    )
    try:
        await channel.send(embed=embed)
    except discord.Forbidden:
        logger.error(f"Cannot send messages to channel {channel.name}")
    except Exception as e:
        logger.error(f"Error sending status message: {str(e)}")

async def restore_role_assignments(guild, old_role_id, new_role):
    """Restores role assignments when a role is recreated"""
    try:
        # Load the role assignments file
        assignments_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "role_assignments.json")
        assignments = {}
        
        if os.path.exists(assignments_file):
            with open(assignments_file, 'r') as f:
                assignments = json.load(f)
        
        # Get the list of member IDs for the old role
        member_ids = assignments.get(str(old_role_id), [])
        
        # Reassign the role to all previous members
        success_count = 0
        for member_id in member_ids:
            member = guild.get_member(int(member_id))
            if member:
                try:
                    await member.add_roles(new_role)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to reassign role to member {member_id}: {str(e)}")
        
        # Update the assignments with the new role ID
        assignments[str(new_role.id)] = member_ids
        assignments.pop(str(old_role_id), None)
        
        # Save the updated assignments
        with open(assignments_file, 'w') as f:
            json.dump(assignments, f, indent=2)
        
        logger.info(f"Restored role assignments for {success_count}/{len(member_ids)} members")
        
    except Exception as e:
        logger.error(f"Error restoring role assignments: {str(e)}")

async def track_role_assignment(member, role):
    """Tracks when a role is assigned to a member"""
    try:
        assignments_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "role_assignments.json")
        assignments = {}
        
        if os.path.exists(assignments_file):
            with open(assignments_file, 'r') as f:
                assignments = json.load(f)
        
        # Add the member to the role's assignments
        role_assignments = assignments.get(str(role.id), [])
        if str(member.id) not in role_assignments:
            role_assignments.append(str(member.id))
            assignments[str(role.id)] = role_assignments
            
            with open(assignments_file, 'w') as f:
                json.dump(assignments, f, indent=2)
            
            logger.debug(f"Tracked role assignment: {role.name} -> {member.name}")
            
    except Exception as e:
        logger.error(f"Error tracking role assignment: {str(e)}")

async def setup_roles(guild):
    """
    Sets up required roles for the bot in the specified guild.
    Recreates missing roles and restores assignments if needed.
    Returns a dictionary of role IDs.
    """
    roles = {
        'factorio_admin_role': {
            'name': 'Factorio-Admin',
            'color': discord.Color.red(),
            'permissions': discord.Permissions(
                administrator=True,
                manage_channels=True,
                manage_messages=True,
                manage_roles=True,
                view_channel=True
            ),
            'position_shift': 3
        },
        'factorio_mod': {
            'name': 'Factorio-Mod',
            'color': discord.Color.blue(),
            'permissions': discord.Permissions(
                manage_messages=True,
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            'position_shift': 2
        },
        'factorio_user': {
            'name': 'Factorio-User',
            'color': discord.Color.green(),
            'permissions': discord.Permissions(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            'position_shift': 1
        }
    }
    
    role_ids = {}
    existing_roles = {}
    
    for role_key, config in roles.items():
        should_create = True
        role = None
        old_role_id = None
        
        # Try to get role by stored ID
        stored_role_id = bot.config_manager.get(f'discord.{role_key}_id')
        if stored_role_id:
            try:
                role = guild.get_role(int(stored_role_id))
                if role:
                    should_create = False
                    logger.info(f'Found existing role {role.name} by ID')
                else:
                    old_role_id = stored_role_id
                    logger.warning(f'Stored role with ID {stored_role_id} not found, will recreate')
            except ValueError:
                # Invalid role ID in config, will create new role
                logger.warning(f'Invalid role ID in config for {role_key}, will create new role')
        
        # If no role found by ID, check by name
        if not role:
            role = discord.utils.get(guild.roles, name=config['name'])
            if role:
                should_create = False
                logger.info(f'Found existing role {role.name} by name')
        
        # Create role if it doesn't exist
        if should_create:
            try:
                role = await guild.create_role(
                    name=config['name'],
                    color=config['color'],
                    permissions=config['permissions'],
                    reason="Factorio bot role setup"
                )
                logger.info(f'Created new role: {role.name}')
                
                # If we had an old role ID, restore assignments
                if old_role_id and old_role_id.isdigit():
                    await restore_role_assignments(guild, old_role_id, role)
            except Exception as e:
                logger.error(f'Failed to create role {config["name"]}: {e}')
                continue
        
        # Store role for position adjustment
        existing_roles[role_key] = role
        role_ids[f"{role_key}_id"] = str(role.id)
    
    # Adjust role positions
    try:
        # Sort roles by position_shift
        sorted_roles = sorted(
            existing_roles.items(),
            key=lambda x: roles[x[0]]['position_shift'],
            reverse=True
        )
        
        # Calculate positions
        positions = {
            role: min(
                guild.me.top_role.position - 1,
                guild.me.top_role.position - (len(sorted_roles) - idx)
            )
            for idx, (_, role) in enumerate(sorted_roles)
        }
        
        # Update role positions
        await guild.edit_role_positions(positions=positions)
        logger.info('Role positions updated')
    except Exception as e:
        logger.error(f'Failed to adjust role positions: {e}')
    
    return role_ids

async def setup_channels(guild):
    """
    Sets up required channels for the bot in the specified guild.
    Automatically recreates deleted channels and verifies channel integrity.
    Returns a dictionary of channel IDs.
    """
    # Define channel configurations
    channels = {
        'factorio_general_channel': {
            'name': 'factorio-general',
            'topic': 'General Factorio discussion, commands, and game logs',
            'category_name': 'Factorio',
            'permissions': {
                'view': True,  # Everyone can view
                'admin_only': False
            }
        },
        'factorio_admin_channel': {
            'name': 'factorio-admin',
            'topic': 'Bot updates, errors, and administrative notifications',
            'category_name': 'Factorio',
            'permissions': {
                'view': False,  # Admin only
                'admin_only': True
            }
        }
    }
    
    # Get or create Factorio category
    category = discord.utils.get(guild.categories, name='Factorio')
    if not category:
        try:
            category = await guild.create_category('Factorio')
            logger.info('Created Factorio category')
        except discord.Forbidden:
            logger.error('Missing permissions to create category')
            return {}
        except Exception as e:
            logger.error(f'Error creating category: {e}')
            return {}
    
    # Get role IDs safely
    admin_role = None
    mod_role = None
    user_role = None
    
    try:
        admin_role_id = bot.config_manager.get('discord.factorio_admin_role_id')
        if admin_role_id and admin_role_id.isdigit():
            admin_role = guild.get_role(int(admin_role_id))
            
        mod_role_id = bot.config_manager.get('discord.factorio_mod_id')
        if mod_role_id and mod_role_id.isdigit():
            mod_role = guild.get_role(int(mod_role_id))
            
        user_role_id = bot.config_manager.get('discord.factorio_user_id')
        if user_role_id and user_role_id.isdigit():
            user_role = guild.get_role(int(user_role_id))
    except Exception as e:
        logger.error(f'Error getting roles: {e}')
    
    channel_ids = {}
    
    for channel_key, config in channels.items():
        should_create = True
        channel = None
        
        # First, try to get channel by stored ID
        stored_channel_id = bot.config_manager.get(f'discord.{channel_key}_id')
        if stored_channel_id:
            try:
                if stored_channel_id.isdigit():
                    channel = guild.get_channel(int(stored_channel_id))
                    if channel:
                        should_create = False
                        logger.info(f'Found existing channel {channel.name} by ID')
            except Exception as e:
                logger.warning(f'Error getting channel by ID {stored_channel_id}: {e}')
        
        # If no channel found by ID, check by name in category
        if not channel:
            channel = discord.utils.get(category.channels, name=config['name'])
            if channel:
                should_create = False
                logger.info(f'Found existing channel {channel.name} by name')
        
        # Create channel if it doesn't exist or was deleted
        if should_create:
            try:
                # Set up permissions
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=False
                    )
                }
                
                if user_role:
                    overwrites[user_role] = discord.PermissionOverwrite(
                        view_channel=config['permissions']['view'],
                        send_messages=True,
                        read_message_history=True
                    )
                
                # Add admin and mod role permissions
                if admin_role:
                    overwrites[admin_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True
                    )
                
                if mod_role:
                    overwrites[mod_role] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        read_message_history=True,
                        manage_messages=True
                    )
                
                # Create the channel
                channel = await guild.create_text_channel(
                    name=config['name'],
                    category=category,
                    topic=config['topic'],
                    overwrites=overwrites
                )
                logger.info(f'Created new channel: {channel.name}')
                
                # Send initialization message
                try:
                    await channel.send(f'Channel initialized: {config["topic"]}')
                except Exception as e:
                    logger.warning(f'Could not send initialization message: {e}')
                
            except discord.Forbidden:
                logger.error(f'Missing permissions to create channel {config["name"]}')
                continue
            except Exception as e:
                logger.error(f'Failed to create channel {config["name"]}: {e}')
                continue
        
        # Store/update channel ID in config
        channel_ids[f"{channel_key}_id"] = str(channel.id)
    
    return channel_ids


@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')
    
    # Set application ID in config if not already set
    if bot.application_id:
        current_app_id = bot.config_manager.get('discord.application_id')
        if current_app_id != str(bot.application_id):
            logger.info(f'Setting application ID in config: {bot.application_id}')
            bot.config_manager.set('discord.application_id', str(bot.application_id))
            bot.config_manager.save()
    
    # Get the guild ID from config or set it if not present
    guild_id = bot.config_manager.get('discord.server_id')
    
    # Check if guild_id is a placeholder or invalid
    if not guild_id or guild_id == 'your-server-id' or not guild_id.isdigit():
        if len(bot.guilds) > 0:
            # If no valid guild ID is set and bot is in a guild, use the first guild
            guild = bot.guilds[0]
            logger.info(f'Setting server ID in config: {guild.id}')
            bot.config_manager.set('discord.server_id', str(guild.id))
            
            # Set owner ID
            logger.info(f'Setting owner ID in config: {guild.owner_id}')
            bot.config_manager.set('discord.owner_id', str(guild.owner_id))
            
            bot.config_manager.save()
            guild_id = str(guild.id)
        else:
            logger.warning('No server ID configured and bot is not in any guilds')
            return
    
    try:
        guild = bot.get_guild(int(guild_id))
        if guild:
            # Update owner ID if it changed
            current_owner_id = bot.config_manager.get('discord.owner_id')
            if str(guild.owner_id) != current_owner_id:
                logger.info(f'Updating owner ID in config: {guild.owner_id}')
                bot.config_manager.set('discord.owner_id', str(guild.owner_id))
                bot.config_manager.save()
            
            await bot.setup_guild(guild)
        else:
            logger.error(f'Could not find guild with ID: {guild_id}')
            return
    except ValueError as e:
        logger.error(f'Invalid guild ID in config: {guild_id}')
        return
    
    try:
        # Initial permissions check
        permissions_ok, issues = await check_bot_permissions(guild)
        if not permissions_ok:
            logger.error(f"Permission issues detected: {issues}")
            # Continue anyway to try setting up what we can
        
        # Set up roles first
        role_ids = await setup_roles(guild)
        if role_ids:
            # Update config with role IDs
            for key, role_id in role_ids.items():
                bot.config_manager.set(f'discord.{key}', role_id)
            bot.config_manager.save()
        
        # Then set up channels
        channel_ids = await setup_channels(guild)
        if channel_ids:
            # Update config with channel IDs
            for key, channel_id in channel_ids.items():
                bot.config_manager.set(f'discord.{key}', channel_id)
            bot.config_manager.save()
        
        # Get admin channel for status messages
        admin_channel = None
        admin_channel_id = channel_ids.get('factorio_admin_channel_id')
        if admin_channel_id and admin_channel_id.isdigit():
            admin_channel = guild.get_channel(int(admin_channel_id))
        
        if admin_channel:
            # Send setup status
            setup_status = []
            setup_status.append("✅ Channels configured successfully" if channel_ids else "❌ Channel setup failed")
            setup_status.append("✅ Roles configured successfully" if role_ids else "❌ Role setup failed")
            
            if not permissions_ok:
                setup_status.append("⚠️ Permission issues detected")
            
            await send_status_message(
                admin_channel,
                "Bot Start Up Status",
                "\n".join(setup_status),
                discord.Color.green() if all(setup_status) else discord.Color.orange()
            )
        
        # Sync the commands globally
        try:
            await bot.tree.sync()
            logger.info('Synced commands globally')
        except Exception as e:
            logger.error(f'Failed to sync commands: {e}')
        
    except Exception as e:
        logger.error(f'Error during setup: {e}')
        traceback.print_exc()

@bot.event
async def on_guild_role_delete(role):
    """Handles recreation of essential roles if they are deleted"""
    guild = role.guild
    role_id = str(role.id)
    
    # Check if the deleted role was one of our managed roles
    managed_roles = {
        'discord.factorio_admin_role_id': 'factorio_admin',
        'discord.factorio_mod_id': 'factorio_mod',
        'discord.factorio_user_id': 'factorio_user'
    }
    
    for config_key, role_key in managed_roles.items():
        if bot.config_manager.get(config_key) == role_id:
            logger.warning(f'Managed role {role.name} was deleted. Triggering recreation...')
            try:
                # Trigger role setup to recreate all roles and restore assignments
                role_ids = await setup_roles(guild)
                
                # Update config with new role IDs
                for key, new_id in role_ids.items():
                    bot.config_manager.set(f'discord.{key}', new_id)
                bot.config_manager.save()
                
                logger.info('Role recreation complete')
            except Exception as e:
                logger.error(f'Failed to recreate role: {e}')
                traceback.print_exc()
            break

@bot.event
async def on_guild_channel_delete(channel):
    """Handles recreation of essential channels if they are deleted"""
    guild = channel.guild
    
    # Check if the deleted channel was one of our managed channels
    channel_id = str(channel.id)
    managed_channels = {
        'discord.factorio_general_channel_id': 'factorio_general',
        'discord.factorio_admin_channel_id': 'factorio_admin'
    }
    
    for config_key, channel_key in managed_channels.items():
        if bot.config_manager.get(config_key) == channel_id:
            logger.warning(f'Managed channel {channel.name} was deleted. Triggering recreation...')
            try:
                # Trigger channel setup to recreate the deleted channel
                channel_ids = await setup_channels(guild)
                
                # Update config with new channel IDs
                for key, new_id in channel_ids.items():
                    bot.config_manager.set(f'discord.{key}', new_id)
                bot.config_manager.save()
                
                logger.info('Channel recreation complete')
            except Exception as e:
                logger.error(f'Failed to recreate channel: {e}')
                traceback.print_exc()
            break



# Set up cog watcher
cog_watcher = CogWatcher(bot)
observer = Observer()
observer.schedule(cog_watcher, path='cogs', recursive=False)
observer.daemon = True  # Make the observer thread a daemon thread
observer.start()

if __name__ == "__main__":
    # Check and setup service if needed
    ensure_service_running()
    
    try:
        asyncio.run(load_cogs())
        bot.run(config_manager.get('discord.bot_token'))
    finally:
        observer.stop()
        observer.join()