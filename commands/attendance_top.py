import logging
from discord.ext import commands
from discord import app_commands
import discord
import json
import os
from typing import Dict, Any
from .base_command import BaseCommandCog

GUILD_ID = int(os.getenv("GUILD_ID"))
DATA_FILE = "attendance_data.json"

# 데이터 파일 로드
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        attendance = json.load(f)
else:
    attendance = {}

class Paginator(discord.ui.View):
    def __init__(self, embeds):
        super().__init__(timeout=None)
        self.embeds = embeds
        self.current_page = 0

        self.prev_button = discord.ui.Button(label="⬅️ 이전", style=discord.ButtonStyle.primary)
        self.page_label = discord.ui.Button(label=f"{self.current_page + 1}/{len(self.embeds)}", style=discord.ButtonStyle.secondary, disabled=True)
        self.next_button = discord.ui.Button(label="➡️ 다음", style=discord.ButtonStyle.primary)

        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        self.add_item(self.prev_button)
        self.add_item(self.page_label)
        self.add_item(self.next_button)

        self.update_buttons_state()

    def update_buttons_state(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.embeds) - 1
        self.page_label.label = f"{self.current_page + 1}/{len(self.embeds)}"

    async def update_message(self, interaction):
        self.update_buttons_state()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    async def prev_page(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("현재 페이지가 첫 번째 페이지입니다.", ephemeral=True)

    async def next_page(self, interaction: discord.Interaction):
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("현재 페이지가 마지막 페이지입니다.", ephemeral=True)


class RankingCommands(commands.Cog):  # BaseCommandCog 대신 commands.Cog 사용
    def __init__(self, bot):
        self.bot = bot
        self.DATA_FILE = DATA_FILE

    def load_attendance_data(self) -> Dict[str, Any]:
        if os.path.exists(self.DATA_FILE):
            try:
                with open(self.DATA_FILE, "r", encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print("JSON 파일 읽기 오류. 빈 데이터로 초기화합니다.")
                return {}
        return {}

    @commands.command(name="순위")
    async def rank_prefix(self, ctx):
        await self._handle_ranking(ctx)

    @app_commands.command(name="순위", description="출석 순위를 확인합니다.")
    async def rank_slash(self, interaction: discord.Interaction):
        await self._handle_ranking(interaction)

    async def _handle_ranking(self, ctx_or_interaction):
        is_interaction = isinstance(ctx_or_interaction, discord.Interaction)
        if is_interaction:
            await ctx_or_interaction.response.defer()
        
        attendance = self.load_attendance_data()

        if not attendance:
            message = "아직 출석 기록이 없습니다!"
            if is_interaction:
                await ctx_or_interaction.followup.send(message)
            else:
                await ctx_or_interaction.send(message)
            return

        try:
            sorted_attendance = sorted(
                attendance.items(),
                key=lambda x: x[1].get("count", 0) if isinstance(x[1], dict) else 0,
                reverse=True
            )

            embeds = []
            embed = discord.Embed(
                title="📊 출석 순위",
                description="출석 횟수에 따른 순위입니다.",
                color=discord.Color.blue()
            )

            guild = ctx_or_interaction.guild
            for rank, (user_id, data) in enumerate(sorted_attendance, start=1):
                try:
                    member = await guild.fetch_member(int(user_id))
                    if member:
                        count = data.get("count", 0) if isinstance(data, dict) else 0
                        rank_display = "👑 1위" if rank == 1 else f"{rank}위"
                        embed.add_field(name=rank_display, value=f"{member.display_name} - {count}회", inline=False)

                        if rank % 10 == 0:
                            embeds.append(embed)
                            embed = discord.Embed(
                                title="📊 출석 순위",
                                description="출석 횟수에 따른 순위입니다.",
                                color=discord.Color.blue()
                            )
                except (discord.NotFound, discord.HTTPException):
                    continue

            if len(embed.fields) > 0:
                embeds.append(embed)

            if not embeds:
                message = "표시할 순위가 없습니다."
                if is_interaction:
                    await ctx_or_interaction.followup.send(message)
                else:
                    await ctx_or_interaction.send(message)
                return

            view = Paginator(embeds)
            if len(embeds) == 1:
                if is_interaction:
                    await ctx_or_interaction.followup.send(embed=embeds[0])
                else:
                    await ctx_or_interaction.send(embed=embeds[0])
            else:
                if is_interaction:
                    await ctx_or_interaction.followup.send(embed=embeds[0], view=view)
                else:
                    await ctx_or_interaction.send(embed=embeds[0], view=view)

        except Exception as e:
            error_msg = f"순위를 가져오는 중 오류가 발생했습니다: {e}"
            if is_interaction:
                await ctx_or_interaction.followup.send(error_msg)
            else:
                await ctx_or_interaction.send(error_msg)

async def setup(bot: commands.Bot):
    await bot.add_cog(RankingCommands(bot))
    logging.info("RankingCommands cog added to bot")  # 로그 추가