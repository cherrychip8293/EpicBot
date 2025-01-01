from datetime import datetime
from discord import Interaction, Embed, app_commands
from discord.ext import commands
import discord
import pytz
import logging
from typing import Optional
from event.GoogleSheetsManager import GoogleSheetsManager

# Google Sheets 설정
SERVICE_ACCOUNT_FILE = 'resources/service_account.json'
SPREADSHEET_ID = '1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE'
LOG_CHANNEL_ID = 1320605395676299305

seoul_tz = pytz.timezone("Asia/Seoul")

class InfoChangeView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

        button = discord.ui.Button(
            label="정보 변경",
            style=discord.ButtonStyle.green,
            custom_id="info_change_button"
        )
        button.callback = self.change_info
        self.add_item(button)

    async def change_info(self, interaction: Interaction):
        modal = InfoChangeModal(self.sheets_manager)
        await interaction.response.send_modal(modal)

class InfoChangeModal(discord.ui.Modal, title="정보 변경"):
    def __init__(self, sheets_manager):
        super().__init__()
        self.sheets_manager = sheets_manager

        self.old_nickname = discord.ui.TextInput(
            label="이전 닉네임",
            placeholder="태그 포함된 이전 닉네임을 입력하세요",
            required=True
        )
        self.new_nickname = discord.ui.TextInput(
            label="변경된 닉네임",
            placeholder="태그 포함된 변경 후 닉네임을 입력하세요",
            required=True
        )
        self.new_tier = discord.ui.TextInput(
            label="변경된 티어",
            placeholder="변경 후 티어를 입력하세요",
            required=True
        )
        self.reason = discord.ui.TextInput(
            label="변경 사유",
            placeholder="변경 사유를 입력하세요",
            required=True,
            style=discord.TextStyle.long
        )

        self.add_item(self.old_nickname)
        self.add_item(self.new_nickname)
        self.add_item(self.new_tier)
        self.add_item(self.reason)

    async def on_submit(self, interaction: Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            old_nickname = self.old_nickname.value.strip()
            new_nickname = self.new_nickname.value.strip()
            new_tier = self.new_tier.value.strip()
            reason = self.reason.value.strip()

            logging.info(f"정보 변경 시도: old={old_nickname}, new={new_nickname}, tier={new_tier}")

            member_data = self.sheets_manager.get_values(sheet_name="MEMBER", range_notation="A:Z")
            if not member_data:
                logging.error("멤버 데이터를 가져올 수 없습니다.")
                await interaction.followup.send("멤버 데이터를 가져올 수 없습니다.", ephemeral=True)
                return

            # D열(닉네임)에서 해당 멤버 찾기
            target_row = None
            for row_idx, row in enumerate(member_data, start=1):
                if len(row) >= 4 and row[3].strip() == old_nickname:  # D열은 인덱스 3
                    target_row = row_idx
                    break

            if not target_row:
                logging.warning(f"멤버를 찾을 수 없음: {old_nickname}")
                await interaction.followup.send("해당 닉네임을 가진 멤버를 찾을 수 없습니다.", ephemeral=True)
                return

            try:
                # D열에 새 닉네임 업데이트
                self.sheets_manager.update_cell(
                    sheet_name="MEMBER",
                    start_column="D",
                    start_row=target_row,
                    values=[[new_nickname]]
                )

                # E열에 새 티어 업데이트
                self.sheets_manager.update_cell(
                    sheet_name="MEMBER",
                    start_column="E",
                    start_row=target_row,
                    values=[[new_tier]]
                )

                await interaction.followup.send(
                    f"'{old_nickname}' 닉네임이 '{new_nickname}'(으)로, 티어가 '{new_tier}'(으)로 성공적으로 변경되었습니다.",
                    ephemeral=True
                )

                # 로그 채널에 기록
                if interaction.guild:
                    log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
                    if isinstance(log_channel, discord.TextChannel):
                        current_time = datetime.now(seoul_tz)
                        embed = Embed(
                            title="정보 변경 로그",
                            description=f"**변경자**: {interaction.user.mention}",
                            color=0x00FF00
                        )
                        embed.add_field(name="이전 닉네임", value=f"`{old_nickname}`", inline=False)
                        embed.add_field(name="변경된 닉네임", value=f"`{new_nickname}`", inline=False)
                        embed.add_field(name="변경된 티어", value=f"`{new_tier}`", inline=False)
                        embed.add_field(name="사유", value=f"`{reason}`", inline=False)
                        embed.set_footer(text=f"요청자: {interaction.user.display_name}\n{current_time.strftime('%Y-%m-%d %H:%M:%S')}")

                        await log_channel.send(embed=embed)

            except Exception as e:
                logging.error(f"시트 업데이트 중 오류 발생: {e}", exc_info=True)
                await interaction.followup.send("정보 업데이트 중 오류가 발생했습니다.", ephemeral=True)

        except Exception as e:
            logging.error(f"정보 변경 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("정보 변경 중 오류가 발생했습니다. 관리자에게 문의해주세요.", ephemeral=True)
            
class InfoCommands(commands.GroupCog, group_name="정보"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self.sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

    @app_commands.command(name="변경메시지")
    @app_commands.guild_only()
    @app_commands.describe(channel="메시지를 보낼 채널을 선택하세요")
    async def send_info_change_message(self, interaction: Interaction, channel: Optional[discord.TextChannel]):
        try:
            if not interaction.guild_id:
                await interaction.response.send_message("이 명령어는 서버에서만 사용할 수 있습니다.", ephemeral=True)
                return

            if not channel:
                await interaction.response.send_message("메시지를 보낼 채널을 선택하세요.", ephemeral=True)
                return

            embed = Embed(
                title="정보 변경 안내",
                description="정보를 변경하려면 아래 버튼을 클릭하세요.\n**닉네임 또는 탑 레이팅 갱신시 사용해주세요.**",
                color=discord.Color.blue()
            )

            view = InfoChangeView()
            await channel.send(embed=embed, view=view)

            await interaction.response.send_message(
                f"{channel.mention} 채널에 정보 변경 메시지를 전송했습니다.", ephemeral=True
            )
            
        except Exception as e:
            logging.error(f"정보 변경 메시지 전송 중 오류 발생: {e}", exc_info=True)
            await interaction.response.send_message(
                "메시지 전송 중 오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(InfoCommands(bot))