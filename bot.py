import os
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import asyncio
import traceback
import logging
from typing import Optional
import time
from config_manager import ConfigManager
from logger import setup_logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


# Initialize ConfigManager
config_manager = ConfigManager('config.json')

# Set up logger
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
logger = setup_logger('bot', os.path.join(log_dir, 'bot.log'))

class CogWatcher(FileSystemEventHandler):
    def __init__(self, bot):
        self.bot = bot
        self.last_modified = {}
        
    def should_reload(self, path):
        # Prevent reloading too frequently (debounce)
        current_time = time.time()
        if path in self.last_modified:
            if current_time - self.last_modified[path] < 1:  # 1 second debounce
                return False
        self.last_modified[path] = current_time
        return True

    async def reload_cog(self, path):
        try:
            relative_path = os.path.relpath(path)
            if relative_path.startswith('cogs/') and relative_path.endswith('.py'):
                cog_name = relative_path[:-3].replace('/', '.')  # Remove .py and convert path to module format
                logger.info(f"Reloading {cog_name}...")
                
                try:
                    await self.bot.reload_extension(cog_name)
                    logger.info(f"Successfully reloaded {cog_name}")
                except Exception as e:
                    logger.error(f"Failed to reload {cog_name}: {e}")
        except Exception as e:
            logger.error(f"Error in reload_cog: {e}")

    def on_modified(self, event):
        if event.src_path.endswith('.py') and 'cogs' in event.src_path:
            if self.should_reload(event.src_path):
                asyncio.run_coroutine_threadsafe(
                    self.reload_cog(event.src_path), 
                    self.bot.loop
                )

class AutoReconnectBot(commands.Bot):
    async def setup_hook(self):
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        self.reconnect_delay = 5  # Initial delay in seconds

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
        'factorio_admin': {
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
        'factorio_general': {
            'name': 'factorio-general',
            'topic': 'General Factorio discussion, commands, and game logs',
            'category_name': 'Factorio',
            'permissions': {
                'view': True,  # Everyone can view
                'admin_only': False
            }
        },
        'factorio_admin': {
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
        admin_role_id = bot.config_manager.get('discord.factorio_admin_id')
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


# Event Handlers
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name}')
    
    # Get the guild ID from config
    guild_id = bot.config_manager.get('discord.server_id')
    if not guild_id:
        logger.error('No server ID configured')
        return
        
    guild = bot.get_guild(int(guild_id))
    if not guild:
        logger.error(f'Could not find guild with ID: {guild_id}')
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
        admin_channel_id = channel_ids.get('factorio_admin_id')
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
                "Bot Setup Status",
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
        'discord.factorio_admin_id': 'factorio_admin',
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
        'discord.factorio_general_id': 'factorio_general',
        'discord.factorio_admin_id': 'factorio_admin'
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
observer.start()

try:
    asyncio.run(load_cogs())
    bot.run(config_manager.get('discord.bot_token'))
finally:
    observer.stop()
    observer.join()