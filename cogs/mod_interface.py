import discord
from discord.ext import commands
from discord import app_commands
import logging
import asyncio
from typing import Dict, List, Optional

logger = logging.getLogger('mod_interface')

class ModInterfaceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config_manager = bot.config_manager
        logger.info("ModInterfaceCog initialized")

    async def handle_mod_mismatch(self, interaction: discord.Interaction, mod_name: str, local_info: Dict, portal_info: Dict) -> bool:
        """Handle mod author mismatch with user interaction."""
        embed = discord.Embed(
            title="Mod Author Mismatch",
            description=f"The mod '{mod_name}' has different authors in local files and on the mod portal.",
            color=discord.Color.yellow()
        )
        
        embed.add_field(
            name="Local Version",
            value=f"Author: {local_info['author']}\n"
                  f"Version: {local_info['version']}\n"
                  f"Title: {local_info['title']}",
            inline=True
        )
        
        embed.add_field(
            name="Portal Version",
            value=f"Author: {portal_info['owner']}\n"
                  f"Version: {portal_info['releases'][-1]['version']}\n"
                  f"Title: {portal_info.get('title', 'Unknown')}",
            inline=True
        )

        # Create view with options
        view = discord.ui.View(timeout=60)
        
        # Use Future to get the result
        future = asyncio.Future()
        
        async def button_callback(interaction: discord.Interaction, confirmed: bool):
            if not future.done():
                future.set_result(confirmed)
                await interaction.response.edit_message(
                    content=f"{'Confirmed' if confirmed else 'Skipped'} mod: {mod_name}",
                    embed=None,
                    view=None
                )

        class CorrectURLModal(discord.ui.Modal):
            def __init__(self):
                super().__init__(title="Provide Correct Mod URL")
                self.url = discord.ui.TextInput(
                    label="Correct Mod Portal URL",
                    placeholder="https://mods.factorio.com/mod/mod_name",
                    style=discord.TextStyle.short,
                    required=True,
                    min_length=1,
                    max_length=200
                )
                self.add_item(self.url)

            async def on_submit(self, interaction: discord.Interaction):
                url = self.url.value.strip()
                if not url.startswith("https://mods.factorio.com/mod/"):
                    await interaction.response.send_message(
                        "Invalid URL. Must be a Factorio mod portal URL.",
                        ephemeral=True
                    )
                    return

                mod_name = url.split('/')[-1]
                mods_cog = interaction.client.get_cog('ModsCog')
                if not mods_cog:
                    await interaction.response.send_message(
                        "Mod system not available.",
                        ephemeral=True
                    )
                    return

                # Verify the URL points to a valid mod
                mod_details = await mods_cog.get_mod_details(mod_name)
                if not mod_details:
                    await interaction.response.send_message(
                        "Could not find mod at the provided URL.",
                        ephemeral=True
                    )
                    return

                if not future.done():
                    # Store the URL for future updates
                    # Note: You'll need to implement the store_mod_url method in your ModsCog
                    await mods_cog.store_mod_url(mod_name, url)
                    future.set_result(True)
                    await interaction.response.edit_message(
                        content=f"Updated mod URL for {mod_name}",
                        embed=None,
                        view=None
                    )

        async def correct_url_callback(interaction: discord.Interaction):
            await interaction.response.send_modal(CorrectURLModal())

        # Add buttons
        confirm_button = discord.ui.Button(
            label="Yes, they're the same mod",
            style=discord.ButtonStyle.green,
            custom_id="confirm"
        )
        confirm_button.callback = lambda i: button_callback(i, True)
        
        skip_button = discord.ui.Button(
            label="No, skip this mod",
            style=discord.ButtonStyle.red,
            custom_id="skip"
        )
        skip_button.callback = lambda i: button_callback(i, False)

        correct_url_button = discord.ui.Button(
            label="Provide Correct URL",
            style=discord.ButtonStyle.blurple,
            custom_id="correct_url"
        )
        correct_url_button.callback = correct_url_callback

        view.add_item(confirm_button)
        view.add_item(skip_button)
        view.add_item(correct_url_button)

        # Send verification message
        prompt_msg = await interaction.channel.send(embed=embed, view=view)

        try:
            result = await asyncio.wait_for(future, timeout=60.0)
            return result
        except asyncio.TimeoutError:
            await prompt_msg.edit(
                content=f"Verification timed out for {mod_name}, skipping...",
                embed=None,
                view=None
            )
            return False

    @app_commands.command(name="update_mods", description="Check for and install mod updates")
    @app_commands.default_permissions(administrator=True)
    async def update_mods(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        mods_cog = self.bot.get_cog('ModsCog')
        if not mods_cog:
            await interaction.followup.send("Mod management system is not available.", ephemeral=True)
            return

        # Get installed mods
        installed_mods = mods_cog.get_installed_mods()
        if not installed_mods:
            await interaction.followup.send("No mods are currently installed.", ephemeral=True)
            return

        # Check each mod for updates
        updates_available = []
        for mod_name in installed_mods:
            local_info = mods_cog.get_installed_version(mod_name)
            if not local_info:
                continue

            mod_details = await mods_cog.get_mod_details(mod_name)
            if not mod_details:
                continue

            latest_version = mod_details['releases'][-1]['version']
            if latest_version != local_info['version']:
                # Verify author if possible
                portal_author = mod_details.get('owner')
                local_author = local_info.get('author')
                
                if portal_author and local_author and portal_author != local_author:
                    logger.warning(f"Author mismatch for {mod_name}: Local={local_author}, Portal={portal_author}")
                    is_same_mod = await self.handle_mod_mismatch(
                        interaction,
                        mod_name,
                        local_info,
                        mod_details
                    )
                    if not is_same_mod:
                        continue

                updates_available.append({
                    'name': mod_name,
                    'current_version': local_info['version'],
                    'latest_version': latest_version,
                    'author': local_info.get('author', 'Unknown'),
                    'title': local_info.get('title', mod_name),
                    'description': mod_details.get('summary', local_info.get('description', 'No description available')),
                    'url': f"https://mods.factorio.com/mod/{mod_name}"
                })

        if not updates_available:
            await interaction.followup.send("All mods are up to date!", ephemeral=True)
            return

        # Create verification embed
        verify_embed = discord.Embed(
            title="Update Verification",
            description="Please verify the following updates before proceeding:",
            color=discord.Color.yellow()
        )

        verify_embed.add_field(
            name="Total Updates Available",
            value=f"{len(updates_available)} mod(s) can be updated",
            inline=False
        )

        for mod in updates_available:
            description = mod['description']
            if len(description) > 100:
                description = description[:97] + "..."

            field_value = (
                f"Title: {mod['title']}\n"
                f"Author: {mod['author']}\n"
                f"Current Version: `{mod['current_version']}`\n"
                f"Portal Version: `{mod['latest_version']}`\n"
                f"Description: {description}\n"
                f"[View on Mod Portal]({mod['url']})"
            )
            verify_embed.add_field(
                name=f"📦 {mod['name']}",
                value=field_value,
                inline=False
            )

        # Create buttons for confirmation
        view = discord.ui.View()
        confirm_button = discord.ui.Button(
            label="Confirm Update",
            style=discord.ButtonStyle.green,
            custom_id="confirm_update"
        )
        abort_button = discord.ui.Button(
            label="Abort Update",
            style=discord.ButtonStyle.red,
            custom_id="abort_update"
        )

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()
            
            progress_embed = discord.Embed(
                title="Update Progress",
                description="Beginning mod updates...",
                color=discord.Color.blue()
            )
            progress_msg = await interaction.followup.send(embed=progress_embed)

            results = []
            for index, mod in enumerate(updates_available, 1):
                try:
                    progress_embed.description = f"Updating mod {index}/{len(updates_available)}: {mod['name']}"
                    await progress_msg.edit(embed=progress_embed)

                    success = await mods_cog.install_mod(mod['url'])
                    if success:
                        results.append(f"✅ Updated {mod['name']} to version {mod['latest_version']}")
                    else:
                        results.append(f"❌ Failed to update {mod['name']}")
                except Exception as e:
                    results.append(f"❌ Error updating {mod['name']}: {str(e)}")
                    logger.error(f"Error updating mod {mod['name']}: {str(e)}")

            results_embed = discord.Embed(
                title="Update Results",
                description="\n".join(results),
                color=discord.Color.green() if all("✅" in r for r in results) else discord.Color.red()
            )
            
            success_count = sum(1 for r in results if "✅" in r)
            results_embed.add_field(
                name="Summary",
                value=f"Successfully updated {success_count} out of {len(updates_available)} mods",
                inline=False
            )

            await progress_msg.edit(embed=results_embed)

        async def abort_callback(interaction: discord.Interaction):
            abort_embed = discord.Embed(
                title="Update Aborted",
                description="Mod update process has been cancelled.",
                color=discord.Color.grey()
            )
            await interaction.response.edit_message(embed=abort_embed, view=None)
            logger.info("Mod update process aborted by user")

        confirm_button.callback = confirm_callback
        abort_button.callback = abort_callback

        view.add_item(confirm_button)
        view.add_item(abort_button)

        await interaction.followup.send(
            embed=verify_embed,
            view=view
        )

    @app_commands.command(name="sync_mods", description="Scan and sync installed mods with the tracking system")
    @app_commands.default_permissions(administrator=True)
    async def sync_mods(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        mods_cog = self.bot.get_cog('ModsCog')
        if not mods_cog:
            await interaction.followup.send("Mod management system is not available.", ephemeral=True)
            return

        progress_embed = discord.Embed(
            title="Mod Sync Progress",
            description="Scanning installed mods...",
            color=discord.Color.blue()
        )
        progress_msg = await interaction.followup.send(embed=progress_embed)

        try:
            local_mods = mods_cog.get_installed_mods()
            if not local_mods:
                await progress_msg.edit(content="No mods found to sync.", embed=None)
                return

            results = {
                'synced': [],
                'failed': [],
                'mismatch': []
            }

            total_mods = len(local_mods)
            for index, mod_name in enumerate(local_mods, 1):
                progress_embed.description = f"Processing mod {index}/{total_mods}: {mod_name}"
                await progress_msg.edit(embed=progress_embed)

                try:
                    local_info = mods_cog.get_installed_version(mod_name)
                    if not local_info:
                        results['failed'].append(f"{mod_name} (No local info found)")
                        continue

                    mod_details = await mods_cog.get_mod_details(mod_name)
                    if not mod_details:
                        results['failed'].append(f"{mod_name} (Not found on portal)")
                        continue

                    # Verify author if possible
                    portal_author = mod_details.get('owner')
                    local_author = local_info.get('author')
                    
                    if portal_author and local_author and portal_author != local_author:
                        logger.info(f"Author mismatch found for {mod_name}, prompting user")
                        is_same_mod = await self.handle_mod_mismatch(
                            interaction,
                            mod_name,
                            local_info,
                            mod_details
                        )
                        if is_same_mod:
                            results['synced'].append(f"{mod_name} (v{local_info['version']})")
                        else:
                            results['mismatch'].append(f"{mod_name} (Author mismatch: Local={local_author}, Portal={portal_author})")
                        continue

                    results['synced'].append(f"{mod_name} (v{local_info['version']})")

                except Exception as e:
                    results['failed'].append(f"{mod_name} (Error: {str(e)})")

            # Create final report embed
            report_embed = discord.Embed(
                title="Mod Sync Report",
                color=discord.Color.green() if not results['failed'] and not results['mismatch'] else discord.Color.orange()
            )

            if results['synced']:
                report_embed.add_field(
                    name="✅ Successfully Synced",
                    value="\n".join(results['synced']) if len(results['synced']) < 10 else 
                          f"{len(results['synced'])} mods synced successfully",
                    inline=False
                )

            if results['mismatch']:
                report_embed.add_field(
                    name="⚠️ Author Mismatch",
                    value="\n".join(results['mismatch']),
                    inline=False
                )

            if results['failed']:
                report_embed.add_field(
                    name="❌ Failed to Sync",
                    value="\n".join(results['failed']) if len(results['failed']) < 10 else
                          f"{len(results['failed'])} mods failed to sync",
                    inline=False
                )

            await progress_msg.edit(embed=report_embed)

        except Exception as e:
            error_embed = discord.Embed(
                title="Error During Sync",
                description=f"An error occurred: {str(e)}",
                color=discord.Color.red()
            )
            await progress_msg.edit(embed=error_embed)
            logger.error(f"Error during mod sync: {str(e)}")

async def setup(bot):
    await bot.add_cog(ModInterfaceCog(bot))
    logger.info("ModInterfaceCog added to bot")